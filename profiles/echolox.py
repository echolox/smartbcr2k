import util

from smci import View
from targets import Parameter, SwitchView, PageFlip, FlexSetter, FlexParameter, ModView, SnapshotButton, SnapshotSelector
from modifiers.modifier import AttributeType
from modifiers.basic import Basic, Sine, Square, Saw, SampledRandom
from modifiers.stepsequencer import StepSequencer

comment = {
    "author": "Matt 'Echolox' Duncan",
    "comment":
    """
    The main feature of this profile is the "Struct of Arrays" vs "Arrays of Structs"
    approach. The two rows of buttons on the BCR2k map to these two kinds of views.
    
    From the init view...
    Pushing a button on the upper row selects the respective track and displays
    all 8 FX on that track from left to right. The buttons in the lower row activate
    those FX.

    Pushing a button on the lower row selects the respective fx and displays all
    8 tracks from left to right. The buttons in the upper row now activate those FX.

    So you can either choose a track and manipulate all FX on that or select an
    effect and have all tracks in front of you so you can manipulate the same effect
    on all tracks at once.

    The BCR2k's pageflip button is mapped to the lower left of the buttons on the
    bottom right of the unit.

    The first Macro Bank is set to FlexParameters. Manipulate any dial and then
    click the button of a macro dial to map that dial to the same Parameter you
    manipulated previously.

    If you want to support the development of this project check out my music
    on echolox.bandcamp.com or youtube.com/echolox and leave a few bucks if you like :)
    """,
    "email": "echolox+dev@gmail.com",
    "bandcamp": "echolox.bandcamp.com",
    "website": "echolox.com",
    "twitter": "@echolox",
}


def map_controls_to_targets(view, controls, targets):
        """ Maps the list of controls to the list of targets. """
        for control, target in zip(controls, targets):
            view.map_this(control.ID, target)

def configure_controls(view, controls, attribute, value):
    """ In the provided view, configures the list of controls by setting the attribute to the provided value. """
    for control in controls:
        view.configuration[control.ID][attribute] = value


# @MOVE: This out into util or something
def ccc(channel=0, cc=0, forbidden=None):
    """
    Generates channel and cc messages starting with the ones provided on construction.
    :param i: 
    :param channel: 
    :param cc: 
    :return: 
    """
    if forbidden is None:
        forbidden = []

    while channel <= 16:
        yield channel, cc

        while True:
            cc = (cc + 1) % 128
            if cc not in forbidden:
                break

        if cc == 0:  # We wrapped around
            channel += 1


