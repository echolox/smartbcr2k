from inspect import isclass

from targets.target import *

TARGETS = {C.__name__: C for C in globals().values()
                       if isclass(C) and issubclass(C, Target)}

def get_target(name):
    return TARGETS[name]


