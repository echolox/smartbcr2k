from collections import defaultdict as ddict

from math import sin
from ctrl import ValueTarget
from devices import clip

MIN_MOD = 0
MAX_MOD = 127

class Modifier(object):
    """
    A modifier keeps a list of targets which it periodically updates
    with a value to modify the targets true value with. Think of LFOs.
    """

    def __init__(self, amplitude=MAX_MOD):
        self._amplitude = amplitude
        self._value = 0

        self.targets = ddict(lambda: 0.0)  # target object -> [-1, 1]
    
    def target(self, target, power=0.0):
        """
        Expects a target object and a power in the range [-1, 1]
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
        Stop modifying the provided target
        """
        self.target(target, 0.0)
        target.remove_modifier(self)

    def clear_targets(self):
        """
        Removes all targets from this modifier
        """
        for target in targets:
            self.remove_target(target)

        # Better safe than sorry
        self.targets.clear()

    @property
    def amplitude(self):
        """
        Returns the amplitude, which is the maximum value Modifier.value could have
        """
        return self._amplitude

    @amplitude.setter
    def amplitude(self, a):
        self._amplitude = clip(MIN_MOD, MAX_MOD, a) 

    @property
    def value(self):
        return self._value

    def modvalue(self):
        """
        Returns the current value multiplied by the amplitude
        """
        return self.value * self.amplitude 

    def tick(self, t):
        """
        Calculates a new modifier value and applies it to all its targets
        """
        self._value = self.calculate(t)
        for target, power in self.targets.items():
            target.modify(self, self.modvalue() * power)
        return self.modvalue()

    def calculate(self, t):
        raise NotImplementedError


class LFOSine(Modifier):
    
    def __init__(self, frequency=0.2, **kwargs):
        super().__init__(**kwargs)
        self.frequency = frequency

    def calculate(self, t):
        return sin(t * self.frequency)  


if __name__ == '__main__':
    r = LFOSine()
    s = LFOSine(0.3)

    t = ValueTarget("Testing", None)

    s.target(t, power=1.0)
    r.target(t, power=1.0)

    for i in range(10):
        print("LFO1:", r.tick(i))
        print("LFO2:", s.tick(i))
        print("Target:", t.value)
