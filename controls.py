from util import clip, dprint, iprint

class ControlParent(object):
    """
    All objects of the type Control and its subtypes need to be constructed with a
    parent object of this type (or another type that provides the same methods. This
    is Python, we don't enforce this, right?).
    """
    
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
    """
    A Control "simulates" the controls you would find on a hardware devices. Things
    like buttons, dials, sliders/faders etc. are controls.
    """

    # Designate which attributes of the Control can be configured by the user
    # and provide some defaults
    default_conf = {"minval": 0, 
                    "maxval": 127,
                    "blink": False,
                   }

    def __init__(self, ID, parent=None, minval=0, maxval=127, blink=False):
        self.ID = ID
        self.parent = parent
        self.minval = minval
        self.maxval = maxval
        self.blink = blink
        self._value = 0

    def get_value(self):
        return self._value

    def set_value(self, value):
        """
        Try to set the control to the provided value. Due to the configuration of the
        Control it might assume a different value. The assumed value is returned to
        the caller.
        """
        self._value = clip(self.minval, self.maxval, value)
        return self._value

    def configure(self, conf):
        """
        Configures the control based on the dictionary
        """
        for attribute, value in conf.items():
            try:
                setattr(self, attribute, value)
            except AttributeError:
                eprint("Control of type %s does not have configurable attribute %s!" % (type(self), attribute))

    def __repr__(self):
        return "(%i) %i" % (self.ID, self._value)

    def __str__(self):
        return self.__repr__()


buttonconf = Control.default_conf
buttonconf.update({"toggle": True})

class Button(Control):
    """
    A button can function in toggle or momentary mode. It assumes either Control.minval or Contro.maxval
    which in most cases will be 0 and 127 respectively.  Apart from those "midi" values we also save
    the state of the button as a bool.

    For all of this to work, on a "dumb" device you need to set your buttons to momentary. With a momentary
    hardware button you can emulate a toggle by forcing it on or off.
    """

    # @TODO: This is hacky, make it more straightforward
    default_conf = buttonconf
    
    def __init__(self, ID, parent=None, toggle=True, **kwargs):
        super().__init__(ID, parent, **kwargs)
        self.toggle = toggle
        self.state = False
        self.ignore = 0  # Used to simulate a toggle behaviour from a momentary button
                         # To toggle we need to ignore some inputs. This is a countdown
                         # of how many inputs to ignore before listening again

    def on(self):
        """
        Simulates activating the button.
        """
        self._value = self.maxval
        self.state = True
        if self.toggle:
            self.ignore = 1
        self.parent.send_to_device(self.ID, self._value)
        self.parent.control_changed(self.ID, self.state)

    def off(self):
        """
        Simulates deactivating the button
        """
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

    def set_value(self, value):
        """
        React to value changes on the hardware. If the button configured
        to toggle, we need to reflect that on the hardware where every
        button is actually momentary.
        """
        # When in a toggle cycle, we need to ignore certain presses:
        # On:  Turn on
        # Off: Ignore
        # On:  Ignore
        # Off: Turn off
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
    """
    A dial spans a range of values (typically 0 to 127, configured using minval and maxval).
    The hardware control mapped to this could also be a slider or fader, as they technically
    behave the same, just not in a rotary manner.
    """
    pass
