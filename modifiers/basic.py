from math import sin, cos, pi

from .modifier import Modifier

class Basic(Modifier):
    """
    A basic modulator that just needs a frequency to operate.
    """

    def __init__(self, frequency=0.25, **kwargs):
        super().__init__(**kwargs)
        self.frequency = frequency
        self.positive = False

    def serialize(self):
        m = super().serialize()
        m["frequency"] = self.frequency
        m["positive"] = self.positive
        return m

    def from_dict(self, m, *args, **kwargs):
        super().from_dict(m, *args, **kwargs)
        self.frequency = m["frequency"]
        self.positive = m["positive"]

    def save(self):
        d = super().save()
        d["frequency"] = self.frequency
        d["positive"] = self.positive
        return d

    def load(self, d, i):
        super().load(d, i)
        self.frequency = d["frequency"]
        self.positive = d["positive"]


class Sine(Basic):
    
    def calculate(self, t):
        if self.positive:
            return (sin(self.sync(t)) + 1) / 2
        else:
            return -cos(self.sync(t)) / 2  # Dampen amplitude

    def sync(self, t):
        return t * 2 * pi * self.frequency


class Saw(Basic):
    
    def calculate(self, t):
        if self.positive:
            return t
        else:
            return t * 2 - 1
