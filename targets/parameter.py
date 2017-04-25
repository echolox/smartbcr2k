from .target import ValueTarget, Target

class Parameter(ValueTarget):
    """
    A type of target that simply maps the incoming value to a
    Control Change midi signal on the configured (output) device.
    Button values are (for now) hardcoded to 0 for Off and 127 for On.
    """
    def __init__(self, name, parent, channel, cc, initial=0, is_button=False, **kwargs):
        super().__init__(name, parent, initial, **kwargs)
        self.channel = channel
        self.cc = cc
        self.is_button = is_button

    def serialize(self, *args, **kwargs):
        s = super(Parameter, self).serialize(*args, **kwargs) 
        s["cc"] = self.cc
        s["channel"] = self.channel
        s["value"] = self.value
        s["is_button"] = self.is_button
        return s

    def trigger(self, sender, value=None):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if value is not None:
            if self.modifiers:
                # We want to modify the center value because the one
                # displayed on the Dial is shifted by the modifiers
                self.assume_center_value(value)
            else:
                # Convert anything that evaluates to True as 127
                if self.is_button:
                    if value:
                        value = 127
                    else:
                        value = 0
                self.value = value
        else:
            # Called without value, use own value
            pass

        if sender != self.parent.output:
            self.parent.to_output(self.channel, self.cc, self.value)

        # Skip the ValueTarget parent because of our complicated way of setting
        # self._value and go directly to its Parent, Target
        Target.trigger(self, sender, self.value)
        return self.value

    def from_dict(self, d):
        super(Parameter, self).from_dict(d)
        self.channel = d["channel"]
        self.cc = d["cc"]
        self.value = d["value"]
        self.is_button = d["is_button"]

    @staticmethod
    def blank(parent):
        return Parameter("unnamed", parent, 1, 0)

    def is_connected_to_output(self, channel, cc):
        return channel == self.channel and cc == self.cc


