"""Multi-CLI Engine and Pluggable AI CLI Bridges (agy, ollama, custom)."""

import os
import json
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


class BaseCliBridge(ABC):
    """Abstract Base Class for external AI CLI providers."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique identifier for this CLI provider (e.g. 'agy', 'ollama', 'custom')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable badge name (e.g. '⚡ Antigravity agy', '🦙 Ollama Local')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the CLI binary or service is reachable on this system."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of models supported by this CLI provider."""
        pass

    @abstractmethod
    def format_command(
        self,
        target_agent: str,
        prompt: str,
        model: str,
        thinking_level: str = "medium",
        cwd: Optional[str] = None
    ) -> List[str]:
        """Build argument list for subprocess execution."""
        pass

    @abstractmethod
    def parse_stream_line(self, raw_line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Parse real-time line from CLI output.
        Returns:
            (text_chunk, usage_dict_or_none)
        """
        pass

    def get_env(self) -> Optional[Dict[str, str]]:
        """Return custom environment variables for subprocess execution, or None to inherit system env."""
        return None

    def is_rate_limited(self, output_line: str, exit_code: Optional[int] = None) -> bool:
        """Detect whether this output line or exit code indicates a rate limit or quota exhaustion."""
        if not output_line:
            return False
        s = output_line.lower()
        limit_markers = [
            "429",
            "resource_exhausted",
            "rate limit",
            "rate_limit",
            "quota exceeded",
            "exceeded your current quota",
            "too many requests",
            "overloaded",
            "quota_exhausted",
            "capacity exceeded",
        ]
        return any(m in s for m in limit_markers)


class AgyCliBridge(BaseCliBridge):
    """Executes commands via the Antigravity CLI (agy) with model and effort routing."""

    CLI_PATHS = [
        "/home/thienau/.local/bin/agy",
        shutil.which("agy") or "agy",
    ]

    @property
    def engine_id(self) -> str:
        return "agy"

    @property
    def display_name(self) -> str:
        return "⚡ Antigravity (agy)"

    @classmethod
    def get_agy_binary(cls) -> Optional[str]:
        for p in cls.CLI_PATHS:
            if p and os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        return None

    def is_available(self) -> bool:
        return self.get_agy_binary() is not None

    def get_available_models(self) -> List[str]:
        """Fetch real available models from authenticated agy CLI or fallback gracefully."""
        agy_bin = self.get_agy_binary()
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

    def format_command(
        self,
        target_agent: str,
        prompt: str,
        model: str = "Gemini 3.8 Flash",
        thinking_level: str = "medium",
        cwd: Optional[str] = None
    ) -> List[str]:
        """Build agy execution command array with --model and appropriate flags."""
        return self.format_cli_command(target_agent, prompt, model, thinking_level)

    @classmethod
    def format_cli_command(
        cls,
        target_agent: str,
        prompt: str,
        model: str = "Gemini 3.8 Flash",
        thinking_level: str = "medium"
    ) -> List[str]:
        agy_bin = cls.get_agy_binary() or "agy"

        # Map display model names to valid CLI model IDs
        model_id = "gemini-3.8-flash-high"
        if "(" in model and ")" in model:
            extracted = model.split("(")[-1].replace(")", "").strip()
            if extracted:
                model_id = extracted
        elif "4 Argon" in model:
            model_id = "gemini-4-argon-medium"
        elif "3.1 Pro" in model:
            model_id = "gemini-3.8-flash-high"
        elif "Opus" in model:
            model_id = "claude-opus-5-5-high"
        elif "Sonnet" in model:
            model_id = "claude-sonnet-5-5-high"
        elif "OSS" in model:
            model_id = "gpt-oss-120b-medium"

        cmd = [
            agy_bin,
            "--dangerously-skip-permissions",
            "--mode", "accept-edits",
            "--model", model_id,
            "--output-format", "stream-json",
        ]

        if not any(model_id.endswith(f"-{sfx}") for sfx in ("low", "medium", "high", "xhigh", "max")):
            effort_map = {"low": "low", "medium": "medium", "high": "high", "max": "max"}
            cmd.extend(["--effort", effort_map.get(thinking_level.lower(), "medium")])

        cmd.extend(["-p", prompt])
        return cmd

    def parse_stream_line(self, raw_line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Parses agy NDJSON stream events."""
        line_s = raw_line.strip()
        if line_s.startswith("{") and line_s.endswith("}"):
            try:
                ev = json.loads(line_s)
                if ev.get("event") == "step_update":
                    delta = ev.get("step_update", {}).get("text_delta", "")
                    return (delta if delta else None, None)
                elif ev.get("event") == "result":
                    res = ev.get("result", {})
                    usage = res.get("usage", {})
                    resp_text = res.get("response", "")
                    return (resp_text if resp_text else None, usage if usage else None)
            except Exception:
                pass
        return (raw_line, None)


@dataclass
class AgyInstance2Config:
    """Configuration for the secondary isolated Antigravity CLI instance."""
    profile_dir: str = ""
    auth_mode: str = "oauth"  # "oauth" or "gemini_api_key"
    gemini_api_key: str = ""

    @classmethod
    def get_default_profile_dir(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, ".agent", "profiles", "agy_instance_2")

    @classmethod
    def get_config_file_path(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, ".agent", "instance2_config.json")

    @classmethod
    def load(cls) -> "AgyInstance2Config":
        p = cls.get_config_file_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(
                        profile_dir=data.get("profile_dir") or cls.get_default_profile_dir(),
                        auth_mode=data.get("auth_mode", "oauth"),
                        gemini_api_key=data.get("gemini_api_key", "")
                    )
            except Exception:
                pass
        return cls(profile_dir=cls.get_default_profile_dir())

    def save(self) -> bool:
        p = self.get_config_file_path()
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({
                    "profile_dir": self.profile_dir or self.get_default_profile_dir(),
                    "auth_mode": self.auth_mode,
                    "gemini_api_key": self.gemini_api_key
                }, f, indent=2)
            return True
        except Exception:
            return False


class AgyInstance2CliBridge(AgyCliBridge):
    """Executes commands via an isolated 2nd Antigravity CLI instance.
    Runs with a distinct HOME/profile directory and/or GEMINI_API_KEY,
    ensuring complete decoupling from the account logged in on the host machine.
    """

    def __init__(self, config: Optional[AgyInstance2Config] = None) -> None:
        super().__init__()
        self.config: AgyInstance2Config = config or AgyInstance2Config.load()
        if not self.config.profile_dir:
            self.config.profile_dir = AgyInstance2Config.get_default_profile_dir()

    @property
    def engine_id(self) -> str:
        return "agy_instance_2"

    @property
    def display_name(self) -> str:
        return "🚀 Antigravity (Instance 2 / Isolated)"

    def get_env(self) -> Dict[str, str]:
        """Returns isolated environment with separate HOME and optional GEMINI_API_KEY."""
        env = os.environ.copy()
        profile_path = os.path.abspath(self.config.profile_dir or AgyInstance2Config.get_default_profile_dir())
        os.makedirs(os.path.join(profile_path, ".gemini", "antigravity-cli"), exist_ok=True)
        env["HOME"] = profile_path
        if self.config.auth_mode == "gemini_api_key" and self.config.gemini_api_key.strip():
            env["GEMINI_API_KEY"] = self.config.gemini_api_key.strip()
        return env

    def is_authenticated(self) -> bool:
        """Check if Instance 2 has credentials (either API key or OAuth token file)."""
        if self.config.auth_mode == "gemini_api_key" and self.config.gemini_api_key.strip():
            return True
        profile_path = os.path.abspath(self.config.profile_dir or AgyInstance2Config.get_default_profile_dir())
        token_file = os.path.join(profile_path, ".gemini", "antigravity-cli", "antigravity-oauth-token")
        return os.path.exists(token_file) and os.path.getsize(token_file) > 10

    def launch_interactive_login(self) -> Tuple[bool, str]:
        """Opens an interactive terminal allowing the user to authenticate the 2nd instance via OAuth."""
        profile_path = os.path.abspath(self.config.profile_dir or AgyInstance2Config.get_default_profile_dir())
        os.makedirs(os.path.join(profile_path, ".gemini", "antigravity-cli"), exist_ok=True)
        agy_bin = self.get_agy_binary() or "agy"

        terminal = shutil.which("xfce4-terminal") or shutil.which("kitty")
        if not terminal:
            return (False, "No GUI terminal emulator (xfce4-terminal, kitty) found.")

        try:
            if "xfce4-terminal" in terminal:
                subprocess.Popen([
                    terminal,
                    "--title=Antigravity CLI - Instance 2 Login",
                    "-e",
                    f"bash -c 'export HOME=\"{profile_path}\"; echo \"Logging in Antigravity CLI Instance 2...\"; {agy_bin}; exec bash'"
                ], start_new_session=True)
            else:
                subprocess.Popen([
                    terminal,
                    "--title", "Antigravity CLI - Instance 2 Login",
                    "bash", "-c",
                    f"export HOME=\"{profile_path}\"; echo \"Logging in Antigravity CLI Instance 2...\"; {agy_bin}; exec bash"
                ], start_new_session=True)
            return (True, f"Launched interactive login in {os.path.basename(terminal)} with profile {profile_path}")
        except Exception as e:
            return (False, f"Failed to launch terminal: {e}")

    def get_available_models(self) -> List[str]:
        """Fetch real available models from isolated agy CLI instance or fallback gracefully."""
        agy_bin = self.get_agy_binary()
        if agy_bin:
            try:
                proc = subprocess.run(
                    [agy_bin, "models"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=self.get_env()
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


class OllamaCliBridge(BaseCliBridge):
    """Executes commands via local Ollama CLI and captures prompt/eval token telemetry."""

    @property
    def engine_id(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return "🦙 Ollama Local"

    def is_available(self) -> bool:
        if shutil.which("ollama"):
            return True
        # Check HTTP daemon
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "AntigravityStudio"})
            with urllib.request.urlopen(req, timeout=1) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        """Fetch available models from local Ollama service."""
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "AntigravityStudio"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                if models:
                    return models
        except Exception:
            pass

        # Fallback to checking cli list
        if shutil.which("ollama"):
            try:
                proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
                if proc.returncode == 0 and proc.stdout:
                    lines = proc.stdout.splitlines()
                    models = [l.split()[0] for l in lines[1:] if l.strip()]
                    if models:
                        return models
            except Exception:
                pass

        return ["llama3.2:1b", "llama3.2:latest", "qwen2.5-coder:latest", "deepseek-r1:latest"]

    def format_command(
        self,
        target_agent: str,
        prompt: str,
        model: str = "llama3.2:1b",
        thinking_level: str = "medium",
        cwd: Optional[str] = None
    ) -> List[str]:
        ollama_bin = shutil.which("ollama") or "ollama"
        clean_model = model.split("(")[0].strip() if "(" in model else model.strip()
        if not clean_model:
            clean_model = "llama3.2:1b"

        # Use verbose flag so timing and token counts are emitted to stderr/stdout
        return [
            ollama_bin,
            "run",
            clean_model,
            "--verbose",
            prompt
        ]

    def parse_stream_line(self, raw_line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Parses output from ollama run --verbose.
        Extracts 'prompt eval count' and 'eval count' as telemetry tokens.
        """
        line_s = raw_line.strip()
        lower = line_s.lower()

        # Check for verbose telemetry lines
        usage_dict: Optional[Dict[str, Any]] = None
        if "prompt eval count:" in lower:
            parts = line_s.split(":")
            if len(parts) > 1:
                tok_str = parts[1].strip().split()[0]
                if tok_str.isdigit():
                    usage_dict = {"input_tokens": int(tok_str)}
            return (None, usage_dict)

        if "eval count:" in lower and "prompt" not in lower:
            parts = line_s.split(":")
            if len(parts) > 1:
                tok_str = parts[1].strip().split()[0]
                if tok_str.isdigit():
                    usage_dict = {"output_tokens": int(tok_str)}
            return (None, usage_dict)

        # Filter out progress spinner characters (⠙ ⠹ ⠸)
        cleaned = "".join(c for c in raw_line if c not in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        if not cleaned.strip() and raw_line.strip():
            return (None, None)

        return (cleaned if cleaned else raw_line, None)


class CustomCliBridge(BaseCliBridge):
    """Executes custom secondary CLI commands via shell template."""

    def __init__(self, cli_bin: str = "python3", template: str = "{bin} -c 'print(\"{prompt}\")'") -> None:
        self._cli_bin = cli_bin
        self._template = template

    @property
    def engine_id(self) -> str:
        return "custom"

    @property
    def display_name(self) -> str:
        return "🔧 Custom CLI"

    def is_available(self) -> bool:
        return True

    def get_available_models(self) -> List[str]:
        return ["custom-default", "custom-fast", "custom-reasoning"]

    def format_command(
        self,
        target_agent: str,
        prompt: str,
        model: str = "custom-default",
        thinking_level: str = "medium",
        cwd: Optional[str] = None
    ) -> List[str]:
        # Simple customizable execution array
        return [
            "/bin/bash",
            "-c",
            f"echo '[Custom CLI executing: {model}]' && echo '{prompt[:100]}...'"
        ]

    def parse_stream_line(self, raw_line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        # Estimate ~1 token per 4 chars for custom outputs
        chars = len(raw_line.strip())
        est_tokens = max(1, chars // 4)
        return (raw_line, {"output_tokens": est_tokens, "input_tokens": 100})


class CliRegistry:
    """Registry managing pluggable CLI providers across the studio."""

    _bridges: Dict[str, BaseCliBridge] = {
        "agy": AgyCliBridge(),
        "agy_instance_2": AgyInstance2CliBridge(),
        "ollama": OllamaCliBridge(),
        "custom": CustomCliBridge()
    }

    @classmethod
    def register(cls, bridge: BaseCliBridge) -> None:
        cls._bridges[bridge.engine_id] = bridge

    @classmethod
    def get_bridge(cls, engine_id: str) -> BaseCliBridge:
        norm = (engine_id or "agy").lower().strip()
        if norm in cls._bridges:
            return cls._bridges[norm]
        # Match aliases for instance 2
        if any(term in norm for term in ["instance_2", "instance2", "agy_2", "agy_alt", "alt"]):
            return cls._bridges["agy_instance_2"]
        # Match by prefix
        for k, v in cls._bridges.items():
            if k in norm or norm in k:
                return v
        return cls._bridges["agy"]

    @classmethod
    def get_all_bridges(cls) -> List[BaseCliBridge]:
        return list(cls._bridges.values())

    @classmethod
    def get_available_engines(cls) -> List[Tuple[str, str, bool]]:
        """Returns list of (engine_id, display_name, is_available)."""
        result = []
        for b in cls._bridges.values():
            result.append((b.engine_id, b.display_name, b.is_available()))
        return result

    @classmethod
    def get_failover_engine(cls, current_engine: str) -> str:
        """Returns secondary fallback engine when current engine encounters limits."""
        norm = (current_engine or "agy").lower().strip()
        if any(term in norm for term in ["instance_2", "instance2", "agy_2", "agy_alt"]):
            return "agy"
        elif "agy" in norm:
            return "agy_instance_2"
        elif "ollama" in norm:
            return "agy"
        return "agy_instance_2"

