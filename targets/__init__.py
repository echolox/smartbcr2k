from inspect import isclass

from .target import *
from .flex import * 

TARGETS = {C.__name__: C for C in globals().values()
                       if isclass(C) and issubclass(C, Target)}

def get_target(name):
    return TARGETS[name]


