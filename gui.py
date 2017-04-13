import sys
import itertools
from collections import namedtuple

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QApplication, QHBoxLayout, QVBoxLayout, QLabel, QComboBox
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QBrush, QColor
from PyQt5.QtCore import Qt

from ctrl import Interface, load_profile, save_profile
from devices import BCR2k, MidiLoop

Vector2 = namedtuple("Vector2", ["x", "y"])

class Controller(object):
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

    def __init__(self, interface=None):
        super().__init__()
        self.UI_initialized = False
        self.interface = interface

        if self.interface:
            self.initialize(self.interface)

    def init_UI(self):
        if self.UI_initialized:
            return

        self.setWindowTitle(self.title)
        self.resize(self.size.x, self.size.y)
        self.move(self.position.x, self.position.y)

        
        self.show()
        self.UI_initialized = True

    def initialize(self, interface):
        self.init_UI()

        self.interface = interface
        grid = QGridLayout()
        
        # Do input device specific stuff
        # @Flexibility: Move this out of here and support multiple controllers

        bcr = self.interface.input
        
        row = 0
        col = 0
        rowlen = 8

        WidgetDial = QPushButton
        WidgetButton = QPushButton

        control_widgets = {}  # Map controls to Widgets

        def make_groups(grid, controls, Widget, start_row=0, start_col=0):
            row = 0
            col = 0
            for row, group in enumerate(controls, start=start_row):
                for col, control in enumerate(group, start=start_col):
                    w = grid.addWidget(Widget(str(control)), row, col)
                    control_widgets[control] = w
            return row + 1, col + 1

        def make_group(grid, controls, Widget, length, start_row=0, start_col=0):
            args = [iter(controls)] * length
            l = list( itertools.zip_longest(*args))
            return make_groups(grid, l, Widget, start_row=start_row, start_col=start_col)

        # Macro Dials
        row, _ = make_groups(grid, bcr.macros, WidgetButton, row) 
            
        # Main Buttons
        row, _ = make_groups(grid, bcr.menu_buttons, WidgetButton, row) 
 
        # Main Dials
        row, _ = make_groups(grid, bcr.dialsr, QPushButton, row)

        # Bottom Right Buttons
        row, _ = make_group(grid, bcr.command_buttons, QPushButton, 2, row-2, rowlen+1)

        # End input device specific stuff



        self.setLayout(grid)


        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Setup Devices and Interface
    bcr = BCR2k()
    loop = MidiLoop()

    interface = Interface(bcr, loop)
    load_profile(interface, "default.bcr")

    # Create GUI
    editor = Editor()

    # Create Controller
    controller = Controller(interface, editor)

    # Initialize GUI
    editor.initialize(interface)

    sys.exit(app.exec_())
