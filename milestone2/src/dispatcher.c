/*
 * dispatcher.c - Milestone 2 integrated reference dispatcher.
 * Supplied in Ahmad/Sheryar's AI-assisted handoff; integration revisions are
 * documented in docs/CHANGES.md. This is distinct from Mostafa's initial code.
 * CSC 720 Project 03: Adaptive Background Queue Depth for HDDs.
 *
 * One read-only user-space dispatcher shared by every policy. It runs small
 * 4 KiB foreground (FG) reads from an arrival trace and a sequential
 * background (BG) scan on the same disk, through io_uring with O_DIRECT.
 *
 *   - two pending queues (FG bounded: a full queue REJECTS and logs; BG kept
 *     topped up by the scanner)
 *   - FG quota: at most --fg-quota FG reads in flight (same for every policy)
 *   - BG limit q: at most q BG reads in flight; q comes from the policy
 *   - per-request timestamps: arrival, submit, complete (CLOCK_MONOTONIC ns)
 *   - every returned 4 KiB block is checked against the test-file pattern
 *   - completion accounting: every accepted request ends exactly once as OK,
 *     ERR or UNSUBMITTED; submitted reads are never cancelled
 *   - clean shutdown on time-out or SIGINT/SIGTERM: stop arrivals and the
 *     scanner, drain every in-flight read, then check the counters
 *
 * Logs (format v2, see docs/log_format.md): <out>/run_meta.json,
 * <out>/requests.csv, <out>/windows.csv.
 *
 * Build: make            Run: bin/dispatcher --help
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <limits.h>
#include <math.h>
#include <liburing.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#include "dispatcher.h"
#include "submission.h"

#define BLOCK 4096u
#define MAGIC 0x5453455451444448ull   /* "HDDQTEST" */
#define GOLDEN 0x9E3779B97F4A7C15ull
#define MAX_LEVEL 8
#define MAX_FG_QUOTA 64

/* ------------------------------------------------------------------ util */

static struct timespec g_t0;
static volatile sig_atomic_t g_stop_signal = 0;

static uint64_t now_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)(t.tv_sec - g_t0.tv_sec) * 1000000000ull +
           (uint64_t)t.tv_nsec - (uint64_t)g_t0.tv_nsec;
}

static uint64_t cpu_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}

static void on_signal(int sig) { (void)sig; g_stop_signal = 1; }

static void die(const char *msg)
{
    fprintf(stderr, "dispatcher: %s\n", msg);
    exit(1);
}

/* ------------------------------------------------------------ verification */

/* Returns 1 if every 4 KiB block of buf (n bytes, starting at file offset off)
 * matches the pattern written by tools/make_testfiles.py. */
static int verify_blocks(const void *buf, uint32_t n, uint64_t off, uint64_t file_id)
{
    if (n % BLOCK || off % BLOCK) return 0;
    const uint64_t *w = buf;
    for (uint32_t b = 0; b < n / BLOCK; b++, w += BLOCK / 8) {
        uint64_t blk = off / BLOCK + b;
        if (w[0] != MAGIC || w[1] != file_id || w[2] != blk) return 0;
        uint64_t filler = blk * GOLDEN + file_id;
        for (unsigned i = 3; i < BLOCK / 8; i++)
            if (w[i] != filler) return 0;
    }
    return 1;
}

/* ---------------------------------------------------------------- queues */

static void q_push(struct pending_queue *q, struct request *r)
{
    r->next = NULL;
    if (q->tail) q->tail->next = r; else q->head = r;
    q->tail = r;
    q->len++;
}

static struct request *q_pop(struct pending_queue *q)
{
    struct request *r = q->head;
    if (!r) return NULL;
    q->head = r->next;
    if (!q->head) q->tail = NULL;
    q->len--;
    r->next = NULL;
    return r;
}

/* ---------------------------------------------------------------- policy */

/* Fixed policy: q never changes. The adaptive policy (Milestone 3) plugs in
 * through the same next_q() hook, so every policy pays the same overhead. */
static uint16_t fixed_next_q(void *state, const struct window_stats *w,
                             enum ctrl_action *action)
{
    (void)state;
    *action = ACT_HOLD;
    return w->q_config;
}

static const char *action_name(enum ctrl_action a)
{
    switch (a) {
    case ACT_UP: return "UP";
    case ACT_DOWN: return "DOWN";
    case ACT_SPARSE: return "SPARSE";
    default: return "HOLD";
    }
}

/* ------------------------------------------------------------ dispatcher */

struct run {
    struct dispatcher_cfg c;
    struct io_uring ring;
    int fg_fd, bg_fd;
    uint64_t fg_size, bg_size;

    /* trace */
    uint64_t *tr_t, *tr_off;
    size_t tr_n, tr_next;

    struct pending_queue fg_q, bg_q;
    uint16_t fg_out, bg_out, q;
    struct policy pol;
    uint64_t next_id, next_bg_offset, scan_wraps;

