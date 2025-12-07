"""Base platform interface."""

from abc import ABC, abstractmethod

from price_compare.models import Product
from price_compare.utils import KeywordGroups


class BasePlatform(ABC):
    """Abstract base class for e-commerce platforms."""

    __slots__ = ()

    name: str = "base"

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 100,
        min_price: int = 0,
        max_price: int = 0,
        require_words: KeywordGroups = None,
        **kwargs: object,
    ) -> list[Product]:
        """Search products by keyword."""
