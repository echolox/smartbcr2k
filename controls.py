from util import FULL, clip, dprint, iprint

class ControlParent(object):
    
    def send_to_device(self, ID, value):
        """
        Gets called when the hardware device should receive
        a value change
        """
        pass

    def control_changed(self, ID, value):
        """
        Gets called by the Control object when a value changes
        """
        pass


### HARDWARE CONTROL SIMULATIONS

class Control(object):

    configurable = []

    def __init__(self, ID, parent=None, minval=0, maxval=127, blink=False):
        self.ID = ID
        self.parent = parent
        self.minval = minval
        self.maxval = maxval
        self.blink = blink
        self._value = 0

    def unblink(self):
        self.blink = False
        self.parent.send_to_device(self.ID, 0)

    def get_value(self):
        return self._value

    def value(self, value):
        self._value = value
        return self._value

        #self.reflect(value)
#        self.parent.control_changed(self.ID, self._value)
#        return self._value

#    def reflect(self, value):
#        self._value = clip(self.minval, self.maxval, value)
#        self.parent.send_to_device(self.ID, self._value)

    def configure(self, conf):
        assert(list(conf.keys()) == self.configurable)
        for k, v in conf.items():
            setattr(self, k, v)

    def __repr__(self):
        return "(%i) %i" % (self.ID, self._value)

    def __str__(self):
        return self.__repr__()


class Button(Control):

    configurable = ["toggle"]
    
    def __init__(self, ID, parent=None, toggle=True, **kwargs):
        super().__init__(ID, parent, **kwargs)
        self.toggle = toggle
        self.state = False
        self.ignore = 0

        self.callbacks = []

    def on(self):
        self._value = self.maxval
        self.state = True
        if self.toggle:
            self.ignore = 1
        self.parent.send_to_device(self.ID, self._value)
        self.parent.control_changed(self.ID, self.state)

    def off(self):
        self._value = self.minval
        self.state = False
        self.ignore = 0
        self.parent.send_to_device(self.ID, self._value)
        self.parent.control_changed(self.ID, self.state)

    def toggle(self):
        if self.toggle:
            if self.state:
                self.off()
            else:
                self.on()

    def value(self, value):
        """
        React to value changes on the hardware. If the button configured
        to toggle, we need to reflect that on the hardware where every
        button is actually momentary.
        """
        # When in a toggle cycle, we need to ignore certain presses:
        # 1: Turn on
        # 0: Ignore
        # 1: Ignore
        # 0: Turn off
        if self.ignore > 0:
            self.ignore -= 1
            self.parent.send_to_device(self.ID, self._value)
            return None


        if self.toggle:
            if value == self.maxval and not self.state:
                self._value = self.maxval
                self.state = True
                self.ignore = 2
            elif value == self.minval and self.state:
                self._value = self.minval
                self.state = False

            return self._value
        else:  # Momentary
            self.state = (value == self.maxval)
            self._value = value

            return self._value
    
class Dial(Control):
    pass


