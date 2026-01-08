from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QScreen, QImage, QPixmap
from config import CaptureRegion, TextColor
import mss
import mss.tools


class RegionSelector(QWidget):
    region_selected = pyqtSignal(CaptureRegion)

    def __init__(self):
        super().__init__()
        self._start_pos = None
        self._current_pos = None
        self._setup_window()

    def _setup_window(self):
        # Get the full virtual desktop geometry (all monitors)
        screen = QApplication.primaryScreen()
        geometry = screen.virtualGeometry()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(geometry)
        self.setCursor(Qt.CrossCursor)

        # Store offset for coordinate calculation
        self._offset_x = geometry.x()
        self._offset_y = geometry.y()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Very light tint so user can see through (alpha 30 = ~12% opacity)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))

        # Draw selection rectangle if selecting
        if self._start_pos and self._current_pos:
            rect = self._get_selection_rect()

            # Clear the selection area (make it transparent-ish)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # Draw border around selection (thick bright green)
            pen = QPen(QColor(0, 255, 0), 3)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw a second inner border for visibility
            pen2 = QPen(QColor(255, 255, 255), 1)
            painter.setPen(pen2)
            inner_rect = rect.adjusted(3, 3, -3, -3)
            painter.drawRect(inner_rect)

            # Draw dimensions text
            width = rect.width()
            height = rect.height()
            x = rect.x() + self._offset_x
            y = rect.y() + self._offset_y

            text = f"{width} x {height} @ ({x}, {y})"
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.setPen(QColor(255, 255, 255))

            # Position text above or below selection
            text_y = rect.top() - 10 if rect.top() > 30 else rect.bottom() + 20
            painter.drawText(rect.left(), text_y, text)

        # Instructions (with shadow for visibility)
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        # Shadow
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(22, 32, "Click and drag to select the energy region. Press ESC to cancel.")
        # Text
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(20, 30, "Click and drag to select the energy region. Press ESC to cancel.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start_pos:
            self._current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._start_pos:
            self._current_pos = event.pos()
            rect = self._get_selection_rect()

            if rect.width() > 5 and rect.height() > 5:
                # Create region with screen coordinates
                region = CaptureRegion(
                    x=rect.x() + self._offset_x,
                    y=rect.y() + self._offset_y,
                    width=rect.width(),
                    height=rect.height(),
                )
                self.region_selected.emit(region)

            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def _get_selection_rect(self) -> QRect:
        if not self._start_pos or not self._current_pos:
            return QRect()

        x1 = min(self._start_pos.x(), self._current_pos.x())
        y1 = min(self._start_pos.y(), self._current_pos.y())
        x2 = max(self._start_pos.x(), self._current_pos.x())
        y2 = max(self._start_pos.y(), self._current_pos.y())

        return QRect(x1, y1, x2 - x1, y2 - y1)


class PositionSelector(QWidget):
    """Simplified selector for choosing alert position by clicking."""
    position_selected = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self._setup_window()

    def _setup_window(self):
        screen = QApplication.primaryScreen()
        geometry = screen.virtualGeometry()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(geometry)
        self.setCursor(Qt.CrossCursor)

        self._offset_x = geometry.x()
        self._offset_y = geometry.y()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))

        # Instructions (with shadow for visibility)
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(22, 32, "Click to select alert position. Press ESC to cancel.")
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(20, 30, "Click to select alert position. Press ESC to cancel.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            x = event.pos().x() + self._offset_x
            y = event.pos().y() + self._offset_y
            self.position_selected.emit(x, y)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


class RegionAdjuster(QWidget):
    """Overlay for adjusting an existing region by dragging corners/edges."""
    region_adjusted = pyqtSignal(CaptureRegion)

    HANDLE_SIZE = 12

    # Handle positions
    HANDLE_NONE = 0
    HANDLE_TOP_LEFT = 1
    HANDLE_TOP = 2
    HANDLE_TOP_RIGHT = 3
    HANDLE_RIGHT = 4
    HANDLE_BOTTOM_RIGHT = 5
    HANDLE_BOTTOM = 6
    HANDLE_BOTTOM_LEFT = 7
    HANDLE_LEFT = 8
    HANDLE_MOVE = 9  # Moving the whole region

    def __init__(self, region: CaptureRegion):
        super().__init__()
        self._region = QRect(region.x, region.y, region.width, region.height)
        self._active_handle = self.HANDLE_NONE
        self._drag_start = None
        self._original_region = None
        self._setup_window()

    def _setup_window(self):
        screen = QApplication.primaryScreen()
        geometry = screen.virtualGeometry()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(geometry)
        self.setMouseTracking(True)

        self._offset_x = geometry.x()
        self._offset_y = geometry.y()

    def _screen_to_widget(self, region: QRect) -> QRect:
        """Convert screen coordinates to widget coordinates."""
        return QRect(
            region.x() - self._offset_x,
            region.y() - self._offset_y,
            region.width(),
            region.height()
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        # Light overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))

        # Convert region to widget coordinates for drawing
        rect = self._screen_to_widget(self._region)

        # Clear the region area
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(rect, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Draw region border
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        painter.drawRect(rect)

        # Draw handles
        handle_color = QColor(255, 255, 255)
        handle_border = QColor(0, 0, 0)

        handles = self._get_handle_rects(rect)
        for handle_rect in handles.values():
            painter.fillRect(handle_rect, handle_color)
            painter.setPen(QPen(handle_border, 1))
            painter.drawRect(handle_rect)

        # Draw dimensions
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        text = f"{self._region.width()} x {self._region.height()} @ ({self._region.x()}, {self._region.y()})"
        text_y = rect.top() - 10 if rect.top() > 40 else rect.bottom() + 20
        # Shadow
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(rect.left() + 2, text_y + 2, text)
        # Text
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect.left(), text_y, text)

        # Instructions
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(22, 32, "Drag corners/edges to resize. Drag inside to move. Press ENTER to confirm, ESC to cancel.")
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(20, 30, "Drag corners/edges to resize. Drag inside to move. Press ENTER to confirm, ESC to cancel.")

    def _get_handle_rects(self, rect: QRect) -> dict:
        """Get rectangles for all handles."""
        hs = self.HANDLE_SIZE
        hh = hs // 2
        cx = rect.center().x()
        cy = rect.center().y()

        return {
            self.HANDLE_TOP_LEFT: QRect(rect.left() - hh, rect.top() - hh, hs, hs),
            self.HANDLE_TOP: QRect(cx - hh, rect.top() - hh, hs, hs),
            self.HANDLE_TOP_RIGHT: QRect(rect.right() - hh, rect.top() - hh, hs, hs),
            self.HANDLE_RIGHT: QRect(rect.right() - hh, cy - hh, hs, hs),
            self.HANDLE_BOTTOM_RIGHT: QRect(rect.right() - hh, rect.bottom() - hh, hs, hs),
            self.HANDLE_BOTTOM: QRect(cx - hh, rect.bottom() - hh, hs, hs),
            self.HANDLE_BOTTOM_LEFT: QRect(rect.left() - hh, rect.bottom() - hh, hs, hs),
            self.HANDLE_LEFT: QRect(rect.left() - hh, cy - hh, hs, hs),
        }

    def _get_handle_at(self, pos: QPoint) -> int:
        """Determine which handle (if any) is at the given position."""
        rect = self._screen_to_widget(self._region)
        handles = self._get_handle_rects(rect)

        for handle_id, handle_rect in handles.items():
            if handle_rect.contains(pos):
                return handle_id

        # Check if inside the region (for moving)
        if rect.contains(pos):
            return self.HANDLE_MOVE

        return self.HANDLE_NONE

    def _update_cursor(self, handle: int):
        """Update cursor based on handle."""
        cursors = {
            self.HANDLE_TOP_LEFT: Qt.SizeFDiagCursor,
            self.HANDLE_TOP: Qt.SizeVerCursor,
            self.HANDLE_TOP_RIGHT: Qt.SizeBDiagCursor,
            self.HANDLE_RIGHT: Qt.SizeHorCursor,
            self.HANDLE_BOTTOM_RIGHT: Qt.SizeFDiagCursor,
            self.HANDLE_BOTTOM: Qt.SizeVerCursor,
            self.HANDLE_BOTTOM_LEFT: Qt.SizeBDiagCursor,
            self.HANDLE_LEFT: Qt.SizeHorCursor,
            self.HANDLE_MOVE: Qt.SizeAllCursor,
            self.HANDLE_NONE: Qt.ArrowCursor,
        }
        self.setCursor(cursors.get(handle, Qt.ArrowCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._active_handle = self._get_handle_at(event.pos())
            if self._active_handle != self.HANDLE_NONE:
                self._drag_start = event.pos()
                self._original_region = QRect(self._region)

    def mouseMoveEvent(self, event):
        if self._drag_start and self._active_handle != self.HANDLE_NONE:
            delta = event.pos() - self._drag_start
            self._apply_drag(delta)
            self.update()
        else:
            # Update cursor on hover
            handle = self._get_handle_at(event.pos())
            self._update_cursor(handle)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._active_handle = self.HANDLE_NONE
            self._drag_start = None
            self._original_region = None

    def _apply_drag(self, delta: QPoint):
        """Apply drag delta to the region based on active handle."""
        if not self._original_region:
            return

        r = QRect(self._original_region)
        dx, dy = delta.x(), delta.y()

        if self._active_handle == self.HANDLE_MOVE:
            r.translate(dx, dy)
        elif self._active_handle == self.HANDLE_TOP_LEFT:
            r.setTopLeft(r.topLeft() + delta)
        elif self._active_handle == self.HANDLE_TOP:
            r.setTop(r.top() + dy)
        elif self._active_handle == self.HANDLE_TOP_RIGHT:
            r.setTopRight(r.topRight() + delta)
        elif self._active_handle == self.HANDLE_RIGHT:
            r.setRight(r.right() + dx)
        elif self._active_handle == self.HANDLE_BOTTOM_RIGHT:
            r.setBottomRight(r.bottomRight() + delta)
        elif self._active_handle == self.HANDLE_BOTTOM:
            r.setBottom(r.bottom() + dy)
        elif self._active_handle == self.HANDLE_BOTTOM_LEFT:
            r.setBottomLeft(r.bottomLeft() + delta)
        elif self._active_handle == self.HANDLE_LEFT:
            r.setLeft(r.left() + dx)

        # Ensure minimum size
        if r.width() >= 20 and r.height() >= 20:
            self._region = r.normalized()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Emit the adjusted region
            region = CaptureRegion(
                x=self._region.x(),
                y=self._region.y(),
                width=self._region.width(),
                height=self._region.height(),
            )
            self.region_adjusted.emit(region)
            self.close()


class ColorPicker(QWidget):
    """Overlay for picking a color from the screen by clicking."""
    color_picked = pyqtSignal(int, int, int)  # r, g, b

    MAGNIFIER_SIZE = 150  # Size of magnifier window
    ZOOM_FACTOR = 8  # How much to zoom in

    def __init__(self):
        super().__init__()
        self._screenshot = None
        self._screenshot_pixmap = None
        self._current_pos = QPoint(0, 0)
        self._setup_window()

    def _setup_window(self):
        screen = QApplication.primaryScreen()
        geometry = screen.virtualGeometry()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(geometry)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        self._offset_x = geometry.x()
        self._offset_y = geometry.y()

        # Capture screenshot of entire virtual desktop
        self._capture_screenshot(geometry)

    def _capture_screenshot(self, geometry):
        """Capture the entire screen for color picking."""
        with mss.mss() as sct:
            monitor = {
                "left": geometry.x(),
                "top": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
            }
            screenshot = sct.grab(monitor)
            # Store raw pixel data for color sampling
            self._screenshot_width = screenshot.width
            self._screenshot_height = screenshot.height
            # mss returns BGRA format
            self._screenshot_data = bytes(screenshot.bgra)

            # Convert to QImage for display
            img = QImage(
                self._screenshot_data,
                screenshot.width,
                screenshot.height,
                screenshot.width * 4,
                QImage.Format_ARGB32
            )
            # Note: mss gives BGRA, QImage expects ARGB, but the byte order works out
            # because of how Qt handles it. We may need to swap if colors look wrong.
            self._screenshot_pixmap = QPixmap.fromImage(img)

    def _get_pixel_color(self, x: int, y: int) -> tuple:
        """Get RGB color at screen position."""
        # Convert widget coords to screenshot coords
        sx = x
        sy = y

        if 0 <= sx < self._screenshot_width and 0 <= sy < self._screenshot_height:
            # Calculate byte offset (BGRA format, 4 bytes per pixel)
            offset = (sy * self._screenshot_width + sx) * 4
            if offset + 2 < len(self._screenshot_data):
                b = self._screenshot_data[offset]
                g = self._screenshot_data[offset + 1]
                r = self._screenshot_data[offset + 2]
                return (r, g, b)
        return (255, 255, 255)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw the screenshot with a slight tint
        if self._screenshot_pixmap:
            painter.drawPixmap(0, 0, self._screenshot_pixmap)
            # Add slight overlay
            painter.fillRect(self.rect(), QColor(0, 0, 0, 30))

        # Draw magnifier near cursor
        self._draw_magnifier(painter)

        # Instructions
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(22, 32, "Click on the energy number to sample its color. Press ESC to cancel.")
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(20, 30, "Click on the energy number to sample its color. Press ESC to cancel.")

    def _draw_magnifier(self, painter: QPainter):
        """Draw a magnified view of the area around the cursor."""
        mx, my = self._current_pos.x(), self._current_pos.y()

        # Calculate source rectangle (area to magnify)
        src_size = self.MAGNIFIER_SIZE // self.ZOOM_FACTOR
        src_x = mx - src_size // 2
        src_y = my - src_size // 2

        # Calculate magnifier position (offset from cursor)
        mag_x = mx + 20
        mag_y = my + 20

        # Keep magnifier on screen
        if mag_x + self.MAGNIFIER_SIZE > self.width():
            mag_x = mx - self.MAGNIFIER_SIZE - 20
        if mag_y + self.MAGNIFIER_SIZE > self.height():
            mag_y = my - self.MAGNIFIER_SIZE - 20

        # Draw magnifier background
        mag_rect = QRect(mag_x, mag_y, self.MAGNIFIER_SIZE, self.MAGNIFIER_SIZE)
        painter.fillRect(mag_rect, QColor(40, 40, 40))

        # Draw magnified pixels
        if self._screenshot_pixmap:
            src_rect = QRect(src_x, src_y, src_size, src_size)
            painter.drawPixmap(mag_rect, self._screenshot_pixmap, src_rect)

        # Draw crosshairs in center of magnifier
        center_x = mag_x + self.MAGNIFIER_SIZE // 2
        center_y = mag_y + self.MAGNIFIER_SIZE // 2

        # Draw pixel highlight box
        pixel_size = self.ZOOM_FACTOR
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawRect(
            center_x - pixel_size // 2,
            center_y - pixel_size // 2,
            pixel_size,
            pixel_size
        )

        # Draw border around magnifier
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawRect(mag_rect)

        # Get and display current color
        r, g, b = self._get_pixel_color(mx, my)

        # Draw color preview box
        preview_rect = QRect(mag_x, mag_y + self.MAGNIFIER_SIZE + 5, self.MAGNIFIER_SIZE, 30)
        painter.fillRect(preview_rect, QColor(r, g, b))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawRect(preview_rect)

        # Draw RGB text
        text_rect = QRect(mag_x, mag_y + self.MAGNIFIER_SIZE + 40, self.MAGNIFIER_SIZE, 20)
        painter.fillRect(text_rect, QColor(0, 0, 0, 180))
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(text_rect, Qt.AlignCenter, f"RGB({r}, {g}, {b})")

    def mouseMoveEvent(self, event):
        self._current_pos = event.pos()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            r, g, b = self._get_pixel_color(x, y)
            self.color_picked.emit(r, g, b)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
