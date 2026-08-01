# Running the LagKing Connector

Two audiences: someone who wants to **run it from source on Windows** (that's
the real thing), and someone who wants to **check their changes anywhere else**
without hardware.

---

## Windows, from source — the real run

### ⚠️ Python 3.12, 64-bit. Not 3.13.

`requirements.txt` pins OCR support to a prebuilt wheel:

```
tesserocr @ https://github.com/simonflueckiger/tesserocr-windows_build/releases/
download/tesserocr-v2.7.1-tesseract-5.4.1/tesserocr-2.7.1-cp312-cp312-win_amd64.whl
```

`cp312-cp312-win_amd64` means **CPython 3.12, 64-bit Windows, and nothing
else**. On 3.13 pip fails with "not a supported wheel on this platform", and
the fix is a different interpreter, not a different flag. Verified live
2026-08-01 (HTTP 200, ~4 MB).

`tesserocr` is only used by the screenshot/OCR launch-monitor path. It is not
on the LagKing putting path at all — but it is imported at module scope, so
the app will not start without it.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python LagKingConnector.py
```

### Restore the Rapsodo secret before building (one command)

`Rapsodo MLM2PRO BT` authenticates against Rapsodo's simulator API using a key
in `src/bluetooth/mlm2pro_secret.py`. That path is in `.gitignore` (line 170),
so a fresh clone does **not** have the file on disk and MLM2PRO BT will fail.

It is not lost — upstream committed it in 2024 and never deleted it. It lives on
upstream's `BT-BLEAK` and `r10` branches, so any clone that fetches upstream can
restore it:

```bash
git fetch upstream
git show 19ff295:src/bluetooth/mlm2pro_secret.py > src/bluetooth/mlm2pro_secret.py
```

Verified 2026-08-01: restores cleanly and its encrypt/decrypt round-trips.
It stays gitignored afterwards, so it will not be committed here.

**Do this before `pyinstaller`, not just before running from source.** The file
is read at MLM2PRODevice construction, so an exe built without it ships with
MLM2PRO BT broken — and nothing about the build warns you.

Note the two MLM2PRO entries are different mechanisms, not a preference:
`MLM2PRO BT` is direct Bluetooth (needs the key above), `MLM2PRO` is the
phone-mirror route (Rapsodo Range on the phone, mirrored to the PC, read by OCR).

### Bluetooth

Pair the gate in Windows Bluetooth settings first. Many desktop sim PCs have no
BLE radio at all and need a ~$15 USB BLE dongle — the same constraint the
MLM2PRO path has always had.

### Then

Putting Settings → system is already **LagKing** (default in this fork) →
set **Putting surface stimp** to your mat → Save → press the putting Start
button.

---

## Anywhere else — headless checks, no hardware

Qt has an `offscreen` platform plugin, so the settings model and the widget
tree can be exercised on macOS or Linux. That covers the failure mode that
actually bites: a missing widget, a settings key read without a default, a save
that does not round-trip. All three crash on launch, and catching them here
beats catching them in a tester's log.

```bash
python -m venv .venv
.venv/bin/pip install PySide6-Essentials PySide6-Addons \
    opencv-python-headless pyqtgraph pillow
QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python tests/test_lagking_settings.py
```

26 checks. `PySide6-Addons` is only needed for the launch-speed maths (it
pulls in QtBluetooth); without it those skip cleanly rather than fail.

Windows-only imports are stubbed in the test module — see its docstring.

---

## First bench pass with a real gate

Order matters; item 4 is the one people skip.

1. Connect. The gate's serial log should show the client-kind write, and the
   gate should classify us as a connector rather than a phone.
2. **Select the putter in GSPro.** Gate wakes.
3. Idle 3 minutes with the putter still selected — the gate must **not** sleep
   (LED stays ready, not dim-blue breathing). Then putt: it must measure
   normally rather than swallow the putt.
4. **Switch to any other club.** The gate must go to sleep promptly. This is
   the proof that an idle connector is not holding it awake and draining the
   battery (~347 mA awake vs ~79 mA asleep) — and it is the half everyone
   forgets to check.
5. Change the setup distance in the phone app, reconnect the connector, and
   confirm the reported speed shifts. That proves the ...8127 read, rather
   than the 2.0 ft fallback, is what is feeding the correction.
6. Sanity-check distance: putt a known length on the mat and see what GSPro
   does with it. The launch-speed recovery is derived from the gate's own
   roll-out model; if GSPro's putting physics differs materially, this is
   where it shows up.
