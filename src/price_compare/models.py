"""Data models for price comparison service."""

from msgspec import Struct


class Product(Struct, frozen=True):
    """Represents a product from any platform."""

    name: str
    price: int
    url: str
    platform: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "price": self.price,
            "url": self.url,
            "platform": self.platform,
        }


class SearchResult(Struct):
    """Aggregated search results from all platforms."""

    query: str
    products: list[Product]
    total_count: int

    def get_top_cheapest(self, n: int = 10) -> list[Product]:
        """Return top N cheapest products sorted by price."""
        return sorted(self.products, key=lambda p: p.price)[:n]
