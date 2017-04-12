import time
import rtmidi
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE
from collections import defaultdict

from devices import BCR2k, MidiLoop, Listener


class Target(object):
    """
    A mapping target. In the Interface, the IDs of the input
    device are mapped to targets.    """
    def __init__(self, name):
        self.name = name

    def trigger(self, value):
        """
        Their trigger method is then called
        with the value transmitted by the Control.
        """
        raise NotImplemented


class SwitchView(Target):
    """
    Issues the command to switch to a preconfigured View
    when triggered.
    """
    def __init__(self, name, interface, view):
        self.name = name
        self.interface = interface
        self.view = view

    def trigger(self, value):
        self.interface.switch_to_view(self.view)


class Parameter(Target):
    """
    A type of target that simply maps the incoming value to a
    Control Change midi signal on the configured (output) device.
    Button values are (for now) hardcoded to 0 for Off and 127 for On.
    """
    def __init__(self, name, device, cc, initial=0, is_button=False):
        self.name = name
        self.device = device
        self.cc = cc
        self.value = initial
        self.is_button = is_button

    def trigger(self, value):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if self.is_button:
            if value:
                value = 127
            else:
                value = 0
        self.value = value
        self.device.send(self.cc, self.value)


TargetsWithValues = [Parameter,
                    ]


class Exhausted(Exception):
    pass

class ParameterMaker(object):
    """
    Produces Targets of the type Parameter. Everytime a new target is
    requested it assigns that target the next available CC.
    """
    def __init__(self, output_device, channel, prefix="CC", first_cc=1, expand=True):
        self.device = output_device
        self.channel = channel
        self.next_cc = first_cc
        self.prefix = prefix
        self.expand = expand

        self.exhausted = False

    def make(self, is_button=False):
        if self.exhausted:
            raise Exhausted

        name = "%s_%i" % (self.prefix, self.next_cc)
        t = Parameter(name, self.device, self.next_cc, is_button=is_button)        
        self.next_cc += 1
        if self.next_cc > 128:
            if self.expand and self.channel < 16:
                self.next_cc = 1
                self.channel += 1
            else:
                self.exhausted = True
        return t

class ViewMaker(object):

    def __init__(self, interface, prefix="V"):
        self.interface = interface
        self.next_index = 1
        self.prefix = prefix

    def make(self, view=None):
        name = "%s_%i" % (self.prefix, self.next_index)
        if not view:
            view = View(name=name)
        t = SwitchView(name, self.interface, view)
        self.next_index += 1
        return t, view


class View(object):
    """
    A View is made up of two components:
    - A configuration: How the buttons and dials on the input device should behave
    - A Map: Connects the input device's controls (by their ID) to Targets like
             Parameters, Commands etc. from which their current values can also
             be infered.
    When triggerivating a View, the input Device needs to be reconfigured and the
    values of each mapped target transmitted to that device for it to show those
    values on the hardware.
    """
    def __init__(self, name="Unnamed View"):
        self.name = name
        # Map IDs of a device's controls to configurations like
        # - Buttons: toggle vs momentary
        # - Maxvals / Minvals
        self.configuration = {}

        # Map IDs of a device's controls to Parameters
        self.map = defaultdict(list)

    def find_IDs_by_target(self, vtarget):
        """
        Make a list of IDs on this view mapped to the provided target.
        """
        IDs = []
        for ID, vtargets in self.map.items():
            for target in vtargets:
                if target == vtarget:
                    IDs.append(ID)
        return IDs

    def map_this(self, ID, t):
        """
        Add a mapping from the ID to the target
        """
        self.map[ID].append(t)

    def unmap(self, ID):
        """
        Remove all mappings of the provided ID
        """
        self.map[ID] = []

    def unmap_target(self, target):
        """
        Remove all mappings to the provided target
        """
        for targets in self.map.values():
            if target in targets: targets.remove(target) 

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


