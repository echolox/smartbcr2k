import time
import rtmidi
from queue import Queue, Empty, Full
from threading import Thread
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

from controls import *
from util import FULL, clip, eprint, dprint

from threadshell import Shell, yield_thread

DEFAULT_IN_PORT = 3
DEFAULT_OUT_PORT = 4

DEFAULT_LOOP_IN = 10
DEFAULT_LOOP_OUT = 11 


### DEVICES

def select_port(port_type="input"):
    if port_type=="input":
        list_input_ports()
    elif port_type=="output":
        list_output_ports()
    print("Select Port by number: ", end="")
    return int(input())

class DeviceEvent(Enum):
    CC = 1


def ccc2ID(channel, cc, device_number=0):
    """
    Turns a combination of channel and cc into a Control ID.

    The ID is nothing more than an enumeration of all possible
    channel + cc combinations
    """
    return (channel - 1) * 128 + cc + device_number * 128 * 16

def ID2ccc(ID, device_number=0):
    """
    Turns a control ID into a combination of channel + cc.
    """
    ID -= device_number * 128 * 16
    return (ID // 128) + 1, ID % 128


# @TODO: Move to test suite
test_cases = [ (1, 0, 0), (1, 1, 1), (1, 127, 127),
               (2, 0, 128), (16, 127, 16 * 128 - 1) 
             ]
for channel, cc, ID in test_cases:
    assert(ccc2ID(channel, cc) == ID)
    assert(ID2ccc(ID) == (channel, cc))


class Device(ControlParent):

    def __init__(self, name="unnamed", interactive=False, auto_start=True):
        self.name = name
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input,  self.inname  = open_midiinput (select_port("input"))

        self.controls = {}

        self.blinken = []
        self.blink_state = 0
        self.last_blink = time.time()

        self.thread = Thread(target=self.main_loop, daemon=True)

        self.listener_qs = []

        self.setup_controls()

        if auto_start:
            if not (self.input and self.output):
                print("Could not start the Device thread without any input or output configured")
            else:
                self.start()

    def setup_controls(self):
        """
        Override to create and initialize controls on this Device
        """
        pass

    def add_listener(self, q):
        """
        Add a listener queue to be informed of DeviceEvents
        """
        if q not in self.listener_qs:
            self.listener_qs.append(q)

    def remove_listener(self, q):
        """
        Removes a queue from the listener qs
        """
        try:
            self.listener_qs.remove(q)
        except ValueError:
            print("(Exception): Tried to remove Queue that wasn't registered:", q)
            pass

    def send_to_device(self, ID, value):
        channel, cc = ID2ccc(ID)
        channel_byte = CONTROL_CHANGE | (channel - 1)
        self.output.send_message([channel_byte, cc, value])

    def start(self):
        """
        Start the main_loop of this device
        """
        self.thread.start()

    def main_loop(self):
        while True:
            self.update()
            yield_thread()

    def update(self):
        t = time.time()

        # Handle midi events
        while(True):
            event = self.input.get_message()
            if event:
                self.input_callback(event)
            else:
                break

        # Blinking routine
        if (t - self.last_blink) > 0.5:
            self.blink_state = 1 if self.blink_state==0 else 0 
            for blink in self.blinken:
                # @Feature: Instead of hardcoded FULL, use known value
                #           to make this compatible with encoders
                self.send(blink, self.blink_state * self.controls[blink].maxval)
            self.last_blink = t

    def get_control(self, ID):
        try:
            return self.controls[ID]
        except KeyError:
            eprint("Control with ID %s not found" % ID)


    def set_control(self, ID, value, from_input=False, inform_observers=False):
        """
        Try to set the value of a control. Depending on the flags the value
        set is reported back to:
        - the Hardware (self.input port)
        - to any observer

        from_input: The input came in through the midi port callback
                    -> If the value set is the one we expect, don't
                       report back to the input port
        inform_observers:  Whether to inform observers about the value
                    @Robustness: Only works with one observer right now

        Default assumption: We call this from the outside, which means we only really
        want to set the control value on the hardware and not get the set value reported
        back to use, which might result in an endless loop of messages. Hence the defaults
        from_input=False, inform_observers=False. Any CC messages from the hardware should
        come through the input_callback method which automatically sets the correct flags.
        """
        try:
            control = self.controls[ID]
        except KeyError:
            eprint("Control with ID %s not found" % ID)
            return None

        # The Control might implement some further logic,
        # which can result in a different value being set
        # than what we are trying to set here (think min/max-
        # values or ignoring button presses).
        real_value = control.value(value)

        # Therefore we get the real_value reported back from
        # the control which we can then reflect on the input device
        # If None was returned, the control wants us to ignore it
        if real_value is None:
            return None

        # Otherwise, depending on where the control change came from
        # inform the hardware devices or possible listeners

        # If the cc didn't come from the hardware, or if it did but the
        # real_value is different that what we tried to set the virtual
        # control to, send that cc to the input
#        if not sender == self.input or real_value != value:
        if not from_input or real_value != value:
            self.send_to_device(ID, real_value)

        # If it came from the input device or the value we tried to set is
        # different than what the virutal control assumed, issue the cc
        # to all listeners
        if inform_observers and (from_input or real_value != value):
            self.control_changed(ID, real_value)

        return real_value


    def input_callback(self, event):
        """
        Handles a Midi event from the input device
        """
        message, deltatime = event
        channel_byte, cc, value = message
        channel = (channel_byte - CONTROL_CHANGE) + 1
        ID = ccc2ID(channel, cc)
        self.set_control(ID, value, from_input=True, inform_observers=True)

    def control_changed(self, ID, value):
        """
        Inform the observers that a control value has changed by issuing
        a DeviceEvent.CC.
        """
        for listener in self.listener_qs:
            try:
                listener.put_nowait((DeviceEvent.CC, self, ID, value))
            except Full:
                print(listener, "is full")

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

class BCR2k(Device):
       
    def __init__(self, channel_offset=7, *args, **kwargs):
        # @Temp: Figure out the ports differently
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)
        self.channel_offset = channel_offset
        super().__init__("BCR2k", *args, **kwargs)


    def setup_controls(self):
        ID = ccc2ID(self.channel_offset, 0) + 1  # Because I use Channel 7, starting with cc 1
                                                 # That's gonna change eventually
        def make_controls(ID, n, Cls, *args, **kwargs):
            newly_added = []
            for i in range(n):
                c = self.controls[ID] = Cls(ID, self, *args, **kwargs)
                newly_added.append(c)
                ID += 1
            return ID, newly_added

        ID, self.macros = make_controls(ID, 32, Dial)
        ID, self.macro_buttons = make_controls(ID, 32, Button, toggle=False)
        ID, self.menu_buttons = make_controls(ID, 16, Button, toggle=True)
        ID, self.dials = make_controls(ID, 24, Dial)
        ID, self.command_buttons = make_controls(ID, 4, Button, toggle=False)

        self.dialsc = [[] for _ in range(8)]
        self.dialsr = [[] for _ in range(3)]
        row = 0
        column = 0
        for dial in self.dials:
            self.dialsr[row].append(dial)
            self.dialsc[column].append(dial)

            column += 1
            if column == 8:
                column = 0
                row += 1

    def macro_bank(self, bank):
        return self.macros[bank * 8: bank * 8 + 8]

    def macro_bank_buttons(self, bank):
        return self.macros_buttons[bank * 8: bank * 8 + 8]

    def menu_rows(self, row):
        return self.menu_buttons[row * 8: row * 8 + 8]

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



