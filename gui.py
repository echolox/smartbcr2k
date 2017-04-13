import sys
import itertools
from collections import namedtuple

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QApplication, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QListWidget
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
    position = Vector2(-900, 250)
    size = Vector2(850, 700)
    title = "Smart BCR2k Editor - Dev Edition"

    def __init__(self, interface=None):
        super().__init__()
        self.UI_initialized = False
        self.interface = interface

        if self.interface:
            self.initialize(self.interface)

    def init_UI(self):
        """
        Initialize input device agnostic UI elements
        """
        if self.UI_initialized:
            return

        self.setWindowTitle(self.title)
        self.resize(self.size.x, self.size.y)
        self.move(self.position.x, self.position.y)

        
        self.show()
        self.UI_initialized = True

    def initialize(self, interface):
        """
        Initialize UI elements dependent on the interface and input device
        """
        self.init_UI()

        self.interface = interface
        self.interface.observers.append(self)


        self.layout_container = QWidget()
        self.layout = QHBoxLayout()

        self.view_selector = QListWidget()
        self.view_selector.addItems((view.name for view in self.interface.views))

        self.view_selector.setCurrentRow(self.interface.views.index(self.interface.view))

        self.view_selector.currentItemChanged.connect(
            lambda index: self.interface.switch_to_view(self.view_selector.currentItem().text()))
        self.layout.addWidget(self.view_selector)


        grid = QGridLayout()
        # Do input device specific stuff
        # @Flexibility: Move this out of here and support multiple controllers

        bcr = self.interface.input
        
        row = 0
        col = 0
        rowlen = 8

        WidgetDial = QPushButton
        WidgetButton = QPushButton

        self.control_widgets = {}  # Map control IDs to Widgets

        def make_groups(grid, controls, Widget, start_row=0, start_col=0):
            row = 0
            col = 0
            for row, group in enumerate(controls, start=start_row):
                for col, control in enumerate(group, start=start_col):
                    w = Widget(str(control))
                    grid.addWidget(w, row, col)
                    self.control_widgets[control.ID] = w
            return row + 1, col + 1

        def make_group(grid, controls, Widget, length, start_row=0, start_col=0):
            args = [iter(controls)] * length
            l = (itertools.zip_longest(*args))
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
        grid_container = QWidget()
        grid_container.setLayout(grid)
        self.layout.addWidget(grid_container)

        self.setLayout(self.layout)

        pass


    def reflect(self, ID, value):
        widget = self.control_widgets[ID]
        widget.setText(str(value))
        
    def reflect_all(self, view):
        for ID in self.control_widgets:
            value = str(self.interface.input.controls[ID])
            self.reflect(ID, value)
        

    def callback_value(self, IDs, target):
        """
        Called whenever any value in a target on the interface changed.
        We also get a list of control IDs mapped to that target.
        """
        # @Question: Is target not needed?

        # @TODO: Proper value inference and value setting on Widget
        for ID in IDs:
            value = str(self.interface.input.controls[ID])
            self.reflect(ID, value)

    def callback_view(self, view):
        """
        Called whenever the active view in the interface has changed
        """

        # Reflect values on all controls
        self.reflect_all(view) 

        # Reflect current View in the general UI
        for index in range(self.view_selector.count()):
            item = self.view_selector.item(index)
            if item.text() == view.name:
                self.view_selector.setCurrentRow(index)
                break


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
