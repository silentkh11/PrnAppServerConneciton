from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygon, QIcon
from PyQt6.QtCore import Qt, QPoint


def get_icon(n, c, s=32):
    px = QPixmap(s, s)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(c), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    if n == 'pen':
        p.setPen(QPen(QColor("#999"), 1))
        p.setBrush(QColor("#FFF"))
        p.drawPolygon(QPolygon([QPoint(0, 0), QPoint(8, 2), QPoint(2, 8)]))
        p.setPen(QPen(QColor("#3E2723"), 1))
        p.setBrush(QColor("#795548"))
        p.drawPolygon(QPolygon([QPoint(2, 8), QPoint(8, 2), QPoint(20, 14), QPoint(14, 20)]))
        p.setBrush(QColor("#3E2723"))
        p.drawPolygon(QPolygon([QPoint(14, 20), QPoint(20, 14), QPoint(24, 18), QPoint(18, 24)]))
    elif n == 'laser':
        p.drawLine(8, 24, 20, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FF4B4B"))
        p.drawEllipse(18, 10, 8, 8)
        p.setBrush(QColor("#FFF"))
        p.drawEllipse(20, 12, 4, 4)
    elif n == 'highlighter':
        p.setPen(QPen(QColor(c), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        p.drawLine(10, 22, 22, 10)
        p.setPen(QPen(QColor(c), 1))
        p.drawRect(8, 22, 4, 4)
    elif n == 'eraser':
        p.drawPolygon(QPolygon([QPoint(x, y) for x, y in [(8, 6), (20, 6), (26, 14), (14, 26), (6, 26), (6, 14)]]))
    elif n == 'lasso':
        p.setPen(QPen(QColor(c), 2, Qt.PenStyle.DashLine))
        p.drawEllipse(6, 6, 20, 20)
        p.setPen(QPen(QColor(c), 2))
        p.drawEllipse(22, 22, 4, 4)
    elif n == 'shapes' or n in ['rect', 'circle', 'line', 'arrow', 'text']:
        p.drawEllipse(14, 6, 12, 12)
        p.drawPolygon(QPolygon([QPoint(6, 26), QPoint(16, 26), QPoint(11, 16)]))
    elif n == 'palette':
        p.drawEllipse(4, 4, 24, 24)
        p.setBrush(QColor(c))
        p.setPen(Qt.PenStyle.NoPen)
        [p.drawEllipse(x, y, 3, 3) for x, y in [(8, 12), (14, 8), (20, 12)]]
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(c), 2))
        p.drawEllipse(14, 20, 6, 6)
    elif n == 'folder':
        p.setPen(QPen(QColor(c), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygon([QPoint(4, 12), QPoint(4, 8), QPoint(12, 8), QPoint(16, 12), QPoint(28, 12)]))
        p.drawRect(4, 12, 24, 14)
    elif n == 'sound':
        p.drawRect(4, 12, 6, 8)
        p.drawPolygon(QPolygon([QPoint(10, 12), QPoint(16, 6), QPoint(16, 26), QPoint(10, 20)]))
        p.drawArc(12, 10, 8, 12, -45 * 16, 90 * 16)
        p.drawArc(10, 6, 14, 20, -45 * 16, 90 * 16)
    elif n == 'mute':
        p.drawRect(4, 12, 6, 8)
        p.drawPolygon(QPolygon([QPoint(10, 12), QPoint(16, 6), QPoint(16, 26), QPoint(10, 20)]))
        p.drawLine(20, 12, 26, 18)
        p.drawLine(26, 12, 20, 18)
    elif n == 'focus':
        p.drawEllipse(8, 8, 16, 16)
        p.drawEllipse(14, 14, 4, 4)
        p.drawLine(16, 2, 16, 6)
        p.drawLine(16, 26, 16, 30)
        p.drawLine(2, 16, 6, 16)
        p.drawLine(26, 16, 30, 16)
    elif n == 'ai_scanner':
        p.setPen(QPen(QColor(c), 2, Qt.PenStyle.DashLine))
        p.drawRect(6, 8, 20, 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#BB86FC"))
        p.drawEllipse(22, 4, 6, 6)
        p.drawEllipse(4, 22, 4, 4)

    p.end()
    return QIcon(px)