import os
import time
import rtmidi
import json
import sys
import argparse
import traceback

from threading import Thread
from queue import Queue, Empty, Full
from importlib import import_module

from copy import copy
from enum import Enum
from collections import namedtuple
from collections import defaultdict as ddict

from rtmidi.midiconstants import CONTROL_CHANGE

from colorama import Fore, Back, Style, init
init(autoreset=True)

from util import keys_to_ints, unify, eprint, iprint
from util.threadshell import Shell, yield_thread 
from util.interactive import interact

from targets import get_target, Parameter, SwitchView, ValueTarget
from devices import DeviceEvent, BCR2k, VirtualMidi
from modifiers import get_modifier


class Exhausted(Exception):
    pass


class ParameterMaker(object):
    """
    Produces Targets of the type Parameter. Everytime a new target is
    requested it assigns that target the next available CC.
    """

    # These CC values could cause problems when mapped to
    forbidden = [123]

    def __init__(self, interface, channel, prefix="CC", first_cc=1, expand=True):
        self.interface = interface
        self.channel = channel
        self.next_cc = first_cc
        self.prefix = prefix
        self.expand = expand

        self.exhausted = False

    def make(self, is_button=False):
        if self.exhausted:
            raise Exhausted

        name = "%s_%i" % (self.prefix, self.next_cc)
        t = Parameter(name, self.interface, self.channel, self.next_cc, is_button=is_button)        

        self.advance()

        return t

    def advance(self):
        while True:
            self.next_cc += 1
            if self.next_cc not in self.forbidden:
                break

        if self.next_cc > 128:
            if self.expand and self.channel < 16:
                self.next_cc = 1
                self.channel += 1
            else:
                self.exhausted = True

    def skip(self, n):
        """
        Skips n cc values
        """
        for _ in range(n):
            self.advance()


class ViewMaker(object):

    def __init__(self, interface, prefix="V"):
        self.interface = interface
        self.next_index = 1
        self.prefix = prefix

    def make(self, view=None):
        name = "%s_%i" % (self.prefix, self.next_index)
        if not view:
            view = View(self.interface.input, name=name)
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
    def __init__(self, device, name="Unnamed View"):
        self.name = name
        # Map IDs of a device's controls to configurations:
        # - Buttons: toggle vs momentary
        self.configuration = {}
        for ID, control in device.controls.items():
            self.configuration[ID] = copy(control.default_conf)

        # Map IDs of a device's controls to Targets
        self.map = ddict(list)

    def find_IDs_by_target(self, vtarget):
        """
        Make a list of IDs on this view mapped to the provided target.
        """
        IDs = []
        for ID, vtargets in self.map.items():
            for target in vtargets:
                if target == vtarget or target.is_connected_to(vtarget):
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

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


