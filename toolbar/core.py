# 1. Standard Library Imports
import sys
import os
import time
import math

# 2. Third-Party Library Imports
import keyboard
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QComboBox,
                             QPushButton, QSystemTrayIcon, QMenu, QVBoxLayout)
from PyQt6.QtGui import (QColor, QKeySequence, QShortcut, QPainter, QPixmap,
                         QPainterPath, QPolygonF, QCursor, QBrush,
                         QRadialGradient, QLinearGradient, QPen)
from PyQt6.QtCore import Qt, QRect, QSize, QTimer, QPropertyAnimation, pyqtSignal, QObject, QPointF, QPoint

# 3. Local Application Imports
from windows import MiniBoard, LoadWindow, AIWindow
from utils import B
from storage import save_sticky_notes, load_sticky_notes
from .icons import get_icon
from .components import ColorRing, Popup, HoverButton, ShapeTrigger, StickyNote, Header


class GlobalSignals(QObject):
    change_tool = pyqtSignal(str)
    change_screen = pyqtSignal(int)
    toggle_visibility = pyqtSignal()


class Toolbar(QWidget):
    def __init__(self, c):
        super().__init__(c)
        self.c = c
        self.c.tb = self
        self.active = c
        self.tool = 'cursor'
        self.last_pen_tool = 'pen'
        self.col = QColor('#FF4B4B')
        self.w = 5
        self.boards = []
        self.notes = []

        self.active_cat = 'none'
        self.is_minimized = True
        self.shapes_expanded = False

        self.bg_stretch_down = 0
        self.bg_stretch_up = 0
        self.target_stretch_down = 0
        self.target_stretch_up = 0
        self.deploy_dir = 1

        self.current_ai_mode = "Solve"

        self.sound_enabled = True
        self.ui_bg_col = "#1E1E1E"
        self.ui_fg = "#FFFFFF"
        self.ui_btn_bg = "#000000"
        self.bg_pattern = "none"

        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setGeometry(100, 100, 60, 90)

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.finished.connect(lambda: self.body.setVisible(not self.is_minimized))

        self.tray = QSystemTrayIcon(get_icon('pen', '#007ACC'), self)
        self.tray.setToolTip("ScreenDraw")
        tm = QMenu()
        tm.setStyleSheet(
            "QMenu{background:#2D2D2D; color:#DDD; border:1px solid #444} QMenu::item{padding:8px 20px} QMenu::item:selected{background:#007ACC; color:white}")

        # --- NEW: Add the Hide/Show button and a divider line ---
        tm.addAction("Hide / Show App", self.toggle_canvas)
        tm.addSeparator()

        tm.addAction("Quit App", sys.exit)
        self.tray.setContextMenu(tm)
        self.tray.show()

        # --- BONUS: Double-click the tray icon to quickly show/hide ---
        self.tray.activated.connect(
            lambda reason: self.toggle_canvas() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)

        self.cb = QComboBox(self)
        self.cb.addItems([str(i + 1) for i in range(len(QApplication.screens()))])
        self.cb.currentIndexChanged.connect(self.set_screen)
        self.cb.setStyleSheet(
            "QComboBox { background: #000; color: #FFF; border: 1px solid #444; border-radius: 12px; padding-left: 14px; font-weight: bold; font-size: 12px; } QComboBox::drop-down { border: none; }")
        self.cb.setToolTip("Current Monitor")
        self.cb.setCursor(Qt.CursorShape.PointingHandCursor)

        self.header = Header(self)
        self.header.setParent(self)

        # --- THE FIX: Force the Header to treat double-clicks exactly like a normal click ---
        self.header.mouseDoubleClickEvent = self.header.mousePressEvent

        self.size_badge = QLabel(str(self.w), self)
        self.size_badge.setFixedSize(22, 22)
        self.size_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_badge.setStyleSheet(
            "background: #1E1E1E; color: #FFF; border-radius: 11px; border: 2px solid #007ACC; font-weight: bold; font-size: 11px; font-family: 'Segoe UI';")
        self.size_badge.show()

        self.body = QWidget()
        self.body.setParent(self)
        self.body.paintEvent = self.paint_bg
        self.body.hide()

        def make_btn(icon, tip, cb=None):
            b = QPushButton()
            b.setFixedSize(36, 36)
            b.setToolTip(tip)
            b.setProperty("icon_name", icon)
            if cb:
                b.clicked.connect(cb)
            return b

        def make_emoji_btn(emoji, tip, cb, size=36):
            b = QPushButton(emoji)
            b.setFixedSize(size, size)
            b.setToolTip(tip)
            rad = size // 2
            b.setStyleSheet(
                f"background: #000; color: #FFF; font-size: 16px; border-radius: {rad}px; border: 1px solid #444; font-weight: bold;")
            b.clicked.connect(cb)
            return b

        # LEFT BUTTONS
        self.btn_snd = make_btn('sound', 'Toggle Sound', self.toggle_sound)

        self.bg_menu = Popup(self)
        for p in ['none', 'grid', 'dots']:
            b = B(f" 🖼️ Canvas: {p.title()}",
                  lambda *_, pat=p: (setattr(self, 'bg_pattern', pat), self.c.update(), self.bg_menu.hide()),
                  style="color:#DDD; border:none; font-size:14px; text-align:left; padding-left:10px")
            self.bg_menu.layout.addWidget(b)

        self.hb_bg = HoverButton("palette", self.bg_menu, self, "Canvas Pattern")
        self.btn_focus = make_btn('focus', 'Focus Last Edit',
                                  lambda *_: getattr(self.safe_active, 'jump_to_last_edit', lambda: None)())

        self.btn_keys = make_emoji_btn("!", "Keyboard Shortcuts", self.show_shortcuts)
        self.btn_del = make_emoji_btn("🗑️", "Clear Canvas", lambda *_: self.safe_active.delete_all())
        self.btn_del.setStyleSheet(
            "background: #000; color: #FF4B4B; font-size: 16px; border-radius: 18px; border: 1px solid #FF4B4B;")

        self.left_btns = [self.btn_snd, self.hb_bg, self.btn_focus, self.btn_keys, self.btn_del]

        # CENTER BUTTONS
        def pen_click(*_):
            self.set_tool('cursor' if self.tool in ['pen', 'laser', 'highlighter'] else self.last_pen_tool)

        self.btn_pen = QPushButton()
        self.btn_pen.setFixedSize(36, 36)
        self.btn_pen.setCheckable(True)
        self.btn_pen.setToolTip('Draw (P: Pen, H: Highlighter, L: Laser)')
        self.btn_pen.setProperty("icon_name", "pen")
        self.btn_pen.clicked.connect(pen_click)

        self.color_ring = ColorRing(self)
        self.col_btn = B("",
                         lambda *_: self.color_ring.show_ring(self.col_btn.mapToGlobal(self.col_btn.rect().center())),
                         size=QSize(36, 36),
                         style=f"background:{self.col.name()}; border-radius:18px; border:2px solid #555")

        self.btn_shapes = ShapeTrigger('shapes', self)

        self.ai_menu = Popup(self)
        for mode in ["Solve", "Tutor", "Debug"]:
            b = B(f" ✨ {mode}",
                  lambda *_, m=mode: (setattr(self, 'current_ai_mode', m), self.set_tool('ai_scanner'),
                                      self.ai_menu.hide()),
                  style="color:#DDD; border:none; font-size:14px; text-align:left; padding-left:10px")
            self.ai_menu.layout.addWidget(b)

        self.hb_ai = HoverButton("ai_scanner", self.ai_menu, self, "✨ AI Scanner")

        self.center_btns = [self.btn_pen, self.col_btn, self.btn_shapes, self.hb_ai]

        self.hover_btns = [self.hb_bg, self.hb_ai]

        # SHAPE BUTTONS
        self.shape_btns = []
        for i, m, tip in [('⬜', 'rect', 'Rect'), ('◯', 'circle', 'Circle'), ('╱', 'line', 'Line'),
                          ('➔', 'arrow', 'Arrow'), ('T', 'text', 'Text Tool')]:
            b = make_emoji_btn(i, tip, lambda *_, tool=m: self.set_tool(tool), size=32)
            self.shape_btns.append(b)

        # RIGHT BUTTONS
        self.btn_new = make_emoji_btn("🪟", "New Window", lambda *_: self.add_board('new'))
        self.btn_save = make_emoji_btn("💾", "Save Board", self.save_current_board)
        self.btn_note = make_emoji_btn("📝", "New Sticky Note", self.spawn_note)
        self.btn_load = make_emoji_btn("📂", "Load Saved", self.toggle_load_window)

        self.right_btns = [self.btn_new, self.btn_save, self.btn_note, self.btn_load]

        # INITIALIZE ALL POSITIONS
        all_buttons = self.left_btns + self.center_btns + self.right_btns + self.shape_btns
        for b in all_buttons:
            b.setParent(self.body)
            b.hide()
            b.phys_target = QRect(0, 0, 36, 36)
            b.phys_open = False
            b.phys_delay = time.time()

        for b in self.center_btns:
            b.raise_()

        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.check_shape_hover)
        self.hover_timer.start(100)

        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self.apply_fluid_physics)
        self.physics_timer.start(16)

        self.glass_texture_brush = self.generate_glass_texture()

        self.refresh()

        for k, cb in [
            ("Esc", lambda *_: self.set_tool('cursor')),
            ("Ctrl+S", self.save_current_board),
            ("Ctrl+Z", lambda *_: self.safe_active.undo_last()),
            ("Backspace", lambda *_: getattr(self.safe_active, 'delete_selected', self.safe_active.delete_all)()),
            ("Delete", lambda *_: getattr(self.safe_active, 'delete_selected', self.safe_active.delete_all)()),
            ("Ctrl+V", lambda *_: getattr(self.safe_active, 'paste_image', lambda: None)()),
            ("P", lambda *_: self.set_tool('pen')), ("p", lambda *_: self.set_tool('pen')),
            ("L", lambda *_: self.set_tool('laser')), ("l", lambda *_: self.set_tool('laser')),
            ("H", lambda *_: self.set_tool('highlighter')), ("h", lambda *_: self.set_tool('highlighter'))
        ]:
            QShortcut(QKeySequence(k), self).activated.connect(cb)
            QShortcut(QKeySequence(k), self, context=Qt.ShortcutContext.ApplicationShortcut).activated.connect(cb)

        self.gs = GlobalSignals()
        self.gs.change_tool.connect(self.set_tool)
        self.gs.change_screen.connect(self.cycle_screen)
        self.gs.toggle_visibility.connect(self.toggle_canvas)

        try:
            keyboard.add_hotkey('alt+h', lambda: self.gs.toggle_visibility.emit())
            keyboard.add_hotkey('alt+1', lambda: self.gs.change_tool.emit('pen'))
            keyboard.add_hotkey('ctrl+alt+1', lambda: self.gs.change_tool.emit('laser'))
            keyboard.add_hotkey('ctrl+alt+2', lambda: self.gs.change_tool.emit('highlighter'))
            keyboard.add_hotkey('alt+a', lambda: self.gs.change_tool.emit('ai_scanner'))
            [keyboard.add_hotkey(f'alt+{k}', lambda v=v: self.gs.change_tool.emit(v)) for k, v in
             {'2': 'eraser', '3': 'lasso', '4': 'rect', '5': 'circle', '6': 'line', '7': 'arrow', 't': 'text',
              'q': 'cursor'}.items()]
        except Exception:
            pass

        idx = next((i for i, s in enumerate(QApplication.screens()) if s.geometry().contains(QCursor.pos())), 0)
        self.cb.setCurrentIndex(idx)
        self.set_screen(idx)

        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_all_notes)
        self.save_timer.start(3000)

    # --- THE FIX: Swallow rogue double clicks on the transparent toolbar background ---
    def mouseDoubleClickEvent(self, e):
        e.accept()

    @property
    def safe_active(self):
        try:
            self.active.objectName()
            return self.active
        except RuntimeError:
            self.active = self.c
            return self.c

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.btn_snd.setProperty("icon_name", "sound" if self.sound_enabled else "mute")
        self.refresh()

    def generate_glass_texture(self):
        import random
        tile_size = 400
        px = QPixmap(tile_size, tile_size)
        px.fill(Qt.GlobalColor.transparent)

        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        base_color = QColor(100, 100, 100)
        base_color.setAlpha(12)

        for _ in range(12):
            smudge_size = random.randint(50, tile_size // 2)
            path = QPainterPath()
            points = []
            num_points = 8
            sx, sy = random.randint(0, tile_size), random.randint(0, tile_size)

            for i in range(num_points):
                ang = (360 / num_points) * i
                rad = smudge_size / 2.0 + random.uniform(-smudge_size / 4.0, smudge_size / 4.0)
                px_pt = sx + rad * math.cos(math.radians(ang))
                py_pt = sy + rad * math.sin(math.radians(ang))
                points.append(QPointF(px_pt, py_pt))

            path.moveTo(points[0])
            for i in range(1, num_points):
                path.lineTo(points[i])
            path.closeSubpath()
            p.fillPath(path, QBrush(base_color))

        for _ in range(3):
            sx, sy = random.randint(0, tile_size), random.randint(0, tile_size)
            rad_sz = random.randint(tile_size // 4, tile_size // 2)
            g = QRadialGradient(QPointF(sx, sy), rad_sz)
            g.setColorAt(0, QColor(120, 120, 120, 10))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(sx, sy), rad_sz, rad_sz)

        p.end()
        return QBrush(px)

    def update_width_display(self):
        if hasattr(self, 'size_badge'):
            self.size_badge.setText(str(self.w))

    def shrink_window(self):
        if self.active_cat == 'none':
            self.body.hide()
            if self.width() > 100:
                self.setGeometry(self.x() + 470, self.y() + 440, 60, 90)

    def switch_category(self, cat):
        if self.active_cat == cat:
            return

        self.active_cat = cat
        self.shapes_expanded = False
        cx, cy = 500, 500

        if cat != 'none':
            self.is_minimized = False
            if self.width() < 100:
                self.setGeometry(self.x() - 470, self.y() - 440, 1000, 1000)
            self.body.show()
        else:
            self.is_minimized = True
            QTimer.singleShot(400, self.shrink_window)

        lines_map = {
            'left': self.left_btns,
            'center': self.center_btns,
            'right': self.right_btns
        }

        for key, btns in lines_map.items():
            is_active = (key == cat)
            for i, b in enumerate(btns):
                w = b.width()
                if is_active:
                    if not b.phys_open:
                        b.move(cx - w // 2, cy - 18)
                    self.shoot_btn(b, b.phys_target, True, i * 40)
                else:
                    target_rect = QRect(cx - w // 2, cy - 18, w, 36)
                    if b.phys_open:
                        dist = abs(b.y() - cy) / 50.0
                        self.shoot_btn(b, target_rect, False, dist * 40)
                    else:
                        self.shoot_btn(b, target_rect, False, 0)

        for sb in self.shape_btns:
            target_rect = QRect(cx - 16, cy - 18, 32, 32)
            if sb.phys_open:
                dist = abs(sb.y() - cy) / 50.0
                self.shoot_btn(sb, target_rect, False, dist * 40)
            else:
                self.shoot_btn(sb, target_rect, False, 0)

    def apply_fluid_physics(self):
        cur_time = time.time()
        cx, cy = 500, 500
        d = 50

        if self.active_cat != 'none':
            btns = []
            if self.active_cat == 'left':
                btns = self.left_btns
            elif self.active_cat == 'right':
                btns = self.right_btns
            elif self.active_cat == 'center':
                btns = self.center_btns

            global_cy = self.y() + cy
            screen_bottom = self.screen().availableGeometry().bottom() - 20

            normal = []
            wrapped = []

            for b in btns:
                est_y = global_cy + (len(normal) + 1) * d
                if est_y + 36 > screen_bottom:
                    wrapped.append(b)
                else:
                    normal.append(b)

            for i, b in enumerate(normal):
                b.phys_target = QRect(cx - b.width() // 2, cy + (i + 1) * d - 18, b.width(), 36)

            for i, b in enumerate(wrapped):
                up_idx = len(wrapped) - i
                b.phys_target = QRect(cx - b.width() // 2, cy - (up_idx * d) - 18 - 40, b.width(), 36)

            self.target_stretch_down = len(normal) * d + 10 if normal else 0
            self.target_stretch_up = len(wrapped) * d + 10 + 40 if wrapped else 0
        else:
            self.target_stretch_down = 0
            self.target_stretch_up = 0

        self.bg_stretch_down += (self.target_stretch_down - self.bg_stretch_down) * 0.2
        self.bg_stretch_up += (self.target_stretch_up - self.bg_stretch_up) * 0.2
        self.body.update()

        if self.active_cat == 'center':
            for i, sb in enumerate(self.shape_btns):
                if self.shapes_expanded:
                    sb.phys_target = QRect(self.btn_shapes.x() + 45 * (i + 1), self.btn_shapes.y() + 2, 32, 32)
                else:
                    if not sb.phys_open:
                        sb.phys_target = QRect(self.btn_shapes.x() + 2, self.btn_shapes.y() + 2, 32, 32)

        all_lines = [self.left_btns, self.center_btns, self.right_btns, self.shape_btns]
        for btns in all_lines:
            for b in btns:
                if not hasattr(b, 'phys_target') or cur_time < b.phys_delay:
                    continue

                tx, ty = b.phys_target.x(), b.phys_target.y()
                nx = b.x() + (tx - b.x()) * 0.25
                ny = b.y() + (ty - b.y()) * 0.25

                if abs(tx - nx) < 1: nx = tx
                if abs(ty - ny) < 1: ny = ty

                b.move(int(nx), int(ny))

                if not b.phys_open and abs(tx - nx) <= 1 and abs(ty - ny) <= 1:
                    b.hide()

    def check_shape_hover(self):
        if not self.shapes_expanded:
            return

        pos = self.mapFromGlobal(QCursor.pos())
        bx = self.btn_shapes.x()
        by = self.btn_shapes.y()

        if pos.x() < bx - 20 or pos.x() > bx + 260 or pos.y() < by - 20 or pos.y() > by + 50:
            self.set_shapes_expanded(False)

    def set_shapes_expanded(self, state):
        if self.shapes_expanded == state:
            return
        self.shapes_expanded = state

        if self.active_cat != 'center':
            return

        self.btn_shapes.raise_()

        if state:
            sx, sy = self.btn_shapes.x() + 2, self.btn_shapes.y() + 2
            for i, sb in enumerate(self.shape_btns):
                if not sb.phys_open:
                    sb.move(sx, sy)
                self.shoot_btn(sb, QRect(self.btn_shapes.x() + 45 * (i + 1), self.btn_shapes.y() + 2, 32, 32), True,
                               i * 20)
        else:
            for i, sb in enumerate(self.shape_btns):
                self.shoot_btn(sb, QRect(self.btn_shapes.x() + 2, self.btn_shapes.y() + 2, 32, 32), False, 0)

    def shoot_btn(self, btn, target_rect, open_state, delay):
        if open_state:
            btn.phys_delay = time.time() + (delay / 1000.0)
        else:
            btn.phys_target = target_rect
            btn.phys_delay = time.time() + (delay / 1000.0)

        btn.phys_open = open_state
        if open_state:
            btn.show()

    def resizeEvent(self, e):
        w, h = self.width(), self.height()

        if h > 100:
            cx, cy = 500, 500
        else:
            cx, cy = 30, 60

        self.cb.setGeometry(cx - 20, cy - 48, 40, 24)
        self.header.setGeometry(cx - 30, cy - 30, 60, 60)
        self.size_badge.setGeometry(cx + 12, cy - 40, 22, 22)
        self.body.setGeometry(0, 0, w, h)

        self.cb.raise_()
        self.header.raise_()
        self.size_badge.raise_()

    def toggle_canvas(self, *_):
        state = not self.c.isVisible()

        # --- NEW: If we are showing the app, instantly snap the toolbar to the center of the screen ---
        if state:
            screens = QApplication.screens()
            idx = self.cb.currentIndex()
            if 0 <= idx < len(screens):
                s = screens[idx]
                cx = s.geometry().center().x()
                cy = s.geometry().center().y()
                # Center it perfectly based on its current size (whether expanded or minimized)
                self.move(int(cx - self.width() / 2), int(cy - self.height() / 2))

        self.c.setVisible(state)
        self.setVisible(state)
        for b in self.boards:
            b.setVisible(state)
        for n in self.notes:
            n.setVisible(state)

    def cycle_screen(self, direction):
        ts = len(QApplication.screens())
        if ts > 1:
            self.cb.setCurrentIndex((self.cb.currentIndex() + direction) % ts)

    def set_screen(self, i, *_):
        if i < len(QApplication.screens()):
            s = QApplication.screens()[i]
            self.c.showNormal()
            self.c.setScreen(s)
            self.c.setGeometry(s.geometry())
            self.c.showFullScreen()
            if not s.geometry().contains(self.geometry().center()):
                self.move(int(s.geometry().x() + 100), int(s.geometry().y() + 100))

    def paint_bg(self, e):
        if self.width() < 100 or (self.bg_stretch_down <= 0.5 and self.bg_stretch_up <= 0.5):
            return

        qp = QPainter(self.body)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = 500, 500

        def draw_sheet(stretch, dir_mult):
            path = QPainterPath()
            points_left = []
            points_right = []

            steps = max(10, int(stretch / 3.0))

            for i in range(steps + 1):
                t = i / float(steps)
                y = cy + (stretch * t) * dir_mult
                if i == 0:
                    y = cy

                dist_from_top = stretch * t
                if dist_from_top < 15:
                    base_r = 28 + (4 * (dist_from_top / 15.0))
                else:
                    base_r = 32

                dist_to_tip = stretch - (stretch * t)
                if dist_to_tip < 40:
                    taper_factor = (dist_to_tip / 40.0) ** 0.8
                    r = base_r * taper_factor
                else:
                    r = base_r

                points_left.append(QPointF(cx - r, y))
                points_right.insert(0, QPointF(cx + r, y))

            poly = QPolygonF(points_left + points_right)
            path.addPolygon(poly)

            glow = QRadialGradient(QPointF(cx, cy + (stretch / 2) * dir_mult), stretch)
            glow.setColorAt(0, QColor(0, 150, 255, 30))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            qp.fillPath(path, QBrush(glow))

            base_col = QColor(24, 24, 27, 180)
            qp.fillPath(path, QBrush(base_col))

            shine1 = QLinearGradient(QPointF(cx - 100, cy - 100 * dir_mult), QPointF(cx + 100, cy + 100 * dir_mult))
            shine1.setColorAt(0, QColor(0, 0, 0, 0))
            shine1.setColorAt(0.48, QColor(255, 255, 255, 50))
            shine1.setColorAt(0.5, QColor(255, 255, 255, 90))
            shine1.setColorAt(0.52, QColor(255, 255, 255, 50))
            shine1.setColorAt(1, QColor(0, 0, 0, 0))
            qp.fillPath(path, QBrush(shine1))

            shine2 = QLinearGradient(QPointF(cx + 40, cy - 50 * dir_mult), QPointF(cx - 40, cy + 50 * dir_mult))
            shine2.setColorAt(0.4, QColor(0, 0, 0, 0))
            shine2.setColorAt(0.5, QColor(255, 255, 255, 30))
            shine2.setColorAt(0.6, QColor(0, 0, 0, 0))
            qp.fillPath(path, QBrush(shine2))

            qp.fillPath(path, self.glass_texture_brush)

            qp.setPen(QPen(QColor(224, 247, 250, 60), 1.5))
            qp.drawPath(path)

        if self.bg_stretch_down > 1:
            draw_sheet(self.bg_stretch_down, 1)
        if self.bg_stretch_up > 1:
            draw_sheet(self.bg_stretch_up, -1)

    def set_color(self, c, *_):
        self.col = QColor(c)
        self.col_btn.setStyleSheet(f"background:{c}; border-radius:18px; border:2px solid #FFF")

        target = self.safe_active
        if target and hasattr(target, 'sel') and target.sel:
            for s in target.sel:
                s.update({'c': self.col})
            target.update()

        self.c.update_cursor()

        for b in self.boards:
            if hasattr(b, 'c'):
                b.c.update_cursor()

    def set_tool(self, t, *_):
        if t in ['pen', 'laser', 'highlighter']:
            self.last_pen_tool = t

        self.tool = 'cursor' if self.tool == t else t
        self.c.set_pass(self.tool == 'cursor')
        self.refresh()
        self.c.update_cursor()

        for b in self.boards:
            if hasattr(b, 'c'):
                b.c.update_cursor()

        if self.tool != 'cursor' and not self.c.isVisible():
            self.toggle_canvas()

        if self.tool != 'cursor':
            self.c.raise_()
            self.c.activateWindow()
            for b in self.boards:
                b.raise_()
            for n in self.notes:
                n.raise_()
            self.raise_()
            self.activateWindow()

    def refresh(self):
        self.body.update()

        for hb in self.hover_btns:
            hb.update_style()

        self.header.update()

        is_temp = self.tool in ['eraser', 'lasso']

        self.btn_pen.setChecked(self.tool in ['pen', 'laser', 'highlighter'] or is_temp)
        self.btn_pen.setProperty("icon_name", self.tool if is_temp or self.tool in ['pen', 'laser',
                                                                                    'highlighter'] else self.last_pen_tool)

        is_shape = self.tool in ['rect', 'circle', 'line', 'arrow', 'text']
        if hasattr(self, 'btn_shapes'):
            self.btn_shapes.setProperty("icon_name", self.tool if is_shape else 'shapes')

        for btn in [self.btn_snd, self.btn_focus, getattr(self, 'hb_ai', None) and self.hb_ai.b, self.btn_pen,
                    getattr(self, 'btn_shapes', None)]:
            if not btn:
                continue
            active = btn.isChecked() or (btn.property("icon_name") == self.tool) or (
                        btn == getattr(self, 'btn_shapes', None) and is_shape)
            btn.setIcon(get_icon(btn.property("icon_name"), "#FFF" if active else self.ui_fg))
            btn.setIconSize(QSize(20, 20))
            btn.setStyleSheet(
                f"QPushButton{{background:{'#007ACC' if active else '#000'}; border: 1px solid #444; border-radius:18px}} QPushButton:hover{{background:#007ACC}}")

    def add_board(self, m, strokes=None, path=None, capture=None):
        if len(self.boards) >= 10:
            return

        if m == 'ai':
            mode = getattr(self, 'current_ai_mode', 'Solve')
            if hasattr(self, 'ai_mode_cb') and self.ai_mode_cb.isVisible():
                mode = self.ai_mode_cb.currentText()
            board = AIWindow(self, mode, capture if capture else QPixmap(1, 1))
        else:
            board = MiniBoard(self, m, strokes, path)

        self.boards.append(board)

        btn_pos = self.btn_new.mapToGlobal(QPoint(0, 0))
        btn_w = self.btn_new.width()

        s = self.screen().geometry()
        bw = board.width()
        bh = board.height()

        target_x = btn_pos.x() + btn_w + 10
        target_y = btn_pos.y()

        if target_x + bw > s.right(): target_x = btn_pos.x() - bw - 10
        if target_x < s.left(): target_x = s.left() + 10
        if target_x + bw > s.right(): target_x = s.right() - bw - 10
        if target_y + bh > s.bottom(): target_y = s.bottom() - bh - 40
        if target_y < s.top(): target_y = s.top() + 10

        board.move(target_x, target_y)

        if hasattr(board, 'c'):
            board.c.update_cursor()

        board.show()
        board.raise_()

    def save_current_board(self, *_):
        import time, os
        from storage import save_board, BOARDS_DIR

        target = self.safe_active

        filepath = os.path.join(BOARDS_DIR, f"Board_{int(time.time())}.draw")
        save_board(target.strokes, getattr(target, 'bg_pattern', 'none'), filepath)
        print(f"✅ Board saved perfectly to: {filepath}")

    def save_all_notes(self):
        save_sticky_notes(
            [{'x': int(n.x()), 'y': int(n.y()), 'w': int(n.width()), 'h': int(n.height()), 'text': n.text.toPlainText()}
             for n in self.notes])

    def spawn_note(self, x=None, y=None, w=220, h=220, txt="", *_):
        s = self.screen().geometry()
        if x is None or type(x) is bool or y is None or type(y) is bool:
            btn_pos = self.btn_note.mapToGlobal(QPoint(0, 0))
            btn_w = self.btn_note.width()
            target_x = btn_pos.x() + btn_w + 10
            target_y = btn_pos.y()
            if target_x + w > s.right(): target_x = btn_pos.x() - w - 10
        else:
            target_x, target_y = float(x), float(y)

        if target_x < s.left(): target_x = s.left() + 10
        if target_x + w > s.right(): target_x = s.right() - w - 10
        if target_y + h > s.bottom(): target_y = s.bottom() - h - 40
        if target_y < s.top(): target_y = s.top() + 10

        new_note = StickyNote(self, target_x, target_y, w, h, txt)
        # --- THE FIX: Patch the Sticky Note header as well just in case! ---
        new_note.h.mouseDoubleClickEvent = new_note.h.mousePressEvent
        self.notes.append(new_note)

    def show_shortcuts(self):
        if hasattr(self, 'sc_win') and self.sc_win.isVisible():
            self.sc_win.close()
            return

        self.sc_win = QWidget()
        self.sc_win.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.sc_win.setStyleSheet("background: #1E1E1E; border: 2px solid #007ACC; border-radius: 10px; color: #FFF;")

        l = QVBoxLayout(self.sc_win)
        l.setContentsMargins(20, 20, 20, 20)

        title = QLabel("⌨️ Keyboard Shortcuts")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #007ACC; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)

        text = QLabel(
            "<b>Tools:</b><br>• <b>P</b> : Pen<br>• <b>H</b> : Highlighter<br>• <b>L</b> : Laser<br>• <b>Right-Click</b> : Eraser<br>• <b>Middle-Click</b> : Lasso Tool<br><br><b>Canvas:</b><br>• <b>Ctrl + Left Click</b> : Pan Canvas<br>• <b>Ctrl + Scroll</b> : Zoom<br><br><b>Actions:</b><br>• <b>Ctrl + Z</b> : Undo<br>• <b>Ctrl + S</b> : Save<br>• <b>Ctrl + V</b> : Paste Image<br>• <b>Delete</b> : Clear<br>• <b>Esc</b> : Select Cursor")
        text.setStyleSheet("font-size: 14px; border: none; line-height: 1.5;")
        l.addWidget(text)

        cb = QPushButton("✕ Close")
        cb.setStyleSheet(
            "background: #444; color: #FFF; font-weight: bold; border-radius: 6px; padding: 8px; border: none;")
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(self.sc_win.close)
        l.addWidget(cb)

        s = self.screen().geometry()
        self.sc_win.resize(300, 420)
        self.sc_win.move(s.center().x() - 150, s.center().y() - 210)
        self.sc_win.show()

    def toggle_load_window(self, *_):
        try:
            if hasattr(self, 'load_win') and self.load_win and self.load_win.isVisible():
                self.load_win.close()
                self.load_win = None
                return
        except RuntimeError:
            self.load_win = None

        self.load_win = LoadWindow(self)
        btn_pos = self.btn_load.mapToGlobal(QPoint(0, 0))
        btn_w = self.btn_load.width()
        s = self.screen().geometry()
        lw_w = self.load_win.width()
        lw_h = self.load_win.height()

        target_x = btn_pos.x() + btn_w + 10
        target_y = btn_pos.y()

        if target_x + lw_w > s.right(): target_x = btn_pos.x() - lw_w - 10
        if target_x < s.left(): target_x = btn_pos.x() + btn_w + 10
        if target_y + lw_h > s.bottom(): target_y = s.bottom() - lw_h - 10

        self.load_win.move(target_x, target_y)
        self.load_win.show()
        self.load_win.raise_()