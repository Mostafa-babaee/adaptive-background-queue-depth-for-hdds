"""
controller.py - Milestone 1, Muhammad Ahmad Tariq.
Reference implementation of the background-queue-depth policies.

The C dispatcher will implement the same rule; this Python version is
the specification we test against, and it is used by fake_logs.py so the
analysis pipeline can be built before the dispatcher exists.

Policies:
    FixedPolicy(q)                  q in {1, 2, 4, 8}, never changes
    AdaptivePolicy(cfg)             windowed target-miss rule (below)
    AdaptivePolicy(cfg, ablation)   "no damping": up_windows forced to 1

Adaptive rule, evaluated once per window:
    if not scanning:                hold                      (action HOLD)
    if fg_samples < min_samples:    hold, streak unchanged    (action SPARSE)
    miss = fg_misses / fg_samples
    if miss > miss_high:            q -> next lower level, streak = 0 (DOWN)
    elif miss <= miss_low:          streak += 1
                                    if streak >= up_windows:
                                        q -> next higher level, streak = 0 (UP)
                                    else HOLD
    else:                           streak = 0 (HOLD)
q is always one of `levels`, so it is never below 1 while scanning.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HOLD, UP, DOWN, SPARSE = "HOLD", "UP", "DOWN", "SPARSE"


@dataclass
class WindowStats:
    fg_samples: int
    fg_misses: int
    scanning: bool = True


@dataclass
class ControllerConfig:
    levels: list = field(default_factory=lambda: [1, 2, 4, 8])
    q_start: int = 1
    window_ms: int = 500
    min_samples: int = 50
    target_ms: float | None = None
    miss_high: float = 0.05
    miss_low: float = 0.01
    up_windows: int = 3

    @classmethod
    def load(cls, path: str | Path) -> "ControllerConfig":
        d = json.loads(Path(path).read_text())
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in keys})

    def validate(self) -> None:
        if sorted(self.levels) != self.levels or not self.levels or self.levels[0] < 1:
            raise ValueError("levels must be increasing and >= 1")
        if self.q_start not in self.levels:
            raise ValueError("q_start must be one of levels")
        if not (0 <= self.miss_low <= self.miss_high <= 1):
            raise ValueError("need 0 <= miss_low <= miss_high <= 1")
        if self.min_samples < 1 or self.up_windows < 1 or self.window_ms < 1:
            raise ValueError("min_samples, up_windows, window_ms must be >= 1")


class FixedPolicy:
    name = "fixed"

    def __init__(self, q: int, levels=(1, 2, 4, 8)):
        if q not in levels:
            raise ValueError(f"fixed q must be one of {levels}")
        self.q = q

    def next_q(self, w: WindowStats) -> tuple[int, str]:
        return self.q, HOLD


class AdaptivePolicy:
    name = "adaptive"

    def __init__(self, cfg: ControllerConfig, ablation: bool = False):
        cfg.validate()
        self.cfg = cfg
        self.up_windows = 1 if ablation else cfg.up_windows
        self.idx = cfg.levels.index(cfg.q_start)
        self.streak = 0
        if ablation:
            self.name = "adaptive_nodamp"

    @property
    def q(self) -> int:
        return self.cfg.levels[self.idx]

    def next_q(self, w: WindowStats) -> tuple[int, str]:
        c = self.cfg
        if not w.scanning:
            return self.q, HOLD
        if w.fg_samples < c.min_samples:
            return self.q, SPARSE
        miss = w.fg_misses / w.fg_samples
        if miss > c.miss_high:
            self.streak = 0
            if self.idx > 0:
                self.idx -= 1
                return self.q, DOWN
            return self.q, HOLD
        if miss <= c.miss_low:
            self.streak += 1
            if self.streak >= self.up_windows:
                self.streak = 0
                if self.idx < len(c.levels) - 1:
                    self.idx += 1
                    return self.q, UP
            return self.q, HOLD
        self.streak = 0
        return self.q, HOLD


def make_policy(spec: str, cfg: ControllerConfig | None = None):
    """spec: 'fixed:4', 'adaptive', or 'adaptive_nodamp'."""
    if spec.startswith("fixed:"):
        return FixedPolicy(int(spec.split(":")[1]))
    cfg = cfg or ControllerConfig()
    if spec == "adaptive":
        return AdaptivePolicy(cfg)
    if spec == "adaptive_nodamp":
        return AdaptivePolicy(cfg, ablation=True)
    raise ValueError(spec)
