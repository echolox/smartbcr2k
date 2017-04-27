"""
ModView targets allow the user to change the power of a Modifier on the targets
present in the currently active view. It does so by constructing a temporary
view with temporary targets, that allow the user to dial in a modulation power
per Target.
"""
from time import time

from util import eprint
from .target import Target, ValueTarget
from smci.view import View
from devices.controls import Button
from util.attribute_mapping import AttributeType, AttributeDescriptor
from util.scale import Scale

LONGPRESS_TIME = 0.5  # in seconds

class ModPower(ValueTarget):
    
    def __init__(self, name, parent, modifier, target, *args, **kwargs):
        initial = 64 + (modifier.targets.get(target, 0) * 64)
        super().__init__(name, parent, initial, *args, **kwargs)
        self.modifier = modifier
        self.target = target
 
    def trigger(self, sender, value=None):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if value is not None:
            self.value = value

        self.modifier.target(self.target, power=(self.value - 64) / 64)

        super().trigger(sender, self.value)
        return self.value

    # Doesn't need a blank because they never live to be saved into a profile


class DummyModifier(object):
    value = 0.0

class ModConfig(ValueTarget):
    """
    Maps an attribute of a Modifier to a Target, making it adjustable on the controller.
    The attribute has to be provided in an AttributeDescriptor.
    """
    def __init__(self, name, parent, modifier, attribute_descriptor):
        self.modifier = modifier
        self.attribute = attribute_descriptor

        if self.attribute.scale:
            self.scale = Scale(self.attribute.scale, self.attribute.min, self.attribute.max)
        else:
            self.scale = None

        initial = self.map_to_control(getattr(modifier, attribute_descriptor.name))
        super().__init__(name, parent, initial)

    def map_to_control(self, value):
        if self.scale:
            return self.scale.inverse(value)
        else:
            return int((value - self.attribute.min) / (self.attribute.max - self.attribute.min) * 127)

    def map_from_control(self, value):
        if self.scale:
            return self.scale(value)
        else:
            return self.attribute.cast(value * (self.attribute.max - self.attribute.min) / 127.0 + self.attribute.min)

    def trigger(self, sender, value=None):
        """
        Set the attribute linked to the modifier
        :param sender: 
        :param value: 
        :return: 
        """
        # Some values should only be displayed like the current modulation value
        real_value = super().trigger(sender, value=value)
        if not self.attribute.readonly:
            corrected_value = self.map_from_control(real_value)
            setattr(self.modifier, self.attribute.name, corrected_value)

        return real_value


