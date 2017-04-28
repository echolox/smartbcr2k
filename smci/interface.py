import os
import time
import json

from threading import Thread
from queue import Queue, Empty
from collections import defaultdict as ddict

from colorama import Fore, Back, Style

from devices.controls import controls_to_IDs
from util import keys_to_ints, unify, eprint
from util.threadshell import Shell, yield_thread
from util.attribute_mapping import AttributeType

from targets import get_target, ValueTarget
from devices import DeviceEvent, OutputEvent
from modifiers import get_modifier

from .view import View
from .makers import ParameterMaker, ViewMaker
from .clock import Clock


class Interface(object):
    """
    The Interface connects an input device with an output device by tunneling
    transmitted values from the input through its currently active View.
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

        # TODO: Make a clock
        self.clock = Clock(self)
        self.output.clock = self.clock

        self.event_dispatch = {
            DeviceEvent.CC: self.device_event_callback,

            OutputEvent.CC: self.device_event_callback,
        }
        self.device_q = Queue()
        self.input.add_listener(self.device_q)
        self.output.add_listener(self.device_q)

        self.modifiers = set()

        self.parameter_maker = ParameterMaker(self, 1)
        self.view_maker = ViewMaker(self)

        self.update_thread = None

        self.recent_changes = {}
        self.reset_recent_changes()
        self.last_modified_targets = set()

        self.universal_controls = ddict(list)  # AttributeType -> list of IDs

        self.snapshots = {}

        if auto_start:
            self.start()

    def get_universal_controls_as_iterators(self, exclude=None):
        """
        Provides the Interface's universal controls as iterators per list
        :param exclude: a single ID or iterable of IDs to exclude
        :return: a dict mapping from AttributeType to lists of IDs
        """
        try:
            i = iter(exclude)
        except TypeError:
            exclude = [exclude]

        as_iters = {}
        for attr_type, IDs in self.universal_controls.items():
            as_iters[attr_type] = filter(lambda i: i not in exclude, IDs)

        return as_iters

    def add_to_universal_controls(self, attr_type, controls):
        try:
            i = iter(controls)
        except TypeError:
            exclude = [controls]

        self.universal_controls[attr_type].extend(controls_to_IDs(controls))

    def get_device(self, name):
        if self.input.name == name:
            return self.input
        elif self.output.name == name:
            return self.output
        else:
            return None

    def save_snapshot(self, slot):
        slot = str(slot)
        print("Saving Snapshot", slot)
        self.snapshots[slot] = {
            "targets": {tname: t.save() for tname, t in self.targets.items()},
            "modifiers": {mod.name: mod.save() for mod in self.modifiers}
        }

    def load_snapshot(self, slot):
        print("Loading Snapshot", slot)
        slot = str(slot)
        if slot not in self.snapshots:
            eprint("No snapshot in slot", slot)
            return

        for tname, state in self.snapshots[slot]["targets"].items():
            try:
                self.targets[tname].load(state)            
            except KeyError:
                eprint("Target", tname, "not available")

        for modname, state in self.snapshots[slot]["modifiers"].items():
            self.get_modifier(modname).load(state, self) 
        
        self.reflect_all_on_input()

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
             "universal_controls": {at.name: IDs for at, IDs in self.universal_controls.items()},
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

        # Universal Controls
        self.universal_controls = {AttributeType[at]: IDs for at, IDs in p["universal_controls"].items()}

        # Create modifiers
        for m in p["modifiers"]:
            try:
                M = get_modifier(m["type"])
            except KeyError as e:
                eprint("Mods", e)
                continue
            mod = M.blank()
            mod.from_dict(m, self.targets)
            self.add_modifier(mod)

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
                        eprint("Targets", e)
                        continue
                    target = T.blank(self)
                    target.from_dict(t)
                    self.add_target(target)
                view.map_this(t["ID"], target)

        # activate active view
        self.switch_to_view(p["active_view"])

        print("Profile loaded.")

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

    def switch_to_view(self, view, temp=False):
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

        if not temp:
            new_view = self.add_view(view)

        self.reflect_all_on_input()
        print("[%s] Switched to %s" % (self, view))

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
                # @Robustness: Can we assure this without having to check
                #              explicitely for ValueTarget?
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
                target.trigger(sender, value)
                # but we need to reflect this value change on the input device
                self.reflect_target_on_input(target)

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

    def get_modifier(self, name):
        try:
            return next(filter(lambda m: m.name == name, self.modifiers))
        except StopIteration:
            raise KeyError

    ############## UPDATING ####################

    def start(self):
        self.update_thread = Thread(target=self.main_loop, daemon=True)
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
                    func = self.event_dispatch[event]
                except KeyError:
                    eprint(self, "Cannot handle event of type", event)
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
SNAPSHOTS_EXT = "snp"


def resolve_profile(name):
    """
    Find a script in the profiles dir/package by name.
    """
    profile_file = os.path.join(PROFILES_DIR, "%s.%s" % (name, PROFILES_EXT))
    if not os.path.isfile(profile_file):
        raise FileNotFoundError
    return profile_file


def resolve_snapshots(name):
    """
    Find a script in the profiles dir/package by name.
    """
    snapshots_file = os.path.join(PROFILES_DIR, "%s.%s" % (name, SNAPSHOTS_EXT))
    if not os.path.isfile(snapshots_file):
        raise FileNotFoundError
    return snapshots_file


def load_snapshots(interface, filename):
    with open(filename, "r") as infile:
        print("Loading", filename)
        interface.snapshots = json.load(infile)
        interface.load_snapshot("recall")

def save_snapshots(interface, filename, comment=None):
    with open(filename, "w") as outfile:
        interface.save_snapshot("recall")
        json.dump(interface.snapshots, outfile)
        print("Saved snapshots to %s" % filename)


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
        json.dump(profile, outfile)
        print("Saved profile to %s" % filename)
