"""
Execute this script with another script as its argument to create an Interface profile.

The called script has to have a function called "create" that takes an Interface object.
After that script has run the profile is saved to a file with the same name as the script,
if no outfilename argument is provided.

You can add a dictionary called "comment" to your script that will be included and printed
back whenever the profile is loaded later.
"""
import argparse
import importlib
import os.path

from devices import BCR2k, VirtualMidi
from interface import Interface, save_profile
from util import eprint

PROFILES_DIR = "profiles"
PROFILES_EXT = "bcr"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a profile from a script.')
    parser.add_argument('script', help='a script file to be executed')
    parser.add_argument('-o', '--outfilename', help='name of the profile file')

    args = parser.parse_args()

    # Decide the profile's filename
    if args.outfilename:
        outfilename = args.outfilename
    else:
        outfilename = "%s.bcr" % args.script
    outfilename = os.path.join(PROFILES_DIR, outfilename)

    # Instantiate the objects that will be configured by the script
    bcr = BCR2k(auto_start=False)
    loop = VirtualMidi(auto_start=False)
    interface = Interface(bcr, loop)

    # Load the script and execute the creat function
    script = "%s.%s" % (PROFILES_DIR, args.script)
    module = importlib.import_module(script)
    module.create(interface)

    # Fetch optional comment dictionary
    try:
        comment = module.comment
        if not isinstance(comment, dict):
            eprint("Comment expected to be an instance of dict, found %s." % type(comment))
            eprint("Ignoring comment...")
            comment = None
    except AttributeError:
        comment = None

    save_profile(interface, outfilename, comment=comment)
