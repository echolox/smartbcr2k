import sys
import time
import itertools
from threading import Lock
from collections import namedtuple

from PyQt5.QtWidgets import QWidget, QGridLayout, QPushButton, QApplication, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QListWidget, QLineEdit, QAction, QMenuBar, QMainWindow, QSlider
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QBrush, QColor
from PyQt5.QtCore import Qt, QTimer

from interface import Interface, View, load_profile, save_profile
from devices import BCR2k, MidiLoop
from threadshell import Shell
import devices

Vector2 = namedtuple("Vector2", ["x", "y"])

setters = {QSlider: QSlider.setValue,
           QPushButton: QPushButton.setDown
          }


class Controller(object):
    """
    Takes care of "higher level" commands or command sequences to be
    issued to the interface. It's the 'business logic' part.
    """

    def __init__(self, interface, editor):
        self.interface = interface
        self.editor = editor

    def create_view(self, name, switch=True, copy=None):
        """
        Creates a new view with the provided name.
        Another view can be provided to duplicate (except for the name)
        """
        # @Feature: Copying views
        view = View(self.interface.input, name=name)
        if switch:
            self.interface.switch_to_view(view)
        else:
            self.interface.add_view(view)

    def save_profile(self, filename=None):
        if filename:
            # Save As
            pass
        else:
            print("SAVING")
            save_profile(self.interface, "profile.bcr")

    def load_profile(self, filename=None):
        # TEMP
        print("LOADING")
        load_profile(self.interface, "default.bcr")
        
        # TODO: Reload everything in UI from Profile

    def trigger_targets(self, ID, value):
        """
        Triggers the target(s) the given ID (of a control) is mapped to.
        Since this operation should occur in the shelled interface thread
        we need route through the interface instead of manipulating the
        targets directly.
        """
        targets = self.interface.view.map[ID]
        self.interface.trigger_targets(self, targets, value)


class Editor(QMainWindow):
    """
    The main editor window
    """
    position = Vector2(-950, 250)
    size = Vector2(850, 700)
    title = "Smart BCR2k Editor - Dev Edition"

    def __init__(self, interface=None, controller=None):
        super().__init__()
        self.UI_initialized = False
        self.interface = interface
        self.controller = controller

        if self.interface and self.controller:
            self.initialize(self.interface, self.controller)

        self.locks = {"views": Lock()
                     }

    def initialize(self, interface, controller):
        """
        Initialize UI elements dependent on the interface and input device
        """
        self.init_window()

        self.controller = controller

        self.interface = interface
