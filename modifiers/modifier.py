from collections import defaultdict as ddict

from util import eprint, clip
from util.attribute_mapping import AttributeType, AttributeDescriptor, Configurable

MIN_MOD = 0
MAX_MOD = 127

counter = 0


class Modifier(Configurable):
    """
    A modifier keeps a list of targets which it periodically updates
    with a value to modify the targets true value with. Think of LFOs.

    To create a new modifier, subclass this Class and override the
    method calculate.
    """
    attribute_configs = (
        AttributeDescriptor("amplitude", 0, 127, int, AttributeType.span, False, None),
    )

    def __init__(self, name, amplitude=MAX_MOD):
        self.name = name
        self._amplitude = amplitude  # The maximum value the Modifier will take on
        self._value = 0.0  # The actual current value of the Modifier at any given time

        self.targets = ddict(lambda: 0.0)  # target object -> [-1, 1]

    def serialize(self):
        """
        Returns a dict with key value pairs for all attributes that should be set upon recreation.
        """
        m = {"amplitude": self._amplitude,
             "type": type(self).__name__,
             "name": self.name,
             "targets": {t.name: power for t, power in self.targets.items()}}
        return m

    def from_dict(self, m, all_targets):
        """
        Resets the objects attributes based on the dictionary and hooks the Modifier up to
        all targets provided in the list all_targets.
        """
        self.name = m["name"]
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

    def tick(self, time_report):
        """
        Calculates a new modifier value and applies it to all its targets
        """
        self._value = self.calculate(time_report)
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

    def save(self):
        """
        """
        return {
            "_value": self._value,
            "_amplitude": self._amplitude,
            "targets": {t.name: value for t, value in self.targets.items()},
        }

    def load(self, d, i):
        """
        """
        self._value = d["_value"]
        self._amplitude = d["_amplitude"]
        self.targets = ddict(lambda: 0.0)
        for t_name, value in d["targets"].items():
            try:
                target = i.targets[t_name]
                self.targets[target] = value
            except KeyError:
                eprint("No Target named %s found in interface" % t_name)

    @classmethod
    def blank(cls):
        return cls("unnamed")

    def __repr__(self):
        return type(self).__name__

    def __str__(self):
        return self.__repr__()
