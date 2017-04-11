import time
import rtmidi
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

DEFAULT_IN_PORT = 4
DEFAULT_OUT_PORT = 5
FULL = 127


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
                self.send(blink, self.blink_state * FULL)            
            self.last_blink = time


class MidiLoop(Device):

    def __init__(self):
        super().__init__("MidiLoop", 7)
        self.output, self.outname = open_midioutput(1)
        self.input,  self.inname  = open_midiinput (0)
        self.init_callback()

class Control(object):

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
        self._value = clip(self.minval, self.maxval, value)
        self.parent.send(self.ID, self._value)
        # @Fix: Corrected value not accepted by hardware
        return self._value


class Button(Control):
    
    def __init__(self, ID, parent=None, type=ButtonType.MOMENTARY, **kwargs):
        super().__init__(ID, parent, **kwargs)
        self.type = type
        self.state = False
        self.ignore = 0

        self.callbacks = []

    def fire(self):
        for call in self.callbacks:
            call()

    @Control.value.setter
    def value(self, value):
        if self.ignore > 0:
            self.ignore -= 1
            self.parent.send(self.ID, self._value)
            return

        if self.type == ButtonType.MOMENTARY:
            Control.value.fset(self, value)
            if value == self.maxval:
                self.fire()

        elif self.type == ButtonType.TOGGLE:
            if value == self.maxval and not self.state:
                self._value = self.maxval
                self.state = True
                self.ignore = 2
            elif value == self.minval and self.state:
                self._value = self.minval
                self.state = False

            self.parent.send(self.ID, self._value)
            return self._value



class Dial(Control):
    pass

class BCR2k(Device):
       
    def __init__(self):
        super().__init__("BCR2k", 7)
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)
        self.init_callback()

        self.controls[81] = Dial(81, self)
        self.controls[65] = Button(65, self, type=ButtonType.MOMENTARY)
        self.controls[66] = Button(66, self, type=ButtonType.TOGGLE)

    def set_control(self, ID, value):
        try:
            self.controls[ID].value = value
        except KeyError:
            print("Control with ID %s not found" % ID)

    def input_callback(self, event, date=None):
        message, deltatime = event
        _, ID, value = message
        print("[%s!!] %r" % (self.name, message))

        self.set_control(ID, value)


def test(bcr):
    bcr.send(3, 127)
    bcr.send(4, 0)
    bcr.send(5, 0)

    bcr.set_control(81, 127)
    bcr.set_control(65, 127)

#    bcr.blinken.append(65)

    try:
        while True:
            bcr.update(time.time())
    except KeyboardInterrupt:
        print("Exiting...")

def fun(bcr):
    x = 0
    import math
    import time
    while True:
        time.sleep(0.05)
        for i in range(81, 104 + 1):
            v = min(math.sin(x - (i-81)*0.1) * 64 + 64, 127)
            bcr.send(i, v)
        x += 0.2

if __name__ == "__main__":
    bcr = BCR2k()
    loop = MidiLoop()

#    fun(bcr)
    test(bcr)
