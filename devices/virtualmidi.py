from .ports import open_port_by_name, OutputPort

class VirtualMidi(OutputPort):

    def __init__(self, *args, **kwargs):
        self.input,  self.inname  = open_port_by_name("daw_to_smci", "input")
        self.output, self.outname = open_port_by_name("smci_to_daw", "output")
        print(self.inname, self.outname)
        super().__init__("VirtualMidi", *args, **kwargs)

        self.ignore_daw = kwargs.get("ignore_daw", False)
            
    def input_callback(self, event):
        if not self.ignore_daw:
            super().input_callback(event)


