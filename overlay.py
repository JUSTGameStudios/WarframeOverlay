import ctypes
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QImage
from config import AppConfig, AlertMode
from PIL import Image

# Windows constants for click-through
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20


class AlertOverlay(QWidget):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._current_energy = 0
        self._setup_window()
        self._setup_ui()
        self._apply_config()

    def _setup_window(self):
        # Frameless, always on top, tool window (no taskbar entry)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )

        # Transparent background
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Don't show in taskbar
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)

    def _apply_config(self):
        # Position and size (mode-specific)
        pos = self.config.get_current_position()
        size = self.config.get_current_size()
        self.move(pos.x, pos.y)
        self.resize(size.width, size.height)

        # Opacity
        self.setWindowOpacity(self.config.alert_opacity)

        # Apply mode-specific settings
        if self.config.alert_mode == AlertMode.IMAGE:
            if self.config.alert_image_path:
                self.load_image(self.config.alert_image_path)
        elif self.config.alert_mode == AlertMode.NUMBER:
            self._setup_number_display()

    def _setup_number_display(self):
        """Configure the label for displaying numbers."""
        # Set a large, bold font
        font = QFont("Arial", 72, QFont.Bold)
        self.image_label.setFont(font)
        self.image_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.image_label.setText(str(self._current_energy))

    def update_config(self, config: AppConfig):
        self.config = config
        self._apply_config()

    def load_image(self, path: str):
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                size = self.config.get_current_size()
                scaled = pixmap.scaled(
                    size.width,
                    size.height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)
                self.image_label.setStyleSheet("")  # Clear any text styling

    def update_energy(self, energy: int):
        """Update the displayed energy value (for NUMBER mode)."""
        self._current_energy = energy
        if self.config.alert_mode == AlertMode.NUMBER and self.isVisible():
            self.image_label.setText(str(energy))

    def update_filtered_image(self, img: Image.Image):
        """Update the displayed filtered image (for FILTERED mode)."""
        if self.config.alert_mode == AlertMode.FILTERED:
            # Scale PIL image first for better quality (before Qt conversion)
            size = self.config.get_current_size()
            if img.width != size.width or img.height != size.height:
                # Calculate scale to fit while keeping aspect ratio
                scale_w = size.width / img.width
                scale_h = size.height / img.height
                scale = min(scale_w, scale_h)
                new_w = int(img.width * scale)
                new_h = int(img.height * scale)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Ensure RGBA mode
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Convert to QPixmap
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)

            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("background-color: transparent;")

    def showEvent(self, event):
        super().showEvent(event)
        # Make window click-through on Windows
        self._set_click_through(True)

    def _set_click_through(self, enable: bool):
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enable:
                ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                ex_style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        except Exception:
            pass  # Non-Windows platform or error

    def show_alert(self):
        """Show the alert overlay instantly."""
        if not self.isVisible():
            self.show()

    def hide_alert(self):
        """Hide the alert overlay instantly."""
        if self.isVisible():
            self.hide()

    def set_position(self, x: int, y: int):
        self.move(x, y)

    def set_size(self, width: int, height: int):
        self.resize(width, height)
        # Reload image with new size
        if self.config.alert_mode == AlertMode.IMAGE and self.config.alert_image_path:
            self.load_image(self.config.alert_image_path)

    def set_opacity(self, opacity: float):
        self.setWindowOpacity(opacity)
