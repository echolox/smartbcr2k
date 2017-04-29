from wrapt import synchronized
from time import time
from collections import namedtuple

TimeSignature = namedtuple("TimeSignature", ["top", "bottom"])

TimeReport = namedtuple("TimeReport", ["delta", "measure", "signature", "tick", "bpm", "prog"])

# TODO: CACHE
def ticks_per_measure(signature):
    return signature.top * 24 / (signature.bottom / 4)

def seconds_per_tick(bpm):
    return 60.0 / bpm / 24


@synchronized
class Clock(object):

    def __init__(self, parent):
        self.parent = parent

        self._bpm = 120
        self.signature = TimeSignature(4, 4)
        self.tick_count = 0

        self.measure_count = 0

        self.last_report_time = None
        self.last_tick_time = None

        self.last_report = TimeReport(0.0, 0, self.signature, 0, self._bpm, 0.0)
        self.running = False

    @synchronized
    def get_report(self):
        if self.running:
            # DELTA
            now = time()
            try:
                delta = now - self.last_report_time
            except TypeError:  # self.last_report_time not set yet
                delta = 0
            self.last_report_time = now

            # PROG
            try:
                prog = self.tick_count / ticks_per_measure(self.signature)
                # Let n be self.tick_count. How far are we, on the scale [0, 1), between the nth and n+1th tick?
                delta_tick = now - self.last_tick_time
                prog += delta_tick / seconds_per_tick(self.bpm) / ticks_per_measure(self.signature)
            except TypeError:  # self.last_report_time not set yet
                prog = 0

            assert(0 <= prog < 1)
            self.last_report = TimeReport(delta, self.measure_count, self.signature, self.tick_count, self._bpm, prog)

        return self.last_report

    @property
    def bpm(self):
        return self._bpm

    @synchronized
    @bpm.setter
    def bpm(self, value):
        self._bpm = value

    @synchronized
    def start(self):
        self.measure_count = 0
        self.tick_count = 0
        self.running = True

    @synchronized
    def stop(self):
        self.running = False

    @synchronized
    def unpause(self):
        self.running = True

    @synchronized
    def tick(self):
        if self.tick_count == 0:
            self._at_measure_start()

        self.tick_count = (self.tick_count + 1) % (self.signature.top * 24 / (self.signature.bottom / 4))
        self.last_tick_time = time()

    def _at_measure_start(self):
        print("Measure", self.measure_count, self.signature, self.bpm)
        self.measure_count += 1



