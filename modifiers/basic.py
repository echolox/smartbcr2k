"""
Basic modifiers are the typical LFOs you'd find in the audio world: Sine, Saw, Square,
Triangle, Random. Their frequency can be set freely in Hz.

To unify their definition they all work on the same domain, but two different codomains
based on if the flag "positive" is set:

  let f be the function of the modifier:

  for positive = False:   f: [0, 1] -> [-1, 1]
  for positive = True:    f: [0, 1] -> [ 0, 1]
  with f(0) = 0 in both cases.

  If f yields 0, the target value is not modified at all.
  If f yields 1, the target value is modified to the full effect (which itself is a
                 function of Modifier._amplitude and the per-Target power. See the
                 definition of Modifier for that).

When a ValueTarget is being modified by a centered modifier (positive = False),
the modifier will let the modulated value oscillate around the ValueTargets 
value (center position).
With positive = True it will take the ValueTarget's value as the starting point
and modulate that value in one direction only, depending on if the power is a
positive or negative value.

The Basic base class takes care of preparing the provided time value t to sync up
with the modifiers frequency. It transforms the value to always move from 0 to 1
for one cycle of the waveform.
For musically synced frequencies, calculate the frequency to set using the bpm_syn
function which receives the bpm and the number of quarter notes per cycle.
"""
from collections import namedtuple
from inspect import isclass
from math import sin, cos, pi
from random import random

from util import eprint
from .modifier import Modifier
from util.attribute_mapping import AttributeType, AttributeDescriptor


# @TODO Move to util?
def bpm_sync(bpm, quarter_notes):
    """
    Turns a BPM value and a length given in beats into a frequency usable by a modifier.
    
    :param bpm: Beats Per Minutes
    :param quarter_notes: Length of LFO cycle in quarter notes
    :return: frequency in Hz
    """
    return bpm / 60.0 / quarter_notes


class LFO(object):
    def wave(self, t, positive=False):
        """
        t in [0, 1), which is one cycle. Implement in such a way that:
        positive == True ---> [ 0, 1], wave(0) = 0
        positive == False --> [-1, 1], wave(0) = 0
        """
        raise NotImplementedError


class Sine(LFO):
    def wave(self, t, positive=False):
        if positive:
            return (sin(t * 2 * pi) + 1) / 2
        else:
            return -cos(t * 2 * pi)


class Saw(LFO):
    def wave(self, t, positive=False):
        if positive:
            return t
        else:
            return t * 2 - 1


class Triangle(LFO):
    def wave(self, t, positive=False):
        if positive:
            if t < 0.5:
                return 2 * t
            else:
                return 2 - 2 * t
        else:
            if t < 0.25:
                return t * 4
            elif t < 0.75:
                return 1 - 4 * (t - 0.25)
            else:
                return 4 * (t - 0.75) - 1


class Square(LFO):
    def wave(self, t, positive=False):
        if positive:
            return int(t < 0.25 or t > 0.75)
        else:
            return int(t < 0.5) * 2 - 1


class SampledRandom(LFO):
    last_t = 0
    current_value = 0
    def wave(self, t, positive=False):
        if t <= self.last_t:
            if positive:
                self.current_value = random()
            else:
                self.current_value = random() * 2 - 1

        self.last_t = t
        return self.current_value




#### Define all LFOs above this line!! ####

# We list them explicitly instead of gathering them from locals() to define an order
LFOs = [Sine, Saw, Triangle, Square, SampledRandom]
def pick_lfo_from_list(lfo, lfos):
    return next(filter(lambda l: type(l) == lfo, lfos))

def pick_lfo_from_list_by_name(name, lfos):
    return next(filter(lambda l: type(l).__name__ == name, lfos))


class Basic(Modifier):
    """
    A basic modulator that just needs a frequency to operate. It can choose from a list
    of LFOs at any time.
    
    :param frequency: in Hz
    :param positive: centered mode vs positive mode (see module docstring)
    :param offset: time offset of the cycle 
    """

    attribute_configs = (
        AttributeDescriptor("amplitude",    0, 127, int,   AttributeType.span, False, None),
        AttributeDescriptor("frequency", 0.01,  10, float, AttributeType.span, False, 100),
        AttributeDescriptor("offset",    -0.5, 0.5, float, AttributeType.span, False, None),

        AttributeDescriptor("positive", 0, 1, bool, AttributeType.boolean, False, None),
    )

    def __init__(self, name, frequency=0.25, positive=False, offset=0, init_lfo=Sine, **kwargs):
        super().__init__(name, **kwargs)
        self.frequency = frequency
        self.positive = positive
        self.offset = offset
        self.lfos = [L() for L in LFOs]
        self.lfo = pick_lfo_from_list(init_lfo, self.lfos)

    def serialize(self):
        """
        Serializes Modifier attributes into a dictionary 
        :return: dict to recreate the object in its current state
        """
        m = super().serialize()
        m["frequency"] = self.frequency
        m["positive"] = self.positive
        m["offset"] = self.offset
        m["lfo"] = self.lfo.__class__.__name__
        return m

    def from_dict(self, m, *args, **kwargs):
        """
        Recreates the state of the object from a dictionary generated by serialize
        :param m: the dictionary
        :param args: see parent class
        :param kwargs: see parent class
        """
        super().from_dict(m, *args, **kwargs)
        self.frequency = m["frequency"]
        self.positive = m["positive"]
        self.offset = m["offset"]
        self.lfo = pick_lfo_from_list_by_name(m["lfo"], self.lfos)

    def save(self):
        d = super().save()
        d["frequency"] = self.frequency
        d["positive"] = self.positive
        d["offset"] = self.offset
        d["lfo"] = self.lfo.__class__.__name__
        return d

    def load(self, d, i):
        super().load(d, i)
        self.frequency = d["frequency"]
        self.positive = d["positive"]
        self.offset = d["offset"]
        self.lfo = pick_lfo_from_list_by_name(d["lfo"], self.lfos)

    def switch_to_lfo(self, index):
        try:
            self.lfo = self.lfos[index]
        except IndexError:
            eprint("No LFO in slot", index)

    def calculate(self, t):
        # TODO: Sync to midi clock
        t *= self.frequency

        t = (t + self.offset) % 1

        # Dampen the amplitude of "centered" waves by 0.5
        # That way, setting the power of modulation in ModView
        # the set range equates directly to the range of oscillation
        # However, it would't allow full range modulation in centered
        # mode. It feels better, but makes the centered mode less useful.
        # * (1 + int(self.positive)) / 2
        return self.lfo.wave(t, self.positive)

