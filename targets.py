from collections import defaultdict as ddict

from util import FULL, clip

class Target(object):
    """
    A mapping target. In the Interface, the IDs of the input
    device are mapped to targets.    
    """

    trigger_vals = list(range(128))

    def __init__(self, name, parent, callback=None):
        self.name = name
        self.parent = parent
        self.trigger_callback = callback

    def trigger(self, value=None, reflect=True):
        """
        Their trigger method is then called
        with the value transmitted by the Control.
        """
        if self.trigger_callback:
            self.trigger_callback(self)

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


class SwitchView(Target):
    """
    Issues the command to switch to a preconfigured View
    when triggered.
    """

    def __init__(self, name, parent, view, **kwargs):
        super().__init__(name, parent, **kwargs)
        if type(view) == str:
            self.view_name = view
        else:
            self.view_name = view.name
        # @TODO: Class member override?
        self.trigger_vals = [127]

    def trigger(self, value=None, reflect=False):
        self.parent.switch_to_view(self.view_name)
        super().trigger(value)

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
        self.trigger()

    def remove_modifier(self, modifier):
        """
        """
        try:
            del self.modifiers[modifier]
        except KeyError:
            pass

    @property
    def value(self):
        return clip(self.minimum, self.maximum, self._value + sum(self.modifiers.values()))

    @value.setter
    def value(self, v):
        self._value = v


class Parameter(ValueTarget):
    """
    A type of target that simply maps the incoming value to a
    Control Change midi signal on the configured (output) device.
    Button values are (for now) hardcoded to 0 for Off and 127 for On.
    """
    def __init__(self, name, parent, cc, initial=0, is_button=False, **kwargs):
        super().__init__(name, parent, initial, **kwargs)
        self.cc = cc
        self.is_button = is_button

    def serialize(self, *args, **kwargs):
        s = super(Parameter, self).serialize(*args, **kwargs) 
        s["cc"] = self.cc
        s["value"] = self.value
        s["is_button"] = self.is_button
        return s

    def trigger(self, value=None, reflect=True):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if value:
            if self.is_button:
                if value:
                    value = 127
                else:
                    value = 0
            self.value = value
        if reflect:
            self.parent.reflect_value(self)
        super().trigger(self.value)

    def from_dict(self, d):
        super(Parameter, self).from_dict(d)
        self.cc = d["cc"]
        self.value = d["value"]
        self.is_button = d["is_button"]

    @classmethod
    def blank(self, parent):
        return Parameter("unnamed", parent, 0)

from inspect import isclass
TARGETS = {C.__name__: C for C in globals().values() if isclass(C) and issubclass(C, Target)}

def get_target(name):
    return TARGETS[name]


