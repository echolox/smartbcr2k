# Smart Midi Controller Interface (SMCI)

## You want to have a smarter midi controller

The aim of this project is to create a framework to augment any Midi controllers with more intelligent features like:
- Different behavior and functionality of controls (buttons, dials, etc.) based on Views/Pages
- Save and load snapshots of the current values
- Automation of values (think of LFOs on Control Changes before we even hit the DAW)
- Dynamic mapping of controls

The only requirements for a Midi controller for all of this to work are:
- Has to allow Control Changes to be sent to the unit for visual feedback (LEDs, motorized faders etc.)
- Buttons can be set to function in momentary mode, not (just) toggle mode

Prime examples would be Behringer's BCR 2000 and BCF 2000\*.


\* not tested yet with the BCF but its functionality seems identical to the BCR

## How does it work?

The SMCI program sits between your Midi controller and your DAW. Any input fed from the controller into SMCI will "translate" it into an action on the SMCI itself (change to a different view, apply an LFO etc.) or route it to your DAW. You can set up many different Views on your controller, which allow you to map the same dial or button to different functionalities based on which view is active. Think of the SMCI as a website where each view is a different subpage of that website. They all have the same structure but allow you to do something different with the same controls.

All of this is compatible with any DAW that lets you map things to Midi CC messages, because that's all the SMCI routes to your DAW. For Windows users that also means hot-plugging Midi Controllers becomes possible when routing them through the SMCI.

The SMCI is dependent some kind of virtual midi cable running on your computer (see below for recommendations).

## Installation

You will need Python 3.5+ and install the packages listed in `reqs.txt` by using
```pip install reqs.txt```


Apart from this project you will some software to run that provides you with virtual midi cables.
