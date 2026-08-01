from dataclasses import dataclass

from src.settings_base import SettingsBase

@dataclass
class PuttingSystems:
    EXPUTT = 'ExPutt'
    WEBCAM = 'Webcam'
    LAGKING = 'LagKing'
    NONE = 'None'

@dataclass
class WebcamWindowFocus:
    PUTTING_WINDOW = 'PuttingWindow'
    GSPRO = 'GSPRO'

@dataclass
class WebcamWindowState:
    HIDE = 'Hide'
    MINIMIZE = 'Minimize'
    SEND_TO_BACK = 'SendToBack'
    SHOW = 'Show'

class PuttingSettings(SettingsBase):

    def __init__(self, app_paths):
        SettingsBase.__init__(self,
            app_paths.get_config_path(
                name='putting_settings',
                ext='.json'
            ), {
                # LagKing is the default putting system in this fork. Only
                # affects a FRESH settings file — an existing install keeps
                # whatever the user already chose. Selecting it merely builds
                # the device; no BLE scan happens until Start is pressed, so
                # this is inert for anyone without a gate.
                "system": "LagKing",
                "webcam": {
                    "camera": 0,
                    "ball_color": "yellow",
                    "window_name": "Putting View: Press q to exit / a for adv. settings",
                    "ip_address": "127.0.0.1",
                    "port": 8888,
                    "auto_start": "Yes",
                    "width": 640,
                    "params": "",
                    "window_putting_focus": "PuttingWindow",
                    "window_not_putting_state": "SendToBack"
                },
                "exputt": {
                    "window_name": "Camera",
                    "window_rect": {
                        "left": 0,
                        "top": 0,
                        "right": 0,
                        "bottom": 0
                    },
                    "auto_start": "Yes",
                    "rois": {}
                },
                "lagking": {
                    # The connector auto-scans for any peripheral whose name
                    # starts with this prefix. V3 firmware advertises
                    # exactly "LagKing V3" — the prefix match means future
                    # versions / multiple gates will keep working without
                    # a settings change.
                    "device_name_prefix": "LagKing",
                    # Stimp of the surface the player is ACTUALLY putting on.
                    # The gate reads ball speed ~2 ft downrange, by which point
                    # the surface has already slowed the ball; how much depends
                    # on this number. Used to recover true launch speed, which
                    # is what GSPro expects from a launch monitor. GSPro owns
                    # the green being simulated -- that is not our business.
                    "surface_stimp": 10.0,
                    # Empirical trim applied after the launch-speed recovery.
                    # 1.0 = model only. Raise if putts finish short in GSPro,
                    # lower if they run long. Calibrate with a tape measure.
                    "speed_calibration": 1.0
                }
            }
        )

    def load(self):
        super().load()
        save = False
        if 'width' not in self.webcam:
            self.webcam['width'] = 640
            save = True
        if 'window_putting_focus' not in self.webcam:
            self.webcam['window_putting_focus'] = WebcamWindowFocus.GSPRO
            save = True
        if 'window_not_putting_state' not in self.webcam:
            self.webcam['window_not_putting_state'] = WebcamWindowState.SEND_TO_BACK
            save = True
        if save:
            super().save()

    def width(self):
        return self.exputt['window_rect']['right'] - self.exputt['window_rect']['left']

    def height(self):
        return self.exputt['window_rect']['bottom'] - self.exputt['window_rect']['top']

    @staticmethod
    def webcam_window_focus_as_list():
        keys = []
        for key in WebcamWindowFocus.__dict__:
            if key != '__' not in key:
                keys.append(getattr(WebcamWindowFocus, key))
        return keys

    @staticmethod
    def webcam_window_state_as_list():
        keys = []
        for key in WebcamWindowState.__dict__:
            if key != '__' not in key:
                keys.append(getattr(WebcamWindowState, key))
        return keys
