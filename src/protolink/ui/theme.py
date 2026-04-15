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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #13202d, stop:1 #0f1822);
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
    background: #111923;
    color: #9fb0c1;
    border: 1px solid #243544;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 12px;
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

QToolButton#SubtleButton {
    background: #111922;
    color: #9fb0c1;
    border: 1px solid #263544;
    border-radius: 9px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}

QToolButton#SubtleButton:hover,
QToolButton#SubtleButton:checked {
    background: #172533;
    border-color: #31506a;
    color: #dfe8f1;
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

QFrame#Hero {
    background: #141d26;
    border-color: #243240;
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
    padding: 8px 10px 8px 12px;
    margin: 3px 0;
    border-radius: 10px;
    border: 1px solid transparent;
}

QListWidget::item:hover {
    background: #152330;
    border-color: #213444;
}

QListWidget::item:selected {
    background: #1b3142;
    border-color: #33536e;
    color: #ffffff;
}

QLabel#HeroTitle {
    font-size: 17px;
    font-weight: 700;
    color: #edf4fb;
}

QLabel#HeroSubtitle {
    color: #93a7ba;
    font-size: 11px;
}

QLabel#ModuleTitle {
    font-size: 18px;
    font-weight: 700;
    color: #f7fbff;
}

QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 700;
    color: #cfdae6;
}

QLabel#MetaLabel {
    color: #93a4b5;
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

QLabel#HeroBadge {
    background: #1b3246;
    color: #b9cadb;
    padding: 3px 9px;
    border-radius: 10px;
    border: 1px solid #294559;
    font-weight: 600;
    font-size: 11px;
}

QLabel#SidebarPill {
    background: #121b24;
    color: #97aabd;
    padding: 2px 8px;
    border-radius: 10px;
    border: 1px solid #28384a;
    font-weight: 600;
    font-size: 11px;
}

QDockWidget::title {
    background: #141d26;
    text-align: left;
    padding: 6px 10px;
    color: #c6d3df;
    font-weight: 600;
    font-size: 12px;
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
    margin-top: 4px;
}

QTabBar::tab {
    background: #13202c;
    color: #9fb0c1;
    border: 1px solid #2a3949;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 6px 12px;
    margin-right: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #182937;
    color: #f7fbff;
    border-color: #2e516d;
}

QTabBar::tab:hover:!selected {
    background: #162431;
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
