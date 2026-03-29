# -*- coding: utf-8 -*-
"""Regression tests for market review soft-timeout behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.core.market_review import run_market_review


class TestMarketReviewBudget(unittest.TestCase):
    @patch("src.core.market_review.get_config")
    @patch("src.core.market_review.time.monotonic", side_effect=[0.0, 9.0])
    @patch("src.core.market_review.MarketAnalyzer")
    def test_run_market_review_skips_second_region_when_budget_is_nearly_exhausted(
        self,
        mock_market_analyzer,
        _mock_monotonic,
        mock_get_config,
    ) -> None:
        mock_get_config.return_value = SimpleNamespace(market_review_region="both")
        notifier = MagicMock()
        notifier.save_report_to_file.return_value = "/tmp/market_review.md"
        notifier.is_available.return_value = False

        cn_analyzer = MagicMock()
        cn_analyzer.run_daily_review.return_value = "CN report"
        us_analyzer = MagicMock()
        us_analyzer.run_daily_review.return_value = "US report"
        mock_market_analyzer.side_effect = [cn_analyzer, us_analyzer]

        report = run_market_review(
            notifier=notifier,
            override_region="both",
            send_notification=False,
            soft_timeout_deadline=10.0,
            soft_timeout_grace_seconds=2.0,
        )

        self.assertIn("A股大盘复盘", report)
        self.assertNotIn("美股大盘复盘", report)
        cn_analyzer.run_daily_review.assert_called_once()
        us_analyzer.run_daily_review.assert_not_called()


if __name__ == "__main__":
    unittest.main()
