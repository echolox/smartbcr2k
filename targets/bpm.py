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
        ValueTarget.value.fset(self, value)  # Pycharm complains here but it's correct
        self.clock.bpm = self._value
