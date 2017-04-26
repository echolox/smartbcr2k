from modifiers import *
from modifiers.basic import bpm_sync
from smci import View
from targets import Parameter, SwitchView, PageFlip, FlexSetter, FlexParameter, ModView, SnapshotButton, SnapshotSelector
from util import flatten, iprint

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

def create(i):
    bcr = i.input._o

    s = Sine(frequency=bpm_sync(180, 4))
    sview = ModView("LFOSine_ModView", i, s)
    i.add_modifier(s)
    modview_button = bcr.command_buttons[0]
    i.view.map_this(modview_button.ID, sview)
    i.view.configuration[modview_button.ID]["toggle"] = False


    ### MACRO BANKS ###
    ## Dials: Parameters
    ## Buttons: Not used
    macros = bcr.macros
    init_view = i.view

    global_pageflip = PageFlip("Global Pageflip", i, bcr)
    pageflip_button = bcr.command_buttons[2]


    # 0: Snapshot Selector
    snpsel = SnapshotSelector("Snapshots", i)
    snpset = SnapshotButton("SnapshotButton", i, snpsel)

    # 1: Flex Targets
    macro_targets = [snpsel] + [FlexParameter("Flex_%i" % (it + 1), i) for it in range(0, 7)]
    for macro, target in zip(bcr.macro_bank(0), macro_targets):
        init_view.map_this(macro.ID, target)

    macro_setters = [snpset] + [FlexSetter("FlexSetter_%i" % (it + 1), i, flex)
                                for it, flex in enumerate(macro_targets[1:], start=1)]
    for mbutton, target in zip(bcr.macro_bank_buttons(0), macro_setters):
        init_view.map_this(mbutton.ID, target)
        init_view.configuration[mbutton.ID]["toggle"] = False

    # Need 8 parameters to keep offset because I'm too lazy to remap in Ableton
    i.parameter_maker.skip(8)

    # 2: Parameters (Patch selection)
    for macro in bcr.macro_bank(1):
        macro_targets.append(i.quick_parameter(macro.ID))

    # 3: Parameters (Reverb Send)
    for macro in bcr.macro_bank(2):
        macro_targets.append(i.quick_parameter(macro.ID))

    # 4: Parameters (Delay Send)
    for macro in bcr.macro_bank(3):
        macro_targets.append(i.quick_parameter(macro.ID))

    # MAIN VIEW BUTTONS AND DIALS

    for dial in bcr.dials:
        i.quick_parameter(dial.ID)
        
