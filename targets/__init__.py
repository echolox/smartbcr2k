from inspect import isclass

from .target import Target, ValueTarget
from .flex import FlexSetter, FlexParameter 
from .modview import ModPower, ModView
from .snap import SnapshotButton, SnapshotSelector

from .parameter import Parameter
from .switchview import SwitchView
from .pageflip import PageFlip

TARGETS = {C.__name__: C for C in globals().values()
                       if isclass(C) and issubclass(C, Target)}
def get_target(name):
    return TARGETS[name]


