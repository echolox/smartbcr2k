from math import sin

from .modifier import Modifier

class Basic(Modifier):
    """
    A basic modulator that just needs a frequency to operate.
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

    def save(self):
        d = super().save()
        d["frequency"] = self.frequency
        return d

    def load(self, d, i):
        super().load(d, i)
        self.frequency = d["frequency"]


class PositiveSine(Basic):
    """
    A positive sine, moving from 0 to 1 * amplitude
    """
    
    def calculate(self, t):
        return (sin(t * self.frequency) + 1) * 0.5


