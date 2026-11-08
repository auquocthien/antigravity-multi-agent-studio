"""Checkpoint Manager for pipeline state persistence, rate limit failover, and session resumption."""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union


@dataclass
class PipelineCheckpoint:
    """Represents a frozen snapshot of the multi-agent pipeline state."""
    stage_index: int = 1  # 1: Leader, 2: Parallel Devs, 3: Reviewer, 4: Tester, 5: Completed
    stage_name: str = "Stage 1"
    checkpoint_id: str = ""
    timestamp: str = ""
    department_id: str = "dept_dev"
    task_prompt: str = ""
    completed_stages: List[str] = field(default_factory=list)
    agent_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    failover_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            self.checkpoint_id = f"chk_{int(time.time())}_{self.stage_index}"
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineCheckpoint":
        return cls(
            checkpoint_id=data.get("checkpoint_id", f"chk_{int(time.time())}"),
            timestamp=data.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
            department_id=data.get("department_id", "dept_dev"),
            task_prompt=data.get("task_prompt", ""),
            stage_index=data.get("stage_index", 1),
            stage_name=data.get("stage_name", "Stage 1"),
            completed_stages=data.get("completed_stages", []),
            agent_states=data.get("agent_states", {}),
            artifacts=data.get("artifacts", []),
            failover_log=data.get("failover_log", [])
        )


class CheckpointManager:
    """Manages persistence and recovery of pipeline checkpoints."""

    def __init__(
        self,
        persistence_file: Optional[str] = None,
        checkpoint_file: Optional[str] = None
    ) -> None:
        target = persistence_file or checkpoint_file
        if target:
            self.persistence_file = target
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.persistence_file = os.path.join(base_dir, ".agent", "pipeline_checkpoint.json")

    def save_checkpoint(
        self,
        checkpoint: Optional[Union[PipelineCheckpoint, str]] = None,
        department_id: str = "dept_dev",
        task_prompt: str = "",
        stage_index: int = 1,
        stage_name: str = "Stage 1",
        completed_stages: Optional[List[str]] = None,
        agent_states: Optional[Dict[str, Dict[str, Any]]] = None,
        artifacts: Optional[List[str]] = None,
        failover_log: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> PipelineCheckpoint:
        """Saves current pipeline execution state to JSON checkpoint file."""
        os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)

        if isinstance(checkpoint, PipelineCheckpoint):
            chk = checkpoint
        elif isinstance(checkpoint, str):
            chk = PipelineCheckpoint(
                checkpoint_id=f"chk_{int(time.time())}_{stage_index}",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                department_id=checkpoint,
                task_prompt=task_prompt,
                stage_index=stage_index,
                stage_name=stage_name,
                completed_stages=list(completed_stages or []),
                agent_states=agent_states or {},
                artifacts=artifacts or [],
                failover_log=failover_log or []
            )
        else:
            chk = PipelineCheckpoint(
                checkpoint_id=f"chk_{int(time.time())}_{stage_index}",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                department_id=kwargs.get("department_id", department_id),
                task_prompt=task_prompt,
                stage_index=stage_index,
                stage_name=stage_name,
                completed_stages=list(completed_stages or []),
                agent_states=agent_states or {},
                artifacts=artifacts or [],
                failover_log=failover_log or []
            )

        try:
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(chk.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError:
            pass

        return chk

    def load_checkpoint(self) -> Optional[PipelineCheckpoint]:
        """Loads and parses the existing checkpoint from disk."""
        if not os.path.exists(self.persistence_file):
            return None

        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PipelineCheckpoint.from_dict(data)
        except (OSError, json.JSONDecodeError):
            return None

    def has_valid_checkpoint(self) -> bool:
        """Returns True if a valid resumable checkpoint exists."""
        chk = self.load_checkpoint()
        if chk is None:
            return False
        # If pipeline already completed 100% (stage 5), not resumable
        return 1 <= chk.stage_index < 5

    def clear_checkpoint(self) -> None:
        """Removes existing checkpoint file upon successful pipeline completion."""
        if os.path.exists(self.persistence_file):
            try:
                os.remove(self.persistence_file)
            except OSError:
                pass