    /* counters for the exactly-once check */
    uint64_t accepted, rejected, submitted, completed_ok, completed_err, unsubmitted;
    uint64_t fg_ok, bg_ok, verify_fail;
    uint64_t fg_admitted, fg_expected;
    uint64_t scan_bytes_total;

    /* current window */
    uint64_t win_idx, win_start, bg_area, bg_last_change;
    uint16_t bg_out_max;
    uint32_t win_fg_samples, win_fg_misses;
    uint32_t streak;

    /* free lists so buffers are reused */
    struct request *free_fg, *free_bg;

    FILE *req_log, *win_log;
    int stopping;
    int arrivals_closed;
    int early_stop;
};

static void advance_windows(struct run *R, uint64_t t);

static struct request *req_alloc(struct run *R, enum req_class cls)
{
    struct request **fl = cls == REQ_FG ? &R->free_fg : &R->free_bg;
    struct request *r = *fl;
    uint32_t len = cls == REQ_FG ? BLOCK : R->c.chunk_bytes;
    if (r) {
        *fl = r->next;
    } else {
        r = calloc(1, sizeof *r);
        if (!r || posix_memalign(&r->buf, BLOCK, len)) die("out of memory");
    }
    void *buf = r->buf;
    memset(r, 0, sizeof *r);
    r->buf = buf;
    r->cls = cls;
    r->len = len;
    r->id = R->next_id++;
    return r;
}

static void req_free(struct run *R, struct request *r)
{
    struct request **fl = r->cls == REQ_FG ? &R->free_fg : &R->free_bg;
    r->next = *fl;
    *fl = r;
}

static void log_request(struct run *R, const struct request *r, const char *status, int err)
{
    fprintf(R->req_log, "%llu,%s,%llu,%u,%llu,",
            (unsigned long long)r->id, r->cls == REQ_FG ? "FG" : "BG",
            (unsigned long long)r->offset, r->len, (unsigned long long)r->t_arrival);
    if (r->state == RS_SUBMITTED || r->state == RS_DONE)
        fprintf(R->req_log, "%llu,%llu,", (unsigned long long)r->t_submit,
                (unsigned long long)r->t_complete);
    else
        fputs(",,", R->req_log);
    fprintf(R->req_log, "%s,%d,%u,%u,%u,%u,%d,%llu,%llu\n", status, err, r->verified,
            r->q_at_submit, r->bg_out_at_submit, r->fg_out_at_submit,
            r->result > 0 ? r->result : 0,
            (unsigned long long)r->t_admit, (unsigned long long)r->t_verify);
    if (ferror(R->req_log)) die("request log write failed; run incomplete");
}

static void bg_area_until(struct run *R, uint64_t t)
{
    if (t < R->bg_last_change) die("window clock moved backwards");
    R->bg_area += (uint64_t)R->bg_out * (t - R->bg_last_change);
    R->bg_last_change = t;
}

static void bg_out_change(struct run *R, int delta)
{
    uint64_t t = now_ns();
    advance_windows(R, t);
    bg_area_until(R, t);
    R->bg_out = (uint16_t)(R->bg_out + delta);
    if (R->bg_out > R->bg_out_max) R->bg_out_max = R->bg_out;
}

/* FG arrivals whose trace time has come. A full FG queue rejects. */
static void admit_arrivals(struct run *R, uint64_t t)
{
    while (!R->stopping && !R->arrivals_closed && R->tr_next < R->tr_n &&
           R->tr_t[R->tr_next] <= t &&
           R->tr_t[R->tr_next] < R->c.warmup_ns + R->c.duration_ns) {
        struct request *r = req_alloc(R, REQ_FG);
        r->t_arrival = R->tr_t[R->tr_next];
        r->offset = R->tr_off[R->tr_next];
        R->tr_next++;
        if (R->fg_q.len >= R->c.fg_queue_cap) {
            r->state = RS_REJECTED;
            R->rejected++;
            log_request(R, r, "REJECTED", 0);
            req_free(R, r);
            continue;
        }
        r->state = RS_PENDING;
        r->t_admit = now_ns();
        R->accepted++;
        R->fg_admitted++;
        q_push(&R->fg_q, r);
    }
}

/* Keep the BG queue topped up with the next sequential chunks. The scan
 * wraps to its start at the end of the file so it lasts the whole run. */
static void top_up_scanner(struct run *R, uint64_t t)
{
    if (R->stopping || R->arrivals_closed || !R->c.scan) return;
    while (R->bg_q.len < R->c.bg_queue_cap) {
        if (R->next_bg_offset >= R->bg_size) {
            R->next_bg_offset = R->c.bg_start_offset;
            R->scan_wraps++;
        }
        struct request *r = req_alloc(R, REQ_BG);
        r->offset = R->next_bg_offset;
        r->t_arrival = t;
        r->state = RS_PENDING;
        r->t_admit = now_ns();
        R->next_bg_offset += R->c.chunk_bytes;
        R->accepted++;
        q_push(&R->bg_q, r);
    }
}

