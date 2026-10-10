"""Timing of the grapple sequence: close the snare, pause, then pull the pin in."""

CLOSE_TIME = 2.0  # s for the snare to close
SETTLE_TIME = 2.0  # s between closed and the start of the pull-in
RETRACT_TIME = 2.0  # s for the carriage to retract
SEQUENCE_TIME = CLOSE_TIME + SETTLE_TIME + RETRACT_TIME


def grapple_command(t: float) -> tuple[float, float]:
    """Snare (close, retract) fractions t seconds after the grapple is triggered."""
    close = min(max(t / CLOSE_TIME, 0.0), 1.0)
    retract = min(max((t - CLOSE_TIME - SETTLE_TIME) / RETRACT_TIME, 0.0), 1.0)
    return close, retract
