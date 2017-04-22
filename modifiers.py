from inspect import isclass
from math import sin
from collections import defaultdict as ddict

from targets import ValueTarget
from devices import clip

from util import FULL, eprint, dprint, iprint

MIN_MOD = 0
MAX_MOD = 127

class Modifier(object):
    """
    A modifier keeps a list of targets which it periodically updates
    with a value to modify the targets true value with. Think of LFOs.

    To create a new modifier, subclass this Class and override the
    method calculate.
    """

    def __init__(self, amplitude=MAX_MOD):
        self._amplitude = amplitude  # The maximum value the Modifier will take on
        self._value = 0              # The actual current value of the Modifier at any given time

        self.targets = ddict(lambda: 0.0)  # target object -> [-1, 1]
    
    def serialize(self):
        """
        Returns a dict with key value pairs for all attributes that should be set upon recreation.
        """
        m = {"amplitude": self._amplitude,
             "type": type(self).__name__,
            }
        m["targets"] = {t.name: power for t, power in self.targets.items()}
        return m

    def from_dict(self, m, all_targets):
        """
        Resets the objects attributes based on the dictionary and hooks the Modifier up to
        all targets provided in the list all_targets.
        """
        self._amplitude = m["amplitude"]
        for target_name, power in m["targets"].items():
            try:
                target = all_targets[target_name]
            except KeyError as e:
                eprint(e)
                continue
            self.target(target, power)

    def target(self, target, power=1.0):
        """
        Expects a target object and a power in the range [-1, 1]. The Modifier will then
        start modifying that target.
        """
        if float(power) == 0.0:
            try:
                del self.targets[target]
            except KeyError:
                pass
        else:
            self.targets[target] = float(power)

    def remove_target(self, target):
        """
        Stop modifying the provided target.
        """
        self.target(target, 0.0)
        try:
            target.remove_modifier(self)
        except AttributeError as e:
            eprint(e)

    def clear_targets(self):
        """
        Removes all targets from this modifier
        """
        for target in self.targets:
            self.remove_target(target)

        # Better safe than sorry
        self.targets.clear()

    @property
    def amplitude(self):
        return self._amplitude

    @amplitude.setter
    def amplitude(self, a):
        self._amplitude = clip(MIN_MOD, MAX_MOD, a) 

    @property
    def value(self):
        return self._value

    def modvalue(self):
        """
        Returns the current value multiplied by the amplitude. Use this to modify things.
        """
        return self.value * self.amplitude 

    def tick(self, t):
        """
        Calculates a new modifier value and applies it to all its targets
        """
        self._value = self.calculate(t)
        modvalue = self.modvalue()
        for target, power in self.targets.items():
            try:
                target.modify(self, modvalue * power)
            except AttributeError as e:
                eprint(e)
                
        return modvalue

    def calculate(self, t):
        """
        Override with your own formula that calculates a new modifier value based on
        the current time t.
        """
        raise NotImplementedError

    def __repr__(self):
        return type(self).__name__

    def __str__(self):
        return self.__repr__()


class LFOSine(Modifier):
    """
    A positive sine, moving from 0 to 1 * amplitude
    """
    
    def __init__(self, frequency=0.2, **kwargs):
        super().__init__(**kwargs)
        self.frequency = frequency

    def serialize(self):
        m = super().serialize()
        m["frequency"] = self.frequency
        return m

    def from_dict(self, m, *args, **kwargs):
        super().from_dict(m, *args, **kwargs)
        self.frequency = m["frequency"]

    def calculate(self, t):
        return (sin(t * self.frequency) + 1) * 0.5


# Create a catalogue of modifiers to fetch Classes by name
MODIFIERS = {C.__name__: C for C in globals().values() if isclass(C) and issubclass(C, Modifier)}

def get_modifier(name):
    """
    Retrieves the Modifier class by name. Raises KeyError if the Modifier does not exist.
    """
    return MODIFIERS[name]

if __name__ == '__main__':
    r = LFOSine()
    s = LFOSine(0.3)

    t = ValueTarget("Testing", None)
    t.value = 64

    s.target(t, power=1.0)
    r.target(t, power=-1.0)

    for i in range(10):
        print("LFO1:", r.tick(i))
        print("LFO2:", s.tick(i))
        print("Target:", t.value)