static void submit_one(struct run *R, struct request *r)
{
    struct io_uring_sqe *sqe = io_uring_get_sqe(&R->ring);
    if (!sqe) die("submission queue full (ring too small)");
    int fd = r->cls == REQ_FG ? R->fg_fd : R->bg_fd;
    /* Test hook: a request at --fault-offset is sent to an invalid file
     * descriptor, so the kernel returns a real error (-EBADF). */
    if (r->cls == REQ_FG && R->c.fault_offset != UINT64_MAX && r->offset == R->c.fault_offset)
        fd = -1;
    io_uring_prep_read(sqe, fd, r->buf, r->len, r->offset);
    io_uring_sqe_set_data(sqe, r);
    r->q_at_submit = R->q;
    r->bg_out_at_submit = R->bg_out;
    r->fg_out_at_submit = R->fg_out;
    r->t_submit = now_ns();
    r->state = RS_PREPARED;
    /* Reserve quota now; count submitted only after the kernel accepts it. */
    if (r->cls == REQ_FG) R->fg_out++; else bg_out_change(R, +1);
}

struct submission_context { struct run *run; struct request **prepared; };

static int submit_to_kernel(void *context)
{
    struct submission_context *c = context;
    return io_uring_submit(&c->run->ring);
}

static void mark_submitted(void *context, unsigned first, unsigned count)
{
    struct submission_context *c = context;
    for (unsigned i = first; i < first + count; i++) {
        c->prepared[i]->state = RS_SUBMITTED;
        c->run->submitted++;
    }
}

static int submit_ready(struct run *R)
{
    int n = 0;
    struct request *prepared[MAX_FG_QUOTA + MAX_LEVEL];
    if (R->stopping) return 0;
    while (R->fg_out < R->c.fg_quota && R->fg_q.len) {
        prepared[n] = q_pop(&R->fg_q); submit_one(R, prepared[n]); n++;
    }
    /* If q was lowered below bg_out, nothing is submitted until enough BG
     * reads finish; submitted reads are never cancelled. */
    while (R->bg_out < R->q && R->bg_q.len) {
        prepared[n] = q_pop(&R->bg_q); submit_one(R, prepared[n]); n++;
    }
    struct submission_context context = {R, prepared};
    if (m2_flush_batch((unsigned)n, submit_to_kernel, mark_submitted, &context))
        die("io_uring_submit made no progress or failed; run incomplete");
    return n;
}

static void complete_one(struct run *R, struct io_uring_cqe *cqe)
{
    struct request *r = io_uring_cqe_get_data(cqe);
    if (!r || r->state != RS_SUBMITTED) die("unexpected or duplicate completion");
    int res = cqe->res;
    r->t_complete = now_ns();
    advance_windows(R, r->t_complete);
    r->result = res;
    r->state = RS_DONE;
    if (r->cls == REQ_FG) R->fg_out--; else bg_out_change(R, -1);

    uint64_t size = r->cls == REQ_FG ? R->fg_size : R->bg_size;
    uint64_t want = r->offset >= size ? 0 : (size - r->offset < r->len ? size - r->offset : r->len);
    uint64_t fid = r->cls == REQ_FG ? R->c.fg_file_id : R->c.bg_file_id;
    int err = 0;
    if (res < 0) {
        err = -res;
    } else if ((uint64_t)res != want || want == 0) {
        err = EIO;                         /* short read or read past end */
    } else if (!verify_blocks(r->buf, (uint32_t)res, r->offset, fid)) {
        err = EBADMSG;                     /* bytes do not match the pattern */
        R->verify_fail++;
    } else {
        r->verified = 1;
    }
    r->t_verify = now_ns();

    if (err) {
        R->completed_err++;
        log_request(R, r, "ERR", err);
    } else {
        R->completed_ok++;
        if (r->cls == REQ_FG) {
            R->fg_ok++;
            R->win_fg_samples++;
            if (R->c.target_ms > 0 &&
                (double)(r->t_complete - r->t_arrival) > R->c.target_ms * 1e6)
                R->win_fg_misses++;
        } else {
            R->bg_ok++;
            R->scan_bytes_total += (uint64_t)res;
        }
        log_request(R, r, "OK", 0);
    }
    req_free(R, r);
}

static int reap(struct run *R, uint64_t wait_ns)
{
    struct io_uring_cqe *cqe;
    int n = 0;
    if (R->fg_out + R->bg_out == 0) {
        if (wait_ns) {
            struct timespec ts = { (time_t)(wait_ns / 1000000000ull), (long)(wait_ns % 1000000000ull) };
            nanosleep(&ts, NULL);
        }
        return 0;
    }
    if (wait_ns) {
        struct __kernel_timespec ts = { (long long)(wait_ns / 1000000000ull), (long long)(wait_ns % 1000000000ull) };
        int e = io_uring_wait_cqe_timeout(&R->ring, &cqe, &ts);
        if (e == -ETIME || e == -EINTR) return 0;
        if (e < 0) die("io_uring_wait_cqe_timeout failed");
    }
    while (io_uring_peek_cqe(&R->ring, &cqe) == 0) {
        complete_one(R, cqe);
        io_uring_cqe_seen(&R->ring, cqe);
        n++;
    }
    return n;
}

