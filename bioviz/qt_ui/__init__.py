use_pyqt6 = True
try:
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QFrame,
        QGridLayout,
        QGroupBox,
        QCheckBox,
        QComboBox,
        QScrollArea,
        QBoxLayout,
        QHBoxLayout,
        QVBoxLayout,
        QPushButton,
        QWidget,
        QLabel,
        QInputDialog,
        QWidget,
        QLineEdit,
        QFileDialog,
        QSlider,
        QMessageBox,
        QRadioButton,
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColorConstants, QPalette, QColor, QPixmap, QIcon, QPainter
except ImportError:
    use_pyqt6 = False

if not use_pyqt6:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QFrame,
        QGridLayout,
        QGroupBox,
        QCheckBox,
        QComboBox,
        QScrollArea,
        QBoxLayout,
        QHBoxLayout,
        QVBoxLayout,
        QPushButton,
        QWidget,
        QLabel,
        QInputDialog,
        QWidget,
        QLineEdit,
        QFileDialog,
        QSlider,
        QMessageBox,
        QRadioButton,
    )
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColorConstants, QPalette, QColor, QPixmap, QIcon, QPainter
