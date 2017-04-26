from math import sin

from .modifier import Modifier

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

    def save(self):
        d = super().save()
        d["frequency"] = self.frequency
        return d

    def load(self, d, i):
        super().load(d, i)
        self.frequency = d["frequency"]
