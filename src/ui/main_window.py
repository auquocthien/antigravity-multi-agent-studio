"""MainWindow featuring 3-tab layout: Horizontal Pipeline, Agent Detail Inspector, and Configuration Matrix."""

import os
import subprocess
from typing import Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QTextCursor, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QDialog,
    QFileDialog,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTextBrowser,
    QSplitter,
    QGroupBox,
    QStatusBar,
    QTabWidget,
    QComboBox,
    QGridLayout,
    QScrollArea,
    QCheckBox,
)

from src.core.engine import AgentOrchestrator, StandardMessagePacket, SubAgentConfig, AgyCliBridge, CustomizationDiscovery
from src.core.report_generator import QAReportGenerator
from src.ui.tree_node import CompactAgentNodeWidget


class PipelineLineConnector(QWidget):
    """Draws sleek vector connector lines between pipeline stages without any text arrows."""

    def __init__(self, mode: str = "straight", width: int = 44, height: int = 280, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.mode = mode

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("#38BDF8"))
        pen.setWidth(2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        w = self.width()
        mid_x = w // 2

        if self.mode == "fork":
            # From Leader (0, 140) to mid_x
            painter.drawLine(0, 140, mid_x, 140)
            # Vertical distribution line
            painter.drawLine(mid_x, 60, mid_x, 220)
            # Top branch to Dev 1
            painter.drawLine(mid_x, 60, w, 60)
            # Bottom branch to Dev 2
            painter.drawLine(mid_x, 220, w, 220)
            # Elegant junction dot
            painter.setBrush(QColor("#38BDF8"))
            painter.drawEllipse(mid_x - 3, 140 - 3, 6, 6)

        elif self.mode == "join":
            # Top branch from Dev 1
            painter.drawLine(0, 60, mid_x, 60)
            # Bottom branch from Dev 2
            painter.drawLine(0, 220, mid_x, 220)
            # Vertical collection line
            painter.drawLine(mid_x, 60, mid_x, 220)
            # Out to Reviewer (mid_x to w)
            painter.drawLine(mid_x, 140, w, 140)
            # Junction dot
            painter.setBrush(QColor("#38BDF8"))
            painter.drawEllipse(mid_x - 3, 140 - 3, 6, 6)

        elif self.mode == "straight":
            # Straight horizontal line connecting Reviewer to Tester
            painter.drawLine(0, 140, w, 140)
            painter.setBrush(QColor("#38BDF8"))
            painter.drawEllipse(mid_x - 3, 140 - 3, 6, 6)


class DevsColumnContainer(QWidget):
    """Container for parallel Devs with a vertical connector line."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(195, 280)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#38BDF8"))
        pen.setWidth(2)
        painter.setPen(pen)
        # Vertical connector passing behind peer review badge
        mid_x = self.width() // 2
        painter.drawLine(mid_x, 120, mid_x, 160)


class PersonaEditorDialog(QDialog):
    """Modal dialog to inspect, write, and save an agent's persona markdown file."""

    def __init__(self, config: SubAgentConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(f"Employee Persona Profile - {config.name}")
        self.resize(700, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header info
        header = QHBoxLayout()
        lbl_icon = QLabel(config.avatar)
        lbl_icon.setStyleSheet("font-size: 24px;")
        header.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel(f"<b>{config.name}</b> · {config.role.value}")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #F9FAFB;")
        self.lbl_path = QLabel(f"File: {config.persona_file or 'No file assigned'}")
        self.lbl_path.setStyleSheet("font-size: 11px; color: #94A3B8; font-family: 'JetBrains Mono', monospace;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(self.lbl_path)
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)

        # Markdown editor
        self.editor = QTextEdit()
        self.editor.setObjectName("detail_terminal")
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #0B0F19;
                color: #E2E8F0;
                font-family: "JetBrains Mono", monospace;
                font-size: 12px;
                border: 1px solid #1F2937;
                border-radius: 6px;
                padding: 10px;
            }
            QTextEdit:focus {
                border-color: #38BDF8;
            }
        """)
        self.editor.setPlainText(config.persona_content or config.load_persona() or "")
        layout.addWidget(self.editor)

        # Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save Persona")
        btn_save.setObjectName("btn_dispatch")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #0B0F19;
                font-weight: 700;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        btn_save.clicked.connect(self._save_and_apply)
        btn_bar.addWidget(btn_save)

        layout.addLayout(btn_bar)

    def _save_and_apply(self) -> None:
        content = self.editor.toPlainText().strip()
        self.config.save_persona(content)
        self.accept()


class QAReportDialog(QDialog):
    """Modal dialog displaying the human-readable QA and stability certification report."""

    def __init__(self, report_markdown: str, report_html: str, file_path: str = "", parent=None) -> None:
        super().__init__(parent)
        self.report_markdown = report_markdown
        self.report_html = report_html
        self.file_path = file_path
        self.setWindowTitle("🛡️ QA Verification & Stability Certification Report")
        self.resize(880, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header bar
        header = QHBoxLayout()
        lbl_icon = QLabel("🛡️")
        lbl_icon.setStyleSheet("font-size: 28px;")
        header.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("<b>QA Verification & Stability Report</b> · Audit Sign-off Certificate")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #F9FAFB;")
        self.lbl_path = QLabel(f"File: {self.file_path or 'In-Memory Report'}")
        self.lbl_path.setStyleSheet("font-size: 11px; color: #94A3B8; font-family: 'JetBrains Mono', monospace;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(self.lbl_path)
        header.addLayout(title_box)
        header.addStretch()

        # Badge
        badge = QLabel("VERIFIED 100% PASS")
        badge.setStyleSheet("""
            background-color: #064E3B;
            color: #34D399;
            border: 1px solid #059669;
            border-radius: 6px;
            font-weight: bold;
            font-size: 11px;
            padding: 4px 10px;
        """)
        header.addWidget(badge)
        layout.addLayout(header)

        # Content Viewer (QTextBrowser for styled HTML preview)
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setStyleSheet("""
            QTextBrowser {
                background-color: #0B0F19;
                color: #F8FAFC;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.viewer.setHtml(self.report_html)
        layout.addWidget(self.viewer)

        # Action Buttons
        btn_bar = QHBoxLayout()

        self.btn_toggle_view = QPushButton("🔄 Raw Markdown")
        self.btn_toggle_view.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0F172A;
            }
        """)
        self.btn_toggle_view.clicked.connect(self._toggle_view_mode)
        btn_bar.addWidget(self.btn_toggle_view)
        self.is_raw_view = False

        btn_copy = QPushButton("📋 Copy Markdown")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                color: #F3F4F6;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        btn_copy.clicked.connect(self._copy_markdown)
        btn_bar.addWidget(btn_copy)

        btn_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #0B0F19;
                font-weight: 700;
                border-radius: 6px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def _toggle_view_mode(self) -> None:
        if not self.is_raw_view:
            self.viewer.setPlainText(self.report_markdown)
            self.btn_toggle_view.setText("🔄 Formatted View")
            self.is_raw_view = True
        else:
            self.viewer.setHtml(self.report_html)
            self.btn_toggle_view.setText("🔄 Raw Markdown")
            self.is_raw_view = False

    def _copy_markdown(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.report_markdown)


TAB_THEME_QSS = """
QMainWindow {
    background-color: #0B0F19;
}

QWidget {
    color: #F9FAFB;
    font-family: "Inter", "Ubuntu", "Segoe UI", sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #1F2937;
    background-color: #0F172A;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background-color: #111827;
    color: #9CA3AF;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
    border: 1px solid transparent;
}

QTabBar::tab:selected {
    background-color: #1E293B;
    color: #38BDF8;
    border-top: 1px solid #38BDF8;
    border-bottom: 2px solid #38BDF8;
}

QTabBar::tab:hover:!selected {
    background-color: #1A2338;
    color: #E2E8F0;
}

QGroupBox {
    border: 1px solid #1F2937;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    background-color: #111827;
    font-weight: 700;
    color: #38BDF8;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
}

QLineEdit, QTextEdit, QComboBox {
    background-color: #0B0F19;
    border: 1px solid #1F2937;
    border-radius: 6px;
    padding: 7px 11px;
    color: #F9FAFB;
    font-size: 12px;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #38BDF8;
    background-color: #0F172A;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    border: 1px solid #1F2937;
    selection-background-color: #1E293B;
    selection-color: #38BDF8;
    color: #F9FAFB;
}

QPushButton {
    background-color: #1F2937;
    color: #F9FAFB;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #374151;
    border-color: #4B5563;
}

QPushButton:pressed {
    background-color: #111827;
}

QPushButton#btn_dispatch {
    background-color: #10B981;
    color: #0B0F19;
    border: none;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#btn_dispatch:hover {
    background-color: #059669;
}
QPushButton#btn_dispatch:disabled {
    background-color: #1F2937;
    color: #6B7280;
}

