"""
Generator utilities — deterministic weighted choice.

Faker's `random_element` does NOT support weights (passing tuples returns the
tuple, not the first element). `random.choices` breaks determinism because it
uses the stdlib RNG, not Faker's seed.

This helper bridges both:
  - Uses Faker's seeded RNG via `fake.random_int(1, total_weight)`
  - Returns the chosen element, not a tuple
"""
from __future__ import annotations

from typing import TypeVar

from faker import Faker

T = TypeVar("T")


def weighted_choice(
    fake: Faker,
    elements: list[T],
    weights: list[float | int],
) -> T:
    """
    Deterministic weighted choice using Faker's seeded RNG.

    Args:
        fake: Faker instance (with seed set)
        elements: list of choices
        weights: parallel list of non-negative weights (must sum > 0)

    Returns:
        One element, chosen with probability proportional to its weight.
    """
    if len(elements) != len(weights):
        raise ValueError("elements and weights must have the same length")
    if not elements:
        raise ValueError("elements must not be empty")

    # Convert floats to ints so we can use fake.random_int
    # Scale by 1000 for 3 decimals of precision
    scaled = [max(0, int(round(w * 1000))) for w in weights]
    total = sum(scaled)
    if total <= 0:
        raise ValueError("sum of weights must be > 0")

    pick = fake.random_int(min=1, max=total)
    cum = 0
    for elem, w in zip(elements, scaled):
        cum += w
        if pick <= cum:
            return elem
    return elements[-1]  # fallback (should not happen)