class Interface(object):
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
    def __init__(self, devin, devout, initview=None, auto_start=True):
        """
        Initialize the Interface with the provided input and output device
        and a View. If no View is provided and empty View will be produced.

        The Interface attaches itself as a listener to both input and output
        devices.
        """
        self.input = Shell(devin, devin.update)
        self.output = Shell(devout, devout.update)
        self.targets = {}
        self.view = initview if initview else View(self.input, "Init")
        self.views = [self.view]

        self.device_event_dispatch = {
            DeviceEvent.CC: self.device_event_callback,
        }
        self.device_q = Queue()
        self.input.add_listener(self.device_q)
        self.output.add_listener(self.device_q)

        self.observers = []

        self.modifiers = set()

        self.parameter_maker = ParameterMaker(self, 1)
        self.view_maker      = ViewMaker(self)

        self.update_thread = Thread(target=self.main_loop, daemon=True)

        self.recent_changes = {}
        self.last_modified_targets = set()

        self.reset_recent_changes()

        if auto_start:
            self.start()

    def get_device(self, name):
        if self.input.name == name:
            return self.input
        elif self.output.name == name:
            return self.output
        else:
            return None

    def reset_recent_changes(self):
        self.recent_changes = {
            "controls": {},
            "targets": {},
            "views": {"active": self.view,
                      "all": self.views}
        }

    def make_profile(self):
        p = {"input": self.input.name,
             "output": self.output.name,
             "next_cc": self.parameter_maker.next_cc,
             "next_view_index": self.view_maker.next_index,
             "active_view": self.view.name,
             "views": [],
             "modifiers": [],
             "name": "Default Profile"}
        
        for view in self.views:
            v = {"name": view.name,
                 "configuration": view.configuration,
                 "map": []} 

            m = v["map"]
            for ID, targets in view.map.items():
                for target in targets:
                    m.append(target.serialize(ID))
            p["views"].append(v)

        p["modifiers"] = [m.serialize() for m in self.modifiers]

        return p

    def load_profile(self, p):
        print("Loading profile %s..." % p["name"])
        # @TODO: Connect to correct input/output by name

        # Set next_ values
        self.parameter_maker.next_cc = p["next_cc"]
        self.view_maker.next_index = p["next_view_index"]

        # Create views and their targets
        self.views = []
        self.view = None

        for v in p["views"]:
            view = View(self.input, v["name"])
            view.configuration = keys_to_ints(v["configuration"])
            self.views.append(view)
            for t in v["map"]:
                if t["name"] in self.targets:
                    target = self.targets[t["name"]]
                else:
                    try:
                        T = get_target(t["type"])
                    except KeyError as e:
                        eprint(e)
                        continue
                    target = T.blank(self)
                    target.from_dict(t)
                    self.add_target(target)
                view.map_this(t["ID"], target)

        # Create modifiers

        for m in p["modifiers"]:
            try:
                M = get_modifier(m["type"])
            except KeyError as e:
                eprint(e)
                continue
            mod = M()
            mod.from_dict(m, self.targets)
            self.add_modifier(mod)

        # activate active view
        self.switch_to_view(p["active_view"])

        print("Profile loaded.")

        for o in self.observers:
            o.callback_load_profile()

    ########### VIEWS ###############
           
    def add_view(self, view):
        """
        Adds the view to the view list if it isn't already in there.
        Returns True if it is a new view, False if not
        """
        if view.name not in map(lambda v: v.name, self.views):
            new_view = True
            self.views.append(view)
            for ID, targets in view.map.items():
                for target in targets:
                    self.add_target(target)
            return True
        else:
            return False

    def switch_to_view(self, view):
        """
        Switches to the provided view. If this is a new view it will
        be added to the Interface's view catalog and all targets of
        that view will be added to the total list of targets.
        """
        if type(view) == str:
            # Find view by name
            views = list(filter(lambda v: v.name==view, self.views))
            if len(views) != 1:
                print("View by the name %s not in interface.views" % view)
                raise KeyError
            view = views[0]

        if self.view and self.view == view:  # Nothing to be done
            return

        self.view = view

        for ID, control in self.input.controls.items():
            try:
                control.configure(view.configuration[ID])
            except KeyError:
                pass

        new_view = self.add_view(view)

        self.reflect_all_on_input()
        print("[%s] Switched to %s" % (self, view))

        for o in self.observers:
            o.callback_view(self.view, new_view)

    ############## TARGETS ################

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

    def trigger_targets(self, sender, targets, value):
        """
        Call this to trigger a list of targets with a value on behalf
        of the provided sender.
        """
        for target in targets:
            target.trigger(sender, value)


    def get_recent_changes(self):
        """
        Returns the dict of recent control value changes and resets it
        """
        copy = self.recent_changes
        self.reset_recent_changes()
        return copy


    ############## CALLBACKS / EVENT / INPUT HANDLING ################

    def from_input(self, sender, ID, value):
        """
        Callback method whenever the input (or output devices) produces
        messages to consume (input -> hardware -> controls ((, output ->
        daw -> automation)).
        """
        try:
            targets = self.view.map[ID]
        except KeyError:
            print("No target configured for ID %i" % ID)
            return

        modified_targets = set()
        for target in targets:
            # Some targets should only trigger on certain values
            # TODO: Move this into the target.trigger method?
            if unify(value) in target.trigger_vals:
                real_value = target.trigger(sender, value)

                # We keep a set of last modified targets in the Interface
                # but only for those modified due to a user action on the
                # input device ... which is exactly here.
                # This only works for Value Targets
                if isinstance(target, ValueTarget) and real_value is not None:
                    modified_targets.add(target)

                if real_value is not None and value != real_value:
                    self._set_control(ID, real_value)
                else:
                    self.recent_changes["controls"][ID] = real_value
                self.reflect_target_on_input(target, exclude_IDs=[ID])

        if modified_targets:
            self.last_modified_targets = modified_targets



    def from_output(self, sender, channel, cc, value):
        """
        Callback method whenever the ouput produces a control change.
        Inform the target and reflect the value on the input device always.
        """
        assert(sender == self.output)
        # Look for targets connected to the Control ID of the output

        targets = []
        for target_list in self.view.map.values():
            for target in target_list:
                if target.is_connected_to_output(channel, cc):
                    targets.append(target)

        for target in targets:
            if unify(value) in target.trigger_vals:
                # trigger will notify the output again if needed, we don't care
                real_value = target.trigger(sender, value)
                # but we need to reflect this value change on the input device
                self.reflect_target_on_input(target)
