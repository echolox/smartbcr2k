"""
ModView targets allow the user to change the power of a Modifier on the targets
present in the currently active view. It does so by constructing a temporary
view with temporary targets, that allow the user to dial in a modulation power
per Target.
"""
from .target import Target, ValueTarget
from devices.controls import Button
from modifiers import Modifier

View = None

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
    Constructs a temporary view based on the power of a Modifier on the
    Targets in the interface's active view.
    """

    trigger_vals = [0, 127]

    def __init__(self, name, parent, modifier, **kwargs):
        super().__init__(name, parent, **kwargs)
        self.modifier = modifier
        self.prev_view = None
        self.deferred = None

    def trigger(self, sender, value=None):
        """
        Construct and show the temporary view or switch back to the previous one
        """
        if self.modifier is None:
            self.link_to_mod()
        super().trigger(sender, value)
        if value is 127:
            self.prev_view = self.parent.view

            # Deferred import
            global View
            if View is None:
                import interface
                View = interface.View

            temp_view = View(self.parent.input, name="%s_ModView" % self.modifier)


            for ID, targets in self.prev_view.map.items():
                for target in targets:
                    if isinstance(target, ValueTarget) and not isinstance(self.parent.input.controls[ID], Button):
                        mp = ModPower("%s_%s_PWR" % (target, self.modifier), self.parent, self.modifier, target)
                        temp_view.map[ID].append(mp)

            ID = next(filter(lambda kv: self in kv[1], self.prev_view.map.items()))[0]
            temp_view.map[ID].append(self)
            self.parent.switch_to_view(temp_view, temp=True)
        elif value is 0:
            self.parent.switch_to_view(self.prev_view)

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

