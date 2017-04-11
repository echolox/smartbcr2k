import time
import rtmidi
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from devices import BCR2k, MidiLoop

class Listener(object):

    def inform(self, sender, ID, value):
        print("%s says %i is now %i" % (sender, ID, value))


def test(bcr):
    bcr.blinken.append(65)
    try:
        while True:
            bcr.update(time.time())
    except KeyboardInterrupt:
        print("Exiting...")


def fun(bcr):
    x = 0
    import math
    import time
    while True:
        time.sleep(0.05)
        for i in range(81, 104 + 1):
            v = min(math.sin(x - (i-81)*0.1) * 64 + 64, 127)
            bcr.send(i, v)
        x += 0.2

if __name__ == "__main__":
    bcr = BCR2k()
    loop = MidiLoop()

    bcr.listeners.append(Listener())
#    fun(bcr)
    test(bcr)
