from .ports import Device, ccc2ID, ID2ccc, open_port_by_name
from .controls import Dial, Button


class BCR2k(Device):
    """
    An implementation of the Behringer BCR 2000 Midi Controller. Configure your hardware like so:
    - Set all controls to CC on channel 7 (eventually to 1, right now 7 because my config is stupid and old)
    - From the top left down to the bottom right, configure your Dials and Buttons to send out
      CC values starting with 1
    - Set all buttons to momentary
    - Set all value ranges from 0 to 127
    """
       
    def __init__(self, channel_offset=7, *args, **kwargs):
        # Typically you would configure your BCR2k to start on channel 1
        # Since I don't (or maybe didn't depending on when you read this)
        # I needed a way to offset to channel 7 where my main page on the
        # device starts.
        self.channel_offset = channel_offset

        # Don't forward the auto_start flag to the parent
        auto_start = kwargs.get("auto_start", False)
        try:
            del kwargs["auto_start"]
        except KeyError:
            pass

        super().__init__("BCR2k", *args, auto_start=False, **kwargs)

        self.output, self.outname = open_port_by_name("BCR", "output")
        self.input,  self.inname  = open_port_by_name("BCR", "input")

        if auto_start:
            self.start()

    def setup_controls(self):
        ID = ccc2ID(self.channel_offset, 0) + 1  # Because I use Channel 7, starting with cc 1
                                                 # That's gonna change eventually

        # A helper function to create n controls of the given Class with some options
        # Returns a list of newly created controls
        def make_controls(ID, n, Cls, *args, **kwargs):
            newly_added = []
            for i in range(n):
                c = self.controls[ID] = Cls(ID, self, *args, **kwargs)
                newly_added.append(c)
                ID += 1
            return ID, newly_added

        ID, self.macros = make_controls(ID, 32, Dial)
        ID, self.macro_buttons = make_controls(ID, 32, Button, toggle=False)
        ID, self.menu_buttons = make_controls(ID, 16, Button, toggle=True)

        # We'll only paginate the main dials to get 48 instead of just 24
        ID2 = ID + 16 * 128
        ID, self.dials = make_controls(ID, 24, Dial)
        _,  page2_dials = make_controls(ID2, 24, Dial)
        self.dials.extend(page2_dials)

        # Dials by column and Dials by row
        self.dialsc = [[] for _ in range(8)]
        self.dialsr = [[] for _ in range(6)]
        row = 0
        column = 0
        for dial in self.dials:
            self.dialsr[row].append(dial)
            self.dialsc[column].append(dial)

            column += 1
            if column == 8:
                column = 0
                row += 1

        ID, self.command_buttons = make_controls(ID, 4, Button, toggle=False)

    def macro_bank(self, bank):
        """
        Returns a list of 8 macros on the zero-indexed bank (0, 1, 2, 3).
        """
        return self.macros[bank * 8: bank * 8 + 8]

    def macro_bank_buttons(self, bank):
        """
        Analog to macro_bank but for its buttons.
        """
        return self.macro_buttons[bank * 8: bank * 8 + 8]

    def menu_rows(self, row):
        """
        Returns the row of buttons below the macro dials. Zero-indexed
        """
        return self.menu_buttons[row * 8: row * 8 + 8]

    def page_update(self):
        """
        We only paginate the main dials so depending on the active page we only want to
        update the main dials that are actively shown.
        """
        p = self.page
        for dial in self.dials[p*24:p*24 + 24]:
            self.cc(dial.ID, dial.get_value())

    def control_on_active_page(self, control):
        """
        Since we only paginate the main dials all other controls are always on the
        active page.
        """
        if control in self.dials:
            return super().control_on_active_page(control)
        else:
            return True

if __name__ == "__main__":
    from rtmidi.midiutil import list_input_ports, list_output_ports
    from threadshell import Shell
    from queue import Queue, Empty, Full

    list_input_ports()
    list_output_ports()
    bcr = BCR2k(auto_start=False)
    sbcr = Shell(bcr, bcr.update)

    q = Queue()
    sbcr.add_listener(q)

    try:
        while True:
            try:
                event, *data = q.get_nowait()
                print(event.name, data)
            except Empty:
                pass
    except KeyboardInterrupt:
        pass

    bcr.remove_listener(q)
