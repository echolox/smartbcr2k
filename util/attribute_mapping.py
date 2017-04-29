from collections import namedtuple
from enum import Enum


class AttributeType(Enum):
    boolean = 0
    span = 1
    list = 2


AttributeDescriptor = namedtuple("AttributeDescriptor", ["name", "min", "max", "cast", "type", "readonly", "scale"])
AttributeGapSpan = AttributeDescriptor("_gap_span", 0, 1, lambda x: x, AttributeType.span, True, None)
AttributeGapButton = AttributeDescriptor("_gap_boolean", 0, 1, lambda x: x, AttributeType.boolean, True, None)


class Configurable(object):

    _gap_span = 0
    _gap_boolean = False

    attribute_configs = (AttributeGapSpan, )
