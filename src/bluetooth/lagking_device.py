# LagKing V3 BLE peripheral — putting-only input for the GSPro connector.
#
# The gate publishes putt data on a single notification characteristic
# (PUTT_CHAR_UUID) under SERVICE_UUID. Each notification is a 29-byte
# packed struct (or 47-byte signed variant; we ignore the trailing
# anti-cheat fields here since GSPro doesn't care). Layout:
#
#   float speedMps      offset 0
#   float distanceFt    offset 4
#   float angleDeg      offset 8     (positive = right of target)
#   float proximityFt   offset 12
#   float surfaceStimp  offset 16
#   float targetStimp   offset 20
#   float targetDistFt  offset 24
#   uint8 flags         offset 28    (bit 0 = hasAngle, bit 7 = signed)
#
# Source of truth for layout:
#   product/v3/firmware/ble_service.cpp ble_notifyPutt()
#   app/LagKing/src/ble/BleProtocol.ts  parsePuttNotification()
#
# No bonding / no encryption / no auth handshake — connect, subscribe,
# read notifications. Everything else (battery, beam-debug, settings
# writes) is exposed by the firmware but irrelevant to GSPro and we
# leave those characteristics alone.

import logging
import struct

from PySide6.QtBluetooth import QBluetoothDeviceInfo, QBluetoothUuid, QLowEnergyCharacteristic
from PySide6.QtCore import QUuid, QByteArray, Signal

from src.ball_data import BallData, PuttType
from src.bluetooth.bluetooth_device_base import BluetoothDeviceBase
from src.bluetooth.bluetooth_device_service import BluetoothDeviceService

# m/s → mph. GSPro Open Connect expects ball speed in mph.
METERS_PER_S_TO_MPH = 2.2369362921


