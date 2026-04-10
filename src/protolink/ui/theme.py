APP_STYLESHEET = """
QWidget {
    background: #11151c;
    color: #e8ecf1;
    font-family: Segoe UI;
    font-size: 13px;
}

QMainWindow {
    background: #11151c;
}

QFrame#Sidebar,
QFrame#Panel,
QFrame#Hero,
QDockWidget {
    background: #19202a;
    border: 1px solid #2b3746;
}

QFrame#Sidebar,
QFrame#Panel,
QFrame#Hero {
    border-radius: 12px;
}

QDockWidget::title {
    background: #19202a;
    text-align: left;
    padding: 8px 12px;
    color: #f4c96b;
    font-weight: 700;
}

QListWidget {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 10px 12px;
    margin: 4px 6px;
    border-radius: 8px;
}

QListWidget::item:selected {
    background: #25476a;
    color: #ffffff;
}

QLabel#HeroTitle {
    font-size: 28px;
    font-weight: 700;
}

QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 700;
    color: #f4c96b;
}

QLabel#MetaLabel {
    color: #9fb0c1;
}

QLabel#Badge {
    background: #244563;
    color: #dbeaf7;
    padding: 4px 10px;
    border-radius: 10px;
    font-weight: 600;
}

QTextEdit {
    background: #131922;
    border: 1px solid #2b3746;
    border-radius: 8px;
    padding: 8px;
}

QLineEdit,
QComboBox,
QSpinBox {
    background: #131922;
    border: 1px solid #2b3746;
    border-radius: 8px;
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
    border: 1px solid #325777;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: 600;
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
