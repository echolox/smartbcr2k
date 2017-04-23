"""
Flex Parameters allow the user to dynamically map targets to a Control.

It comes in two parts:
The FlexSetter is what activates the dynamic mapping. It takes list of targets
that have been manipulated last by the user and maps the Flex to behave as if
it was those targets.

On a BCR2k it makes sense to map a Flex Target to a Macro Dial and the respective
FlexSetter to the button action (momentary) on that same dial.
"""
from .target import Target, ValueTarget


class FlexSetter(Target):
    """
    Is connected to a Flex Target. Upon triggering, it takes the last manipulated
    targets from the interface and provides them to the Flex Target.
    """

    def __init__(self, name, parent, flex_parameter, *args, **kwargs):
        super().__init__(name, parent, *args, **kwargs)
        self.flex = flex_parameter
        self.deferred = None

    def trigger(self, sender, value=None):
        if self.deferred:
            self.flex = self.parent.targets[d[self.deferred]]
            self.deferred = None

        if value:
            self.flex.link(self.parent.last_modified_targets)

    def serialize(self, *args, **kwargs):
        s = super().serialize(*args, **kwargs) 
        s["flex"] = self.flex.name
        return s

    def from_dict(self, d):
        super().from_dict(d)
        try:
            self.flex = self.parent.targets[d["flex"]]
        except KeyError:
            eprint("Flex target %s for %s not yet instantiated. Defering until first trigger")
            self.deferred = d["flex"]

    @classmethod
    def blank(self, parent):
        return FlexSetter("unnamed", parent, None)


class FlexParameter(ValueTarget):
    """
    Forwards all triggers to the linked targets which are set by FlexSetter.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parameters = set()

    def link(self, targets):
        """
        Gets called by the FlexSetter. Release old targets and link with new targets.
        """
        self.parameters = set(targets)
        ft = next(iter(targets))
        self._value = ft.value
        self.parent.target_triggered(self, self._value, self)

    def unlink(self):
        self.parameters = set()

    def trigger(self, sender, value=None):
        """
        Forward the trigger value and sender to the linked parameters.
        """
        real_value = None
        for parameter in self.parameters:
            real_value = parameter.trigger(self, value)

        return real_value

    @property
    def value(self):
        """
        Pick a target from the ones linked to and return their value
        """
        try:
            ft = next(iter(self.parameters))
            return ft.value
        except StopIteration:
            # We are not linked to anything
            return 0 

    @classmethod
    def blank(self, parent):
        return FlexParameter("unnamed", parent)

    def is_connected_to(self, target):
        return target in self.parameters

    # @BUG: There is a bug where switching views sets the hardware mapped to this
    #       target to some wrong value. It otherwise functions correctly though.
