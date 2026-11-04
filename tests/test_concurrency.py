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


if __name__ == "__main__":
    unittest.main()
