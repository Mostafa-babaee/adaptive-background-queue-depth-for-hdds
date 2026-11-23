/*
 * test_controller.c - Milestone 3, Muhammad Ahmad Tariq.
 * Unit tests for the adaptive controller (src/controller.c). No disk needed.
 *
 * Covered (Project Execution Plan, Milestone 3):
 *   sparse windows: fewer than min_samples reads -> q and streak are held
 *   allowed q values: q is always 1, 2, 4 or 8, never below 1 while scanning
 *   plus: DOWN on misses, UP only after up_windows good windows, a middle
 *   window resets the streak, no scan -> hold, the no-damping ablation goes
 *   up after one good window, config loading and bad settings are refused.
 * Build and run: make test-unit
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "controller.h"

static int failures = 0, checks = 0;
#define CHECK(cond, msg) do { checks++; if (!(cond)) { failures++; \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, msg); } } while (0)

static struct ctrl_cfg cfg(void)
{
    struct ctrl_cfg c;
    ctrl_defaults(&c);
    c.target_ms = 0.5;
    return c;
}

static int allowed(uint16_t q) { return q == 1 || q == 2 || q == 4 || q == 8; }

static void test_sparse_windows_hold(void)
{
    struct ctrl_cfg c = cfg();
    c.q_start = 4;
    struct ctrl_state s;
    ctrl_init(&s, &c);
    int a;
    /* two good windows, then sparse ones: streak must stay at 2 */
    ctrl_step(&s, 100, 0, 1, &a);
    ctrl_step(&s, 100, 0, 1, &a);
    CHECK(s.streak == 2, "two good windows give streak 2");
    for (int i = 0; i < 10; i++) {
        uint16_t q = ctrl_step(&s, 24, 24, 1, &a);    /* 24 < 25: all misses ignored */
        CHECK(q == 4 && a == CTRL_SPARSE, "sparse window holds q");
    }
    CHECK(s.streak == 2, "sparse windows do not change the streak");
    CHECK(ctrl_step(&s, 0, 0, 1, &a) == 4 && a == CTRL_SPARSE, "empty window is sparse");
    /* exactly min_samples is not sparse */
    CHECK(ctrl_step(&s, 25, 0, 1, &a) == 8 && a == CTRL_UP, "third good window steps up");
    CHECK(s.n_sparse == 11, "sparse windows are counted");
}

static void test_down_and_floor(void)
{
    struct ctrl_cfg c = cfg();
    c.q_start = 8;
    struct ctrl_state s;
    ctrl_init(&s, &c);
    int a;
    uint16_t want[] = {4, 2, 1, 1, 1};
    for (int i = 0; i < 5; i++) {
        uint16_t q = ctrl_step(&s, 100, 50, 1, &a);
        CHECK(q == want[i], "each bad window goes one level down");
        CHECK(q >= 1, "q never below 1 while scanning");
    }
    CHECK(a == CTRL_HOLD, "at q = 1 a bad window holds");
    /* miss exactly at miss_high is not "above" */
    c.q_start = 4;
    ctrl_init(&s, &c);
    CHECK(ctrl_step(&s, 100, 5, 1, &a) == 4 && a == CTRL_HOLD, "miss == miss_high holds");
    CHECK(ctrl_step(&s, 100, 6, 1, &a) == 2 && a == CTRL_DOWN, "miss > miss_high goes down");
}

static void test_up_needs_streak(void)
{
    struct ctrl_cfg c = cfg();
    struct ctrl_state s;
    ctrl_init(&s, &c);
    int a;
    CHECK(ctrl_q(&s) == 1, "start at q_start = 1");
    CHECK(ctrl_step(&s, 50, 0, 1, &a) == 1 && a == CTRL_HOLD, "good window 1 holds");
    CHECK(ctrl_step(&s, 50, 0, 1, &a) == 1 && a == CTRL_HOLD, "good window 2 holds");
    CHECK(ctrl_step(&s, 50, 0, 1, &a) == 2 && a == CTRL_UP, "good window 3 steps up");
    CHECK(s.streak == 0, "streak resets after a step up");
    /* a middle window (between miss_low and miss_high) resets the streak */
    ctrl_step(&s, 100, 0, 1, &a);
    ctrl_step(&s, 100, 0, 1, &a);
    CHECK(ctrl_step(&s, 100, 3, 1, &a) == 2 && a == CTRL_HOLD && s.streak == 0, "middle window resets streak");
    ctrl_step(&s, 100, 1, 1, &a);                     /* miss == miss_low counts as good */
    CHECK(s.streak == 1, "miss == miss_low is a good window");
    /* climb to the top and stay there */
    for (int i = 0; i < 20; i++) ctrl_step(&s, 100, 0, 1, &a);
    CHECK(ctrl_q(&s) == 8, "reaches the top level");
    CHECK(ctrl_step(&s, 100, 0, 1, &a) <= 8, "never above 8");
}