QPushButton#btn_pause {
    background-color: #F59E0B;
    color: #0B0F19;
    border: none;
    font-weight: 700;
}
QPushButton#btn_pause:hover {
    background-color: #D97706;
}
QPushButton#btn_pause:disabled {
    background-color: #1F2937;
    color: #6B7280;
}

QPushButton#btn_stop {
    background-color: #EF4444;
    color: #0B0F19;
    border: none;
    font-weight: 700;
}
QPushButton#btn_stop:hover {
    background-color: #DC2626;
}
QPushButton#btn_stop:disabled {
    background-color: #1F2937;
    color: #6B7280;
}

QTextEdit#bus_terminal, QTextEdit#detail_terminal {
    background-color: #0B0F19;
    color: #E2E8F0;
    font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", monospace;
    font-size: 12px;
    border: 1px solid #1F2937;
    border-radius: 6px;
    padding: 10px;
}

QStatusBar {
    background-color: #0B0F19;
    color: #9CA3AF;
    border-top: 1px solid #1F2937;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #0B0F19;
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #1F2937;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #0284C7;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

AVAILABLE_MODELS = AgyCliBridge.get_available_models()

THINKING_LEVELS = [
    "Low (1k)",
    "Medium (4k)",
    "High (16k)",
    "Max (32k)",
]


class MainWindow(QMainWindow):
    """Refactored Multi-Agent Studio with Horizontal Pipeline, Detail Inspector, and Config Tab."""

    def __init__(self, orchestrator: Optional[AgentOrchestrator] = None) -> None:
        super().__init__()
        self.setWindowTitle("Multi-Agent Real-Time Studio - Horizontal Pipeline & Inspector")
        self.resize(1260, 780)
        self.setMinimumSize(1020, 640)

        self.available_models: List[str] = AVAILABLE_MODELS
        self.orchestrator = orchestrator if orchestrator is not None else AgentOrchestrator(self)
        self.node_widgets: Dict[str, CompactAgentNodeWidget] = {}
        self.pipeline_slots: List[CompactAgentNodeWidget] = []
        self.detail_terminals: Dict[str, QTextEdit] = {}
        self.config_combos: Dict[str, Dict[str, QComboBox]] = {}
        self.config_personas: Dict[str, QLabel] = {}
        self.matrix_row_widgets: List[Dict] = []
        self._is_paused = False

        self._setup_ui()
        self._wire_signals()
        self.setStyleSheet(TAB_THEME_QSS)

    def _setup_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # --- Top Department & Workspace Selector Bar ---
        dept_bar = QFrame()
        dept_bar.setObjectName("dept_bar")
        dept_bar.setStyleSheet("""
            QFrame#dept_bar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111827, stop:1 #1E1B4B);
                border: 1px solid #1F2937;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        dept_layout = QHBoxLayout(dept_bar)
        dept_layout.setContentsMargins(12, 6, 12, 6)
        dept_layout.setSpacing(10)

        lbl_dept_title = QLabel("🏢 <b>Squad:</b>")
        lbl_dept_title.setStyleSheet("font-size: 13px; color: #F9FAFB;")
        dept_layout.addWidget(lbl_dept_title)

        self.combo_department = QComboBox()
        self.combo_department.setFixedHeight(30)
        self.combo_department.setStyleSheet("""
            QComboBox {
                background-color: #0B0F19;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 3px 12px;
                font-weight: 700;
                font-size: 12px;
                min-width: 220px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
        """)

        for dept in self.orchestrator.get_departments():
            self.combo_department.addItem(f"{dept.icon}  {dept.name}", dept.dept_id)

        self.combo_department.currentIndexChanged.connect(self._on_department_switched)
        dept_layout.addWidget(self.combo_department)

        self.lbl_dept_desc = QLabel(self.orchestrator.get_active_department().description)
        self.lbl_dept_desc.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        dept_layout.addWidget(self.lbl_dept_desc, stretch=1)

        root_layout.addWidget(dept_bar)

        # Tab Widget
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        configs = self.orchestrator.get_default_configs()
        self.configs = configs

        # --- Tab 1: Horizontal Pipeline Overview ---
        tab_pipeline = QWidget()
        self._setup_tab_pipeline(tab_pipeline)
        self.tabs.addTab(tab_pipeline, "🌐 Pipeline")

        # --- Tab 2: Agent Detail View ---
        tab_detail = QWidget()
        self._setup_tab_detail(tab_detail)
        self.tabs.addTab(tab_detail, "🔍 Inspector")

        # --- Tab 3: Configuration Page ---
        tab_config = QWidget()
        self._setup_tab_config(tab_config)
        self.tabs.addTab(tab_config, "⚙️ Settings")

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status = QLabel("Ready.")
        self.status_bar.addWidget(self.lbl_status)

    def _setup_tab_pipeline(self, parent: QWidget) -> None:
        """Tab 1: Horizontal Left-to-Right compact pipeline with bus log."""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Quick Control Toolbar Frame
        toolbar = QFrame()
        toolbar.setObjectName("pipeline_toolbar")
        toolbar.setStyleSheet("""
            QFrame#pipeline_toolbar {
                background-color: #111827;
                border: 1px solid #1F2937;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        ctrl_bar = QHBoxLayout(toolbar)
        ctrl_bar.setContentsMargins(10, 8, 10, 8)
        ctrl_bar.setSpacing(10)

        self.btn_dispatch = QPushButton("🚀 Run")
        self.btn_dispatch.setObjectName("btn_dispatch")
        self.btn_dispatch.setFixedHeight(32)
        self.btn_dispatch.clicked.connect(self._handle_dispatch)
        ctrl_bar.addWidget(self.btn_dispatch)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setFixedHeight(32)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._handle_pause)
        ctrl_bar.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setFixedHeight(32)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._handle_stop)
        ctrl_bar.addWidget(self.btn_stop)

        ctrl_bar.addSpacing(12)
        self.lbl_active_prompt = QLabel("Mission: Linux desktop utility")
        self.lbl_active_prompt.setStyleSheet("""
            color: #E2E8F0;
            font-size: 12px;
            background-color: #0B0F19;
            border: 1px solid #1F2937;
            border-radius: 6px;
            padding: 5px 12px;
        """)
        ctrl_bar.addWidget(self.lbl_active_prompt, stretch=1)

        self.btn_mode_toggle = QPushButton("🧪 Simulation")
        self.btn_mode_toggle.setFixedHeight(32)
        self.btn_mode_toggle.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0284C7;
                color: #FFFFFF;
            }
        """)
        self.btn_mode_toggle.clicked.connect(self._toggle_execution_mode)
        ctrl_bar.addWidget(self.btn_mode_toggle)

        has_existing_report = os.path.exists(os.path.join(QAReportGenerator.get_reports_dir(), "qa_report_latest.md"))
        self.btn_view_report = QPushButton("📄 QA Report Ready" if has_existing_report else "📄 View QA Report")
        self.btn_view_report.setFixedHeight(32)
        self.btn_view_report.setObjectName("btn_view_report")
        self.btn_view_report.setStyleSheet("""
            QPushButton#btn_view_report {
                background-color: #065F46;
                color: #A7F3D0;
                border: 1px solid #10B981;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton#btn_view_report:hover {
                background-color: #047857;
                color: #FFFFFF;
            }
            QPushButton#btn_view_report:disabled {
                background-color: #1F2937;
                color: #6B7280;
                border: 1px solid #374151;
            }
        """)
        self.btn_view_report.setEnabled(has_existing_report)
        self.btn_view_report.clicked.connect(self._show_qa_report_dialog)
        ctrl_bar.addWidget(self.btn_view_report)

        btn_go_config = QPushButton("⚙️ Settings")
        btn_go_config.setFixedHeight(32)
        btn_go_config.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        ctrl_bar.addWidget(btn_go_config)

        layout.addWidget(toolbar)

        # Main Splitter: Horizontal Canvas on top, Message Bus below
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)

        # Horizontal Pipeline Canvas (Left to Right)
        h_scroll = QScrollArea()
        h_scroll.setWidgetResizable(True)
        h_scroll.setStyleSheet("QScrollArea { border: 1px solid #1F2937; background-color: #0B0F19; border-radius: 8px; }")

        pipeline_container = QWidget()
        pipeline_container.setStyleSheet("background-color: transparent;")
        pipeline_layout = QHBoxLayout(pipeline_container)
        pipeline_layout.setContentsMargins(20, 20, 20, 20)
        pipeline_layout.setSpacing(0)
        pipeline_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Slot 0: Leader / Creative Director (Stage 1)
        slot_0 = CompactAgentNodeWidget(self.configs[0])
        slot_0.clicked.connect(self._open_agent_detail)
        pipeline_layout.addWidget(slot_0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.pipeline_slots.append(slot_0)
        self.node_widgets[self.configs[0].agent_id] = slot_0

        # Connector 1: Fork Line from Leader to Dev 1 & Dev 2
        connector_fork = PipelineLineConnector(mode="fork", width=46, height=280)
        pipeline_layout.addWidget(connector_fork, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Slot 1 & Slot 2: Parallel Developers (Stage 2: Parallel with peer review)
        devs_column = DevsColumnContainer()
        devs_vbox = QVBoxLayout(devs_column)
        devs_vbox.setContentsMargins(0, 0, 0, 0)
        devs_vbox.setSpacing(8)

        slot_1 = CompactAgentNodeWidget(self.configs[1])
        slot_1.clicked.connect(self._open_agent_detail)
        devs_vbox.addWidget(slot_1)
        self.pipeline_slots.append(slot_1)
        self.node_widgets[self.configs[1].agent_id] = slot_1

        lbl_peer = QLabel("Peer Review")
        lbl_peer.setFixedHeight(24)
        lbl_peer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_peer.setStyleSheet("""
            color: #FDE68A;
            background-color: #451A03;
            border: 1px solid #78350F;
            border-radius: 4px;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
        """)
        devs_vbox.addWidget(lbl_peer)

        slot_2 = CompactAgentNodeWidget(self.configs[2])
        slot_2.clicked.connect(self._open_agent_detail)
        devs_vbox.addWidget(slot_2)
        self.pipeline_slots.append(slot_2)
        self.node_widgets[self.configs[2].agent_id] = slot_2

        pipeline_layout.addWidget(devs_column, alignment=Qt.AlignmentFlag.AlignCenter)

        # Connector 2: Join Line from Dev 1 & Dev 2 to Reviewer
        connector_join = PipelineLineConnector(mode="join", width=46, height=280)
        pipeline_layout.addWidget(connector_join, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Slot 3: Code / Video Reviewer (Stage 3)
        slot_3 = CompactAgentNodeWidget(self.configs[3])
        slot_3.clicked.connect(self._open_agent_detail)
        pipeline_layout.addWidget(slot_3, alignment=Qt.AlignmentFlag.AlignCenter)
        self.pipeline_slots.append(slot_3)
        self.node_widgets[self.configs[3].agent_id] = slot_3

        # Connector 3: Straight Line from Reviewer to Tester
        connector_straight = PipelineLineConnector(mode="straight", width=46, height=280)
        pipeline_layout.addWidget(connector_straight, alignment=Qt.AlignmentFlag.AlignCenter)

        # 4. Slot 4: Runtime Tester / Render QA (Stage 4)
        slot_4 = CompactAgentNodeWidget(self.configs[4])
        slot_4.clicked.connect(self._open_agent_detail)
        pipeline_layout.addWidget(slot_4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.pipeline_slots.append(slot_4)
        self.node_widgets[self.configs[4].agent_id] = slot_4

        h_scroll.setWidget(pipeline_container)
        splitter.addWidget(h_scroll)

        # Message Bus Group
        bus_group = QGroupBox("📡 Message Bus")
        bus_layout = QVBoxLayout(bus_group)
        bus_layout.setContentsMargins(10, 10, 10, 10)
        bus_layout.setSpacing(6)

        self.bus_terminal = QTextEdit()
        self.bus_terminal.setObjectName("bus_terminal")
        self.bus_terminal.setReadOnly(True)
        self.bus_terminal.setPlaceholderText("Communication stream...")
        bus_layout.addWidget(self.bus_terminal)

        splitter.addWidget(bus_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _setup_tab_detail(self, parent: QWidget) -> None:
        """Tab 2: Full-sized Inspector view to examine what each agent is doing."""
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left Column: Agent selector buttons
        selector_group = QGroupBox("Roster")
        selector_layout = QVBoxLayout(selector_group)
        selector_layout.setContentsMargins(10, 12, 10, 10)
        selector_layout.setSpacing(6)

        self.inspector_buttons: List[QPushButton] = []
        self.btn_agent_inspectors: Dict[str, QPushButton] = {}
        for slot_idx in range(5):
            cfg = self.configs[slot_idx] if slot_idx < len(self.configs) else None
            title_text = f"{cfg.avatar}  {cfg.name}" if cfg else f"Slot {slot_idx+1}"
            btn = QPushButton(title_text)
            btn.setFixedHeight(36)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #111827;
                    color: #9CA3AF;
                    border: 1px solid #1F2937;
                    border-left: 3px solid transparent;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1A2338;
                    color: #F9FAFB;
                    border-color: #38BDF8;
                }
            """)
            btn.clicked.connect(lambda _, idx=slot_idx: self._select_inspector_slot(idx))
            self.inspector_buttons.append(btn)
            selector_layout.addWidget(btn)
            if cfg:
                self.btn_agent_inspectors[cfg.agent_id] = btn

        selector_layout.addStretch()
        layout.addWidget(selector_group, stretch=1)

        # Right Column: Detail View for Selected Agent
        detail_group = QGroupBox("Live Inspector")
        detail_vbox = QVBoxLayout(detail_group)
        detail_vbox.setContentsMargins(12, 12, 12, 12)
        detail_vbox.setSpacing(8)

        # Detail header
        info_bar = QHBoxLayout()
        info_bar.setContentsMargins(4, 4, 4, 8)
        self.lbl_detail_avatar = QLabel("👑")
        self.lbl_detail_avatar.setFixedSize(36, 36)
        self.lbl_detail_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_detail_avatar.setStyleSheet(
            "font-size: 20px; background-color: #1E1B4B; border: 1px solid #8B5CF6; border-radius: 8px;"
        )
        info_bar.addWidget(self.lbl_detail_avatar)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_detail_title = QLabel("Leader / Architect")
        self.lbl_detail_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F9FAFB;")
        self.lbl_detail_role = QLabel("Lead Architect")
        self.lbl_detail_role.setStyleSheet("font-size: 11px; color: #9CA3AF;")
        title_vbox.addWidget(self.lbl_detail_title)
        title_vbox.addWidget(self.lbl_detail_role)
        info_bar.addLayout(title_vbox)

        meta_vbox = QVBoxLayout()
        meta_vbox.setSpacing(2)
        self.lbl_detail_skills = QLabel("Skills: [concurrency-safe-engine]")
        self.lbl_detail_skills.setStyleSheet("font-size: 11px; color: #34D399; font-weight: 600;")
        self.lbl_detail_rules = QLabel("Rules: [01-architecture-boundaries.md]")
        self.lbl_detail_rules.setStyleSheet("font-size: 11px; color: #FBBF24; font-weight: 600;")
        meta_vbox.addWidget(self.lbl_detail_skills)
        meta_vbox.addWidget(self.lbl_detail_rules)
        info_bar.addLayout(meta_vbox)

        info_bar.addStretch()

        self.lbl_detail_params = QLabel("Gemini 3.1 Pro · High")
        self.lbl_detail_params.setStyleSheet("""
            font-size: 11px;
            color: #38BDF8;
            font-weight: 700;
            background-color: #0F172A;
            border: 1px solid #1E293B;
            border-radius: 6px;
            padding: 5px 12px;
        """)
        info_bar.addWidget(self.lbl_detail_params)

        btn_view_persona = QPushButton("📜 Persona")
        btn_view_persona.setFixedHeight(28)
        btn_view_persona.clicked.connect(lambda: self._edit_persona(self.current_detail_agent_id))
        info_bar.addWidget(btn_view_persona)

        btn_clear_detail = QPushButton("Clear")
        btn_clear_detail.setFixedHeight(28)
        btn_clear_detail.clicked.connect(self._clear_active_detail_log)
        info_bar.addWidget(btn_clear_detail)

        detail_vbox.addLayout(info_bar)

        # Pre-instantiate Terminals for all departments
        self.current_detail_agent_id = self.configs[0].agent_id
        for dept in self.orchestrator.get_departments():
            for c in self.orchestrator.get_department_configs(dept.dept_id):
                if c.agent_id not in self.detail_terminals:
                    term = QTextEdit()
                    term.setObjectName("detail_terminal")
                    term.setReadOnly(True)
                    term.setPlaceholderText(f"Detailed activity stream for {c.name}...")
                    term.setVisible(c.agent_id == self.current_detail_agent_id)
                    detail_vbox.addWidget(term, stretch=1)
                    self.detail_terminals[c.agent_id] = term

        layout.addWidget(detail_group, stretch=4)

    def _setup_tab_config(self, parent: QWidget) -> None:
        """Tab 3: Configuration page for Customizations, Prompt, Models, and Thinking Levels."""
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        outer_layout = QVBoxLayout(parent)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Customization Architecture Status Box
        custom_group = QGroupBox("Customizations (.agent & Global)")
        custom_layout = QHBoxLayout(custom_group)
        custom_layout.setContentsMargins(14, 12, 14, 12)
        custom_layout.setSpacing(14)

        rules_discovered = CustomizationDiscovery.discover_rules()
        skills_discovered = CustomizationDiscovery.discover_skills()

        lbl_ws_status = QLabel(
            f"<b>📁 Workspace:</b> {len(rules_discovered['workspace'])} Rules · {len(skills_discovered['workspace'])} Skills"
        )
        lbl_ws_status.setStyleSheet("color: #38BDF8; font-size: 12px;")
        custom_layout.addWidget(lbl_ws_status)

        lbl_gl_status = QLabel(
            f"<b>🌐 Global:</b> {len(rules_discovered['global'])} Rules · {len(skills_discovered['global'])} Skills"
        )
        lbl_gl_status.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        custom_layout.addWidget(lbl_gl_status)

        custom_layout.addStretch()

        btn_open_agent = QPushButton("📂 Open .agent")
        btn_open_agent.setFixedHeight(28)
        btn_open_agent.clicked.connect(self._open_agent_folder)
        custom_layout.addWidget(btn_open_agent)

        layout.addWidget(custom_group)

        # Mission Prompt Box
        prompt_group = QGroupBox("Mission Prompt")
        prompt_vbox = QVBoxLayout(prompt_group)
        prompt_vbox.setContentsMargins(14, 12, 14, 12)
        prompt_vbox.setSpacing(8)

        self.edit_prompt = QLineEdit()
        self.edit_prompt.setFixedHeight(36)
        self.edit_prompt.setText(self.orchestrator.get_active_department().default_prompt)
        prompt_vbox.addWidget(self.edit_prompt)
        layout.addWidget(prompt_group)

        # Agent Configuration Matrix Box
        matrix_group = QGroupBox("Agent Matrix (Model & Thinking Allocations)")
        matrix_layout = QGridLayout(matrix_group)
        matrix_layout.setContentsMargins(16, 16, 16, 16)
        matrix_layout.setSpacing(12)

        # Column stretch factors for optimal alignment
        matrix_layout.setColumnStretch(0, 3)  # Agent Role / Name
        matrix_layout.setColumnStretch(1, 3)  # LLM Model Selector
        matrix_layout.setColumnStretch(2, 2)  # Budget / Thinking Level
        matrix_layout.setColumnStretch(3, 3)  # Persona file & Actions

        # Headers
        headers = ["Agent", "Model", "Budget", "Persona (.md)"]
        matrix_layout.setRowMinimumHeight(0, 26)
        for col, h in enumerate(headers):
            lbl_h = QLabel(h)
            lbl_h.setStyleSheet("font-weight: 700; color: #38BDF8; font-size: 12px; padding-bottom: 6px; border-bottom: 2px solid #1E293B;")
            matrix_layout.addWidget(lbl_h, 0, col)

        self.matrix_row_widgets = []
        for row_idx in range(5):
            matrix_layout.setRowMinimumHeight(row_idx + 1, 42)

            lbl_agent = QLabel(f"Slot {row_idx + 1}")
            lbl_agent.setStyleSheet("font-size: 12px; font-weight: 600; color: #F9FAFB;")
            matrix_layout.addWidget(lbl_agent, row_idx + 1, 0)

            combo_model = QComboBox()
            combo_model.setFixedHeight(34)
            combo_model.addItems(self.available_models)
            combo_model.currentIndexChanged.connect(lambda _, idx=row_idx: self._sync_config_slot(idx))

            combo_thinking = QComboBox()
            combo_thinking.setFixedHeight(34)
            combo_thinking.addItems(THINKING_LEVELS)
            combo_thinking.currentIndexChanged.connect(lambda _, idx=row_idx: self._sync_config_slot(idx))

            matrix_layout.addWidget(combo_model, row_idx + 1, 1)
            matrix_layout.addWidget(combo_thinking, row_idx + 1, 2)

            persona_col = QWidget()
            persona_col.setFixedHeight(34)
            persona_box = QHBoxLayout(persona_col)
            persona_box.setContentsMargins(0, 0, 0, 0)
            persona_box.setSpacing(6)

            lbl_persona = QLabel("📄 Persona")
            lbl_persona.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 500;")
            persona_box.addWidget(lbl_persona, stretch=1)

            btn_browse = QPushButton("📂 Browse")
            btn_browse.setFixedHeight(28)
            btn_browse.setStyleSheet("""
                QPushButton {
                    background-color: #1F2937;
                    color: #9CA3AF;
                    border: 1px solid #374151;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #374151;
                    color: #F9FAFB;
                    border-color: #4B5563;
                }
            """)
            btn_browse.clicked.connect(lambda _, idx=row_idx: self._browse_persona_slot(idx))
            persona_box.addWidget(btn_browse)

            btn_edit = QPushButton("✏️ Edit")
            btn_edit.setFixedHeight(28)
            btn_edit.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #38BDF8;
                    border: 1px solid #0284C7;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #0284C7;
                    color: #FFFFFF;
                }
            """)
            btn_edit.clicked.connect(lambda _, idx=row_idx: self._edit_persona_slot(idx))
            persona_box.addWidget(btn_edit)

            matrix_layout.addWidget(persona_col, row_idx + 1, 3)

            self.matrix_row_widgets.append({
                "lbl_agent": lbl_agent,
                "combo_model": combo_model,
                "combo_thinking": combo_thinking,
                "lbl_persona": lbl_persona,
                "btn_browse": btn_browse,
                "btn_edit": btn_edit
            })

        self._rebind_tab_config()
        layout.addWidget(matrix_group)

        # Telegram Remote Operations & Push Notifications Box
        tele_group = QGroupBox("📱 Telegram Remote Ops & Push Notifications")
        tele_layout = QVBoxLayout(tele_group)
        tele_layout.setContentsMargins(14, 12, 14, 12)
        tele_layout.setSpacing(10)

        # Row 1: Enable checkbox and Status indicator
        row1 = QHBoxLayout()
        self.chk_tele_enabled = QCheckBox("Enable Telegram Notifications & Remote Control")
        self.chk_tele_enabled.setStyleSheet("font-weight: 600; color: #F9FAFB; font-size: 12px;")
        self.chk_tele_enabled.setChecked(self.orchestrator.telegram_config.enabled)
        row1.addWidget(self.chk_tele_enabled)
        row1.addStretch()

        is_connected = self.orchestrator.telegram_config.enabled and self.orchestrator.telegram_config.bot_token
        self.lbl_tele_status = QLabel("Status: Active & Polling" if is_connected else "Status: Disabled")
        self.lbl_tele_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;" if is_connected else "color: #94A3B8; font-size: 11px;")
        row1.addWidget(self.lbl_tele_status)
        tele_layout.addLayout(row1)

        # Row 2: Inputs for Bot Token and Chat ID
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        token_box = QVBoxLayout()
        token_box.setSpacing(4)
        lbl_tok = QLabel("Bot Token (@BotFather):")
        lbl_tok.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.edit_tele_token = QLineEdit()
        self.edit_tele_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_tele_token.setPlaceholderText("e.g. 7182938472:AAFlw91kL8kZ9Q...")
        self.edit_tele_token.setText(self.orchestrator.telegram_config.bot_token)
        token_box.addWidget(lbl_tok)
        token_box.addWidget(self.edit_tele_token)
        row2.addLayout(token_box, stretch=3)

        chat_box = QVBoxLayout()
        chat_box.setSpacing(4)
        lbl_chat = QLabel("Chat ID (@userinfobot):")
        lbl_chat.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.edit_tele_chat_id = QLineEdit()
        self.edit_tele_chat_id.setPlaceholderText("e.g. 123456789")
        self.edit_tele_chat_id.setText(self.orchestrator.telegram_config.chat_id)
        chat_box.addWidget(lbl_chat)
        chat_box.addWidget(self.edit_tele_chat_id)
        row2.addLayout(chat_box, stretch=2)

        tele_layout.addLayout(row2)

        # Row 3: Action buttons
        row3 = QHBoxLayout()
        row3.setSpacing(10)

        self.btn_tele_test = QPushButton("🧪 Test Connection")
        self.btn_tele_test.setFixedHeight(30)
        self.btn_tele_test.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0F172A;
            }
        """)
        self.btn_tele_test.clicked.connect(self._test_telegram_connection)
        row3.addWidget(self.btn_tele_test)

        self.btn_tele_save = QPushButton("💾 Save & Connect")
        self.btn_tele_save.setFixedHeight(30)
        self.btn_tele_save.setStyleSheet("""
            QPushButton {
                background-color: #065F46;
                color: #A7F3D0;
                border: 1px solid #10B981;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #FFFFFF;
            }
        """)
        self.btn_tele_save.clicked.connect(self._save_telegram_settings)
        row3.addWidget(self.btn_tele_save)

        row3.addStretch()
        tele_layout.addLayout(row3)

        layout.addWidget(tele_group)

        # History and Action Buttons
        btn_box = QHBoxLayout()
        btn_apply = QPushButton("💾 Apply & Back")
        btn_apply.setObjectName("btn_dispatch")
        btn_apply.setFixedHeight(34)
        btn_apply.clicked.connect(self._apply_config_and_return)
        btn_box.addWidget(btn_apply)

        btn_hist = QPushButton("📁 History")
        btn_hist.setFixedHeight(34)
        btn_hist.clicked.connect(self._open_history_folder)
        btn_box.addWidget(btn_hist)
        btn_box.addStretch()

        layout.addLayout(btn_box)
        layout.addStretch()

    def _rebind_tab_config(self) -> None:
        """Update Tab 3 labels and combo bindings for active department."""
        self.config_combos.clear()
        self.config_personas.clear()

        for idx, cfg in enumerate(self.configs):
            if idx >= len(self.matrix_row_widgets):
                break
            w = self.matrix_row_widgets[idx]
            w["lbl_agent"].setText(f"{cfg.avatar}  <b>{cfg.name}</b> <span style='color: #9CA3AF;'>({cfg.role.value.split(':')[0]})</span>")

            w["combo_model"].blockSignals(True)
            w["combo_thinking"].blockSignals(True)

            matched_model = next((m for m in self.available_models if cfg.model.lower() in m.lower()), None)
            if not matched_model:
                matched_model = self.available_models[0]
            w["combo_model"].setCurrentText(matched_model)
            cfg.model = matched_model

            if cfg.thinking_level == "high":
                w["combo_thinking"].setCurrentText("High (16k)")
            elif cfg.thinking_level == "low":
                w["combo_thinking"].setCurrentText("Low (1k)")
            else:
                w["combo_thinking"].setCurrentText("Medium (4k)")

            w["combo_model"].blockSignals(False)
            w["combo_thinking"].blockSignals(False)

            persona_display_name = os.path.basename(cfg.persona_file) if cfg.persona_file else "Default"
            w["lbl_persona"].setText(f"📄 {persona_display_name}")
            w["lbl_persona"].setToolTip(cfg.persona_file if cfg.persona_file else "No custom persona loaded")

            self.config_combos[cfg.agent_id] = {
                "model": w["combo_model"],
                "thinking": w["combo_thinking"]
            }
            self.config_personas[cfg.agent_id] = w["lbl_persona"]

    def _on_department_switched(self, index: int) -> None:
        """Handle switching between Software Engineering and Video Production squads."""
        dept_id = self.combo_department.currentData()
        if not dept_id:
            return

        self.orchestrator.set_active_department(dept_id)
        dept = self.orchestrator.get_active_department()
        self.configs = self.orchestrator.get_department_configs(dept_id)
        self.lbl_dept_desc.setText(dept.description)

        # Update Mission Prompt
        self.edit_prompt.setText(dept.default_prompt)
        self.lbl_active_prompt.setText(f"Mission: {dept.default_prompt[:45]}...")

        # Rebind Tab 1 Pipeline Slots
        self.node_widgets.clear()
        for i, cfg in enumerate(self.configs):
            if i < len(self.pipeline_slots):
                slot = self.pipeline_slots[i]
                slot.update_config(cfg)
                slot.set_status("IDLE")
                slot.set_progress(0)
                self.node_widgets[cfg.agent_id] = slot

        # Rebind Tab 2 Inspector Buttons
        self.btn_agent_inspectors.clear()
        for i, cfg in enumerate(self.configs):
            if i < len(self.inspector_buttons):
                btn = self.inspector_buttons[i]
                btn.setText(f"{cfg.avatar}  {cfg.name}")
                self.btn_agent_inspectors[cfg.agent_id] = btn

        # Select first agent in department
        if self.configs:
            self._select_detail_agent(self.configs[0].agent_id)

        # Rebind Tab 3 Configuration Matrix
        self._rebind_tab_config()

        self.lbl_status.setText(f"Active Squad: {dept.name}")

    def _select_inspector_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < len(self.configs):
            self._select_detail_agent(self.configs[slot_idx].agent_id)

    def _sync_config_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < len(self.configs):
            self._sync_config(self.configs[slot_idx].agent_id)

    def _browse_persona_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < len(self.configs):
            self._browse_persona(self.configs[slot_idx].agent_id)

    def _edit_persona_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < len(self.configs):
            self._edit_persona(self.configs[slot_idx].agent_id)

    def _browse_persona(self, agent_id: str) -> None:
        """Browse and load an external employee persona markdown file."""
        cfg = next((c for c in self.configs if c.agent_id == agent_id), None)
        if not cfg:
            return
        base_dir = os.path.dirname(cfg.persona_file) if (cfg.persona_file and os.path.exists(cfg.persona_file)) else os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Persona Profile (.md) for {cfg.name}",
            base_dir,
            "Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            cfg.persona_file = file_path
            cfg.load_persona()
            if agent_id in self.config_personas:
                self.config_personas[agent_id].setText(f"📄 {os.path.basename(file_path)}")
                self.config_personas[agent_id].setToolTip(file_path)
            self.lbl_status.setText(f"Loaded persona for {cfg.name}")

    def _edit_persona(self, agent_id: str) -> None:
        """Open in-app Markdown dialog to edit and update employee persona prompt."""
        cfg = next((c for c in self.configs if c.agent_id == agent_id), None)
        if not cfg:
            return
        dialog = PersonaEditorDialog(cfg, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if agent_id in self.config_personas:
                self.config_personas[agent_id].setText(f"📄 {os.path.basename(cfg.persona_file) if cfg.persona_file else 'Custom'}")
                if cfg.persona_file:
                    self.config_personas[agent_id].setToolTip(cfg.persona_file)
            self.lbl_status.setText(f"Updated persona for {cfg.name}")

    def _sync_config(self, agent_id: str) -> None:
        """Sync updated model or thinking from config tab into node card and engine."""
        combos = self.config_combos.get(agent_id)
        if not combos:
            return
        new_model = combos["model"].currentText()
        raw_thinking = combos["thinking"].currentText()
        new_thinking = "low" if "Low" in raw_thinking else (
            "high" if "High" in raw_thinking else ("max" if "Max" in raw_thinking else "medium")
        )

        if agent_id in self.node_widgets:
            self.node_widgets[agent_id].update_tags(new_model, new_thinking)
        self.orchestrator.update_agent_params(agent_id, new_model, new_thinking)

    def _apply_config_and_return(self) -> None:
        prompt_text = self.edit_prompt.text().strip()
        self.lbl_active_prompt.setText(f"Mission: {prompt_text[:45]}...")
        self.tabs.setCurrentIndex(0)

    def _open_agent_detail(self, agent_id: str) -> None:
        """Switch to Tab 2 and inspect the clicked agent."""
        self.tabs.setCurrentIndex(1)
        self._select_detail_agent(agent_id)

    def _select_detail_agent(self, agent_id: str) -> None:
        self.current_detail_agent_id = agent_id
        cfg_map = {c.agent_id: c for c in self.configs}
        cfg = cfg_map.get(agent_id)
        if cfg:
            self.lbl_detail_avatar.setText(cfg.avatar)
            self.lbl_detail_title.setText(cfg.name)
            self.lbl_detail_role.setText(cfg.role.value)
            effort_tag = cfg.thinking_level.capitalize()
            model_short = cfg.model.split("(")[0].strip()
            self.lbl_detail_params.setText(f"{model_short} · {effort_tag}")
            skills_str = ", ".join(cfg.skills) if cfg.skills else "Standard"
            rules_str = ", ".join(cfg.rules) if cfg.rules else "Standard"
            self.lbl_detail_skills.setText(f"Skills: [{skills_str}]")
            self.lbl_detail_rules.setText(f"Rules: [{rules_str}]")

        for a_id, term in self.detail_terminals.items():
            term.setVisible(a_id == agent_id)

        # Highlight active button
        for a_id, btn in self.btn_agent_inspectors.items():
            if a_id == agent_id:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1E293B;
                        color: #38BDF8;
                        border: 1px solid #38BDF8;
                        border-left: 4px solid #38BDF8;
                        border-radius: 6px;
                        text-align: left;
                        padding-left: 12px;
                        font-size: 11px;
                        font-weight: 700;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #111827;
                        color: #9CA3AF;
                        border: 1px solid #1F2937;
                        border-left: 3px solid transparent;
                        border-radius: 6px;
                        text-align: left;
                        padding-left: 12px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #1A2338;
                        color: #F9FAFB;
                        border-color: #38BDF8;
                    }
                """)

    def _clear_active_detail_log(self) -> None:
        if self.current_detail_agent_id in self.detail_terminals:
            self.detail_terminals[self.current_detail_agent_id].clear()

    def _wire_signals(self) -> None:
        self.orchestrator.token_stream_forwarded.connect(self._on_token_stream)
        self.orchestrator.status_forwarded.connect(self._on_agent_status)
        self.orchestrator.progress_forwarded.connect(self._on_agent_progress)
        self.orchestrator.message_bus_forwarded.connect(self._on_message_packet)
        self.orchestrator.pipeline_finished.connect(self._on_pipeline_finished)
        self.orchestrator.subordinate_adjusted.connect(self._on_subordinate_adjusted)
        self.orchestrator.qa_report_ready.connect(self._on_qa_report_ready)
        self.orchestrator.remote_command_dispatched.connect(self._on_remote_command_received)

    def _handle_dispatch(self) -> None:
        prompt = self.edit_prompt.text().strip()
        if not prompt:
            return

        for node in self.node_widgets.values():
            node.set_progress(0)
            node.set_status("IDLE")

        for term in self.detail_terminals.values():
            term.clear()

        self.bus_terminal.clear()
        self.btn_dispatch.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_stop.setEnabled(True)
        self._is_paused = False

        self.lbl_status.setText("Running: Stage 1 (Architect)...")
        self.orchestrator.dispatch_hierarchical_pipeline(prompt)

    def _handle_pause(self) -> None:
        if not self._is_paused:
            self.orchestrator.pause_all()
            self._is_paused = True
            self.btn_pause.setText("Resume")
            self.lbl_status.setText("Pipeline paused.")
        else:
            self.orchestrator.resume_all()
            self._is_paused = False
            self.btn_pause.setText("Pause")
            self.lbl_status.setText("Pipeline resumed.")

    def _handle_stop(self) -> None:
        self.orchestrator.stop_all()
        self.btn_dispatch.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("Pause")
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Pipeline stopped.")

    def _on_token_stream(self, agent_id: str, stream_type: str, chunk: str) -> None:
        # Stream into detail view terminal
        if agent_id in self.detail_terminals:
            term = self.detail_terminals[agent_id]
            cursor = term.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)

            color_map = {
                "CLI_CMD": "#4ADE80",
                "THOUGHT": "#C084FC",
                "TOOL": "#FCD34D",
                "OUTPUT": "#38BDF8",
                "MESSAGE": "#2DD4BF",
                "SYSTEM": "#FB923C",
            }
            color = color_map.get(stream_type, "#E2E8F0")
            formatted = chunk.replace("\n", "<br/>").replace(" ", "&nbsp;")
            cursor.insertHtml(f"<span style='color: {color};'>{formatted}</span>")
            term.setTextCursor(cursor)
            term.ensureCursorVisible()

    def _on_agent_status(self, agent_id: str, state_name: str) -> None:
        if agent_id in self.node_widgets:
            self.node_widgets[agent_id].set_status(state_name)

    def _on_agent_progress(self, agent_id: str, percent: int) -> None:
        if agent_id in self.node_widgets:
            self.node_widgets[agent_id].set_progress(percent)

    def _on_subordinate_adjusted(self, agent_id: str, new_model: str, new_effort: str) -> None:
        if agent_id in self.node_widgets:
            self.node_widgets[agent_id].update_tags(new_model, new_effort)
        if agent_id in self.config_combos:
            self.config_combos[agent_id]["model"].setCurrentText(new_model)
            self.config_combos[agent_id]["thinking"].setCurrentText(
                "High (16k)" if new_effort == "high" else "Medium (4k)"
            )

    def _on_message_packet(self, packet: StandardMessagePacket) -> None:
        ts = packet.timestamp.split("T")[1][:8]
        intent_color_map = {
            "TASK_DISPATCH": "#38BDF8",
            "PEER_REVIEW_REQUEST": "#F59E0B",
            "BUG_REPORT": "#EF4444",
            "APPROVAL_NOTICE": "#10B981",
        }
        color = intent_color_map.get(packet.intent, "#E2E8F0")

        html = (
            f"<div style='margin-bottom: 6px; padding: 6px 10px; border-left: 3px solid {color}; background-color: #111827; border-radius: 4px;'>"
            f"<span style='color: #64748B; font-weight: 600;'>[{ts}]</span> "
            f"<b style='color: {color};'>[{packet.intent}]</b> "
            f"<b style='color: #F9FAFB;'>{packet.from_agent}</b> &rarr; <b style='color: #F9FAFB;'>{packet.to_agent}</b> "
            f"<span style='color: #94A3B8; font-size: 11px;'>[Model: {packet.model} · Effort: {packet.effort}]</span><br/>"
            f"<span style='color: #CBD5E1;'>&bull; {packet.payload}</span>"
            f"</div>"
        )
        self.bus_terminal.append(html)
        self.bus_terminal.moveCursor(QTextCursor.MoveOperation.End)

    def _on_pipeline_finished(self, success: bool, summary: str) -> None:
        self.btn_dispatch.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("Pause")
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText(summary)

    def _toggle_execution_mode(self) -> None:
        """Switch between Simulation mode and Live CLI mode."""
        if self.orchestrator.execution_mode == "simulation":
            self.orchestrator.set_execution_mode("live_cli")
            self.btn_mode_toggle.setText("⚡ Live CLI")
            self.btn_mode_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #7C3AED;
                    color: #FFFFFF;
                    border: 1px solid #A78BFA;
                    border-radius: 6px;
                    padding: 0 12px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #6D28D9;
                }
            """)
            self.lbl_status.setText("Mode: Live CLI")
        else:
            self.orchestrator.set_execution_mode("simulation")
            self.btn_mode_toggle.setText("🧪 Simulation")
            self.btn_mode_toggle.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #38BDF8;
                    border: 1px solid #0284C7;
                    border-radius: 6px;
                    padding: 0 12px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #0284C7;
                    color: #FFFFFF;
                }
            """)
            self.lbl_status.setText("Mode: Simulation")

    def _open_agent_folder(self) -> None:
        """Open the .agent directory in Linux file manager."""
        agent_dir = CustomizationDiscovery.get_workspace_agent_dir()
        if os.path.exists(agent_dir):
            subprocess.Popen(["xdg-open", agent_dir], start_new_session=True)

    def _open_history_folder(self) -> None:
        hist_dir = self.orchestrator.logger.base_dir
        if os.path.exists(hist_dir):
            subprocess.Popen(["xdg-open", hist_dir], start_new_session=True)

    def _on_qa_report_ready(self, dept_id: str, report_path: str, markdown_content: str) -> None:
        """Handle incoming QA report certificate and enable view button."""
        self.btn_view_report.setEnabled(True)
        self.btn_view_report.setText("📄 QA Report Ready")
        self.btn_view_report.setStyleSheet("""
            QPushButton#btn_view_report {
                background-color: #059669;
                color: #FFFFFF;
                border: 2px solid #34D399;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton#btn_view_report:hover {
                background-color: #047857;
            }
        """)
        self.lbl_status.setText(f"QA Certificate: {os.path.basename(report_path)}")

    def _show_qa_report_dialog(self) -> None:
        """Opens modal QA Verification Report Dialog."""
        reports_dir = QAReportGenerator.get_reports_dir()
        latest_file = os.path.join(reports_dir, "qa_report_latest.md")

        markdown_text = ""
        file_path = latest_file
        if self.orchestrator.latest_report_data:
            markdown_text = self.orchestrator.latest_report_data.get("markdown", "")
            file_path = self.orchestrator.latest_report_data.get("file_path", latest_file)
        elif os.path.exists(latest_file):
            try:
                with open(latest_file, "r", encoding="utf-8") as f:
                    markdown_text = f.read()
            except OSError:
                pass

        if not markdown_text:
            # Baseline report if none has executed yet
            dept = self.orchestrator.get_active_department()
            if dept.dept_id == "dept_video":
                data = QAReportGenerator.generate_video_report(
                    task_prompt=self.lbl_active_prompt.text(),
                    model="Gemini 3.8 Flash"
                )
            else:
                data = QAReportGenerator.generate_dev_report(
                    task_prompt=self.lbl_active_prompt.text(),
                    model="Gemini 3.8 Flash"
                )
            markdown_text = data["markdown"]
            file_path = data["file_path"]

        html_text = QAReportGenerator.markdown_to_html(markdown_text)
        dialog = QAReportDialog(markdown_text, html_text, file_path, self)
        dialog.exec()

    def _test_telegram_connection(self) -> None:
        """Tests the Telegram Bot Token and connection."""
        token = self.edit_tele_token.text().strip()
        chat_id = self.edit_tele_chat_id.text().strip()
        try:
            from src.core.telegram_notifier import TelegramConfig, TelegramNotifier
        except ImportError:
            from .telegram_notifier import TelegramConfig, TelegramNotifier

        cfg = TelegramConfig(bot_token=token, chat_id=chat_id, enabled=True)
        notifier = TelegramNotifier(cfg)
        ok, msg = notifier.test_connection()
        if ok:
            if chat_id:
                notifier.send_message("🧪 <b>Antigravity Studio</b>: Telegram connection test successful! Ready to receive notifications and commands.")
            self.lbl_tele_status.setText(f"Status: {msg}")
            self.lbl_tele_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;")
            self.lbl_status.setText(f"Telegram verified: {msg}")
        else:
            self.lbl_tele_status.setText(f"Status: {msg}")
            self.lbl_tele_status.setStyleSheet("color: #F87171; font-size: 11px; font-weight: bold;")
            self.lbl_status.setText(f"Telegram test failed: {msg}")

    def _save_telegram_settings(self) -> None:
        """Saves Telegram configuration and updates background bridge."""
        token = self.edit_tele_token.text().strip()
        chat_id = self.edit_tele_chat_id.text().strip()
        enabled = self.chk_tele_enabled.isChecked()

        ok = self.orchestrator.update_telegram_settings(token, chat_id, enabled)
        if ok:
            status_text = "Status: Active & Polling" if enabled and token and chat_id else "Status: Saved (Disabled)"
            self.lbl_tele_status.setText(status_text)
            self.lbl_tele_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;" if enabled else "color: #94A3B8; font-size: 11px;")
            self.lbl_status.setText("Telegram configuration saved to .agent/telegram_config.json")
        else:
            self.lbl_status.setText("Failed to save Telegram configuration.")

    def _on_remote_command_received(self, action: str, payload: str, user_name: str) -> None:
        """Handle UI notification when mobile command arrives."""
        if action == "PROMPT":
            self.lbl_status.setText(f"Remote Mission from {user_name}: {payload}")
            self.edit_prompt.setText(payload)
            self.lbl_active_prompt.setText(f"Mission: {payload}")
        elif action == "ACCEPT":
            self.lbl_status.setText(f"Remote Approval from {user_name} on Telegram.")
        elif action == "REJECT":
            self.lbl_status.setText(f"Remote Rejection from {user_name} on Telegram.")

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self.orchestrator, "telegram_bridge"):
            self.orchestrator.telegram_bridge.stop_polling()
        self.orchestrator.stop_all()
        event.accept()
