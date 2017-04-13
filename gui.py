import sys

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QApplication, QHBoxLayout, QVBoxLayout, QLabel, QComboBox
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QBrush, QColor
from PyQt5.QtCore import Qt


class Editor(QWidget):
    """
    The main editor window
    """

    def __init__(self):
        super().__init__()
        self.UI_initialized = False
        self.init_UI()


    def init_UI(self):
        if self.UI_initialized:
            return

        self.setWindowTitle("Smart BCR2k Editor - Dev Edition")
        self.show()

        self.UI_initialized = True

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = Editor()

    sys.exit(app.exec_())
