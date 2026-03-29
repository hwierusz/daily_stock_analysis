# -*- coding: utf-8 -*-
"""Regression tests for scheduled mode stock selection behavior."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

import main
from src.config import Config


class _DummyConfig(SimpleNamespace):
    def validate(self):
        return []


class MainScheduleModeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.env_path.write_text("STOCK_LIST=600519\n", encoding="utf-8")
        self.env_patch = patch.dict(os.environ, {"ENV_FILE": str(self.env_path)}, clear=False)
        self.env_patch.start()
        Config.reset_instance()

    def tearDown(self) -> None:
        Config.reset_instance()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _make_args(self, **overrides):
        defaults = {
            "debug": False,
            "stocks": None,
            "webui": False,
            "webui_only": False,
            "serve": False,
            "serve_only": False,
            "host": "0.0.0.0",
            "port": 8000,
            "backtest": False,
            "market_review": False,
            "schedule": False,
            "no_run_immediately": False,
            "no_notify": False,
            "no_market_review": False,
            "dry_run": False,
            "workers": 1,
            "force_run": False,
            "single_notify": False,
            "no_context_snapshot": False,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def _make_config(self, **overrides):
        defaults = {
            "log_dir": self.temp_dir.name,
            "webui_enabled": False,
            "dingtalk_stream_enabled": False,
            "feishu_stream_enabled": False,
            "schedule_enabled": False,
            "schedule_time": "18:00",
            "schedule_run_immediately": True,
            "run_immediately": True,
            "daily_run_soft_timeout_seconds": 1500,
            "daily_run_soft_timeout_grace_seconds": 180,
            "market_review_enabled": True,
            "merge_email_notification": False,
            "single_stock_notify": False,
            "analysis_delay": 0,
            "backtest_enabled": False,
            "stock_list": ["600519"],
            "trading_day_check_enabled": True,
            "market_review_region": "cn",
            "gemini_api_key": None,
            "openai_api_key": None,
        }
        defaults.update(overrides)
        return _DummyConfig(**defaults)

    def test_schedule_mode_ignores_cli_stock_snapshot(self) -> None:
        args = self._make_args(schedule=True, stocks="600519,000001")
        config = self._make_config(schedule_enabled=False)
        scheduled_call = {}

        def fake_run_with_schedule(task, schedule_time, run_immediately, background_tasks=None):
            scheduled_call["schedule_time"] = schedule_time
            scheduled_call["run_immediately"] = run_immediately
            scheduled_call["background_tasks"] = background_tasks or []
            task()

        with patch("main.parse_arguments", return_value=args), \
             patch("main.get_config", return_value=config), \
             patch("main.setup_logging"), \
             patch("main.run_full_analysis") as run_full_analysis, \
             patch("main.logger.warning") as warning_log, \
             patch("src.scheduler.run_with_schedule", side_effect=fake_run_with_schedule):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            scheduled_call,
            {"schedule_time": "18:00", "run_immediately": True, "background_tasks": []},
        )
        run_full_analysis.assert_called_once_with(config, args, None)
        warning_log.assert_any_call(
            "定时模式下检测到 --stocks 参数；计划执行将忽略启动时股票快照，并在每次运行前重新读取最新的 STOCK_LIST。"
        )

    def test_single_run_keeps_cli_stock_override(self) -> None:
        args = self._make_args(stocks="600519,000001")
        config = self._make_config(run_immediately=True)

        with patch("main.parse_arguments", return_value=args), \
             patch("main.get_config", return_value=config), \
             patch("main.setup_logging"), \
             patch("main.run_full_analysis") as run_full_analysis:
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        run_full_analysis.assert_called_once_with(config, args, ["600519", "000001"])

    def test_run_full_analysis_skips_market_review_when_remaining_budget_is_too_small(self) -> None:
        args = self._make_args(no_notify=True)
        config = self._make_config(
            daily_run_soft_timeout_seconds=1,
            daily_run_soft_timeout_grace_seconds=1,
            trading_day_check_enabled=False,
        )
        pipeline = MagicMock()
        pipeline.run.return_value = []

        with patch("main.StockAnalysisPipeline", return_value=pipeline), \
             patch("main.run_market_review") as run_market_review, \
             patch("main.time.monotonic", side_effect=[0.0, 1.0]):
            main.run_full_analysis(config, args, ["600519"])

        run_market_review.assert_not_called()
        pipeline.run.assert_called_once()

    def test_market_review_only_mode_skips_when_budget_is_already_exhausted(self) -> None:
        args = self._make_args(market_review=True, no_notify=True, force_run=True)
        config = self._make_config(
            daily_run_soft_timeout_seconds=1,
            daily_run_soft_timeout_grace_seconds=1,
            trading_day_check_enabled=False,
        )
        config.has_search_capability_enabled = lambda: False

        with patch("main.parse_arguments", return_value=args), \
             patch("main.get_config", return_value=config), \
             patch("main.setup_logging"), \
             patch("main.run_market_review") as run_market_review, \
             patch("main.time.monotonic", side_effect=[0.0, 1.0]):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        run_market_review.assert_not_called()


if __name__ == "__main__":
    unittest.main()