static void end_window(struct run *R, uint64_t t_end)
{
    struct window_stats w = {0};
    uint64_t len = t_end - R->win_start;
    if (!len) return;
    bg_area_until(R, t_end);                 /* exact nominal window boundary */
    w.win_idx = R->win_idx;
    w.t_start = R->win_start;
    w.t_end = t_end;
    w.fg_samples = R->win_fg_samples;
    w.fg_misses = R->win_fg_misses;
    w.q_config = R->q;
    w.bg_out_max = R->bg_out_max;
    w.bg_out_mean = len ? (double)R->bg_area / (double)len : 0;
    w.fg_pending_len = R->fg_q.len;
    w.bg_pending_len = R->bg_q.len;
    w.scan_bytes_total = R->scan_bytes_total;
    w.rejected_total = R->rejected;
    w.scanning = R->c.scan && !R->stopping;

    enum ctrl_action act;
    uint64_t c0 = cpu_ns();
    uint16_t nq = R->pol.next_q(R->pol.state, &w, &act);
    uint64_t ctrl = cpu_ns() - c0;

    fprintf(R->win_log, "%llu,%llu,%llu,%u,%u,%.4f,%u,%u,%u,",
            (unsigned long long)w.win_idx, (unsigned long long)w.t_start,
            (unsigned long long)w.t_end, w.q_config, w.bg_out_max, w.bg_out_mean,
            w.fg_pending_len, w.bg_pending_len, w.fg_samples);
    if (R->c.target_ms > 0) {
        fprintf(R->win_log, "%u,", w.fg_misses);
        if (w.fg_samples) fprintf(R->win_log, "%.6f,", (double)w.fg_misses / w.fg_samples);
        else fputc(',', R->win_log);
    } else {
        fputs(",,", R->win_log);
    }
    fprintf(R->win_log, "%s,%u,%llu,%llu,%llu\n", action_name(act), R->streak,
            (unsigned long long)w.scan_bytes_total, (unsigned long long)w.rejected_total,
            (unsigned long long)ctrl);
    if (ferror(R->win_log)) die("window log write failed; run incomplete");

    if (nq == 1 || nq == 2 || nq == 4 || nq == 8) R->q = nq;
    else die("policy returned an invalid q");
    R->win_idx++;
    R->win_start = t_end;
    R->bg_area = 0;
    R->bg_out_max = R->bg_out;
    R->win_fg_samples = R->win_fg_misses = 0;
}

static void advance_windows(struct run *R, uint64_t t)
{
    const uint64_t step = (uint64_t)R->c.window_ms * 1000000ull;
    while (t >= R->win_start + step) end_window(R, R->win_start + step);
}

/* ------------------------------------------------------------- set-up */

static void load_trace(struct run *R)
{
    if (!R->c.trace_path) return;
    FILE *f = fopen(R->c.trace_path, "r");
    if (!f) die("cannot open trace file");
    size_t cap = 1 << 16;
    R->tr_t = malloc(cap * sizeof *R->tr_t);
    R->tr_off = malloc(cap * sizeof *R->tr_off);
    if (!R->tr_t || !R->tr_off) die("trace allocation failed");
    char line[256];
    if (!fgets(line, sizeof line, f) ||
        (strcmp(line, "t_ns,offset\n") && strcmp(line, "t_ns,offset\r\n")))
        die("trace must start with t_ns,offset");
    while (fgets(line, sizeof line, f)) {
        unsigned long long t, off;
        char extra;
        if (line[0] == '-' || sscanf(line, "%llu,%llu %c", &t, &off, &extra) != 2 ||
            strchr(line, '-') || off % BLOCK || off > (unsigned long long)INT64_MAX - R->c.chunk_bytes)
            die("malformed or unaligned trace row");
        if (R->tr_n >= 2000000) die("trace exceeds 2 million requests");
        if (R->tr_n == cap) {
            cap *= 2;
            R->tr_t = realloc(R->tr_t, cap * sizeof *R->tr_t);
            R->tr_off = realloc(R->tr_off, cap * sizeof *R->tr_off);
            if (!R->tr_t || !R->tr_off) die("out of memory");
        }
        R->tr_t[R->tr_n] = t;
        R->tr_off[R->tr_n] = off;
        R->tr_n++;
    }
    if (ferror(f)) die("trace read failed");
    fclose(f);
    for (size_t i = 1; i < R->tr_n; i++)
        if (R->tr_t[i] < R->tr_t[i - 1]) die("trace times must be sorted");
    for (size_t i = 0; i < R->tr_n; i++)
        if (R->tr_t[i] < R->c.warmup_ns + R->c.duration_ns) R->fg_expected++;
}

