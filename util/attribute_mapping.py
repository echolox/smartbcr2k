from collections import namedtuple
from enum import Enum


class AttributeType(Enum):
    boolean = 0
    span = 1


AttributeDescriptor = namedtuple("AttributeDescriptor", ["name", "min", "max", "cast", "type", "readonly", "scale"])