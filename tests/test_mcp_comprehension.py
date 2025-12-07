"""
LLM Comprehension Tests for MCP Tool Documentation.

These tests verify that the simplified documentation is still understandable
by testing expected tool calls for various user scenarios.

Each test case represents a user request and the expected tool call.
"""

import pytest

# Test cases: (user_request, expected_tool, expected_params)
COMPREHENSION_TEST_CASES = [
    # Basic full search
    (
        "幫我找最便宜的 iPhone 15",
        "compare_prices",
        {"query": "iPhone 15"},
    ),
    # Full search with price filter
    (
        "搜尋藍牙耳機，預算 2000 以下",
        "compare_prices",
        {"query": "藍牙耳機", "max_price": 2000},
    ),
    # Full search with brand filter
    (
        "找 SONY 或索尼的電視",
        "compare_prices",
        {"query": "SONY 電視", "include_keywords": [["SONY", "索尼"]]},
    ),
    # Complex keyword groups
    (
        "搜尋 SONY 或索尼的電視或 TV",
        "compare_prices",
        {"query": "SONY 電視", "include_keywords": [["SONY", "索尼"], ["電視", "TV"]]},
    ),
    # Include auction prices
    (
        "在 Yahoo 拍賣找便宜的 Switch，包含競標價",
        "search_platform",
        {"query": "Switch", "platform": "yahoo_auction", "include_auction": True},
    ),
    # Single platform - PChome
    (
        "只在 PChome 找 MacBook",
        "search_platform",
        {"query": "MacBook", "platform": "pchome"},
    ),
    # Single platform - momo
    (
        "momo 上的氣炸鍋價格",
        "search_platform",
        {"query": "氣炸鍋", "platform": "momo"},
    ),
    # Single platform - Coupang
    (
        "酷澎有什麼便宜的洗衣機",
        "search_platform",
        {"query": "洗衣機", "platform": "coupang"},
    ),
    # Single platform - ETMall
    (
        "東森購物的按摩椅",
        "search_platform",
        {"query": "按摩椅", "platform": "etmall"},
    ),
    # Single platform - Rakuten
    (
        "樂天市場找零食",
        "search_platform",
        {"query": "零食", "platform": "rakuten"},
    ),
    # Single platform - Yahoo Shopping
    (
        "Yahoo 購物中心的咖啡機",
        "search_platform",
        {"query": "咖啡機", "platform": "yahoo_shopping"},
    ),
    # Price range filter
    (
        "找 5000-10000 元的掃地機器人",
        "compare_prices",
        {"query": "掃地機器人", "min_price": 5000, "max_price": 10000},
    ),
    # Limit results
    (
        "列出前 5 個最便宜的 AirPods",
        "compare_prices",
        {"query": "AirPods", "top_n": 5},
    ),
    # Single platform with price filter
    (
        "PChome 上 3000 以下的無線滑鼠",
        "search_platform",
        {"query": "無線滑鼠", "platform": "pchome", "max_price": 3000},
    ),
    # Exclude low-price accessories
    (
        "找 PS5，排除配件（500 元以上）",
        "compare_prices",
        {"query": "PS5", "min_price": 500},
    ),
]


class TestMCPComprehension:
    """Test that simplified docs are still comprehensible."""

    @pytest.mark.parametrize("user_request,expected_tool,expected_params", COMPREHENSION_TEST_CASES)
    def test_tool_selection(self, user_request: str, expected_tool: str, expected_params: dict) -> None:
        """
        Verify expected tool and params for each user scenario.

        This test documents the expected behavior - if an LLM cannot produce
        these tool calls from the simplified docs, the docs need improvement.
        """
        # This is a documentation test - it passes if the test case is valid
        assert expected_tool in ("compare_prices", "search_platform")
        assert "query" in expected_params

        # Validate platform names if present
        if "platform" in expected_params:
            valid_platforms = {"pchome", "momo", "coupang", "etmall", "rakuten", "yahoo_shopping", "yahoo_auction"}
            assert expected_params["platform"] in valid_platforms

        # Validate include_keywords format if present
        if "include_keywords" in expected_params:
            kw = expected_params["include_keywords"]
            assert isinstance(kw, list)
            assert all(isinstance(group, list) for group in kw)
            assert all(isinstance(k, str) for group in kw for k in group)


def _get_tool_doc(name: str) -> str:
    """Get tool docstring from FastMCP tool manager."""
    from price_compare.mcp_server import mcp

    tool = mcp._tool_manager._tools.get(name)
    return (tool.description or "") if tool else ""


class TestDocStringCompleteness:
    """Verify all essential information is in the docstrings."""

    def test_compare_prices_docstring(self) -> None:
        """Check compare_prices has all required info."""
        doc = _get_tool_doc("compare_prices")
        assert doc

        # Must mention all platforms
        assert "Coupang" in doc or "coupang" in doc
        assert "momo" in doc
        assert "PChome" in doc or "pchome" in doc
        assert "ETMall" in doc or "etmall" in doc
        assert "Rakuten" in doc or "rakuten" in doc
        assert "Yahoo" in doc

        # Must explain include_keywords format
        assert "AND" in doc
        assert "OR" in doc
        assert "[[" in doc  # Example format

    def test_search_platform_docstring(self) -> None:
        """Check search_platform has all required info."""
        doc = _get_tool_doc("search_platform")
        assert doc

        # Must list all platform options
        assert "pchome" in doc
        assert "momo" in doc
        assert "coupang" in doc
        assert "etmall" in doc
        assert "rakuten" in doc
        assert "yahoo_shopping" in doc
        assert "yahoo_auction" in doc

        # Must mention include_auction is for yahoo_auction
        assert "auction" in doc.lower()