class LagKingDevice(BluetoothDeviceBase):
    """BLE peripheral wrapper for the LagKing V3 putting gate."""

    putt_received = Signal(BallData)

    # No heartbeat on the LagKing side — the firmware doesn't require one.
    # Pick a long interval just to satisfy BluetoothDeviceBase.
    HEARTBEAT_INTERVAL = 60_000
    DEVICE_HEARTBEAT_INTERVAL = 600_000

    SERVICE_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8091}'))
    PUTT_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8092}'))

    PUTT_NOTIFICATION_SIZE = 29
    SIGNED_PUTT_NOTIFICATION_SIZE = 47
    FLAG_SIGNED = 0x80

    # All three mirror the gate firmware's config.h. Roll-out is empirically
    # ~v^1.5, NOT the textbook v^2 -- inverting it uses 1/1.5, not 1/2.
    STIMP_REF_SPEED_MPS = 1.83
    STIMP_ROLLOUT_EXPONENT = 1.5
    SETUP_DISTANCE_FT = 2.0

    @classmethod
    def launch_speed_mps(cls, measured_mps: float, surface_stimp: float) -> float:
        """Recover speed at the putter from speed measured at the gate.

        GSPro, like any launch monitor consumer, wants ball speed AT LAUNCH.
        The gate sits ~2 ft downrange, so by the time the ball is measured the
        surface has already taken some speed out of it -- and how much depends
        on the surface. A slow mat eats more of it than a fast one, so sending
        the raw reading under-reports launch speed, and under-reports it
        unevenly across surfaces.

        Roll-out goes as `stimp * (v / v_ref) ** 1.5`, so total roll from the
        putter is the roll still remaining at the gate plus the 2 ft already
        travelled. Inverting that for the speed which would have produced it:

            v_launch = v_ref * ((v/v_ref) ** 1.5 + setup_ft / stimp) ** (1/1.5)

        Note this always scales UP, by roughly 7-11%, and more on a slower
        surface. Nothing here depends on the green GSPro is simulating -- that
        is GSPro's to model, and it applies its own green speed to what we send.
        """
        if measured_mps <= 0.0 or surface_stimp <= 0.01:
            return measured_mps
        remaining = (measured_mps / cls.STIMP_REF_SPEED_MPS) ** cls.STIMP_ROLLOUT_EXPONENT
        total = remaining + (cls.SETUP_DISTANCE_FT / surface_stimp)
        return cls.STIMP_REF_SPEED_MPS * (total ** (1.0 / cls.STIMP_ROLLOUT_EXPONENT))

    def __init__(self, device: QBluetoothDeviceInfo):
        # Overwritten by apply_settings() before any putt arrives; this is
        # only the fallback if the settings push were ever missed.
        self._surface_stimp = 10.0
        self._services = []
        self._primary_service: BluetoothDeviceService = BluetoothDeviceService(
            device,
            LagKingDevice.SERVICE_UUID,
            [LagKingDevice.PUTT_CHAR_UUID],
            self._data_handler,
            None,
        )
        self._services.append(self._primary_service)
        # As soon as we're subscribed the device is considered ready —
        # no auth handshake to complete.
        self._primary_service.notifications_subscribed.connect(
            lambda _uuid: self.launch_monitor_connected.emit()
        )
        super().__init__(
            device,
            self._services,
            LagKingDevice.HEARTBEAT_INTERVAL,
            LagKingDevice.DEVICE_HEARTBEAT_INTERVAL,
        )

    def apply_settings(self, surface_stimp: float) -> None:
        if surface_stimp and surface_stimp > 0.01:
            self._surface_stimp = float(surface_stimp)

    def _data_handler(
        self, characteristic: QLowEnergyCharacteristic, data: QByteArray
    ) -> None:
        if characteristic.uuid() != LagKingDevice.PUTT_CHAR_UUID:
            return
        payload = bytes(data.data())
        if len(payload) < LagKingDevice.PUTT_NOTIFICATION_SIZE:
            logging.debug(
                f'LagKing putt notification too short: {len(payload)} bytes'
            )
            return
        try:
            ball_data = self._parse_putt(payload)
        except Exception as e:
            msg = f'LagKing putt parse error: {e}'
            logging.debug(msg)
            self.error.emit(msg)
            return
        if ball_data is None:
            return
        self.putt_received.emit(ball_data)
        # The base class also exposes a generic `shot` signal that the
        # connector wires into the GSPro send path for launch monitors.
        # Mirror onto it so callers can use either.
        self.shot.emit(ball_data)

    def _parse_putt(self, payload: bytes) -> BallData | None:
        # 7 little-endian floats + uint8 flags.
        speed_mps, _distance_ft, angle_deg, _proximity_ft, _surface_stimp, \
            _target_stimp, _target_dist_ft = struct.unpack_from('<7f', payload, 0)
        flags = payload[28]
        # If the gate happened to fire the signed variant, the rest of
        # the bytes are anti-cheat trailer that we ignore — same parsed
        # core fields apply.
        ball_data = BallData()
        ball_data.putt_type = PuttType.LAGKING
        ball_data.good_shot = True
        ball_data.club = 'PT'
        # Recover launch speed from the gate reading, then m/s -> mph.
        launch_mps = self.launch_speed_mps(speed_mps, self._surface_stimp)
        ball_data.speed = round(launch_mps * METERS_PER_S_TO_MPH, 2)
        # HLA: degrees, positive = right of target (matches GSPro).
        # Hide the value if the gate didn't have a confident angle read —
        # default to 0 (straight) rather than passing noise through.
        if flags & 0x01:  # FLAG_HAS_ANGLE
            ball_data.hla = round(angle_deg, 2)
        else:
            ball_data.hla = 0.0
        # Putts roll, no flight: zero everything else GSPro might key on.
        ball_data.vla = 0.0
        ball_data.total_spin = 0.0
        ball_data.spin_axis = 0.0
        ball_data.back_spin = 0.0
        ball_data.side_spin = 0.0
        return ball_data
