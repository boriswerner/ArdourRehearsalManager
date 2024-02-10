# ArdourRehearsalManager

## Ardour
Copy _osc_hook_session_loaded.lua to 
%localAppData%\Ardour8\scripts
(Create folder if not existent)

In Ardour: 
Edit > Lua Scripts > Script Manager > Action Hooks > New Hook
Select "OSC Session loaded message" and click add

Edit > Preferences > Control Surfaces
Enable "Open Sound Control (OSC)"
> Show Protocol Settings
Port Mode: "Manual - Specify Below"
Reply Manual Port: 8000
Debug: Log all messages

Other useful Ardour settings:

Edit > Preferences > Metering > Region Analysis > Enable automatic analysis of audio (set true)
(To enable Jump to next transient with Ctrl-Left/Right)

## TouchOSC

Load ARM_view_fretboard.tosc from https://github.com/boriswerner/touchosc_templates/ in TouchOSC
Setup an OSC connection (Edit/Connections/OSC) of type UDP
In ARM go to Tools/OSC Conncetion and enter connection details to Touch OSC and select "Connect to OSC server"

## Known issues / Roadmap
Unicode characters in lyrics and structure files are not shown correctly in Touch OSC
Missing config file leads to error
Tests with empty setlist / missing setlist file (errors?)
First song can only be started from bottom of the list or when no song is selected (can not be done actively)
Error handling in Touch OSC template (e.g. Key = N/A)
Ardour OSC hook, muting, etc.
Maintenance of band members
