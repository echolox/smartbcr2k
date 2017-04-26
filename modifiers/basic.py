from math import sin, cos, pi
from random import random

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

    def calculate(self, t):
        # Dampen the amplitude of "centered" waves by 0.5
        return self.wave(t) * (1 + int(self.positive)) / 2

    def wave(self, t):
        """
        Implement in such a way that:
        self.positive == True ---> [ 0, 1], wave(0) = 0
        self.positive == Fales --> [-1, 1], wave(0) = 0
        """
        raise NotImplementedError


class Sine(Basic):
    
    def wave(self, t):
        if self.positive:
            return (sin(self.period(t)) + 1) / 2
        else:
            return -cos(self.period(t))

    def period(self, t):
        return t * 2 * pi * self.frequency


class Saw(Basic):
    
    def wave(self, t):
        if self.positive:
            return t
        else:
            return t * 2 - 1


class Triangle(Basic):
    
    def wave(self, t):
        if self.positive:
            if t < 0.5:
                return 2 * t
            else:
                return 2 - 2 * t
        else:
            if t < 0.25:
                return t * 4
            elif t < 0.75:
                return 1 - 4(t - 0.25)
            else:
                return 4 * (t - 0.75) - 1


class Square(Basic):
    
    def wave(self, t):
        if self.positive:
            return int(t < 0.25 or t > 0.75)
        else:
            return int(t < 0.5) * 2 - 1


class SampledRandom(Basic):

    last_t = 0
    current_value = 0
    
    def wave(self, t):

        # While t doesn't go from 0 to 1 yet
        t = t - int(t)

        if t <= self.last_t:
            if self.positive:
                self.current_value = random()
            else:
                self.current_value = random() * 2 - 1

        self.last_t = t
        return self.current_value
