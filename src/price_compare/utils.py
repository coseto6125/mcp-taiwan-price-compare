"""Shared utilities for price comparison service."""

import itertools
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
    if isinstance(value, float):
        return int(value)
    try:
        return int(float(str(value).replace(",", "").replace("$", "").strip()))
    except (TypeError, ValueError):
        return None


def calc_search_multiplier(require_words: KeywordGroups) -> int:
    """
    Calculate search volume multiplier based on require_words filter strictness.

    Each AND group roughly halves pass rate, so multiply by 2^n (capped at 4x to avoid 429).
    """
    return min(1 << len(require_words), 4) if require_words else 1
