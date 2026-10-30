#ifndef M2_SUBMISSION_H
#define M2_SUBMISSION_H
#include <errno.h>
/* Flush a prepared batch. A positive prefix is accepted exactly once.
   A fatal return makes the entire run incomplete; no buffers may be reused. */
static inline int m2_flush_batch(unsigned count, int (*submit)(void *),
                                void (*accepted)(void *, unsigned, unsigned), void *ctx)
{
    unsigned done = 0;
    while (done < count) {
        int rc = submit(ctx);
        if (rc == -EINTR) continue;
        if (rc <= 0 || (unsigned)rc > count - done) return -1;
        accepted(ctx, done, (unsigned)rc);
        done += (unsigned)rc;
    }
    return 0;
}
#endif
