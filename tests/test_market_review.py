# -*- coding: utf-8 -*-
"""Tests for localized market review wrappers."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


for _mod in ("litellm", "google.generativeai", "google.genai", "anthropic"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


from src.core.market_review import run_market_review


class MarketReviewLocalizationTestCase(unittest.TestCase):
    def _make_notifier(self) -> MagicMock:
        notifier = MagicMock()
        notifier.save_report_to_file.return_value = "/tmp/market_review.md"
        notifier.is_available.return_value = True
        notifier.send.return_value = True
        return notifier

    def test_run_market_review_uses_english_notification_title(self) -> None:
        notifier = self._make_notifier()
        market_analyzer = MagicMock()
        market_analyzer.run_daily_review.return_value = "## 2026-04-10 A-share Market Recap\n\nBody"

        with patch(
            "src.core.market_review.get_config",
            return_value=SimpleNamespace(report_language="en", market_review_region="cn"),
        ), patch("src.core.market_review.MarketAnalyzer", return_value=market_analyzer):
            result = run_market_review(notifier, send_notification=True)

        self.assertEqual(result, "## 2026-04-10 A-share Market Recap\n\nBody")
        saved_content = notifier.save_report_to_file.call_args.args[0]
        self.assertTrue(saved_content.startswith("# 🎯 Market Review\n\n"))
        sent_content = notifier.send.call_args.args[0]
        self.assertTrue(sent_content.startswith("🎯 Market Review\n\n"))
        self.assertTrue(notifier.send.call_args.kwargs["email_send_to_all"])

    def test_run_market_review_merges_both_regions_with_english_wrappers(self) -> None:
        notifier = self._make_notifier()
        cn_analyzer = MagicMock()
        cn_analyzer.run_daily_review.return_value = "CN body"
        us_analyzer = MagicMock()
        us_analyzer.run_daily_review.return_value = "US body"

        with patch(
            "src.core.market_review.get_config",
            return_value=SimpleNamespace(report_language="en", market_review_region="both"),
        ), patch(
            "src.core.market_review.MarketAnalyzer",
            side_effect=[cn_analyzer, us_analyzer],
        ):
            result = run_market_review(notifier, send_notification=False)

        self.assertIn("# A-share Market Recap\n\nCN body", result)
        self.assertIn("> US market recap follows", result)
        self.assertIn("# US Market Recap\n\nUS body", result)
        saved_content = notifier.save_report_to_file.call_args.args[0]
        self.assertTrue(saved_content.startswith("# 🎯 Market Review\n\n"))
        notifier.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
