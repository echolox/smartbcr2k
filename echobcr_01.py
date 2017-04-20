from modifiers import LFOSine
from interface import View
from targets import Parameter, SwitchView
from util import flatten

def create(i):
    bcr = i.input._o

    ### MACRO BANKS ###
    ## Dials: Parameters
    ## Buttons: Not used
    macros = bcr.macros

    # 1: Empty for now. Later: Dynamic Targets
    for macro in bcr.macro_bank(0):
        pass

    # 2: Parameters (Patch selection)
    for macro in bcr.macro_bank(1):
        i.quick_parameter(macro.ID)

    # 3: Parameters (Reverb Send)
    for macro in bcr.macro_bank(2):
        i.quick_parameter(macro.ID)

    # 4: Parameters (Delay Send)
    for macro in bcr.macro_bank(3):
        i.quick_parameter(macro.ID)

    ### MENU BUTTONS ###
    ## Top Row: Switch to View of that Track
    ## Buttom Row: Switch to View of that Effect per Track
    ## First we set up the targets and then distribute them to the eight views
    to_init_view = SwitchView("To_INIT", i, i.view)
    views_tracks = [View(bcr, "Track_%i" % (it + 1)) for it in range(8)]
    views_fx     = [View(bcr, "FX_%i"    % (it + 1)) for it in range(8)]
    switch_tracks = [SwitchView("To_T%i" % (it + 1), i, views_tracks[it]) for it in range(8)]
    switch_fx =     [SwitchView("To_FX%i" % (it + 1), i, views_fx[it]) for it in range(8)]
    
    next_cc = i.parameter_maker.next_cc
    # @MOVE: This out into util or something
    def ccc(channel=0, cc=0):
        while channel <= 16:
            yield channel, cc

            cc = (cc + 1) % 128
            if cc == 0:  # We wrapped around
                channel += 1

    gen = ccc(7, next_cc)

    dials = flatten(bcr.dialsc)
    for track_index in range(8):
        view = views_tracks[track_index]

        fx_onoff = []
        it = 1
        for channel, cc in [next(gen)] * 8:
            p = Parameter("T%i_FX%i_OnOff" % (track_index + 1, it),
                          i, channel, cc, is_button=True) 
            print(p)
            fx_onoff.append(p)
            it += 1

        fx_params = []
        fx_index = 1
        subparam_index = 0
        for channel, cc in [next(gen)] * 24:
            p = Parameter("T%i_FX%i_%i" % (track_index + 1, fx_index, subparam_index + 1),
                          i, channel, cc)
            fx_params.append(p)
            subparam_index = (subparam_index + 1) % 3
            if subparam_index == 0:
                fx_index += 1

        # First Row Buttons: Switch To View
        it = 0
        for button, target in zip(bcr.menu_rows(0), switch_tracks):
            if it != track_index:
                view.map_this(button.ID, target)
            else:
                view.map_this(button.ID, to_init_view)
            it += 1

        # Second Row Buttons: FX On Off
        for button, target in zip(bcr.menu_rows(1), fx_onoff):
            view.map_this(button.ID, target)
         
        # Dials:
        for dial, target in zip(dials, fx_params):
            view.map_this(dial.ID, target)
        
        i.views.append(view) 
