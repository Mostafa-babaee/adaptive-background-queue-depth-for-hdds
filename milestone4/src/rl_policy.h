/*
 * rl_policy.h - Milestone 4, Muhammad Ahmad Tariq.
 * Table-driven background queue-depth policy (trained offline, see tools/).
 *
 * Once per window, the state is read from this window only:
 *   q index    the current q (0..3 for q = 1, 2, 4, 8)
 *   miss bucket  0: miss <= 1 %, 1: miss <= 5 %, 2: miss > 5 %
 *   load bucket  0: fg reads < 100, 1: fg reads < 500, 2: otherwise
 * The next q index is RL_TABLE[q][miss][load] (src/rl_table.h).
 * Hold (no change) when not scanning or when there are too few fg samples.
 * Same interface as controller.h so the dispatcher treats both alike.
 */
#ifndef RL_POLICY_H
#define RL_POLICY_H

#include <stdint.h>
#include "controller.h"   /* enum { CTRL_HOLD, CTRL_UP, CTRL_DOWN, CTRL_SPARSE } */

struct rl_state {
    int      idx;             /* current index into levels {1, 2, 4, 8} */
    uint64_t n_up, n_down, n_sparse, n_hold;
};

void rl_init(struct rl_state *s);

/* One window: returns the new q and writes the action (CTRL_*). */
uint16_t rl_step(struct rl_state *s, uint32_t fg_samples, uint32_t fg_misses,
                 int scanning, int *action);

static inline uint16_t rl_q(const struct rl_state *s)
{
    static const uint16_t levels[4] = {1, 2, 4, 8};
    return levels[s->idx];
}

#endif
