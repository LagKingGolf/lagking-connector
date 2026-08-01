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

    def apply_settings(self, surface_stimp: float) -> None:
        """Push Putting Settings down to the live device (if any).

        Called on construction and again whenever the settings form saves,
        so a stimp change takes effect without reconnecting the gate.
        """
        self._surface_stimp = surface_stimp
        if self._device is not None:
            self._device.apply_settings(surface_stimp)

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
        self._device = LagKingDevice(device)
        self._device.apply_settings(self._surface_stimp)
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

    # The connector's putting flow signals club selection so launch
    # monitors can disarm during full swings. LagKing is putt-only —
    # nothing to do here, but the base WorkerBase contract expects the
    # method to exist.
    def club_selected(self, club: str) -> None:
        super().club_selected(club)

    def send_error(self, error) -> None:
        self.error.emit((error,))
