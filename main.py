import argparse

from colorama import Fore, Back, Style, init
init(autoreset=True)

from devices import BCR2k, VirtualMidi
from smci.interface import *
from smci.view import View
from util.interactive import interact


parser = argparse.ArgumentParser(description='Run the commandline interface')
parser.add_argument('profile', help="""The name of a profile to load. Example:
                                       'python main.py myprofile' to load the profile
                                       located at %s/myprofile.bcr
                                    """ % PROFILES_DIR)
parser.add_argument('-i', '--interactive', dest='interactive', action='store_true',
                    help="Drop into the interactive Python console when running.")
args = parser.parse_args()

bcr = BCR2k(auto_start=False)
loop = VirtualMidi(auto_start=False)
print("Devices started")

interface = Interface(bcr, loop)
print("Interface started")

profile_file = resolve_profile(args.profile)
load_profile(interface, profile_file)

try:
    load_snapshots(interface, args.profile)
except FileNotFoundError:
    print("No snapshots available")

try:
    if args.interactive:
        from rtmidi.midiutil import list_output_ports, list_input_ports

        interact(local=locals(), banner="""
The Interface is now running and you've been dropped into Python's
interactive console. The following objects are available:

interface: The Interface making your Midi Controller smart
bcr:       Your BCR 2000 Midi Controller
loop:      The Midi Port that leads to your DAW

Call the function 'attributes' on an object to find out what attributes
it carries. eg.: attributes(interface)

Exit by hitting Ctrl+Z and then Enter.
        """)


    else:  # non-interactive mode
        while True:
            yield_thread()
except KeyboardInterrupt:
    pass

save_snapshots(interface, make_snapshots_file_name(args.profile))

exit()
