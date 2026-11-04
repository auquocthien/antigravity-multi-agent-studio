"""Multi-Agent 5-Tier Hierarchical Engine with Antigravity CLI & Message History Logging."""

import os
import sys
import json
import shutil
import subprocess
import datetime
import time
from enum import Enum
from typing import Dict, List, Any, Optional
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QWaitCondition


class AgentRole(Enum):
    # Software Engineering Squad Roles
    LEADER = "Lead Architect"
    DEV_UI = "Frontend Dev"
    DEV_CORE = "Backend Dev"
    REVIEWER = "Code Reviewer"
    TESTER = "QA Tester"
    # Video & Media Production Squad Roles
    DIRECTOR = "Creative Director"
    DEV_MOTION = "Motion Dev"
    DEV_AUDIO = "Audio & Captions"
    VIDEO_REVIEWER = "Video Auditor"
    RENDER_QA = "Render QA"


class DepartmentConfig:
    """Descriptor for an autonomous organizational department."""

    def __init__(
        self,
        dept_id: str,
        name: str,
        icon: str,
        default_prompt: str,
        description: str = ""
    ) -> None:
        self.dept_id = dept_id
        self.name = name
        self.icon = icon
        self.default_prompt = default_prompt
        self.description = description


class AgentState(Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    THINKING = "THINKING"
    CALLING_TOOL = "CALLING_TOOL"
    PEER_REVIEW = "PEER_REVIEW"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class StandardMessagePacket:
    """Standardized schema for all inter-agent communication packets."""

    def __init__(
        self,
        intent: str,
        from_agent: str,
        to_agent: str,
        model: str,
        effort: str,
        payload: str,
        scope_files: Optional[List[str]] = None,
        severity: str = "NORMAL"
    ) -> None:
        self.packet_id: str = f"pkt_{int(time.time() * 1000)}"
        self.timestamp: str = datetime.datetime.now().isoformat()
        self.intent: str = intent  # TASK_DISPATCH | PEER_REVIEW_REQUEST | BUG_REPORT | APPROVAL_NOTICE
        self.from_agent: str = from_agent
        self.to_agent: str = to_agent
        self.model: str = model
        self.effort: str = effort
        self.scope_files: List[str] = scope_files or []
        self.severity: str = severity
        self.payload: str = payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "timestamp": self.timestamp,
            "intent": self.intent,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "model": self.model,
            "effort": self.effort,
            "scope_files": self.scope_files,
            "severity": self.severity,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class HistoryLogger:
    """Persists structured conversation packets into session JSONL log files."""

    def __init__(self, base_dir: str = "/mnt/data/linux-desktop-utility/history") -> None:
        self.base_dir: str = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file: str = os.path.join(self.base_dir, f"session_{session_id}.jsonl")

    def record_packet(self, packet: StandardMessagePacket) -> None:
        """Append a packet to the session history file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(packet.to_json() + "\n")
        except OSError:
            pass


class CustomizationDiscovery:
    """Discovers workspace (.agent/) and global (~/.gemini/config/) skills and rules."""

    @classmethod
    def get_workspace_dir(cls) -> str:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @classmethod
    def get_workspace_agent_dir(cls) -> str:
        base = cls.get_workspace_dir()
        for candidate in [".agent", ".agents"]:
            p = os.path.join(base, candidate)
            if os.path.exists(p):
                return p
        return os.path.join(base, ".agent")

    @classmethod
    def get_global_config_dir(cls) -> str:
        return os.path.expanduser("~/.gemini/config")

    @classmethod
    def discover_rules(cls) -> Dict[str, List[str]]:
        rules = {"workspace": [], "global": []}
        ws_rules_dir = os.path.join(cls.get_workspace_agent_dir(), "rules")
        if os.path.exists(ws_rules_dir):
            try:
                rules["workspace"] = sorted([f for f in os.listdir(ws_rules_dir) if f.endswith(".md")])
            except OSError:
                pass
        gl_rules_dir = os.path.join(cls.get_global_config_dir(), "rules")
        if os.path.exists(gl_rules_dir):
            try:
                rules["global"] = sorted([f for f in os.listdir(gl_rules_dir) if f.endswith(".md")])
            except OSError:
                pass
        return rules

    @classmethod
    def discover_skills(cls) -> Dict[str, List[str]]:
        skills = {"workspace": [], "global": []}
        ws_skills_dir = os.path.join(cls.get_workspace_agent_dir(), "skills")
        if os.path.exists(ws_skills_dir):
            try:
                skills["workspace"] = sorted([
                    d for d in os.listdir(ws_skills_dir)
                    if os.path.isdir(os.path.join(ws_skills_dir, d))
                ])
            except OSError:
                pass
        gl_skills_dir = os.path.join(cls.get_global_config_dir(), "skills")
        if os.path.exists(gl_skills_dir):
            try:
                skills["global"] = sorted([d for d in os.listdir(gl_skills_dir)])
            except OSError:
                pass
        return skills


class SubAgentConfig:
    """Configuration descriptor for a specialized subagent in the hierarchical tree."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: AgentRole,
        avatar: str,
        model: str = "Gemini 3.8 Flash",
        thinking_level: str = "medium",
        system_prompt: str = "",
        persona_file: str = "",
        skills: Optional[List[str]] = None,
        rules: Optional[List[str]] = None
    ) -> None:
        self.agent_id: str = agent_id
        self.name: str = name
        self.role: AgentRole = role
        self.avatar: str = avatar
        self.model: str = model
        self.thinking_level: str = thinking_level  # "low", "medium", "high", "max"
        self.system_prompt: str = system_prompt
        self.persona_file: str = persona_file
        self.persona_content: str = ""
        self.skills: List[str] = list(skills) if skills else []
        self.rules: List[str] = list(rules) if rules else []
        self.load_persona()

    def load_persona(self) -> str:
        """Load markdown persona content from persona_file if it exists."""
        if self.persona_file and os.path.exists(self.persona_file):
            try:
                with open(self.persona_file, "r", encoding="utf-8") as f:
                    self.persona_content = f.read()
                    return self.persona_content
            except OSError:
                pass
        return self.persona_content

    def save_persona(self, new_content: str) -> bool:
        """Save updated persona content back to the persona_file."""
        self.persona_content = new_content
        if self.persona_file:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.persona_file)), exist_ok=True)
                with open(self.persona_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return True
            except OSError:
                return False
        return False


class AgyCliBridge:
    """Executes commands via the Antigravity CLI (agy) with model and effort routing."""

    CLI_PATHS = [
        "/home/thienau/.local/bin/agy",
        shutil.which("agy") or "agy",
    ]

    @classmethod
    def get_agy_binary(cls) -> Optional[str]:
        for p in cls.CLI_PATHS:
            if p and os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        return None

    @classmethod
    def get_available_models(cls) -> List[str]:
        """Fetch real available models from authenticated agy CLI or fallback gracefully."""
        agy_bin = cls.get_agy_binary()
        if agy_bin:
            try:
                proc = subprocess.run(
                    [agy_bin, "models"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if proc.returncode == 0 and proc.stdout:
                    models = []
                    for line in proc.stdout.splitlines():
                        line = line.strip()
                        if line and not line.startswith("⠋") and not line.startswith("Error") and not line.startswith("Please"):
                            clean_line = "".join(c for c in line if ord(c) < 128 or c in "()·-").strip()
                            parts = clean_line.split()
                            if parts:
                                model_id = parts[0]
                                if len(parts) > 1:
                                    display_name = " ".join(parts[1:])
                                    models.append(f"{display_name} ({model_id})")
                                else:
                                    models.append(model_id)
                    if models:
                        return models
            except Exception:
                pass

        return [
            "Gemini 4 Argon (gemini-4-argon-medium)",
            "Gemini 3.8 Flash (gemini-3.8-flash-high)",
            "Claude Opus 5.5 (claude-opus-5-5-high)",
            "Claude Sonnet 5.5 (claude-sonnet-5-5-high)",
            "GPT-OSS 120B (gpt-oss-120b-medium)",
            "Gemini 3.1 Pro (gemini-3.1-pro)",
        ]

    @classmethod
    def format_cli_command(
        cls,
        target_agent: str,
        prompt: str,
        model: str = "Gemini 3.8 Flash",
        thinking_level: str = "medium"
    ) -> List[str]:
        """Build agy execution command array with --model and --effort."""
        agy_bin = cls.get_agy_binary() or "agy"
        effort_map = {"low": "low", "medium": "medium", "high": "high", "max": "max"}
        effort = effort_map.get(thinking_level.lower(), "medium")

        # Map display model names to CLI model IDs
        model_id = "gemini-3.8-flash"
        if "(" in model and ")" in model:
            extracted = model.split("(")[-1].replace(")", "").strip()
            if extracted:
                model_id = extracted
        elif "4 Argon" in model:
            model_id = "gemini-4-argon-medium"
        elif "3.1 Pro" in model:
            model_id = "gemini-3.1-pro"
        elif "Opus" in model:
            model_id = "claude-opus-5-5-high"
        elif "Sonnet" in model:
            model_id = "claude-sonnet-5-5-high"
        elif "OSS" in model:
            model_id = "gpt-oss-120b-medium"

        return [
            agy_bin,
            "--agent", target_agent,
            "--model", model_id,
            "--effort", effort,
            "--output-format", "text",
            "-p", prompt
        ]


class SubAgentWorker(QThread):
    """Dedicated background thread running an autonomous agent workflow in the hierarchical tree."""

    stream_signal = pyqtSignal(str, str, str)  # (agent_id, stream_type, chunk)
    status_signal = pyqtSignal(str, str)        # (agent_id, state)
    progress_signal = pyqtSignal(str, int)      # (agent_id, percent)
    message_bus_signal = pyqtSignal(object)     # StandardMessagePacket
    finished_signal = pyqtSignal(str, bool, str)# (agent_id, success, summary)
    adjust_subordinate_signal = pyqtSignal(str, str, str) # (target_agent_id, new_model, new_effort)

    def __init__(
        self,
        config: SubAgentConfig,
        task_prompt: str,
        logger: HistoryLogger,
        execution_mode: str = "simulation",
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.config: SubAgentConfig = config
        self.task_prompt: str = task_prompt
        self.logger: HistoryLogger = logger
        self.execution_mode: str = execution_mode
        self._is_running: bool = True
        self._is_paused: bool = False
        self._mutex: QMutex = QMutex()
        self._pause_condition: QWaitCondition = QWaitCondition()
        self._active_subprocess: Optional[subprocess.Popen] = None

    def pause(self) -> None:
        self._mutex.lock()
        try:
            self._is_paused = True
        finally:
            self._mutex.unlock()
        self.status_signal.emit(self.config.agent_id, AgentState.PAUSED.value)
        self.stream_signal.emit(self.config.agent_id, "SYSTEM", "Agent execution paused.")

    def resume(self) -> None:
        self._mutex.lock()
        try:
            self._is_paused = False
            self._pause_condition.wakeAll()
        finally:
            self._mutex.unlock()
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.stream_signal.emit(self.config.agent_id, "SYSTEM", "Agent resumed execution.")

    def stop(self) -> None:
        self._mutex.lock()
        try:
            self._is_running = False
            self._is_paused = False
            self._pause_condition.wakeAll()
            if self._active_subprocess is not None and self._active_subprocess.poll() is None:
                try:
                    self._active_subprocess.terminate()
                except OSError:
                    pass
        finally:
            self._mutex.unlock()
        self.status_signal.emit(self.config.agent_id, AgentState.STOPPED.value)
        self.stream_signal.emit(self.config.agent_id, "SYSTEM", "Agent terminated by user.")

    def _check_pause_and_running(self) -> bool:
        self._mutex.lock()
        try:
            while self._is_paused and self._is_running:
                self._pause_condition.wait(self._mutex)
            return self._is_running
        finally:
            self._mutex.unlock()

    def run(self) -> None:
        agent_id = self.config.agent_id
        self.status_signal.emit(agent_id, AgentState.PLANNING.value)
        self.progress_signal.emit(agent_id, 0)
        mode_label = "⚡ LIVE CLI" if self.execution_mode == "live_cli" else "🧪 SIMULATION"
        self.stream_signal.emit(
            agent_id,
            "SYSTEM",
            f"Node Online [{mode_label}] | Model: {self.config.model} | Effort: {self.config.thinking_level.upper()}"
        )
        if self.config.persona_content:
            first_line = self.config.persona_content.splitlines()[0] if self.config.persona_content else ""
            self.stream_signal.emit(
                agent_id,
                "SYSTEM",
                f"Persona Active: {os.path.basename(self.config.persona_file)} ({first_line.replace('#', '').strip()})"
            )
        if self.config.skills:
            self.stream_signal.emit(
                agent_id,
                "SYSTEM",
                f"Active Skills: {', '.join(self.config.skills)}"
            )
        if self.config.rules:
            self.stream_signal.emit(
                agent_id,
                "SYSTEM",
                f"Enforced Rules: {', '.join(self.config.rules)}"
            )

        try:
            if self.config.role == AgentRole.LEADER:
                self._execute_leader_flow()
            elif self.config.role == AgentRole.DIRECTOR:
                self._execute_director_flow()
            elif self.config.role == AgentRole.DEV_UI:
                self._execute_dev_ui_flow()
            elif self.config.role == AgentRole.DEV_MOTION:
                self._execute_dev_motion_flow()
            elif self.config.role == AgentRole.DEV_CORE:
                self._execute_dev_core_flow()
            elif self.config.role == AgentRole.DEV_AUDIO:
                self._execute_dev_audio_flow()
            elif self.config.role == AgentRole.REVIEWER:
                self._execute_reviewer_flow()
            elif self.config.role == AgentRole.VIDEO_REVIEWER:
                self._execute_video_reviewer_flow()
            elif self.config.role == AgentRole.TESTER:
                self._execute_tester_flow()
            elif self.config.role == AgentRole.RENDER_QA:
                self._execute_render_qa_flow()

            if self._check_pause_and_running():
                self.status_signal.emit(agent_id, AgentState.COMPLETED.value)
                self.progress_signal.emit(agent_id, 100)
                self.finished_signal.emit(agent_id, True, f"{self.config.name} completed successfully.")
            else:
                self.status_signal.emit(agent_id, AgentState.STOPPED.value)
                self.finished_signal.emit(agent_id, False, f"{self.config.name} was stopped.")

        except Exception as exc:
            self.stream_signal.emit(agent_id, "SYSTEM", f"Unhandled error in agent: {exc}")
            self.status_signal.emit(agent_id, AgentState.ERROR.value)
            self.finished_signal.emit(agent_id, False, str(exc))

    def _stream_text(self, stream_type: str, text: str, delay_ms: int = 15) -> bool:
        words = text.split(" ")
        for i, word in enumerate(words):
            if not self._check_pause_and_running():
                return False
            chunk = word + (" " if i < len(words) - 1 else "")
            self.stream_signal.emit(self.config.agent_id, stream_type, chunk)
            self.msleep(delay_ms)
        self.stream_signal.emit(self.config.agent_id, stream_type, "\n")
        return True

    def _dispatch_structured_packet(
        self,
        intent: str,
        to_agent: str,
        payload: str,
        scope_files: Optional[List[str]] = None,
        severity: str = "NORMAL"
    ) -> None:
        """Emit structured packet to UI and persist in history log."""
        pkt = StandardMessagePacket(
            intent=intent,
            from_agent=self.config.agent_id,
            to_agent=to_agent,
            model=self.config.model,
            effort=self.config.thinking_level,
            payload=payload,
            scope_files=scope_files,
            severity=severity
        )
        self.logger.record_packet(pkt)
        self.message_bus_signal.emit(pkt)

        # Trigger Antigravity CLI call preview
        cmd = AgyCliBridge.format_cli_command(to_agent, payload, self.config.model, self.config.thinking_level)
        self.stream_signal.emit(self.config.agent_id, "CLI_CMD", f"\n$ {' '.join(cmd)}\n")

    # --- Role-Specific Execution Flows ---

    def _execute_leader_flow(self) -> None:
        """Leader Flow: Decomposes tasks, assigns scopes, and steers subagent parameters."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 20)

        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Partitioning tasks strictly adhering to '01-architecture-boundaries.md'")
        if "concurrency-safe-engine" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Leader activated 'concurrency-safe-engine' (workspace)")

        thought = (
            f"[THOUGHT] Architectural analysis on: '{self.task_prompt}'. "
            f"Using model {self.config.model} (effort: {self.config.thinking_level}). "
            "Partitioning strict boundaries: Dev 1 -> src/ui/*, Dev 2 -> src/core/*. "
            "Optimizing Dev efforts: Setting Dev 1 to Medium, Dev 2 to Medium."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 45)

        # Leader dynamically adjusts Dev 2 if complexity is high
        self.adjust_subordinate_signal.emit("agent_dev_core", "Gemini 3.8 Flash", "high")
        self._stream_text("THOUGHT", "[LEADER ACTION] Adjusted Dev 2 thinking level to HIGH for concurrency safety.")

        # Dispatch to Dev 1
        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        dev1_payload = "Build hierarchical tree PyQt6 node widgets and status indicators."
        self._dispatch_structured_packet(
            intent="TASK_DISPATCH",
            to_agent="agent_dev_ui",
            payload=dev1_payload,
            scope_files=["src/ui/tree_node.py", "src/ui/main_window.py"]
        )
        self.msleep(200)

        # Dispatch to Dev 2
        dev2_payload = "Implement StandardMessagePacket history logger and QThread signals."
        self._dispatch_structured_packet(
            intent="TASK_DISPATCH",
            to_agent="agent_dev_core",
            payload=dev2_payload,
            scope_files=["src/core/engine.py"]
        )
        self.progress_signal.emit(self.config.agent_id, 85)
        self.msleep(250)

        self._stream_text("OUTPUT", "Leader successfully orchestrated task delegation to Dev 1 and Dev 2.")

    def _execute_dev_ui_flow(self) -> None:
        """Dev 1 Flow: UI Builder."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 20)

        if "pyqt-ui-builder" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Elena Rostova activated 'pyqt-ui-builder' & 'ui-ux-pro-max'")
        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Confining changes exclusively to src/ui/ per '01-architecture-boundaries.md'")

        thought = (
            f"[THOUGHT] Dev 1 accepted UI task. Running with {self.config.model}. "
            "Constructing AgentTreeNodeWidget with model & effort selectors."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 50)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: write_file('src/ui/tree_node.py', size=3500)")
        self.msleep(300)
        self.progress_signal.emit(self.config.agent_id, 80)

        # Peer Review request to Dev 2
        self.status_signal.emit(self.config.agent_id, AgentState.PEER_REVIEW.value)
        review_msg = "Please cross-review tree_node.py signal bindings with engine QThread."
        self._dispatch_structured_packet(
            intent="PEER_REVIEW_REQUEST",
            to_agent="agent_dev_core",
            payload=review_msg,
            scope_files=["src/ui/tree_node.py"]
        )
        self.msleep(250)
        self._stream_text("OUTPUT", "UI implementation ready. Submitted for peer-review.")

    def _execute_dev_core_flow(self) -> None:
        """Dev 2 Flow: Core & Concurrency."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 25)

        if "concurrency-safe-engine" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Marcus Chen activated 'concurrency-safe-engine' for thread synchronization")
        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Confining core engine logic exclusively to src/core/ per '01-architecture-boundaries.md'")

        thought = (
            f"[THOUGHT] Dev 2 analyzing concurrency contracts under {self.config.model} (effort: {self.config.thinking_level}). "
            "Designing thread-safe AgyCliBridge and HistoryLogger."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 55)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: write_file('src/core/engine.py', size=4200)")
        self.msleep(300)
        self.progress_signal.emit(self.config.agent_id, 80)

        # Submit combined work to Reviewer
        self.status_signal.emit(self.config.agent_id, AgentState.PEER_REVIEW.value)
        handoff = "Handoff to Reviewer: Peer review between Dev 1 & Dev 2 complete. Requesting formal audit."
        self._dispatch_structured_packet(
            intent="PEER_REVIEW_REQUEST",
            to_agent="agent_reviewer",
            payload=handoff,
            scope_files=["src/core/engine.py", "src/ui/tree_node.py"]
        )
        self.msleep(250)
        self._stream_text("OUTPUT", "Core concurrency modules built. Handoff to Reviewer.")

    def _execute_reviewer_flow(self) -> None:
        """Reviewer Flow: Static audit and verification."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 25)

        if "03-peer-review-gating.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Evaluating cross-developer diff against '03-peer-review-gating.md'")
        if any("investigate" in r for r in self.config.rules):
            self._stream_text("THOUGHT", "[RULE ENFORCED] Verifying root cause analysis criteria per '02-investigate-before-fix.md'")

        thought = (
            f"[THOUGHT] Reviewer deep cognitive check using {self.config.model} ({self.config.thinking_level}). "
            "Checking: 1. Strict file scope adherence, 2. No cross-thread widget mutation, 3. Clean teardown."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 60)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: ast_static_verifier(files=['src/ui/tree_node.py', 'src/core/engine.py'])")
        self.msleep(350)
        self.progress_signal.emit(self.config.agent_id, 85)

        # Approval notice sent to Tester
        pass_msg = "Review PASS: Code conforms to clean architecture standards. Passing to Tester for runtime tests."
        self._dispatch_structured_packet(
            intent="APPROVAL_NOTICE",
            to_agent="agent_tester",
            payload=pass_msg
        )
        self.msleep(200)
        self._stream_text("OUTPUT", "Review completed successfully. Passed gate to Runtime Tester.")

    def _execute_tester_flow(self) -> None:
        """Tester Flow: Runtime tests, Playwright browser E2E, and Chrome DevTools MCP inspection."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 15)

        if "headless-qa-automation" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] David Kim activated 'headless-qa-automation'")
        if "playwright-automation" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] David Kim activated 'playwright-automation' (Chromium E2E Runner)")
        if "chrome-devtools" in self.config.skills:
            self._stream_text("TOOL", "[MCP SERVER CONNECTED] David Kim connected to 'chrome-devtools' via MCP protocol")

        thought = (
            f"[THOUGHT] QA Automation Engineer deploying comprehensive test matrix with {self.config.model}. "
            "1. QT_QPA_PLATFORM=offscreen headless unit tests. "
            "2. Playwright headless browser E2E layout validation. "
            "3. Chrome DevTools MCP deep inspection (console errors, DOM mutations, and network latency)."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 45)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: run_headless_tests('tests/test_concurrency.py')")
        self.msleep(250)
        self._stream_text("TOOL", "call_tool: mcp__chrome_devtools__navigate(url='http://localhost:8080', timeout=5000)")
        self.msleep(250)
        self._stream_text("TOOL", "call_tool: playwright_test_runner(specs=['tests/e2e/layout.spec.ts'], browser='chromium')")
        self.msleep(250)
        self.progress_signal.emit(self.config.agent_id, 85)

        # Publish final certificate to Leader
        final_test_msg = "QA Verification 100% SUCCESS: Unit tests, Playwright E2E suites, and Chrome DevTools MCP diagnostics passed."
        self._dispatch_structured_packet(
            intent="APPROVAL_NOTICE",
            to_agent="agent_leader",
            payload=final_test_msg,
            severity="NORMAL"
        )
        self.msleep(200)
        self._stream_text("OUTPUT", "QA sign-off granted: 0 console errors, unit & Playwright E2E tests verified via MCP.")

    # --- Video & Media Production Squad Flows ---

    def _execute_director_flow(self) -> None:
        """Director Flow: Storyboard pacing, timeline decomposition, and scene sequencing."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 20)

        if "remotion-best-practices" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Liam Parker activated 'remotion-best-practices' & 'design-system'")
        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Partitioning scenes strictly per '01-architecture-boundaries.md'")

        thought = (
            f"[THOUGHT] Storyboard architectural pacing on: '{self.task_prompt}'. "
            f"Using model {self.config.model} (effort: {self.config.thinking_level}). "
            "Timeline Partition: Scene 1 (0-15s Hook), Scene 2 (15-40s Feature Deep-Dive), Scene 3 (40-60s CTA). "
            "Canvas: 1920x1080 @ 60fps. Allocating Motion to Dev 1 and Audio/Captions to Dev 2."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 45)

        self.adjust_subordinate_signal.emit("agent_video_audio", "Gemini 3.8 Flash (High) (gemini-3.8-flash-high)", "high")
        self._stream_text("THOUGHT", "[DIRECTOR ACTION] Adjusted Audio Engineer thinking level to HIGH for exact word-level TTS timing.")

        # Dispatch to Motion Dev
        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        motion_payload = "Implement Remotion React scene components (IntroScene, FeatureShowcase, OutroCTA) with spring physics."
        self._dispatch_structured_packet(
            intent="TASK_DISPATCH",
            to_agent="agent_video_motion",
            payload=motion_payload,
            scope_files=["src/scenes/IntroScene.tsx", "src/Root.tsx"]
        )
        self.msleep(200)

        # Dispatch to Audio Dev
        audio_payload = "Generate speech synthesis narration track and create kinetic animated SRT subtitles."
        self._dispatch_structured_packet(
            intent="TASK_DISPATCH",
            to_agent="agent_video_audio",
            payload=audio_payload,
            scope_files=["src/audio/narration.mp3", "src/captions/subtitles.srt"]
        )
        self.progress_signal.emit(self.config.agent_id, 85)
        self.msleep(250)

        self._stream_text("OUTPUT", "Creative Director decomposed storyboard and delegated scene assets to Motion and Audio teams.")

    def _execute_dev_motion_flow(self) -> None:
        """Motion Dev Flow: Remotion React UI & Animations."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 20)

        if "remotion-create" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Chloe Bennett activated 'remotion-create' & 'remotion-markup'")
        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Confining visual components to src/scenes/ per '01-architecture-boundaries.md'")

        thought = (
            f"[THOUGHT] Building Remotion React compositions with {self.config.model}. "
            "Configuring <Composition id='MainVideo' fps={60} width={1920} height={1080}>. "
            "Applying spring() physics curves for kinetic typography and card transitions."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 50)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: write_file('src/scenes/IntroScene.tsx', size=3800)")
        self.msleep(300)
        self.progress_signal.emit(self.config.agent_id, 80)

        # Peer review to Audio Dev
        self.status_signal.emit(self.config.agent_id, AgentState.PEER_REVIEW.value)
        review_msg = "Please cross-review IntroScene spring transitions with audio speech peak markers."
        self._dispatch_structured_packet(
            intent="PEER_REVIEW_REQUEST",
            to_agent="agent_video_audio",
            payload=review_msg,
            scope_files=["src/scenes/IntroScene.tsx"]
        )
        self.msleep(250)
        self._stream_text("OUTPUT", "Motion graphics and scene compositions built. Submitted for audio sync review.")

    def _execute_dev_audio_flow(self) -> None:
        """Audio & Captions Flow: Audio synthesis & SRT sync."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 25)

        if "remotion-captions" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Julian Ross activated 'remotion-captions' & 'remotion-multimedia'")
        if "01-architecture-boundaries.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Confining audio assets to src/audio/ per '01-architecture-boundaries.md'")

        thought = (
            f"[THOUGHT] Synthesizing speech narration audio and computing word timestamps under {self.config.model}. "
            "Applying audio ducking (-14 LUFS standard) and generating word-level kinetic subtitle coordinates."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 55)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: generate_subtitles('src/captions/subtitles.srt', style='viral_highlight')")
        self.msleep(300)
        self.progress_signal.emit(self.config.agent_id, 80)

        # Handoff to Video Reviewer
        self.status_signal.emit(self.config.agent_id, AgentState.PEER_REVIEW.value)
        handoff = "Handoff to Video Reviewer: Motion components and audio/caption sync verified. Ready for visual compliance audit."
        self._dispatch_structured_packet(
            intent="PEER_REVIEW_REQUEST",
            to_agent="agent_video_reviewer",
            payload=handoff,
            scope_files=["src/scenes/IntroScene.tsx", "src/captions/subtitles.srt"]
        )
        self.msleep(250)
        self._stream_text("OUTPUT", "Audio voiceover and kinetic subtitles complete. Handoff to Video Reviewer.")

    def _execute_video_reviewer_flow(self) -> None:
        """Video Reviewer Flow: Frame rate, color grading, and subtitle contrast audit."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 25)

        if "03-peer-review-gating.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Evaluating audio-video sync against '03-peer-review-gating.md'")
        if "02-investigate-before-fix.md" in self.config.rules:
            self._stream_text("THOUGHT", "[RULE ENFORCED] Auditing WCAG contrast on captions per '02-investigate-before-fix.md'")

        thought = (
            f"[THOUGHT] Reviewer visual compliance check using {self.config.model} ({self.config.thinking_level}). "
            "Inspecting: 1. No frame drops at 60fps, 2. Subtitle contrast >= 7:1 against video background, 3. No layout overflow."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 60)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: remotion_frame_auditor(fps=60, resolution='1920x1080', check_contrast=True)")
        self.msleep(350)
        self.progress_signal.emit(self.config.agent_id, 85)

        pass_msg = "Video Review PASS: Broadcast compliance verified. Zero dropped frames, perfect audio-subtitle sync. Passing to Render QA."
        self._dispatch_structured_packet(
            intent="APPROVAL_NOTICE",
            to_agent="agent_video_render",
            payload=pass_msg
        )
        self.msleep(200)
        self._stream_text("OUTPUT", "Video quality verified. Approved and escalated to Remotion Render QA.")

    def _execute_render_qa_flow(self) -> None:
        """Render QA Flow: Headless Remotion rendering & packaging."""
        self.status_signal.emit(self.config.agent_id, AgentState.THINKING.value)
        self.progress_signal.emit(self.config.agent_id, 20)

        if "remotion-render" in self.config.skills:
            self._stream_text("TOOL", "[SKILL AUTO-INVOKE] Ethan Cole activated 'remotion-render' & 'headless-qa-automation'")

        thought = (
            f"[THOUGHT] Render QA executing headless Remotion compilation pipeline with {self.config.model}. "
            "Running: npx remotion render src/index.ts MainVideo out/video.mp4 --codec=h264 --crf=18."
        )
        if not self._stream_text("THOUGHT", thought):
            return
        self.progress_signal.emit(self.config.agent_id, 50)

        self.status_signal.emit(self.config.agent_id, AgentState.CALLING_TOOL.value)
        self._stream_text("TOOL", "call_tool: npx remotion render out/video.mp4 (progress: 100%, 3600/3600 frames)")
        self.msleep(350)
        self.progress_signal.emit(self.config.agent_id, 85)

        final_msg = "Render Complete: 3600 frames rendered at 68.4 fps. Zero dropped frames. File size: 42.1 MB MP4 certified."
        self._dispatch_structured_packet(
            intent="APPROVAL_NOTICE",
            to_agent="agent_video_director",
            payload=final_msg,
            severity="NORMAL"
        )
        self.msleep(200)
        self._stream_text("OUTPUT", "Video render certified and exported to out/video.mp4. Sent completion certificate to Director.")


class AgentOrchestrator(QObject):
    """Hierarchical Orchestrator coordinating multiple specialized departments."""

    token_stream_forwarded = pyqtSignal(str, str, str)
    status_forwarded = pyqtSignal(str, str)
    progress_forwarded = pyqtSignal(str, int)
    message_bus_forwarded = pyqtSignal(object)  # StandardMessagePacket
    agent_finished_forwarded = pyqtSignal(str, bool, str)
    pipeline_finished = pyqtSignal(bool, str)
    subordinate_adjusted = pyqtSignal(str, str, str) # (agent_id, model, effort)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.workers: Dict[str, SubAgentWorker] = {}
        self.logger = HistoryLogger()
        self.execution_mode: str = "simulation"
        self._pending_queue: List[SubAgentConfig] = []
        self._current_task: str = ""
        self._is_active: bool = False
        self.departments: Dict[str, DepartmentConfig] = {
            "dept_dev": DepartmentConfig(
                dept_id="dept_dev",
                name="Dev Squad",
                icon="💻",
                default_prompt="Implement Linux desktop utility with peer-review and runtime tests",
                description="Desktop App & Concurrency"
            ),
            "dept_video": DepartmentConfig(
                dept_id="dept_video",
                name="Video Squad",
                icon="🎬",
                default_prompt="Create 60s product showcase video with typography, voiceover, and Remotion",
                description="Remotion & Motion Graphics"
            ),
        }
        self.active_department_id: str = "dept_dev"

    def set_execution_mode(self, mode: str) -> None:
        """Switch between 'simulation' and 'live_cli'."""
        self.execution_mode = mode

    def get_departments(self) -> List[DepartmentConfig]:
        return list(self.departments.values())

    def get_active_department(self) -> DepartmentConfig:
        return self.departments.get(self.active_department_id, self.departments["dept_dev"])

    def set_active_department(self, dept_id: str) -> DepartmentConfig:
        if dept_id in self.departments:
            self.active_department_id = dept_id
        return self.get_active_department()

    def get_department_configs(self, dept_id: Optional[str] = None) -> List[SubAgentConfig]:
        target_dept = dept_id or self.active_department_id
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            personas_dir = os.path.join(sys._MEIPASS, "personas")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            personas_dir = os.path.join(base_dir, "personas")

        if not os.path.exists(personas_dir):
            exec_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidate = os.path.join(exec_dir, "personas")
            if os.path.exists(candidate):
                personas_dir = candidate

        if target_dept == "dept_video":
            return [
                SubAgentConfig(
                    agent_id="agent_video_director",
                    name="Creative Director",
                    role=AgentRole.DIRECTOR,
                    avatar="🎬",
                    model="Gemini 4 Argon (High) (gemini-4-argon-high)",
                    thinking_level="high",
                    system_prompt="Direct video composition, storyboards, pacing, and coordinate motion & audio teams.",
                    persona_file=os.path.join(personas_dir, "06_creative_director.md"),
                    skills=["remotion-best-practices", "design-system", "banner-design"],
                    rules=["01-architecture-boundaries.md"]
                ),
                SubAgentConfig(
                    agent_id="agent_video_motion",
                    name="Motion Graphics Dev",
                    role=AgentRole.DEV_MOTION,
                    avatar="🎨",
                    model="Gemini 3.8 Flash (High) (gemini-3.8-flash-high)",
                    thinking_level="medium",
                    system_prompt="Build Remotion React scenes, kinetic text, and spring-physics animations.",
                    persona_file=os.path.join(personas_dir, "07_motion_graphics_dev.md"),
                    skills=["remotion-create", "remotion-markup", "remotion-interactivity"],
                    rules=["01-architecture-boundaries.md"]
                ),
                SubAgentConfig(
                    agent_id="agent_video_audio",
                    name="Audio & Captions Eng",
                    role=AgentRole.DEV_AUDIO,
                    avatar="🎙️",
                    model="Gemini 3.8 Flash (Medium) (gemini-3.8-flash-medium)",
                    thinking_level="medium",
                    system_prompt="Synthesize voiceover narration, audio ducking, and word-synchronized SRT subtitles.",
                    persona_file=os.path.join(personas_dir, "08_audio_captions_dev.md"),
                    skills=["remotion-captions", "remotion-multimedia"],
                    rules=["01-architecture-boundaries.md"]
                ),
                SubAgentConfig(
                    agent_id="agent_video_reviewer",
                    name="Video Quality Auditor",
                    role=AgentRole.VIDEO_REVIEWER,
                    avatar="🎞️",
                    model="Claude Sonnet 5.5 (High) (claude-sonnet-5-5-high)",
                    thinking_level="high",
                    system_prompt="Audit 60fps frame rates, subtitle readability, color grading, and timing compliance.",
                    persona_file=os.path.join(personas_dir, "09_video_quality_reviewer.md"),
                    skills=["remotion-best-practices"],
                    rules=["02-investigate-before-fix.md", "03-peer-review-gating.md"]
                ),
                SubAgentConfig(
                    agent_id="agent_video_render",
                    name="Remotion Render QA",
                    role=AgentRole.RENDER_QA,
                    avatar="🚀",
                    model="Gemini 3.8 Flash (High) (gemini-3.8-flash-high)",
                    thinking_level="high",
                    system_prompt="Execute headless Remotion render compilation and verify final MP4 artifact stability.",
                    persona_file=os.path.join(personas_dir, "10_render_qa_engineer.md"),
                    skills=["remotion-render", "headless-qa-automation"],
                    rules=[]
                ),
            ]

        # Default: Software Engineering Squad
        return [
            SubAgentConfig(
                agent_id="agent_leader",
                name="Leader / Architect",
                role=AgentRole.LEADER,
                avatar="👑",
                model="Gemini 3.1 Pro",
                thinking_level="high",
                system_prompt="Analyze requirements, partition scopes, and dynamically allocate subagent models and effort.",
                persona_file=os.path.join(personas_dir, "01_leader_architect.md"),
                skills=["concurrency-safe-engine"],
                rules=["01-architecture-boundaries.md"]
            ),
            SubAgentConfig(
                agent_id="agent_dev_ui",
                name="Dev 1: UI & Layout",
                role=AgentRole.DEV_UI,
                avatar="💻",
                model="Gemini 3.8 Flash",
                thinking_level="medium",
                system_prompt="Build responsive PyQt6 widgets and visual indicators.",
                persona_file=os.path.join(personas_dir, "02_dev_frontend.md"),
                skills=["pyqt-ui-builder", "ui-ux-pro-max", "ui-styling"],
                rules=["01-architecture-boundaries.md"]
            ),
            SubAgentConfig(
                agent_id="agent_dev_core",
                name="Dev 2: Core & Threads",
                role=AgentRole.DEV_CORE,
                avatar="💻",
                model="Gemini 3.8 Flash",
                thinking_level="medium",
                system_prompt="Implement asynchronous thread safety, message logging, and agy CLI integration.",
                persona_file=os.path.join(personas_dir, "03_dev_backend.md"),
                skills=["concurrency-safe-engine"],
                rules=["01-architecture-boundaries.md"]
            ),
            SubAgentConfig(
                agent_id="agent_reviewer",
                name="Code Reviewer",
                role=AgentRole.REVIEWER,
                avatar="🛡️",
                model="Claude 3.7 Sonnet",
                thinking_level="high",
                system_prompt="Audit code across threads, verify boundaries, and prevent bugs.",
                persona_file=os.path.join(personas_dir, "04_code_reviewer.md"),
                skills=[],
                rules=["02-investigate-before-fix.md", "03-peer-review-gating.md", "investigate-before-fix.md"]
            ),
            SubAgentConfig(
                agent_id="agent_tester",
                name="Runtime Tester",
                role=AgentRole.TESTER,
                avatar="🧪",
                model="Gemini 3.8 Flash",
                thinking_level="high",
                system_prompt="Execute runtime tests, Playwright browser E2E suites, and Chrome DevTools MCP diagnostics.",
                persona_file=os.path.join(personas_dir, "05_qa_tester.md"),
                skills=["headless-qa-automation", "playwright-automation", "chrome-devtools"],
                rules=[]
            ),
        ]

    def get_default_configs(self) -> List[SubAgentConfig]:
        return self.get_department_configs(self.active_department_id)

    def update_agent_params(self, agent_id: str, new_model: str, new_effort: str) -> None:
        """Dynamically update model and thinking effort of an agent."""
        if agent_id in self.workers:
            self.workers[agent_id].config.model = new_model
            self.workers[agent_id].config.thinking_level = new_effort

    def dispatch_hierarchical_pipeline(self, task_prompt: str) -> None:
        """Start hierarchical pipeline flow: Leader/Director -> Parallel Devs -> Reviewer -> Tester/Render QA."""
        self.stop_all()
        self._current_task = task_prompt
        self._is_active = True

        configs = self.get_department_configs(self.active_department_id)
        self.config_map = {c.agent_id: c for c in configs}

        # Stage 1: Initiator (Leader or Director)
        initial_agent_id = "agent_video_director" if self.active_department_id == "dept_video" else "agent_leader"
        if initial_agent_id in self.config_map:
            self._start_worker(self.config_map[initial_agent_id])

    def _start_worker(self, config: SubAgentConfig) -> None:
        worker = SubAgentWorker(config, self._current_task, self.logger, execution_mode=self.execution_mode)
        worker.stream_signal.connect(self.token_stream_forwarded.emit)
        worker.status_signal.connect(self.status_forwarded.emit)
        worker.progress_signal.connect(self.progress_forwarded.emit)
        worker.message_bus_signal.connect(self.message_bus_forwarded.emit)
        worker.finished_signal.connect(self._on_stage_finished)
        worker.adjust_subordinate_signal.connect(self._on_subordinate_adjusted)

        self.workers[config.agent_id] = worker
        worker.start()

    def _on_subordinate_adjusted(self, target_agent: str, model: str, effort: str) -> None:
        """Forward Leader's adjustment of a subordinate agent to the UI."""
        if target_agent in self.config_map:
            self.config_map[target_agent].model = model
            self.config_map[target_agent].thinking_level = effort
        self.subordinate_adjusted.emit(target_agent, model, effort)

    def _on_stage_finished(self, agent_id: str, success: bool, summary: str) -> None:
        self.agent_finished_forwarded.emit(agent_id, success, summary)
        if not self._is_active or not success:
            if not success:
                self.pipeline_finished.emit(False, f"Pipeline halted: {agent_id} encountered an error.")
            return

        is_video = "video" in agent_id
        # Advance hierarchical stages
        if agent_id in ("agent_leader", "agent_video_director"):
            # Stage 2: Parallel execution of Dev 1 and Dev 2 (or Motion & Audio)
            dev1_id = "agent_video_motion" if is_video else "agent_dev_ui"
            dev2_id = "agent_video_audio" if is_video else "agent_dev_core"
            self._start_worker(self.config_map[dev1_id])
            self._start_worker(self.config_map[dev2_id])

        elif agent_id in ["agent_dev_ui", "agent_dev_core", "agent_video_motion", "agent_video_audio"]:
            dev1_id = "agent_video_motion" if is_video else "agent_dev_ui"
            dev2_id = "agent_video_audio" if is_video else "agent_dev_core"
            dev1_done = not self.workers.get(dev1_id, SubAgentWorker(self.config_map[dev1_id], "", self.logger)).isRunning()
            dev2_done = not self.workers.get(dev2_id, SubAgentWorker(self.config_map[dev2_id], "", self.logger)).isRunning()

            reviewer_id = "agent_video_reviewer" if is_video else "agent_reviewer"
            if dev1_done and dev2_done and reviewer_id not in self.workers:
                # Stage 3: Handoff to Reviewer
                self._start_worker(self.config_map[reviewer_id])

        elif agent_id in ("agent_reviewer", "agent_video_reviewer"):
            # Stage 4: Handoff to Runtime Tester / Render QA
            test_id = "agent_video_render" if is_video else "agent_tester"
            self._start_worker(self.config_map[test_id])

        elif agent_id in ("agent_tester", "agent_video_render"):
            self._is_active = False
            self.pipeline_finished.emit(True, "All 5 hierarchical pipeline stages successfully completed & verified.")

    def pause_all(self) -> None:
        for worker in self.workers.values():
            if worker.isRunning():
                worker.pause()

    def resume_all(self) -> None:
        for worker in self.workers.values():
            if worker.isRunning():
                worker.resume()

    def stop_all(self) -> None:
        self._is_active = False
        for worker in self.workers.values():
            if worker.isRunning():
                try:
                    worker.stream_signal.disconnect()
                    worker.status_signal.disconnect()
                    worker.progress_signal.disconnect()
                    worker.message_bus_signal.disconnect()
                    worker.finished_signal.disconnect()
                except (TypeError, RuntimeError):
                    pass
                worker.stop()
                if not worker.wait(1500):
                    worker.terminate()
                    worker.wait(300)
        self.workers.clear()
