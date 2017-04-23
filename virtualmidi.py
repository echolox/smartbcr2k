from rtmidi.midiutil import open_midioutput, open_midiinput
from devices import OutputPort

DEFAULT_LOOP_IN = 11
DEFAULT_LOOP_OUT = 12 

class VirtualMidi(OutputPort):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_midiinput (DEFAULT_LOOP_IN)
        self.output, self.outname = open_midioutput(DEFAULT_LOOP_OUT)
        super().__init__("VirtualMidi", *args, **kwargs)

        self.ignore_daw = kwargs.get("ignore_daw", False)
            
    def input_callback(self, event):
        if not self.ignore_daw:
            super().input_callback(event)


