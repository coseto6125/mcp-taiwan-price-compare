"""Shared utilities for price comparison service."""

import itertools
import math
from typing import Any, Iterable

# Type alias for keyword groups: [[group1_kw1, group1_kw2], [group2_kw1, group2_kw2]]
# Logic: (group1_kw1 OR group1_kw2) AND (group2_kw1 OR group2_kw2)
type KeywordGroups = list[list[str]] | None


def flatten(iterable: Iterable[Iterable[Any]]) -> Iterable[Any]:
    """
    Flatten an iterable of iterables.

    Args:
        iterable: An iterable containing other iterables

    Returns:
        A flat iterable containing all elements
    """
    try:
        from tkinter import _flatten  # type: ignore[attr-defined]  # noqa: RUF100

        return _flatten(list(iterable))
    except ImportError:
        return itertools.chain.from_iterable(iterable)


def prepare_keyword_groups(groups: KeywordGroups) -> tuple[tuple[str, ...], ...] | None:
    """
    Pre-process keyword groups for efficient matching.

    Converts to lowercase tuples for faster iteration.

    Args:
        groups: List of keyword groups, e.g. [["SONY", "索尼"], ["電視", "TV"]]

    Returns:
        Tuple of tuples with lowercased keywords, or None if empty
    """
    if not groups:
        return None
    return tuple(tuple(kw.lower() for kw in group) for group in groups)


def matches_keywords(name_lower: str, prepared_groups: tuple[tuple[str, ...], ...] | None) -> bool:
    """
    Check if name matches all keyword groups.

    Args:
        name_lower: Product name in lowercase
        prepared_groups: Pre-processed keyword groups from prepare_keyword_groups()

    Returns:
        True if name contains at least one keyword from EACH group
    """
    if not prepared_groups:
        return True
    return all(any(kw in name_lower for kw in group) for group in prepared_groups)


def parse_price(value: object) -> int | None:
    """
    Coerce a site's price field to whole TWD, or None when it is not a price.

    Sites hand back ints, floats, and strings like "1,299" or "$1,299"; every adapter
    used to strip and cast this itself, each guarding failure differently.

    Args:
        value: Raw price as the site reported it.

    Returns:
        The price as an int, or None if it cannot be read as one.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        # NaN and infinities reach here from JSON payloads and from strings like
        # "1e309"; int() raises on both, which would escape the whole search.
        number = value if isinstance(value, float) else float(str(value).replace(",", "").replace("$", "").strip())
        return int(number) if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None



def calc_search_multiplier(require_words: KeywordGroups) -> int:
    """
    Widen a candidate pool in proportion to how much a keyword filter will discard.

    Each AND group roughly halves the pass rate, so ask for 2^n as many, capped at 4x
    to stay clear of the rate limits a much larger request would attract.

    Args:
        require_words: Keyword groups the caller will filter on, or None.

    Returns:
        The multiplier to apply to the pool size.
    """
    return min(1 << len(require_words), 4) if require_words else 1
