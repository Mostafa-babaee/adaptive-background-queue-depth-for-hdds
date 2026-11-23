/*
 * rl_policy.c - Milestone 4, Muhammad Ahmad Tariq. See rl_policy.h.
 */
#include "rl_policy.h"
#include "rl_table.h"

void rl_init(struct rl_state *s)
{
    s->idx = 0;               /* start at q = 1, as the adaptive policy does */
    s->n_up = s->n_down = s->n_sparse = s->n_hold = 0;
}

static int miss_bucket(double miss)
{
    if (miss <= 0.01) return 0;
    if (miss <= 0.05) return 1;
    return 2;
}

static int load_bucket(uint32_t fg_samples)
{
    if (fg_samples < 100) return 0;
    if (fg_samples < 500) return 1;
    return 2;
}

uint16_t rl_step(struct rl_state *s, uint32_t fg_samples, uint32_t fg_misses,
                 int scanning, int *action)
{
    int act = CTRL_HOLD;
    if (!scanning) {
        act = CTRL_HOLD;
    } else if (fg_samples < 25) {
        act = CTRL_SPARSE;                       /* too few reads: keep q */
    } else {
        double miss = (double)fg_misses / (double)fg_samples;
        int next = RL_TABLE[s->idx][miss_bucket(miss)][load_bucket(fg_samples)];
        if (next > s->idx) act = CTRL_UP;
        else if (next < s->idx) act = CTRL_DOWN;
        s->idx = next;
    }
    switch (act) {
    case CTRL_UP: s->n_up++; break;
    case CTRL_DOWN: s->n_down++; break;
    case CTRL_SPARSE: s->n_sparse++; break;
    default: s->n_hold++; break;
    }
    if (action) *action = act;
    return rl_q(s);
}
