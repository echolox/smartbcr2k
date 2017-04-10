import time
import rtmidi
from rtmidi.midiconstants import CONTROL_CHANGE

from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

DEFAULT_IN_PORT = 4
DEFAULT_OUT_PORT = 5
FULL = 127

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


class BCR2k(Device):
       
    def __init__(self):
        super().__init__("BCR2k", 7)
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)
        self.init_callback()


def test(bcr):
    bcr.send(3, 127)
    bcr.send(4, 0)
    bcr.send(5, 0)

    bcr.blinken.append(65)

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
        v = min(math.sin(x) * 64 + 64, 127)
        bcr.send(3, v)
        x += 0.2

if __name__ == "__main__":
    bcr = BCR2k()
    loop = MidiLoop()

    test(bcr)
