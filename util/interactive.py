import code

from colorama import Fore, Style, init
init()

def lprint(l):
    """
    Just print a nice little list of things
    """
    for e in l:
        print("-", e)

def attributes(obj):
    """
    Print the attributes of an object
    """
    lprint(obj.__dict__.keys())


helpers = locals()

def interact(local=None, banner="Starting interactive mode..."):
    merged_local = {**dict(local), **(dict(helpers))}
    code.interact(local=merged_local, banner=Fore.BLUE + Style.BRIGHT + banner)
