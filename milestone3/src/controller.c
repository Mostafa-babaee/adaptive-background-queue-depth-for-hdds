/*
 * controller.c - Milestone 3, Muhammad Ahmad Tariq.
 * Adaptive background queue-depth controller. See controller.h for the rule.
 */
#define _GNU_SOURCE
#include "controller.h"

#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void ctrl_defaults(struct ctrl_cfg *c)
{
    memset(c, 0, sizeof *c);
    c->levels[0] = 1; c->levels[1] = 2; c->levels[2] = 4; c->levels[3] = 8;
    c->n_levels = 4;
    c->q_start = 1;
    c->window_ms = 1000;
    c->min_samples = 25;
    c->target_ms = 0;
    c->miss_high = 0.05;
    c->miss_low = 0.01;
    c->up_windows = 3;
    c->ablation = 0;
}

static void say(char *err, int errlen, const char *msg)
{
    if (err && errlen > 0) snprintf(err, (size_t)errlen, "%s", msg);
}

int ctrl_validate(const struct ctrl_cfg *c, char *err, int errlen)
{
    static const uint16_t allowed[] = {1, 2, 4, 8};
    if (c->n_levels < 1 || c->n_levels > CTRL_MAX_LEVELS) { say(err, errlen, "levels: 1 to 4 values"); return -1; }
    int start_ok = 0;
    for (int i = 0; i < c->n_levels; i++) {
        int ok = 0;
        for (int k = 0; k < 4; k++) if (c->levels[i] == allowed[k]) ok = 1;
        if (!ok) { say(err, errlen, "levels must be taken from 1, 2, 4, 8"); return -1; }
        if (i && c->levels[i] <= c->levels[i - 1]) { say(err, errlen, "levels must be increasing"); return -1; }
        if (c->levels[i] == c->q_start) start_ok = 1;
    }
    if (!start_ok) { say(err, errlen, "q_start must be one of levels"); return -1; }
    if (!(c->target_ms > 0) || !isfinite(c->target_ms)) { say(err, errlen, "target_ms must be a positive number"); return -1; }
    if (!(c->miss_low >= 0 && c->miss_low <= c->miss_high && c->miss_high <= 1)) {
        say(err, errlen, "need 0 <= miss_low <= miss_high <= 1"); return -1;
    }
    if (c->min_samples < 1 || c->up_windows < 1 || c->window_ms < 1) {
        say(err, errlen, "min_samples, up_windows and window_ms must be >= 1"); return -1;
    }
    return 0;
}

void ctrl_init(struct ctrl_state *s, const struct ctrl_cfg *c)
{
    memset(s, 0, sizeof *s);
    s->cfg = *c;
    if (s->cfg.ablation) s->cfg.up_windows = 1;
    for (int i = 0; i < c->n_levels; i++)
        if (c->levels[i] == c->q_start) s->idx = i;
}

uint16_t ctrl_step(struct ctrl_state *s, uint32_t fg_samples, uint32_t fg_misses,
                   int scanning, int *action)
{
    const struct ctrl_cfg *c = &s->cfg;
    int act = CTRL_HOLD;
    if (!scanning) {
        act = CTRL_HOLD;
    } else if (fg_samples < c->min_samples) {
        act = CTRL_SPARSE;                       /* too little data: hold q and streak */
    } else {
        double miss = (double)fg_misses / (double)fg_samples;
        if (miss > c->miss_high) {
            s->streak = 0;
            if (s->idx > 0) { s->idx--; act = CTRL_DOWN; }
        } else if (miss <= c->miss_low) {
            s->streak++;
            if (s->streak >= c->up_windows) {
                s->streak = 0;
                if (s->idx < c->n_levels - 1) { s->idx++; act = CTRL_UP; }
            }
        } else {
            s->streak = 0;
        }
    }
    switch (act) {
    case CTRL_UP: s->n_up++; break;
    case CTRL_DOWN: s->n_down++; break;
    case CTRL_SPARSE: s->n_sparse++; break;
    default: s->n_hold++; break;
    }
    if (action) *action = act;
    return ctrl_q(s);
}

