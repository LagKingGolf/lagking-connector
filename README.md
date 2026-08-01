# LagKing Connector

Free, open-source GSPro connector for a wide range of launch monitors, with
**LagKing** measured putting built in alongside Webcam and ExPutt.

A fork of [springbok/MLM2PRO-GSPro-Connector](https://github.com/springbok/MLM2PRO-GSPro-Connector)
(GPL-3.0). Nearly all of the launch-monitor work here is springbok's; this
fork adds the LagKing putting input and makes it the default. See
[RUNNING.md](RUNNING.md) to run it.

## Modifications from upstream (GPLv3 §5)

This is a **modified version** of springbok's MLM2PRO-GSPro-Connector, released
under the same GPL-3.0 licence. springbok is not affiliated with LagKing and
does not endorse this fork. Changes by LagKing, 2026-05-08 and 2026-08-01:

- **Added** a LagKing V3 BLE putting input (`src/bluetooth/lagking_device.py`,
  `src/worker_device_lagking.py`, `src/device_putting_lagking.py`) and made it
  the default, first-listed putting system. ExPutt and Webcam putting, and every
  launch monitor, are unchanged and still available.
- **Modified** `src/putting_settings.py`, `src/putting.py`, `src/PuttingForm.py`,
  `src/ball_data.py`, `src/log_message.py` to register that input and its settings.
- **Modified** `src/MainWindow.py`: renamed the application and its settings
  directory, with migration from an upstream install.
- **Modified** `src/bluetooth/mlm2pro_device.py` so a missing (gitignored)
  `mlm2pro_secret.py` degrades instead of preventing startup from source.
- **Renamed** the entry point and PyInstaller spec to `LagKingConnector`.
- **Added** `tests/`, `RUNNING.md`.

Complete corresponding source is this repository.

## Launch monitor support

Every launch monitor springbok supports works here unchanged — this fork adds a
putting input, it removes nothing.

**Rapsodo MLM2PRO owners: read [docs/MLM2PRO_SETUP.md](docs/MLM2PRO_SETUP.md)
before you start.** The Bluetooth path needs a third-party authorization done in
the Rapsodo phone app first, and you must authorize **Awesome Golf, not GSPro** —
the GSPro entry is Rapsodo's own official integration, which is the one without
putting. Skipping that step produces an error that reads like a broken install.

One build note: `Rapsodo MLM2PRO BT` also needs `src/bluetooth/mlm2pro_secret.py`,
which upstream gitignores, so it is absent from a fresh clone. Restore it from
upstream history before building — see [RUNNING.md](RUNNING.md).

## LagKing putting input

This fork adds a third putting input alongside Webcam and ExPutt: the
**LagKing** putting gate ([lagking.com](https://lagking.com)), which measures
ball speed and start line and publishes them over BLE.

To use the LagKing input:

1. Power on your LagKing gate.
2. Pair it from Windows Bluetooth settings (it advertises with a name starting
   `LagKing`). The connector uses Qt's BLE stack, which on Windows requires the
   device to already be paired in the OS.
3. Open the connector's Putting Settings dialog and select **LagKing** from
   the Putting System dropdown. Save and start putting.

The connector auto-scans for any peripheral whose name starts with
`LagKing`, connects, subscribes to the gate's putt-notification
characteristic, and forwards each putt to GSPro as a `BallData` payload
(speed in mph, HLA in degrees, VLA / spin zeroed). Disconnect / re-scan
is automatic when the gate goes out of range and back.

LagKing-specific files:
- `src/bluetooth/lagking_device.py` — BLE peripheral wrapper, parses the
  gate's 29-byte putt notification.
- `src/worker_device_lagking.py` — scan + connect + subscribe lifecycle.
- `src/device_putting_lagking.py` — DevicePuttingBase wrapper for the worker.
- Plus single-line additions in `ball_data.py` (PuttType.LAGKING),
  `putting_settings.py` (PuttingSystems.LAGKING + lagking config block),
  `putting.py` (device dispatch), and `PuttingForm.py` (system combo entry).

## Support springbok, the upstream author

Almost all of this connector is springbok's work. The link below goes to
**springbok**, not to LagKing — if this tool is useful to you, that is where
support belongs.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/X8X3OXE0L)

springbok also sells a GSPro control box, the Brain Box, which has some very
unique features. It is springbok's product; LagKing has no involvement in it
and takes nothing from it.

[![Brain Box](images/brain_box.jpg)](https://cascadia3dpd.com/product/brain-box-golf-simulator-control-box-for-gspro/)

To find out more details you go to the online shop [here](https://cascadia3dpd.com/product/brain-box-golf-simulator-control-box-for-gspro/)

## Announcements:

### 7 February 24:

**GSCloud Support**

From V1.01.32 the connector now supports GSCloud. This means you can now use the connector with the GSCloud app.

*Thanks to Paul McMahon for his work on this.*

Go to https://golfsimcloud.com/, reserve a timeslot. 

![Reserve timeslot](images/gscloud_order_page.png)

And when that time comes, copy the IP settings from the second (player 2 / connector) area into the connector, replacing localhost/921 as shown.

![Update IP address](images/gscloud_ip_settings.png)


### 3 November 23: 

**MEVO+ is now supported.**

We are excited to announce support for the Mevo+ launch monitor has now been added to the connector.

For more details see [here](https://github.com/springbok/MLM2PRO-GSPro-Connector/wiki/Mevo-)

## Highlights

*The rest of this README is upstream's own documentation of the connector,
written by springbok. First-person statements below are theirs.*

This connector was built from the ground up to be easy to use, reliable, accurate, and fast.

1. User Friendly
   - Windows application using a Graphical User Interface.
   - All configuration is done via user friendly dialogs.
   - Allows you to easily manage & select from multiple devices.
   
2. Performance:
   - True Windows multithreading with all processes running in seperate threads.
   - Direct use of Windows API which improves performance and reduces reliance on third party libraries.
   - Efficient detection of new shots.
   - Near instant response times.

3. Maintainability:
   - Uses Object-oriented programming techniques.
   - Code seperated into easily maintainable classes.

### Main Window
![Main Window](images/mainwindow.png)

### Devices
![Devices](images/devices.png)

### ROI's
![ROI's](images/specify_rois.png)

### Verify ROI's
![Verify ROI's](images/verify_rois.png)

### Putting
![Putting](images/putting.png)

## Documentation

* For a installation & setup video you can go [here](https://youtu.be/9mhtPu8xs0s)

* For a video on how to setup the Exputt with the connector you can go [here](https://www.youtube.com/watch?v=dV0CH2Vy0Y0)

* For a video on how to setup Webcam putting with the connector you can go [here](https://www.youtube.com/watch?v=6YxTzUPReB0)

* More detailed documentation can be found [here](https://github.com/springbok/MLM2PRO-GSPro-Connector/wiki)

### Joe Lagowski Connector Videos

Subscribe to Joe's YT channel [here](https://www.youtube.com/@JLagGOLF) 

* [How to connect your MLM2PRO and Ex Putt to play GS Pro!](https://www.youtube.com/watch?v=9wt06I_euHs&t=664s)

* [How to connect your Rapsodo MLM2PRO to GS Pro UPDATED!](https://www.youtube.com/watch?v=4iaM1k672ZU&t=1s)

* [THIS CHANGES EVERYTHING! Rapsodo MLM2PRO and EX Putt Playing GS Pro](https://www.youtube.com/watch?v=STaRJjlfda8&t=114s)

### Ben Rinken Videos

Ben has some great content on his YT channel, you can find it [here](https://www.youtube.com/@trpl_bgy) 

* [MLM2PRO GSPRO CONNECTOR - How to set up and configure](https://www.youtube.com/watch?v=-W3tzu48Ad0&t=366s)
* [No More MIS-READS! PERFECT ROI Settings for the MLM2Pro to GSPro Connector!](https://www.youtube.com/watch?v=gPnbO8ycCRY&t=219s)
* [#1 FATAL MISTAKE when Setting ROI's for MLM2Pro to GSPro Connector! HD-ROI's - How did I miss this!](https://www.youtube.com/watch?v=suuIaPTU70I&t=331s)

## Acknowledgments

### Joe Lagowski Facebook Group
I want to give a special thank you to members of Joe's FB group who did a lot of testing and provided invaluable feedback:

**Jarad Cohen**, thanks for your patience and hours of testing!\
**Joe Lagowski\
Ben Barratt**

If you want to join a great golfing community & watch some great golf content I'd encourage you to join Joe's FB group and subscribe to his YouTube channel:

To join the Facebook group follow this [link](https://www.facebook.com/groups/771573784649240)\
You can access Joe's YouTube channel [here](https://www.youtube.com/@JLagGOLF)

### Original Connector
[rowenb](https://github.com/rowengb) for producing the first [connector](https://github.com/rowengb/GSPro-MLM2PRO-OCR-Connector).

### Other Contributors

**[Paul McMahon (wonder99)](https://github.com/wonder99)** for his great work in adding putting to the original connector, also for his testing & valuable feedback.  

**[alleexx](https://github.com/alleexx)** for providing the webcam based putting utility, for more details go [here](https://github.com/alleexx/cam-putting-py). 

## Latest Release

LagKing Connector releases: [LagKingGolf/lagking-connector/releases](https://github.com/LagKingGolf/lagking-connector/releases).

Upstream's own releases (springbok's build, without the LagKing putting input) are [here](https://github.com/springbok/MLM2PRO-GSPro-Connector/releases)


