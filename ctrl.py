import time
import rtmidi
from enum import Enum
from rtmidi.midiconstants import CONTROL_CHANGE

from devices import BCR2k, MidiLoop

class Listener(object):

    def inform(self, sender, ID, value):
        print("(%s) %s says %i is now %i" % (self, sender, ID, value))


class Target(object):
    
    def __init__(self, name):
        self.name = name

    def act(self, value):
        raise NotImplemented

class Parameter(Target):

    def __init__(self, name, device, cc, initial=0):
        self.name = name
        self.device = device
        self.cc = cc
        self.initial = initial

    def act(self, value):
        self.device.send(self.cc, value)

class View(object):

    def __init__(self):
        # Map IDs of a device's controls to configurations like
        # - Buttons: toggle vs momentary
        # - Maxvals / Minvals
        self.configuration = {}

        # Map IDs of a device's controls to Parameters
        self.map = {}

    
    
class Interface(Listener):

    def __init__(self, devin, devout, initview=None):
        self.input = devin
        self.output = devout
        self.view = initview if initview else View()

        self.view.map[81] = Parameter("Testing", self.output, 57)

        self.input.listeners.append(self)

    def inform(self, sender, ID, value):
        print(sender, ID, value)
        try:
            target = self.view.map[ID]
            target.act(value)
        except KeyError:
            print("No target configured for ID %i" % ID)
            pass

    def __repr__(self):
        return "Interface"

    def __str__(self):
        return self.__repr__()

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

    interface = Interface(bcr, loop)

#    fun(bcr)
    test(bcr)
