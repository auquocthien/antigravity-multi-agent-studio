"""Test suite for 5-tier Hierarchical Multi-Agent Engine and Tree UI."""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.engine import (
    AgentRole,
    AgentState,
    StandardMessagePacket,
    HistoryLogger,
    SubAgentConfig,
    SubAgentWorker,
    AgentOrchestrator,
    CustomizationDiscovery,
)
from src.ui.main_window import MainWindow


class TestHierarchicalArchitecture(unittest.TestCase):
    """Test suite verifying hierarchical pipeline, dynamic reasoning, and packet persistence."""

    @classmethod
    def setUpClass(cls) -> None:
        app = QApplication.instance()
        if app is None:
            cls.app = QApplication(sys.argv)
        else:
            cls.app = app

    def test_01_standard_packet_and_history_logging(self) -> None:
        """Verify StandardMessagePacket serialization and JSONL persistence."""
        test_dir = "/tmp/test_agent_history"
        logger = HistoryLogger(base_dir=test_dir)

        pkt = StandardMessagePacket(
            intent="TASK_DISPATCH",
            from_agent="agent_leader",
            to_agent="agent_dev_ui",
            model="Gemini 3.8 Flash",
            effort="medium",
            payload="Create tree node component",
            scope_files=["src/ui/tree_node.py"]
        )

        logger.record_packet(pkt)
        self.assertTrue(os.path.exists(logger.log_file))

        with open(logger.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("TASK_DISPATCH", lines[0])
        self.assertIn("agent_leader", lines[0])

    def test_02_subagent_worker_execution_and_signals(self) -> None:
        """Verify an individual SubAgentWorker emits stream, status, and packet signals."""
        logger = HistoryLogger(base_dir="/tmp/test_agent_history")
        cfg = SubAgentConfig(
            agent_id="test_worker",
            name="Test Worker",
            role=AgentRole.DEV_UI,
            avatar="💻",
            model="Gemini 3.8 Flash",
            thinking_level="low"
        )
        worker = SubAgentWorker(cfg, "Build test widget", logger)

        streams = []
        statuses = []
        packets = []

        worker.stream_signal.connect(lambda a, s, c: streams.append((s, c)))
        worker.status_signal.connect(lambda a, st: statuses.append(st))
        worker.message_bus_signal.connect(lambda pkt: packets.append(pkt))

        worker.start()
        while worker.isRunning():
            self.app.processEvents()

        self.assertTrue(worker.wait(3000))
        self.app.processEvents()

        self.assertGreater(len(streams), 0)
        self.assertIn(AgentState.COMPLETED.value, statuses)
        self.assertGreaterEqual(len(packets), 1)

    def test_03_hierarchical_orchestrator_pipeline_stages(self) -> None:
        """Verify complete 5-agent hierarchical pipeline advancing through stages."""
        orch = AgentOrchestrator()
        packets_received = []
        finished_results = []
        adjusted_events = []

        orch.message_bus_forwarded.connect(lambda pkt: packets_received.append(pkt))
        orch.pipeline_finished.connect(lambda ok, msg: finished_results.append((ok, msg)))
        orch.subordinate_adjusted.connect(lambda a, m, e: adjusted_events.append((a, m, e)))

        orch.dispatch_hierarchical_pipeline("Build full stack app with tests")

        # Let stages run (Leader -> 2 Devs -> Reviewer -> Tester)
        import time
        max_wait_seconds = 4.0
        start_t = time.time()
        while orch._is_active and (time.time() - start_t) < max_wait_seconds:
            self.app.processEvents()
            self.app.sendPostedEvents()
            time.sleep(0.02)
            if len(adjusted_events) > 0 and len(packets_received) > 0:
                break

        orch.stop_all()

        # Verify Leader adjusted Dev 2 dynamically
        self.assertGreaterEqual(len(adjusted_events), 1)
        self.assertEqual(adjusted_events[0][0], "agent_dev_core")
        self.assertEqual(adjusted_events[0][2], "high")

        # Verify packets were logged
        self.assertGreater(len(packets_received), 0)

    def test_04_tree_main_window_headless(self) -> None:
        """Verify MainWindow instantiates all 5 tier nodes, handles clicks, and closes cleanly."""
        window = MainWindow()
        window.show()
        self.app.processEvents()

        # Check all 5 nodes present
        self.assertEqual(len(window.node_widgets), 5)
        self.assertIn("agent_leader", window.node_widgets)
        self.assertIn("agent_dev_ui", window.node_widgets)
        self.assertIn("agent_dev_core", window.node_widgets)
        self.assertIn("agent_reviewer", window.node_widgets)
        self.assertIn("agent_tester", window.node_widgets)

        # Trigger run
        window.btn_dispatch.click()
        self.app.processEvents()
        self.assertFalse(window.btn_dispatch.isEnabled())
        self.assertTrue(window.btn_stop.isEnabled())

        # Test tab switching to Detail View on node click
        dev_node = window.node_widgets["agent_dev_ui"]
        dev_node.clicked.emit("agent_dev_ui")
        self.app.processEvents()
        self.assertEqual(window.tabs.currentIndex(), 1)
        self.assertEqual(window.current_detail_agent_id, "agent_dev_ui")

        # Test updating config from Tab 3 with live dynamic model
        window.tabs.setCurrentIndex(2)
        dev_combos = window.config_combos["agent_dev_ui"]
        target_model = window.available_models[1] if len(window.available_models) > 1 else window.available_models[0]
        dev_combos["model"].setCurrentText(target_model)
        dev_combos["thinking"].setCurrentText("High (16k)")
        self.app.processEvents()

        self.assertEqual(dev_node.config.model, target_model)
        self.assertEqual(dev_node.config.thinking_level, "high")

        # Stop and close
        window.btn_stop.click()
        self.app.processEvents()
        self.assertTrue(window.btn_dispatch.isEnabled())

        window.close()
        self.app.processEvents()

    def test_05_persona_and_live_models_integration(self) -> None:
        """Verify persona markdown loading, editing, and live model listing in Tab 3."""
        window = MainWindow()
        window.show()
        self.app.processEvents()

        # Check persona column exists in config matrix
        self.assertEqual(len(window.config_personas), 5)
        self.assertIn("agent_leader", window.config_personas)
        leader_label = window.config_personas["agent_leader"]
        self.assertIn(".md", leader_label.text())

        # Verify editing persona updates config content
        leader_cfg = next(c for c in window.configs if c.agent_id == "agent_leader")
        original_content = leader_cfg.persona_content
        self.assertTrue(len(original_content) > 0)

        # Test simulated persona edit
        custom_persona = "# Senior Lead Architect\n15+ years experience in distributed Linux systems."
        leader_cfg.save_persona(custom_persona)
        self.assertEqual(leader_cfg.persona_content, custom_persona)

        # Restore original content
        leader_cfg.save_persona(original_content)

        window.close()
        self.app.processEvents()

    def test_06_agent_customization_discovery_and_modes(self) -> None:
        """Verify .agent/ discovery, persona skill/rule assignments, and execution mode toggling."""
        # Test Discovery
        rules = CustomizationDiscovery.discover_rules()
        skills = CustomizationDiscovery.discover_skills()

        self.assertIn("01-architecture-boundaries.md", rules["workspace"])
        self.assertIn("02-investigate-before-fix.md", rules["workspace"])
        self.assertIn("03-peer-review-gating.md", rules["workspace"])

        self.assertIn("concurrency-safe-engine", skills["workspace"])
        self.assertIn("headless-qa-automation", skills["workspace"])
        self.assertIn("pyqt-ui-builder", skills["workspace"])

        # Test MainWindow Mode Toggling and Skills Display
        window = MainWindow()
        window.show()
        self.app.processEvents()

        self.assertEqual(window.orchestrator.execution_mode, "simulation")
        self.assertIn("Simulation", window.btn_mode_toggle.text())

        # Toggle to Live CLI
        window.btn_mode_toggle.click()
        self.app.processEvents()
        self.assertEqual(window.orchestrator.execution_mode, "live_cli")
        self.assertIn("Live CLI", window.btn_mode_toggle.text())

        # Toggle back to Simulation
        window.btn_mode_toggle.click()
        self.app.processEvents()
        self.assertEqual(window.orchestrator.execution_mode, "simulation")

        # Verify Tab 2 detail skills/rules binding
        window._select_detail_agent("agent_dev_ui")
        self.assertIn("pyqt-ui-builder", window.lbl_detail_skills.text())
        self.assertIn("01-architecture-boundaries.md", window.lbl_detail_rules.text())

        # Verify Tester skills binding
        window._select_detail_agent("agent_tester")
        self.assertIn("playwright-automation", window.lbl_detail_skills.text())
        self.assertIn("chrome-devtools", window.lbl_detail_skills.text())

        window.close()
        self.app.processEvents()

    def test_07_multi_department_switching(self) -> None:
        """Verify dynamic switching between Software Engineering and Video Production departments."""
        window = MainWindow()
        window.show()
        self.app.processEvents()

        # 1. Verify 2 departments registered in ComboBox
        self.assertEqual(window.combo_department.count(), 2)
        depts = window.orchestrator.get_departments()
        self.assertEqual(len(depts), 2)
        self.assertEqual(depts[0].dept_id, "dept_dev")
        self.assertEqual(depts[1].dept_id, "dept_video")

        # 2. Check initial Dev department nodes
        self.assertEqual(window.orchestrator.get_active_department().dept_id, "dept_dev")
        self.assertIn("agent_leader", window.node_widgets)
        self.assertIn("agent_dev_ui", window.node_widgets)
        self.assertEqual(window.pipeline_slots[0].config.name, "Leader / Architect")
        self.assertIn("Alexander Vance", window.pipeline_slots[0].config.load_persona())

        # 3. Switch to Video & Media Production Squad
        window.combo_department.setCurrentIndex(1)
        self.app.processEvents()

        # Verify active department changed
        self.assertEqual(window.orchestrator.get_active_department().dept_id, "dept_video")
        self.assertIn("Remotion", window.lbl_dept_desc.text())
        self.assertIn("Remotion", window.edit_prompt.text())

        # Verify 5 nodes updated to Video roles
        self.assertEqual(len(window.node_widgets), 5)
        self.assertIn("agent_video_director", window.node_widgets)
        self.assertIn("agent_video_motion", window.node_widgets)
        self.assertIn("agent_video_audio", window.node_widgets)
        self.assertIn("agent_video_reviewer", window.node_widgets)
        self.assertIn("agent_video_render", window.node_widgets)

        director_node = window.node_widgets["agent_video_director"]
        self.assertEqual(director_node.config.name, "Creative Director")
        self.assertIn("Liam Parker", director_node.config.load_persona())
        self.assertIn("06_creative_director.md", director_node.config.persona_file)

        # 4. Verify Tab 2 Inspector switched to Video Director
        self.assertEqual(window.current_detail_agent_id, "agent_video_director")
        self.assertEqual(window.lbl_detail_title.text(), "Creative Director")
        self.assertIn("remotion-best-practices", window.lbl_detail_skills.text())

        # Click motion graphics dev in inspector
        window._select_inspector_slot(1)
        self.app.processEvents()
        self.assertEqual(window.current_detail_agent_id, "agent_video_motion")
        self.assertEqual(window.lbl_detail_title.text(), "Motion Graphics Dev")
        self.assertIn("remotion-create", window.lbl_detail_skills.text())

        # 5. Verify Tab 3 Configuration matrix updated with Video Personas
        self.assertIn("agent_video_director", window.config_personas)
        self.assertIn("06_creative_director.md", window.config_personas["agent_video_director"].text())
        self.assertIn("agent_video_render", window.config_personas)
        self.assertIn("10_render_qa_engineer.md", window.config_personas["agent_video_render"].text())

        # 6. Switch back to Dev department cleanly
        window.combo_department.setCurrentIndex(0)
        self.app.processEvents()
        self.assertEqual(window.orchestrator.get_active_department().dept_id, "dept_dev")
        self.assertIn("agent_leader", window.node_widgets)
        self.assertEqual(window.pipeline_slots[0].config.name, "Leader / Architect")

        window.close()
        self.app.processEvents()

    def test_08_tester_playwright_and_chrome_mcp(self) -> None:
        """Verify Tester is equipped with Playwright and Chrome DevTools MCP tools."""
        import json
        orch = AgentOrchestrator()
        dev_configs = orch.get_department_configs("dept_dev")
        tester_cfg = next(c for c in dev_configs if c.agent_id == "agent_tester")

        # 1. Verify skills in SubAgentConfig
        self.assertIn("headless-qa-automation", tester_cfg.skills)
        self.assertIn("playwright-automation", tester_cfg.skills)
        self.assertIn("chrome-devtools", tester_cfg.skills)

        # 2. Verify .agent/mcp.json configuration exists and has servers
        mcp_path = os.path.join(CustomizationDiscovery.get_workspace_agent_dir(), "mcp.json")
        self.assertTrue(os.path.exists(mcp_path))
        with open(mcp_path, "r", encoding="utf-8") as f:
            mcp_data = json.load(f)
        self.assertIn("chrome-devtools", mcp_data.get("mcpServers", {}))
        self.assertIn("playwright", mcp_data.get("mcpServers", {}))

        # 3. Verify tester persona mentions Playwright and Chrome DevTools
        persona_content = tester_cfg.load_persona()
        self.assertIn("Playwright", persona_content)
        self.assertIn("Chrome DevTools", persona_content)
        self.assertIn("chrome-devtools", persona_content)

        # 4. Verify worker execution emits Playwright & MCP telemetry
        logger = HistoryLogger(base_dir="/tmp/test_agent_history")
        worker = SubAgentWorker(tester_cfg, "Validate app with Playwright and Chrome DevTools", logger)
        streams = []
        worker.stream_signal.connect(lambda a, s, c: streams.append((s, c)))

        worker.start()
        while worker.isRunning():
            self.app.processEvents()
        self.assertTrue(worker.wait(3000))

        stream_texts = " ".join([c for s, c in streams])
        self.assertIn("playwright-automation", stream_texts)
        self.assertIn("chrome-devtools", stream_texts)
        self.assertIn("mcp__chrome_devtools", stream_texts)
    def test_09_qa_report_generation_and_viewer(self) -> None:
        """Verify QAReportGenerator creates reports and MainWindow displays them."""
        from src.core.report_generator import QAReportGenerator
        from src.ui.main_window import QAReportDialog

        # 1. Test Dev Report Generation
        dev_rep = QAReportGenerator.generate_dev_report(
            task_prompt="Build Linux desktop utility",
            model="Gemini 3.8 Flash",
            tester_name="David Kim",
            leader_name="Alexander Vance"
        )
        self.assertIn("QA Verification & Stability Certification Report", dev_rep["markdown"])
        self.assertIn("David Kim", dev_rep["markdown"])
        self.assertIn("Alexander Vance", dev_rep["markdown"])
        self.assertTrue(os.path.exists(dev_rep["file_path"]))
        self.assertTrue(os.path.exists(os.path.join(QAReportGenerator.get_reports_dir(), "qa_report_latest.md")))

        # 2. Test Video Report Generation
        vid_rep = QAReportGenerator.generate_video_report(
            task_prompt="Create 60s product showcase video",
            model="Gemini 3.8 Flash",
            tester_name="Ethan Cole",
            leader_name="Liam Parker"
        )
        self.assertIn("Video Production QA & Broadcast Certification Report", vid_rep["markdown"])
        self.assertIn("Ethan Cole", vid_rep["markdown"])
        self.assertIn("Liam Parker", vid_rep["markdown"])
        self.assertTrue(os.path.exists(vid_rep["file_path"]))

        # 3. Test Orchestrator Signal Wiring
        orch = AgentOrchestrator()
        dev_configs = orch.get_department_configs("dept_dev")
        tester_cfg = next(c for c in dev_configs if c.agent_id == "agent_tester")

        reports_received = []
        orch.qa_report_ready.connect(lambda d, p, m: reports_received.append((d, p, m)))

        logger = HistoryLogger(base_dir="/tmp/test_agent_history")
        worker = SubAgentWorker(tester_cfg, "Verify desktop app", logger)
        worker.message_bus_signal.connect(orch._on_message_bus_packet)

        worker.start()
        while worker.isRunning():
            self.app.processEvents()
        self.assertTrue(worker.wait(3000))

        self.assertGreaterEqual(len(reports_received), 1)
        dept_id, path, md = reports_received[0]
        self.assertEqual(dept_id, "dept_dev")
        self.assertTrue(os.path.exists(path))
        self.assertIn("David Kim", md)

        # 4. Test UI MainWindow and QAReportDialog
        window = MainWindow(orch)
        self.assertTrue(window.btn_view_report.isEnabled())
        self.assertIn("QA Report", window.btn_view_report.text())

        dialog = QAReportDialog(dev_rep["markdown"], dev_rep["html"], dev_rep["file_path"], window)
        self.assertIn("David Kim", dialog.viewer.toPlainText())
        # Toggle view to raw markdown
        dialog._toggle_view_mode()
        self.assertTrue(dialog.is_raw_view)
        self.assertIn("# 🛡️ QA Verification", dialog.viewer.toPlainText())
        dialog.close()

    def test_10_telegram_notifier_and_remote_bridge(self) -> None:
        """Verify TelegramConfig, TelegramNotifier payload formatting, and RemoteBridge dispatching."""
        from src.core.telegram_notifier import TelegramConfig, TelegramNotifier, TelegramRemoteBridge

        # 1. Test TelegramConfig persistence
        config = TelegramConfig(bot_token="test_token_123", chat_id="987654321", enabled=True)
        config.save()
        self.assertTrue(os.path.exists(config.get_config_path()))

        loaded_config = TelegramConfig()
        self.assertEqual(loaded_config.bot_token, "test_token_123")
        self.assertEqual(loaded_config.chat_id, "987654321")
        self.assertTrue(loaded_config.enabled)

        # 2. Test TelegramNotifier validation & payload generation
        notifier = TelegramNotifier(loaded_config)
        # Empty token test
        empty_notifier = TelegramNotifier(TelegramConfig(bot_token="", chat_id="", enabled=True))
        ok, msg = empty_notifier.test_connection()
        self.assertFalse(ok)
        self.assertIn("empty", msg.lower())

        # Disabled notifier test
        disabled_notifier = TelegramNotifier(TelegramConfig(bot_token="tok", chat_id="123", enabled=False))
        ok, msg = disabled_notifier.send_message("Test message")
        self.assertFalse(ok)
        self.assertIn("disabled", msg.lower())

        # Test QA Report payload formatting
        report_data = {
            "department_name": "Software Engineering Squad",
            "task_prompt": "Implement Telegram notifications",
            "tester_name": "David Kim",
            "leader_name": "Alexander Vance",
            "score": 99.8,
            "file_path": "/tmp/non_existent_report.md"
        }
        # Capture payload by mocking _api_request
        intercepted = {}
        def mock_api(endpoint, payload=None, timeout=10):
            intercepted["endpoint"] = endpoint
            intercepted["payload"] = payload
            return True, {"ok": True, "result": {"message_id": 101}}

        notifier._api_request = mock_api
        ok, res_msg = notifier.send_qa_report(report_data)
        self.assertTrue(ok)
        self.assertEqual(intercepted["endpoint"], "sendMessage")
        payload = intercepted["payload"]
        self.assertEqual(payload["chat_id"], "987654321")
        self.assertIn("David Kim", payload["text"])
        self.assertIn("QA CERTIFICATE", payload["text"])
        # Check inline keyboard
        buttons = payload.get("reply_markup", {}).get("inline_keyboard", [])
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0][0]["callback_data"], "action_accept")
        self.assertEqual(buttons[0][1]["callback_data"], "action_reject")
        self.assertEqual(buttons[1][0]["callback_data"], "action_send_report")

        # 3. Test Orchestrator Remote Command Dispatching
        orch = AgentOrchestrator()
        remote_events = []
        orch.remote_command_dispatched.connect(lambda a, p, u: remote_events.append((a, p, u)))

        # Simulate incoming mobile prompt command
        orch._on_remote_command("PROMPT", "Build responsive mobile widget", "Thien Mobile")
        self.assertEqual(len(remote_events), 1)
        self.assertEqual(remote_events[0], ("PROMPT", "Build responsive mobile widget", "Thien Mobile"))
        self.assertEqual(orch._current_task, "Build responsive mobile widget")

        # Simulate mobile accept command
        pipeline_results = []
        orch.pipeline_finished.connect(lambda s, m: pipeline_results.append((s, m)))
        orch._on_remote_command("ACCEPT", "", "Thien Mobile")
        self.assertTrue(any(s is True and "Thien Mobile" in m for s, m in pipeline_results))

        # 4. Test UI Tab 3 Telegram widgets
        window = MainWindow(orch)
        self.assertTrue(hasattr(window, "chk_tele_enabled"))
        self.assertTrue(hasattr(window, "edit_tele_token"))
        self.assertTrue(hasattr(window, "edit_tele_chat_id"))
        self.assertTrue(hasattr(window, "btn_tele_test"))
        self.assertTrue(hasattr(window, "btn_tele_save"))
        self.assertTrue(hasattr(window, "lbl_tele_status"))

        # Test UI save action
        window.edit_tele_token.setText("new_tok_456")
        window.edit_tele_chat_id.setText("555123")
        window.chk_tele_enabled.setChecked(True)
        window._save_telegram_settings()

        self.assertEqual(orch.telegram_config.bot_token, "new_tok_456")
        self.assertEqual(orch.telegram_config.chat_id, "555123")
        self.assertTrue(orch.telegram_config.enabled)

        # Cleanup config to disabled state for future clean test runs
        config.save(bot_token="", chat_id="", enabled=False)

        window.close()
        self.app.processEvents()

    def test_11_usage_tracker_and_system_metrics(self) -> None:
        """Verify UsageTracker telemetry recording, /proc resource monitoring, and UI Tab 4."""
        from src.core.usage_tracker import SystemResourceMonitor, UsageTracker

        # 1. Test SystemResourceMonitor POSIX /proc reading
        cpu = SystemResourceMonitor.get_cpu_percent()
        self.assertIsInstance(cpu, float)
        self.assertGreaterEqual(cpu, 0.0)

        mem = SystemResourceMonitor.get_memory_info()
        self.assertIn("total_mb", mem)
        self.assertIn("used_mb", mem)
        self.assertIn("percent", mem)
        self.assertGreater(mem["total_mb"], 0)
        self.assertGreaterEqual(mem["percent"], 0.0)

        # 2. Test UsageTracker token recording & JSON persistence
        temp_stats_file = "/tmp/test_usage_stats.json"
        if os.path.exists(temp_stats_file):
            os.remove(temp_stats_file)

        tracker = UsageTracker(persistence_file=temp_stats_file)
        usage_emissions = []
        tracker.usage_updated.connect(lambda snap: usage_emissions.append(snap))

        tracker.record_usage(
            agent_id="agent_leader",
            name="Alexander Vance",
            avatar="👔",
            model="Gemini 3.8 Flash",
            input_tokens=150,
            output_tokens=220,
            thinking_tokens=50,
            duration_sec=1.5
        )

        self.assertEqual(tracker.total_tokens, 420)
        self.assertEqual(tracker.input_tokens, 150)
        self.assertEqual(tracker.output_tokens, 220)
        self.assertEqual(tracker.thinking_tokens, 50)
        self.assertEqual(tracker.cli_invocations, 1)
        self.assertEqual(len(usage_emissions), 1)
        self.assertTrue(os.path.exists(temp_stats_file))

        # Test reload from file
        reloaded = UsageTracker(persistence_file=temp_stats_file)
        self.assertEqual(reloaded.total_tokens, 420)
        self.assertIn("agent_leader", reloaded.agent_stats)
        self.assertEqual(reloaded.agent_stats["agent_leader"].total_tokens, 420)

        # Test reset
        reloaded.reset_stats()
        self.assertEqual(reloaded.total_tokens, 0)
        self.assertEqual(len(reloaded.agent_stats), 0)

        # 3. Test MainWindow Tab 4 Setup & Signal Binding with isolated tracker
        orch = AgentOrchestrator(usage_tracker=reloaded)
        window = MainWindow(orch)

        # Tab check
        self.assertEqual(window.tabs.count(), 4)
        self.assertEqual(window.tabs.tabText(3), "📊 Usage")

        # Widget presence
        self.assertTrue(hasattr(window, "bar_cpu"))
        self.assertTrue(hasattr(window, "bar_ram"))
        self.assertTrue(hasattr(window, "lbl_total_tokens"))
        self.assertTrue(hasattr(window, "lbl_input_tokens"))
        self.assertTrue(hasattr(window, "lbl_output_tokens"))
        self.assertTrue(hasattr(window, "lbl_thinking_tokens"))
        self.assertTrue(hasattr(window, "lbl_total_calls"))
        self.assertTrue(hasattr(window, "tbl_usage"))
        self.assertEqual(window.tbl_usage.columnCount(), 9)

        # Simulate usage emission to verify UI updates
        orch.usage_tracker.record_usage(
            agent_id="agent_dev_ui",
            name="Sarah Chen",
            avatar="💻",
            model="gemini-3.8-flash-high",
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=200,
            duration_sec=2.4
        )
        self.app.processEvents()

        self.assertIn("1,700", window.lbl_total_tokens.text())
        self.assertIn("1,000", window.lbl_input_tokens.text())
        self.assertIn("500", window.lbl_output_tokens.text())
        self.assertIn("200", window.lbl_thinking_tokens.text())
        self.assertGreaterEqual(window.tbl_usage.rowCount(), 1)

        window.close()
        self.app.processEvents()

        if os.path.exists(temp_stats_file):
            os.remove(temp_stats_file)

    def test_12_multi_cli_concurrency_and_dual_usage(self) -> None:
        """Verify pluggable CLI registry, Ollama streaming parser, dual-CLI tracking, and parallel workers."""
        from src.core.cli_engine import (
            CliRegistry,
            AgyCliBridge,
            OllamaCliBridge,
            CustomCliBridge,
        )
        from src.core.usage_tracker import UsageTracker

        # 1. Test CLI Bridge Registry and Command Generation
        bridge_agy = CliRegistry.get_bridge("agy")
        bridge_ollama = CliRegistry.get_bridge("ollama")
        bridge_custom = CliRegistry.get_bridge("custom")

        self.assertIsInstance(bridge_agy, AgyCliBridge)
        self.assertIsInstance(bridge_ollama, OllamaCliBridge)
        self.assertIsInstance(bridge_custom, CustomCliBridge)

        cmd_agy = bridge_agy.format_command(
            target_agent="agent_dev_ui",
            prompt="Build feature",
            model="gemini-3.8-flash-medium",
            thinking_level="medium"
        )
        self.assertIn("agy", cmd_agy[0])
        self.assertIn("--output-format", cmd_agy)
        self.assertIn("stream-json", cmd_agy)

        cmd_ollama = bridge_ollama.format_command(
            target_agent="agent_dev_core",
            prompt="Refactor backend",
            model="llama3.2:1b"
        )
        self.assertIn("ollama", cmd_ollama[0])
        self.assertEqual(cmd_ollama[1], "run")
        self.assertEqual(cmd_ollama[2], "llama3.2:1b")
        self.assertIn("--verbose", cmd_ollama)

        # 2. Test Ollama stream line parser
        _, parsed_in = bridge_ollama.parse_stream_line("prompt eval count: 42 token(s)")
        self.assertIsNotNone(parsed_in)
        self.assertEqual(parsed_in.get("input_tokens"), 42)

        _, parsed_out = bridge_ollama.parse_stream_line("eval count: 18 token(s)")
        self.assertIsNotNone(parsed_out)
        self.assertEqual(parsed_out.get("output_tokens"), 18)

        parsed_text, _ = bridge_ollama.parse_stream_line("Hello from Ollama Llama 3.2!")
        self.assertIsNotNone(parsed_text)
        self.assertIn("Hello from Ollama", parsed_text)

        # 3. Test Dual-CLI Usage Telemetry Isolation
        temp_dual_stats = "/tmp/test_dual_usage.json"
        if os.path.exists(temp_dual_stats):
            os.remove(temp_dual_stats)

        tracker = UsageTracker(persistence_file=temp_dual_stats)

        # Record CLI 1: agy
        tracker.record_usage(
            agent_id="agent_dev_ui",
            name="Sarah Chen",
            avatar="💻",
            model="gemini-3.8-flash-medium",
            input_tokens=1200,
            output_tokens=600,
            thinking_tokens=200,
            duration_sec=3.1,
            cli_engine="agy"
        )

        # Record CLI 2: ollama
        tracker.record_usage(
            agent_id="agent_dev_core",
            name="Marcus Brody",
            avatar="⚙️",
            model="llama3.2:1b",
            input_tokens=850,
            output_tokens=350,
            thinking_tokens=0,
            duration_sec=2.2,
            cli_engine="ollama"
        )

        # Global totals
        self.assertEqual(tracker.total_tokens, 3200)
        self.assertEqual(tracker.input_tokens, 2050)
        self.assertEqual(tracker.output_tokens, 950)
        self.assertEqual(tracker.thinking_tokens, 200)
        self.assertEqual(tracker.cli_invocations, 2)

        # Per-CLI breakdown
        self.assertIn("agy", tracker.cli_stats)
        self.assertIn("ollama", tracker.cli_stats)
        self.assertEqual(tracker.cli_stats["agy"]["total_tokens"], 2000)
        self.assertEqual(tracker.cli_stats["agy"]["calls_count"], 1)
        self.assertEqual(tracker.cli_stats["ollama"]["total_tokens"], 1200)
        self.assertEqual(tracker.cli_stats["ollama"]["calls_count"], 1)

        # Reload persistence check
        reloaded = UsageTracker(persistence_file=temp_dual_stats)
        self.assertEqual(reloaded.cli_stats["agy"]["total_tokens"], 2000)
        self.assertEqual(reloaded.cli_stats["ollama"]["total_tokens"], 1200)

        # 4. Test Multi-CLI Concurrent SubAgent Workers
        cfg_agy = SubAgentConfig(
            agent_id="agent_dev_ui",
            name="Sarah Chen",
            role=AgentRole.DEV_UI,
            avatar="💻",
            model="gemini-3.8-flash-medium",
            cli_engine="agy"
        )
        cfg_ollama = SubAgentConfig(
            agent_id="agent_dev_core",
            name="Marcus Brody",
            role=AgentRole.DEV_CORE,
            avatar="⚙️",
            model="llama3.2:1b",
            cli_engine="ollama"
        )

        test_logger = HistoryLogger(base_dir="/tmp/test_dual_history")
        worker_agy = SubAgentWorker(cfg_agy, "Design responsive layout", test_logger)
        worker_ollama = SubAgentWorker(cfg_ollama, "Build concurrency locks", test_logger)

        # Verify threads run in parallel without conflicts
        worker_agy.start()
        worker_ollama.start()
        while worker_agy.isRunning() or worker_ollama.isRunning():
            self.app.processEvents()

        self.assertTrue(worker_agy.wait(3000))
        self.assertTrue(worker_ollama.wait(3000))
        self.assertTrue(worker_agy.isFinished())
        self.assertTrue(worker_ollama.isFinished())

        # 5. Test MainWindow UI Dual-CLI Telemetry & Matrix Bindings
        orch = AgentOrchestrator(usage_tracker=reloaded)
        window = MainWindow(orch)

        # Verify Dual-CLI Comparison Cards
        self.assertTrue(hasattr(window, "lbl_agy_total"))
        self.assertTrue(hasattr(window, "lbl_ollama_total"))
        self.assertIn("2,000", window.lbl_agy_total.text())
        self.assertIn("1,200", window.lbl_ollama_total.text())

        # Verify 9-column usage table with Engine column
        self.assertEqual(window.tbl_usage.columnCount(), 9)
        self.assertEqual(window.tbl_usage.horizontalHeaderItem(1).text(), "Engine")

        # Verify Engine badge text in table
        found_agy = False
        found_ollama = False
        for row in range(window.tbl_usage.rowCount()):
            item = window.tbl_usage.item(row, 1)
            if item:
                if "agy" in item.text():
                    found_agy = True
                if "ollama" in item.text():
                    found_ollama = True
        self.assertTrue(found_agy)
        self.assertTrue(found_ollama)

        # Verify Matrix row engine switching
        row_widget = window.matrix_row_widgets[1]  # Slot 2 (agent_dev_ui)
        combo_engine = row_widget["combo_engine"]
        combo_model = row_widget["combo_model"]

        # Switch slot 2 engine to ollama
        ollama_idx = combo_engine.findData("ollama")
        self.assertGreaterEqual(ollama_idx, 0)
        combo_engine.setCurrentIndex(ollama_idx)
        self.app.processEvents()

        # Verify combo_model reloaded with ollama models
        ollama_models = bridge_ollama.get_available_models()
        for m in ollama_models:
            self.assertGreaterEqual(combo_model.findText(m), 0)

        window.close()
        self.app.processEvents()

        if os.path.exists(temp_dual_stats):
            os.remove(temp_dual_stats)

    def test_13_checkpoint_and_failover_mechanism(self) -> None:
        """Verify CheckpointManager persistence, rate-limit detection, automated failover, and resume flow."""
        from src.core.checkpoint_manager import CheckpointManager, PipelineCheckpoint
        from src.core.cli_engine import CliRegistry, AgyCliBridge, OllamaCliBridge

        # 1. Test CheckpointManager Persistence
        temp_cp_file = "/tmp/test_pipeline_checkpoint.json"
        if os.path.exists(temp_cp_file):
            os.remove(temp_cp_file)

        cp_mgr = CheckpointManager(checkpoint_file=temp_cp_file)
        self.assertFalse(cp_mgr.has_valid_checkpoint())
        self.assertIsNone(cp_mgr.load_checkpoint())

        sample_cp = PipelineCheckpoint(
            stage_index=2,
            stage_name="Stage 2 (Development)",
            completed_stages=["agent_leader"],
            agent_states={
                "agent_dev_ui": {"engine": "agy", "model": "gemini-3.8-flash-medium", "status": "COMPLETED"},
                "agent_dev_core": {"engine": "ollama", "model": "llama3.2:1b", "status": "PLANNING"},
            },
            task_prompt="Build multi-cli utility",
            department_id="dept_dev"
        )
        saved_ok = cp_mgr.save_checkpoint(sample_cp)
        self.assertTrue(saved_ok)
        self.assertTrue(cp_mgr.has_valid_checkpoint())

        loaded_cp = cp_mgr.load_checkpoint()
        self.assertIsNotNone(loaded_cp)
        self.assertEqual(loaded_cp.stage_index, 2)
        self.assertEqual(loaded_cp.stage_name, "Stage 2 (Development)")
        self.assertEqual(loaded_cp.completed_stages, ["agent_leader"])
        self.assertIn("agent_dev_ui", loaded_cp.agent_states)
        self.assertEqual(loaded_cp.agent_states["agent_dev_ui"]["engine"], "agy")
        self.assertEqual(loaded_cp.agent_states["agent_dev_core"]["engine"], "ollama")

        # 2. Test Rate Limit Detection & Failover Mapping
        bridge_agy = CliRegistry.get_bridge("agy")
        self.assertTrue(bridge_agy.is_rate_limited("Error: 429 Too Many Requests: Rate limit exceeded", 1))
        self.assertTrue(bridge_agy.is_rate_limited("google.api_core.exceptions.ResourceExhausted: 429 Quota reached", 1))
        self.assertFalse(bridge_agy.is_rate_limited("Building component successfully", 0))

        # Test failover registry
        self.assertEqual(CliRegistry.get_failover_engine("agy"), "ollama")
        self.assertEqual(CliRegistry.get_failover_engine("ollama"), "agy")

        # 3. Test Department Default Dual-CLI Configuration
        orch = AgentOrchestrator()
        orch.checkpoint_manager = cp_mgr

        dev_configs = orch.get_department_configs("dept_dev")
        dev1 = next(c for c in dev_configs if c.agent_id == "agent_dev_ui")
        dev2 = next(c for c in dev_configs if c.agent_id == "agent_dev_core")

        # Dev 1 on agy, Dev 2 on ollama with llama3.2:1b
        self.assertEqual(dev1.cli_engine, "agy")
        self.assertEqual(dev2.cli_engine, "ollama")
        self.assertEqual(dev2.model, "llama3.2:1b")

        # Media department check
        video_configs = orch.get_department_configs("dept_video")
        v_dev1 = next(c for c in video_configs if c.agent_id == "agent_video_motion")
        v_dev2 = next(c for c in video_configs if c.agent_id == "agent_video_audio")
        self.assertEqual(v_dev1.cli_engine, "agy")
        self.assertEqual(v_dev2.cli_engine, "ollama")
        self.assertEqual(v_dev2.model, "llama3.2:1b")

        # 4. Test Orchestrator Resume from Checkpoint
        self.assertTrue(orch.has_checkpoint())
        self.assertEqual(orch.get_checkpoint_stage_name(), "Stage 2 (Development)")

        resumed = orch.resume_from_checkpoint()
        self.assertTrue(resumed)
        self.assertEqual(orch._current_task, "Build multi-cli utility")
        self.assertIn("agent_leader", orch.completed_stages)

        # Stage 2 workers should be started, but not Stage 1 (agent_leader)
        self.assertNotIn("agent_leader", orch.workers)
        self.assertIn("agent_dev_core", orch.workers)

        orch.stop_all()

        # 5. Test MainWindow UI Checkpoint & Failover bindings
        window = MainWindow(orch)

        # Verify Resume Button is enabled and displays stage name
        self.assertTrue(window.btn_resume.isEnabled())
        self.assertIn("Stage 2 (Development)", window.btn_resume.text())

        # Verify Failover Strategy Checkbox
        self.assertTrue(hasattr(window, "chk_auto_failover"))
        self.assertTrue(window.chk_auto_failover.isChecked())
        self.assertTrue(orch.auto_failover_enabled)

        # Toggle failover off and verify
        window.chk_auto_failover.setChecked(False)
        self.assertFalse(orch.auto_failover_enabled)

        # Toggle failover back on
        window.chk_auto_failover.setChecked(True)
        self.assertTrue(orch.auto_failover_enabled)

        # Simulate Failover Signal
        orch.failover_forwarded.emit("agent_dev_ui", "agy", "ollama", "429 Rate Limit")
        self.app.processEvents()
        self.assertIn("Failover", window.lbl_status.text())

        # Clear checkpoint and verify UI updates
        cp_mgr.clear_checkpoint()
        self.assertFalse(cp_mgr.has_valid_checkpoint())
        window._update_resume_button()
        self.assertFalse(window.btn_resume.isEnabled())
        self.assertEqual(window.btn_resume.text(), "▶️ Resume")

        window.close()
        self.app.processEvents()

        if os.path.exists(temp_cp_file):
            os.remove(temp_cp_file)


if __name__ == "__main__":
    unittest.main()