def create(interface):
    """
    :param iterface: The Interface object managing the Devices, Targets, Modifiers etc. on which we build the profile
    """

    """ HELPERS AND SHORTCUTS
    First, let's define some helper variables to make some of the following lines shorter.
    """
    # It's just so much to type every time
    i = interface

    # The BCR2k is in a Shell within the Interface. Don't know what that means? Have a look in
    # util.threadshell. Anyway, for the purposes of setting up a profile we'd like to have direct
    # access to the Device.
    # TODO: Inject this when calling create from make_profile
    bcr = i.input._o
    # Macro dials. Get each bank using [i] with i in [0, 1, 2, 3]
    macros = bcr.macros

    # The initial View that is active on startup
    view_init = i.view


    """ UNIVERSAL CONTROLS
    We start out by defining which controls (buttons and dials) should be used by the Interface
    to display certain pre-configured values to us. An example would be the configuration of 
    Modifiers like LFOs (frequency, amplitude, offset, positive...). When switching into the config
    view of an LFO, these values will be made adjustable for us using the controls defined as
    universal controls.
    
    boolean refers to settings that can be either on or off.
    span refers to settings that can hold a value within a certain interval (typically 0-1 or 0-127)
    """
    # Use the second row of buttons
    i.add_to_universal_controls(AttributeType.boolean, bcr.menu_rows(1))
    # All the dials, starting in the top left and going row by row
    i.add_to_universal_controls(AttributeType.span, bcr.dials)

    """ SETUP MODIFIERS
    We map four types of modifiers to the function buttons of the BCR2k. Holding the button of an
    LFO down will allow us to dial in a modulation power for the target values in that view.
    Tapping it (and letting go immediately) brings up the config view where you can adjust frequency,
    amplitude etc.
    
    Make sure to pick unique names!
    """
    # TODO: Make this helper function available elsewhere
    def create_lfo(interface, name, button, Init_Type):
        """
        Creates a LFO and maps it to a button on the active view of the Interface. Returns the LFO and the ModView
        :param interface: Interface to map on
        :return: (LFO, ModView)
        """
        lfo = Basic(name, init_lfo=Init_Type)
        view = ModView("%s_ModView" % name, interface, lfo)
        interface.add_modifier(lfo)
        interface.view.map_this(button.ID, view)
        interface.view.configuration[button.ID]["toggle"] = False
        return lfo, view

    lfos, lfo_views = [], []
    sa = util.split_append(lfos, lfo_views)

    sa(create_lfo(i, "LFOSine", bcr.command_buttons[0], Sine))
    sa(create_lfo(i, "LFOSaw", bcr.command_buttons[1], Saw))
    sa(create_lfo(i, "LFORandom", bcr.command_buttons[2], SampledRandom))

    steps = StepSequencer("StepSequencer")
    steps_view = ModView("StepSequencer_ModView", i, steps)
    i.add_modifier(steps)
    view_init.map_this(bcr.command_buttons[3].ID, steps_view)
    view_init.configuration[bcr.command_buttons[3].ID]["toggle"] = False


    """ GLOBAL PAGEFLIP
    Our simulated BCR2k provides us three more rows of dials than the real unit has.
    To switch between the two, we need to issue a pageflip command. Thankfully, there's
    a Target for that!
    
    We map it to the bottom left button of the function buttons (EDIT, originally).
    It is set to toggle. Otherwise you'd need to hold the button down to reach the second
    set of dials, which might also suit your workflow.
    """
    global_pageflip = PageFlip("Global Pageflip", i, bcr)
    pageflip_button = bcr.function_buttons[2]
    view_init.map_this(pageflip_button.ID, global_pageflip)
    view_init.configuration[pageflip_button.ID]["toggle"] = True


    """ MACRO BANKS ###
    # BANK 1
    The first dial is set up to save and load snapshots. Turn the dial to select a snapshot,
    hold it down to save and tap it to load.
    
    The other 7 dials are set up as FlexParameters. After manipulating any other control on
    BCR2k, tap one of these to map the same Target to it. Dynamic Macro controls!
    
    # BANKS 2-4
    No special functions here, so we map them directly to output parameters. We make use of
    the quick_parameter method of the interface we will sequentially assign the controls
    Parameter Targets. All these do is send out a CC message to the output Device of the Interface.
    """
    # BANK 1
    snpsel = SnapshotSelector("Snapshots", i)
    snpset = SnapshotButton("SnapshotButton", i, snpsel)

    flex_params  = [FlexParameter("Flex_%i" % index, i)          for index in range(1, 8)]
    flex_setters = [FlexSetter("FlexSetter_%i" % index, i, flex) for index, flex in enumerate(flex_params, start=1)]

    map_controls_to_targets(view_init, bcr.macro_bank(0),         [snpsel] + flex_params)
    map_controls_to_targets(view_init, bcr.macro_bank_buttons(0), [snpset] + flex_setters)
    configure_controls(view_init, bcr.macro_bank_buttons(0), "toggle", False)

    # Skip 8 parameters (CC Values) to keep offset because I'm too lazy to remap in Ableton Live
    i.parameter_maker.skip(8)

    # Collect all the Targets that the BCR2k's macros are mapped to, starting with the ones we already did
    macro_targets = flex_params

    # BANKS 2-4: Good old CC Parameters
    # 2: Parameters (Patch selection)
    for macro in bcr.macro_bank(1):
        macro_targets.append(i.quick_parameter(macro.ID))

    # 3: Parameters (Reverb Send)
    for macro in bcr.macro_bank(2):
        macro_targets.append(i.quick_parameter(macro.ID))

    # 4: Parameters (Delay Send)
    for macro in bcr.macro_bank(3):
        macro_targets.append(i.quick_parameter(macro.ID))


    """ INIT VIEW  DIALS
    Just map all of the dials to simple CC Parameters. Nothing fancy
    bcr.dials includes the second set of dials we can reach using the pageflip function.
    """
    for dial in bcr.dials:
        i.quick_parameter(dial.ID)


    """ MENU BUTTONS: Let's get complicated!
    The top row of buttons let's us select a track. On each track, the buttons in the bottom row activate
    and deactivate the 8 effects on that track. Each column of 6 dials (pageflip!) controls maps to the
    parameters of that effect. 
    
    That means, for each track we need to have a View with unique Parameters per Dial. We also need to make
    sure that in each view the top row still maps to the other Track Views. The button of the currently active
    view should blink and lead us back to the Init View.
    
    Suppose you're back in the Init View. Instead of choosing a track on the top row, you can select an effect on
    the bottom row. Now, the top row houses the activators for that effect for each track. These are the same
    Targets (not duplicates, the exact same objects) we mapped per track before that. We do the same things with
    the dials.
    
    Tapping another button in the bottom row chooses a different effect. Tapping the same button (that's again
    blinking) takes us back to Init View.
    """
    # Construct the Views. We'll fill them later but need them now to construct SwitchTargets
    views_tracks   = [View(bcr, "Track_%i" % (index + 1)) for index in range(8)]
    views_fx       = [View(bcr, "FX_%i"    % (index + 1)) for index in range(8)]

    # These SwitchTargets will bring us to the Views constructed above
    switch_tracks  = [SwitchView("To_T%i"  % (index + 1), i, views_tracks[index]) for index in range(8)]
    switch_fx      = [SwitchView("To_FX%i" % (index + 1), i, views_fx[index])     for index in range(8)]
    switch_to_init =  SwitchView("To_INIT",               i, view_init)

    # Distribute them on the Init View
    map_controls_to_targets(view_init, bcr.menu_rows(0), switch_tracks)
    configure_controls(view_init, bcr.menu_rows(0), "toggle", False)

    map_controls_to_targets(view_init, bcr.menu_rows(1), switch_fx)
    configure_controls(view_init, bcr.menu_rows(1), "toggle", False)


    ### FOR ALL OF THE FOLLOWING VIEWS
    ### We want to set up the follow controls, so lets define a helper function for that
    def controls_for_all(view):
        """
        - Macro Buttons and Dials
        - Pageflip
        - Modifiers
        :param view: The view on which to map
        """
        ## @TODO: Create some "map globally" functionality so we only need to do this once for all possible views
        ##        or at least a subset of views.

        # Macros
        for dial, target in zip(bcr.macros, macro_targets):
            view.map_this(dial.ID, target)
        for mbutton, target in zip(bcr.macro_bank_buttons(0), flex_setters):
            view.map_this(mbutton.ID, target)
            view.configuration[mbutton.ID]["toggle"] = False

        # Command Buttons:
        view.map_this(pageflip_button.ID, global_pageflip)
        view.configuration[pageflip_button.ID]["toggle"] = True

        # Modifiers
        map_controls_to_targets(view, bcr.command_buttons, lfo_views)
        configure_controls(view, bcr.command_buttons, "toggle", False)

        view.map_this(bcr.command_buttons[3].ID, steps_view)
        view.configuration[bcr.command_buttons[3].ID]["toggle"] = False
    ### END GLOBAL STUFF


    ### We start by going track by track and mapping the FX activators, FX parameters and of course
    ### our top row menu buttons to lead us to the other tracks or back to Init View

    # Create a generator that will yield the next combination of Channel and CC Value for us
    gen = ccc(channel=1, cc=i.parameter_maker.next_cc, forbidden=i.parameter_maker.forbidden)
    gen_n = lambda n: [next(gen) for _ in range(n)]

    # We want to move through the dials by column, but do so in one big list
    dials = util.flatten(bcr.dialsc)

    # Now let's iterate per Track
    for track_index in range(8):
        view = views_tracks[track_index]

        ## First, let's map things that we want to keep from init view, our global controls if you will
        controls_for_all(view)

        # First Row Buttons: Switch To View
        index = 0
        for button, target in zip(bcr.menu_rows(0), switch_tracks):
            view.configuration[button.ID]["toggle"] = False
            if index != track_index:
                view.map_this(button.ID, target)
            else:
                view.map_this(button.ID, switch_to_init)
                view.configuration[button.ID]["blink"] = True
            index += 1

        # Second Row Buttons: Effects activators
        fx_onoff = []
        for index, (channel, cc) in enumerate(gen_n(8), start=1):
            p = Parameter("T%i_FX%i_OnOff" % (track_index + 1, index), i, channel, cc, is_button=True)
            fx_onoff.append(p)
        map_controls_to_targets(view, bcr.menu_rows(1), fx_onoff)
        # SPECIAL CASE: Stutter and Repeater momentary
        # @TODO: Move this somewhere else for easier configuration
        view.configuration[bcr.menu_rows(1)[4].ID]["toggle"] = False
        view.configuration[bcr.menu_rows(1)[6].ID]["toggle"] = False

        # Effects parameters
        fx_params = []
        subparam_index = 0
        for index, (channel, cc) in enumerate(gen_n(48), start=1):
            p = Parameter("T%i_FX%i_%i" % (track_index + 1, (index - 1) / 6 + 1, subparam_index + 1), i, channel, cc)
            fx_params.append(p)

            subparam_index = (subparam_index + 1) % 6
        map_controls_to_targets(view, dials, fx_params)

        i.views.append(view)
    # END PER TRACK VIEW

    # Now we'll iterate per FX. The Parameters already exist, we just need to cherry-pick them
    for index, view in enumerate(views_fx):
        # Don't forget our "global controls"
        controls_for_all(view)

        fx_index = 0
        for button, target in zip(bcr.menu_rows(1), switch_fx):
            view.configuration[button.ID]["toggle"] = False
            if fx_index != index:
                view.map_this(button.ID, target)
            else:
                view.map_this(button.ID, switch_to_init)
                view.configuration[button.ID]["blink"] = True
            fx_index += 1

        for track, t_view in enumerate(views_tracks):
            onoff = t_view.map[bcr.menu_rows(1)[index].ID][0] 
            params = [t_view.map[d.ID][0] for d in bcr.dialsc[index]]

            view.map_this(bcr.menu_rows(0)[track].ID, onoff)
            if index in (4, 6):
                view.configuration[bcr.menu_rows(0)[track].ID]["toggle"] = False

            for subparam, p in enumerate(params):
                view.map_this(bcr.dialsc[track][subparam].ID, p)

        i.views.append(view)
    # END PER EFFECT VIEW
