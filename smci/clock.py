from collections import namedtuple

TimeSignature = namedtuple("TimeSignature", ["top", "bottom"])

class Clock(object):

    def __init__(self, parent):
        self.parent = parent

        self.bpm = 120
        self.signature = TimeSignature(4, 4)
        self.tick_count = 0

        self.measure_count = 0

    def start(self):
        self.measure_count = 0
        self.tick_count = 0
        pass

    def stop(self):
        pass

    def unpause(self):
        pass

    def tick(self):
        if self.tick_count == 0:
            self.at_measure_start()

        self.tick_count = (self.tick_count + 1) % (self.signature.top * 24 / (self.signature.bottom / 4))

    def at_measure_start(self):
        print("Measure", self.measure_count, self.signature, self.bpm)
        self.measure_count += 1



