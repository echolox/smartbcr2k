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

    def __init__(self, name, device, cc, initial=0, is_button=False):
        self.name = name
        self.device = device
        self.cc = cc
        self.initial = initial
        self.is_button = is_button

    def act(self, value):
        if self.is_button:
            if value:
                value = 127
            else:
                value = 0
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
        self.targets = {}
        self.view = initview if initview else View()
        self.views = [self.view]

        self.input.listeners.append(self)

        self.add_target(Parameter("Testing", self.output, 57, is_button=True))
        self.view.map[90] = self.targets["Testing"]

    def set_value(self, target, value):
        for ID, vtarget in self.view.map.items():
            if target == vtarget:
                self.input.send(ID, value)

    def switch_to_view(self, view):
        self.view = view
        if view not in self.views:
            self.views.append(view)
            for ID, target in view.map:
                self.add_target(target)

    def add_target(self, target):
        if target.name in self.targets:
            print("Target with same name already exists! Ignoring...")
            return

        self.targets[target.name] = target

    def inform(self, sender, ID, value):
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

def test(i):
    i.set_value(i.targets["Testing"], 127)
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
    test(interface)
