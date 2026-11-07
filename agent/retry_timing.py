
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import random


@dataclass(frozen=True)
class BackoffPolicy:
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter_fraction: float = 0.25

    def __post_init__(self):
        if not 0 < self.base_delay <= self.max_delay:
            raise ValueError("Invalid backoff delays")
        if not 0 <= self.jitter_fraction <= 1:
            raise ValueError("Invalid jitter fraction")

    def delay(
        self,
        retry_number: int,
        *,
        random_value: Callable[[], float] = random.random,
    ) -> float:
        if retry_number < 1:
            raise ValueError("retry_number must be positive")

        nominal = min(
            self.max_delay,
            self.base_delay * (2 ** min(retry_number - 1, 30)),
        )

        sample = random_value()
        if not 0 <= sample <= 1:
            raise ValueError("Random sample outside [0, 1]")

        # Bounded downward jitter; never exceeds max_delay.
        return nominal * (
            1 - self.jitter_fraction * sample
        )
