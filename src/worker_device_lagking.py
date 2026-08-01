# Worker that owns the LagKing BLE lifecycle (scan → connect → subscribe)
# and forwards each parsed putt as a `shot` signal that the connector's
# DevicePuttingBase wires into the GSPro send pipeline.
#
# We don't reuse the launch-monitor-style DevicesForm/SelectDeviceForm
# pairing flow because LagKing is a putting-only input — selecting it
# from the Putting Settings dialog should "just work" without dropping
# the user into a separate device-pair dialog. The worker auto-scans
# for any peripheral whose advertised name starts with "LagKing" and
# connects to the first match. The user pre-pairs the gate in Windows
# Bluetooth settings (same constraint as the MLM2PRO path).

import logging

from PySide6.QtBluetooth import QBluetoothDeviceInfo
from PySide6.QtCore import Signal

from src.ball_data import BallData
from src.bluetooth.bluetooth_device_scanner import BluetoothDeviceScanner
from src.bluetooth.lagking_device import LagKingDevice
from src.worker_base import WorkerBase


class WorkerDeviceLagKing(WorkerBase):
    shot = Signal(object)
    status = Signal(str, str)
    connected = Signal(str)
    disconnected = Signal(str)

    DEVICE_NAME_PREFIXES = ['LagKing']

    def __init__(self):
        super().__init__()
        self.name = 'WorkerDeviceLagKing'
        self._scanner: BluetoothDeviceScanner | None = None
        self._device: LagKingDevice | None = None
        self._surface_stimp = 10.0
        self._setup_distance_ft = 2.0
        self._on_green = False

    def apply_settings(self, surface_stimp: float,
                       setup_distance_ft: float | None = None) -> None:
        """Push Putting Settings down to the live device (if any).

        Called on construction and again whenever the settings form saves, so a
        stimp or setup-distance change takes effect without reconnecting.
        """
        self._surface_stimp = surface_stimp
        if setup_distance_ft:
            self._setup_distance_ft = setup_distance_ft
        if self._device is not None:
            self._device.apply_settings(surface_stimp, self._setup_distance_ft)

    def run(self) -> None:
        self.started.emit()
        logging.debug(f'{self.name} starting — scanning for LagKing gate')
        self._start_scan()

    def _start_scan(self) -> None:
        if self._scanner is not None:
            self._scanner.deleteLater()
        self._scanner = BluetoothDeviceScanner(self.DEVICE_NAME_PREFIXES)
        self._scanner.device_found.connect(self._on_device_found)
        self._scanner.device_not_found.connect(self._on_device_not_found)
        self._scanner.error.connect(self._on_scanner_error)
        self._scanner.status_update.connect(
            lambda msg: self.status.emit('Scanning', msg)
        )
        self._scanner.scan()

    def _on_device_found(self, device: QBluetoothDeviceInfo) -> None:
        logging.debug(f'LagKing gate found: {device.name()}')
        # Advertising RSSI, i.e. signal strength AT DISCOVERY. Qt's desktop LE
        # API exposes no live RSSI once connected, so this is a connect-time
        # reading and is reported as such rather than implying a live meter.
        try:
            rssi = device.rssi()
        except Exception:
            rssi = 0
        if rssi:
            self.status.emit('Signal', f'{rssi} dBm at connect ({self._signal_label(rssi)})')
        self._device = LagKingDevice(device)
        self._device.battery_update.connect(self._on_battery)
        self._device.apply_settings(self._surface_stimp, self._setup_distance_ft)
        # A gate that connects (or reconnects) mid-round must inherit the
        # club state we already know, or it sits awake/asleep incorrectly
        # until the player next changes club.
        self._device.set_on_green(self._on_green)
        self._device.shot.connect(self.shot.emit)
        self._device.connected.connect(lambda msg: self.connected.emit(msg))
        self._device.disconnected.connect(self._on_device_disconnected)
        self._device.error.connect(self._on_device_error)
        self._device.status_update.connect(
            lambda action, name: self.status.emit(action, name)
        )
        self._device.connect_device()

    def _on_device_not_found(self) -> None:
        msg = 'No LagKing gate found in range. Make sure the gate is on and paired in Windows Bluetooth settings.'
        logging.debug(msg)
        self.error.emit((Exception(msg),))

    def _on_device_disconnected(self, msg: str) -> None:
        logging.debug(f'LagKing disconnected: {msg}')
        self.disconnected.emit(msg)
        # Auto-rescan so the connector recovers when the user power-cycles
        # the gate or steps out of range and back.
        if self.is_running():
            self._start_scan()

    def _on_device_error(self, msg: str) -> None:
        logging.debug(f'LagKing device error: {msg}')
        self.error.emit((Exception(msg),))

    def _on_scanner_error(self, msg: str) -> None:
        logging.debug(f'LagKing scanner error: {msg}')
        self.error.emit((Exception(str(msg)),))

    def shutdown(self) -> None:
        if self._device is not None:
            try:
                self._device.disconnect_device()
                self._device.shutdown()
            except Exception as e:
                logging.debug(f'LagKing shutdown error: {e}')
            self._device = None
        if self._scanner is not None:
            try:
                self._scanner.stop_scanning()
            except Exception as e:
                logging.debug(f'LagKing scanner stop error: {e}')
            self._scanner = None
        super().shutdown()

    @staticmethod
    def _signal_label(rssi: int) -> str:
        # Rough bands for a BLE peripheral a few feet away on a sim mat. The
        # gate needs its external antenna to reach the good end -- without one
        # it sits around -85 dBm at a foot, which is the 'weak' band.
        if rssi >= -60:
            return 'strong'
        if rssi >= -75:
            return 'good'
        if rssi >= -85:
            return 'weak'
        return 'very weak — check the antenna'

    def _on_battery(self, soc: int, charging: bool) -> None:
        if charging:
            self.status.emit('Battery', f'charging (USB connected), {soc}%')
        else:
            self.status.emit('Battery', f'{soc}% on battery')

    def club_selected(self, club: str) -> None:
        """GSPro tells us the club; the putter means the player is on the green.

        We use that to sleep the gate through the full-shot part of every hole
        and wake it for the putts. WorkerBase.putter_selected() is the test
        ('PT'), and super() records the club that it reads.
        """
        super().club_selected(club)
        on_green = self.putter_selected()
        if on_green != self._on_green:
            self._on_green = on_green
            self.status.emit(
                'Gate', 'awake — on the green' if on_green else 'asleep — off the green'
            )
        if self._device is not None:
            self._device.set_on_green(on_green)

    def send_error(self, error) -> None:
        self.error.emit((error,))
