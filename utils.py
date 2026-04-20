from PyQt6.QtWidgets import QPushButton, QFrame
from PyQt6.QtGui import QCursor, QPixmap, QPainter, QColor, QPen, QPainterPath, QBrush
from PyQt6.QtCore import Qt, QSize, QPoint


class B(QPushButton):
    """Helper class to create QPushButtons with less boilerplate."""

    def __init__(self, text, callback=None, size=None, style=None, check=False):
        super().__init__(text)
        if callback: self.clicked.connect(callback)
        if size: self.setFixedSize(size)
        if style: self.setStyleSheet(style)
        if check: self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class F(QFrame):
    """Helper class for Frames (used in headers)."""

    def __init__(self, height, style):
        super().__init__()
        self.setFixedHeight(height)
        self.setStyleSheet(style)


class CursorFactory:
    """Generates custom cursors (Realistic Pen, Square Eraser)."""

    @staticmethod
    def get(type_, color=Qt.GlobalColor.black, size=20):
        # Create a pixmap large enough to hold the icon (32x32 standard)
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if type_ == 'eraser':
            # Draw Square Eraser (Size adapts to brush size)
            p.setPen(QPen(Qt.GlobalColor.black, 1))
            p.setBrush(Qt.GlobalColor.white)
            rect_size = max(10, int(size))  # Minimum size visibility
            center = (32 - rect_size) // 2
            p.drawRect(center, center, rect_size, rect_size)
            p.end()
            return QCursor(pix)

        elif type_ == 'pen':
            # --- REALISTIC PEN DRAWING (Pointing Top-Left) ---

            # 1. The Nib (Colored Tip)
            # Points exactly at 0,0
            path_nib = QPainterPath()
            path_nib.moveTo(0, 0)  # The Tip (Hotspot)
            path_nib.lineTo(8, 2)  # Top side
            path_nib.lineTo(2, 8)  # Left side
            path_nib.closeSubpath()

            p.setPen(QPen(QColor("#999999"), 1))
            p.setBrush(QColor(color))  # <--- DYNAMIC COLOR TIP
            p.drawPath(path_nib)

            # 2. The Barrel (Brown Body)
            path_body = QPainterPath()
            path_body.moveTo(2, 8)
            path_body.lineTo(8, 2)
            path_body.lineTo(20, 14)
            path_body.lineTo(14, 20)
            path_body.closeSubpath()

            p.setPen(QPen(QColor("#3E2723"), 1))
            p.setBrush(QColor("#795548"))
            p.drawPath(path_body)

            # 3. The Cap (Dark Brown End)
            path_cap = QPainterPath()
            path_cap.moveTo(14, 20)
            path_cap.lineTo(20, 14)
            path_cap.lineTo(24, 18)
            path_cap.lineTo(18, 24)
            path_cap.closeSubpath()

            p.setBrush(QColor("#3E2723"))
            p.drawPath(path_cap)

            p.end()

            # Return Cursor with Hotspot at the Nib Tip (0, 0)
            return QCursor(pix, 0, 0)

        else:
            # Fallback simple circle
            p.setPen(QPen(QColor(0, 0, 0, 100), 1))
            p.setBrush(QColor(color))
            p.drawEllipse(1, 1, int(size) - 1, int(size) - 1)
            p.end()
            return QCursor(pix)
