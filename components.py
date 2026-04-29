import re
import html
import markdown
from PyQt6.QtWidgets import (QWidget, QPushButton, QFrame, QHBoxLayout, QVBoxLayout,
                             QLabel, QLineEdit, QTextBrowser, QApplication, QFontComboBox, QSpinBox, QColorDialog)
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat

# Assume AIWorker is available in your project
from ai_worker import AIWorker


class TextFormatBar(QFrame):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setStyleSheet("background: #2D2D2D; border-radius: 6px; border: 1px solid #555;")
        l = QHBoxLayout(self)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(8)

        self.font_cb = QFontComboBox()
        self.font_cb.setStyleSheet("background: #FFF; color: #000; border-radius: 3px; padding: 2px;")
        self.font_cb.currentFontChanged.connect(self.set_font)
        l.addWidget(self.font_cb)

        self.size_sp = QSpinBox()
        self.size_sp.setStyleSheet("background: #FFF; color: #000; border-radius: 3px; padding: 2px;")
        self.size_sp.setRange(8, 200)
        self.size_sp.setValue(24)
        self.size_sp.valueChanged.connect(self.set_size)
        l.addWidget(self.size_sp)

        self.color_btn = QPushButton("🎨 Color")
        self.color_btn.setStyleSheet(
            "background: #444; color: #FFF; font-weight: bold; border-radius: 3px; padding: 4px 10px;")
        self.color_btn.clicked.connect(self.set_color)
        l.addWidget(self.color_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setStyleSheet(
            "background: #D32F2F; color: #FFF; font-weight: bold; border-radius: 3px; padding: 4px 10px;")
        self.cancel_btn.clicked.connect(
            lambda: self.parent().cancel_text() if hasattr(self.parent(), 'cancel_text') else None)
        l.addWidget(self.cancel_btn)

        self.editor.cursorPositionChanged.connect(self.update_ui)

    def set_font(self, font):
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self.editor.textCursor().mergeCharFormat(fmt)
        self.editor.setFocus()

    def set_size(self, size):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.editor.textCursor().mergeCharFormat(fmt)
        self.editor.setFocus()

    def set_color(self):
        if (c := QColorDialog.getColor(Qt.GlobalColor.white, self)).isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(c)
            self.editor.textCursor().mergeCharFormat(fmt)
        self.editor.setFocus()

    def update_ui(self):
        fmt = self.editor.textCursor().charFormat()
        if fmt.fontPointSize() > 0:
            self.size_sp.blockSignals(True)
            self.size_sp.setValue(int(fmt.fontPointSize()))
            self.size_sp.blockSignals(False)
        self.font_cb.blockSignals(True)
        self.font_cb.setCurrentFont(fmt.font())
        self.font_cb.blockSignals(False)


class AIChatWidget(QWidget):
    def __init__(self, x, y, qimage, mode, parent_canvas, history="", log_html=""):
        super().__init__()
        self.qimage, self.mode, self.history, self.parent_canvas, self.code_blocks = qimage, mode, history, parent_canvas, {}
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(int(x), int(y), 400, 450)
        self.setStyleSheet("background: #1E1E1E; border: 2px solid #BB86FC; border-radius: 8px;")
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)

        # Header
        self.h = QFrame()
        self.h.setFixedHeight(35)
        self.h.setCursor(Qt.CursorShape.PointingHandCursor)
        self.h.setStyleSheet(
            "background: #332940; border-bottom: 1px solid #BB86FC; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        hl = QHBoxLayout(self.h)
        hl.setContentsMargins(10, 0, 10, 0)

        title = QLabel(f"✨ AI {mode} Mode")
        title.setStyleSheet("color: #BB86FC; font-weight: bold; border: none; font-size: 14px;")
        hl.addWidget(title)

        def make_btn(txt, w, col, cb):
            b = QPushButton(txt)
            b.setFixedSize(w, 22)
            b.setStyleSheet(
                f"QPushButton {{ background: {col}; color: {'#000' if col != '#444' else '#E0E0E0'}; font-weight: bold; border-radius: 4px; font-size: 11px; }}")
            b.clicked.connect(cb)
            hl.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
            return b

        make_btn("📌 Stamp", 70, "#BB86FC", self.stamp_to_canvas)
        make_btn("🧹 Clear", 60, "#444", self.clear_history)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #BB86FC; font-weight: bold; font-size: 16px; } QPushButton:hover { color: red; }")
        close_btn.clicked.connect(self.deleteLater)
        hl.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
        l.addWidget(self.h)

        self.chat_log = QTextBrowser()
        self.chat_log.setReadOnly(True)
        self.chat_log.setOpenLinks(False)
        self.chat_log.anchorClicked.connect(self.handle_link_click)
        self.chat_log.setStyleSheet(
            "background: transparent; border: none; color: #E0E0E0; font-family: 'Segoe UI'; font-size: 14px; padding: 10px;")
        l.addWidget(self.chat_log)

        input_frame = QFrame()
        input_frame.setStyleSheet(
            "background: #2D2D2D; border-top: 1px solid #555; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        il = QHBoxLayout(input_frame)
        il.setContentsMargins(10, 10, 10, 10)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask a follow-up question...")
        self.input_box.setStyleSheet(
            "background: #1E1E1E; color: #FFF; border: 1px solid #555; border-radius: 4px; padding: 8px; font-size: 14px;")
        self.input_box.returnPressed.connect(self.send_message)
        il.addWidget(self.input_box)

        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(
            "background: #BB86FC; color: #000; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.send_btn.clicked.connect(self.send_message)
        il.addWidget(self.send_btn)
        l.addWidget(input_frame)

        self.offset = None
        self.h.mousePressEvent = lambda e: setattr(self, 'offset',
                                                   e.globalPosition().toPoint() - self.pos()) if e.button() == Qt.MouseButton.LeftButton else None
        self.h.mouseMoveEvent = lambda e: self.move(e.globalPosition().toPoint() - self.offset) if self.offset else None
        self.h.mouseReleaseEvent = lambda e: setattr(self, 'offset', None)

        self.show()
        if log_html:
            self.chat_log.setHtml(log_html)
        else:
            self.input_box.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.input_box.setPlaceholderText("🧠 Thinking... Analyzing image...")
            self.worker = AIWorker(self.qimage, self.mode)
            self.worker.finished.connect(self.on_reply)
            self.worker.error.connect(self.on_error)
            self.worker.start()

    def stamp_to_canvas(self):
        pixmap = self.grab()
        local_pos = self.parent_canvas.mapFromGlobal(self.pos())

        # Pull the helper from parent to keep math clean!
        logical_pos = self.parent_canvas.get_logical_pt(local_pos)
        logical_w = float(self.width()) / float(self.parent_canvas.scale)
        logical_h = float(self.height()) / float(self.parent_canvas.scale)

        s = {'type': 'image', 'pixmap': pixmap, 'rect': QRectF(logical_pos.x(), logical_pos.y(), logical_w, logical_h),
             'c': '#BB86FC', 'is_ai_stamp': True, 'ai_history': self.history, 'ai_qimage': self.qimage,
             'ai_mode': self.mode, 'ai_log_html': self.chat_log.toHtml()}
        self.parent_canvas.strokes.append(s)
        self.parent_canvas.add_undo({'t': 'add', 's': s})
        self.parent_canvas.active_img = s
        self.parent_canvas.tb.set_tool('lasso')
        self.parent_canvas.update()
        self.deleteLater()

    def append_message(self, sender, text, color="#BB86FC"):
        self.history += f"{sender}: {text}\n"
        md_html = markdown.markdown(text, extensions=['fenced_code', 'tables', 'nl2br'])

        def code_replacer(match):
            clean_code = html.unescape(match.group(1)).strip()
            block_id = str(len(self.code_blocks))
            self.code_blocks[block_id] = clean_code
            header = f"<div style='background:#282828; padding:5px 10px; border-bottom:1px solid #444; text-align:right;'><a href='copy:{block_id}' style='color:#BB86FC; text-decoration:none; font-weight:bold; font-size:12px;'>📋 Copy Code</a></div>"
            body = f"<div style='background:#121212; padding:10px;'><pre style='color:#569CD6; font-family:Consolas, monospace; margin:0;'>{match.group(1)}</pre></div>"
            return f"<div style='border:1px solid #444; border-radius:5px; margin:10px 0;'>{header}{body}</div>"

        md_html = re.sub(r'<pre><code.*?>(.*?)</code></pre>', code_replacer, md_html, flags=re.DOTALL)
        md_html = re.sub(r'<code>(.*?)</code>',
                         r"<code style='background-color:#2D2D2D; color:#CE9178; font-family:Consolas, monospace;'>\1</code>",
                         md_html)
        self.chat_log.append(
            f"<div style='margin-bottom: 10px;'><b style='color: {color}; font-size: 15px;'>{sender}:</b><br><div style='color: #E0E0E0; font-family: \"Segoe UI\", sans-serif; font-size: 14px;'>{md_html}</div></div>")

    def handle_link_click(self, url):
        if url.scheme() == "copy" and (bid := url.path()) in self.code_blocks:
            QApplication.clipboard().setText(self.code_blocks[bid])
            self.input_box.setPlaceholderText("✅ Code copied!")
            QTimer.singleShot(2000, lambda: self.input_box.setPlaceholderText("Ask a follow-up question..."))

    def send_message(self):
        if not (q := self.input_box.text().strip()): return
        self.append_message("You", q, color="#4CAF50")
        self.input_box.clear()
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.worker = AIWorker(self.qimage, self.mode, self.history, q)
        self.worker.finished.connect(self.on_reply)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_reply(self, text):
        self.append_message("AI", text)
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setFocus()

    def on_error(self, err):
        self.append_message("System Error", err, color="red")
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)

    def clear_history(self):
        self.history = ""
        self.code_blocks.clear()
        self.chat_log.clear()
        self.chat_log.append(
            "<div style='text-align:center; color:#888; font-style:italic; font-size:12px; margin-top:10px;'>Chat history cleared.</div>")