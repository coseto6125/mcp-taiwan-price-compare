"""Platform implementations."""

from price_compare.platforms.base import BasePlatform
from price_compare.platforms.books import BooksPlatform
from price_compare.platforms.buy123 import Buy123Platform
from price_compare.platforms.costco import CostcoPlatform
from price_compare.platforms.coupang import CoupangPlatform
from price_compare.platforms.etmall import ETMallPlatform
from price_compare.platforms.momo import MomoPlatform
from price_compare.platforms.pchome import PChomePlatform
from price_compare.platforms.pcone import PconePlatform
from price_compare.platforms.pxbox import PxboxPlatform
from price_compare.platforms.rakuten import RakutenPlatform
from price_compare.platforms.ruten import RutenPlatform
from price_compare.platforms.uniprosperity import UniProsperityPlatform
from price_compare.platforms.yahoo_auction import YahooAuctionPlatform
from price_compare.platforms.yahoo_shopping import YahooShoppingPlatform

__all__ = [
    "BasePlatform",
    "BooksPlatform",
    "Buy123Platform",
    "CostcoPlatform",
    "CoupangPlatform",
    "ETMallPlatform",
    "MomoPlatform",
    "PChomePlatform",
    "PconePlatform",
    "PxboxPlatform",
    "RakutenPlatform",
    "RutenPlatform",
    "UniProsperityPlatform",
    "YahooAuctionPlatform",
    "YahooShoppingPlatform",
]