static void test_not_scanning_holds(void)
{
    struct ctrl_cfg c = cfg();
    c.q_start = 2;
    struct ctrl_state s;
    ctrl_init(&s, &c);
    int a;
    for (int i = 0; i < 5; i++)
        CHECK(ctrl_step(&s, 100, 100, 0, &a) == 2 && a == CTRL_HOLD, "no scan: hold");
    CHECK(s.streak == 0, "no scan: streak unchanged");
}

static void test_nodamp_ablation(void)
{
    struct ctrl_cfg c = cfg();
    c.ablation = 1;
    struct ctrl_state s;
    ctrl_init(&s, &c);
    int a;
    CHECK(s.cfg.up_windows == 1, "ablation forces up_windows = 1");
    CHECK(ctrl_step(&s, 50, 0, 1, &a) == 2 && a == CTRL_UP, "ablation: up after one good window");
    CHECK(ctrl_step(&s, 50, 0, 1, &a) == 4, "ablation: up again");
    CHECK(ctrl_step(&s, 50, 10, 1, &a) == 2 && a == CTRL_DOWN, "ablation: down is the same");
}

static void test_random_always_allowed(void)
{
    struct ctrl_cfg c = cfg();
    struct ctrl_state s;
    srand(7);
    for (int ab = 0; ab < 2; ab++) {
        c.ablation = ab;
        ctrl_init(&s, &c);
        int ok = 1, step_ok = 1;
        uint16_t prev = ctrl_q(&s);
        for (int i = 0; i < 100000; i++) {
            uint32_t n = (uint32_t)(rand() % 120);
            uint32_t m = n ? (uint32_t)(rand() % (n + 1)) : 0;
            if (rand() % 3) m = n ? (uint32_t)(rand() % (n / 20 + 1)) : 0;
            int a;
            uint16_t q = ctrl_step(&s, n, m, rand() % 10 != 0, &a);
            if (!allowed(q)) ok = 0;
            /* at most one level per window */
            if (!(q == prev || q == prev * 2 || q * 2 == prev)) step_ok = 0;
            prev = q;
        }
        CHECK(ok, "random windows: q always 1, 2, 4 or 8");
        CHECK(step_ok, "random windows: q moves at most one level per window");
    }
}

static void test_config(void)
{
    char err[160];
    struct ctrl_cfg c;
    const char *path = "bin/_ctrl_test.json";
    FILE *f = fopen(path, "w");
    if (!f) { CHECK(0, "cannot write temp config"); return; }
    fputs("{\"policy\": \"adaptive\", \"levels\": [1, 2, 4, 8], \"q_start\": 2,\n"
          " \"window_ms\": 1000, \"min_samples\": 25, \"target_ms\": 0.5,\n"
          " \"miss_high\": 0.05, \"miss_low\": 0.01, \"up_windows\": 3}\n", f);
    fclose(f);
    CHECK(ctrl_load(&c, path, err, sizeof err) == 0, "valid config loads");
    CHECK(c.q_start == 2 && c.window_ms == 1000 && c.min_samples == 25 && c.up_windows == 3 &&
          c.target_ms == 0.5 && c.miss_high == 0.05 && c.miss_low == 0.01 && c.n_levels == 4 &&
          !c.ablation, "config values are read");

    const char *bad[] = {
        "{\"levels\": [1, 3, 8], \"target_ms\": 0.5}",
        "{\"levels\": [8, 4], \"q_start\": 8, \"target_ms\": 0.5}",
        "{\"target_ms\": null}",
        "{\"target_ms\": 0.5, \"q_start\": 3}",
        "{\"target_ms\": 0.5, \"miss_low\": 0.2, \"miss_high\": 0.1}",
        "{\"target_ms\": 0.5, \"min_samples\": 0}",
        "{\"target_ms\": 0.5, \"up_windows\": 1.5}",
        "{\"target_ms\": -1}",
    };
    for (unsigned i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        f = fopen(path, "w");
        fputs(bad[i], f);
        fclose(f);
        CHECK(ctrl_load(&c, path, err, sizeof err) != 0, bad[i]);
    }
    f = fopen(path, "w");
    fputs("{\"policy\": \"adaptive_nodamp\", \"target_ms\": 0.5, \"up_windows\": 1}", f);
    fclose(f);
    CHECK(ctrl_load(&c, path, err, sizeof err) == 0 && c.ablation, "nodamp config sets the ablation");
    remove(path);
    CHECK(ctrl_load(&c, "bin/does_not_exist.json", err, sizeof err) != 0, "missing config is refused");
}

int main(void)
{
    test_sparse_windows_hold();
    test_down_and_floor();
    test_up_needs_streak();
    test_not_scanning_holds();
    test_nodamp_ablation();
    test_random_always_allowed();
    test_config();
    printf("controller tests: %d checks, %d failed (7 test groups)\n", checks, failures);
    return failures ? 1 : 0;
}
