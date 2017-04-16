FULL = 127

def clip(minval, maxval, value):
    return sorted((minval, value, maxval))[1]

def keys_to_ints(j):
    return {int(k): v for k, v in j.items()}


def unify(value):
    if type(value) == bool:
        return 127 if value else 0
    elif type(value) == str:
        return 127 if value == "on" else 0
    else:
        return value

import sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
