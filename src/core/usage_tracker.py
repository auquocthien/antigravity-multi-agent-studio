"""Usage and System Resource Telemetry Tracker for Agy Multi-Agent Studio."""

import os
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


@dataclass
class AgentUsageStats:
    agent_id: str
    name: str
    avatar: str
    model: str
    calls_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    last_latency_sec: float = 0.0
    last_updated: str = ""


class SystemResourceMonitor:
    """Reads Linux host CPU and Memory metrics using POSIX /proc virtual filesystem."""

    _last_cpu_idle: int = 0
    _last_cpu_total: int = 0

    @classmethod
    def get_cpu_percent(cls) -> float:
        """Calculate CPU utilization percentage from /proc/stat."""
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                first_line = f.readline()
            fields = [int(v) for v in first_line.split()[1:]]
            idle = fields[3] + fields[4]  # idle + iowait
            total = sum(fields)

            if cls._last_cpu_total == 0:
                cls._last_cpu_idle = idle
                cls._last_cpu_total = total
                return 0.0

            delta_total = total - cls._last_cpu_total
            delta_idle = idle - cls._last_cpu_idle

            cls._last_cpu_idle = idle
            cls._last_cpu_total = total

            if delta_total <= 0:
                return 0.0
            cpu_percent = 100.0 * (1.0 - (delta_idle / delta_total))
            return max(0.0, min(100.0, round(cpu_percent, 1)))
        except (OSError, ValueError, IndexError):
            return 0.0

    @classmethod
    def get_memory_info(cls) -> Dict[str, Any]:
        """Read RAM usage from /proc/meminfo in MB and percent."""
        try:
            mem_data: Dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip().split()[0]
                        if val_str.isdigit():
                            mem_data[key] = int(val_str)  # kB

            total_kb = mem_data.get("MemTotal", 0)
            avail_kb = mem_data.get("MemAvailable", mem_data.get("MemFree", 0))

            if total_kb <= 0:
                return {"total_mb": 0, "used_mb": 0, "percent": 0.0}

            used_kb = total_kb - avail_kb
            total_mb = int(total_kb / 1024)
            used_mb = int(used_kb / 1024)
            percent = round((used_kb / total_kb) * 100.0, 1)

            return {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "percent": percent
            }
        except (OSError, ValueError):
            return {"total_mb": 0, "used_mb": 0, "percent": 0.0}


class UsageTracker(QObject):
    """Tracks token consumption, agy CLI sessions, and Linux host resources."""

    usage_updated = pyqtSignal(dict)  # Emits current aggregate telemetry stats
    system_resources_updated = pyqtSignal(float, float, int, int)  # (cpu_pct, ram_pct, ram_used_mb, ram_total_mb)

    def __init__(self, persistence_file: Optional[str] = None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if persistence_file:
            self.persistence_file = persistence_file
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.persistence_file = os.path.join(base_dir, ".agent", "usage_stats.json")

        self.total_tokens: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.thinking_tokens: int = 0
        self.cli_invocations: int = 0
        self.total_duration_sec: float = 0.0
        self.agent_stats: Dict[str, AgentUsageStats] = {}
        self.model_stats: Dict[str, int] = {}  # model_name -> total_tokens

        self._load()

        # System resource sampling timer (every 1.5 seconds)
        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self._sample_system_resources)
        self.sys_timer.start(1500)

    def _sample_system_resources(self) -> None:
        cpu = SystemResourceMonitor.get_cpu_percent()
        mem = SystemResourceMonitor.get_memory_info()
        self.system_resources_updated.emit(cpu, mem["percent"], mem["used_mb"], mem["total_mb"])

    def record_usage(
        self,
        agent_id: str,
        name: str,
        avatar: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
        duration_sec: float = 0.0
    ) -> None:
        """Record tokens and execution stats for a specific subagent turn."""
        turn_total = input_tokens + output_tokens + thinking_tokens

        self.total_tokens += turn_total
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.thinking_tokens += thinking_tokens
        self.cli_invocations += 1
        self.total_duration_sec += duration_sec

        # Update per-agent record
        if agent_id not in self.agent_stats:
            self.agent_stats[agent_id] = AgentUsageStats(
                agent_id=agent_id,
                name=name,
                avatar=avatar,
                model=model
            )

        agent = self.agent_stats[agent_id]
        agent.calls_count += 1
        agent.input_tokens += input_tokens
        agent.output_tokens += output_tokens
        agent.thinking_tokens += thinking_tokens
        agent.total_tokens += turn_total
        agent.last_latency_sec = round(duration_sec, 2)
        agent.model = model
        agent.last_updated = time.strftime("%H:%M:%S")

        # Update per-model consumption
        self.model_stats[model] = self.model_stats.get(model, 0) + turn_total

        self._save()
        self.usage_updated.emit(self.get_telemetry_snapshot())

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """Produce serializable snapshot of aggregate usage metrics."""
        return {
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cli_invocations": self.cli_invocations,
            "total_duration_sec": round(self.total_duration_sec, 2),
            "model_stats": dict(self.model_stats),
            "agents": {aid: asdict(stats) for aid, stats in self.agent_stats.items()}
        }

    def reset_stats(self) -> None:
        """Clear all usage metrics and persist empty stats."""
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.thinking_tokens = 0
        self.cli_invocations = 0
        self.total_duration_sec = 0.0
        self.agent_stats.clear()
        self.model_stats.clear()
        self._save()
        self.usage_updated.emit(self.get_telemetry_snapshot())

    def _save(self) -> None:
        """Persist usage statistics to JSON file."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.persistence_file)), exist_ok=True)
            snapshot = self.get_telemetry_snapshot()
            snapshot["last_saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except OSError:
            pass

    def _load(self) -> None:
        """Load stored usage statistics if available."""
        if not os.path.exists(self.persistence_file):
            return
        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.total_tokens = data.get("total_tokens", 0)
            self.input_tokens = data.get("input_tokens", 0)
            self.output_tokens = data.get("output_tokens", 0)
            self.thinking_tokens = data.get("thinking_tokens", 0)
            self.cli_invocations = data.get("cli_invocations", 0)
            self.total_duration_sec = data.get("total_duration_sec", 0.0)
            self.model_stats = data.get("model_stats", {})

            agents_data = data.get("agents", {})
            for aid, a_dict in agents_data.items():
                self.agent_stats[aid] = AgentUsageStats(**a_dict)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
