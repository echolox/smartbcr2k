import statistics
import time

from enum import Enum
from queue import Full, Queue
from threading import Thread

import rtmidi
from rtmidi.midiconstants import CONTROL_CHANGE, SONG_START, SONG_CONTINUE, SONG_STOP, TIMING_CLOCK
from rtmidi.midiutil import open_midioutput, open_midiinput, get_api_from_environment, \
    list_output_ports, list_input_ports

from util import eprint
from util.threadshell import yield_thread


BLINK_INTERVAL = 0.3  # in seconds


class PortNotFoundError(Exception):
    pass


def open_port_by_name(name, inout):
    if inout == "input":
        # noinspection PyUnresolvedReferences,PyUnresolvedReferences
        midiio = rtmidi.MidiIn(get_api_from_environment(rtmidi.API_UNSPECIFIED))
        open_func = open_midiinput
    elif inout == "output":
        # noinspection PyUnresolvedReferences,PyUnresolvedReferences
        midiio = rtmidi.MidiOut(get_api_from_environment(rtmidi.API_UNSPECIFIED))
        open_func = open_midioutput
    else:
        eprint("Call with either input or output as inout argument")
        raise PortNotFoundError

    ports = midiio.get_ports()
    # noinspection PyUnresolvedReferences
    type_ = " input" if isinstance(midiio, rtmidi.MidiIn) else " ouput"

    if ports:
        for portno, pname in enumerate(ports):
            if name.lower() in pname.lower():
                return open_func(portno)
        raise PortNotFoundError
    else:
        print("No MIDI{} ports found.".format(type_))
        raise PortNotFoundError


def select_port(port_type="input"):
    """
    Convenience function to select midi ports interactively
    """
    if port_type == "input":
        list_input_ports()
    elif port_type == "output":
        list_output_ports()
    print("Select Port by number: ", end="")
    return int(input())


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


class Port(object):
    """
    Common parent to Device and Output Port. 
    """

    def __init__(self, name="Unnamed Port", interactive=False, auto_start=True):
        self.name = name
        if interactive:
            self.output, self.outname = open_midioutput(select_port("output"))
            self.input, self.inname = open_midiinput(select_port("input"))

        # The port's main_loop is supposed to run in its own thread. It is only started if
        # the object is constructed with auto_start = True or if the start method is called
        self.thread = Thread(target=self.main_loop, daemon=True)

        # Listeners to this Device register Queue objects to be informed of Events
        self.listener_qs = set()

        if auto_start:
            if not (self.input and self.output):
                print("Could not start the Device thread without any input or output configured")
            else:
                self.start()

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
        pass

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


class DeviceEvent(Enum):
    """
    The type of events a Device would inform its listeners about.
    """
    CC = 1


class Device(Port):
    def __init__(self, *args, **kwargs):
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

        # Create the controls this device actually has
        self.setup_controls()

        super().__init__(*args, **kwargs)

    def setup_controls(self):
        """
        Override to create and initialize controls on this Device.
        """
        pass

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

    def update(self):
        """
        Within one update cycle we want to
        - Handle midi events from the input port
        - Update the blinking on the device
        """
        # Handle midi events
        while True:
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

    def set_control(self, ID, value, from_input=False, inform_listeners=False, force=False):
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
        force: Assures the value we try to set the control to is actually assumed,
               circumventing any logic the control might implement. This is necessary
               for actions like recalling previous values and bringing the control back
               into that state.

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
        real_value = control.set_value(value, force=force)

        #        iprint(ID == 873, self, value, real_value)
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
        # TODO: Actually figure out whether the message is a CC, Note, Timing or something else
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


class OutputEvent(Enum):
    CC = 1
    ClockStart = 2
    ClockContinue = 3
    ClockStop = 4
    ClockQuarterTick = 5


class OutputPort(Port):
    """
    An output port forwards whatever messages we send into it to its connected
    midi output while also reporting back and values it receives. Example:
    OutputPort <-> Virtual Midi Cable Driver <-> Ableton Live (or other DAW)
    """

    def __init__(self, *args, **kwargs):
        self.last_sent_values = {}
        super().__init__(*args, **kwargs)
        self.input.ignore_types(timing=False)

        self.clock_count = 0

    def update(self):
        # Handle midi events
        event = self.input.get_message()
        if event:
            self.input_callback(event)

    def cc(self, channel, cc, value):
        """
        Forwards the CC event to the output
        """
        ID = ccc2ID(channel, cc)
        self.last_sent_values[ID] = value
        channel_byte = CONTROL_CHANGE | (channel - 1)
        self.output.send_message([channel_byte, cc, value])

    #        print(channel, cc, value)

    def input_callback(self, event):
        """
        Handles a Midi event from the DAW
        """
        message, deltatime = event


        t = message[0]
        if t == SONG_START:
            self.clock_count = 0
            self.inform_listeners(OutputEvent.ClockStart)
        elif t == SONG_CONTINUE:
            self.inform_listeners(OutputEvent.ClockContinue)
        elif t == SONG_STOP:
            self.inform_listeners(OutputEvent.ClockStop)
        elif t == TIMING_CLOCK:
            self.clock_count += 1
            if (self.clock_count == 24):
                self.clock_count = 0
                self.inform_listeners(OutputEvent.ClockQuarterTick)

        else:  # TODO: Filter for Note events
            try:
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
            except Exception as e:
                eprint(self, e)

    def received(self, channel, cc, value):
        """
        Inform the observers that a control value has changed by issuing
        an OutputEvent.CC.
        """
        self.inform_listeners(OutputEvent.CC, self, channel, cc, value)

    def inform_listeners(self, *data):
        for listener in self.listener_qs:
            try:
                listener.put_nowait(data)
            except Full:
                print(listener, "is full")

