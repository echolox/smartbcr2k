# Smart Midi Controller Interface (SMCI)

## You want to have a smarter midi controller

The aim of this project is to create a framework to augment any Midi controllers with more intelligent features like:
- Simulate more controls than the device actually has
- Different behavior and functionality of controls (buttons, dials, etc.) based on Views/Pages
- Automation of values (think of LFOs on Control Changes before we even hit the DAW)
- Save and load snapshots of the current values
- Mapping controls to behave like other controls to create Macros


The only requirements for a Midi controller for all of this to work are:
- Has to allow Control Changes to be sent to the unit for visual feedback (LEDs, motorized faders etc.)
- Buttons can be set to function in momentary mode, not (just) toggle mode

Prime examples would be Behringer's BCR 2000 and BCF 2000\*.

\* not tested yet with the BCF but its functionality seems identical to the BCR

#### Here's a quick video demo: >> https://www.youtube.com/watch?v=NkC_V2LblDI <<


## How does it work?

The SMCI program sits between your Midi controller and your DAW. Any input fed from the controller into SMCI will "translate" it into an action on the SMCI itself (change to a different view, apply an LFO etc.) or route it to your DAW. You can set up many different Views on your controller, which allow you to map the same dial or button to different functionalities based on which view is active. Think of the SMCI as a website where each view is a different subpage of that website. They all have the same structure but allow you to do something different with the same controls.

All of this is compatible with any DAW that lets you map things to Midi CC messages, because that's all the SMCI routes to your DAW. For Windows users that also means hot-plugging Midi Controllers becomes possible when routing them through the SMCI.

The SMCI is dependent some kind of virtual midi cable running on your computer (see below for recommendations).

## Installation

You will need **Python 3.5+** and install the packages listed in `reqs.txt` by using `pip install reqs.txt`. It is advisable to create a virtualenvironment for this.

Apart from that you will need some software that provides you with virtual midi cables:
- **[Win]** [loopMidi](https://www.tobias-erichsen.de/software/loopmidi.html) (free for private, non-commercial use)

*Please add more software to the list if you know of any*

If you are using virtual midi cables that act as a loopback (as in: anything that hits its input automatically comes out of its output) you will need to create two ports to route between the SMCI and your DAW, one for each direction. Otherwise you will run into nasty feedback loops. Example:
```
      +---> smci_to_daw >--+
      |                    |
SMCI -+                    +-- DAW
      |                    |
      +---< daw_to_smci <--+
```
In Ableton Live it would look like this. Notice how we don't directly connect to the BCR2000 ports:
![Ableton Live Midi Screenshot](https://cloud.githubusercontent.com/assets/10747793/25379343/fceb28a8-29ac-11e7-8082-0958e5a531c3.png)

You will also need to dedicate at least one page on your BCR2k (used here as an example) to the SMCI. Map all your controls in this order: Macro Dials, Macro Dial Buttons, Buttons, Main Dials, Bottom Right Buttons, starting with CC1 und Channel 7 (eventually 1, my config is a little old). The last Button on the very bottom right should end up with CC 108. See the [definition of the BCR2k](devices/bcr2k.py) device for further details.

Now you should be able to start the main script. I'm providing my own profile that has a bunch of features already configured. Just start it by running
```
python main.py echolox -i
```
`echolox` is the name of the profile to be loaded. It refers to a `echolox.bcr` file in the profiles directory.
The `-i` flag drops us into interactive mode. This is useful if you want to do some scripting while the unit and the SMCI are running, possibly even connected to the DAW. Remember: Because this script sits between your controller and the DAW it is possible to stop, start, dis- and reconnect controllers and develop new features without ever closing your DAW.
Exit using `CTRL+Z then Enter`.


## Creating profiles

To create your own profiles you will need to look into the architecture of this framework a little bit. It's best to start with the [definition of the BCR2k](devices/bcr2k.py) and [the provided profile script](profiles/echolox.py).

The profiles that get loaded by the SMCI are JSON files that save every property needed to configure the unit. For very elaborate profiles this quickly becomes too complex so it's easier to write a script that generates such a profile using `python make_profile profilename`.

**TODO**: Proper introduction to writing your own profile scripts.

