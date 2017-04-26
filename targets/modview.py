"""
ModView targets allow the user to change the power of a Modifier on the targets
present in the currently active view. It does so by constructing a temporary
view with temporary targets, that allow the user to dial in a modulation power
per Target.
"""
from .target import Target, ValueTarget
from smci.view import View
from devices.controls import Button
from modifiers import Modifier

class ModPower(ValueTarget):
    
    def __init__(self, name, parent, modifier, target, *args, **kwargs):
        initial = 64 + (modifier.targets.get(target, 0) * 64)
        super().__init__(name, parent, initial, *args, **kwargs)
        self.modifier = modifier
        self.target = target
 
    def trigger(self, sender, value=None):
        """
        Forwards the value to the configured (output) Device with
        the transmitted value.
        """
        if value is not None:
            self.value = value

        self.modifier.target(self.target, power=(self.value - 64) / 64)

        super().trigger(sender, self.value)
        return self.value

    # Doesn't need a blank because they never live to be saved into a profile


class ModView(Target):
    """
    If the button is held:
    Constructs a temporary view based on the power of a Modifier on the
    Targets in the interface's active view.
    If the button is pushed momentarily:
    Constructs a temporary view to configure the modifier itself.
    """

    trigger_vals = [0, 127]

    def __init__(self, name, parent, modifier, **kwargs):
        super().__init__(name, parent, **kwargs)
        self.modifier = modifier
        self.prev_view = None
        self.deferred = None

    def trigger(self, sender, value=None):
        """
        Switch to the mod_config_view or mod_power_view based on how long the button
        is held/pushed.
        """
        if self.modifier is None:
            self.link_to_mod()

        super().trigger(sender, value)

        # Longpress/Shortpres logic
        if value is 127:
            self.prev_view = self.parent.view
            self.mod_power_view()
        elif value is 0:
            self.go_back()
    
    def go_back(self):
        """
        Go back to the view that was shown before switching to the mod views.
        """
        self.parent.switch_to_view(self.prev_view)

    def mod_config_view(self):
        """
        Constructs and shows a view that let's the user configure the modifier attributes
        itself (amplitude, frequeny ...) with a display of the waveform.
        """
        pass

    def mod_power_view(self):
        """
        Constructs and shows a view that let's the user adjust the power of the modifier
        on the targets available in the current view.
        """
        temp_view = View(self.parent.input, name="%s_ModView" % self.modifier)

        for ID, targets in self.prev_view.map.items():
            for target in targets:
                if isinstance(target, ValueTarget) and not isinstance(self.parent.input.controls[ID], Button):
                    mp = ModPower("%s_%s_PWR" % (target, self.modifier), self.parent, self.modifier, target)
                    temp_view.map[ID].append(mp)

        ID = next(filter(lambda kv: self in kv[1], self.prev_view.map.items()))[0]
        temp_view.map[ID].append(self)
        self.parent.switch_to_view(temp_view, temp=True)

    def serialize(self, *args, **kwargs):
        s = super().serialize(*args, **kwargs) 
        s["modifier"] = self.modifier.name
        return s

    def from_dict(self, d):
        super().from_dict(d)
        self.link_to_mod(name=d["modifier"])

    def link_to_mod(self, name=None):
        if name is None:
            name = self.deferred
        try:
            self.modifier = self.parent.get_modifier(name)
        except KeyError:
            self.deferred = name


    @staticmethod
    def blank(parent):
        return ModView("unnamed", parent, None)
