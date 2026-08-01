"""Headless checks for the LagKing putting input's settings and UI.

WHY THIS EXISTS
---------------
This connector is a Windows PySide6 app that talks Bluetooth to a gate and TCP
to GSPro, so the reflex is "it can't be tested without the hardware." Most of
it can't. But Qt ships an `offscreen` platform plugin and PySide6 runs on
macOS and Linux, so the settings model and the widget tree CAN be exercised
anywhere — which covers the failure mode that actually bites: a widget that
doesn't exist, a settings key read without a default, a save that doesn't
round-trip. Those crash on launch, and finding them here beats finding them in
a tester's log.

The Windows-only imports (tesserocr, pywin32, ctypes.WinDLL) are stubbed
below. They are dragged in transitively by PuttingForm's import chain and are
not exercised by anything this file asserts.

RUN
---
    python -m venv .venv && .venv/bin/pip install PySide6-Essentials \\
        opencv-python-headless pyqtgraph pillow
    QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python tests/test_lagking_settings.py

Exits non-zero on the first failure. No pytest dependency on purpose — the
project has no test runner and this should stay runnable with a bare
interpreter.
"""

import ctypes
import os
import sys
import tempfile
import types

# --- stub the Windows-only surface before importing anything from src -------
for _name in (
    'tesserocr', 'win32gui', 'win32ui', 'win32con', 'win32api',
    'win32process', 'pywintypes', 'winsound',
):
    sys.modules.setdefault(_name, types.ModuleType(_name))


class _FakeDLL:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, _name):
        return lambda *a, **k: 0


ctypes.WinDLL = _FakeDLL
ctypes.windll = types.SimpleNamespace(
    user32=_FakeDLL(), kernel32=_FakeDLL(), gdi32=_FakeDLL()
)
ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE

from PySide6.QtWidgets import QApplication, QGroupBox, QMessageBox  # noqa: E402

# Modal dialogs block forever with no event loop and no display. __save shows
# one on success, so it has to go before the form is touched.
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)

from src.PuttingForm import PuttingForm  # noqa: E402
from src.putting_settings import PuttingSettings, PuttingSystems  # noqa: E402

_passed = 0


def check(label, condition, detail=''):
    global _passed
    if not condition:
        print(f'FAIL  {label}' + (f'  ({detail})' if detail else ''))
        sys.exit(1)
    _passed += 1
    print(f'pass  {label}' + (f'  [{detail}]' if detail else ''))


class _FakePaths:
    def __init__(self, root):
        self._root = root

    def get_config_path(self, name, ext):
        return os.path.join(self._root, name + ext)


