from .target import Target

class SwitchView(Target):
    """
    Issues the command to switch to a preconfigured View
    when triggered.
    """

    trigger_vals = [127]

    def __init__(self, name, parent, view):
        super().__init__(name, parent)
        if type(view) == str:
            self.view_name = view
        else:
            self.view_name = view.name

    def trigger(self, sender, value=None):
        super().trigger(sender, value)
        self.parent.switch_to_view(self.view_name)

    def serialize(self, *args, **kwargs):
        s = super(SwitchView, self).serialize(*args, **kwargs) 
        s["view"] = self.view_name
        return s

    def from_dict(self, d):
        super(SwitchView, self).from_dict(d)
        self.view_name = d["view"]

    @classmethod
    def blank(cls, parent):
        return cls("unnamed", parent, "")


