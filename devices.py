# TODO: Move devices into their own package
import time

from enum import Enum
from queue import Empty, Full
from threading import Thread

import rtmidi
from rtmidi.midiconstants import CONTROL_CHANGE
from rtmidi.midiutil import open_midioutput, open_midiinput, list_available_ports, list_output_ports, list_input_ports

from controls import Dial, Button, ControlParent
from util import FULL, clip, eprint, dprint, iprint

from threadshell import Shell, yield_thread

# TODO: Figure out correct ports based on device names
DEFAULT_IN_PORT = 3
DEFAULT_OUT_PORT = 4

DEFAULT_LOOP_IN = 10
DEFAULT_LOOP_OUT = 11 

BLINK_INTERVAL = 0.3  # in seconds

def select_port(port_type="input"):
    """
    Convenience function to select midi ports interactively
    """
    if port_type=="input":
        list_input_ports()
    elif port_type=="output":
        list_output_ports()
    print("Select Port by number: ", end="")
    return int(input())


class DeviceEvent(Enum):
    """
    The type of events a Device would inform its listeners about.
    """
    CC = 1


def ccc2ID(channel, cc, page=0, device_number=0):
    """
    Turns a combination of channel and cc into a Control ID.

    The ID is nothing more than an enumeration of all possible
    channel + cc combinations
    >>> ccc2ID(1, 0)
    0
    >>> ccc2ID(1, 1)
    1
    >>> ccc2ID(1, 127)
    127
    >>> ccc2ID(2, 0)
    128 
    >>> ccc2ID(16, 127)
    2047 
    """
    return ((channel - 1) * 128 + cc + device_number * 128 * 16) + (page * 128 * 16)