def main():
    tmp = tempfile.mkdtemp()
    paths = _FakePaths(tmp)
    app = QApplication.instance() or QApplication([])  # noqa: F841

    # --- settings model ----------------------------------------------------
    settings = PuttingSettings(paths)
    check('LagKing is the default putting system', settings.system == 'LagKing',
          repr(settings.system))
    check('surface_stimp defaults to 10.0',
          abs(float(settings.lagking['surface_stimp']) - 10.0) < 1e-9,
          settings.lagking.get('surface_stimp'))
    check('no speed_calibration key (removed deliberately)',
          'speed_calibration' not in settings.lagking)

    # --- the form builds at all -------------------------------------------
    # The LagKing group box is created in code rather than in PuttingForm.ui,
    # so nothing but constructing the form proves it does not raise.
    class _FakeMain:
        def __init__(self, s):
            self.putting_settings = s

    form = PuttingForm(_FakeMain(settings))
    check('PuttingForm constructs', form is not None)

    spin = getattr(form, 'lagking_surface_stimp_spin', None)
    check('surface stimp spin box exists', spin is not None)
    check('spin box range is 5.0-15.0 at 1 decimal',
          (spin.minimum(), spin.maximum(), spin.decimals()) == (5.0, 15.0, 1),
          f'{spin.minimum()}-{spin.maximum()} @{spin.decimals()}')
    check('no calibration widget',
          not hasattr(form, 'lagking_speed_calibration_spin'))

    # --- placement ---------------------------------------------------------
    # findChildren returns creation order, so assert LAYOUT order instead.
    boxes = []
    for i in range(form.verticalLayout.count()):
        w = form.verticalLayout.itemAt(i).widget()
        if isinstance(w, QGroupBox):
            boxes.append(w.title())
    check('LagKing settings box is first in the layout',
          bool(boxes) and boxes[0] == 'LagKing Settings', str(boxes))

    items = [form.putting_system_combo.itemText(i)
             for i in range(form.putting_system_combo.count())]
    check('LagKing is first in the system dropdown',
          items and items[0] == PuttingSystems.LAGKING, str(items))
    check('the other putting systems are still offered',
          {PuttingSystems.EXPUTT, PuttingSystems.WEBCAM}.issubset(set(items)),
          str(items))

    # --- load / save round trip -------------------------------------------
    settings.lagking['surface_stimp'] = 12.5
    form._PuttingForm__load_values()
    check('load populates the spin box from settings',
          abs(spin.value() - 12.5) < 1e-9, spin.value())

    spin.setValue(8.5)
    form._PuttingForm__save()
    reloaded = PuttingSettings(_FakePaths(tmp))
    check('save round-trips to disk',
          abs(float(reloaded.lagking['surface_stimp']) - 8.5) < 1e-9,
          reloaded.lagking.get('surface_stimp'))

    # --- a settings file written before these keys existed must still load --
    stale = os.path.join(tmp, 'stale')
    os.makedirs(stale, exist_ok=True)
    with open(os.path.join(stale, 'putting_settings.json'), 'w') as fh:
        fh.write('{"system": "ExPutt", "webcam": {}, "exputt": {}}')
    legacy = PuttingSettings(_FakePaths(stale))
    check('a settings file predating the lagking block still loads',
          hasattr(legacy, 'system'), legacy.system)

    # --- launch-speed recovery maths ---------------------------------------
    # Imported late: it needs QtBluetooth, which PySide6-Essentials may lack.
    try:
        from src.bluetooth.lagking_device import LagKingDevice
    except ImportError as e:
        print(f'skip  launch-speed maths (QtBluetooth unavailable: {e})')
        print(f'\n{_passed} checks passed')
        return

    ls = LagKingDevice.launch_speed_mps
    check('launch speed always scales UP', ls(2.40, 10.0) > 2.40,
          f'{ls(2.40, 10.0):.4f}')
    check('a slower surface gets a bigger uplift',
          ls(2.40, 8.0) > ls(2.40, 13.0),
          f'{ls(2.40, 8.0):.4f} > {ls(2.40, 13.0):.4f}')

    # Rolling the recovered speed must cover the roll seen at the gate PLUS
    # the setup distance -- that is the whole derivation.
    def roll(v, stimp):
        return stimp * (v / LagKingDevice.STIMP_REF_SPEED_MPS) ** \
            LagKingDevice.STIMP_ROLLOUT_EXPONENT

    for stimp in (7.0, 10.0, 14.0):
        for setup in (1.5, 2.0, 3.0):
            got = roll(ls(2.40, stimp, setup), stimp)
            want = roll(2.40, stimp) + setup
            check(f'round-trip stimp={stimp} setup={setup}',
                  abs(got - want) < 1e-6, f'{got:.6f} vs {want:.6f}')

    check('a non-positive setup distance falls back to the default',
          abs(ls(2.40, 10.0, 0.0) - ls(2.40, 10.0,
              LagKingDevice.SETUP_DISTANCE_FT_DEFAULT)) < 1e-12)
    check('degenerate inputs pass through untouched',
          ls(0.0, 10.0) == 0.0 and ls(2.40, 0.0) == 2.40)

    print(f'\n{_passed} checks passed')


if __name__ == '__main__':
    main()