class ModView(Target):
    """
    If the button is held:
    Constructs a temporary view based on the power of a Modifier on the
    Targets in the interface's active view.
    If the button is pushed momentarily:
    Constructs a temporary view to configure the modifier itself.
    """

    trigger_vals = [0, 127]

    def __init__(self, name, parent, modifier):
        super().__init__(name, parent)
        self.modifier = modifier
        self.prev_view = None
        self.deferred = None

        self.value = 0
        self.time_pressed = None
        self.in_config_view = False

        self.config_view_targets = {}
        self.power_view_targets = {}

    def construct_config_view(self):
        temp_view = View(self.parent.input, name="%s_ModConfigView" % self.modifier)

        ID = self.prev_view.find_IDs_by_target(self)[0]
        temp_view.map_this(ID, self)
        temp_view.configuration[ID]["toggle"] = False
        temp_view.configuration[ID]["blink"] = True

        # Filter out the ID we mapped to go back from the universal controls
        # so we don't end up stuck in config view or mapping to that ID twice
        type_IDs = self.parent.get_universal_controls_as_iterators(exclude=ID)

        def map_modconfig_target(attr_desc, target):
            try:
                ID = next(type_IDs[attr_desc.type])
                temp_view.map_this(ID, target)
            except StopIteration:
                eprint("Not enough universal controls available to make %s available in Config View" % target)

        # Construct a target that displays the Modifier's current value
        attribute_descriptor = AttributeDescriptor("value", -1.0, 1.0, float, AttributeType.span, True, None)
        try:
            modconfig = self.config_view_targets["value"]
        except KeyError:
            modconfig = ModConfig("value", self.parent, DummyModifier(), attribute_descriptor)
            self.modifier.target(modconfig, power=0.5)
            self.config_view_targets["value"] = modconfig
        map_modconfig_target(attribute_descriptor, modconfig)

        # Construct targets for the configurable attributes of the Modifier
        for attribute_descriptor in self.modifier.attribute_configs:
            try:
                modconfig = self.config_view_targets[attribute_descriptor.name]
            except KeyError:
                modconfig = ModConfig(attribute_descriptor.name, self.parent, self.modifier, attribute_descriptor)
                self.config_view_targets[attribute_descriptor.name] = modconfig

            map_modconfig_target(attribute_descriptor, modconfig)

        # Map the button we came here with to get us back
        return temp_view

    def construct_power_view(self):
        """
        Constructs and shows a view that let's the user adjust the power of the modifier
        on the targets available in the current view.
        """
        temp_view = View(self.parent.input, name="%s_ModView" % self.modifier)

        for ID, targets in self.prev_view.map.items():
            for target in targets:
                if isinstance(target, ValueTarget) and not isinstance(self.parent.input.controls[ID], Button):
                    try:
                        mp = self.power_view_targets[target]
                    except KeyError:
                        mp = ModPower("%s_%s_PWR" % (target, self.modifier), self.parent, self.modifier, target)
                        self.power_view_targets[target] = mp
                    temp_view.map_this(ID, mp)

        # Map the button we came here with to get us back
        ID = self.prev_view.find_IDs_by_target(self)[0]
        temp_view.map[ID].append(self)
        temp_view.configuration[ID]["toggle"] = False

        return temp_view

    def trigger(self, sender, value=None):
        """
        Switch to the mod_config_view or mod_power_view based on how long the button
        is held/pushed.
        """
        if value is False:
            return None

        if self.modifier is None:
            self.link_to_mod()

        super().trigger(sender, value)

        # Longpress/Shortpres logic
        if value == 127:
            self.value = 127
            if not self.in_config_view:
                self.time_pressed = time()
                self.prev_view = self.parent.view
                self.enter_power_view()
        elif value is 0:  # Ignore False, actually check for 0 (thanks Python)
            self.value = 0
            if not self.in_config_view:
                if self.time_pressed and (time() - self.time_pressed) <= LONGPRESS_TIME:
                    self.enter_config_view()
                else:
                    self.go_back()
            else:
                self.go_back()

    def enter_power_view(self):
        self.parent.switch_to_view(self.construct_power_view(), temp=True)

    def enter_config_view(self):
        """
        Constructs and shows a view that let's the user configure the modifier attributes
        itself (amplitude, frequeny ...) with a display of the waveform.
        """
        self.time_pressed = None
        self.in_config_view = True
        self.parent.switch_to_view(self.construct_config_view(), temp=True)

    def go_back(self):
        """
        Go back to the view that was shown before switching to the mod views.
        """
        self.time_pressed = None
        self.in_config_view = False
        self.parent.switch_to_view(self.prev_view)

    def serialize(self, *args, **kwargs):
        s = super().serialize(*args, **kwargs) 
        s["modifier"] = self.modifier.name
        return s

    def from_dict(self, d):
        super().from_dict(d)
        self.link_to_mod(name=d["modifier"])

    def link_to_mod(self, name=None):
        if name is None:
            name = self.deferred
        try:
            self.modifier = self.parent.get_modifier(name)
        except KeyError:
            print("Deferring resolution of modifier", name)
            self.deferred = name

    @staticmethod
    def blank(parent):
        return ModView("unnamed", parent, None)
