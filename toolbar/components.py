import math
from PyQt6.QtWidgets import (QApplication, QWidget, QGridLayout, QFrame,
                             QPushButton, QVBoxLayout, QSizeGrip, QTextEdit, QHBoxLayout)
from PyQt6.QtGui import QColor, QPainter, QCursor
from PyQt6.QtCore import Qt, QPoint, QPointF, QVariantAnimation, QEasingCurve, QTimer, QSize

from .icons import get_icon


class ColorRing(QWidget):
    def __init__(self, tb):
        super().__init__()
        self.tb = tb
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(140, 140)

        self.bg_radius = 0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.valueChanged.connect(self.update_radius)

        self.colors = ['#000000', '#FF4B4B', '#FFFF4B', '#4BFF4B', '#4B8BFF']
        self.btns = []

        for i, c in enumerate(self.colors):
            b = QPushButton(self)
            b.setFixedSize(24, 24)
            b.setStyleSheet(f"background:{c}; border-radius:12px; border:2px solid #FFF;")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, col=c: self.select_color(col))
            b.hide()
            self.btns.append(b)

    def update_radius(self, v):
        self.bg_radius = v
        cx, cy = 70, 70
        for i, b in enumerate(self.btns):
            if v > 18:
                b.show()
                angle = math.radians(-90 + i * 72)
                dist = ((v - 18) / 52.0) * 45
                b.move(int(cx - 12 + math.cos(angle) * dist), int(cy - 12 + math.sin(angle) * dist))
            else:
                b.hide()
        self.update()

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.setBrush(QColor(20, 20, 20, 220))
        qp.drawEllipse(QPointF(70, 70), self.bg_radius, self.bg_radius)

    def show_ring(self, pos):
        self.move(pos.x() - 70, pos.y() - 70)
        self.show()
        self.anim.stop()
        self.anim.setStartValue(18)
        self.anim.setEndValue(70)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        try:
            self.anim.finished.disconnect(self.hide)
        except:
            pass
        self.anim.start()

    def select_color(self, c):
        self.tb.set_color(c)
        self.close_ring()

    def close_ring(self):
        self.anim.stop()
        self.anim.setStartValue(self.bg_radius)
        self.anim.setEndValue(0)
        self.anim.setEasingCurve(QEasingCurve.Type.InBack)
        self.anim.finished.connect(self.hide)
        self.anim.start()

    def leaveEvent(self, e):
        if self.bg_radius > 20: self.close_ring()


class Popup(QWidget):
    def __init__(self, tb, grid=False):
        super().__init__(tb.c)
        self.tb = tb
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background:#2D2D2D; border:1px solid #444; border-radius:8px;")
        self.layout = QGridLayout(self) if grid else QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)

    def leaveEvent(self, e):
        self.hide()


class HoverButton(QWidget):
    def __init__(self, icon, menu, tb, tip=""):
        super().__init__()
        self.menu = menu
        self.tb = tb
        self.icon = icon

        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)

        self.b = QPushButton()
        self.b.setFixedSize(36, 36)
        self.b.setToolTip(tip)
        self.b.setProperty("icon_name", icon)
        self.b.clicked.connect(self.show_menu)
        self.update_style()
        l.addWidget(self.b)

    def update_style(self):
        self.b.setIcon(get_icon(self.icon, self.tb.ui_fg))
        self.b.setIconSize(QSize(20, 20))
        self.b.setStyleSheet(
            f"QPushButton{{background:#000; border: 1px solid #444; border-radius:18px}} QPushButton:hover{{background:#007ACC}}")

    def enterEvent(self, e):
        self.show_menu()

    def leaveEvent(self, e):
        QTimer.singleShot(600, lambda: self.menu.hide() if not self.menu.underMouse() else None)

    def show_menu(self, *_):
        s = self.tb.screen().geometry()
        m_w, m_h = self.menu.sizeHint().width(), self.menu.sizeHint().height()
        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        x, y = global_pos.x(), global_pos.y() + 5
        if x + m_w > s.right(): x = s.right() - m_w - 5
        if y + m_h > s.bottom(): y = self.mapToGlobal(QPoint(0, 0)).y() - m_h - 5
        self.menu.setGeometry(int(x), int(y), int(m_w), int(m_h))
        self.menu.show()


class ShapeTrigger(QPushButton):
    def __init__(self, icon, tb):
        super().__init__()
        self.tb = tb
        self.setFixedSize(36, 36)
        self.setProperty("icon_name", icon)
        self.setToolTip("Shapes (Hover to Expand)")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self.tb.set_shapes_expanded(True)
        super().enterEvent(e)


