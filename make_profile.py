import argparse
import importlib
from interface import Interface, BCR2k, MidiLoop, save_profile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a profile from a script.')
    parser.add_argument('script', help='a script file to be executed')
    parser.add_argument('-o', '--outfilename', help='name of the profile file')

    args = parser.parse_args()

    if args.outfilename:
        outfilename = args.outfilename
    else:
        outfilename = args.script.replace(".py", ".bcr")

    bcr = BCR2k(auto_start=False)
    loop = MidiLoop(auto_start=False)
    
    interface = Interface(bcr, loop)

    print(args)

    module = importlib.import_module(args.script)
    module.create(interface)
    save_profile(interface, outfilename)
