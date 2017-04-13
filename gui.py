import sys
from collections import namedtuple

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QApplication, QHBoxLayout, QVBoxLayout, QLabel, QComboBox
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QBrush, QColor
from PyQt5.QtCore import Qt

from ctrl import Interface, load_profile, save_profile
from devices import BCR2k, MidiLoop

Vector2 = namedtuple("Vector2", ["x", "y"])

class Controller(Object):
    """
    Communicates between Editor (GUI) and Interface (Model)
    """

    def __init__(self, interface, editor):
        self.interface = interface
        self.editor = editor


class Editor(QWidget):
    """
    The main editor window
    """
    position = Vector2(-750, 250)
    size = Vector2(700, 700)
    title = "Smart BCR2k Editor - Dev Edition"

    def __init__(self):
        super().__init__()
        self.UI_initialized = False
        self.init_UI()


    def init_UI(self):
        if self.UI_initialized:
            return

        self.setWindowTitle(self.title)
        self.resize(self.size.x, self.size.y)
        self.move(self.position.x, self.position.y)
        self.show()

        self.UI_initialized = True

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = Editor()

    bcr = BCR2k()
    loop = MidiLoop()

    interface = Interface(bcr, loop)
    interface.load_profile(


    sys.exit(app.exec_())
