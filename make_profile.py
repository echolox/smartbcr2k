"""
Execute this script with another script as its argument to create an Interface profile.

The called script has to have a function called "create" that takes an Interface object.
After that script has run the profile is saved to a file with the same name as the script,
if an ---outfilename is not provided.
"""
import argparse
import importlib
import os.path

from devices import BCR2k, VirtualMidi
from interface import Interface, save_profile

import profiles

PROFILES_EXT = "bcr"
PROFILES_DIR = "profiles"

class ProfileNotFoundError(Exception):
    pass


def resolve_profile(name):
    profile_file = os.path.join(PROFILES_DIR, "%s.%s" % (name, PROFILES_EXT))
    if not os.path.isfile(profile_file):
        raise ProfileNotFoundError
    return profile_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a profile from a script.')
    parser.add_argument('script', help='a script file to be executed')
    parser.add_argument('-o', '--outfilename', help='name of the profile file')

    args = parser.parse_args()

    if args.outfilename:
        outfilename = args.outfilename
    else:
        outfilename = "%s.bcr" % args.script
    outfilename = os.path.join(PROFILES_DIR, outfilename)

    bcr = BCR2k(auto_start=False)
    loop = VirtualMidi(auto_start=False)
    
    interface = Interface(bcr, loop)

    script = "%s.%s" % (PROFILES_DIR, args.script)

    module = importlib.import_module(script)
    module.create(interface)
    save_profile(interface, outfilename)
