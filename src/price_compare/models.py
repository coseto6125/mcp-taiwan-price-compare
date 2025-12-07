"""Data models for price comparison service."""

from msgspec import Struct


class Product(Struct, frozen=True):
    """Represents a product from any platform."""

    name: str
    price: int
    url: str
    platform: str


class SearchResult(Struct):
    """Aggregated search results from all platforms."""

    query: str
    products: list[Product]
    total_count: int
