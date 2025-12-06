"""Base platform interface."""

from abc import ABC, abstractmethod

from price_compare.models import Product


class BasePlatform(ABC):
    """Abstract base class for e-commerce platforms."""

    __slots__ = ("_client",)

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, max_results: int = 50) -> list[Product]:
        """
        Search products by keyword.

        Args:
            query: Search keyword
            max_results: Maximum number of results to return

        Returns:
            List of Product objects
        """
