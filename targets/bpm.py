from targets import ValueTarget
from util import clip


class BPM(ValueTarget):

    def __init__(self, name, parent, minimum=30, maximum=157):
        self.clock = parent.clock
        super().__init__(name, parent, minimum=minimum, maximum=maximum)

    @property
    def value(self):
        return self.clock.bpm - self.minimum

    @value.setter
    def value(self, value):
        self._value = int(clip(self.minimum, self.maximum, value + self.minimum + sum(self.modifiers.values())))
        self.clock.bpm = self._value
