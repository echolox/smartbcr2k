from .modifier import *

from .basic import *

# Create a catalogue of modifiers to fetch Classes by name
MODIFIERS = {C.__name__: C for C in globals().values() if isclass(C) and issubclass(C, Modifier)}
del MODIFIERS["Modifier"]

print(MODIFIERS)


def get_modifier(name):
    """
    Retrieves the Modifier class by name. Raises KeyError if the Modifier does not exist.
    """
    return MODIFIERS[name]