static int open_file(const char *path, int direct, uint64_t *size)
{
    struct stat original;
    if (lstat(path, &original) || !S_ISREG(original.st_mode)) die("input must be a regular file, not a symlink/device");
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | (direct ? O_DIRECT : 0));
    if (fd < 0) { perror(path); exit(1); }
    struct stat st;
    if (fstat(fd, &st)) die("fstat failed");
    if (!S_ISREG(st.st_mode) || st.st_size < (off_t)BLOCK || st.st_size % (off_t)BLOCK)
        die("input must be a nonempty 4 KiB-aligned regular file");
    *size = (uint64_t)st.st_size;
    return fd;
}

static void json_str(FILE *f, const char *k, const char *v, int comma)
{
    fprintf(f, "  \"%s\": ", k);
    if (!v) fputs("null", f);
    else {
        fputc('"', f);
        for (const char *p = v; *p; p++) {
            if ((unsigned char)*p < 32) fprintf(f, "\\u%04x", (unsigned char)*p);
            else {
                if (*p == '"' || *p == '\\') fputc('\\', f);
                fputc(*p, f);
            }
        }
        fputc('"', f);
    }
    fputs(comma ? ",\n" : "\n", f);
}

static void write_meta(struct run *R, const char *start_wall, int ok)
{
    char path[4096];
    snprintf(path, sizeof path, "%s/run_meta.json", R->c.log_dir);
    FILE *f = fopen(path, "wx");
    if (!f) die("cannot write run_meta.json");
    struct utsname u;
    uname(&u);
    double loadavg = -1;
    FILE *la = fopen("/proc/loadavg", "r");
    if (la) { if (fscanf(la, "%lf", &loadavg) != 1) loadavg = -1; fclose(la); }
    fputs("{\n", f);
    fprintf(f, "  \"log_format\": 3,\n");
    json_str(f, "implementation", "team-reference-integrated-revised", 1);
    json_str(f, "run_status", !ok || R->completed_err ? "failed" :
             g_stop_signal ? "interrupted" : R->early_stop ? "stopped_early" : "completed", 1);
    fprintf(f, "  \"actual_elapsed_ns\": %llu,\n", (unsigned long long)now_ns());
    fprintf(f, "  \"expected_foreground_requests\": %llu,\n  \"offered_foreground_requests\": %zu,\n",
            (unsigned long long)R->fg_expected, R->tr_next);
    fprintf(f, "  \"arrival_schedule_complete\": %s,\n", R->fg_expected == R->tr_next ? "true" : "false");
    fprintf(f, "  \"normal_shutdown_drains_pending\": true,\n");
    fprintf(f, "  \"fg_size_bytes\": %llu,\n  \"bg_size_bytes\": %llu,\n",
            (unsigned long long)R->fg_size, (unsigned long long)R->bg_size);
    json_str(f, "run_id", R->c.run_id, 1);
    json_str(f, "group", R->c.group, 1);
    json_str(f, "policy", R->pol.name, 1);
    fprintf(f, "  \"q\": %u,\n", R->c.q_start);
    json_str(f, "mode", R->c.mode, 1);
    fprintf(f, "  \"repetition\": %d,\n", R->c.repetition);
    json_str(f, "fg_path", R->c.fg_path, 1);
    json_str(f, "bg_path", R->c.bg_path, 1);
    json_str(f, "trace", R->c.trace_path, 1);
    fprintf(f, "  \"trace_requests\": %zu,\n", R->tr_n);
    fprintf(f, "  \"fg_req_bytes\": %u,\n  \"chunk_bytes\": %u,\n", BLOCK, R->c.chunk_bytes);
    fprintf(f, "  \"bg_start_offset\": %llu,\n", (unsigned long long)R->c.bg_start_offset);
    fprintf(f, "  \"fg_quota\": %u,\n  \"fg_queue_cap\": %u,\n  \"bg_queue_cap\": %u,\n",
            R->c.fg_quota, R->c.fg_queue_cap, R->c.bg_queue_cap);
    fprintf(f, "  \"window_ms\": %u,\n", R->c.window_ms);
    if (R->c.target_ms > 0) fprintf(f, "  \"target_ms\": %.3f,\n", R->c.target_ms);
    else fputs("  \"target_ms\": null,\n", f);
    fprintf(f, "  \"direct_io\": %s,\n", R->c.direct ? "true" : "false");
    fprintf(f, "  \"cpu\": %d,\n", R->c.cpu);
    json_str(f, "device", R->c.device, 1);
    json_str(f, "kernel", u.release, 1);
    json_str(f, "host", u.nodename, 1);
    json_str(f, "git_commit", R->c.git_commit, 1);
    json_str(f, "start_time", start_wall, 1);
    fprintf(f, "  \"server_load_1min\": %.2f,\n", loadavg);
    fprintf(f, "  \"warmup_ns\": %llu,\n  \"duration_ns\": %llu,\n",
            (unsigned long long)R->c.warmup_ns, (unsigned long long)R->c.duration_ns);
    fprintf(f, "  \"stopped_by_signal\": %s,\n", g_stop_signal ? "true" : "false");
    fprintf(f, "  \"counts\": {\"accepted\": %llu, \"rejected\": %llu, \"submitted\": %llu, "
               "\"completed_ok\": %llu, \"completed_err\": %llu, \"unsubmitted\": %llu, "
               "\"verify_fail\": %llu, \"fg_ok\": %llu, \"bg_ok\": %llu, "
               "\"scan_bytes_total\": %llu, \"scan_wraps\": %llu},\n",
            (unsigned long long)R->accepted, (unsigned long long)R->rejected,
            (unsigned long long)R->submitted, (unsigned long long)R->completed_ok,
            (unsigned long long)R->completed_err, (unsigned long long)R->unsubmitted,
            (unsigned long long)R->verify_fail, (unsigned long long)R->fg_ok,
            (unsigned long long)R->bg_ok, (unsigned long long)R->scan_bytes_total,
            (unsigned long long)R->scan_wraps);
    fprintf(f, "  \"foreground_admitted\": %llu,\n", (unsigned long long)R->fg_admitted);
    fprintf(f, "  \"accounting_ok\": %s,\n", ok ? "true" : "false");
    json_str(f, "notes", R->c.notes, 0);
    fputs("}\n", f);
    int write_error = ferror(f);
    if (fclose(f)) write_error = 1;
    if (write_error) die("metadata write failed; run incomplete");
}

