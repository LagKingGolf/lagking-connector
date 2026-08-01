# LagKing putting input for the GSPro connector. Slots in next to
# DevicePuttingWebcam and DevicePuttingExPutt — same DevicePuttingBase
# contract, same `shot → gspro_connection` wiring. The actual BLE work
# lives in WorkerDeviceLagKing.

from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtWidgets import QMessageBox

from src.device_putting_base import DevicePuttingBase
from src.log_message import LogMessageTypes, LogMessageSystems
from src.worker_device_lagking import WorkerDeviceLagKing


class DevicePuttingLagKing(DevicePuttingBase):

    def __init__(self, main_window):
        DevicePuttingBase.__init__(self, main_window)
        self.device_worker = WorkerDeviceLagKing()
        self.setup()
        self.__push_settings()

    def __push_settings(self):
        """Copy Putting Settings into the worker.

        Read with .get() defaults so a settings file written before these
        keys existed (an upstream install, or an older build of this fork)
        loads instead of raising KeyError on the startup path.
        """
        lagking = getattr(self.main_window.putting_settings, 'lagking', {}) or {}
        try:
            surface_stimp = float(lagking.get('surface_stimp', 10.0))
        except (TypeError, ValueError):
            surface_stimp = 10.0
        try:
            setup_distance = float(lagking.get('setup_distance_ft', 2.0))
        except (TypeError, ValueError):
            setup_distance = 2.0
        self.device_worker.apply_settings(surface_stimp, setup_distance)

    def reload_putting_rois(self):
        # Base hook fired whenever Putting Settings are saved -- re-push so a
        # stimp change takes effect without reconnecting the gate.
        super().reload_putting_rois()
        self.__push_settings()

    def start_app(self):
        # Putting.putting_stop_start calls start_app() immediately before
        # start(); this is where the BLE scan actually begins. Queued because
        # the scanner and device must be built on the worker's thread.
        QMetaObject.invokeMethod(
            self.device_worker, 'start_scanning', Qt.ConnectionType.QueuedConnection
        )

    def stop(self):
        QMetaObject.invokeMethod(
            self.device_worker, 'stop_scanning', Qt.ConnectionType.QueuedConnection
        )
        super().stop()

    def setup_device_thread(self):
        super().setup_device_thread()
        # Surface BLE-side status updates in the connector's log window so
        # the user can tell the difference between "scanning", "connecting",
        # and "subscribed" without having to open the Windows Bluetooth UI.
        self.device_worker.status.connect(self._on_status)
        self.device_worker.connected.connect(self._on_connected)
        self.device_worker.disconnected.connect(self._on_disconnected)

    def _on_status(self, action: str, detail: str) -> None:
        self.main_window.log_message(
            LogMessageTypes.LOGS,
            LogMessageSystems.CONNECTOR,
            f'LagKing: {action} {detail}',
        )

    def _on_connected(self, msg: str) -> None:
        self.main_window.log_message(
            LogMessageTypes.LOG_WINDOW,
            LogMessageSystems.CONNECTOR,
            f'LagKing connected: {msg}',
        )

    def _on_disconnected(self, msg: str) -> None:
        self.main_window.log_message(
            LogMessageTypes.LOG_WINDOW,
            LogMessageSystems.CONNECTOR,
            f'LagKing disconnected: {msg}',
        )

    # Errors that mean "this session is over" rather than "something
    # transient happened". Everything else is logged and play continues.
    FATAL_HINTS = ('bluetooth is not', 'adapter', 'permission', 'powered off')

    def device_worker_error(self, error):
        msg = format(error[0]) if isinstance(error, tuple) and error else format(error)
        self.main_window.log_message(
            LogMessageTypes.LOGS, LogMessageSystems.CONNECTOR, f'LagKing: {msg}'
        )
        # A routine disconnect is NOT fatal. BluetoothDeviceBase emits
        # 'Unexpected disconnection' on every controller drop -- including the
        # gate going to sleep, which this connector deliberately causes when the
        # putter is put away. Treating that as fatal popped a modal and stopped
        # the device, which also killed the auto-rescan the same disconnect had
        # just started. So: log, let the rescan do its job, and stay running.
        lowered = msg.lower()
        if not any(hint in lowered for hint in DevicePuttingLagKing.FATAL_HINTS):
            return
        QMessageBox.warning(self.main_window, 'LagKing Error', msg)
        self.stop()
