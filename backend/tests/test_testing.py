from __future__ import annotations

import unittest
from unittest.mock import patch

from backend import testing


class FakeResponse:
    def __init__(self, html: str, content_type: str = "text/html; charset=utf-8") -> None:
        self._html = html.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._html


class TestWalmartScraper(unittest.TestCase):
    def test_scrape_walmart_product_extracts_basic_metadata(self) -> None:
        html = """
        <html>
          <head>
            <title>Raid Max Bed Bug Foaming Spray</title>
            <meta name="description" content="Fast action pest control for home protection.">
          </head>
          <body>
            <h1>Raid Max Bed Bug Foaming Spray</h1>
          </body>
        </html>
        """

        with patch("backend.testing.urlopen", return_value=FakeResponse(html)):
            result = testing.scrape_walmart_product("https://www.walmart.com/ip/raid")

        self.assertEqual(result["domain"], "www.walmart.com")
        self.assertEqual(result["page_title"], "Raid Max Bed Bug Foaming Spray")
        self.assertEqual(result["h1"], "Raid Max Bed Bug Foaming Spray")
        self.assertEqual(
            result["meta_description"],
            "Fast action pest control for home protection.",
        )
        self.assertIn("Raid Max Bed Bug Foaming Spray", result["summary"])
        self.assertEqual(result["notes"], [])

    def test_scrape_walmart_product_handles_missing_url(self) -> None:
        result = testing.scrape_walmart_product("")

        self.assertEqual(result["summary"], "")
        self.assertIn("No product URL supplied.", result["notes"])


if __name__ == "__main__":
    unittest.main()
