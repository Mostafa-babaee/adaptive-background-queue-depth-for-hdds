/*
 * controller.h - Milestone 3, Muhammad Ahmad Tariq.
 * Adaptive background queue-depth controller (windowed target-miss rule).
 *
 * Pure C, no I/O: the dispatcher calls ctrl_next_q() once per window through
 * the same next_q() hook the fixed policy uses, so every policy pays the same
 * overhead. tests/test_controller.c tests it without a disk.
 *
 * Rule, once per window (same as analysis/controller.py):
 *   not scanning                  -> hold                         (HOLD)
 *   fg_samples < min_samples      -> hold, streak unchanged       (SPARSE)
 *   miss = fg_misses / fg_samples
 *   miss >  miss_high             -> one level down, streak = 0   (DOWN)
 *   miss <= miss_low              -> streak += 1; when streak reaches
 *                                    up_windows: one level up, streak = 0 (UP)
 *   otherwise                     -> streak = 0                   (HOLD)
 * q is always one of the levels {1, 2, 4, 8}, so q >= 1 while scanning.
 *
 * No-damping ablation ("adaptive_nodamp"): the same rule with up_windows = 1,
 * so q goes up after a single good window.
 */
#ifndef CONTROLLER_H
#define CONTROLLER_H

#include <stdint.h>

#define CTRL_MAX_LEVELS 4

struct ctrl_cfg {
    uint16_t levels[CTRL_MAX_LEVELS];
    int      n_levels;
    uint16_t q_start;
    uint32_t window_ms;
    uint32_t min_samples;
    double   target_ms;
    double   miss_high, miss_low;
    uint32_t up_windows;
    int      ablation;            /* 1 = no damping (up_windows forced to 1) */
};

struct ctrl_state {
    struct ctrl_cfg cfg;
    int      idx;                 /* index of the current q in levels        */
    uint32_t streak;              /* good windows in a row                   */
    uint64_t n_up, n_down, n_sparse, n_hold;
};

/* Actions use the same numbers as enum ctrl_action in dispatcher.h. */
enum { CTRL_HOLD = 0, CTRL_UP = 1, CTRL_DOWN = 2, CTRL_SPARSE = 3 };

/* Defaults (levels 1,2,4,8, q_start 1, window 1000 ms, min_samples 25,
 * miss_high 0.05, miss_low 0.01, up_windows 3, no target). */
void ctrl_defaults(struct ctrl_cfg *c);

/* Read the numbers from a config file such as config/adaptive.json.
 * Returns 0 on success, or -1 and writes a reason into err. */
int ctrl_load(struct ctrl_cfg *c, const char *path, char *err, int errlen);

/* Check the settings. Returns 0 if valid, or -1 and a reason in err. */
int ctrl_validate(const struct ctrl_cfg *c, char *err, int errlen);

void ctrl_init(struct ctrl_state *s, const struct ctrl_cfg *c);

static inline uint16_t ctrl_q(const struct ctrl_state *s) { return s->cfg.levels[s->idx]; }

/* One window: returns the new q and writes the action (CTRL_*). */
uint16_t ctrl_step(struct ctrl_state *s, uint32_t fg_samples, uint32_t fg_misses,
                   int scanning, int *action);

#endif
