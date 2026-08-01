# LagKing putting input for the GSPro connector. Slots in next to
# DevicePuttingWebcam and DevicePuttingExPutt — same DevicePuttingBase
# contract, same `shot → gspro_connection` wiring. The actual BLE work
# lives in WorkerDeviceLagKing.

from PySide6.QtWidgets import QMessageBox

from src.device_putting_base import DevicePuttingBase
from src.log_message import LogMessageTypes, LogMessageSystems
from src.worker_device_lagking import WorkerDeviceLagKing


class DevicePuttingLagKing(DevicePuttingBase):

    def __init__(self, main_window):
        DevicePuttingBase.__init__(self, main_window)
        self.device_worker = WorkerDeviceLagKing()
        self.setup()

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

    def device_worker_error(self, error):
        msg = format(error[0]) if isinstance(error, tuple) and error else format(error)
        self.main_window.log_message(
            LogMessageTypes.LOGS, LogMessageSystems.CONNECTOR, f'LagKing error: {msg}'
        )
        QMessageBox.warning(self.main_window, 'LagKing Error', msg)
        self.stop()
