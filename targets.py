from collections import defaultdict as ddict

from util import FULL, clip, unify, dprint

class Target(object):
    """
    A mapping target. In the Interface, the IDs of the input
    device are mapped to targets.    
    """

    trigger_vals = list(range(128))

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent

    def trigger(self, sender, value=None):
        """
        Triggers the targets action with the given value. If the sender
        is not associated with our parent, we have to inform our parent
        that our value has changed. Otherwise, since the trigger was
        called from the parent, we rely on it to do what it needs to do
        to react to the Target's trigger.
        """
        dprint(self.name, value)
        if sender not in (self.parent.input, self.parent.output):
            self.parent.target_triggered(self, value, sender)

    def serialize(self, ID):
        return {"name": self.name,
                "type": type(self).__name__,
                "ID": ID,
                }

    def from_dict(self, d):
        self.name = d["name"]

    @classmethod
    def blank(self, parent):
        return Target("unnamed", parent)

    def is_connected_to_output(self, ID):
        return False

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

class SwitchView(Target):
    """
    Issues the command to switch to a preconfigured View
    when triggered.
    """

    trigger_vals = [127]

    def __init__(self, name, parent, view, **kwargs):
        super().__init__(name, parent, **kwargs)
        if type(view) == str:
            self.view_name = view
        else:
            self.view_name = view.name
        # @TODO: Class member override?

    def trigger(self, sender, value=None):
        super().trigger(sender, value)
        self.parent.switch_to_view(self.view_name)

    def serialize(self, *args, **kwargs):
        s = super(SwitchView, self).serialize(*args, **kwargs) 
        s["view"] = self.view_name
        return s

    def from_dict(self, d):
        super(SwitchView, self).from_dict(d)
        self.view_name = d["view"]

    @classmethod
    def blank(self, parent):
        return SwitchView("unnamed", parent, "")


class ValueTarget(Target):
    """
    A type of Target that caries a value with it. These are automatically
    modifiable without having to know much about modifiers (see modifiers.py)
    """
    
    def __init__(self, name, parent, initial=0, minimum=0, maximum=FULL, **kwargs):
        super().__init__(name, parent, **kwargs)
        self._value = initial  # This is the 'center' value
        self.minimum = minimum
        self.maximum = maximum
        self.modifiers = ddict(lambda: 0.0)  # object -> float

    def modify(self, modifier, value):
        """
        """
        self.modifiers[modifier] = value
        self.trigger(modifier)

    def remove_modifier(self, modifier):
        """
        """
        try:
            del self.modifiers[modifier]
        except KeyError:
            pass

    @property
    def value(self):
        return int(clip(self.minimum, self.maximum, self._value + sum(self.modifiers.values())))

    @value.setter
    def value(self, v):
        self._value = v


class Parameter(ValueTarget):
    """
    A type of target that simply maps the incoming value to a
    Control Change midi signal on the configured (output) device.
    Button values are (for now) hardcoded to 0 for Off and 127 for On.
    """
    def __init__(self, name, parent, channel, cc, initial=0, is_button=False, **kwargs):
        super().__init__(name, parent, initial, **kwargs)
        self.channel = channel
        self.cc = cc
        self.is_button = is_button

    def serialize(self, *args, **kwargs):
        s = super(Parameter, self).serialize(*args, **kwargs) 
        s["cc"] = self.cc
        s["channel"] = self.channel
        s["value"] = self.value
        s["is_button"] = self.is_button
        return s

    def trigger(self, sender, value=None):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if value is not None:
            if self.is_button:
                if value:
                    value = 127
                else:
                    value = 0
            self.value = value
        else:
            # Called without value, use own value
            pass

        if sender != self.parent.output:
            self.parent.to_output(self.channel, self.cc, self.value)
        super().trigger(sender, self.value)
        return self.value

    def from_dict(self, d):
        super(Parameter, self).from_dict(d)
        self.channel = d["channel"]
        self.cc = d["cc"]
        self.value = d["value"]
        self.is_button = d["is_button"]

    @classmethod
    def blank(self, parent):
        return Parameter("unnamed", parent, 1, 0)

    def is_connected_to_output(self, channel, cc):
        return channel == self.channel and cc == self.cc

from inspect import isclass
TARGETS = {C.__name__: C for C in globals().values() if isclass(C) and issubclass(C, Target)}

def get_target(name):
    return TARGETS[name]


