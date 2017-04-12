import time
import rtmidi
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

DEFAULT_IN_PORT = 4
DEFAULT_OUT_PORT = 5
FULL = 127

list_input_ports()
list_output_ports()


class ButtonType(Enum):
    MOMENTARY = 1
    TOGGLE    = 2

def clip(minval, maxval, value):
    return sorted((minval, value, maxval))[1]


def select_port(port_type="input"):
    if port_type=="input":
        list_input_ports()
    elif port_type=="output":
        list_output_ports()
    print("Select Port by number: ", end="")
    return int(input())


class Device(object):
    def __init__(self, name="unnamed", channel=7, interactive=False):
        self.name = name
        self.channel = channel 
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input,  self.inname  = open_midiinput (select_port("input"))
            self.init_callback()
        else:
            self.output = self.input = None
            self.outname = self.inname = "Uninitialized"

        self.controls = {} 

        self.listeners = []

        self.blinken = []
        self.blink_state = 0
        self.last_blink = time.time()

    def init_callback(self):
        self.input.set_callback(self.input_callback) 

    def input_callback(self, event, date=None):
        message, deltatime = event
        print("[%s] %r" % (self.name, message))

    def send(self, cc, value):
        channel_byte = CONTROL_CHANGE | (self.channel - 1)
        self.output.send_message([channel_byte, cc, value])

    def update(self, time):
        # Blinking routine
        if (time - self.last_blink) > 0.5:
            self.blink_state = 1 if self.blink_state==0 else 0 
            for blink in self.blinken:
                # @Feature: Instead of hardcoded FULL, use known value
                #           to make this compatible with encoders
                self.send(blink, self.blink_state * self.controls[blink].maxval)
            self.last_blink = time

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

class MidiLoop(Device):

    def __init__(self):
        super().__init__("MidiLoop", 1)
        self.input,  self.inname  = open_midiinput (0)
        self.output, self.outname = open_midioutput(1)
        self.init_callback()

class Control(object):

    configurable = []

    def __init__(self, ID, parent=None, minval=0, maxval=127):
        self.ID = ID
        self.parent = parent
        self.minval = minval
        self.maxval = maxval
        self._value = 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.reflect(value)
        self.parent.broadcast(self.ID, self._value)
        return self._value

    def reflect(self, value):
        self._value = clip(self.minval, self.maxval, value)
        self.parent.send(self.ID, self._value)

    def configure(self, conf):
        assert(conf.keys() == self.configurable)
        for k, v in conf.items():
            setattr(self, k, v)

    def __repr__(self):
        return "(%i) %i" % (self.ID, self.value)

    def __str__(self):
        return self.__repr__()


class Button(Control):

    configurable = ["type"]
    
    def __init__(self, ID, parent=None, type=ButtonType.MOMENTARY, **kwargs):
        super().__init__(ID, parent, **kwargs)
        self.type = type
        self.state = False
        self.ignore = 0

        self.callbacks = []

    def on(self):
        self._value = self.maxval
        self.state = True
        self.ignore = 1
        self.parent.send(self.ID, self._value)
        self.parent.broadcast(self.ID, self.state)

    def off(self):
        self._value = self.minval
        self.state = False
        self.ignore = 0
        self.parent.send(self.ID, self._value)
        self.parent.broadcast(self.ID, self.state)

    def toggle(self):
        if self.type == ButtonType.TOGGLE:
            if self.state:
                self.off()
            else:
                self.on()

    @Control.value.setter
    def value(self, value):
        """
        React to value changes on the hardware. If the button configured
        to toggle, we need to reflect that on the hardware where every
        button is actually momentary.
        """
        # When in a toggle cycle, we need to ignore certain presses:
        # 1: Turn on
        # 0: Ignore
        # 1: Ignore
        # 0: Turn off
        if self.ignore > 0:
            self.ignore -= 1
            self.parent.send(self.ID, self._value)
            return

        if self.type == ButtonType.MOMENTARY:
            self.reflect(value)
            self.parent.broadcast(self.ID, self.state)

        elif self.type == ButtonType.TOGGLE:
            if value == self.maxval and not self.state:
                self._value = self.maxval
                self.state = True
                self.ignore = 2
            elif value == self.minval and self.state:
                self._value = self.minval
                self.state = False

            self.parent.send(self.ID, self._value)
            self.parent.broadcast(self.ID, self.state)
            return self._value
    
    def reflect(self, value):
        """
        Reflects the value (True, False, 0-127) back to the hardware
        """
        if type(value) == bool:
            self.state  = value
            self._value = FULL if value else 0
        else:
            self._value = clip(self.minval, self.maxval, value)
            self.state  = self._value == self.maxval

        if self.type == ButtonType.TOGGLE:
            if self.state:
                self.ignore = 1
            else:
                self.ignore = 0
        self.parent.send(self.ID, self._value)


class Dial(Control):
    pass

class BCR2k(Device):
       
    def __init__(self):
        super().__init__("BCR2k", 7)
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)
        self.init_callback()

        self.macros = [[], [], [], []]
        for i in range(1, 32 + 1):
            self.controls[i] = Dial(i, self)
            self.macros[(i-1) // 8].append(self.controls[i])

        self.macro_buttons = [[], [], [], []]
        for i in range(33, 64 + 1):
            self.controls[i] = Button(i, self, type=ButtonType.MOMENTARY)
            self.macro_buttons[(i-33) // 8].append(self.controls[i])

        self.menu_buttons = [[],[]]
        for i in range(65, 80 + 1):
            self.controls[i] = Button(i, self, type=ButtonType.TOGGLE)
            self.macro_buttons[(i-65) // 8].append(self.controls[i])

        self.dialsc = [[] for _ in range(8)]
        self.dialsr = [[] for _ in range(3)]
        self.dials  = []
        for i in range(81, 104 + 1):
            self.controls[i] = Dial(i, self)
            self.dials.append(self.controls[i])
            z = i - 81
            self.dialsc[z % 8].append(self.controls[i])
            self.dialsr[z // 8].append(self.controls[i])

        self.command_buttons = []
        for i in range(104, 108 + 1):
            self.controls[i] = Button(i, self, type=ButtonType.MOMENTARY)
            self.command_buttons.append(self.controls[i])


    def set_control(self, ID, value, reflect=False):
        try:
            self.controls[ID].value = value
        except KeyError:
            print("Control with ID %s not found" % ID)

    def reflect(self, ID, value):
        """
        Sets the value of a control without issuing the value back
        as a broadcast from the device.
        """
        try:
            self.controls[ID].reflect(value)
        except KeyError:
            print("Control with ID %s not found" % ID)

    def input_callback(self, event, date=None):
        message, deltatime = event
        _, ID, value = message
        self.set_control(ID, value)

    def broadcast(self, ID, value):
        if (type(value) == bool and value) or type(value) != bool:
            for listener in self.listeners:
                listener.inform(self, ID, value)


class Listener(object):
    """
    Can be added to a device's listeners list
    """
    def inform(self, sender, ID, value):
        """
        Override this function.
        @sender: A Device
        @ID:     ID of the device's control that sent the...
        @value:  Transmitted value of the control
        """
        print("(%s) %s says %i is now %i" % (self, sender, ID, value))


