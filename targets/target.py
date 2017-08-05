from collections import defaultdict as ddict

from util import FULL, clip, unify, dprint, iprint

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
        if sender not in (self.parent.input, self.parent.output):
            self.parent.target_triggered(self, value, sender)

    def serialize(self, ID):
        return {"name": self.name,
                "type": type(self).__name__,
                "ID": ID,
                }

    def from_dict(self, d):
        self.name = d["name"]

    # @Robustness: Most of the overrides of this method are trivial, find
    #              a way to have them happen automatically?
    @classmethod
    def blank(cls, parent):
        return cls("unnamed", parent)

    def is_connected_to_output(self, ID):
        return False

    def is_connected_to(self, target):
        return False

    def save(self):
        """
        Return a dictionary of attributes and values (similar to serialize),
        however this is for creating snapshots. Only store those values you
        need to recreate a certain state, not to recreate the object itself.
        """
        return {}

    def load(self, d):
        """
        Set the target into the state encoded in the dictionary of attributes
        and values.
        """
        pass

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


class ValueTarget(Target):
    """
    A type of Target that caries a value with it. These are automatically
    modifiable without having to know much about modifiers (see modifiers.py)
    """
    
    def __init__(self, name, parent, initial=0, minimum=0, maximum=FULL):
        super().__init__(name, parent)
        self._value = initial  # This is the 'center' value
        self.minimum = minimum
        self.maximum = maximum
        self.modifiers = ddict(lambda: 0.0)  # object_name -> float

    def modify(self, modifier, value):
        """
        """
        self.modifiers[modifier.name] = value
        self.trigger(modifier)

    def remove_modifier(self, modifier):
        """
        """
        try:
            del self.modifiers[modifier.name]
        except KeyError:
            pass

    def assume_center_value(self, value):
        """
        Because of modifiers, the value reported by self.value
        and on the hardware is not the same as self._value which
        is the center value. In this case we'll only look at the
        difference (how far the dial/slider was moved) and add
        or subtract that from the center value self._value.
        """
        delta = value - self.value  # The new value - the modified value
        self._value += delta        # Add directly to private variable
                                    # to modify the center value

    def trigger(self, sender, value=None):
        if value is not None:
            self.value = value
        super().trigger(sender, self.value)

        return self.value

    @property
    def value(self):
        return int(clip(self.minimum, self.maximum, self._value - self.minimum + sum(self.modifiers.values())))

    @value.setter
    def value(self, value):
        self._value = int(clip(self.minimum, self.maximum, value + self.minimum))

    def save(self):
        # TODO: Annotate which attributes to save and load in Class list
        return {
            "_value": self._value,
            "modifiers": self.modifiers,
        }

    def load(self, d):
        super().load(d)
        self._value = d["_value"]
        self.modifiers = ddict(lambda: 0.0, d["modifiers"])
        self.trigger(self)
