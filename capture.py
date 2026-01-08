import mss
import numpy as np
from PIL import Image
import pytesseract
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from config import AppConfig, CaptureRegion, TextColor, AlertMode


class EnergyMonitor(QThread):
    energy_changed = pyqtSignal(int)  # Emits current energy value
    threshold_crossed = pyqtSignal(bool)  # True = below threshold, False = above
    filtered_image = pyqtSignal(object)  # Emits filtered PIL Image for display
    ocr_error = pyqtSignal(str)  # Emits error message if OCR fails

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._running = False
        self._mutex = QMutex()
        self._last_energy = -1
        self._last_below_threshold = None
        self._sct = None

    def update_config(self, config: AppConfig):
        self._mutex.lock()
        self.config = config
        self._mutex.unlock()

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        self._sct = mss.mss()

        # Configure tesseract path if specified
        if self.config.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_path

        while self._running:
            try:
                self._mutex.lock()
                region = self.config.capture_region
                threshold = self.config.threshold
                polling_rate = self.config.polling_rate_ms
                text_color = self.config.text_color
                alert_mode = self.config.alert_mode
                self._mutex.unlock()

                # Capture the screen region
                energy, filtered_img = self._capture_and_read(region, text_color, alert_mode)

                # Always emit filtered image for FILTERED mode
                if alert_mode == AlertMode.FILTERED and filtered_img is not None:
                    self.filtered_image.emit(filtered_img)

                if energy is not None:
                    # Emit energy changed if value changed
                    if energy != self._last_energy:
                        self.energy_changed.emit(energy)
                        self._last_energy = energy

                    # Check threshold crossing
                    below_threshold = energy < threshold
                    if below_threshold != self._last_below_threshold:
                        self.threshold_crossed.emit(below_threshold)
                        self._last_below_threshold = below_threshold
                elif alert_mode == AlertMode.FILTERED:
                    # For filtered mode, still check threshold based on whether we see anything
                    # Just emit that we're below threshold to show the overlay
                    if self._last_below_threshold != True:
                        self.threshold_crossed.emit(True)
                        self._last_below_threshold = True

                # Sleep for polling interval
                self.msleep(polling_rate)

            except Exception as e:
                self.ocr_error.emit(str(e))
                self.msleep(1000)  # Wait longer on error

        if self._sct:
            self._sct.close()

    def _capture_and_read(self, region: CaptureRegion, text_color: TextColor, alert_mode: AlertMode) -> tuple[int | None, Image.Image | None]:
        # Define capture region for mss
        monitor = {
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        }

        # Capture screenshot
        screenshot = self._sct.grab(monitor)

        # Convert to PIL Image
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # For FILTERED mode, use soft filtering for better display quality
        if alert_mode == AlertMode.FILTERED:
            display_img = self._preprocess_for_display(img, text_color)
            return None, display_img

        # Preprocess for OCR (hard binary threshold, 2x scale)
        filtered_img = self._preprocess_image(img, text_color)

        # Run OCR with optimized settings
        try:
            custom_config = r"--psm 7 -c tessedit_char_whitelist=0123456789"
            text = pytesseract.image_to_string(filtered_img, config=custom_config).strip()

            if text and text.isdigit():
                return int(text), filtered_img
            return None, filtered_img
        except Exception:
            return None, filtered_img

    def _apply_skew(self, img: Image.Image, skew: float) -> Image.Image:
        """Apply vertical shear transformation to correct angled text baseline."""
        if skew == 0:
            return img

        # Calculate how much the image will shift vertically
        shift = abs(skew * img.width)
        new_height = int(img.height + shift)

        # Affine transform coefficients (a, b, c, d, e, f)
        # Maps output (x, y) to input via: input_x = ax + by + c, input_y = dx + ey + f
        # For vertical shear: input_y = y - skew * x (when skew > 0, left side moves down in input = up in output)
        if skew > 0:
            # Left side higher: shift input down as x increases from right
            # Output y maps to input y + skew * (width - x)
            coeffs = (1, 0, 0, -skew, 1, skew * img.width)
        else:
            # Right side higher
            coeffs = (1, 0, 0, -skew, 1, 0)

        # Create larger canvas to fit skewed image
        result = img.transform(
            (img.width, new_height),
            Image.AFFINE,
            coeffs,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(0, 0, 0, 0) if img.mode == "RGBA" else 0
        )
        return result

    def _preprocess_image(self, img: Image.Image, text_color: TextColor) -> Image.Image:
        # Apply skew correction first
        if text_color.skew != 0:
            img = self._apply_skew(img, text_color.skew)

        # Convert to numpy array (RGB)
        arr = np.array(img)

        # Extract target color and tolerance
        target_r, target_g, target_b = text_color.r, text_color.g, text_color.b
        tolerance = text_color.tolerance

        # Calculate color distance for each pixel
        # Using simple per-channel difference within tolerance
        r_match = np.abs(arr[:, :, 0].astype(np.int16) - target_r) <= tolerance
        g_match = np.abs(arr[:, :, 1].astype(np.int16) - target_g) <= tolerance
        b_match = np.abs(arr[:, :, 2].astype(np.int16) - target_b) <= tolerance

        # Pixel matches if all channels are within tolerance
        matches = r_match & g_match & b_match

        # Create binary image: matching pixels are white, others are black
        result = np.where(matches, 255, 0).astype(np.uint8)

        # Convert back to PIL Image
        img = Image.fromarray(result, mode="L")

        # Scale up for better OCR (2x)
        new_size = (img.width * 2, img.height * 2)
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        return img

    def _preprocess_for_display(self, img: Image.Image, text_color: TextColor) -> Image.Image:
        """Soft color filtering for display - preserves anti-aliasing."""
        # Apply skew correction first
        if text_color.skew != 0:
            img = self._apply_skew(img, text_color.skew)

        arr = np.array(img, dtype=np.float32)

        target_r, target_g, target_b = text_color.r, text_color.g, text_color.b
        tolerance = text_color.tolerance

        # Calculate color distance (Euclidean distance in RGB space)
        r_diff = arr[:, :, 0] - target_r
        g_diff = arr[:, :, 1] - target_g
        b_diff = arr[:, :, 2] - target_b
        distance = np.sqrt(r_diff**2 + g_diff**2 + b_diff**2)

        # Convert distance to alpha (closer = more opaque)
        # Use tolerance * sqrt(3) as max distance (corner of RGB cube at tolerance)
        max_distance = tolerance * 1.732  # sqrt(3)

        # Soft falloff: pixels within tolerance are fully visible,
        # pixels beyond fade out smoothly
        alpha = np.clip(1.0 - (distance / max_distance), 0, 1)

        # Apply a slight boost to make text more visible
        alpha = np.power(alpha, 0.7)  # Gamma correction to brighten
        alpha = (alpha * 255).astype(np.uint8)

        # Create RGBA image with white text and variable alpha
        result = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
        result[:, :, 0] = 255  # R
        result[:, :, 1] = 255  # G
        result[:, :, 2] = 255  # B
        result[:, :, 3] = alpha  # A

        return Image.fromarray(result, mode="RGBA")

    def capture_single(self) -> tuple[int | None, Image.Image]:
        """Capture a single frame and return energy value and processed image."""
        if self.config.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_path

        with mss.mss() as sct:
            region = self.config.capture_region
            text_color = self.config.text_color
            monitor = {
                "left": region.x,
                "top": region.y,
                "width": region.width,
                "height": region.height,
            }
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            processed = self._preprocess_image(img, text_color)

            try:
                custom_config = r"--psm 7 -c tessedit_char_whitelist=0123456789"
                text = pytesseract.image_to_string(processed, config=custom_config).strip()
                energy = int(text) if text and text.isdigit() else None
            except Exception:
                energy = None

            return energy, img