#    for command in bcr.command_buttons:
#        i.quick_parameter(command.ID)
    
    i.view.map_this(pageflip_button.ID, global_pageflip)
    i.view.configuration[pageflip_button.ID]["toggle"] = True

    ### MENU BUTTONS ###
    ## Top Row: Switch to View of that Track
    ## Buttom Row: Switch to View of that Effect per Track
    ## First we set up the targets and then distribute them to the eight views
    to_init_view = SwitchView("To_INIT", i, i.view)
    views_tracks = [View(bcr, "Track_%i" % (it + 1)) for it in range(8)]
    views_fx     = [View(bcr, "FX_%i"    % (it + 1)) for it in range(8)]
    switch_tracks = [SwitchView("To_T%i" % (it + 1), i, views_tracks[it]) for it in range(8)]
    switch_fx =     [SwitchView("To_FX%i" % (it + 1), i, views_fx[it]) for it in range(8)]

    for button, to_track in zip(bcr.menu_rows(0), switch_tracks):
        i.view.configuration[button.ID]["toggle"] = False
        i.view.map_this(button.ID, to_track)
    
    for button, to_fx in zip(bcr.menu_rows(1), switch_fx):
        i.view.configuration[button.ID]["toggle"] = False
        i.view.map_this(button.ID, to_fx)
    
    next_cc = i.parameter_maker.next_cc
    # @MOVE: This out into util or something
    def ccc(channel=0, cc=0):
        while channel <= 16:
            yield channel, cc

            while True:
                cc = (cc + 1) % 128
                if cc not in i.parameter_maker.forbidden:
                    break

            if cc == 0:  # We wrapped around
                channel += 1

    gen = ccc(1, next_cc)

    dials = flatten(bcr.dialsc)
    for track_index in range(8):
        view = views_tracks[track_index]

        for dial, target in zip(bcr.macros, macro_targets):
            view.map_this(dial.ID, target)
        for mbutton, target in zip(bcr.macro_bank_buttons(0), macro_setters):
            view.map_this(mbutton.ID, target)
            view.configuration[mbutton.ID]["toggle"] = False

        fx_onoff = []
        it = 1
        for channel, cc in [next(gen) for _ in range(8)]:
            p = Parameter("T%i_FX%i_OnOff" % (track_index + 1, it),
                          i, channel, cc, is_button=True) 

            fx_onoff.append(p)
            it += 1

        fx_params = []
        fx_index = 1
        subparam_index = 0
        for channel, cc in [next(gen) for _ in range(48)]:
            p = Parameter("T%i_FX%i_%i" % (track_index + 1, fx_index, subparam_index + 1),
                          i, channel, cc)
            fx_params.append(p)
            subparam_index = (subparam_index + 1) % 3
            if subparam_index == 0:
                fx_index += 1

        # First Row Buttons: Switch To View
        it = 0
        for button, target in zip(bcr.menu_rows(0), switch_tracks):
            view.configuration[button.ID]["toggle"] = False
            if it != track_index:
                view.map_this(button.ID, target)
            else:
                view.map_this(button.ID, to_init_view)
                view.configuration[button.ID]["blink"] = True
            it += 1


        # Second Row Buttons: FX On Off
        it = 1
        for button, target in zip(bcr.menu_rows(1), fx_onoff):
            view.map_this(button.ID, target)

            # SPECIAL CASE: Stutter and Repeater momentary
            # @TODO: Move this somewhere else for easier configuration
            if it in (5, 7):
                view.configuration[button.ID]["toggle"] = False

            it += 1

         
        # Dials:
        for dial, target in zip(dials, fx_params):
            view.map_this(dial.ID, target)
        
        # Command Buttons:
        view.map_this(pageflip_button.ID, global_pageflip)
        view.configuration[pageflip_button.ID]["toggle"] = True
        view.map_this(modview_button.ID, sview)

        i.views.append(view) 
        

    # END PER TRACK VIEW

    for index, view in enumerate(views_fx):

        for dial, target in zip(bcr.macros, macro_targets):
            view.map_this(dial.ID, target)
        for mbutton, target in zip(bcr.macro_bank_buttons(0), macro_setters):
            view.map_this(mbutton.ID, target)


        it = 0
        for button, target in zip(bcr.menu_rows(1), switch_fx):
            view.configuration[button.ID]["toggle"] = False
            if it != index:
                view.map_this(button.ID, target)
            else:
                view.map_this(button.ID, to_init_view)
                view.configuration[button.ID]["blink"] = True
            it += 1


        for track, t_view in enumerate(views_tracks):
            onoff = t_view.map[bcr.menu_rows(1)[index].ID][0] 
            params = [t_view.map[d.ID][0] for d in bcr.dialsc[index]]

            view.map_this(bcr.menu_rows(0)[track].ID, onoff)
            if index in (4, 6):
                view.configuration[bcr.menu_rows(0)[track].ID]["toggle"] = False

            for subparam, p in enumerate(params):
                view.map_this(bcr.dialsc[track][subparam].ID, p)

        # Command Buttons:
        view.map_this(pageflip_button.ID, global_pageflip)
        view.configuration[pageflip_button.ID]["toggle"] = True
        view.map_this(modview_button.ID, sview)

        i.views.append(view)

    # TODO: Some buttons shouldn't be toggle in some views