def ID2ccc(ID, device_number=0):
    """
    Turns a control ID into a combination of channel + cc.
    >>> ID2ccc(0)
    1, 0
    >>> ID2ccc(1)
    1, 1
    >>> ID2ccc(127)
    1, 127
    >>> ID2ccc(128)
    2, 0
    >>> ID2ccc(2047)
    16, 127
    """
    ID -= device_number * 128 * 16
    ID %= 128 * 16
    return (ID // 128) + 1, ID % 128


# TODO: Unify the common functions of Device and OutputPort into a Parent class

class Device(ControlParent):

    def __init__(self, name="Unnamed Device", interactive=False, auto_start=True):
        self.name = name
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input,  self.inname  = open_midiinput (select_port("input"))

        # The controls on this device are collected in a map with Control.ID -> Control object
        # For any object using this Device we abstract away which Control is mapped to which
        # Midi CC value and just handle them through their IDs. This enables us, among other things,
        # to handle more controls than actually available on the hardware (see paging below).
        self.controls = {}

        # A Device can simulate pages of controls. Which page is active is set by this attribute.
        # On page 0 the controls are mapped as usual. Further (virtual) controls are handled with
        # IDs offset by the page number times the total amount of controls possible (16 * 128, 16
        # channels, 128 CC each). Whenever we interact with the hardware device (receiving input,
        # sending values back for reflection) we check whether that control is part of the current
        # page.
        # EG.: A Dial on CC 10 has the ID 10. A second Dial on page 2 is mapped to CC 10 as well,
        # but with the ID 10 + 2048 = 2058. Both are effectively controlled with the same Dial on
        # the hardware device.
        # Any object issuing changes to the device doesn't need to know both controls are mapped
        # to the same hardware dial, but the Device decides whether to forward values that are 
        # assumed by these controls to the hardware device based on which page is active.
        self._page = 0

        # It can be useful to let controls blink. We control the state and the last time we
        # blinked in these attributes. We control blinking here instead of implementing it in
        # the controls because blinking is merely a "cosmetic" thing. On a hardware device,
        # turning (for example) the light of a button on means sending a Midi message with the
        # value 127 to that control as a CC message. We don't actually want the Control object
        # to assume that value though.
        self.blink_state = False
        self.last_blink = time.time()

        # The Device's main_loop is supposed to run in its own thread. It is only started if
        # the object is constructed with auto_start = True of if the start method is called
        self.thread = Thread(target=self.main_loop, daemon=True)

        # Listeners to this Device register Queue objects to be informed of Events
        self.listener_qs = set()

        # Create the controls this device actually has
        self.setup_controls()

        if auto_start:
            if not (self.input and self.output):
                print("Could not start the Device thread without any input or output configured")
            else:
                self.start()

    def setup_controls(self):
        """
        Override to create and initialize controls on this Device.
        """
        pass

    def add_listener(self, q):
        """
        Add a listener queue to be informed of DeviceEvents
        """
        self.listener_qs.add(q)

    def remove_listener(self, q):
        """
        Removes a queue from the listener qs
        """
        try:
            self.listener_qs.remove(q)
        except KeyError:
            eprint("(Exception): Tried to remove Queue that wasn't registered:", q)

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, p):
        """
        Any value than what equates to a True sets it to 1, else 0
        Calls page_update() after setting
        """
        self._page = 1 if p else 0
        self.page_update()

    def pageflip(self):
        """
        Flips the page between 0 and 1 and calls page_update() afterwards
        """
        self._page = 1 if self._page == 0 else 0
        self.page_update()

    def page_update(self):
        """
        Override this to control what gets updated on a pageflip. This is necessary because
        you might want to only virtualize a subset of the device's controls (e.g. a BCR2k's
        main 24 dials but not the rest of the controls).
        Use this method to synchronize the Control values and what the hardware displays.
        You'll make use of the cc method for this.
        """
        pass

    def control_on_active_page(self, control):
        """
        Check whether the control is on the active page. If you plan to only page
        a subset of the controls you'll want to override this for the exceptions.
        """
        return control.ID in range(self.page * 16 * 128, (self.page + 1) * 16 * 128)


    def cc(self, ID, value, ignore_page=False):
        """
        Send a CC message to the device's midi port. The ID will be transformed
        into the (channel, cc) combination. If the ID is not mapped in the current
        page, this call is ignored unless ignore_page is set to True which forces
        the message out.
        """
        if ignore_page or self.control_on_active_page(self.controls[ID]):
            channel, cc = ID2ccc(ID)
            channel_byte = CONTROL_CHANGE | (channel - 1)
            self.output.send_message([channel_byte, cc, value])

    def send_to_device(self, ID, value):
        """
        This is what Control objects call to effectively send their value to the hardware
        """
        self.cc(ID, value)

    def start(self):
        """
        Start the main_loop of this device in its own thread
        """
        self.thread.start()

    def main_loop(self):
        """
        The real work happens in update()
        """
        while True:
            self.update()
            yield_thread()

    def update(self):
        """
        Within one update cycle we want to
        - Handle midi events from the input port
        - Update the blinking on the device
        """
        # Handle midi events
        while(True):
            event = self.input.get_message()
            if event:
                self.input_callback(event)
            else:
                break

        # Blinking routine
        t = time.time()
        if (t - self.last_blink) > BLINK_INTERVAL:
            self.blink_state = not self.blink_state
            for control in filter(lambda c: c.blink, self.controls.values()):
                self.cc(control.ID, self.blink_state * control.maxval)
            self.last_blink = t

    def set_control(self, ID, value, from_input=False, inform_listeners=False):
        """
        Try to set the value of a control. Depending on the flags the value is reported back to:
        - the hardware (self.input port)
        - to any listener (self.listener_qs)

        from_input: The input came in through the midi port callback
                    -> If the value set is the one we expect, don't
                       report back to the input port
        inform_listeners:  Whether to inform listeners about the value
                    @Robustness: Only works with one listener right now
                                 Gotta add some exclude functionality

        Default assumption: We call this from the outside, which means we only really
        want to set the control value on the hardware and not get the set value reported
        back to us, which might result in an endless loop of messages. Hence the defaults
        from_input=False, inform_listeners=False. Any CC messages from the hardware should
        come through the input_callback method which automatically sets the correct flags.
        """
        try:
            control = self.controls[ID]
        except KeyError:
            eprint("Control with ID %s not found" % ID)
            return None

        # The Control might implement some further logic which can result in a different
        # value being set than what we are trying to set here (think min/max-values or
        # ignoring button presses to simulate toggle behaviour).
        real_value = control.set_value(value)
        # Therefore we get the real_value reported back from the control which we can
        # then reflect on the input device. If None was returned, the control wants us
        # to ignore it
        if real_value is None:
            return None

        # Otherwise, depending on where the control change came from inform the hardware
        # device or possible listeners

        # If the cc didn't come from the hardware, or if it did but the real_value is
        # different that what we tried to set the virtual control to, send that cc to
        # the input. The cc method checks whether the control is on the active page.
        if not from_input or real_value != value:
            self.cc(ID, real_value)

        # If it came from the input device or the value we tried to set is different
        # than what the virutal control assumed, issue the cc to all listeners
        if inform_listeners and (from_input or real_value != value):
            self.control_changed(ID, real_value)

        return real_value

    def input_callback(self, event):
        """
        Handles a Midi event from the input device.
        """
        message, deltatime = event
        channel_byte, cc, value = message
        channel = (channel_byte - CONTROL_CHANGE) + 1
        ID = ccc2ID(channel, cc, self.page)

        # @TODO: More robust way of handling controls that only exist
        #        on one page.
        if ID not in self.controls:
            ID = ccc2ID(channel, cc, page=0)
        self.set_control(ID, value, from_input=True, inform_listeners=True)

    def control_changed(self, ID, value):
        """
        Inform the listeners that a control value has changed by issuing a DeviceEvent.CC.
        Can also be called by controls directly (due to subclassing from Controlparent) in
        case there is some logic making Controls change their value on their own.
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
    """
    An implementation of the Behringer BCR 2000 Midi Controller. Configure your hardware like so:
    - Set all controls to CC on channel 1 (eventually, right now 7 because my config is stupid and old)
    - From the top left down to the bottom right, configure your Dials and Buttons to send out
      CC values starting with 0 (eventually, right now 1 because my config is stupid and old)
    - Set all buttons to momentary
    - Set all value ranges from 0 to 127
    """
       
    def __init__(self, channel_offset=7, *args, **kwargs):
        # @Temp: Figure out the ports differently
        self.output, self.outname = open_midioutput(DEFAULT_OUT_PORT)
        self.input,  self.inname  = open_midiinput (DEFAULT_IN_PORT)

        # Typically you would configure your BCR2k to start on channel 1
        # Since I don't (or maybe didn't depending on when you read this)
        # I needed a way to offset to channel 7 where my main page on the
        # device starts.
        self.channel_offset = channel_offset
        super().__init__("BCR2k", *args, **kwargs)

    def setup_controls(self):
        ID = ccc2ID(self.channel_offset, 0) + 1  # Because I use Channel 7, starting with cc 1
                                                 # That's gonna change eventually

        # A helper function to create n controls of the given Class with some options
        # Returns a list of newly created controls
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

        # We'll only paginate the main dials to get 48 instead of just 24
        ID2 = ID + 16 * 128
        ID, self.dials = make_controls(ID, 24, Dial)
        _,  page2_dials = make_controls(ID2, 24, Dial)
        self.dials.extend(page2_dials)

        # Dials by column and Dials by row
        self.dialsc = [[] for _ in range(8)]
        self.dialsr = [[] for _ in range(6)]
        row = 0
        column = 0
        for dial in self.dials:
            self.dialsr[row].append(dial)
            self.dialsc[column].append(dial)

            column += 1
            if column == 8:
                column = 0
                row += 1

        ID, self.command_buttons = make_controls(ID, 4, Button, toggle=False)

    def macro_bank(self, bank):
        """
        Returns a list of 8 macros on the zero-indexed bank (0, 1, 2, 3).
        """
        return self.macros[bank * 8: bank * 8 + 8]

    def macro_bank_buttons(self, bank):
        """
        Analog to macro_bank but for its buttons.
        """
        return self.macros_buttons[bank * 8: bank * 8 + 8]

    def menu_rows(self, row):
        """
        Returns the row of buttons below the macro dials. Zero-indexed
        """
        return self.menu_buttons[row * 8: row * 8 + 8]

    def page_update(self):
        """
        We only paginate the main dials so depending on the active page we only want to
        update the main dials that are actively shown.
        """
        p = self.page
        for dial in self.dials[p*24:p*24 + 24]:
            self.cc(dial.ID, dial.get_value())

    def control_on_active_page(self, control):
        """
        Again, since we only paginate the main dials all other controls are always on the
        active page.
        """
        if control in self.dials:
            return super().control_on_active_page(control)
        else:
            return True


# TODO: Compare to Device, can we make a parent Class for both?
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

    def cc(self, channel, cc, value, inform_listeners=False):
        """
        Forwards the CC event to the output
        """
        ID = ccc2ID(channel, cc)
        self.last_sent_values[ID] = value
        channel_byte = CONTROL_CHANGE | (channel - 1)
        self.output.send_message([channel_byte, cc, value])

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


class VirtualMidi(OutputPort):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_midiinput (DEFAULT_LOOP_IN)
        self.output, self.outname = open_midioutput(DEFAULT_LOOP_OUT)
        super().__init__("VirtualMidi", *args, **kwargs)

        self.ignore_daw = kwargs.get("ignore_daw", False)
            
    def input_callback(self, event):
        if not self.ignore_daw:
            super().input_callback(event)


if __name__ == "__main__":
    list_input_ports()
    list_output_ports()
    bcr = BCR2k(auto_start=False)
    sbcr = Shell(bcr, bcr.update)

    from queue import Queue
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
