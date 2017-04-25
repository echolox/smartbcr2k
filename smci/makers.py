from targets import Parameter, SwitchView
from .view import View


class Exhausted(Exception):
    pass


class ParameterMaker(object):
    """
    Produces Targets of the type Parameter. Everytime a new target is
    requested it assigns that target the next available CC.
    """

    # These CC values could cause problems when mapped to (in Ableton Live)
    forbidden = [123]

    def __init__(self, interface, channel, prefix="CC", first_cc=1, expand=True):
        self.interface = interface
        self.channel = channel
        self.next_cc = first_cc
        self.prefix = prefix
        self.expand = expand

        self.exhausted = False

    def make(self, is_button=False):
        if self.exhausted:
            raise Exhausted

        name = "%s_%i" % (self.prefix, self.next_cc)
        t = Parameter(name, self.interface, self.channel, self.next_cc, is_button=is_button)        

        self.advance()

        return t

    def advance(self):
        while True:
            self.next_cc += 1
            if self.next_cc not in self.forbidden:
                break

        if self.next_cc > 128:
            if self.expand and self.channel < 16:
                self.next_cc = 1
                self.channel += 1
            else:
                self.exhausted = True

    def skip(self, n):
        """
        Skips n cc values
        """
        for _ in range(n):
            self.advance()


class ViewMaker(object):

    def __init__(self, interface, prefix="V"):
        self.interface = interface
        self.next_index = 1
        self.prefix = prefix

    def make(self, view=None):
        name = "%s_%i" % (self.prefix, self.next_index)
        if not view:
            view = View(self.interface.input, name=name)
        t = SwitchView(name, self.interface, view)
        self.next_index += 1
        return t, view


