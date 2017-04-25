from collections import defaultdict as ddict
from copy import copy


class View(object):
    """
    A View is made up of two components:
    - A configuration: How the buttons and dials on the input device should behave
    - A Map: Connects the input device's controls (by their ID) to Targets like
             Parameters, Commands etc. from which their current values can also
             be infered.
    When triggerivating a View, the input Device needs to be reconfigured and the
    values of each mapped target transmitted to that device for it to show those
    values on the hardware.
    """
    def __init__(self, device, name="Unnamed View"):
        # WARNING! The device might be in a threadshell, therefore do not use any of its
        #          methods. Just access attributes. Methods on those attributes are fine though.
        self.name = name
        # Map IDs of a device's controls to configurations:
        # - Buttons: toggle vs momentary
        self.configuration = {}
        for ID, control in device.controls.items():
            self.configuration[ID] = copy(control.default_conf)

        # Map IDs of a device's controls to Targets
        self.map = ddict(list)

    def find_IDs_by_target(self, vtarget):
        """
        Make a list of IDs on this view mapped to the provided target.
        """
        IDs = []
        for ID, vtargets in self.map.items():
            for target in vtargets:
                if target == vtarget or target.is_connected_to(vtarget):
                    IDs.append(ID)
        return IDs

    def map_this(self, ID, t):
        """
        Add a mapping from the ID to the target
        """
        self.map[ID].append(t)

    def unmap(self, ID):
        """
        Remove all mappings of the provided ID
        """
        self.map[ID] = []

    def unmap_target(self, target):
        """
        Remove all mappings to the provided target
        """
        for targets in self.map.values():
            if target in targets: targets.remove(target) 

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()


