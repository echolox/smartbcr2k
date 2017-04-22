"""
Execute this script with another script as its argument to create an Interface profile.

The called script has to have a function called "create" that takes an Interface object.
After that script has run the profile is saved to a file with the same name as the script,
if an ---outfilename is not provided.
"""
import argparse
import importlib

from interface import Interface, BCR2k, VirtualMidi, save_profile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a profile from a script.')
    parser.add_argument('script', help='a script file to be executed')
    parser.add_argument('-o', '--outfilename', help='name of the profile file')

    args = parser.parse_args()

    if args.outfilename:
        outfilename = args.outfilename
    else:
        outfilename = "%s.bcr" % args.script

    bcr = BCR2k(auto_start=False)
    loop = VirtualMidi(auto_start=False)
    
    interface = Interface(bcr, loop)

    module = importlib.import_module(args.script)
    module.create(interface)
    save_profile(interface, outfilename)
