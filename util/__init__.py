import sys
import code

FULL = 127

def flatten(l):
    """
    Flattens a list of list into a single list
    """
    return [item for sublist in l for item in sublist]


def clip(minval, maxval, value):
    """
    Clips the provided value between minval and maxval
    """
    return sorted((minval, value, maxval))[1]


def keys_to_ints(d):
    """
    Takes a dict and returns the same dict with all keys converted to ints
    """
    return {int(k): v for k, v in d.items()}


def unify(value):
    """
    Converts the value to a number from 0 to 127.
    Bools: 0 and 127 for False and True respectively.
    Strings: 127 for "on", 0 for anything else
    """
    if type(value) == bool:
        return 127 if value else 0
    elif type(value) == str:
        return 127 if value == "on" else 0
    else:
        return int(value)


def eprint(*args, **kwargs):
    """
    Prints to the error stream
    """
    print(*args, file=sys.stderr, **kwargs)


DEBUG_PRINT = True
def dprint(*args, **kwargs):
    """
    Regular print of DEBUG_PRINT is True
    """
    if DEBUG_PRINT:
        print(*args, **kwargs)


def iprint(condition, *args, **kwargs):
    """
    Regular print if the condition evaluates to True
    """
    if condition:
        print(*args, **kwargs)


def interactive_mode():
    """
    Drop into interactive mode
    """
    code.interact(local=locals())