class Interface(Listener):
    """
    The Interface connects an input device with an output device by tunneling
    transmitted values from the input through its currently triggerive View.
    This view can transform CC messages, issue commands like switching to a
    different View or other meta functions. For a simple mapped CC parameter,
    the - possibly modified - value is sent to the Interface's output device.

    Changes communicated from the output device (e.g. automation in Ableton Live
    needs to be reflected on the hardware) is sent back to the input device,
    depending on if any of its controls are currently mapped to the changed Parameter.
    """
    def __init__(self, devin, devout, initview=None):
        """
        Initialize the Interface with the provided input and output device
        and a View. If no View is provided and empty View will be produced.

        The Interface attaches itself as a listener to both input and output
        devices.
        """
        self.input = devin
        self.output = devout
        self.targets = {}
        self.view = initview if initview else View("Init")
        self.views = [self.view]

        self.input.listeners.append(self)
        self.output.listeners.append(self)

        self.parameter_maker = ParameterMaker(self.output, 1)
        self.view_maker      = ViewMaker(self)


    def set_value(self, target, value, input_only=False, exclude_IDs=None):
        """
        Sets the value of a Target. The value is typically communicated
        to both input and output device. This makes it possible to automate
        values from within the interface and having that reflect on both
        the input device (hardware) and the output device (DAW).

        We a value change was communicated from the output device (e.g.
        DAW automation) we only want to inform the input device about the
        new value. In that case, use the input_only flag. If you don't, a
        feedback loop might occur.

        Should not be called because a value directly on the input changed.
        That's what target.trigger() is for.
        """
        # Inform input controls mapped to this target about the change
        self.reflect_value(target, value)

        # Prevent feedback loop, for example if the source of the
        # new value was the output device itself
        if input_only:
            # We still need to reflect the value change in the target
            # but without performing the associated triggerion
            target.value = value
        else:
            target.trigger(value) 

    def reflect_value(self, target, value, exclude_IDs=None):
        """
        Inform the input device of a value change, possibly excluding
        certain IDs. Only controls mapped to the given target will
        be updated.
        """
        for ID in self.view.find_IDs_by_target(target):
            if not exclude_IDs or ID not in exclude_IDs:
                self.input.reflect(ID, value)


    def reflect_all(self):
        """
        Based on the current view, reflect all values to the input device
        """
        for ID, targets in self.view.map.items():
            for target in targets:
                try:
                    # Does the target have a value type?
                    getattr(target, "value")
                    # If so, no exception was triggered
                    self.input.reflect(ID, target.value)
                except AttributeError:
                    pass

    def switch_to_view(self, view):
        """
        Switches to the provided view. If this is a new view it will
        be added to the Interface's view catalog and all targets of
        that view will be added to the total list of targets.
        """
        print("[%s] Switching to %s" % (self, view))
        self.view = view
        if view not in self.views:
            self.views.append(view)
            for ID, targets in view.map.items():
                for target in targets:
                    self.add_target(target)
        self.reflect_all()

    def add_target(self, target):
        """
        Add a configured target. This method checks for duplicates and
        ignores them if detected.
        """
        if target.name in self.targets:
            print("Target with same name already exists! Ignoring...")
            return
        self.targets[target.name] = target

    def quick_parameter(self, ID, is_button=False):
        """
        Quickly map the provided ID to a Parameter by creating a new
        Parameter target using the class's own maker
        """
        t = self.parameter_maker.make(is_button=is_button)
        self.add_target(t)
        self.view.map_this(ID, t)
        return t

    def quick_view(self, ID, to_view=None, on_view=None):
        """
        Quickly map the provided ID to a switch view command with either
        the provided view or a newly created view
        """
        t, view = self.view_maker.make(to_view)
        if on_view:
            on_view.map_this(ID, t)
        else:
            self.add_target(t)
            self.view.map_this(ID, t)
        return t, view

    def inform(self, sender, ID, value):
        """
        Callback method whenever the input or output devices produce
        messages to consume (input -> hardware -> controls, output ->
        daw -> automation).
        """
        try:
            targets = self.view.map[ID]
        except KeyError:
            print("No target configured for ID %i" % ID)
            return

        for target in targets:
            if sender == self.input:
                # Perform the triggerion of the target. This might send a
                # message to the output device but could also be a meta
                # command like switching views
                target.trigger(value)
                # Multiple input controls might be mapped to this
                # so let's reflect on the input device but exclude the
                # ID that issued the value change
                self.reflect_value(target, value, exclude_IDs=[ID])
            elif sender == self.output:
                # Just reflect the value in both target and on the input device
                self.set_value(target, value, input_only=True)

    def __repr__(self):
        return "Interface"

    def __str__(self):
        return self.__repr__()


##################################


def test(i):
    t = i.quick_parameter(1)
    for macro in i.input.macros[0][1:]:
        i.view.map_this(macro.ID, t)

    init_view = i.view
    _, second_view = i.quick_view(105)
    i.quick_view(105, to_view=init_view, on_view=second_view)

    i.quick_parameter(81)
    i.quick_parameter(82)
    t = i.quick_parameter(83)
    i.view.map_this(84, t)

    i.switch_to_view(second_view)

    i.quick_parameter(81)
    i.quick_parameter(82)
    t = i.quick_parameter(83)
    i.view.map_this(84, t)

    i.switch_to_view(init_view)

    while True:
        bcr.update(time.time())


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

    interface = Interface(bcr, loop)

#    fun(bcr)
    test(interface)