#        self.interface.observers.append(self)

        ### Menu Bar
        def create_action(label, shortcut, tip, callback):
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.setStatusTip(tip)
            action.triggered.connect(callback)
            return action

        menu_file_save = create_action("Save", "Ctrl+S", "Save the current profile",
                                       self.controller.save_profile)
        menu_file_load = create_action("Load", "Ctrl+O", "Load a profile",
                                       self.controller.load_profile)

        menu = self.menuBar()
        menu_file = menu.addMenu("&File")
        menu_file.addAction(menu_file_save)
        menu_file.addAction(menu_file_load)

        ### Status Bar
        self.statusBar()


        ### MAIN LAYOUT
        self.layout = QHBoxLayout()
        self.layout_container = QWidget()
        self.layout_container.setLayout(self.layout)
        self.setCentralWidget(self.layout_container)



        ### View Management
        self.view_layout = QVBoxLayout()

        self.view_selector = QListWidget()
        self.view_selector.addItems((view.name for view in self.interface.views))
        self.view_selector.setCurrentRow(self.interface.views.index(self.interface.view))
        self.view_selector.itemClicked.connect(self.view_changed)
        self.view_selector.setMinimumWidth(100)
        self.view_layout.addWidget(self.view_selector)


        ## View Creation
        self.view_add_text = QLineEdit()
        def create_view():
            if (self.view_add_text.text().strip() != ""):
                self.controller.create_view(self.view_add_text.text())
                self.view_add_text.setText("")
        self.view_add_text.returnPressed.connect(create_view)
        self.view_layout.addWidget(self.view_add_text)

        self.view_add_button = QPushButton("+")
        self.view_add_button.clicked.connect(create_view)
        self.view_layout.addWidget(self.view_add_button)


        ## View Layout
        self.view_container = QWidget()
        self.view_container.setLayout(self.view_layout)
        self.layout.addWidget(self.view_container)



        ### Device Management
        grid = QGridLayout()
        # Do input device specific stuff
        # @Flexibility: Move this out of here and support multiple controllers

        bcr = self.interface.input
        
        row = 0
        col = 0
        rowlen = 8


        def create_dial(control):
            ID = control.ID
            sld = QSlider(Qt.Horizontal, self)
            sld.setMaximum(127)
            #sld.setFocusPolicy(Qt.NoFocus)
            sld.sliderMoved.connect(lambda value: self.value_changed(ID, value))
            return sld

        def create_button(control):
            ID = control.ID
            button = QPushButton(str(control))
            button.setCheckable(True)
            button.clicked[bool].connect(lambda value: self.value_changed(ID, value))
            return button

        factory = {devices.Dial: create_dial,
                   devices.Button: create_button,
                  }

        self.control_widgets = {}  # Map control IDs to Widgets

        def make_groups(grid, controls, Widget, start_row=0, start_col=0):
            row = 0
            col = 0
            for row, group in enumerate(controls, start=start_row):
                for col, control in enumerate(group, start=start_col):
                    w = factory[type(control)](control)
                    grid.addWidget(w, row, col)
                    self.control_widgets[control.ID] = w
            return row + 1, col + 1

        def make_group(grid, controls, Widget, length, start_row=0, start_col=0):
            args = [iter(controls)] * length
            l = (itertools.zip_longest(*args))
            return make_groups(grid, l, Widget, start_row=start_row, start_col=start_col)

        # Macro Dials
        row, _ = make_groups(grid, bcr.macros, None, row) 
            
        # Main Buttons
        row, _ = make_groups(grid, bcr.menu_buttons, None, row) 
 
        # Main Dials
        row, _ = make_groups(grid, bcr.dialsr, QPushButton, row)

        # Bottom Right Buttons
        row, _ = make_group(grid, bcr.command_buttons, QPushButton, 2, row-2, rowlen+1)

        # End input device specific stuff
        grid_container = QWidget()
        grid_container.setLayout(grid)
        self.layout.addWidget(grid_container)

        #self.setLayout(self.layout)

        
        # Set all controls to the current view's values
        self.reflect_all(self.interface.view)

        # Launch the update Timer
        self.update_editor()


    def init_window(self):
        """
        Initialize device-agnostic UI elements
        """
        if self.UI_initialized:
            return

        self.setWindowTitle(self.title)
        self.resize(self.size.x, self.size.y)
        self.move(self.position.x, self.position.y)
        
        self.show()
        self.UI_initialized = True


    def update_editor(self):
        """
        Polls the interface for values to display. Calls itself
        periodically using QTimer.
        """
        try:
            changes = self.interface.get_recent_changes().get() # Returns a promise
            for ID, value in changes["controls"].items():
                self.reflect(ID, value)

            with self.locks["views"]:
                self.reflect_views(changes["views"]["all"], changes["views"]["active"])
        finally:
            QTimer.singleShot(50, self.update_editor)

    def reflect(self, ID, value):
        """
        Reflects the value of a control to the widget representing it.
        """
        try:
            widget = self.control_widgets[ID]
            setters[type(widget)](widget, value)
        except KeyError:
            return

    def reflect_all(self, view):
        """
        Reflects all target values of the view on their respective widgets
        """
        for ID in self.control_widgets:
            value = self.interface.input.controls[ID].get_value()
            self.reflect(ID, value)
            
    def reflect_views(self, all_views, active_view):
        """
        Called whenever the active view in the interface has changed
        """
        # @TODO: Check for new views
#        if new_view:
#            self.view_selector.addItem(view.name)

        # @TODO: Shit's flickering
        # Reflect current View in the general UI
        if active_view.name != self.view_selector.currentItem().text():
            for index in range(self.view_selector.count()):
                item = self.view_selector.item(index)
                if item.text() == active_view.name:
                    self.view_selector.setCurrentItem(item)
                    break



    ### GUI EVENT CALLBACKS ###

    def view_changed(self, item):
        view_name = item.text()
        with self.locks["views"]:
            self.interface.switch_to_view(view_name).get()  # Forces blocking

    def value_changed(self, ID, value):
        """
        Called when the user changes the value of a Control on a widget.
        This means the targets this control is mapped to should be
        triggered.
        """
        self.controller.trigger_targets(ID, value)


    def callback_load_profile(self):
        # TODO: Reflect newly loaded profile in UI
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Setup Devices and Interface
    bcr = BCR2k(auto_start=False)
    loop = MidiLoop(auto_start=False)
    print(">> Devices started")

    interface = Interface(bcr, loop, auto_start=False)
    print(">> Interface started")
    load_profile(interface, "default.bcr")

    # Create GUI
    editor = Editor()
    print(">> Editor started")

    sinterface = Shell(interface, interface.update)

    # Create Controller
    controller = Controller(sinterface, editor)
    print(">> Controller created")

    # Initialize GUI
    editor.initialize(sinterface, controller)

    sys.exit(app.exec_())