#                for input_ID in self.view.find_IDs_by_target(target):
#                    self.input.set_control(input_ID, real_value)

    def target_triggered(self, target, value, sender):
        """
        Usually targets are modified by some logic in the Interface. If not,
        the target will call this method to report a value change that happened
        indepedently. This is our chance to inform self.input of the value change
        to keep everything in sync.
        The self.output will already have been notified by the Target itself,
        if such an action was part of the Target's trigger method.
        """
        assert(sender not in (self.input, self.output))
        if value is not None:
            for ID in self.view.find_IDs_by_target(target):
                self._set_control(ID, target.value)

    def _set_control(self, ID, value, force=False):
        """
        Sets the control of the input device of the Interface and caches
        the set value in our recent_changes dict.

        The force flag causes the Controls of the Device to assume a state
        appropriate for that value. E.g.: Toggle buttons might be implemented
        using an ignore state. Using force means "Assume the value and state
        I provide" vs. "I'm trying to set this value, is that okay in your
        current configuration?"
        """
        set_value = self.input.set_control(ID, value, force=force).get()  # Returns a promise
        if set_value is not None:
            self.recent_changes["controls"][ID] = set_value
        

    def device_event_callback(self, sender, ID, value):
        """
        Is called to handle DeviceEvents from both input and output.
        Basically forwards the calls to the dedicated from_input and from_output.
        """
        if sender == self.input:
            self.from_input(sender, ID, value)
        elif sender == self.output:
            self.from_output(sender, ID, value)
        else:
            print("Received DeviceEvent from Device other than input or output:")
            print(sender, ID, value)

    def to_input(self, ID, value):
        self.input.cc(ID, value)

    def to_output(self, channel, cc, value):
        """
        Set a control on the output
        """
        self.output.cc(channel, cc, value)

    def reflect_target_on_input(self, target, exclude_IDs=None):
        """
        Inform the input device of a value change, possibly excluding
        certain IDs. Only controls mapped to the given target will
        be updated.
        """
        for ID in self.view.find_IDs_by_target(target):
            if not exclude_IDs or ID not in exclude_IDs:
                self._set_control(ID, target.value)

    def reflect_all_on_input(self):
        """
        Based on the current view, reflect all values to the input device
        """
        untouched = set(self.input.controls.keys())
        for ID, targets in self.view.map.items():
            for target in targets:
                try:
                    # Does the target have a value type?
                    getattr(target, "value")
                except AttributeError:
                    continue
                self._set_control(ID, target.value, force=True)
                untouched.remove(ID)

        for ID in untouched:
            self._set_control(ID, 0, force=True)
 

    ############## MODIFIERS ####################


    def add_modifier(self, modifier):
        self.modifiers.add(modifier)

    def remove_modifier(self, modifier):
        try:
            self.modifiers.remove(modifier)
        except KeyError:
            pass

    ############## UPDATING ####################

    def start(self):
        self.update_thread.start()

    def main_loop(self):
        while True:
            try:
                self.update()
            except Exception as e:
                eprint(e)
            yield_thread()

    def update(self):
        time_now = time.time()

        # Handle DeviceEvent queue
        max_messages = 50
        try:
            while max_messages > 0:
                event, *data = self.device_q.get_nowait()
                max_messages -= 1
                try:
                    func = self.device_event_dispatch[event]
                except KeyError:
                    print(self, "Cannot handle event of type", event, file=sys.stderr)
                    continue
                func(*data)

        except Empty:
            pass


        for m in self.modifiers:
            m.tick(time_now)


    def __repr__(self):
        return "Interface"

    def __str__(self):
        return self.__repr__()

##################################

PROFILES_DIR = "profiles"
PROFILES_EXT = "bcr"

class ProfileNotFoundError(Exception):
    """
    Thrown when a profile script could not be resolved by name.
    """
    pass


def resolve_profile(name):
    """
    Find a script in the profiles dir/package by name. Raises ProfileNotFoundError
    of none could be find.
    """
    profile_file = os.path.join(PROFILES_DIR, "%s.%s" % (name, PROFILES_EXT))
    if not os.path.isfile(profile_file):
        raise ProfileNotFoundError
    return profile_file


def load_profile(interface, filename):
    with open(filename, "r") as infile:
        print("Loading", filename)
        profile = json.load(infile)
        interface.load_profile(profile)
        if "comment" in profile:
            for k, v in profile["comment"].items():
                print(Fore.YELLOW + Style.BRIGHT + "%s: %s" % (k, v))


def save_profile(interface, filename, comment=None):
    with open(filename, "w") as outfile:
        profile = interface.make_profile()
        if comment:
            profile["comment"] = comment
        json.dump(profile, outfile, sort_keys=True)
        print("Saved to %s" % filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the commandline interface')
    parser.add_argument('profile', help='A profile to load')
    parser.add_argument('-i', '--interactive', dest='interactive', action='store_true',
                        help="Drop into the interactive Python console when running.")
    args = parser.parse_args()

    bcr = BCR2k(auto_start=False)
    loop = VirtualMidi(auto_start=False)
    print("Devices started")

    interface = Interface(bcr, loop)
    print("Interface started")

    profile_file = resolve_profile(args.profile)
    load_profile(interface, profile_file)


    try:
        if args.interactive:
            from rtmidi.midiutil import list_output_ports, list_input_ports

            def test_mod():
                ID = 862
                from modifiers import LFOSine
                s = LFOSine(frequency=0.5)
                interface.add_modifier(s)
                s.target(interface.view.map[862][0])

            interact(local=locals(), banner="""
    The Interface is now running and you've been dropped into Python's
    interactive console. The following objects are available:

    interface: The Interface making your Midi Controller smart
    bcr:       Your BCR 2000 Midi Controller
    loop:      The Midi Port that leads to your DAW

    Call the function 'attributes' on an object to find out what attributes
    it carries. eg.: attributes(interface)

    Exit using 'exit()'
            """)


        else:  # non-interactive mode
            while True:
                yield_thread()
    except KeyboardInterrupt:
        pass

    exit()