class StickyNote(QWidget):
    def __init__(self, tb, x=None, y=None, w=220, h=220, txt=""):
        super().__init__()
        self.tb = tb
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        try:
            if x is None or type(x) is bool: x = tb.geometry().right() + 20
            if y is None or type(y) is bool: y = tb.geometry().top() + 20
            self.setGeometry(int(float(x)), int(float(y)), int(float(w)), int(float(h)))
        except Exception:
            self.setGeometry(100, 100, 220, 220)

        self.setStyleSheet("background: #FFF59D; border: 1px solid #E6C500; border-radius: 4px;")
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)

        self.h = QFrame()
        self.h.setFixedHeight(24)
        self.h.setCursor(Qt.CursorShape.PointingHandCursor)
        self.h.setStyleSheet(
            "background: #FBE983; border-bottom: 1px solid #E6C500; border-top-left-radius: 4px; border-top-right-radius: 4px;")

        hl = QHBoxLayout(self.h)
        hl.setContentsMargins(5, 0, 5, 0)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #555; font-weight: bold; } QPushButton:hover { color: red; }")
        self.close_btn.clicked.connect(self.close_note)

        hl.addStretch()
        hl.addWidget(self.close_btn)
        l.addWidget(self.h)

        self.text = QTextEdit()
        self.text.setStyleSheet(
            "background: transparent; border: none; color: #333; font-family: 'Segoe UI'; font-size: 16px; padding: 8px;")
        self.text.setText(txt)
        l.addWidget(self.text)

        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background: transparent;")
        l.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        self.offset = None
        self.h.mousePressEvent = lambda e: setattr(self, 'offset',
                                                   e.globalPosition().toPoint() - self.pos()) if e.button() == Qt.MouseButton.LeftButton else None
        self.h.mouseMoveEvent = lambda e: self.move(e.globalPosition().toPoint() - self.offset) if self.offset else None
        self.h.mouseReleaseEvent = lambda e: setattr(self, 'offset', None)
        self.show()

    def close_note(self):
        if self in self.tb.notes:
            self.tb.notes.remove(self)
        self.tb.save_all_notes()
        self.deleteLater()


class Header(QFrame):
    def __init__(self, tb):
        super().__init__()
        self.tb = tb
        self.setFixedHeight(60)
        self.setFixedSize(60, 60)

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet("background: #18181B; border-radius: 30px; border: 1px solid #444444;")

        self.offset = self.click_pos = None
        self.dragged = False

        self.wheel_btns = []
        self.btn_data = []

        categories = ['center', 'left', 'right']
        self.icons = ['pen', 'palette', 'folder']
        base_angles = [90, 210, 330]

        for i in range(3):
            b = QPushButton(self)
            b.setFixedSize(24, 24)
            b.setStyleSheet("background: transparent; border: none;")
            b.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            self.wheel_btns.append(b)
            self.btn_data.append(
                {'btn': b, 'base_angle': base_angles[i], 'cat': categories[i], 'icon': self.icons[i], 'idx': i})

        self.current_rotation = 0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(500)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.valueChanged.connect(self.update_positions)

        self.update_positions(0)
        self.refresh_icons('none')

    def refresh_icons(self, active_cat):
        for d in self.btn_data:
            if active_cat == 'none':
                col = "#FFFFFF"
            else:
                col = "#FFFFFF" if active_cat == d['cat'] else "#888888"
            d['btn'].setIcon(get_icon(d['icon'], col))
            d['btn'].setIconSize(QSize(18, 18))

    def on_wheel_click(self, idx):
        data = self.btn_data[idx]

        if self.tb.active_cat == data['cat']:
            self.refresh_icons('none')
            target_rot = 0
            self.tb.switch_category('none')
        else:
            self.refresh_icons(data['cat'])
            target_rot = 90 - data['base_angle']
            self.tb.switch_category(data['cat'])

        diff = (target_rot - self.current_rotation) % 360
        if diff > 180: diff -= 360

        self.anim.stop()
        self.anim.setStartValue(self.current_rotation)
        self.anim.setEndValue(self.current_rotation + diff)
        self.anim.start()

    def update_positions(self, rot):
        self.current_rotation = rot
        r = 16
        for data in self.btn_data:
            b = data['btn']
            ang_deg = (data['base_angle'] + rot) % 360
            ang_rad = math.radians(ang_deg)
            x = 30 + r * math.cos(ang_rad) - 12
            y = 30 + r * math.sin(ang_rad) - 12
            b.move(int(x), int(y))

    def mousePressEvent(self, e):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.click_pos = e.globalPosition().toPoint()
        self.offset = self.click_pos - self.tb.pos()
        self.dragged = False

    def mouseMoveEvent(self, e):
        if self.click_pos:
            if (e.globalPosition().toPoint() - self.click_pos).manhattanLength() >= 5:
                self.dragged = True
            self.tb.move(e.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        if not getattr(self, 'dragged', False):
            local_pos = e.position().toPoint()

            for d in self.btn_data:
                button_center = d['btn'].geometry().center()
                if (local_pos - button_center).manhattanLength() < 20:
                    self.on_wheel_click(d['idx'])
                    break

        if not self.click_pos or getattr(self, 'dragged', False):
            center = self.tb.geometry().center()
            idx = next((i for i, s in enumerate(QApplication.screens()) if s.geometry().contains(center)),
                       self.tb.cb.currentIndex())
            if self.tb.cb.currentIndex() != idx: self.tb.cb.setCurrentIndex(idx)

        self.click_pos = None
        self.dragged = False