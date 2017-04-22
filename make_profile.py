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
