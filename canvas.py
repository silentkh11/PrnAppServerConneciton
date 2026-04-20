import math
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QPolygonF, QCursor, QPainterPathStroker, QPixmap, \
    QPolygon, QEnterEvent, QShortcut, QKeySequence, QDrag
from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint, QRect, QMimeData, QByteArray


class CanvasWidget(QWidget):
    global_dragged_strokes = []

    def __init__(self, tb=None, parent_board=None):
        super().__init__()
        self.tb = tb
        self.parent_board = parent_board

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setAcceptDrops(True)

        self.strokes = []
        self.current_stroke = None
        self.sel = []

        self.undo_stack = []
        self.erasing_session = False

        self.pan_x = 0
        self.pan_y = 0
        self.scale = 1.0

        self.is_panning = False
        self.last_pan_pos = None

        self.is_moving_sel = False
        self.is_resizing = False
        self.resize_edge = None
        self.move_start_pos = None

        self.cross_dragging = False
        self.cross_drag_start_pos = None
        self.cross_drag_strokes = []

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- NEW: The Smoothing Engine ---
    def build_path(self, pts):
        path = QPainterPath()
        if not pts: return path
        path.moveTo(pts[0])

        if len(pts) < 3:
            for p in pts[1:]: path.lineTo(p)
        else:
            # Draw a line to the very first midpoint
            p0, p1 = pts[0], pts[1]
            path.lineTo(QPointF((p0.x() + p1.x()) / 2, (p0.y() + p1.y()) / 2))

            # Chain quadratic curves through all the other midpoints
            for i in range(1, len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                mid = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                path.quadTo(p1, mid)

            # Finish the stroke exactly at your mouse tip
            path.lineTo(pts[-1])

        return path

    def enterEvent(self, event):
        self.setFocus()
        if hasattr(self, 'tb') and self.tb:
            self.tb.active = self
        super().enterEvent(event)

    def keyPressEvent(self, e):
        if (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_V:
            self.paste_image()
        else:
            super().keyPressEvent(e)

    def paste_image(self):
        if not self.tb or self.tb.tool == 'cursor': return

        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        pixmap = None

        if mime.hasImage():
            pixmap = clipboard.pixmap()
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        pixmap = QPixmap(path)
                        break

        if pixmap and not pixmap.isNull():
            mouse_global = QCursor.pos()
            mouse_local = self.mapFromGlobal(mouse_global)
            canvas_pos = self.map_pos(mouse_local)

            cx = canvas_pos.x()
            cy = canvas_pos.y()
            w, h = pixmap.width(), pixmap.height()

            rect = QRectF(cx - w / 2, cy - h / 2, w, h)

            self.save_state()
            self.strokes.append({
                'tool': 'image',
                'pixmap': pixmap,
                'rect': rect,
                'p': [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight(), QPointF(cx, cy)],
                'c': Qt.GlobalColor.transparent,
                'w': 0
            })
            self.sel = [self.strokes[-1]]
            self.update()

    def map_pos(self, pos):
        return QPointF((pos.x() - self.pan_x) / self.scale, (pos.y() - self.pan_y) / self.scale)

    def set_pass(self, passthrough):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, passthrough)

    def save_state(self):
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        copied_strokes = []
        for s in self.strokes:
            new_s = s.copy()
            if 'p' in new_s:
                new_s['p'] = [QPointF(pt.x(), pt.y()) for pt in new_s['p']]
            if 'rect' in new_s:
                new_s['rect'] = QRectF(new_s['rect'])
            copied_strokes.append(new_s)
        self.undo_stack.append(copied_strokes)

    def undo_last(self):
        if self.undo_stack:
            self.strokes = self.undo_stack.pop()
            self.sel.clear()
            self.update()

    def update_cursor(self, force_tool=None):
        if not hasattr(self, 'tb') or not self.tb: return
        t = force_tool if force_tool else self.tb.tool

        if t == 'cursor':
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif t == 'eraser':
            pm = QPixmap(24, 24);
            pm.fill(Qt.GlobalColor.transparent);
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing);
            qp.setPen(QPen(QColor(0, 0, 0, 180), 2))
            qp.setBrush(QColor(255, 255, 255, 80));
            qp.drawEllipse(2, 2, 20, 20);
            qp.end()
            self.setCursor(QCursor(pm, 12, 12))
        elif t == 'pen':
            c = getattr(self.tb, 'col', QColor('#FF4B4B'))
            pm = QPixmap(32, 32);
            pm.fill(Qt.GlobalColor.transparent);
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.setPen(QPen(QColor("#999"), 1));
            qp.setBrush(QColor(c))
            qp.drawPolygon(QPolygon([QPoint(0, 0), QPoint(8, 2), QPoint(2, 8)]))
            qp.setPen(QPen(QColor("#3E2723"), 1));
            qp.setBrush(QColor("#795548"))
            qp.drawPolygon(QPolygon([QPoint(2, 8), QPoint(8, 2), QPoint(20, 14), QPoint(14, 20)]))
            qp.setBrush(QColor("#3E2723"));
            qp.drawPolygon(QPolygon([QPoint(14, 20), QPoint(20, 14), QPoint(24, 18), QPoint(18, 24)]))
            qp.end();
            self.setCursor(QCursor(pm, 0, 0))
        elif t in ['laser', 'highlighter', 'ai_scanner']:
            color = QColor("#BB86FC") if t == 'ai_scanner' else getattr(self.tb, 'col', QColor('#FF4B4B'))
            pm = QPixmap(16, 16);
            pm.fill(Qt.GlobalColor.transparent);
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing);
            qp.setPen(QPen(QColor(255, 255, 255, 255), 2))
            qp.setBrush(QColor(color));
            qp.drawEllipse(3, 3, 10, 10);
            qp.end()
            self.setCursor(QCursor(pm, 8, 8))
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def delete_all(self):
        if self.strokes:
            self.save_state()
            self.strokes.clear();
            self.sel.clear();
            self.update()

    def delete_selected(self):
        if self.sel:
            self.save_state()
            for s in self.sel:
                if s in self.strokes: self.strokes.remove(s)
            self.sel.clear();
            self.update()
        else:
            self.delete_all()

    def jump_to_last_edit(self):
        if not self.strokes: return
        last_point = self.strokes[-1]['p'][-1]
        self.pan_x = (self.width() / 2) - (last_point.x() * self.scale)
        self.pan_y = (self.height() / 2) - (last_point.y() * self.scale)
        self.update()

    def get_selection_bounding_rect(self):
        if not self.sel: return QRectF()
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        for s in self.sel:
            if s.get('tool') == 'image':
                r = s['rect']
                min_x, min_y = min(min_x, r.left()), min(min_y, r.top())
                max_x, max_y = max(max_x, r.right()), max(max_y, r.bottom())
            else:
                for p in s.get('p', []):
                    min_x, min_y = min(min_x, p.x()), min(min_y, p.y())
                    max_x, max_y = max(max_x, p.x()), max(max_y, p.y())
        return QRectF(min_x - 10, min_y - 10, max_x - min_x + 20, max_y - min_y + 20)

    def get_image_handles(self, rect):
        sze = 12 / self.scale
        return {
            'tl': QRectF(rect.left() - sze / 2, rect.top() - sze / 2, sze, sze),
            'tr': QRectF(rect.right() - sze / 2, rect.top() - sze / 2, sze, sze),
            'bl': QRectF(rect.left() - sze / 2, rect.bottom() - sze / 2, sze, sze),
            'br': QRectF(rect.right() - sze / 2, rect.bottom() - sze / 2, sze, sze)
        }

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-screendraw-stroke"):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasFormat("application/x-screendraw-stroke"):
            drop_pos = self.map_pos(e.position())

            if hasattr(CanvasWidget, 'global_dragged_strokes') and CanvasWidget.global_dragged_strokes:
                self.save_state()

                for s in CanvasWidget.global_dragged_strokes:
                    new_s = s.copy()
                    if new_s.get('tool') == 'image':
                        new_s['rect'] = QRectF(new_s['rect'])
                        new_s['rect'].translate(drop_pos.x(), drop_pos.y())

                    if 'p' in new_s:
                        new_s['p'] = [QPointF(pt.x() + drop_pos.x(), pt.y() + drop_pos.y()) for pt in new_s['p']]

                    self.strokes.append(new_s)

                self.sel = []
                self.update()

            e.acceptProposedAction()

    def wheelEvent(self, e):
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier:
            old_scale = self.scale
            self.scale *= 1.1 if e.angleDelta().y() > 0 else 0.9
            self.scale = max(0.1, min(self.scale, 10.0))
            m = e.position()
            self.pan_x = m.x() - (m.x() - self.pan_x) * (self.scale / old_scale)
            self.pan_y = m.y() - (m.y() - self.pan_y) * (self.scale / old_scale)
            self.update()
        else:
            if hasattr(self, 'tb') and self.tb:
                drawing_tools = ['pen', 'highlighter', 'laser', 'eraser', 'rect', 'circle', 'line', 'arrow']

                if self.tb.tool in drawing_tools:
                    if e.angleDelta().y() > 0:
                        self.tb.w = min(50, self.tb.w + 1)
                    else:
                        self.tb.w = max(1, self.tb.w - 1)

                    self.tb.update_width_display()
                    self.update()

    def mousePressEvent(self, e):
        self.setFocus()

        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier and e.button() == Qt.MouseButton.LeftButton:
            pos = self.map_pos(e.position())

            clicked_item = None
            hit_rect = QRectF(pos.x() - 8 / self.scale, pos.y() - 8 / self.scale, 16 / self.scale, 16 / self.scale)

            for s in reversed(self.strokes):
                if s.get('tool') == 'image':
                    if s['rect'].contains(pos):
                        clicked_item = s
                        break
                elif s.get('p'):
                    path = QPainterPath()
                    if s['tool'] == 'rect' and len(s['p']) > 1:
                        path.addRect(QRectF(s['p'][0], s['p'][-1]))
                    elif s['tool'] == 'circle' and len(s['p']) > 1:
                        p1, p2 = s['p'][0], s['p'][-1]
                        r = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
                        path.addEllipse(p1, r, r)
                    elif s['tool'] in ['line', 'arrow'] and len(s['p']) > 1:
                        path.moveTo(s['p'][0])
                        path.lineTo(s['p'][-1])
                    else:
                        path = self.build_path(s['p'])

                    stk = QPainterPathStroker()
                    stk.setWidth(s.get('w', 4) + 15)
                    if stk.createStroke(path).intersects(hit_rect):
                        clicked_item = s
                        break

            if clicked_item:
                self.cross_dragging = True
                self.cross_drag_start_pos = pos

                if clicked_item in self.sel:
                    self.cross_drag_strokes = self.sel.copy()
                else:
                    self.cross_drag_strokes = [clicked_item]
                return

            self.is_panning = True
            self.last_pan_pos = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if not hasattr(self, 'tb') or not self.tb or self.tb.tool == 'cursor': return
        pos = self.map_pos(e.position())

        tool = self.tb.tool

        if e.button() == Qt.MouseButton.MiddleButton:
            if self.sel:
                for s in self.sel:
                    if s.get('tool') == 'image':
                        handles = self.get_image_handles(s['rect'])
                        for edge, h_rect in handles.items():
                            if h_rect.contains(pos):
                                self.save_state()
                                self.is_resizing = True
                                self.resize_edge = edge
                                self.move_start_pos = pos
                                return

            if self.sel and self.get_selection_bounding_rect().contains(pos):
                self.save_state()
                self.is_moving_sel = True
                self.move_start_pos = pos
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

            clicked_item = None
            hit_rect = QRectF(pos.x() - 8 / self.scale, pos.y() - 8 / self.scale, 16 / self.scale, 16 / self.scale)

            for s in reversed(self.strokes):
                if s.get('tool') == 'image':
                    if s['rect'].contains(pos):
                        clicked_item = s
                        break
                elif s.get('p'):
                    path = QPainterPath()
                    if s['tool'] == 'rect' and len(s['p']) > 1:
                        path.addRect(QRectF(s['p'][0], s['p'][-1]))
                    elif s['tool'] == 'circle' and len(s['p']) > 1:
                        p1, p2 = s['p'][0], s['p'][-1]
                        r = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
                        path.addEllipse(p1, r, r)
                    elif s['tool'] in ['line', 'arrow'] and len(s['p']) > 1:
                        path.moveTo(s['p'][0])
                        path.lineTo(s['p'][-1])
                    else:
                        path = self.build_path(s['p'])

                    stk = QPainterPathStroker()
                    stk.setWidth(s.get('w', 4) + 15)
                    if stk.createStroke(path).intersects(hit_rect):
                        clicked_item = s
                        break

            if clicked_item:
                if clicked_item not in self.sel:
                    self.sel = [clicked_item]
                self.save_state()
                self.is_moving_sel = True
                self.move_start_pos = pos
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()
                return

            tool = 'lasso'

        elif e.button() == Qt.MouseButton.RightButton:
            tool = 'eraser';
            self.update_cursor(force_tool='eraser')

        if tool != 'lasso' and self.sel:
            self.sel = [];
            self.update()

        if tool == 'eraser':
            self.erasing_session = False;
            self.erase_at(pos);
            return

        self.save_state()
        self.current_stroke = {'tool': tool, 'c': self.tb.col, 'w': self.tb.w, 'p': [pos]}
        self.strokes.append(self.current_stroke);
        self.update()

    def mouseMoveEvent(self, e):
        if getattr(self, 'cross_dragging', False):
            extracted_strokes = []
            for s in self.cross_drag_strokes:
                new_s = s.copy()
                if new_s.get('tool') == 'image':
                    new_s['rect'] = QRectF(new_s['rect'])
                    new_s['rect'].translate(-self.cross_drag_start_pos.x(), -self.cross_drag_start_pos.y())
                if 'p' in new_s:
                    new_s['p'] = [
                        QPointF(pt.x() - self.cross_drag_start_pos.x(), pt.y() - self.cross_drag_start_pos.y()) for pt
                        in new_s['p']]
                extracted_strokes.append(new_s)

            CanvasWidget.global_dragged_strokes = extracted_strokes

            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            for s in extracted_strokes:
                if s.get('tool') == 'image':
                    r = s['rect']
                    min_x, min_y = min(min_x, r.left()), min(min_y, r.top())
                    max_x, max_y = max(max_x, r.right()), max(max_y, r.bottom())
                else:
                    for pt in s.get('p', []):
                        min_x, min_y = min(min_x, pt.x()), min(min_y, pt.y())
                        max_x, max_y = max(max_x, pt.x()), max(max_y, pt.y())

            min_x -= 10;
            min_y -= 10;
            max_x += 10;
            max_y += 10
            w = max(1, max_x - min_x) * self.scale
            h = max(1, max_y - min_y) * self.scale

            pm = QPixmap(int(w), int(h))
            pm.fill(Qt.GlobalColor.transparent)
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.scale(self.scale, self.scale)
            qp.translate(-min_x, -min_y)
            for s in extracted_strokes: self.draw_stroke(qp, s)
            qp.end()

            self.save_state()
            for s in self.cross_drag_strokes:
                if s in self.strokes: self.strokes.remove(s)
                if s in self.sel: self.sel.remove(s)
            self.update()

            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-screendraw-stroke", QByteArray())
            drag.setMimeData(mime)
            drag.setPixmap(pm)
            drag.setHotSpot(QPoint(int((0 - min_x) * self.scale), int((0 - min_y) * self.scale)))

            self.cross_dragging = False
            res = drag.exec(Qt.DropAction.MoveAction)

            if res == Qt.DropAction.IgnoreAction:
                self.undo_last()
            return

        if self.is_panning and self.last_pan_pos:
            delta = e.position() - self.last_pan_pos
            self.pan_x += delta.x();
            self.pan_y += delta.y()
            self.last_pan_pos = e.position();
            self.update();
            return

        if self.is_resizing and self.move_start_pos and self.sel:
            pos = self.map_pos(e.position())
            dx = pos.x() - self.move_start_pos.x()
            dy = pos.y() - self.move_start_pos.y()

            for s in self.sel:
                if s.get('tool') == 'image':
                    rect = s['rect']

                    if self.resize_edge == 'tl':
                        rect.setLeft(min(rect.left() + dx, rect.right() - 20))
                        rect.setTop(min(rect.top() + dy, rect.bottom() - 20))
                    elif self.resize_edge == 'tr':
                        rect.setRight(max(rect.right() + dx, rect.left() + 20))
                        rect.setTop(min(rect.top() + dy, rect.bottom() - 20))
                    elif self.resize_edge == 'bl':
                        rect.setLeft(min(rect.left() + dx, rect.right() - 20))
                        rect.setBottom(max(rect.bottom() + dy, rect.top() + 20))
                    elif self.resize_edge == 'br':
                        rect.setRight(max(rect.right() + dx, rect.left() + 20))
                        rect.setBottom(max(rect.bottom() + dy, rect.top() + 20))

                    s['rect'] = rect
                    s['p'] = [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight(), rect.center()]

            self.move_start_pos = pos
            self.update()
            return

        if self.is_moving_sel and self.move_start_pos:
            pos = self.map_pos(e.position())
            dx = pos.x() - self.move_start_pos.x()
            dy = pos.y() - self.move_start_pos.y()

            for s in self.sel:
                if s.get('tool') == 'image':
                    s['rect'].translate(dx, dy)
                for pt in s.get('p', []):
                    pt.setX(pt.x() + dx)
                    pt.setY(pt.y() + dy)

            self.move_start_pos = pos
            self.update()
            return

        if not self.current_stroke or not self.tb:
            if e.buttons() == Qt.MouseButton.RightButton: self.erase_at(self.map_pos(e.position()))
            return

        pos = self.map_pos(e.position())
        if self.current_stroke['tool'] in ['pen', 'highlighter', 'laser', 'lasso']:
            self.current_stroke['p'].append(pos)
        else:
            if len(self.current_stroke['p']) > 1:
                self.current_stroke['p'][1] = pos
            else:
                self.current_stroke['p'].append(pos)
        self.update()

    def mouseReleaseEvent(self, e):
        if getattr(self, 'cross_dragging', False):
            self.cross_dragging = False
            self.sel = []
            self.update()
            return

        if self.is_panning:
            self.is_panning = False;
            self.update_cursor();
            return

        if self.is_resizing:
            self.is_resizing = False
            self.resize_edge = None
            self.move_start_pos = None
            self.sel = []
            self.update_cursor()
            self.update()
            return

        if self.is_moving_sel:
            self.is_moving_sel = False
            self.move_start_pos = None
            self.sel = []
            self.update_cursor()
            self.update()
            return

        if self.current_stroke:
            t = self.current_stroke['tool']
            pts = self.current_stroke.get('p', [])

            if t == 'ai_scanner' and len(pts) > 1:
                self.strokes.remove(self.current_stroke)

                self.repaint()
                QApplication.processEvents()

                p1_widget = QPoint(
                    int((pts[0].x() * self.scale) + self.pan_x),
                    int((pts[0].y() * self.scale) + self.pan_y)
                )
                p2_widget = QPoint(
                    int((pts[-1].x() * self.scale) + self.pan_x),
                    int((pts[-1].y() * self.scale) + self.pan_y)
                )

                box_global = QRect(self.mapToGlobal(p1_widget), self.mapToGlobal(p2_widget)).normalized()

                current_screen = QApplication.screenAt(box_global.center())
                if not current_screen:
                    current_screen = QApplication.primaryScreen()

                full_screenshot = current_screen.grabWindow(0)

                screen_geo = current_screen.geometry()
                local_logical_box = QRect(
                    box_global.x() - screen_geo.x(),
                    box_global.y() - screen_geo.y(),
                    box_global.width(),
                    box_global.height()
                )

                ratio = current_screen.devicePixelRatio()
                physical_box = QRect(
                    int(local_logical_box.x() * ratio),
                    int(local_logical_box.y() * ratio),
                    int(local_logical_box.width() * ratio),
                    int(local_logical_box.height() * ratio)
                )

                capture = full_screenshot.copy(physical_box)
                capture.setDevicePixelRatio(ratio)

                if hasattr(self, 'tb') and hasattr(self.tb, 'add_board'):
                    self.tb.add_board(m='ai', capture=capture)

            elif t == 'lasso' and len(pts) > 2:
                self.strokes.remove(self.current_stroke)
                poly = QPolygonF(pts)
                self.sel = [s for s in self.strokes if
                            any(poly.containsPoint(pt, Qt.FillRule.OddEvenFill) for pt in s.get('p', []))]

        self.update_cursor();
        self.current_stroke = None;
        self.update()

    def erase_at(self, pos):
        rect = QRectF(pos.x() - 10 / self.scale, pos.y() - 10 / self.scale, 20 / self.scale, 20 / self.scale)
        to_rem = []
        for s in self.strokes:
            if s.get('tool') == 'image': continue
            if not s.get('p'): continue

            path = QPainterPath()
            if s['tool'] == 'rect' and len(s['p']) > 1:
                path.addRect(QRectF(s['p'][0], s['p'][-1]))
            elif s['tool'] == 'circle' and len(s['p']) > 1:
                p1, p2 = s['p'][0], s['p'][-1];
                r = math.hypot(p2.x() - p1.x(), p2.y() - p1.y());
                path.addEllipse(p1, r, r)
            elif s['tool'] in ['line', 'arrow'] and len(s['p']) > 1:
                path.moveTo(s['p'][0])
                path.lineTo(s['p'][-1])
            else:
                path = self.build_path(s['p'])

            stk = QPainterPathStroker();
            stk.setWidth(s['w'] + 10)
            if stk.createStroke(path).intersects(rect): to_rem.append(s)

        if to_rem:
            if not self.erasing_session: self.save_state(); self.erasing_session = True
            for s in to_rem:
                self.strokes.remove(s)
                if s in self.sel: self.sel.remove(s)
            self.update()

    def paintEvent(self, e):
        qp = QPainter(self);
        qp.setRenderHint(QPainter.RenderHint.Antialiasing);
        self.paint_strokes(qp)

    def paint_strokes(self, qp):
        qp.save();
        qp.translate(self.pan_x, self.pan_y);
        qp.scale(self.scale, self.scale)
        pat = getattr(self.tb, 'bg_pattern', 'none') if hasattr(self, 'tb') and self.tb else 'none'
        if pat != 'none':
            t, _ = qp.transform().inverted();
            r = t.mapRect(QRectF(self.rect()))
            sx, sy, ex, ey = int(r.left() // 40) * 40, int(r.top() // 40) * 40, int(r.right()) + 40, int(
                r.bottom()) + 40
            if pat == 'grid':
                qp.setPen(QPen(QColor(0, 150, 255, 50), 1));
                [qp.drawLine(x, sy, x, ey) for x in range(sx, ex, 40)];
                [qp.drawLine(sx, y, ex, y) for y in range(sy, ey, 40)]
            elif pat == 'dots':
                qp.setPen(Qt.PenStyle.NoPen);
                qp.setBrush(QColor(0, 150, 255, 70));
                [qp.drawEllipse(QPointF(x, y), 2, 2) for x in range(sx, ex, 40) for y in range(sy, ey, 40)]

        for s in self.strokes: self.draw_stroke(qp, s)
        qp.restore()

    def draw_stroke(self, qp, s):
        t, c, w = s.get('tool'), s.get('c'), s.get('w')

        if t == 'image':
            qp.drawPixmap(s['rect'].toRect(), s['pixmap'])

            if hasattr(self, 'sel') and s in self.sel and not getattr(self, 'cross_dragging', False):
                qp.setPen(QPen(QColor("#007ACC"), 2, Qt.PenStyle.DashLine))
                qp.setBrush(Qt.BrushStyle.NoBrush)
                qp.drawRect(s['rect'])

                qp.setPen(QPen(QColor("#FFF"), 1))
                qp.setBrush(QColor("#007ACC"))
                sze = 10 / self.scale
                r = s['rect']
                qp.drawRect(QRectF(r.left() - sze / 2, r.top() - sze / 2, sze, sze))
                qp.drawRect(QRectF(r.right() - sze / 2, r.top() - sze / 2, sze, sze))
                qp.drawRect(QRectF(r.left() - sze / 2, r.bottom() - sze / 2, sze, sze))
                qp.drawRect(QRectF(r.right() - sze / 2, r.bottom() - sze / 2, sze, sze))
            return

        pts = s.get('p', [])
        if not pts: return

        def trace_shape():
            if t in ['rect', 'circle', 'line', 'arrow', 'ai_scanner'] and len(pts) > 1:
                p1, p2 = pts[0], pts[-1]
                if t in ['rect', 'ai_scanner']:
                    qp.drawRect(QRectF(p1, p2))
                elif t == 'circle':
                    r = math.hypot(p2.x() - p1.x(), p2.y() - p1.y()); qp.drawEllipse(p1, r, r)
                elif t == 'line':
                    qp.drawLine(p1, p2)
                elif t == 'arrow':
                    qp.drawLine(p1, p2);
                    ang = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
                    qp.drawPolygon(QPolygonF([p2, QPointF(p2.x() - 15 * math.cos(ang - math.pi / 6),
                                                          p2.y() - 15 * math.sin(ang - math.pi / 6)),
                                              QPointF(p2.x() - 15 * math.cos(ang + math.pi / 6),
                                                      p2.y() - 15 * math.sin(ang + math.pi / 6))]))
            else:
                # --- NEW: Use the new smooth curve logic to draw the ink! ---
                path = self.build_path(pts)
                qp.drawPath(path)

        if t == 'highlighter':
            col = QColor(c);
            col.setAlpha(100);
            qp.setPen(QPen(col, w * 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.RoundJoin))
            qp.setBrush(Qt.BrushStyle.NoBrush)
        elif t in ['pen', 'laser']:
            col = QColor(c)
            if t == 'laser':
                qp.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 50), w * 3, Qt.PenStyle.SolidLine,
                               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                trace_shape()
            qp.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            qp.setBrush(Qt.BrushStyle.NoBrush)
        elif t in ['lasso', 'ai_scanner']:
            color = QColor("#BB86FC") if t == 'ai_scanner' else QColor(c)
            qp.setPen(QPen(color, 2, Qt.PenStyle.DashLine));
            qp.setBrush(QColor(color.red(), color.green(), color.blue(), 40))
        elif t in ['rect', 'circle', 'line', 'arrow']:
            qp.setPen(QPen(QColor(c), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if t == 'arrow':
                qp.setBrush(QColor(c))
            else:
                qp.setBrush(Qt.BrushStyle.NoBrush)

        trace_shape()

        if hasattr(self, 'sel') and s in self.sel and not getattr(self, 'cross_dragging', False):
            dash_w = 2 if w > 4 else 1
            dash_pen = QPen(QColor(255, 255, 255, 220), dash_w, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin)
            qp.setPen(dash_pen)
            qp.setBrush(Qt.BrushStyle.NoBrush)
            trace_shape()