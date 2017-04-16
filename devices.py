import time
import rtmidi
from queue import Queue
from threading import Thread
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

from controls import *
from util import FULL, clip

DEFAULT_IN_PORT = 3
DEFAULT_OUT_PORT = 4



### DEVICES

def select_port(port_type="input"):
    if port_type=="input":
        list_input_ports()
    elif port_type=="output":
        list_output_ports()
    print("Select Port by number: ", end="")
    return int(input())


class Device(ControlParent):

    def __init__(self, name="unnamed", channel=7, interactive=False, auto_start=True):
        self.name = name
        self.channel = channel 
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input,  self.inname  = open_midiinput (select_port("input"))

        self.controls = {} 

        self.listeners = []

        self.blinken = []
        self.blink_state = 0
        self.last_blink = time.time()

        self.thread = Thread(target=self.main_loop, daemon=True)
        if auto_start:
            if not (self.input and self.output):
                print("Could not start the Device thread without any input or output configured")
            else:
                self.start()

    def input_callback(self, event):
        """
        Override this to respond to midi events
        """
        message, deltatime = event
        print("[%s] %r" % (self.name, message))

    def send_to_device(self, cc, value):
        channel_byte = CONTROL_CHANGE | (self.channel - 1)
        self.output.send_message([channel_byte, cc, value])

    def start(self):
        """
        Start the main_loop of this device
        """
        self.thread.start()

    def main_loop(self):
        while True:
            t = time.time()

            # Handle midi events
            event = self.input.get_message()
            if event:
                self.input_callback(event)

            # Blinking routine
            if (t - self.last_blink) > 0.5:
                self.blink_state = 1 if self.blink_state==0 else 0 
                for blink in self.blinken:
                    # @Feature: Instead of hardcoded FULL, use known value
                    #           to make this compatible with encoders
                    self.send(blink, self.blink_state * self.controls[blink].maxval)
                self.last_blink = t

            time.sleep(0)  # YIELD THREAD

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

class MidiLoop(Device):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_midiinput (0)
        self.output, self.outname = open_midioutput(1)
        super().__init__("MidiLoop", 1, *args, **kwargs)

class BCR2k(Device):
       
    def __init__(self, *args, **kwargs):
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)
        super().__init__("BCR2k", 7, *args, **kwargs)

        self.macros = [[], [], [], []]
        for i in range(1, 32 + 1):
            self.controls[i] = Dial(i, self)
            self.macros[(i-1) // 8].append(self.controls[i])

        self.macro_buttons = [[], [], [], []]
        for i in range(33, 64 + 1):
            self.controls[i] = Button(i, self, toggle=False)
            self.macro_buttons[(i-33) // 8].append(self.controls[i])

        self.menu_buttons = [[],[]]
        for i in range(65, 80 + 1):
            self.controls[i] = Button(i, self, toggle=True)
            self.menu_buttons[(i-65) // 8].append(self.controls[i])

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
        for i in range(105, 108 + 1):
            self.controls[i] = Button(i, self, toggle=False)
            self.command_buttons.append(self.controls[i])


    def set_control(self, ID, value):
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

    def input_callback(self, event):
        message, deltatime = event
        _, ID, value = message
        self.set_control(ID, value)

    def control_changed(self, ID, value):
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


if __name__ == "__main__":
    list_input_ports()
    list_output_ports()
    bcr = BCR2k(auto_start=True)

    while True:
        try:
            pass
        except KeyboardInterrupt:
            break