static uint64_t integer_arg(const char *s, uint64_t maximum)
{
    char *end;
    if (!s[0] || s[0] < '0' || s[0] > '9') die("expected an unsigned integer");
    errno = 0;
    unsigned long long n = strtoull(s, &end, 10);
    if (errno || *end || n > maximum) die("integer out of range");
    return n;
}

static double decimal_arg(const char *s, double maximum)
{
    char *end;
    errno = 0;
    double n = strtod(s, &end);
    if (errno || !s[0] || *end || !isfinite(n) || n < 0 || n > maximum)
        die("invalid nonnegative number");
    return n;
}

static void usage(void)
{
    puts(
"usage: dispatcher --mode fg|bg|mixed --out DIR [options]\n"
"  --fg FILE            foreground test file (fg.dat, file id 1)\n"
"  --bg FILE            background test file (bg.dat, file id 2)\n"
"  --trace FILE         FG arrival trace: lines 't_ns,offset' (needed for fg/mixed)\n"
"  --q N                background limit, 1..8 (fixed policy)      [4]\n"
"  --chunk BYTES        background read size                       [262144]\n"
"  --fg-quota N         max FG reads in flight                     [4]\n"
"  --fg-cap N           FG pending queue size (full -> REJECTED)   [256]\n"
"  --bg-cap N           BG pending queue size                      [16]\n"
"  --window-ms N        window length for windows.csv              [500]\n"
"  --target-ms X        FG latency target for miss counting        [none]\n"
"  --warmup-s S         warm-up seconds (logged, dropped in analysis) [10]\n"
"  --duration-s S       measured seconds after warm-up             [120]\n"
"  --bg-start BYTES     scan start offset                          [0]\n"
"  --cpu N              pin to this CPU (-1 = no pinning)          [-1]\n"
"  --run-id ID --group G --rep N --device DEV --git COMMIT --notes TEXT\n"
"  --no-direct          buffered reads (debugging only, never for results)\n"
"  --fault-offset BYTES test hook: FG reads at this offset get a real error\n"
"  --stop-after-ms MS   test hook: stop early, as if Ctrl-C was pressed\n");
}

/* --------------------------------------------------------------- main */

