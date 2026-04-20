# -*- coding: utf-8 -*-
"""
Regression tests for prefetch behavior in StockAnalysisPipeline.run().
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.core.pipeline import StockAnalysisPipeline, _DryRunTaskResult


class TestPipelinePrefetchBehavior(unittest.TestCase):
    @staticmethod
    def _build_pipeline(process_result):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.max_workers = 1
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False
        pipeline.process_single_stock = MagicMock(return_value=process_result)
        pipeline.config = SimpleNamespace(
            stock_list=["000001"],
            refresh_stock_list=lambda: None,
            single_stock_notify=False,
            report_type="simple",
            analysis_delay=0,
            agent_mode=False,
            agent_skills=[],
        )
        return pipeline

    def test_run_dry_run_skips_stock_name_prefetch(self):
        pipeline = self._build_pipeline(
            process_result=_DryRunTaskResult(code="000001", success=True)
        )

        pipeline.run(stock_codes=["000001"], dry_run=True, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_not_called()

    def test_run_non_dry_run_prefetches_stock_names(self):
        pipeline = self._build_pipeline(process_result=SimpleNamespace(code="000001"))

        pipeline.run(stock_codes=["000001"], dry_run=False, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_called_once_with(
            ["000001"], use_bulk=False
        )

    def test_run_dry_run_counts_real_step1_results_without_rechecking_db(self):
        pipeline = self._build_pipeline(process_result=None)
        pipeline.process_single_stock.side_effect = [
            _DryRunTaskResult(code="600519", success=True),
            _DryRunTaskResult(code="AAPL", success=False, error_message="历史K线缓存准备失败"),
        ]

        pipeline.run(
            stock_codes=["600519", "AAPL"],
            dry_run=True,
            send_notification=False,
        )

        pipeline.db.has_today_data.assert_not_called()

    def test_run_uses_one_frozen_reference_time_for_all_dry_run_tasks(self):
        pipeline = self._build_pipeline(
            process_result=_DryRunTaskResult(code="600519", success=True)
        )

        pipeline.run(
            stock_codes=["600519", "AAPL"],
            dry_run=True,
            send_notification=False,
        )

        task_reference_times = [
            recorded_call.kwargs["current_time"]
            for recorded_call in pipeline.process_single_stock.call_args_list
        ]

        self.assertEqual(len(task_reference_times), 2)
        self.assertEqual(len({id(value) for value in task_reference_times}), 1)
        self.assertIs(task_reference_times[0], task_reference_times[1])

    def test_run_dry_run_agent_mode_does_not_recompute_success_from_db(self):
        pipeline = self._build_pipeline(process_result=None)
        pipeline.config.agent_mode = True
        pipeline.process_single_stock.return_value = _DryRunTaskResult(
            code="SH600519",
            success=False,
            error_message="历史K线缓存准备失败",
        )

        pipeline.run(
            stock_codes=["SH600519"],
            dry_run=True,
            send_notification=False,
        )

        pipeline.db.has_today_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
