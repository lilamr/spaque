"""
ui/components/style_editor.py — App-wide dark stylesheet loader
"""

APP_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1a1d23;
    color: #e0e6f0;
    font-family: 'Segoe UI', 'Noto Sans', Arial, sans-serif;
    font-size: 12px;
}
QMenuBar {
    background: #13151a;
    color: #c0cad8;
    border-bottom: 1px solid #2d3340;
    padding: 2px;
}
QMenuBar::item:selected { background: #2d3340; border-radius: 4px; }
QMenu {
    background: #1e2229;
    color: #c0cad8;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 5px 20px 5px 10px; border-radius: 3px; }
QMenu::item:selected { background: #2e5bff28; color: #ffffff; }
QMenu::separator { height: 1px; background: #2d3340; margin: 4px 8px; }
QToolBar {
    background: #13151a;
    border-bottom: 1px solid #2d3340;
    padding: 3px 8px;
    spacing: 3px;
}
QPushButton {
    background: #2e5bff;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
}
QPushButton:hover   { background: #4a70ff; }
QPushButton:pressed { background: #1a47ff; }
QPushButton:disabled { background: #2d3340; color: #50586a; }
QPushButton#secondary {
    background: #2d3340;
    color: #c0cad8;
    border: 1px solid #3d4455;
}
QPushButton#secondary:hover { background: #3d4455; color: #ffffff; }
QPushButton#success { background: #1e9e6a; }
QPushButton#success:hover { background: #22b87a; }
QPushButton#danger  { background: #e03c4a; }
QPushButton#danger:hover  { background: #f04a58; }
QLineEdit, QTextEdit, QPlainTextEdit {
    background: #13151a;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e6f0;
}
QLineEdit:focus, QTextEdit:focus { border-color: #2e5bff; }
QComboBox {
    background: #13151a;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 5px 10px;
    color: #e0e6f0;
    min-width: 100px;
}
QComboBox:focus { border-color: #2e5bff; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #1e2229;
    border: 1px solid #2d3340;
    border-radius: 4px;
    color: #c0cad8;
    selection-background-color: #2e5bff44;
}
QSpinBox, QDoubleSpinBox {
    background: #13151a;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 5px 8px;
    color: #e0e6f0;
}
QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2e5bff; }
QTreeWidget {
    background: #13151a;
    border: none;
    color: #c0cad8;
    outline: none;
}
QTreeWidget::item { padding: 4px 2px; border-radius: 3px; }
QTreeWidget::item:hover    { background: #1e2229; }
QTreeWidget::item:selected { background: #2e5bff28; color: #6699ff; }
QHeaderView::section {
    background: #13151a;
    color: #6a7590;
    border: none;
    border-bottom: 1px solid #2d3340;
    padding: 5px 8px;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 0.5px;
}
QTableWidget {
    background: #1a1d23;
    alternate-background-color: #1d2028;
    border: none;
    color: #c0cad8;
    gridline-color: #2d3340;
    selection-background-color: #2e5bff44;
    selection-color: #ffffff;
}
QTableWidget::item { padding: 3px 6px; }
QTabWidget::pane { border: none; background: #1a1d23; }
QTabBar::tab {
    background: #13151a;
    color: #6a7590;
    border: 1px solid #2d3340;
    padding: 5px 16px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-size: 11px;
}
QTabBar::tab:selected {
    background: #1a1d23;
    color: #e0e6f0;
    border-bottom-color: #1a1d23;
}
QTabBar::tab:hover { background: #2d3340; color: #c0cad8; }
QGroupBox {
    border: 1px solid #2d3340;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 6px;
    color: #6a7590;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 0.5px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QScrollBar:vertical {
    background: #1a1d23;
    width: 7px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3d4455;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #4d5570; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #1a1d23;
    height: 7px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #3d4455;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background: #2d3340; }
QStatusBar {
    background: #13151a;
    color: #6a7590;
    border-top: 1px solid #2d3340;
    font-size: 11px;
    padding: 2px 8px;
}
QProgressBar {
    background: #2d3340;
    border-radius: 3px;
    text-align: center;
    color: transparent;
    max-height: 5px;
}
QProgressBar::chunk { background: #2e5bff; border-radius: 3px; }
QCheckBox { color: #c0cad8; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid #3d4455;
    background: #13151a;
}
QCheckBox::indicator:checked { background: #2e5bff; border-color: #2e5bff; }
QLabel { color: #c0cad8; }
QFrame#card {
    background: #1e2229;
    border: 1px solid #2d3340;
    border-radius: 10px;
    padding: 10px;
}
"""
