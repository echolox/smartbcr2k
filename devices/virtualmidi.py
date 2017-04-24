from rtmidi.midiutil import open_midioutput, open_midiinput
from devices import OutputPort
from .ports import open_port_by_name


class VirtualMidi(OutputPort):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_midiinput (open_port_by_name("ableton_to_i", "input"))
        self.output, self.outname = open_midioutput(open_port_by_name("i_to_ableton", "output"))
        super().__init__("VirtualMidi", *args, **kwargs)

        self.ignore_daw = kwargs.get("ignore_daw", False)
            
    def input_callback(self, event):
        if not self.ignore_daw:
            super().input_callback(event)


