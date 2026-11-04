"""Compact Agent Node Widget tailored for sleek horizontal pipeline flows."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)

from src.core.engine import SubAgentConfig


class CompactAgentNodeWidget(QFrame):
    """Compact rectangular node widget representing an agent with PRO-MAX visual polish."""

    clicked = pyqtSignal(str)  # agent_id

    def __init__(self, config: SubAgentConfig, parent=None) -> None:
        super().__init__(parent)
        self.config: SubAgentConfig = config
        self._is_active_stage = False

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self) -> None:
        self.setObjectName("compact_node_card")
        self.setFixedSize(195, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Top row: Role Avatar Pill + Name & Title
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Color-coded avatar badge container
        role_colors = {
            "agent_leader": ("#8B5CF6", "#1E1B4B"),
            "agent_dev_ui": ("#06B6D4", "#083344"),
            "agent_dev_core": ("#3B82F6", "#172554"),
            "agent_reviewer": ("#F59E0B", "#451A03"),
            "agent_tester": ("#10B981", "#022C22"),
        }
        border_col, bg_col = role_colors.get(self.config.agent_id, ("#6366F1", "#1E1B4B"))

        self.avatar_pill = QLabel(self.config.avatar)
        self.avatar_pill.setFixedSize(28, 28)
        self.avatar_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_pill.setStyleSheet(
            f"font-size: 15px; background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 6px;"
        )
        top_row.addWidget(self.avatar_pill)

        name_box = QVBoxLayout()
        name_box.setSpacing(1)
        self.lbl_name = QLabel(self.config.name)
        self.lbl_name.setStyleSheet("font-size: 11px; font-weight: 700; color: #F9FAFB;")
        self.lbl_role = QLabel(self.config.role.value.split(":")[0])
        self.lbl_role.setStyleSheet("font-size: 9px; color: #9CA3AF; font-weight: 500;")
        name_box.addWidget(self.lbl_name)
        name_box.addWidget(self.lbl_role)
        top_row.addLayout(name_box)
        top_row.addStretch()

        layout.addLayout(top_row)

        # Status row with LED indicator dot
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        self.badge_status = QLabel("● IDLE")
        self.badge_status.setObjectName("badge_status")
        status_row.addWidget(self.badge_status)
        status_row.addStretch()

        # Model and Thinking tags
        self.lbl_model_tag = QLabel(f"{self.config.model.split()[0]} · {self.config.thinking_level.upper()}")
        self.lbl_model_tag.setStyleSheet("font-size: 9px; color: #38BDF8; font-weight: 600;")
        status_row.addWidget(self.lbl_model_tag)

        layout.addLayout(status_row)

        # Mini Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Inspect button
        btn_inspect = QPushButton("🔍 Inspect")
        btn_inspect.setFixedHeight(22)
        btn_inspect.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                color: #E5E7EB;
                border: 1px solid #374151;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #374151;
                color: #38BDF8;
                border-color: #38BDF8;
            }
        """)
        btn_inspect.clicked.connect(lambda: self.clicked.emit(self.config.agent_id))
        layout.addWidget(btn_inspect)

    def _apply_styling(self) -> None:
        border_color = "#38BDF8" if self._is_active_stage else "#1F2937"
        bg_color = "#172033" if self._is_active_stage else "#111827"
        self.setStyleSheet(f"""
        QFrame#compact_node_card {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
        QFrame#compact_node_card:hover {{
            border-color: #38BDF8;
            background-color: #1A2338;
        }}
        QLabel#badge_status {{
            background-color: #1F2937;
            color: #9CA3AF;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        QProgressBar {{
            background-color: #1F2937;
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background-color: #38BDF8;
            border-radius: 2px;
        }}
        """)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.config.agent_id)
        super().mousePressEvent(event)

    def update_tags(self, model: str, thinking: str) -> None:
        self.config.model = model
        self.config.thinking_level = thinking
        self.lbl_model_tag.setText(f"{model.split()[0]} · {thinking.upper()}")

    def set_status(self, status: str) -> None:
        palette = {
            "IDLE": ("#1F2937", "#9CA3AF", "● IDLE", False),
            "PLANNING": ("#1E3A8A", "#93C5FD", "● PLANNING", True),
            "THINKING": ("#3B0764", "#E9D5FF", "● THINKING", True),
            "CALLING_TOOL": ("#451A03", "#FDE68A", "⚡ CALLING TOOL", True),
            "PEER_REVIEW": ("#3730A3", "#C7D2FE", "👥 PEER REVIEW", True),
            "COMPLETED": ("#064E3B", "#6EE7B7", "✔ COMPLETED", False),
            "PAUSED": ("#78350F", "#FDE68A", "⏸ PAUSED", False),
            "STOPPED": ("#4C0519", "#FDA4AF", "⏹ STOPPED", False),
            "ERROR": ("#4C0519", "#FDA4AF", "✖ ERROR", False),
        }
        bg, fg, label_text, is_active = palette.get(status, ("#1F2937", "#9CA3AF", f"● {status}", False))
        self._is_active_stage = is_active
        self._apply_styling()

        self.badge_status.setText(label_text)
        self.badge_status.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)

    def update_config(self, new_config: SubAgentConfig) -> None:
        """Update node widget visual attributes when department is switched."""
        self.config = new_config
        self.avatar_pill.setText(new_config.avatar)
        self.lbl_name.setText(new_config.name)
        self.lbl_role.setText(new_config.role.value.split(":")[0])
        self.update_tags(new_config.model, new_config.thinking_level)
        self.set_status("IDLE")
        self.set_progress(0)

