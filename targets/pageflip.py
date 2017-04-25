from .target import Target

class PageFlip(Target):
    """
    Issues the command to pageflip on a device.
    """

    def __init__(self, name, parent, device, **kwargs):
        super().__init__(name, parent, **kwargs)
        self.device = device

    def trigger(self, sender, value=None):
        super().trigger(sender, value)
        self.device.page = 1 if value >= 64 else 0

    def serialize(self, *args, **kwargs):
        s = super().serialize(*args, **kwargs) 
        s["device"] = self.device.name
        return s

    def from_dict(self, d):
        super().from_dict(d)
        self.device = self.parent.get_device(d["device"])

    @staticmethod
    def blank(parent):
        return PageFlip("unnamed", parent, parent.input)