int main(int argc, char **argv)
{
    struct run R;
    memset(&R, 0, sizeof R);
    struct dispatcher_cfg *c = &R.c;
    c->fg_file_id = 1; c->bg_file_id = 2;
    c->chunk_bytes = 262144; c->fg_quota = 4; c->fg_queue_cap = 256; c->bg_queue_cap = 16;
    c->window_ms = 500; c->q_start = 4; c->direct = 1; c->cpu = -1; c->repetition = 1;
    c->warmup_ns = 10000000000ull; c->duration_ns = 120000000000ull;
    c->fault_offset = UINT64_MAX; c->group = "tuning"; c->run_id = "run";
    uint64_t stop_after_ns = 0;

    static struct option opts[] = {
        {"fg", 1, 0, 'f'}, {"bg", 1, 0, 'b'}, {"trace", 1, 0, 't'}, {"mode", 1, 0, 'm'},
        {"out", 1, 0, 'o'}, {"q", 1, 0, 'q'}, {"chunk", 1, 0, 'c'}, {"fg-quota", 1, 0, 1},
        {"fg-cap", 1, 0, 2}, {"bg-cap", 1, 0, 3}, {"window-ms", 1, 0, 4}, {"target-ms", 1, 0, 5},
        {"warmup-s", 1, 0, 6}, {"duration-s", 1, 0, 7}, {"bg-start", 1, 0, 8}, {"cpu", 1, 0, 9},
        {"run-id", 1, 0, 10}, {"group", 1, 0, 11}, {"rep", 1, 0, 12}, {"device", 1, 0, 13},
        {"git", 1, 0, 14}, {"notes", 1, 0, 15}, {"no-direct", 0, 0, 16},
        {"fault-offset", 1, 0, 17}, {"stop-after-ms", 1, 0, 18}, {"help", 0, 0, 'h'}, {0, 0, 0, 0}};
    int o;
    while ((o = getopt_long(argc, argv, "h", opts, NULL)) != -1) {
        switch (o) {
        case 'f': c->fg_path = optarg; break;
        case 'b': c->bg_path = optarg; break;
        case 't': c->trace_path = optarg; break;
        case 'm': c->mode = optarg; break;
        case 'o': c->log_dir = optarg; break;
        case 'q': c->q_start = (uint16_t)integer_arg(optarg, MAX_LEVEL); break;
        case 'c': c->chunk_bytes = (uint32_t)integer_arg(optarg, 1048576); break;
        case 1: c->fg_quota = (uint16_t)integer_arg(optarg, MAX_FG_QUOTA); break;
        case 2: c->fg_queue_cap = (uint32_t)integer_arg(optarg, 65536); break;
        case 3: c->bg_queue_cap = (uint32_t)integer_arg(optarg, 65536); break;
        case 4: c->window_ms = (uint32_t)integer_arg(optarg, 60000); break;
        case 5: c->target_ms = decimal_arg(optarg, 1000000); if (!c->target_ms) die("target must be positive"); break;
        case 6: c->warmup_ns = (uint64_t)(decimal_arg(optarg, 3600) * 1e9); break;
        case 7: c->duration_ns = (uint64_t)(decimal_arg(optarg, 3600) * 1e9); break;
        case 8: c->bg_start_offset = integer_arg(optarg, INT64_MAX - 1048576); break;
        case 9: c->cpu = !strcmp(optarg, "-1") ? -1 : (int)integer_arg(optarg, CPU_SETSIZE - 1); break;
        case 10: c->run_id = optarg; break;
        case 11: c->group = optarg; break;
        case 12: c->repetition = (int)integer_arg(optarg, 1000000); break;
        case 13: c->device = optarg; break;
        case 14: c->git_commit = optarg; break;
        case 15: c->notes = optarg; break;
        case 16: c->direct = 0; break;
        case 17: c->fault_offset = integer_arg(optarg, INT64_MAX - 1048576); break;
        case 18: stop_after_ns = (uint64_t)(decimal_arg(optarg, 3600000) * 1e6); break;
        default: usage(); return o == 'h' ? 0 : 1;
        }
    }
    if (!c->mode || !c->log_dir) { usage(); return 1; }
    int want_fg = !strcmp(c->mode, "fg") || !strcmp(c->mode, "mixed");
    c->scan = !strcmp(c->mode, "bg") || !strcmp(c->mode, "mixed");
    if (!want_fg && !c->scan) die("--mode must be fg, bg or mixed");
    if (want_fg && (!c->fg_path || !c->trace_path)) die("--fg and --trace are needed for this mode");
    if (c->scan && !c->bg_path) die("--bg is needed for this mode");
    if (!(c->q_start == 1 || c->q_start == 2 || c->q_start == 4 || c->q_start == 8))
        die("--q must be 1, 2, 4 or 8");
    if (c->chunk_bytes == 0 || c->chunk_bytes % BLOCK) die("--chunk must be a multiple of 4096");
    if (c->bg_start_offset % BLOCK) die("--bg-start must be 4 KiB aligned");
    if (c->fg_quota < 1 || c->fg_queue_cap < 1 || c->bg_queue_cap < MAX_LEVEL) die("bad queue sizes (bg-cap must be >= 8)");
    if (!c->window_ms || !c->duration_ns || !c->repetition) die("window, duration and repetition must be positive");

    if (c->cpu >= 0) {
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(c->cpu, &set);
        if (sched_setaffinity(0, sizeof set, &set)) die("requested CPU affinity could not be applied");
    }
    if (mkdir(c->log_dir, 0755)) die("output directory must be new and have an existing parent");

    R.fg_fd = R.bg_fd = -1;
    if (want_fg) R.fg_fd = open_file(c->fg_path, c->direct, &R.fg_size);
    if (c->scan) R.bg_fd = open_file(c->bg_path, c->direct, &R.bg_size);
    if (c->scan && c->bg_start_offset >= R.bg_size) die("--bg-start is past the end of the background file");
    if (want_fg) load_trace(&R);

    unsigned entries = 1;
    while (entries < (unsigned)c->fg_quota + MAX_LEVEL + 4) entries <<= 1;
    if (io_uring_queue_init(entries, &R.ring, 0)) die("io_uring_queue_init failed");

    char path[4096];
    snprintf(path, sizeof path, "%s/requests.csv", c->log_dir);
    R.req_log = fopen(path, "wx");
    snprintf(path, sizeof path, "%s/windows.csv", c->log_dir);
    R.win_log = fopen(path, "wx");
    if (!R.req_log || !R.win_log) die("cannot create log files");
    setvbuf(R.req_log, NULL, _IOFBF, 1 << 20);
    fputs("req_id,class,offset,len,t_arrival,t_submit,t_complete,status,errno,verified,"
          "q_at_submit,bg_out_at_submit,fg_out_at_submit,bytes_read,t_admit,t_verify\n", R.req_log);
    fputs("win_idx,t_start,t_end,q_config,bg_out_max,bg_out_mean,fg_pending_len,"
          "bg_pending_len,fg_samples,fg_misses,miss_frac,action,streak,scan_bytes_total,"
          "rejected_total,ctrl_cpu_ns\n", R.win_log);

    R.pol.name = "fixed";
    R.pol.next_q = fixed_next_q;
    R.q = c->q_start;
    R.next_bg_offset = c->bg_start_offset;

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_signal;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    char start_wall[64];
    time_t wall = time(NULL);
    strftime(start_wall, sizeof start_wall, "%Y-%m-%dT%H:%M:%S%z", localtime(&wall));

    clock_gettime(CLOCK_MONOTONIC, &g_t0);
    uint64_t end_ns = c->warmup_ns + c->duration_ns;
    uint64_t win_ns = (uint64_t)c->window_ms * 1000000ull;

    /* ---- main loop ---- */
    for (;;) {
        uint64_t t = now_ns();
        if (g_stop_signal || (stop_after_ns && t >= stop_after_ns)) {
            R.early_stop = !g_stop_signal;
            break;
        }
        advance_windows(&R, t);
        if (!R.arrivals_closed) {
            admit_arrivals(&R, t < end_ns ? t : end_ns - 1);
            if (t < end_ns) top_up_scanner(&R, t);
            else R.arrivals_closed = 1;
        }
        submit_ready(&R);
        if (R.arrivals_closed && !R.fg_q.len && !R.bg_q.len && !R.fg_out && !R.bg_out) break;

        uint64_t next = R.win_start + win_ns;
        if (!R.arrivals_closed && R.tr_next < R.tr_n && R.tr_t[R.tr_next] < next) next = R.tr_t[R.tr_next];
        if (!R.arrivals_closed && next > end_ns) next = end_ns;
        uint64_t wait = next > t ? next - t : 0;
        if (wait > 1000000ull) wait = 1000000ull;        /* wake at least every 1 ms */
        reap(&R, wait);
    }

    /* ---- clean shutdown ---- */
    R.stopping = 1;
    struct request *r;
    while ((r = q_pop(&R.fg_q))) { R.unsubmitted++; log_request(&R, r, "UNSUBMITTED", ECANCELED); req_free(&R, r); }
    while ((r = q_pop(&R.bg_q))) { R.unsubmitted++; log_request(&R, r, "UNSUBMITTED", ECANCELED); req_free(&R, r); }
    while (R.fg_out + R.bg_out > 0) {                     /* drain in-flight reads */
        struct io_uring_cqe *cqe;
        int e = io_uring_wait_cqe(&R.ring, &cqe);
        if (e == -EINTR) continue;
        if (e < 0) die("io_uring_wait_cqe failed during shutdown");
        reap(&R, 0);
    }
    advance_windows(&R, now_ns());
    end_window(&R, now_ns());

    int ok = R.accepted == R.submitted + R.unsubmitted &&
             R.submitted == R.completed_ok + R.completed_err;
    if (!R.early_stop && !g_stop_signal && R.tr_next != R.fg_expected) ok = 0;
    int log_error = ferror(R.req_log) || ferror(R.win_log);
    if (fclose(R.req_log)) log_error = 1;
    if (fclose(R.win_log)) log_error = 1;
    if (log_error) die("log flush failed; run incomplete");
    write_meta(&R, start_wall, ok);
    io_uring_queue_exit(&R.ring);

    fprintf(stderr,
            "%s: accepted=%llu rejected=%llu submitted=%llu ok=%llu err=%llu unsubmitted=%llu "
            "verify_fail=%llu scan=%.1f MiB accounting=%s\n",
            c->run_id, (unsigned long long)R.accepted, (unsigned long long)R.rejected,
            (unsigned long long)R.submitted, (unsigned long long)R.completed_ok,
            (unsigned long long)R.completed_err, (unsigned long long)R.unsubmitted,
            (unsigned long long)R.verify_fail, R.scan_bytes_total / 1048576.0, ok ? "OK" : "BROKEN");
    return !ok || R.completed_err ? 2 : (g_stop_signal || R.early_stop) ? 130 : 0;
}
