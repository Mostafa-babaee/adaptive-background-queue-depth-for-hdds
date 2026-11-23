/* test_rl.c - Milestone 4. Checks the RL policy's state buckets, hold rules
 * and action mapping against the generated table. No disk needed. */
#include <stdio.h>
#include <stdlib.h>
#include "rl_policy.h"
#include "rl_table.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { fprintf(stderr, "FAIL: %s (line %d)\n", msg, __LINE__); fails++; } } while (0)

int main(void)
{
    struct rl_state s; int act;

    /* Table entries reached from q = 1 with quiet load (fg 50, miss 0 -> bucket 0). */
    rl_init(&s);
    CHECK(rl_q(&s) == 1, "start q is 1");
    uint16_t q = rl_step(&s, 50, 0, 1, &act);
    CHECK(q == (uint16_t)(1 << RL_TABLE[0][0][0]), "q follows RL_TABLE[0][0][0]");

    /* Miss bucket boundaries: 1 % and 5 % inclusive go to the lower bucket. */
    for (int idx = 0; idx < 4; idx++) {
        struct rl_state t; rl_init(&t); t.idx = idx;
        rl_step(&t, 50, 0, 1, &act);                       /* miss 0 % -> bucket 0 */
        CHECK(t.idx == RL_TABLE[idx][0][0], "bucket 0 quiet");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 100, 1, 1, &act);                      /* miss exactly 1 % -> bucket 0 */
        CHECK(t.idx == RL_TABLE[idx][0][1], "1 % is bucket 0, busy load bucket 1");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 100, 5, 1, &act);                      /* miss exactly 5 % -> bucket 1 */
        CHECK(t.idx == RL_TABLE[idx][1][1], "5 % is bucket 1");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 100, 6, 1, &act);                      /* miss 6 % -> bucket 2 */
        CHECK(t.idx == RL_TABLE[idx][2][1], "6 % is bucket 2");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 2000, 10, 1, &act);                    /* overload load bucket 2 */
        CHECK(t.idx == RL_TABLE[idx][0][2], "2000 reads is load bucket 2");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 499, 0, 1, &act);                      /* 499 reads: load bucket 1 */
        CHECK(t.idx == RL_TABLE[idx][0][1], "499 reads is load bucket 1");
        rl_init(&t); t.idx = idx;
        rl_step(&t, 500, 0, 1, &act);                      /* 500 reads: load bucket 2 */
        CHECK(t.idx == RL_TABLE[idx][0][2], "500 reads is load bucket 2");
    }

    /* Hold rules: not scanning, and too few samples, must not change q. */
    rl_init(&s); s.idx = 2;
    rl_step(&s, 2000, 2000, 0, &act);
    CHECK(s.idx == 2 && act == CTRL_HOLD, "not scanning holds q");
    rl_step(&s, 24, 24, 1, &act);
    CHECK(s.idx == 2 && act == CTRL_SPARSE, "fewer than 25 samples holds q");

    /* Action mapping: a move up or down reports UP or DOWN. */
    for (int idx = 0; idx < 4; idx++)
        for (int b = 0; b < 3; b++)
            for (int l = 0; l < 3; l++) {
                struct rl_state t; rl_init(&t); t.idx = idx;
                uint32_t samples = (l == 0) ? 50 : (l == 1 ? 200 : 2000);
                uint32_t misses = (b == 0) ? 0 : (b == 1 ? (uint32_t)(samples * 0.03) : (uint32_t)(samples * 0.5));
                rl_step(&t, samples, misses, 1, &act);
                int want = RL_TABLE[idx][b][l];
                CHECK(t.idx == want, "state maps to table entry");
                if (want > idx) CHECK(act == CTRL_UP, "up move reports UP");
                else if (want < idx) CHECK(act == CTRL_DOWN, "down move reports DOWN");
                else CHECK(act == CTRL_HOLD, "same level reports HOLD");
            }

    if (fails) { fprintf(stderr, "%d check(s) failed\n", fails); return 1; }
    printf("test_rl: all checks passed\n");
    return 0;
}
