/*
 * ctrl_replay.c - Milestone 3, Muhammad Ahmad Tariq.
 * Replays window statistics through the C controller, so the Python test
 * (analysis/test_ctrl_match.py) can check that the C controller and the
 * Python reference (analysis/controller.py) give the same q every window.
 *
 * Usage: bin/ctrl_replay CONFIG.json [nodamp] < windows.txt
 *   input lines:  fg_samples fg_misses scanning
 *   output lines: q action      (action: HOLD, UP, DOWN, SPARSE)
 */
#include <stdio.h>
#include <string.h>

#include "controller.h"

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: ctrl_replay CONFIG [nodamp] < windows\n"); return 1; }
    struct ctrl_cfg c;
    char err[160];
    if (ctrl_load(&c, argv[1], err, sizeof err)) { fprintf(stderr, "ctrl_replay: %s\n", err); return 1; }
    if (argc > 2 && !strcmp(argv[2], "nodamp")) c.ablation = 1;
    struct ctrl_state s;
    ctrl_init(&s, &c);
    static const char *names[] = {"HOLD", "UP", "DOWN", "SPARSE"};
    unsigned n, m;
    int scanning;
    while (scanf("%u %u %d", &n, &m, &scanning) == 3) {
        int a;
        unsigned q = ctrl_step(&s, n, m, scanning, &a);
        printf("%u %s\n", q, names[a]);
    }
    return 0;
}