/* ---------------------------------------------------------- config file */

/* Find "key": in text and return a pointer just after the colon, or NULL. */
static const char *find_key(const char *text, const char *key)
{
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\"", key);
    const char *p = text;
    while ((p = strstr(p, pat))) {
        const char *q = p + strlen(pat);
        while (isspace((unsigned char)*q)) q++;
        if (*q == ':') {
            q++;
            while (isspace((unsigned char)*q)) q++;
            return q;
        }
        p++;
    }
    return NULL;
}

static int get_num(const char *text, const char *key, double *out, int required, int *is_null)
{
    const char *p = find_key(text, key);
    if (is_null) *is_null = 0;
    if (!p) return required ? -1 : 1;
    if (!strncmp(p, "null", 4)) { if (is_null) *is_null = 1; return required ? -1 : 1; }
    char *end;
    errno = 0;
    double v = strtod(p, &end);
    if (end == p || errno || !isfinite(v)) return -1;
    *out = v;
    return 0;
}

static int get_uint(const char *text, const char *key, uint32_t *out)
{
    double v;
    int r = get_num(text, key, &v, 0, NULL);
    if (r) return r;
    if (v < 0 || v > 4294967295.0 || v != floor(v)) return -1;
    *out = (uint32_t)v;
    return 0;
}

int ctrl_load(struct ctrl_cfg *c, const char *path, char *err, int errlen)
{
    FILE *f = fopen(path, "r");
    if (!f) { say(err, errlen, "cannot open controller config"); return -1; }
    char text[8192];
    size_t n = fread(text, 1, sizeof text - 1, f);
    int too_big = !feof(f);
    fclose(f);
    if (too_big) { say(err, errlen, "controller config is too large"); return -1; }
    text[n] = 0;

    ctrl_defaults(c);
    const char *lv = find_key(text, "levels");
    if (lv) {
        if (*lv != '[') { say(err, errlen, "levels must be a list"); return -1; }
        lv++;
        c->n_levels = 0;
        for (;;) {
            while (isspace((unsigned char)*lv) || *lv == ',') lv++;
            if (*lv == ']') break;
            char *end;
            long v = strtol(lv, &end, 10);
            if (end == lv || c->n_levels >= CTRL_MAX_LEVELS || v < 1 || v > 8) {
                say(err, errlen, "levels must be a list of 1 to 4 values from 1, 2, 4, 8"); return -1;
            }
            c->levels[c->n_levels++] = (uint16_t)v;
            lv = end;
        }
    }
    uint32_t u;
    int r;
    if ((r = get_uint(text, "q_start", &u)) < 0) goto bad; else if (!r) c->q_start = (uint16_t)u;
    if ((r = get_uint(text, "window_ms", &u)) < 0) goto bad; else if (!r) c->window_ms = u;
    if ((r = get_uint(text, "min_samples", &u)) < 0) goto bad; else if (!r) c->min_samples = u;
    if ((r = get_uint(text, "up_windows", &u)) < 0) goto bad; else if (!r) c->up_windows = u;
    double d;
    int is_null;
    if ((r = get_num(text, "target_ms", &d, 0, &is_null)) < 0) goto bad; else if (!r) c->target_ms = d;
    if ((r = get_num(text, "miss_high", &d, 0, NULL)) < 0) goto bad; else if (!r) c->miss_high = d;
    if ((r = get_num(text, "miss_low", &d, 0, NULL)) < 0) goto bad; else if (!r) c->miss_low = d;
    const char *pol = find_key(text, "policy");
    if (pol && !strncmp(pol, "\"adaptive_nodamp\"", 17)) c->ablation = 1;
    return ctrl_validate(c, err, errlen);
bad:
    say(err, errlen, "controller config has a bad number");
    return -1;
}
