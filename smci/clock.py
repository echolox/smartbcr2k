from functools import lru_cache
from wrapt import synchronized
from time import time
from collections import namedtuple

from util import iprint

TimeSignature = namedtuple("TimeSignature", ["top", "bottom"])

TimeReport = namedtuple("TimeReport", ["delta", "measure", "signature", "tick", "bpm", "prog", "playing"])
"""
- delta:     Time passed since last report, in seconds
- measure:   Current measure of the song, starting with 0
- signature: TimeSignature namedtuple
- tick:      Tick within the current measure
- bpm:       Currently set BPM
- prog:      Moves within [0.0, 1.0) c R over the span of one measure
- playing:   Whether the song is playing or not
"""

@lru_cache(8)
def ticks_per_measure(signature):
    return signature.top * 24 / (signature.bottom / 4)

@lru_cache()
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
        self.prog = 0.0

        self.running = False

        self.absolute_time = 0.0


        self.last_prog = 0.0

    @synchronized
    def get_report(self):
        # DELTA
        now = time()
        try:
            delta = now - self.last_report_time
        except TypeError:  # self.last_report_time not set yet
            delta = 0.0
        self.absolute_time += delta
        self.last_report_time = now

        # PROG
        if self.running:
            try:
                self.prog = self.tick_count / ticks_per_measure(self.signature)
                delta_tick = now - self.last_tick_time
                iprint(delta_tick < 0, "OOPS")
                self.prog += delta_tick / seconds_per_tick(self.bpm) / ticks_per_measure(self.signature)
            except TypeError:  # self.last_report_time not set yet
                self.prog = 0.0
        else:

            free_prog = delta / seconds_per_tick(self.bpm) / ticks_per_measure(self.signature)
            self.prog = self.prog + free_prog
        self.prog %= 1
        # @BUG: prog not monotone. Happens when the clock stops and then resumes running (sometimes)

        if (self.prog <= self.last_prog):
            print(self.prog, self.last_prog, now, self.last_tick_time)
        self.last_prog = self.prog

        return TimeReport(delta, self.measure_count, self.signature, self.tick_count, self._bpm, self.prog, self.running)

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



