APP_STYLESHEET = """
QWidget {
    background: #0e151d;
    color: #e6edf5;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC", "Noto Sans CJK SC", "SimSun";
    font-size: 13px;
}

QMainWindow {
    background: #0a1016;
}

QFrame#WindowSurface {
    background: #0f1720;
    border: 1px solid #263544;
    border-radius: 18px;
}

QFrame#TitleBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #152333, stop:1 #101922);
    border-bottom: 1px solid #2b3b4d;
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
}

QLabel#TitleBarTitle {
    font-size: 19px;
    font-weight: 700;
    color: #f7fbff;
}

QLabel#TitleBarSubtitle {
    color: #9fb3c8;
}

QLabel#TitleBarContext {
    background: #152433;
    color: #c9d7e5;
    border: 1px solid #27435d;
    border-radius: 11px;
    padding: 4px 10px;
    font-weight: 600;
}

QToolButton#WindowButton,
QToolButton#WindowCloseButton {
    background: transparent;
    color: #dbe5ef;
    border: 1px solid #304354;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
}

QToolButton#WindowButton:hover {
    background: #1e3142;
}

QToolButton#WindowCloseButton:hover {
    background: #8c2630;
    border-color: #b94855;
    color: #ffffff;
}

QFrame#Sidebar,
QFrame#Panel,
QFrame#Hero,
QDockWidget {
    background: #16212c;
    border: 1px solid #2a3949;
    border-radius: 14px;
}

QScrollArea#PanelScrollArea {
    background: transparent;
    border: none;
}

QScrollArea#PanelScrollArea > QWidget > QWidget {
    background: transparent;
}

QListWidget {
    background: transparent;
    border: none;
    outline: none;
    padding: 4px 0;
}

QListWidget::item {
    padding: 8px 10px;
    margin: 3px 0;
    border-radius: 10px;
}

QListWidget::item:hover {
    background: #1b2c3e;
}

QListWidget::item:selected {
    background: #245176;
    color: #ffffff;
}

QLabel#HeroTitle {
    font-size: 19px;
    font-weight: 700;
    color: #f5f9fd;
}

QLabel#HeroSubtitle {
    color: #b7c6d6;
    font-size: 11px;
}

QLabel#ModuleTitle {
    font-size: 20px;
    font-weight: 700;
    color: #f7fbff;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #dbe7f3;
}

QLabel#MetaLabel {
    color: #9fb0c1;
}

QFrame#WorkspaceCard {
    background: #111a23;
    border: 1px solid #263544;
    border-radius: 12px;
}

QLabel#WorkspaceEyebrow {
    color: #88a2bb;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

QLabel#WorkspaceTitle {
    color: #f4f8fc;
    font-size: 16px;
    font-weight: 700;
}

QLabel#PathLabel {
    background: #111922;
    border: 1px solid #263544;
    border-radius: 10px;
    padding: 8px 10px;
    color: #dfe8f1;
}

QLabel#Badge {
    background: #1b3246;
    color: #dbeaf7;
    padding: 4px 10px;
    border-radius: 11px;
    border: 1px solid #2d536f;
    font-weight: 600;
    font-size: 12px;
}

QLabel#SidebarPill {
    background: #1b3246;
    color: #dbeaf7;
    padding: 3px 10px;
    border-radius: 10px;
    border: 1px solid #2d536f;
    font-weight: 600;
    font-size: 12px;
}

QDockWidget::title {
    background: #16212c;
    text-align: left;
    padding: 8px 10px;
    color: #dbe7f3;
    font-weight: 700;
}

QTextEdit {
    background: #101821;
    border: 1px solid #2a3949;
    border-radius: 10px;
    padding: 8px;
}

QTabWidget::pane {
    background: #101821;
    border: 1px solid #2a3949;
    border-radius: 12px;
    margin-top: 6px;
}

QTabBar::tab {
    background: #13202c;
    color: #9fb0c1;
    border: 1px solid #2a3949;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 7px 14px;
    margin-right: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #1d3142;
    color: #f7fbff;
    border-color: #32587b;
}

QTabBar::tab:hover:!selected {
    background: #182734;
    color: #dbe5ef;
}

QSplitter::handle {
    background: #0f1720;
}

QSplitter::handle:horizontal {
    width: 8px;
    margin: 0 2px;
}

QLineEdit,
QComboBox,
QSpinBox {
    background: #101821;
    border: 1px solid #2a3949;
    border-radius: 10px;
    padding: 6px 8px;
    min-height: 18px;
}

QComboBox::drop-down,
QSpinBox::drop-down {
    border: none;
    width: 22px;
}

QPushButton {
    background: #244563;
    color: #dbeaf7;
    border: 1px solid #315777;
    border-radius: 10px;
    padding: 7px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #2c587d;
}

QPushButton:disabled {
    background: #1a2633;
    color: #708396;
    border-color: #263443;
}

QComboBox:editable {
    padding-right: 4px;
}
"""
