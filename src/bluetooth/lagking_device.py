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
    # soc percent, charging (USB present). -1 percent = gate did not say.
    battery_update = Signal(int, bool)

    # Drives the on-green keepalive (see _heartbeat). 30 s sits comfortably
    # inside the gate's 5-minute connector soft-sleep window even if a couple
    # of writes are dropped, which Windows BLE stacks do occasionally.
    HEARTBEAT_INTERVAL = 30_000
    DEVICE_HEARTBEAT_INTERVAL = 600_000

    SERVICE_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8091}'))
    PUTT_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8092}'))
    # Written, never subscribed. All live on the same primary service.
    WAKE_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8104}'))
    CLIENT_KIND_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8112}'))
    SOFT_SLEEP_NOW_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8113}'))
    # READ|WRITE float: distance from the ball's start to the gate. The gate
    # makes this user-configurable, so it must be read, not assumed.
    SETUP_DISTANCE_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8127}'))
    # NOTIFY. Packed: float volts, uint8 soc%, uint8 charging, float raw,
    # uint8 dev-override. Append-only in the firmware, so read a PREFIX and
    # never assume the total length.
    BATTERY_CHAR_UUID = QBluetoothUuid(QUuid('{4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8101}'))

    # Value the gate expects on CLIENT_KIND to classify us as a connector
    # rather than a phone. Load-bearing: without it the gate applies the
    # 1-minute APP soft-sleep timeout instead of the 5-minute connector one.
    CLIENT_KIND_CONNECTOR = 1

    PUTT_NOTIFICATION_SIZE = 29
    SIGNED_PUTT_NOTIFICATION_SIZE = 47
    FLAG_SIGNED = 0x80

    # All three mirror the gate firmware's config.h. Roll-out is empirically
    # ~v^1.5, NOT the textbook v^2 -- inverting it uses 1/1.5, not 1/2.
    STIMP_REF_SPEED_MPS = 1.83
    STIMP_ROLLOUT_EXPONENT = 1.5
    # Fallback only. The live value is read from the gate on connect; this
    # matches SETUP_DISTANCE_FT in the firmware's config.h and is used when
    # the read fails or the gate is too old to expose the characteristic.
    SETUP_DISTANCE_FT_DEFAULT = 2.0

    @classmethod
    def launch_speed_mps(
        cls, measured_mps: float, surface_stimp: float,
        setup_distance_ft: float = SETUP_DISTANCE_FT_DEFAULT,
    ) -> float:
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
        setup_ft = setup_distance_ft if setup_distance_ft > 0.01 else cls.SETUP_DISTANCE_FT_DEFAULT
        total = remaining + (setup_ft / surface_stimp)
        return cls.STIMP_REF_SPEED_MPS * (total ** (1.0 / cls.STIMP_ROLLOUT_EXPONENT))

    def __init__(self, device: QBluetoothDeviceInfo):
        # Overwritten by apply_settings() before any putt arrives; this is
        # only the fallback if the settings push were ever missed.
        self._surface_stimp = 10.0
        self._setup_distance_ft = LagKingDevice.SETUP_DISTANCE_FT_DEFAULT
        self._last_battery = None
        self._on_green = False
        self._services = []
        self._primary_service: BluetoothDeviceService = BluetoothDeviceService(
            device,
            LagKingDevice.SERVICE_UUID,
            [LagKingDevice.PUTT_CHAR_UUID, LagKingDevice.BATTERY_CHAR_UUID],
            self._data_handler,
            None,
        )
        self._services.append(self._primary_service)
        # As soon as we're subscribed the device is considered ready —
        # no auth handshake to complete.
        self._primary_service.notifications_subscribed.connect(
            self._on_subscribed
        )
        super().__init__(
            device,
            self._services,
            LagKingDevice.HEARTBEAT_INTERVAL,
            LagKingDevice.DEVICE_HEARTBEAT_INTERVAL,
        )

    def _on_subscribed(self, _uuid) -> None:
        # Identify as a connector BEFORE anything else. ble_appClientConnected()
        # in the firmware treats any peer that has NOT written this as a phone,
        # and picks the 1-minute app soft-sleep timeout accordingly -- so the
        # gate would sleep mid-hole with its rear emitters off and swallow the
        # putt that woke it.
        self._write(
            LagKingDevice.CLIENT_KIND_CHAR_UUID,
            bytearray([LagKingDevice.CLIENT_KIND_CONNECTOR]),
            'client-kind',
        )
        self._push_setup_distance()
        self.launch_monitor_connected.emit()

    def _write(self, uuid: QBluetoothUuid, data: bytearray, what: str) -> None:
        """Best-effort characteristic write.

        Every write here is an optimisation, never correctness: an older gate
        may not expose the characteristic at all. Failing loudly would turn a
        cosmetic gap into a broken putting session, so log and carry on.
        """
        try:
            self._primary_service.write_characteristic(uuid, data)
        except Exception as e:
            logging.debug(f'LagKing {what} write failed: {e}')

    def set_on_green(self, on_green: bool) -> None:
        """Follow GSPro's club selection: putter out = player is on the green.

        Awake the gate draws ~347 mA against ~79 mA in soft sleep, and a round
        is mostly full shots, so holding it awake for the whole round wastes
        most of a battery. Tracking the club instead means it is awake exactly
        when a putt can arrive.
        """
        if on_green == self._on_green:
            return
        self._on_green = on_green
        if on_green:
            self._write(LagKingDevice.WAKE_CHAR_UUID, bytearray([1]), 'wake')
        else:
            self._write(
                LagKingDevice.SOFT_SLEEP_NOW_CHAR_UUID, bytearray([1]), 'sleep-now'
            )

    def _heartbeat(self) -> None:
        # Only while the putter is out. An idle connector must never hold the
        # gate awake -- that is the whole point of following the club.
        if self._on_green:
            self._write(LagKingDevice.WAKE_CHAR_UUID, bytearray([1]), 'wake')

    def apply_settings(self, surface_stimp: float,
                       setup_distance_ft: float | None = None) -> None:
        if surface_stimp and surface_stimp > 0.01:
            self._surface_stimp = float(surface_stimp)
        if setup_distance_ft and setup_distance_ft > 0.01:
            self._setup_distance_ft = float(setup_distance_ft)
            self._push_setup_distance()

    def _push_setup_distance(self) -> None:
        """Tell the gate where the ball starts.

        The connector owns this, not the gate: without the phone app the gate's
        stored value is whatever was last set, possibly by a different user on a
        different mat. Writing it down keeps the gate's own projection honest and
        keeps our speed correction and the gate agreeing on one number.
        """
        self._write(
            LagKingDevice.SETUP_DISTANCE_CHAR_UUID,
            bytearray(struct.pack('<f', self._setup_distance_ft)),
            'setup-distance',
        )

    def _data_handler(
        self, characteristic: QLowEnergyCharacteristic, data: QByteArray
    ) -> None:
        uuid = characteristic.uuid()
        if uuid == LagKingDevice.BATTERY_CHAR_UUID:
            self._handle_battery(bytes(data.data()))
            return
        if uuid != LagKingDevice.PUTT_CHAR_UUID:
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

    def _handle_battery(self, payload: bytes) -> None:
        # Prefix read: the firmware appends fields over time, so anything past
        # the first six bytes is optional and must never be required.
        if len(payload) < 6:
            return
        try:
            _volts, soc, charging = struct.unpack_from('<fBB', payload, 0)
        except Exception:
            return
        state = (int(soc), bool(charging))
        if state == self._last_battery:
            return                      # notifies every ~30 s; only report changes
        self._last_battery = state
        self.battery_update.emit(state[0], state[1])

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
        launch_mps = self.launch_speed_mps(
            speed_mps, self._surface_stimp, self._setup_distance_ft
        )
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