class OutputPort(object):

    """
    An output port forwards whatever messages we send into it to its connected
    midi output while also reporting back and values it receives. Example:
    Interface <-+-> Device
                |
                +-> OutputPort <-> Virtual Midi Cable <-> Ableton Live
    """
    def __init__(self, name="unnamed", interactive=False, auto_start=True):
        self.name = name
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input,  self.inname  = open_midiinput (select_port("input"))

        self.thread = Thread(target=self.main_loop, daemon=True)

        self.last_sent_values = {}
        self.listener_qs = []

        if auto_start:
            if not (self.input and self.output):
                print("Could not start the Device thread without any input or output configured")
            else:
                self.start()

    def add_listener(self, q):
        """
        Add a listener queue to be informed of DeviceEvents
        """
        if q not in self.listener_qs:
            self.listener_qs.append(q)

    def remove_listener(self, q):
        """
        Removes a queue from the listener qs
        """
        try:
            self.listener_qs.remove(q)
        except ValueError:
            print("(Exception): Tried to remove Queue that wasn't registered:", q)
            pass

    def start(self):
        """
        Start the main_loop of this device
        """
        self.thread.start()

    def main_loop(self):
        while True:
            self.update()
            yield_thread()

    def update(self):
        t = time.time()

        # Handle midi events
        event = self.input.get_message()
        if event:
            self.input_callback(event)

    def cc(self, channel, cc, value, inform_observers=False):
        """
        Forwards the CC event to the output
        """
        ID = ccc2ID(channel, cc)
        self.last_sent_values[ID] = value
        channel_byte = CONTROL_CHANGE | (channel - 1)
        self.output.send_message([channel_byte, cc, value])
        print(channel, cc, value)

    def input_callback(self, event):
        """
        Handles a Midi event from the DAW
        """
        message, deltatime = event
        channel, cc, value = message
        ID = ccc2ID(channel, cc)

        worth_reporting = False
        try: 
            if value != self.last_sent_values[ID]:
                worth_reporting = True
        except KeyError:
            pass

        if worth_reporting:
            self.received(channel, cc, value)

    def received(self, channel, cc, value):
        """
        Inform the observers that a control value has changed by issuing
        an OutputEvent.CC.
        """
        for listener in self.listener_qs:
            try:
                listener.put_nowait((OutputEvent.CC, self, channel, cc, value))
            except Full:
                print(listener, "is full")

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


class OutputEvent(Enum):
    CC = 1


class MidiLoop(OutputPort):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_midiinput (DEFAULT_LOOP_IN)
        self.output, self.outname = open_midioutput(DEFAULT_LOOP_OUT)
        super().__init__("MidiLoop", *args, **kwargs)



if __name__ == "__main__":
    list_input_ports()
    list_output_ports()
    bcr = BCR2k(auto_start=False)
    sbcr = Shell(bcr, bcr.update)

    q = Queue()
    sbcr.add_listener(q)
    sbcr.set_control(90, 127)
    print(bcr)
    c = sbcr.get_control(91).get()
    print(c)

    try:
        while True:
            try:
                event, *data = q.get_nowait()
                print(event.name, data)
            except Empty:
                pass
    except KeyboardInterrupt:
        pass

    bcr.remove_listener(q)
