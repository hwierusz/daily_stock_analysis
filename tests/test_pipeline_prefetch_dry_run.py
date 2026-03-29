# -*- coding: utf-8 -*-
"""
Regression tests for prefetch behavior in StockAnalysisPipeline.run().
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.core.pipeline import StockAnalysisPipeline


class TestPipelinePrefetchBehavior(unittest.TestCase):
    @staticmethod
    def _build_pipeline(process_result):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.max_workers = 1
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False
        pipeline.process_single_stock = MagicMock(return_value=process_result)
        pipeline._save_local_report = MagicMock()
        pipeline._send_notifications = MagicMock()
        pipeline.config = SimpleNamespace(
            stock_list=["000001"],
            refresh_stock_list=lambda: None,
            single_stock_notify=False,
            report_type="simple",
            analysis_delay=0,
        )
        return pipeline

    def test_run_dry_run_skips_stock_name_prefetch(self):
        pipeline = self._build_pipeline(process_result=None)

        pipeline.run(stock_codes=["000001"], dry_run=True, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_not_called()

    def test_run_non_dry_run_prefetches_stock_names(self):
        pipeline = self._build_pipeline(process_result=SimpleNamespace(code="000001"))

        pipeline.run(stock_codes=["000001"], dry_run=False, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_called_once_with(
            ["000001"], use_bulk=False
        )

    def test_run_stops_submitting_new_stocks_when_soft_timeout_buffer_is_hit(self):
        pipeline = self._build_pipeline(process_result=SimpleNamespace(code="000001"))
        pipeline.process_single_stock = MagicMock(
            side_effect=[
                SimpleNamespace(code="000001"),
                SimpleNamespace(code="000002"),
                SimpleNamespace(code="000003"),
            ]
        )

        with patch("src.core.pipeline.time.monotonic", side_effect=[0.0, 0.45, 0.45]):
            results = pipeline.run(
                stock_codes=["000001", "000002", "000003"],
                dry_run=False,
                send_notification=False,
                soft_timeout_deadline=0.5,
                soft_timeout_grace_seconds=0.1,
            )

        self.assertEqual([result.code for result in results], ["000001"])
        self.assertEqual(pipeline.process_single_stock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
