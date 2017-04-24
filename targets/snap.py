"""
SnapshotButton and SnapshotSelector allow the user to save and load snapshots
on the Interface.

It comes in two parts:
SnapshotSelector is a dial or slider used to select a snapshot slot.

SnapshotButton is used to save and load into/from that slot.
Short-press to load, long-press to save.

On a BCR2k it makes sense to map a Selector to a Macro Dial and the respective
Button to the button action (momentary) on that same dial.
"""
from .target import Target, ValueTarget
from time import time

LONGPRESS_THRESHOLD = 1  # in seconds

class SnapshotButton(Target):
    """
    Is connected to a Flex Target. Upon triggering, it takes the last manipulated
    targets from the interface and provides them to the Flex Target.
    """

    trigger_vals = [0, 127]

    def __init__(self, name, parent, selector, *args, **kwargs):
        super().__init__(name, parent, *args, **kwargs)
        self.selector = selector
        self.deferred = None

    def trigger(self, sender, value=None):
        if self.deferred:
            self.selector = self.parent.targets[d[self.deferred]]
            self.deferred = None

        if value is 127:
            self.down = time()
            return None
        elif value is 0:
            delta = time() - self.down 
            if delta < LONGPRESS_THRESHOLD:
                self.selector.issue_load()
            else:
                self.selector.issue_save()

    def serialize(self, *args, **kwargs):
        s = super().serialize(*args, **kwargs) 
        s["selector"] = self.selector.name
        return s

    def from_dict(self, d):
        super().from_dict(d)
        try:
            self.selector = self.parent.targets[d["selector"]]
        except KeyError:
            eprint("Selector target %s for %s not yet instantiated. Defering until first trigger")
            self.deferred = d["flex"]

    @classmethod
    def blank(self, parent):
        return SnapshotButton("unnamed", parent, None)


class SnapshotSelector(ValueTarget):
    """
    
    """

    def issue_load(self):
        self.parent.load_snapshot(self.value)

    def issue_save(self):
        self.parent.save_snapshot(self.value)

    @classmethod
    def blank(self, parent):
        return SnapshotSelector("unnamed", parent)

