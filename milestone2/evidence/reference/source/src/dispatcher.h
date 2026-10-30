/*
 * dispatcher.h - Milestone 2, Mostafa Babaei.
 * Data structures of the common read dispatcher (implemented in dispatcher.c).
 *
 * One dispatcher is shared by every policy (fixed q = 1, 2, 4, 8 now; the
 * adaptive policy plugs into the same next_q() hook), so all policies pay the
 * same software overhead.
 */
#ifndef DISPATCHER_H
#define DISPATCHER_H

#include <stdint.h>
#include <stddef.h>

/* ---------- requests ---------------------------------------------------- */

enum req_class { REQ_FG = 0, REQ_BG = 1 };
enum req_state { RS_PENDING, RS_SUBMITTED, RS_DONE, RS_REJECTED };

struct request {
    uint64_t id;             /* unique within a run, assigned on arrival      */
    enum req_class cls;
    enum req_state state;    /* PENDING -> SUBMITTED -> DONE, exactly once     */
    uint64_t offset;         /* bytes, 4 KiB aligned                           */
    uint32_t len;            /* bytes: 4096 (FG) or chunk size (BG)            */
    void    *buf;            /* 4 KiB-aligned buffer for O_DIRECT              */
    /* timestamps: ns since run start, CLOCK_MONOTONIC */
    uint64_t t_arrival;      /* FG: trace time. BG: time the chunk was queued  */
    uint64_t t_submit;       /* handed to io_uring                             */
    uint64_t t_complete;     /* completion reaped                              */
    int32_t  result;         /* bytes read, or -errno                          */
    uint8_t  verified;       /* 1 if every 4 KiB block matched the pattern     */
    /* state at submit time, for the log */
    uint16_t q_at_submit;
    uint16_t bg_out_at_submit;
    uint16_t fg_out_at_submit;
    struct request *next;    /* pending-queue / free-list link                 */
};

/* Bounded FIFO. A full FG queue REJECTS (and logs) the new request; it is
 * never silently dropped. */
struct pending_queue {
    struct request *head, *tail;
    uint32_t len;
};

/* ---------- controller interface --------------------------------------- */

/* Statistics of one window, filled by the dispatcher, read by the policy. */
struct window_stats {
    uint64_t win_idx, t_start, t_end;
    uint32_t fg_samples;       /* FG reads completed OK in this window         */
    uint32_t fg_misses;        /* of those, latency > target                   */
    uint16_t q_config;         /* q during the window                          */
    uint16_t bg_out_max;       /* actual outstanding BG reads, max             */
    double   bg_out_mean;      /* time-weighted mean outstanding BG reads      */
    uint32_t fg_pending_len, bg_pending_len;
    uint64_t scan_bytes_total, rejected_total;
    int      scanning;         /* 1 while the background scan is active        */
};

enum ctrl_action { ACT_HOLD, ACT_UP, ACT_DOWN, ACT_SPARSE };

struct policy {
    const char *name;                       /* "fixed" (now) or "adaptive"     */
    void *state;                            /* policy-private state            */
    /* Called once per window. Returns the new q and sets *action for the log.
     * Must be cheap: its CPU time is logged as ctrl_cpu_ns. */
    uint16_t (*next_q)(void *state, const struct window_stats *w,
                       enum ctrl_action *action);
};

/* ---------- configuration ----------------------------------------------- */

struct dispatcher_cfg {
    const char *fg_path, *bg_path, *trace_path, *log_dir, *mode;
    const char *run_id, *group, *device, *git_commit, *notes;
    uint64_t fg_file_id, bg_file_id;
    uint32_t chunk_bytes;        /* BG read size, fixed within a run (256 KiB) */
    uint64_t bg_start_offset;    /* same scan start for every policy           */
    uint16_t fg_quota;           /* max outstanding FG reads, same everywhere  */
    uint32_t fg_queue_cap, bg_queue_cap;
    uint32_t window_ms;
    double   target_ms;          /* FG latency target (arrival -> complete)    */
    uint16_t q_start;            /* fixed q, or start q for adaptive           */
    uint64_t warmup_ns, duration_ns;
    int      scan;               /* 1 if the background scan runs              */
    int      direct;             /* O_DIRECT (always 1 for real results)       */
    int      cpu, repetition;
    uint64_t fault_offset;       /* test hook, UINT64_MAX = off                */
};

/*
 * Main loop (one thread, no locks):
 *   while running:
 *     1. admit arrivals whose trace time has come -> fg_q (REJECTED if full);
 *        keep bg_q topped up with the next sequential chunks while scanning
 *     2. submit FG while fg_out < fg_quota and fg_q non-empty
 *     3. submit BG while bg_out < q and bg_q non-empty
 *        (if q was lowered below bg_out, step 3 submits nothing until enough
 *         BG reads finish; submitted reads are never cancelled)
 *     4. reap completions (wait with a short timeout); verify; log; counters
 *     5. at each window boundary: stats -> pol->next_q() -> q; log window row
 *   shutdown: stop arrivals and scanner, log pending requests as UNSUBMITTED,
 *             drain all in-flight reads, check
 *             accepted == submitted + unsubmitted and
 *             submitted == completed_ok + completed_err, flush logs.
 */

#endif
