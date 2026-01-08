import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config import load_config, save_config, AppConfig
from capture import EnergyMonitor
from overlay import AlertOverlay
from config_window import ConfigWindow


class WarframeEnergyApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Load configuration
        self.config = load_config()

        # Create components
        self.overlay = AlertOverlay(self.config)
        self.config_window = ConfigWindow(self.config)
        self.monitor = None

        # Connect signals
        self._connect_signals()

        # Show config window
        self.config_window.show()

        # Auto-resume monitoring if it was active
        if self.config.monitoring_active:
            # Delay start to ensure window is ready
            QTimer.singleShot(500, self._start_monitoring)

    def _connect_signals(self):
        # Config window signals
        self.config_window.config_changed.connect(self._on_config_changed)
        self.config_window.start_monitoring.connect(self._start_monitoring)
        self.config_window.stop_monitoring.connect(self._stop_monitoring)
        self.config_window.test_alert.connect(self._test_alert)

    def _on_config_changed(self, config: AppConfig):
        self.config = config
        self.overlay.update_config(config)
        if self.monitor:
            self.monitor.update_config(config)

    def _start_monitoring(self):
        if self.monitor and self.monitor.isRunning():
            return

        self.monitor = EnergyMonitor(self.config)
        self.monitor.energy_changed.connect(self._on_energy_changed)
        self.monitor.threshold_crossed.connect(self._on_threshold_crossed)
        self.monitor.filtered_image.connect(self._on_filtered_image)
        self.monitor.ocr_error.connect(self._on_ocr_error)
        self.monitor.start()

        self.config_window.update_status(True)

    def _stop_monitoring(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait(2000)  # Wait up to 2 seconds
            self.monitor = None

        self.overlay.hide_alert()
        self.config_window.update_status(False)

    def _on_energy_changed(self, energy: int):
        self.config_window.update_energy_display(energy)
        # Update overlay for NUMBER mode
        self.overlay.update_energy(energy)

    def _on_threshold_crossed(self, below_threshold: bool):
        if below_threshold:
            self.overlay.show_alert()
        else:
            self.overlay.hide_alert()

    def _on_filtered_image(self, img):
        """Handle filtered image updates for FILTERED mode."""
        self.overlay.update_filtered_image(img)

    def _on_ocr_error(self, error: str):
        print(f"OCR Error: {error}")

    def _test_alert(self):
        """Show alert for 2 seconds then hide."""
        self.overlay.show_alert()
        QTimer.singleShot(2000, self.overlay.hide_alert)

    def run(self) -> int:
        return self.app.exec_()

    def cleanup(self):
        self._stop_monitoring()
        save_config(self.config)


def main():
    app = WarframeEnergyApp()
    try:
        result = app.run()
    finally:
        app.cleanup()
    sys.exit(result)


if __name__ == "__main__":
    main()
