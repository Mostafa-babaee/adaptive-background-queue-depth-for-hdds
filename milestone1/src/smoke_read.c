#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <liburing.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include "pattern.h"

enum { BAD_ARGS = 2, OPEN_ERROR = 3, NOT_REGULAR = 4,
       IO_ERROR = 6, SHORT_READ = 7, VERIFY_ERROR = 8,
       INTERNAL_ERROR = 9, BLOCKED = 77 };

static uint64_t now_ns(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) {
        perror("clock_gettime");
        exit(INTERNAL_ERROR);
    }
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

static int number(const char *text, uint64_t *value)
{
    char *end = NULL;
    if (!text[0] || text[0] < '0' || text[0] > '9') return -1;
    errno = 0;
    unsigned long long parsed = strtoull(text, &end, 10);
    if (errno || !end || *end) return -1;
    *value = (uint64_t)parsed;
    return 0;
}

int main(int argc, char **argv)
{
    uint64_t offset = 0, length = 4096, count = 1;
    if (argc < 2 || argc > 5 ||
        (argc > 2 && number(argv[2], &offset)) ||
        (argc > 3 && number(argv[3], &length)) ||
        (argc > 4 && number(argv[4], &count)) ||
        offset > (uint64_t)INT64_MAX - UINT64_C(1048576) ||
        length < 4096 || length > 1048576 || offset % 4096 || length % 4096 ||
        count < 1 || count > 64) {
        fprintf(stderr, "Usage: smoke_read FILE [OFFSET [LENGTH [COUNT]]]\n"
                "OFFSET/LENGTH: multiples of 4096; LENGTH 4096..1048576; COUNT 1..64.\n");
        return BAD_ARGS;
    }

    struct stat info;
    if (lstat(argv[1], &info) != 0) { perror("lstat"); return OPEN_ERROR; }
    if (!S_ISREG(info.st_mode)) {
        fprintf(stderr, "Rejected: expected a regular file, not a directory, symlink, or device.\n");
        return NOT_REGULAR;
    }
    int fd = open(argv[1], O_RDONLY | O_DIRECT | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) {
        int saved = errno;
        fprintf(stderr, "open O_DIRECT: %s\n", strerror(saved));
        return (saved == EINVAL || saved == EOPNOTSUPP || saved == ENOSYS) ? BLOCKED : OPEN_ERROR;
    }
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode)) {
        fprintf(stderr, "Opened object is not an accessible regular file.\n");
        close(fd);
        return NOT_REGULAR;
    }

    size_t alignment = 4096;
    printf("backend=io_uring direct_io=requested_with_O_DIRECT file_size=%jd\n", (intmax_t)info.st_size);
#ifdef STATX_DIOALIGN
    struct statx sx;
    memset(&sx, 0, sizeof(sx));
    if (statx(fd, "", AT_EMPTY_PATH, STATX_DIOALIGN, &sx) == 0 &&
        (sx.stx_mask & STATX_DIOALIGN)) {
        printf("reported_memory_alignment=%u reported_offset_alignment=%u\n",
               sx.stx_dio_mem_align, sx.stx_dio_offset_align);
        if (!sx.stx_dio_mem_align || !sx.stx_dio_offset_align) {
            fprintf(stderr, "BLOCKED: filesystem reports no direct-I/O support.\n");
            close(fd);
            return BLOCKED;
        }
        if (sx.stx_dio_mem_align > alignment) alignment = sx.stx_dio_mem_align;
        if (offset % sx.stx_dio_offset_align || length % sx.stx_dio_offset_align) {
            fprintf(stderr, "BLOCKED: request does not meet reported filesystem alignment.\n");
            close(fd);
            return BLOCKED;
        }
    } else {
        printf("reported_alignment=unavailable using_4096_byte_alignment\n");
    }
#else
    printf("reported_alignment=unavailable_in_headers using_4096_byte_alignment\n");
#endif
    unsigned char *buffer = NULL;
    int err = posix_memalign((void **)&buffer, alignment, (size_t)length);
    if (err) {
        fprintf(stderr, "posix_memalign: %s\n", strerror(err));
        close(fd);
        return INTERNAL_ERROR;
    }
    struct io_uring ring;
    int rc = io_uring_queue_init(2, &ring, 0);
    if (rc < 0) {
        fprintf(stderr, "BLOCKED: io_uring_queue_init: %s (%d)\n", strerror(-rc), -rc);
        free(buffer);
        close(fd);
        return BLOCKED;
    }

    int status = 0, in_flight = 0;
    uint64_t verified = 0;
    printf("request_id,offset,bytes,arrival_ns,submission_ns,completion_ns,verified\n");
    for (uint64_t id = 1; id <= count; ++id) {
        uint64_t arrival = now_ns();
        struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
        if (!sqe) { fprintf(stderr, "No SQE available.\n"); status = INTERNAL_ERROR; break; }
        memset(buffer, 0, (size_t)length);
        io_uring_prep_read(sqe, fd, buffer, (unsigned)length, (off_t)offset);
        sqe->user_data = id;
        uint64_t submitted = now_ns();
        /* On an ambiguous failure, keep the buffer alive until process exit. */
        in_flight = 1;
        rc = io_uring_submit(&ring);
        if (rc != 1) {
            fprintf(stderr, "Submit failed: %s (return %d)\n", rc < 0 ? strerror(-rc) : "no request submitted", rc);
            status = IO_ERROR;
            break;
        }
        struct io_uring_cqe *cqe = NULL;
        do { rc = io_uring_wait_cqe(&ring, &cqe); } while (rc == -EINTR);
        if (rc < 0) {
            fprintf(stderr, "Wait failed: %s\n", strerror(-rc));
            status = IO_ERROR;
            break;
        }
        uint64_t completed = now_ns();
        int bytes = cqe->res;
        uint64_t completed_id = cqe->user_data;
        io_uring_cqe_seen(&ring, cqe);
        in_flight = 0;
        if (completed_id != id) {
            fprintf(stderr, "Completion ID mismatch.\n"); status = INTERNAL_ERROR; break;
        }
        if (bytes < 0) {
            fprintf(stderr, "Read completion error: %s (%d)\n", strerror(-bytes), -bytes);
            status = (bytes == -EINVAL || bytes == -EOPNOTSUPP || bytes == -ENOSYS) ? BLOCKED : IO_ERROR;
            break;
        }
        if ((uint64_t)bytes != length) {
            fprintf(stderr, "SHORT_READ: expected %" PRIu64 " bytes, got %d at offset %" PRIu64 ".\n", length, bytes, offset);
            status = SHORT_READ;
            break;
        }
        for (uint64_t j = 0; j < length; ++j) {
            unsigned char expected = expected_byte(offset + j);
            if (buffer[j] != expected) {
                fprintf(stderr, "VERIFY_ERROR at byte %" PRIu64 ": expected %u, got %u.\n",
                        offset + j, (unsigned)expected, (unsigned)buffer[j]);
                status = VERIFY_ERROR;
                break;
            }
        }
        if (status) break;
        ++verified;
        printf("%" PRIu64 ",%" PRIu64 ",%d,%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",yes\n",
               id, offset, bytes, arrival, submitted, completed);
    }
    io_uring_queue_exit(&ring);
    /* Normally no reads remain. Avoid releasing a potentially active buffer on
       an unexpected submission/wait failure; the process exits immediately. */
    if (!in_flight) free(buffer);
    close(fd);
    if (!status) printf("PASS: %" PRIu64 " reads completed and verified. No performance conclusion.\n", verified);
    return status;
}
