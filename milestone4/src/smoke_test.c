/*
 * smoke_test.c - Milestone 1 smoke test for CSC 720 Project 03.
 * Reads a test file made by make_testfiles.py with O_DIRECT through io_uring,
 * keeps up to QD reads in flight, and verifies every 4 KiB block it gets back.
 *
 * Build:  gcc -O2 -Wall -o smoke_test smoke_test.c -luring
 *   (liburing in your home dir: add -I$HOME/local/include -L$HOME/local/lib
 *    and run with LD_LIBRARY_PATH=$HOME/local/lib)
 * Run:    ./smoke_test <file> <file_id> <mode: rand|seq> <req_KiB> <count> <qd>
 * Example: ./smoke_test fg.dat 1 rand 4 2000 4      (4 KiB random reads, depth 4)
 *          ./smoke_test bg.dat 2 seq 256 400 2      (256 KiB sequential reads, depth 2)
 * Prints per-request latency stats (submit -> complete) and exits non-zero on any
 * verification failure or I/O error.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <liburing.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define BLOCK 4096
#define MAGIC 0x5453455451444448ULL
#define GOLDEN 0x9E3779B97F4A7C15ULL

struct req {
    uint64_t id, offset;
    uint64_t t_submit, t_complete;
    void *buf;
};

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

/* returns number of bad blocks in the buffer */
static int verify(const void *buf, size_t len, uint64_t offset, uint64_t file_id) {
    int bad = 0;
    for (size_t o = 0; o < len; o += BLOCK) {
        const uint64_t *w = (const uint64_t *)((const char *)buf + o);
        uint64_t bn = (offset + o) / BLOCK;
        uint64_t fill = bn * GOLDEN + file_id;
        int ok = w[0] == MAGIC && w[1] == file_id && w[2] == bn;
        for (int i = 3; ok && i < BLOCK / 8; i++) ok = (w[i] == fill);
        if (!ok) {
            if (bad < 5) fprintf(stderr, "bad block %lu (magic %#lx id %lu bn %lu)\n",
                                 (unsigned long)bn, (unsigned long)w[0],
                                 (unsigned long)w[1], (unsigned long)w[2]);
            bad++;
        }
    }
    return bad;
}

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
    if (argc != 7) {
        fprintf(stderr, "usage: %s <file> <file_id> <rand|seq> <req_KiB> <count> <qd>\n", argv[0]);
        return 2;
    }
    const char *path = argv[1];
    uint64_t file_id = strtoull(argv[2], 0, 10);
    int rnd = strcmp(argv[3], "rand") == 0;
    size_t req_len = (size_t)atoi(argv[4]) * 1024;
    int count = atoi(argv[5]), qd = atoi(argv[6]);
    if (req_len == 0 || req_len % BLOCK || count <= 0 || qd <= 0) {
        fprintf(stderr, "req_KiB must be a multiple of 4; count, qd > 0\n");
        return 2;
    }

    int fd = open(path, O_RDONLY | O_DIRECT);
    if (fd < 0) { perror("open O_DIRECT"); return 1; }
    struct stat st;
    fstat(fd, &st);
    uint64_t nreq_slots = (uint64_t)st.st_size / req_len;
    if (nreq_slots == 0) { fprintf(stderr, "file smaller than one request\n"); return 1; }

    struct io_uring ring;
    int rc = io_uring_queue_init(qd, &ring, 0);
    if (rc < 0) { fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-rc)); return 1; }

    struct req *reqs = calloc(count, sizeof *reqs);
    uint64_t *lat = calloc(count, sizeof *lat);
    srand(12345);  /* fixed seed: same offsets every run */
    uint64_t next_seq = 0;
    int submitted = 0, completed = 0, inflight = 0, errors = 0, badblocks = 0;
    uint64_t bytes = 0, t0 = now_ns();

    while (completed < count) {
        /* top up to qd outstanding reads */
        while (inflight < qd && submitted < count) {
            struct req *r = &reqs[submitted];
            r->id = submitted;
            if (rnd) {
                uint64_t slot = (((uint64_t)rand() << 31) ^ (uint64_t)rand()) % nreq_slots;
                r->offset = slot * req_len;
            } else {
                r->offset = (next_seq++ % nreq_slots) * req_len;
            }
            if (posix_memalign(&r->buf, BLOCK, req_len)) { perror("posix_memalign"); return 1; }
            struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
            io_uring_prep_read(sqe, fd, r->buf, req_len, r->offset);
            io_uring_sqe_set_data(sqe, r);
            r->t_submit = now_ns();
            rc = io_uring_submit(&ring);
            if (rc < 0) { fprintf(stderr, "submit: %s\n", strerror(-rc)); return 1; }
            submitted++;
            inflight++;
        }
        /* wait for at least one completion */
        struct io_uring_cqe *cqe;
        rc = io_uring_wait_cqe(&ring, &cqe);
        if (rc < 0) { fprintf(stderr, "wait_cqe: %s\n", strerror(-rc)); return 1; }
        struct req *r = io_uring_cqe_get_data(cqe);
        r->t_complete = now_ns();
        if (cqe->res < 0) {
            fprintf(stderr, "req %lu offset %lu: error %s\n", (unsigned long)r->id,
                    (unsigned long)r->offset, strerror(-cqe->res));
            errors++;
        } else if ((size_t)cqe->res != req_len) {
            fprintf(stderr, "req %lu: short read %d\n", (unsigned long)r->id, cqe->res);
            errors++;
        } else {
            badblocks += verify(r->buf, req_len, r->offset, file_id);
            bytes += req_len;
        }
        lat[completed] = r->t_complete - r->t_submit;
        free(r->buf);
        io_uring_cqe_seen(&ring, cqe);
        inflight--;
        completed++;
    }
    double secs = (now_ns() - t0) / 1e9;

    qsort(lat, count, sizeof *lat, cmp_u64);
    printf("file=%s mode=%s req=%zuKiB count=%d qd=%d\n", path, rnd ? "rand" : "seq",
           req_len / 1024, count, qd);
    printf("latency submit->complete: p50=%.3f ms  p99=%.3f ms  max=%.3f ms\n",
           lat[count / 2] / 1e6, lat[(int)(count * 0.99)] / 1e6, lat[count - 1] / 1e6);
    printf("throughput: %.2f MiB/s  (%.2f s)\n", bytes / 1048576.0 / secs, secs);
    printf("verify: %d bad blocks, %d I/O errors -> %s\n", badblocks, errors,
           (badblocks || errors) ? "FAIL" : "PASS");

    io_uring_queue_exit(&ring);
    close(fd);
    free(reqs);
    free(lat);
    return (badblocks || errors) ? 1 : 0;
}
