"""Timing of the grapple sequence: close the snare, pause, pull the pin in, latch.

Canadarm2's end effector was required to complete a free-flyer capture (snare,
rigidize, and latch) in 30 s, with the snare closing within 3 s and the latches
taking about 6 s at normal speed (Walker and Vandersluis, 1995). The pause and
the pull-in time are this model's choices, sized to fit inside the 30 s.
"""

CLOSE_TIME = 2.0  # s for the snare to close
SETTLE_TIME = 2.0  # s between closed and the start of the pull-in
RETRACT_TIME = 10.0  # s for the carriage to pull the pin in
LATCH_TIME = 6.0  # s for the latches to reach full force
PULL_IN_END = CLOSE_TIME + SETTLE_TIME + RETRACT_TIME
SEQUENCE_TIME = PULL_IN_END + LATCH_TIME


def grapple_command(t: float) -> tuple[float, float]:
    """Snare (close, retract) fractions t seconds after the grapple is triggered."""
    close = min(max(t / CLOSE_TIME, 0.0), 1.0)
    retract = min(max((t - CLOSE_TIME - SETTLE_TIME) / RETRACT_TIME, 0.0), 1.0)
    return close, retract


def latch_command(t: float) -> float:
    """Latch force fraction t seconds after the grapple is triggered, if the latches engage."""
    return min(max((t - PULL_IN_END) / LATCH_TIME, 0.0), 1.0)
