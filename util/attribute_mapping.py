from collections import namedtuple
from enum import Enum


class AttributeType(Enum):
    boolean = 0
    span = 1


AttributeDescriptor = namedtuple("AttributeDescriptor", ["name", "min", "max", "cast", "type", "readonly", "scale"])

""" AttributeGap***
These object can be used to create an unmapped control.

There is a problem though: When defining the layout of the attributes on the object to be modified, we commit
to that layout without knowing anything about the control surface/user interface. Right now, we are dealing only
with the BCR2k.

@TODO: Figure out a way to declare the desired layout of
- Modifier configs including the step sequencer
in the profile, so every user can map the controls the way they want it.
"""
AttributeGapSpan = AttributeDescriptor("_gap_span", 0, 1, lambda x: x, AttributeType.span, True, None)
AttributeGapButton = AttributeDescriptor("_gap_boolean", 0, 1, lambda x: x, AttributeType.boolean, True, None)


class Configurable(object):

    _gap_span = 0
    _gap_boolean = False

    attribute_configs = (AttributeGapSpan, )
