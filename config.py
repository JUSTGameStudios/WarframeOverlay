import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class AlertMode(Enum):
    IMAGE = "image"           # Show custom alert image
    NUMBER = "number"         # Show the energy number as text
    FILTERED = "filtered"     # Show filtered capture region


@dataclass
class CaptureRegion:
    x: int = 1800
    y: int = 1030
    width: int = 60
    height: int = 35


@dataclass
class AlertPosition:
    x: int = 960
    y: int = 540


@dataclass
class AlertSize:
    width: int = 200
    height: int = 200


@dataclass
class TextColor:
    """RGB color of UI text for filtering."""
    r: int = 255
    g: int = 255
    b: int = 255
    tolerance: int = 30  # How much deviation from exact color to allow
    skew: float = 0.0  # Vertical skew factor (positive = left side higher)


@dataclass
class AppConfig:
    capture_region: CaptureRegion = field(default_factory=CaptureRegion)
    text_color: TextColor = field(default_factory=TextColor)
    threshold: int = 50
    polling_rate_ms: int = 100
    alert_mode: AlertMode = AlertMode.IMAGE
    alert_image_path: str = ""
    # Per-mode position and size settings
    image_position: AlertPosition = field(default_factory=AlertPosition)
    image_size: AlertSize = field(default_factory=AlertSize)
    number_position: AlertPosition = field(default_factory=AlertPosition)
    number_size: AlertSize = field(default_factory=lambda: AlertSize(width=150, height=100))
    filtered_position: AlertPosition = field(default_factory=AlertPosition)
    filtered_size: AlertSize = field(default_factory=lambda: AlertSize(width=100, height=60))
    alert_opacity: float = 1.0
    monitoring_active: bool = False
    tesseract_path: str = ""

    def get_current_position(self) -> AlertPosition:
        """Get position for current alert mode."""
        if self.alert_mode == AlertMode.IMAGE:
            return self.image_position
        elif self.alert_mode == AlertMode.NUMBER:
            return self.number_position
        else:
            return self.filtered_position

    def set_current_position(self, pos: AlertPosition):
        """Set position for current alert mode."""
        if self.alert_mode == AlertMode.IMAGE:
            self.image_position = pos
        elif self.alert_mode == AlertMode.NUMBER:
            self.number_position = pos
        else:
            self.filtered_position = pos

    def get_current_size(self) -> AlertSize:
        """Get size for current alert mode."""
        if self.alert_mode == AlertMode.IMAGE:
            return self.image_size
        elif self.alert_mode == AlertMode.NUMBER:
            return self.number_size
        else:
            return self.filtered_size

    def set_current_size(self, size: AlertSize):
        """Set size for current alert mode."""
        if self.alert_mode == AlertMode.IMAGE:
            self.image_size = size
        elif self.alert_mode == AlertMode.NUMBER:
            self.number_size = size
        else:
            self.filtered_size = size

    def to_dict(self) -> dict:
        return {
            "capture_region": asdict(self.capture_region),
            "text_color": asdict(self.text_color),
            "threshold": self.threshold,
            "polling_rate_ms": self.polling_rate_ms,
            "alert_mode": self.alert_mode.value,
            "alert_image_path": self.alert_image_path,
            "image_position": asdict(self.image_position),
            "image_size": asdict(self.image_size),
            "number_position": asdict(self.number_position),
            "number_size": asdict(self.number_size),
            "filtered_position": asdict(self.filtered_position),
            "filtered_size": asdict(self.filtered_size),
            "alert_opacity": self.alert_opacity,
            "monitoring_active": self.monitoring_active,
            "tesseract_path": self.tesseract_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        config = cls()
        if "capture_region" in data:
            config.capture_region = CaptureRegion(**data["capture_region"])
        if "text_color" in data:
            config.text_color = TextColor(**data["text_color"])
        if "threshold" in data:
            config.threshold = data["threshold"]
        if "polling_rate_ms" in data:
            config.polling_rate_ms = data["polling_rate_ms"]
        if "alert_mode" in data:
            config.alert_mode = AlertMode(data["alert_mode"])
        if "alert_image_path" in data:
            config.alert_image_path = data["alert_image_path"]
        # Per-mode settings
        if "image_position" in data:
            config.image_position = AlertPosition(**data["image_position"])
        if "image_size" in data:
            config.image_size = AlertSize(**data["image_size"])
        if "number_position" in data:
            config.number_position = AlertPosition(**data["number_position"])
        if "number_size" in data:
            config.number_size = AlertSize(**data["number_size"])
        if "filtered_position" in data:
            config.filtered_position = AlertPosition(**data["filtered_position"])
        if "filtered_size" in data:
            config.filtered_size = AlertSize(**data["filtered_size"])
        # Legacy: migrate old single position/size to image mode
        if "alert_position" in data and "image_position" not in data:
            config.image_position = AlertPosition(**data["alert_position"])
        if "alert_size" in data and "image_size" not in data:
            config.image_size = AlertSize(**data["alert_size"])
        if "alert_opacity" in data:
            config.alert_opacity = data["alert_opacity"]
        if "monitoring_active" in data:
            config.monitoring_active = data["monitoring_active"]
        if "tesseract_path" in data:
            config.tesseract_path = data["tesseract_path"]
        return config


def load_config() -> AppConfig:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error loading config, using defaults: {e}")
            return AppConfig()
    return AppConfig()


def save_config(config: AppConfig) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.to_dict(), f, indent=2)
