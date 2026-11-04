"""Individual Agent Observer Card Widget with live streaming console."""

import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QPushButton,
)

from src.core.engine import SubAgentConfig


class AgentCardWidget(QFrame):
    """Visual monitor card displaying live thoughts, tools, and output for a single agent."""

    def __init__(self, config: SubAgentConfig, parent=None) -> None:
        super().__init__(parent)
        self.config: SubAgentConfig = config

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self) -> None:
        self.setObjectName("agent_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        lbl_avatar = QLabel(self.config.avatar)
        lbl_avatar.setStyleSheet("font-size: 20px;")
        header_layout.addWidget(lbl_avatar)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_name = QLabel(self.config.name)
        lbl_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        lbl_role = QLabel(self.config.role.value)
        lbl_role.setStyleSheet("font-size: 11px; color: #a6adc8;")
        title_box.addWidget(lbl_name)
        title_box.addWidget(lbl_role)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Status badge pill
        self.badge_status = QLabel("IDLE")
        self.badge_status.setObjectName("badge_status")
        header_layout.addWidget(self.badge_status)

        layout.addLayout(header_layout)

        # Reasoning Budget Bar
        budget_layout = QHBoxLayout()
        lbl_budget_tag = QLabel(f"Reasoning Budget: <b>{self.config.thinking_level.upper()}</b>")
        lbl_budget_tag.setStyleSheet("font-size: 11px; color: #fab387;")
        budget_layout.addWidget(lbl_budget_tag)
        budget_layout.addStretch()
        layout.addLayout(budget_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Live Terminal Console
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setObjectName("agent_terminal")
        self.terminal.setPlaceholderText(f"Awaiting task dispatch for {self.config.name}...")
        layout.addWidget(self.terminal, stretch=1)

        # Bottom Quick actions
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        btn_clear.clicked.connect(self.clear_console)
        bottom_layout.addWidget(btn_clear)
        layout.addLayout(bottom_layout)

    def _apply_styling(self) -> None:
        self.setStyleSheet("""
        QFrame#agent_card {
            background-color: #1e1e2e;
            border: 1px solid #313244;
            border-radius: 10px;
        }
        QLabel#badge_status {
            background-color: #313244;
            color: #a6adc8;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 8px;
        }
        QTextEdit#agent_terminal {
            background-color: #11111b;
            color: #cdd6f4;
            font-family: "JetBrains Mono", "Fira Code", monospace;
            font-size: 12px;
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 6px;
        }
        QProgressBar {
            background-color: #11111b;
            border: none;
            border-radius: 4px;
        }
        QProgressBar::chunk {
            background-color: #89b4fa;
            border-radius: 4px;
        }
        """)

    def set_status(self, status: str) -> None:
        """Update the agent status badge with responsive palette coloring."""
        self.badge_status.setText(status)
        palette = {
            "IDLE": ("#313244", "#a6adc8"),
            "PLANNING": ("#89b4fa", "#11111b"),
            "THINKING": ("#cba6f7", "#11111b"),
            "CALLING_TOOL": ("#f9e2af", "#11111b"),
            "COLLABORATING": ("#94e2d5", "#11111b"),
            "COMPLETED": ("#a6e3a1", "#11111b"),
            "PAUSED": ("#fab387", "#11111b"),
            "STOPPED": ("#f38ba8", "#11111b"),
            "ERROR": ("#f38ba8", "#11111b"),
        }
        bg, fg = palette.get(status, ("#313244", "#a6adc8"))
        self.badge_status.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 8px;"
        )

    def set_progress(self, percent: int) -> None:
        """Set agent progress percentage."""
        self.progress_bar.setValue(percent)

    def append_chunk(self, stream_type: str, chunk: str) -> None:
        """Append streaming token or message into the terminal with syntax colors."""
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        color_map = {
            "CLI_CMD": "#a6e3a1",   # Green for CLI commands
            "THOUGHT": "#cba6f7",   # Mauve
            "TOOL": "#f9e2af",      # Yellow
            "OUTPUT": "#89b4fa",    # Blue
            "MESSAGE": "#94e2d5",   # Teal
            "SYSTEM": "#fab387",    # Peach
        }
        color = color_map.get(stream_type, "#cdd6f4")

        # Format newlines safely
        formatted_html = chunk.replace("\n", "<br/>").replace(" ", "&nbsp;")
        cursor.insertHtml(f"<span style='color: {color};'>{formatted_html}</span>")
        self.terminal.setTextCursor(cursor)
        self.terminal.ensureCursorVisible()

    def clear_console(self) -> None:
        """Clear the console terminal content."""
        self.terminal.clear()
