from modifiers import LFOSine

def create(i):
    t = i.quick_parameter(1)
    for macro in i.input.macros[0][1:]:
        i.view.map_this(macro.ID, t)

    if True:
        from modifiers import LFOSine
        s = LFOSine(frequency=1)
        i.add_modifier(s)
        s.target(t)

    init_view = i.view
    _, second_view = i.quick_view(105)
    i.quick_view(105, to_view=init_view, on_view=second_view)

    # Dials
    i.quick_parameter(81)
    i.quick_parameter(82)
    t = i.quick_parameter(83)
    i.view.map_this(84, t)


    # Command button momentary
    i.quick_parameter(106)

    i.switch_to_view(second_view)

    i.quick_parameter(81)
    i.quick_parameter(82)
    t = i.quick_parameter(83)
    i.view.map_this(84, t)

    # Command button toggle
    tt = i.quick_parameter(106)
    second_view.configuration[106]["toggle"] = True
    # TODO: This is indirect configuration


    i.switch_to_view(init_view)
    i.view.map_this(107, tt)
    i.view.configuration[107]["toggle"] = True

