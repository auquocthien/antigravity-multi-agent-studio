"""MainWindow featuring 3-tab layout: Horizontal Pipeline, Agent Detail Inspector, and Configuration Matrix."""

import os
import subprocess
from typing import Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QTextCursor, QPainter, QPen, QColor, QWheelEvent
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
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from src.core.engine import AgentOrchestrator, StandardMessagePacket, SubAgentConfig, AgyCliBridge, CustomizationDiscovery
from src.core.cli_engine import CliRegistry, AgyInstance2Config, AgyInstance2CliBridge
from src.core.report_generator import QAReportGenerator
from src.ui.tree_node import CompactAgentNodeWidget


class ClickOnlyComboBox(QComboBox):
    """Custom QComboBox that responds only to click events for opening and selection.
    Ignores mouse wheel and touchpad scroll events when the dropdown is closed,
    allowing smooth page scrolling without accidentally changing dropdown values."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Ignore mouse wheel / touchpad scroll so it propagates to parent scroll areas
        event.ignore()


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
    left: 12px;
    padding: 2px 8px;
    background-color: #111827;
    border-radius: 4px;
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

        self.combo_department = ClickOnlyComboBox()
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

        # --- Tab 4: Usage & System Resource Monitor ---
        tab_usage = QWidget()
        self._setup_tab_usage(tab_usage)
        self.tabs.addTab(tab_usage, "📊 Usage")

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

        self.btn_resume = QPushButton("▶️ Resume")
        self.btn_resume.setObjectName("btn_resume")
        self.btn_resume.setFixedHeight(32)
        self.btn_resume.setEnabled(False)
        self.btn_resume.setStyleSheet("""
            QPushButton#btn_resume {
                background-color: #4338CA;
                color: #FFFFFF;
                border: 1px solid #6366F1;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton#btn_resume:hover {
                background-color: #4F46E5;
            }
            QPushButton#btn_resume:disabled {
                background-color: #1F2937;
                color: #6B7280;
                border-color: #374151;
            }
        """)
        self.btn_resume.clicked.connect(self._handle_resume)
        ctrl_bar.addWidget(self.btn_resume)

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
        matrix_layout.setColumnStretch(1, 2)  # CLI Engine Selector
        matrix_layout.setColumnStretch(2, 3)  # LLM Model Selector
        matrix_layout.setColumnStretch(3, 2)  # Budget / Thinking Level
        matrix_layout.setColumnStretch(4, 3)  # Persona file & Actions

        # Headers
        headers = ["Agent", "CLI Engine", "Model", "Budget", "Persona (.md)"]
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

            combo_engine = ClickOnlyComboBox()
            combo_engine.setFixedHeight(34)
            combo_engine.addItem("⚡ agy", "agy")
            combo_engine.addItem("🚀 agy_2", "agy_instance_2")
            combo_engine.addItem("🦙 ollama", "ollama")
            combo_engine.addItem("🔧 custom", "custom")
            combo_engine.currentIndexChanged.connect(lambda _, idx=row_idx: self._on_engine_changed(idx))

            combo_model = ClickOnlyComboBox()
            combo_model.setFixedHeight(34)
            combo_model.addItems(self.available_models)
            combo_model.currentIndexChanged.connect(lambda _, idx=row_idx: self._sync_config_slot(idx))

            combo_thinking = ClickOnlyComboBox()
            combo_thinking.setFixedHeight(34)
            combo_thinking.addItems(THINKING_LEVELS)
            combo_thinking.currentIndexChanged.connect(lambda _, idx=row_idx: self._sync_config_slot(idx))

            matrix_layout.addWidget(combo_engine, row_idx + 1, 1)
            matrix_layout.addWidget(combo_model, row_idx + 1, 2)
            matrix_layout.addWidget(combo_thinking, row_idx + 1, 3)

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

            matrix_layout.addWidget(persona_col, row_idx + 1, 4)

            self.matrix_row_widgets.append({
                "lbl_agent": lbl_agent,
                "combo_engine": combo_engine,
                "combo_model": combo_model,
                "combo_thinking": combo_thinking,
                "lbl_persona": lbl_persona,
                "btn_browse": btn_browse,
                "btn_edit": btn_edit
            })

        self._rebind_tab_config()
        layout.addWidget(matrix_group)

        # Failover Strategy Box
        failover_group = QGroupBox("🔄 Multi-CLI Failover & Recovery Strategy")
        failover_layout = QHBoxLayout(failover_group)
        failover_layout.setContentsMargins(14, 12, 14, 12)
        failover_layout.setSpacing(12)

        self.chk_auto_failover = QCheckBox("Automated Failover: Switch to Secondary CLI upon Rate Limit / Quota Exceeded (429)")
        self.chk_auto_failover.setStyleSheet("font-weight: 600; color: #38BDF8; font-size: 12px;")
        self.chk_auto_failover.setChecked(self.orchestrator.auto_failover_enabled)
        self.chk_auto_failover.toggled.connect(self._on_toggle_failover)
        failover_layout.addWidget(self.chk_auto_failover)
        failover_layout.addStretch()

        layout.addWidget(failover_group)

        # Antigravity CLI Instance 2 (Isolated Account & Profile) Box
        inst2_bridge = CliRegistry.get_bridge("agy_instance_2")
        inst2_cfg = getattr(inst2_bridge, "config", None) or AgyInstance2Config.load()

        inst2_group = QGroupBox("🚀 Antigravity CLI Instance 2 (Isolated Account & Profile)")
        inst2_layout = QVBoxLayout(inst2_group)
        inst2_layout.setContentsMargins(14, 12, 14, 12)
        inst2_layout.setSpacing(10)

        # Row 1: Profile Directory and Auth Status
        i2_row1 = QHBoxLayout()
        lbl_p_title = QLabel("Profile Directory:")
        lbl_p_title.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.lbl_inst2_profile = QLabel(inst2_cfg.profile_dir)
        self.lbl_inst2_profile.setStyleSheet("color: #38BDF8; font-size: 11px; font-family: monospace; font-weight: 600;")
        i2_row1.addWidget(lbl_p_title)
        i2_row1.addWidget(self.lbl_inst2_profile)
        i2_row1.addStretch()

        is_auth = inst2_bridge.is_authenticated() if hasattr(inst2_bridge, "is_authenticated") else False
        self.lbl_inst2_status = QLabel("● Authenticated" if is_auth else "● Authentication Required")
        self.lbl_inst2_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;" if is_auth else "color: #F59E0B; font-size: 11px; font-weight: bold;")
        i2_row1.addWidget(self.lbl_inst2_status)
        inst2_layout.addLayout(i2_row1)

        # Row 2: API Key input & Terminal OAuth Login button
        i2_row2 = QHBoxLayout()
        i2_row2.setSpacing(10)

        lbl_api_key = QLabel("Gemini API Key (Direct Mode):")
        lbl_api_key.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.edit_inst2_api_key = QLineEdit()
        self.edit_inst2_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_inst2_api_key.setPlaceholderText("Paste GEMINI_API_KEY for isolated instance...")
        self.edit_inst2_api_key.setText(inst2_cfg.gemini_api_key)
        self.edit_inst2_api_key.setFixedHeight(28)

        self.btn_inst2_save_key = QPushButton("💾 Save API Key")
        self.btn_inst2_save_key.setFixedHeight(28)
        self.btn_inst2_save_key.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
        """)
        self.btn_inst2_save_key.clicked.connect(self._save_inst2_settings)

        self.btn_inst2_term_login = QPushButton("🔑 Login Instance 2 in Terminal")
        self.btn_inst2_term_login.setFixedHeight(28)
        self.btn_inst2_term_login.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.btn_inst2_term_login.clicked.connect(self._launch_inst2_terminal)

        i2_row2.addWidget(lbl_api_key)
        i2_row2.addWidget(self.edit_inst2_api_key, stretch=1)
        i2_row2.addWidget(self.btn_inst2_save_key)
        i2_row2.addWidget(self.btn_inst2_term_login)
        inst2_layout.addLayout(i2_row2)

        layout.addWidget(inst2_group)

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

            w["combo_engine"].blockSignals(True)
            w["combo_model"].blockSignals(True)
            w["combo_thinking"].blockSignals(True)

            # Set CLI Engine selection
            engine_idx = w["combo_engine"].findData(cfg.cli_engine)
            if engine_idx >= 0:
                w["combo_engine"].setCurrentIndex(engine_idx)
            else:
                w["combo_engine"].setCurrentIndex(0)

            # Populate models available for this specific CLI engine
            bridge = CliRegistry.get_bridge(cfg.cli_engine)
            engine_models = bridge.get_available_models()
            w["combo_model"].clear()
            w["combo_model"].addItems(engine_models)

            matched_model = next((m for m in engine_models if cfg.model.lower() in m.lower()), None)
            if not matched_model:
                matched_model = engine_models[0]
            w["combo_model"].setCurrentText(matched_model)
            cfg.model = matched_model

            if cfg.thinking_level == "high":
                w["combo_thinking"].setCurrentText("High (16k)")
            elif cfg.thinking_level == "low":
                w["combo_thinking"].setCurrentText("Low (1k)")
            else:
                w["combo_thinking"].setCurrentText("Medium (4k)")

            w["combo_engine"].blockSignals(False)
            w["combo_model"].blockSignals(False)
            w["combo_thinking"].blockSignals(False)

            persona_display_name = os.path.basename(cfg.persona_file) if cfg.persona_file else "Default"
            w["lbl_persona"].setText(f"📄 {persona_display_name}")
            w["lbl_persona"].setToolTip(cfg.persona_file if cfg.persona_file else "No custom persona loaded")

            self.config_combos[cfg.agent_id] = {
                "engine": w["combo_engine"],
                "model": w["combo_model"],
                "thinking": w["combo_thinking"]
            }
            self.config_personas[cfg.agent_id] = w["lbl_persona"]

    def _setup_tab_usage(self, parent: QWidget) -> None:
        """Tab 4: System Resource Monitor and LLM Token Usage Telemetry."""
        outer_layout = QVBoxLayout(parent)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        # === 1. System Resource Monitor Group ===
        sys_group = QGroupBox("💻 Host System Resources (Linux /proc)")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setContentsMargins(14, 12, 14, 12)
        sys_layout.setSpacing(10)

        sys_desc = QLabel("Real-time host CPU & Memory telemetry polled via POSIX /proc virtual filesystem")
        sys_desc.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        sys_layout.addWidget(sys_desc)

        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 4, 0, 4)
        metrics_grid.setSpacing(12)

        # CPU Metric
        lbl_cpu_title = QLabel("Host CPU Utilization:")
        lbl_cpu_title.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 12px;")
        metrics_grid.addWidget(lbl_cpu_title, 0, 0)

        self.lbl_cpu_val = QLabel("0.0%")
        self.lbl_cpu_val.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 13px;")
        metrics_grid.addWidget(self.lbl_cpu_val, 0, 1, Qt.AlignmentFlag.AlignRight)

        self.bar_cpu = QProgressBar()
        self.bar_cpu.setRange(0, 100)
        self.bar_cpu.setValue(0)
        self.bar_cpu.setFixedHeight(14)
        self.bar_cpu.setTextVisible(False)
        self.bar_cpu.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1F2937;
                border-radius: 4px;
                background-color: #0B0F19;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
                border-radius: 3px;
            }
        """)
        metrics_grid.addWidget(self.bar_cpu, 1, 0, 1, 2)

        # RAM Metric
        lbl_ram_title = QLabel("System RAM Utilization:")
        lbl_ram_title.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 12px;")
        metrics_grid.addWidget(lbl_ram_title, 0, 2)

        self.lbl_ram_val = QLabel("0 MB / 0 MB (0.0%)")
        self.lbl_ram_val.setStyleSheet("color: #34D399; font-weight: bold; font-size: 13px;")
        metrics_grid.addWidget(self.lbl_ram_val, 0, 3, Qt.AlignmentFlag.AlignRight)

        self.bar_ram = QProgressBar()
        self.bar_ram.setRange(0, 100)
        self.bar_ram.setValue(0)
        self.bar_ram.setFixedHeight(14)
        self.bar_ram.setTextVisible(False)
        self.bar_ram.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1F2937;
                border-radius: 4px;
                background-color: #0B0F19;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #34D399);
                border-radius: 3px;
            }
        """)
        metrics_grid.addWidget(self.bar_ram, 1, 2, 1, 2)

        sys_layout.addLayout(metrics_grid)
        layout.addWidget(sys_group)

        # === 2. Global Token Metrics Stat Cards ===
        token_group = QGroupBox("📈 LLM Token Metrics & Autonomous CLI Sessions")
        token_layout = QVBoxLayout(token_group)
        token_layout.setContentsMargins(14, 12, 14, 12)
        token_layout.setSpacing(10)

        token_desc = QLabel("Aggregated metrics captured from agy CLI stream-json outputs across all staff")
        token_desc.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        token_layout.addWidget(token_desc)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        def create_stat_card(icon_title: str, val_label: QLabel, sub_desc: str, color_hex: str) -> QFrame:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #111827;
                    border: 1px solid #1F2937;
                    border-radius: 8px;
                    padding: 6px;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 8, 10, 8)
            c_layout.setSpacing(4)

            t_lbl = QLabel(icon_title)
            t_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600;")
            c_layout.addWidget(t_lbl)

            val_label.setStyleSheet(f"color: {color_hex}; font-size: 20px; font-weight: 800; font-family: 'JetBrains Mono', monospace;")
            c_layout.addWidget(val_label)

            d_lbl = QLabel(sub_desc)
            d_lbl.setStyleSheet("color: #64748B; font-size: 10px;")
            c_layout.addWidget(d_lbl)
            return card

        self.lbl_total_tokens = QLabel("0")
        self.lbl_input_tokens = QLabel("0")
        self.lbl_output_tokens = QLabel("0")
        self.lbl_thinking_tokens = QLabel("0")
        self.lbl_total_calls = QLabel("0")

        cards_layout.addWidget(create_stat_card("⚡ Total Tokens", self.lbl_total_tokens, "Prompt + Gen + Think", "#38BDF8"))
        cards_layout.addWidget(create_stat_card("📥 Input Tokens", self.lbl_input_tokens, "Context & Prompts", "#A78BFA"))
        cards_layout.addWidget(create_stat_card("📤 Output Tokens", self.lbl_output_tokens, "Generated Responses", "#34D399"))
        cards_layout.addWidget(create_stat_card("🧠 Thinking", self.lbl_thinking_tokens, "Reasoning & Deliberation", "#F59E0B"))
        cards_layout.addWidget(create_stat_card("🔄 Turns Executed", self.lbl_total_calls, "Autonomous Sessions", "#E2E8F0"))

        token_layout.addLayout(cards_layout)
        layout.addWidget(token_group)

        # === 2.5 Dual-CLI Engine Comparison Cards ===
        cli_group = QGroupBox("⚔️ Multi-CLI Engine Telemetry (⚡ agy Instance 1 vs 🚀 agy Instance 2 / ollama)")
        cli_layout = QHBoxLayout(cli_group)
        cli_layout.setContentsMargins(14, 12, 14, 12)
        cli_layout.setSpacing(12)

        def create_cli_card(title: str, total_lbl: QLabel, calls_lbl: QLabel, io_lbl: QLabel, border_color: str) -> QFrame:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: #111827;
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 8px;
                }}
            """)
            c_vbox = QVBoxLayout(card)
            c_vbox.setContentsMargins(10, 8, 10, 8)
            c_vbox.setSpacing(6)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(f"color: {border_color}; font-size: 13px; font-weight: 700;")
            c_vbox.addWidget(lbl_t)

            row_tokens = QHBoxLayout()
            lbl_tok_desc = QLabel("Total Tokens:")
            lbl_tok_desc.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            total_lbl.setStyleSheet(f"color: {border_color}; font-size: 16px; font-weight: 800; font-family: 'JetBrains Mono', monospace;")
            row_tokens.addWidget(lbl_tok_desc)
            row_tokens.addStretch()
            row_tokens.addWidget(total_lbl)
            c_vbox.addLayout(row_tokens)

            row_turns = QHBoxLayout()
            lbl_turn_desc = QLabel("Sessions / Calls:")
            lbl_turn_desc.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            calls_lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            row_turns.addWidget(lbl_turn_desc)
            row_turns.addStretch()
            row_turns.addWidget(calls_lbl)
            c_vbox.addLayout(row_turns)

            row_io = QHBoxLayout()
            lbl_io_desc = QLabel("In / Out Split:")
            lbl_io_desc.setStyleSheet("color: #9CA3AF; font-size: 11px;")
            io_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
            row_io.addWidget(lbl_io_desc)
            row_io.addStretch()
            row_io.addWidget(io_lbl)
            c_vbox.addLayout(row_io)

            return card

        self.lbl_agy_total = QLabel("0")
        self.lbl_agy_calls = QLabel("0")
        self.lbl_agy_io = QLabel("0 in / 0 out")

        self.lbl_ollama_total = QLabel("0")
        self.lbl_ollama_calls = QLabel("0")
        self.lbl_ollama_io = QLabel("0 in / 0 out")

        cli_layout.addWidget(create_cli_card("⚡ agy (Instance 1 - Host Account)", self.lbl_agy_total, self.lbl_agy_calls, self.lbl_agy_io, "#38BDF8"))
        cli_layout.addWidget(create_cli_card("🚀 agy (Instance 2 - Isolated Profile)", self.lbl_ollama_total, self.lbl_ollama_calls, self.lbl_ollama_io, "#818CF8"))

        layout.addWidget(cli_group)

        # === 3. Sub-Agent Breakdown Table ===
        table_group = QGroupBox("🤖 Sub-Agent Token & Latency Breakdown")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(14, 12, 14, 12)
        table_layout.setSpacing(10)

        # Table Action Toolbar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        lbl_tbl_info = QLabel("Per-agent token consumption and execution latency metrics:")
        lbl_tbl_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
        action_bar.addWidget(lbl_tbl_info)
        action_bar.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setFixedHeight(28)
        btn_refresh.clicked.connect(self._refresh_usage_stats)
        action_bar.addWidget(btn_refresh)

        btn_reset = QPushButton("🧹 Reset Stats")
        btn_reset.setFixedHeight(28)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #371818;
                color: #F87171;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 0 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4C1D1D;
                color: #FCA5A5;
            }
        """)
        btn_reset.clicked.connect(self._reset_usage_stats)
        action_bar.addWidget(btn_reset)

        btn_open_json = QPushButton("📂 Open Stats (.json)")
        btn_open_json.setFixedHeight(28)
        btn_open_json.clicked.connect(self._open_usage_stats_json)
        action_bar.addWidget(btn_open_json)

        table_layout.addLayout(action_bar)

        # Table Widget
        self.tbl_usage = QTableWidget()
        self.tbl_usage.setColumnCount(9)
        self.tbl_usage.setHorizontalHeaderLabels([
            "Staff / Agent",
            "Engine",
            "Model",
            "Turns",
            "Input Tokens",
            "Output Tokens",
            "Thinking",
            "Total Tokens",
            "Latency"
        ])
        self.tbl_usage.setMinimumHeight(240)
        self.tbl_usage.verticalHeader().setVisible(False)
        self.tbl_usage.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_usage.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_usage.setAlternatingRowColors(True)

        header = self.tbl_usage.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        self.tbl_usage.setStyleSheet("""
            QTableWidget {
                background-color: #0B0F19;
                alternate-background-color: #111827;
                color: #F9FAFB;
                border: 1px solid #1F2937;
                border-radius: 6px;
                gridline-color: #1F2937;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #111827;
                color: #94A3B8;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #1E293B;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QTableWidget::item:selected {
                background-color: #1E293B;
                color: #38BDF8;
            }
        """)

        table_layout.addWidget(self.tbl_usage)
        layout.addWidget(table_group)
        layout.addStretch()

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

        # Rebind Tab 4 Usage Table
        if hasattr(self, "tbl_usage") and hasattr(self.orchestrator, "usage_tracker"):
            self._on_usage_updated(self.orchestrator.usage_tracker.get_telemetry_snapshot())

        self.lbl_status.setText(f"Active Squad: {dept.name}")

    def _select_inspector_slot(self, slot_idx: int) -> None:
        if 0 <= slot_idx < len(self.configs):
            self._select_detail_agent(self.configs[slot_idx].agent_id)

    def _on_engine_changed(self, slot_idx: int) -> None:
        """Handle CLI Engine switch for a specific agent slot."""
        if not (0 <= slot_idx < len(self.matrix_row_widgets)):
            return
        w = self.matrix_row_widgets[slot_idx]
        engine = w["combo_engine"].currentData() or "agy"
        bridge = CliRegistry.get_bridge(engine)
        models = bridge.get_available_models()

        w["combo_model"].blockSignals(True)
        w["combo_model"].clear()
        w["combo_model"].addItems(models)
        if models:
            w["combo_model"].setCurrentIndex(0)
        w["combo_model"].blockSignals(False)

        self._sync_config_slot(slot_idx)

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
        """Sync updated model, thinking, and CLI engine from config tab into node card and engine."""
        combos = self.config_combos.get(agent_id)
        if not combos:
            return
        new_engine = combos["engine"].currentData() if "engine" in combos else "agy"
        new_model = combos["model"].currentText()
        raw_thinking = combos["thinking"].currentText()
        new_thinking = "low" if "Low" in raw_thinking else (
            "high" if "High" in raw_thinking else ("max" if "Max" in raw_thinking else "medium")
        )

        cfg = next((c for c in self.configs if c.agent_id == agent_id), None)
        if cfg:
            cfg.cli_engine = new_engine

        if agent_id in self.node_widgets:
            self.node_widgets[agent_id].update_tags(new_model, new_thinking)
        self.orchestrator.update_agent_params(agent_id, new_model, new_thinking, new_engine=new_engine)

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
        if hasattr(self.orchestrator, "usage_tracker"):
            self.orchestrator.usage_tracker.usage_updated.connect(self._on_usage_updated)
            self.orchestrator.usage_tracker.system_resources_updated.connect(self._on_system_resources_updated)
            self._on_usage_updated(self.orchestrator.usage_tracker.get_telemetry_snapshot())
        if hasattr(self.orchestrator, "checkpoint_updated"):
            self.orchestrator.checkpoint_updated.connect(self._on_checkpoint_updated)
        if hasattr(self.orchestrator, "failover_forwarded"):
            self.orchestrator.failover_forwarded.connect(self._on_failover_triggered)
        self._update_resume_button()

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
        self.btn_resume.setEnabled(False)
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
        self._update_resume_button()
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

        if state_name in ("planning", "thinking", "calling_tool"):
            stage_names = {
                "agent_leader": "Stage 1 (Architect / Planning)",
                "agent_video_director": "Stage 1 (Director / Storyboard)",
                "agent_dev_ui": "Stage 2 (Frontend Dev & Layout)",
                "agent_dev_core": "Stage 2 (Backend Dev & Concurrency)",
                "agent_video_motion": "Stage 2 (Motion Graphics)",
                "agent_video_audio": "Stage 2 (Audio & Captions)",
                "agent_reviewer": "Stage 3 (Code Review & Audit)",
                "agent_video_reviewer": "Stage 3 (Video Quality Audit)",
                "agent_tester": "Stage 4 (Playwright & Chrome MCP Testing)",
                "agent_video_render": "Stage 4 (Headless Render QA)",
            }
            if agent_id in stage_names:
                self.lbl_status.setText(f"Running: {stage_names[agent_id]}...")

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
        self._update_resume_button()
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

    def _on_system_resources_updated(self, cpu_pct: float, ram_pct: float, used_mb: int, total_mb: int) -> None:
        """Slot called periodically by UsageTracker's system monitor."""
        if hasattr(self, "bar_cpu"):
            self.bar_cpu.setValue(int(cpu_pct))
            self.lbl_cpu_val.setText(f"{cpu_pct:.1f}%")
        if hasattr(self, "bar_ram"):
            self.bar_ram.setValue(int(ram_pct))
            self.lbl_ram_val.setText(f"{used_mb:,} MB / {total_mb:,} MB ({ram_pct:.1f}%)")

    def _on_usage_updated(self, snapshot: dict) -> None:
        """Slot called whenever tokens or CLI metrics are updated."""
        if not hasattr(self, "lbl_total_tokens") or not hasattr(self, "tbl_usage"):
            return

        total_tok = snapshot.get("total_tokens", 0)
        in_tok = snapshot.get("input_tokens", 0)
        out_tok = snapshot.get("output_tokens", 0)
        think_tok = snapshot.get("thinking_tokens", 0)
        calls = snapshot.get("cli_invocations", 0)

        self.lbl_total_tokens.setText(f"{total_tok:,}")
        self.lbl_input_tokens.setText(f"{in_tok:,}")
        self.lbl_output_tokens.setText(f"{out_tok:,}")
        self.lbl_thinking_tokens.setText(f"{think_tok:,}")
        self.lbl_total_calls.setText(f"{calls:,}")

        # Update Dual-CLI Engine Telemetry Cards
        cli_stats = snapshot.get("cli_stats", {})
        if hasattr(self, "lbl_agy_total") and hasattr(self, "lbl_ollama_total"):
            agy_stat = cli_stats.get("agy", {})
            self.lbl_agy_total.setText(f"{agy_stat.get('total_tokens', 0):,}")
            self.lbl_agy_calls.setText(f"{agy_stat.get('calls_count', 0):,}")
            self.lbl_agy_io.setText(f"{agy_stat.get('input_tokens', 0):,} in / {agy_stat.get('output_tokens', 0):,} out")

            inst2_stat = cli_stats.get("agy_instance_2", {})
            ollama_stat = cli_stats.get("ollama", {})
            if inst2_stat.get("total_tokens", 0) > 0 or inst2_stat.get("calls_count", 0) > 0:
                sec_stat = inst2_stat
            else:
                sec_stat = ollama_stat

            self.lbl_ollama_total.setText(f"{sec_stat.get('total_tokens', 0):,}")
            self.lbl_ollama_calls.setText(f"{sec_stat.get('calls_count', 0):,}")
            self.lbl_ollama_io.setText(f"{sec_stat.get('input_tokens', 0):,} in / {sec_stat.get('output_tokens', 0):,} out")

        # Update Table Rows (9 columns)
        agents_data = snapshot.get("agents", {})
        all_agent_ids = list(dict.fromkeys([cfg.agent_id for cfg in self.configs] + list(agents_data.keys())))

        self.tbl_usage.setRowCount(len(all_agent_ids))
        for row, aid in enumerate(all_agent_ids):
            cfg = next((c for c in self.configs if c.agent_id == aid), None)
            stat = agents_data.get(aid, {})

            avatar = stat.get("avatar") or (cfg.avatar if cfg else "🤖")
            name = stat.get("name") or (cfg.name if cfg else aid)
            engine = stat.get("cli_engine") or (cfg.cli_engine if cfg else "agy")
            model = stat.get("model") or (cfg.model if cfg else "-")
            turns = stat.get("calls_count", 0)
            in_t = stat.get("input_tokens", 0)
            out_t = stat.get("output_tokens", 0)
            th_t = stat.get("thinking_tokens", 0)
            tot_t = stat.get("total_tokens", 0)
            latency = stat.get("last_latency_sec", 0.0)

            # Column 0: Staff / Agent
            it_name = QTableWidgetItem(f"{avatar}  {name}")
            it_name.setToolTip(f"ID: {aid}")
            self.tbl_usage.setItem(row, 0, it_name)

            # Column 1: Engine Badge
            if engine == "agy":
                engine_text = "⚡ agy (Inst 1)"
                eng_color = "#38BDF8"
            elif engine == "agy_instance_2":
                engine_text = "🚀 agy (Inst 2)"
                eng_color = "#818CF8"
            elif engine == "ollama":
                engine_text = "🦙 ollama"
                eng_color = "#34D399"
            else:
                engine_text = f"🔧 {engine}"
                eng_color = "#F59E0B"

            it_eng = QTableWidgetItem(engine_text)
            it_eng.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_eng.setForeground(QColor(eng_color))
            self.tbl_usage.setItem(row, 1, it_eng)

            # Column 2: Model
            it_model = QTableWidgetItem(model)
            it_model.setForeground(QColor("#94A3B8"))
            self.tbl_usage.setItem(row, 2, it_model)

            # Column 3: Turns
            it_turns = QTableWidgetItem(str(turns))
            it_turns.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_usage.setItem(row, 3, it_turns)

            # Column 4: Input Tokens
            it_in = QTableWidgetItem(f"{in_t:,}")
            it_in.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_in.setForeground(QColor("#A78BFA"))
            self.tbl_usage.setItem(row, 4, it_in)

            # Column 5: Output Tokens
            it_out = QTableWidgetItem(f"{out_t:,}")
            it_out.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_out.setForeground(QColor("#34D399"))
            self.tbl_usage.setItem(row, 5, it_out)

            # Column 6: Thinking
            it_think = QTableWidgetItem(f"{th_t:,}")
            it_think.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_think.setForeground(QColor("#F59E0B"))
            self.tbl_usage.setItem(row, 6, it_think)

            # Column 7: Total Tokens
            it_tot = QTableWidgetItem(f"{tot_t:,}")
            it_tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it_tot.setForeground(QColor("#38BDF8"))
            self.tbl_usage.setItem(row, 7, it_tot)

            # Column 8: Latency
            lat_str = f"{latency:.2f}s" if latency > 0 else "-"
            it_lat = QTableWidgetItem(lat_str)
            it_lat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_usage.setItem(row, 8, it_lat)

    def _refresh_usage_stats(self) -> None:
        """Manually refresh usage stats snapshot and table."""
        if hasattr(self.orchestrator, "usage_tracker"):
            snapshot = self.orchestrator.usage_tracker.get_telemetry_snapshot()
            self._on_usage_updated(snapshot)
            self.lbl_status.setText("Usage stats refreshed.")

    def _reset_usage_stats(self) -> None:
        """Reset all tracked usage metrics."""
        if hasattr(self.orchestrator, "usage_tracker"):
            self.orchestrator.usage_tracker.reset_stats()
            self.lbl_status.setText("Usage stats reset successfully.")

    def _open_usage_stats_json(self) -> None:
        """Open or display the persistent JSON usage metrics file."""
        if not hasattr(self.orchestrator, "usage_tracker"):
            return
        p_file = self.orchestrator.usage_tracker.persistence_file
        if not os.path.exists(p_file):
            self.orchestrator.usage_tracker._save()

        dialog = QDialog(self)
        dialog.setWindowTitle("📊 Usage Telemetry JSON (.agent/usage_stats.json)")
        dialog.resize(680, 520)
        d_layout = QVBoxLayout(dialog)
        d_layout.setContentsMargins(14, 14, 14, 14)
        d_layout.setSpacing(10)

        lbl_path = QLabel(f"File: {p_file}")
        lbl_path.setStyleSheet("color: #94A3B8; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        d_layout.addWidget(lbl_path)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            background-color: #0B0F19;
            color: #F8FAFC;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            border: 1px solid #1F2937;
            border-radius: 6px;
            padding: 8px;
        """)
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            content = f"Error reading file: {e}"
        text_edit.setPlainText(content)
        d_layout.addWidget(text_edit)

        btn_box = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        d_layout.addLayout(btn_box)

        dialog.exec()

    def _update_resume_button(self) -> None:
        """Update Resume button state and label based on active checkpoint."""
        if not hasattr(self, "btn_resume") or not hasattr(self, "orchestrator"):
            return
        has_cp = self.orchestrator.has_checkpoint()
        if has_cp:
            stage_name = self.orchestrator.get_checkpoint_stage_name()
            self.btn_resume.setEnabled(True)
            self.btn_resume.setText(f"▶️ Resume ({stage_name})")
            self.btn_resume.setToolTip(f"Resume mission from checkpoint at {stage_name}")
        else:
            self.btn_resume.setEnabled(False)
            self.btn_resume.setText("▶️ Resume")
            self.btn_resume.setToolTip("No active checkpoint available to resume.")

    def _on_checkpoint_updated(self, has_checkpoint: bool, stage_name: str) -> None:
        """Slot invoked whenever a pipeline checkpoint is created or cleared."""
        self._update_resume_button()
        if has_checkpoint and stage_name:
            self.lbl_status.setText(f"Checkpoint saved: Ready to resume from {stage_name}")

    def _on_failover_triggered(self, agent_id: str, old_engine: str, new_engine: str, reason: str) -> None:
        """Slot invoked when rate limit triggers automatic CLI failover."""
        if agent_id in self.node_widgets:
            node = self.node_widgets[agent_id]
            node.setToolTip(f"Failover triggered from {old_engine} to {new_engine}: {reason}")
        self.lbl_status.setText(f"⚠️ Failover: {agent_id} switched {old_engine} ➔ {new_engine} ({reason})")

    def _on_toggle_failover(self, checked: bool) -> None:
        """Slot invoked when user toggles automated failover setting."""
        self.orchestrator.auto_failover_enabled = checked
        status = "enabled" if checked else "disabled"
        self.lbl_status.setText(f"Automated CLI failover {status}.")

    def _handle_resume(self) -> None:
        """Resumes hierarchical pipeline from saved checkpoint without restarting from stage 1."""
        if not self.orchestrator.has_checkpoint():
            return

        chk = self.orchestrator.checkpoint_manager.load_checkpoint()
        if not chk:
            return

        # Restore prompt UI
        if chk.task_prompt:
            self.edit_prompt.setText(chk.task_prompt)
            self.lbl_active_prompt.setText(f"Mission: {chk.task_prompt}")

        # Mark completed stages on compact nodes
        completed = set(chk.completed_stages)
        for aid, node in self.node_widgets.items():
            if aid in completed:
                node.set_progress(100)
                node.set_status("COMPLETED")
            else:
                node.set_progress(0)
                node.set_status("IDLE")

        self.btn_dispatch.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_stop.setEnabled(True)
        self._is_paused = False

        self.lbl_status.setText(f"Resuming pipeline from {chk.stage_name}...")
        self.orchestrator.resume_from_checkpoint()

    def _save_inst2_settings(self) -> None:
        """Saves Gemini API key and updates Instance 2 config."""
        api_key = self.edit_inst2_api_key.text().strip()
        bridge = CliRegistry.get_bridge("agy_instance_2")
        if hasattr(bridge, "config"):
            bridge.config.gemini_api_key = api_key
            if api_key:
                bridge.config.auth_mode = "gemini_api_key"
            else:
                bridge.config.auth_mode = "oauth"
            bridge.config.save()

            is_auth = bridge.is_authenticated()
            self.lbl_inst2_status.setText("● Authenticated" if is_auth else "● Authentication Required")
            self.lbl_inst2_status.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;" if is_auth else "color: #F59E0B; font-size: 11px; font-weight: bold;")
            self.lbl_status.setText("Antigravity CLI Instance 2 settings saved.")

    def _launch_inst2_terminal(self) -> None:
        """Launches external terminal for OAuth authentication in Instance 2 isolated profile."""
        bridge = CliRegistry.get_bridge("agy_instance_2")
        if hasattr(bridge, "launch_interactive_login"):
            ok, msg = bridge.launch_interactive_login()
            self.lbl_status.setText(msg)

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self.orchestrator, "telegram_bridge"):
            self.orchestrator.telegram_bridge.stop_polling()
        self.orchestrator.stop_all()
        event.accept()

