from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QSlider, QFileDialog,
    QLineEdit, QMessageBox, QFrame, QComboBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image

from config import AppConfig, CaptureRegion, AlertPosition, AlertSize, TextColor, AlertMode, save_config
from region_selector import RegionSelector, PositionSelector, RegionAdjuster, ColorPicker


class ConfigWindow(QMainWindow):
    config_changed = pyqtSignal(AppConfig)
    start_monitoring = pyqtSignal()
    stop_monitoring = pyqtSignal()
    test_alert = pyqtSignal()

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._region_selector = None
        self._position_selector = None
        self._region_adjuster = None
        self._color_picker = None
        self._setup_ui()
        self._load_config_to_ui()

    def _setup_ui(self):
        self.setWindowTitle("Warframe Energy Overlay")
        self.setMinimumWidth(450)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Tesseract path section
        layout.addWidget(self._create_tesseract_group())

        # Capture region section
        layout.addWidget(self._create_capture_group())

        # Threshold section
        layout.addWidget(self._create_threshold_group())

        # Alert settings section
        layout.addWidget(self._create_alert_group())

        # Status section
        layout.addWidget(self._create_status_group())

        # Control buttons
        layout.addWidget(self._create_controls())

    def _create_tesseract_group(self) -> QGroupBox:
        group = QGroupBox("Tesseract OCR")
        layout = QHBoxLayout(group)

        self.tesseract_path_edit = QLineEdit()
        self.tesseract_path_edit.setPlaceholderText("Path to tesseract.exe (leave empty for system PATH)")
        layout.addWidget(self.tesseract_path_edit)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_tesseract)
        layout.addWidget(browse_btn)

        return group

    def _create_capture_group(self) -> QGroupBox:
        group = QGroupBox("Energy Detection")
        layout = QVBoxLayout(group)

        # Capture region selection
        region_label = QLabel("<b>Capture Region:</b> Select the area containing the energy number")
        layout.addWidget(region_label)

        region_display_layout = QHBoxLayout()
        self.region_label = QLabel("Region: Not set")
        region_display_layout.addWidget(self.region_label)

        select_region_btn = QPushButton("Select")
        select_region_btn.clicked.connect(self._open_region_selector)
        region_display_layout.addWidget(select_region_btn)

        adjust_region_btn = QPushButton("Adjust")
        adjust_region_btn.clicked.connect(self._open_capture_region_adjuster)
        region_display_layout.addWidget(adjust_region_btn)

        region_display_layout.addStretch()
        layout.addLayout(region_display_layout)

        # Position with arrow controls
        pos_container = QHBoxLayout()

        # Arrow buttons for position
        arrow_grid = QGridLayout()
        arrow_grid.setSpacing(2)

        btn_up = QPushButton("\u25B2")  # Up triangle
        btn_up.setFixedSize(30, 25)
        btn_up.clicked.connect(lambda: self._nudge_region(0, -1))
        arrow_grid.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("\u25C0")  # Left triangle
        btn_left.setFixedSize(30, 25)
        btn_left.clicked.connect(lambda: self._nudge_region(-1, 0))
        arrow_grid.addWidget(btn_left, 1, 0)

        btn_right = QPushButton("\u25B6")  # Right triangle
        btn_right.setFixedSize(30, 25)
        btn_right.clicked.connect(lambda: self._nudge_region(1, 0))
        arrow_grid.addWidget(btn_right, 1, 2)

        btn_down = QPushButton("\u25BC")  # Down triangle
        btn_down.setFixedSize(30, 25)
        btn_down.clicked.connect(lambda: self._nudge_region(0, 1))
        arrow_grid.addWidget(btn_down, 2, 1)

        pos_container.addLayout(arrow_grid)

        # Coordinate display (hidden spinboxes for value storage)
        coords_layout = QHBoxLayout()
        coords_layout.addWidget(QLabel("X:"))
        self.region_x = QSpinBox()
        self.region_x.setRange(0, 9999)
        self.region_x.valueChanged.connect(self._on_region_changed)
        coords_layout.addWidget(self.region_x)

        coords_layout.addWidget(QLabel("Y:"))
        self.region_y = QSpinBox()
        self.region_y.setRange(0, 9999)
        self.region_y.valueChanged.connect(self._on_region_changed)
        coords_layout.addWidget(self.region_y)

        coords_layout.addWidget(QLabel("W:"))
        self.region_w = QSpinBox()
        self.region_w.setRange(10, 500)
        self.region_w.valueChanged.connect(self._on_region_changed)
        coords_layout.addWidget(self.region_w)

        coords_layout.addWidget(QLabel("H:"))
        self.region_h = QSpinBox()
        self.region_h.setRange(10, 500)
        self.region_h.valueChanged.connect(self._on_region_changed)
        coords_layout.addWidget(self.region_h)

        pos_container.addLayout(coords_layout)
        pos_container.addStretch()

        layout.addLayout(pos_container)

        # Separator
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line1)

        # Text color picker
        color_label = QLabel("<b>Text Color:</b> Sample the UI text color for better detection")
        layout.addWidget(color_label)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))

        self.color_preview = QLabel()
        self.color_preview.setFixedSize(30, 20)
        self.color_preview.setFrameStyle(QFrame.Box)
        self.color_preview.setAutoFillBackground(True)
        color_layout.addWidget(self.color_preview)

        self.color_value_label = QLabel("RGB(255, 255, 255)")
        color_layout.addWidget(self.color_value_label)

        pick_color_btn = QPushButton("Pick Color")
        pick_color_btn.clicked.connect(self._open_color_picker)
        color_layout.addWidget(pick_color_btn)

        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Color tolerance and skew
        adjust_layout = QHBoxLayout()
        adjust_layout.addWidget(QLabel("Tolerance:"))
        self.color_tolerance = QSpinBox()
        self.color_tolerance.setRange(5, 100)
        self.color_tolerance.setValue(30)
        self.color_tolerance.setToolTip("How much color variation to allow (higher = more lenient)")
        self.color_tolerance.valueChanged.connect(self._on_color_tolerance_changed)
        adjust_layout.addWidget(self.color_tolerance)

        adjust_layout.addSpacing(20)
        adjust_layout.addWidget(QLabel("Skew:"))
        self.skew_spin = QDoubleSpinBox()
        self.skew_spin.setRange(-1.0, 1.0)
        self.skew_spin.setSingleStep(0.05)
        self.skew_spin.setDecimals(2)
        self.skew_spin.setValue(0.0)
        self.skew_spin.setToolTip("Vertical skew to correct angled text (positive = left side higher)")
        self.skew_spin.valueChanged.connect(self._on_skew_changed)
        adjust_layout.addWidget(self.skew_spin)

        adjust_layout.addStretch()
        layout.addLayout(adjust_layout)

        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line2)

        # Preview / Test
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))

        self.capture_preview = QLabel()
        self.capture_preview.setMinimumSize(100, 50)
        self.capture_preview.setFrameStyle(QFrame.Box)
        self.capture_preview.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.capture_preview)

        test_capture_btn = QPushButton("Test Capture")
        test_capture_btn.clicked.connect(self._test_capture)
        preview_layout.addWidget(test_capture_btn)

        preview_layout.addStretch()
        layout.addLayout(preview_layout)

        # Polling rate
        polling_layout = QHBoxLayout()
        polling_layout.addWidget(QLabel("Polling Rate (ms):"))
        self.polling_slider = QSlider(Qt.Horizontal)
        self.polling_slider.setRange(50, 500)
        self.polling_slider.setTickInterval(50)
        self.polling_slider.valueChanged.connect(self._on_polling_changed)
        polling_layout.addWidget(self.polling_slider)
        self.polling_value = QLabel("100")
        self.polling_value.setMinimumWidth(40)
        polling_layout.addWidget(self.polling_value)
        layout.addLayout(polling_layout)

        return group

    def _create_threshold_group(self) -> QGroupBox:
        group = QGroupBox("Energy Threshold")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Alert when energy below:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 999)
        self.threshold_spin.valueChanged.connect(self._on_threshold_changed)
        layout.addWidget(self.threshold_spin)

        layout.addStretch()

        return group

    def _create_alert_group(self) -> QGroupBox:
        group = QGroupBox("Alert Settings")
        layout = QVBoxLayout(group)

        # Alert mode selector
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Display Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Custom Image", AlertMode.IMAGE)
        self.mode_combo.addItem("Energy Number", AlertMode.NUMBER)
        self.mode_combo.addItem("Filtered Region", AlertMode.FILTERED)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Mode description
        self.mode_description = QLabel("")
        self.mode_description.setStyleSheet("color: gray; font-size: 10px;")
        self.mode_description.setWordWrap(True)
        layout.addWidget(self.mode_description)

        # Alert image (only for IMAGE mode)
        self.image_widget = QWidget()
        image_inner_layout = QVBoxLayout(self.image_widget)
        image_inner_layout.setContentsMargins(0, 0, 0, 0)

        image_layout = QHBoxLayout()
        image_layout.addWidget(QLabel("Alert Image:"))
        self.image_path_label = QLabel("No image selected")
        self.image_path_label.setWordWrap(True)
        image_layout.addWidget(self.image_path_label, 1)
        select_image_btn = QPushButton("Select Image")
        select_image_btn.clicked.connect(self._select_alert_image)
        image_layout.addWidget(select_image_btn)
        image_inner_layout.addLayout(image_layout)

        # Image preview
        self.alert_preview = QLabel()
        self.alert_preview.setMaximumHeight(100)
        self.alert_preview.setAlignment(Qt.AlignCenter)
        image_inner_layout.addWidget(self.alert_preview)

        layout.addWidget(self.image_widget)

        # Position with arrow controls
        alert_pos_container = QHBoxLayout()

        # Arrow buttons for alert position
        alert_arrow_grid = QGridLayout()
        alert_arrow_grid.setSpacing(2)

        alert_btn_up = QPushButton("\u25B2")  # Up triangle
        alert_btn_up.setFixedSize(30, 25)
        alert_btn_up.clicked.connect(lambda: self._nudge_alert(0, -1))
        alert_arrow_grid.addWidget(alert_btn_up, 0, 1)

        alert_btn_left = QPushButton("\u25C0")  # Left triangle
        alert_btn_left.setFixedSize(30, 25)
        alert_btn_left.clicked.connect(lambda: self._nudge_alert(-1, 0))
        alert_arrow_grid.addWidget(alert_btn_left, 1, 0)

        alert_btn_right = QPushButton("\u25B6")  # Right triangle
        alert_btn_right.setFixedSize(30, 25)
        alert_btn_right.clicked.connect(lambda: self._nudge_alert(1, 0))
        alert_arrow_grid.addWidget(alert_btn_right, 1, 2)

        alert_btn_down = QPushButton("\u25BC")  # Down triangle
        alert_btn_down.setFixedSize(30, 25)
        alert_btn_down.clicked.connect(lambda: self._nudge_alert(0, 1))
        alert_arrow_grid.addWidget(alert_btn_down, 2, 1)

        alert_pos_container.addLayout(alert_arrow_grid)

        # Position values
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("X:"))
        self.alert_x = QSpinBox()
        self.alert_x.setRange(0, 9999)
        self.alert_x.valueChanged.connect(self._on_alert_changed)
        pos_layout.addWidget(self.alert_x)

        pos_layout.addWidget(QLabel("Y:"))
        self.alert_y = QSpinBox()
        self.alert_y.setRange(0, 9999)
        self.alert_y.valueChanged.connect(self._on_alert_changed)
        pos_layout.addWidget(self.alert_y)

        select_pos_btn = QPushButton("Pick Center")
        select_pos_btn.clicked.connect(self._open_position_selector)
        pos_layout.addWidget(select_pos_btn)

        alert_pos_container.addLayout(pos_layout)
        alert_pos_container.addStretch()

        layout.addLayout(alert_pos_container)

        # Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size W:"))
        self.alert_w = QSpinBox()
        self.alert_w.setRange(10, 1000)
        self.alert_w.valueChanged.connect(self._on_alert_changed)
        size_layout.addWidget(self.alert_w)

        size_layout.addWidget(QLabel("H:"))
        self.alert_h = QSpinBox()
        self.alert_h.setRange(10, 1000)
        self.alert_h.valueChanged.connect(self._on_alert_changed)
        size_layout.addWidget(self.alert_h)

        size_layout.addStretch()
        layout.addLayout(size_layout)

        # Opacity
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)
        self.opacity_value = QLabel("100%")
        self.opacity_value.setMinimumWidth(45)
        opacity_layout.addWidget(self.opacity_value)
        layout.addLayout(opacity_layout)

        return group

    def _create_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QHBoxLayout(group)

        self.status_label = QLabel("Monitoring: Stopped")
        layout.addWidget(self.status_label)

        self.energy_label = QLabel("Energy: --")
        layout.addWidget(self.energy_label)

        layout.addStretch()

        return group

    def _create_controls(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.test_btn = QPushButton("Test Alert")
        self.test_btn.clicked.connect(self._on_test_alert)
        layout.addWidget(self.test_btn)

        layout.addStretch()

        self.toggle_btn = QPushButton("Start Monitoring")
        self.toggle_btn.setMinimumWidth(150)
        self.toggle_btn.clicked.connect(self._toggle_monitoring)
        layout.addWidget(self.toggle_btn)

        return widget

    def _load_config_to_ui(self):
        # Block signals during loading
        widgets = [
            self.region_x, self.region_y, self.region_w, self.region_h,
            self.threshold_spin, self.polling_slider, self.color_tolerance,
            self.skew_spin, self.alert_x, self.alert_y, self.alert_w, self.alert_h,
            self.opacity_slider, self.mode_combo
        ]
        for w in widgets:
            w.blockSignals(True)

        # Tesseract
        self.tesseract_path_edit.setText(self.config.tesseract_path)

        # Capture region
        r = self.config.capture_region
        self.region_x.setValue(r.x)
        self.region_y.setValue(r.y)
        self.region_w.setValue(r.width)
        self.region_h.setValue(r.height)
        self._update_region_label()

        # Text color
        c = self.config.text_color
        self._update_color_preview(c.r, c.g, c.b)
        self.color_tolerance.setValue(c.tolerance)
        self.skew_spin.setValue(c.skew)

        # Polling
        self.polling_slider.setValue(self.config.polling_rate_ms)
        self.polling_value.setText(str(self.config.polling_rate_ms))

        # Threshold
        self.threshold_spin.setValue(self.config.threshold)

        # Alert mode
        mode_index = self.mode_combo.findData(self.config.alert_mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self._update_mode_ui()

        # Alert position/size (mode-specific)
        self._load_current_mode_settings()
        self.opacity_slider.setValue(int(self.config.alert_opacity * 100))
        self.opacity_value.setText(f"{int(self.config.alert_opacity * 100)}%")

        if self.config.alert_image_path:
            self._load_alert_preview(self.config.alert_image_path)

        # Unblock signals
        for w in widgets:
            w.blockSignals(False)

    def _update_region_label(self):
        r = self.config.capture_region
        self.region_label.setText(f"Region: {r.width}x{r.height} @ ({r.x}, {r.y})")

    def _update_color_preview(self, r: int, g: int, b: int):
        """Update the color preview box and label."""
        palette = self.color_preview.palette()
        from PyQt5.QtGui import QColor as QC
        palette.setColor(self.color_preview.backgroundRole(), QC(r, g, b))
        self.color_preview.setPalette(palette)
        self.color_value_label.setText(f"RGB({r}, {g}, {b})")

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract Executable",
            "", "Executable (*.exe);;All Files (*)"
        )
        if path:
            self.tesseract_path_edit.setText(path)
            self.config.tesseract_path = path
            self._save_and_emit()

    def _open_region_selector(self):
        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.show()

    def _on_region_selected(self, region: CaptureRegion):
        self.config.capture_region = region
        self.region_x.setValue(region.x)
        self.region_y.setValue(region.y)
        self.region_w.setValue(region.width)
        self.region_h.setValue(region.height)
        self._update_region_label()
        self._save_and_emit()

    def _open_capture_region_adjuster(self):
        region = self.config.capture_region
        self._region_adjuster = RegionAdjuster(region)
        self._region_adjuster.region_adjusted.connect(self._on_capture_region_adjusted)
        self._region_adjuster.show()

    def _on_capture_region_adjusted(self, region: CaptureRegion):
        self.config.capture_region = region
        self.region_x.setValue(region.x)
        self.region_y.setValue(region.y)
        self.region_w.setValue(region.width)
        self.region_h.setValue(region.height)
        self._update_region_label()
        self._save_and_emit()

    def _open_color_picker(self):
        self._color_picker = ColorPicker()
        self._color_picker.color_picked.connect(self._on_color_picked)
        self._color_picker.show()

    def _on_color_picked(self, r: int, g: int, b: int):
        self.config.text_color.r = r
        self.config.text_color.g = g
        self.config.text_color.b = b
        self._update_color_preview(r, g, b)
        self._save_and_emit()

    def _on_color_tolerance_changed(self, value: int):
        self.config.text_color.tolerance = value
        self._save_and_emit()

    def _on_skew_changed(self, value: float):
        self.config.text_color.skew = value
        self._save_and_emit()

    def _on_region_changed(self):
        self.config.capture_region = CaptureRegion(
            x=self.region_x.value(),
            y=self.region_y.value(),
            width=self.region_w.value(),
            height=self.region_h.value(),
        )
        self._update_region_label()
        self._save_and_emit()

    def _nudge_region(self, dx: int, dy: int):
        """Move capture region by dx, dy pixels."""
        self.region_x.setValue(self.region_x.value() + dx)
        self.region_y.setValue(self.region_y.value() + dy)

    def _on_polling_changed(self, value: int):
        self.polling_value.setText(str(value))
        self.config.polling_rate_ms = value
        self._save_and_emit()

    def _on_threshold_changed(self, value: int):
        self.config.threshold = value
        self._save_and_emit()

    def _on_mode_changed(self, index: int):
        mode = self.mode_combo.currentData()
        self.config.alert_mode = mode
        self._update_mode_ui()
        self._load_current_mode_settings()
        self._save_and_emit()

    def _update_mode_ui(self):
        """Update UI visibility based on selected mode."""
        mode = self.config.alert_mode

        # Show/hide image selection based on mode
        self.image_widget.setVisible(mode == AlertMode.IMAGE)

        # Update mode description
        descriptions = {
            AlertMode.IMAGE: "Show a custom image when energy is low.",
            AlertMode.NUMBER: "Display the current energy number in large text.",
            AlertMode.FILTERED: "Show the filtered capture region (no OCR, always visible when monitoring).",
        }
        self.mode_description.setText(descriptions.get(mode, ""))

    def _load_current_mode_settings(self):
        """Load position/size settings for the current mode into the UI."""
        # Block signals to prevent saving while loading
        self.alert_x.blockSignals(True)
        self.alert_y.blockSignals(True)
        self.alert_w.blockSignals(True)
        self.alert_h.blockSignals(True)

        pos = self.config.get_current_position()
        size = self.config.get_current_size()
        self.alert_x.setValue(pos.x)
        self.alert_y.setValue(pos.y)
        self.alert_w.setValue(size.width)
        self.alert_h.setValue(size.height)

        self.alert_x.blockSignals(False)
        self.alert_y.blockSignals(False)
        self.alert_w.blockSignals(False)
        self.alert_h.blockSignals(False)

    def _select_alert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Alert Image",
            "", "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)"
        )
        if path:
            self.config.alert_image_path = path
            self._load_alert_preview(path)
            self._save_and_emit()

    def _load_alert_preview(self, path: str):
        self.image_path_label.setText(path.split("/")[-1].split("\\")[-1])
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.alert_preview.setPixmap(scaled)

    def _open_position_selector(self):
        self._position_selector = PositionSelector()
        self._position_selector.position_selected.connect(self._on_position_selected)
        self._position_selector.show()

    def _on_position_selected(self, x: int, y: int):
        # Convert center position to top-left corner
        size = self.config.get_current_size()
        top_left_x = x - size.width // 2
        top_left_y = y - size.height // 2
        self.alert_x.setValue(top_left_x)
        self.alert_y.setValue(top_left_y)
        self.config.set_current_position(AlertPosition(x=top_left_x, y=top_left_y))
        self._save_and_emit()

    def _on_alert_changed(self):
        self.config.set_current_position(AlertPosition(
            x=self.alert_x.value(),
            y=self.alert_y.value(),
        ))
        self.config.set_current_size(AlertSize(
            width=self.alert_w.value(),
            height=self.alert_h.value(),
        ))
        self._save_and_emit()

    def _nudge_alert(self, dx: int, dy: int):
        """Move alert position by dx, dy pixels."""
        self.alert_x.setValue(self.alert_x.value() + dx)
        self.alert_y.setValue(self.alert_y.value() + dy)

    def _on_opacity_changed(self, value: int):
        self.opacity_value.setText(f"{value}%")
        self.config.alert_opacity = value / 100.0
        self._save_and_emit()

    def _test_capture(self):
        # Import here to avoid circular dependency
        from capture import EnergyMonitor

        self.config.tesseract_path = self.tesseract_path_edit.text()
        monitor = EnergyMonitor(self.config)
        try:
            energy, img = monitor.capture_single()

            # Show preview
            img_qt = self._pil_to_qpixmap(img)
            scaled = img_qt.scaled(100, 50, Qt.KeepAspectRatio)
            self.capture_preview.setPixmap(scaled)

            if energy is not None:
                self.energy_label.setText(f"Energy: {energy}")
            else:
                self.energy_label.setText("Energy: OCR Failed")
        except Exception as e:
            QMessageBox.warning(self, "Capture Error", f"Failed to capture: {str(e)}")

    def _pil_to_qpixmap(self, img: Image.Image) -> QPixmap:
        img = img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    def _on_test_alert(self):
        self.test_alert.emit()

    def _toggle_monitoring(self):
        if self.config.monitoring_active:
            self.stop_monitoring.emit()
            self.config.monitoring_active = False
            self.toggle_btn.setText("Start Monitoring")
            self.status_label.setText("Monitoring: Stopped")
        else:
            # Validate config before starting
            if self.config.alert_mode == AlertMode.IMAGE and not self.config.alert_image_path:
                QMessageBox.warning(self, "Configuration Error", "Please select an alert image first.")
                return

            self.config.tesseract_path = self.tesseract_path_edit.text()
            self.start_monitoring.emit()
            self.config.monitoring_active = True
            self.toggle_btn.setText("Stop Monitoring")
            self.status_label.setText("Monitoring: Active")

        self._save_and_emit()

    def update_energy_display(self, energy: int):
        self.energy_label.setText(f"Energy: {energy}")

    def update_status(self, monitoring: bool):
        self.config.monitoring_active = monitoring
        if monitoring:
            self.toggle_btn.setText("Stop Monitoring")
            self.status_label.setText("Monitoring: Active")
        else:
            self.toggle_btn.setText("Start Monitoring")
            self.status_label.setText("Monitoring: Stopped")

    def _save_and_emit(self):
        save_config(self.config)
        self.config_changed.emit(self.config)

    def closeEvent(self, event):
        save_config(self.config)
        event.accept()
