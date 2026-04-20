# 1. Standard Library Imports
import os
import sys
import time
import datetime

# 2. Third-Party Library Imports
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QTextEdit, QLineEdit,
                             QComboBox, QInputDialog, QScrollArea,
                             QGridLayout, QFileDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QFont, QBrush, QLinearGradient

# 3. Local Application Imports
from ai_worker import AIWorker
from canvas import CanvasWidget
from storage import save_board, get_saved_files, load_board, rename_board, BOARDS_DIR


class Overlay(CanvasWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.passthrough = True

        self.laser_timer = QTimer(self)
        self.laser_timer.timeout.connect(self.process_laser_fade)
        self.laser_timer.start(20)

    def process_laser_fade(self):
        if not hasattr(self, 'strokes') or not self.strokes:
            return

        needs_update = False
        for stroke in self.strokes:
            if stroke.get('tool') == 'laser' and len(stroke['points']) > 0:
                del stroke['points'][:3]
                needs_update = True

        self.strokes = [s for s in self.strokes if not (s.get('tool') == 'laser' and len(s['points']) == 0)]
        if needs_update:
            self.update()

    def set_pass(self, passthrough):
        self.passthrough = passthrough
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, passthrough)
        self.update()

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not getattr(self, 'passthrough', True):
            qp.fillRect(self.rect(), QColor(0, 0, 0, 1))
        self.paint_strokes(qp)
        qp.end()


class BoardHeader(QFrame):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.offset = None

    def mousePressEvent(self, e):
        self.board.raise_()
        self.board.tb.raise_()
        if e.button() == Qt.MouseButton.LeftButton:
            self.offset = e.globalPosition().toPoint() - self.board.pos()

    def mouseMoveEvent(self, e):
        if self.offset:
            self.board.move(e.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, e):
        self.offset = None


class AIWindow(QWidget):
    def __init__(self, tb, mode, capture_pixmap):
        super().__init__()
        self.tb = tb
        self.mode = mode
        self.capture_image = capture_pixmap.toImage()
        self.chat_history = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 480, 650)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 35, 240);
                border: 2px solid #BB86FC;
                border-radius: 20px;
            }
        """)
        self.cont_layout = QVBoxLayout(self.container)

        self.header = QLabel(f" ✨ AI {mode} Analysis")
        self.header.setStyleSheet("color: #BB86FC; font-size: 18px; font-weight: bold; border: none; padding: 5px;")
        self.cont_layout.addWidget(self.header)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 10px; background: rgba(0,0,0,50); border-radius: 5px;}
            QScrollBar::handle:vertical { background: #BB86FC; border-radius: 5px; }
        """)

        self.chat_content = QWidget()
        self.chat_content.setStyleSheet("background: transparent;")
        self.chat_vbox = QVBoxLayout(self.chat_content)
        self.chat_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_scroll.setWidget(self.chat_content)
        self.cont_layout.addWidget(self.chat_scroll)

        self.chat_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type '/imagine [prompt]' for pictures, or ask a question...")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 150); color: white;
                border: 1px solid #555; border-radius: 10px; padding: 10px; font-size: 14px;
            }
        """)
        self.chat_input.returnPressed.connect(self.ask_question)
        self.chat_layout.addWidget(self.chat_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(
            "background: #BB86FC; color: black; font-weight: bold; border-radius: 10px; padding: 10px 20px;")
        self.send_btn.clicked.connect(self.ask_question)
        self.chat_layout.addWidget(self.send_btn)
        self.cont_layout.addLayout(self.chat_layout)

        self.btn_row = QHBoxLayout()
        self.close_btn = QPushButton("Done")
        self.close_btn.setStyleSheet(
            "background: #444; color: white; border-radius: 10px; padding: 8px 20px; font-weight: bold;")
        self.close_btn.clicked.connect(self.close)
        self.btn_row.addStretch()
        self.btn_row.addWidget(self.close_btn)
        self.cont_layout.addLayout(self.btn_row)

        self.main_layout.addWidget(self.container)
        self.offset = None

        self.add_chat_bubble("System", text="Captured Screen Image:", pixmap=capture_pixmap)
        self.add_chat_bubble("AI", text=f"Asking the AI to {mode}... Please wait.")

        self.run_ai()
        self.show()

    def add_chat_bubble(self, sender, text=None, pixmap=None):
        if hasattr(self, 'thinking_bubble') and self.thinking_bubble:
            self.chat_vbox.removeWidget(self.thinking_bubble)
            self.thinking_bubble.deleteLater()
            self.thinking_bubble = None

        if text and sender in ["You", "AI"]:
            self.chat_history.append(f"{sender}: {text}")

        bubble = QFrame()
        bg_col = "rgba(187, 134, 252, 30)" if sender == "You" else "rgba(0, 0, 0, 150)"
        border_col = "#BB86FC" if sender == "You" else "#555"

        bubble.setStyleSheet(f"""
            QFrame {{
                background: {bg_col};
                border: 1px solid {border_col};
                border-radius: 10px;
                margin-bottom: 5px;
            }}
        """)

        lay = QVBoxLayout(bubble)
        lay.setContentsMargins(12, 12, 12, 12)

        name_lbl = QLabel(f"<b>{sender}</b>")
        name_lbl.setStyleSheet("color: #AAA; font-size: 12px; border: none; background: transparent;")
        lay.addWidget(name_lbl)

        if text:
            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setStyleSheet("color: #FFF; font-size: 15px; border: none; background: transparent;")
            text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(text_lbl)

        if pixmap and not pixmap.isNull():
            img_lbl = QLabel()
            scaled_pix = pixmap.scaled(380, 380, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            img_lbl.setPixmap(scaled_pix)
            img_lbl.setStyleSheet("border: 1px solid #444; border-radius: 8px; background: #000; margin-top: 8px;")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(img_lbl)

            btn_lay = QHBoxLayout()
            btn_lay.addStretch()
            dl_btn = QPushButton("💾 Download Image")
            dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dl_btn.setStyleSheet("""
                QPushButton {
                    background: #007ACC; color: #FFF; font-weight: bold;
                    border-radius: 6px; padding: 6px 12px; border: none;
                }
                QPushButton:hover { background: #005A9E; }
            """)
            dl_btn.clicked.connect(lambda _, p=pixmap: self.download_image(p))
            btn_lay.addWidget(dl_btn)
            lay.addLayout(btn_lay)

        self.chat_vbox.addWidget(bubble)

        if text == "Thinking...":
            self.thinking_bubble = bubble

        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))

    def download_image(self, pixmap):
        path, _ = QFileDialog.getSaveFileName(self, "Save Generated Image", "AI_Generation.png",
                                              "PNG Images (*.png);;JPEG Images (*.jpg)")
        if path:
            pixmap.save(path)

    def run_ai(self, history="", new_question="", is_imagine=False):
        self.chat_input.setEnabled(False)
        self.send_btn.setEnabled(False)

        self.worker = AIWorker(qimage=self.capture_image, mode=self.mode, history=history, new_question=new_question,
                               is_imagine=is_imagine)
        self.worker.finished.connect(self.display_result)

        self.worker.image_finished.connect(self.display_image_result)
        self.worker.error.connect(self.display_result)
        self.worker.start()

    def display_image_result(self, byte_array):
        px = QPixmap()
        success = px.loadFromData(byte_array)

        if not success or px.isNull():
            self.add_chat_bubble("AI",
                                 text="Error: I generated an image, but it failed to decode correctly. Your API might be restricting downloads.")
        else:
            self.add_chat_bubble("AI", text="Here is the image I generated for you:", pixmap=px)

        self.chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.chat_input.clear()
        self.chat_input.setFocus()

    def display_result(self, result_text):
        self.add_chat_bubble("AI", text=result_text)

        self.chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.chat_input.clear()
        self.chat_input.setFocus()

    def ask_question(self):
        question = self.chat_input.text().strip()
        if not question: return

        self.add_chat_bubble("You", text=question)
        self.chat_input.clear()

        if question.lower().startswith("/imagine "):
            prompt = question[9:]
            self.add_chat_bubble("AI", text="Thinking...")
            self.run_ai(new_question=prompt, is_imagine=True)
            return

        self.add_chat_bubble("AI", text="Thinking...")
        history_str = "\n".join(self.chat_history)
        self.run_ai(history=history_str, new_question=question)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.offset: self.move(e.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, e):
        self.offset = None


class MiniBoard(QWidget):
    def __init__(self, tb, mode='new', strokes=None, path=None):
        super().__init__(tb.c)
        self.tb = tb
        self.path = path
        self.mode = 'dark' if mode in ['black', 'new'] else mode
        self.pattern = 'blank'

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        # --- NEW: MUST be added so the window can physically render transparency ---
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setGeometry(int(tb.geometry().right() + 20), int(tb.geometry().top()), 800, 600)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.header = BoardHeader(self)
        self.header.setFixedHeight(34)
        self.header.setStyleSheet("background: #333; border-bottom: 1px solid #555;")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)

        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(10, 0, 10, 0)

        title_text = "New Window" if not path else os.path.basename(path).replace('.draw', '')
        self.title = QLabel(title_text)
        self.title.setStyleSheet("color: #FFF; font-weight: bold; font-size: 13px;")
        hl.addWidget(self.title)

        hl.addStretch()

        self.cb_theme = QComboBox()
        # --- NEW: Added Transparent option ---
        self.cb_theme.addItems(["Dark Mode", "Light Mode", "Transparent"])
        self.cb_theme.setStyleSheet(
            "background: #444; color: #FFF; border: 1px solid #666; border-radius: 3px; padding: 2px 6px;")
        self.cb_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cb_theme.currentTextChanged.connect(self.change_theme)

        if self.mode == 'light':
            self.cb_theme.setCurrentText("Light Mode")
        elif self.mode == 'transparent':
            self.cb_theme.setCurrentText("Transparent")

        hl.addWidget(self.cb_theme)

        self.cb_pattern = QComboBox()
        self.cb_pattern.addItems(["Blank", "Grid", "Dotted"])
        self.cb_pattern.setStyleSheet(
            "background: #444; color: #FFF; border: 1px solid #666; border-radius: 3px; padding: 2px 6px;")
        self.cb_pattern.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cb_pattern.currentTextChanged.connect(self.change_pattern)
        hl.addWidget(self.cb_pattern)

        btn_jump = QPushButton("🎯 Focus Edit")
        btn_jump.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_jump.setStyleSheet(
            "color: #FFF; background: #007ACC; border: 1px solid #005A9E; padding: 4px 10px; border-radius: 3px; font-weight: bold;")
        btn_jump.clicked.connect(lambda: getattr(self, 'c', None) and self.c.jump_to_last_edit())
        hl.addWidget(btn_jump)

        btn_save = QPushButton("💾 Save")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            "color: #FFF; background: #444; border: 1px solid #666; padding: 4px 10px; border-radius: 3px;")
        btn_save.clicked.connect(self.save)
        hl.addWidget(btn_save)

        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            "color: #FFF; background: #D32F2F; border: none; padding: 4px 10px; border-radius: 3px; font-weight: bold;")
        btn_close.clicked.connect(self.close_board)
        hl.addWidget(btn_close)

        self.layout.addWidget(self.header)

        self.c = CanvasWidget(tb, self)
        if strokes: self.c.strokes = strokes
        self.layout.addWidget(self.c)

        self.laser_timer = QTimer(self)
        self.laser_timer.timeout.connect(self.process_laser_fade)
        self.laser_timer.start(20)

        self.show()

    def process_laser_fade(self):
        if not hasattr(self, 'c') or not hasattr(self.c, 'strokes') or not self.c.strokes:
            return

        needs_update = False
        for stroke in self.c.strokes:
            if stroke.get('tool') == 'laser' and len(stroke['points']) > 0:
                del stroke['points'][:3]
                needs_update = True

        self.c.strokes = [s for s in self.c.strokes if not (s.get('tool') == 'laser' and len(s['points']) == 0)]
        if needs_update:
            self.c.update()

    def change_theme(self, text):
        if text == "Dark Mode":
            self.mode = 'dark'
        elif text == "Light Mode":
            self.mode = 'light'
        else:
            self.mode = 'transparent'
        self.update()

    def change_pattern(self, text):
        self.pattern = text.lower()
        self.update()

    def paintEvent(self, e):
        qp = QPainter(self)

        # --- NEW: Dynamic Opacity Background ---
        if self.mode == 'dark':
            bg_color = QColor("#1E1E1E")
        elif self.mode == 'light':
            bg_color = QColor("#FFFFFF")
        else:
            # Opacity of 1 is invisible, but maintains a solid surface so you can draw on it!
            bg_color = QColor(0, 0, 0, 1)

        qp.fillRect(self.rect(), bg_color)

        if self.pattern != 'blank':
            # Grid/dots should be dark in light mode, and light in dark/transparent modes
            pen_color = QColor(0, 0, 0, 30) if self.mode == 'light' else QColor(255, 255, 255, 30)
            qp.setPen(QPen(pen_color, 1))
            qp.setBrush(pen_color)
            w, h = self.width(), self.height()

            px = int(self.c.pan_x) if hasattr(self, 'c') else 0
            py = int(self.c.pan_y) if hasattr(self, 'c') else 0

            if self.pattern == 'grid':
                dx = px % 25
                dy = py % 25
                for y in range(34 + dy - 25, h, 25):
                    if y > 34: qp.drawLine(0, y, w, y)
                for x in range(dx - 25, w + 25, 25):
                    qp.drawLine(x, 34, x, h)

            elif self.pattern == 'dotted':
                dx = px % 20
                dy = py % 20
                for y in range(34 + dy - 20, h, 20):
                    if y > 34:
                        for x in range(dx - 20, w + 20, 20):
                            qp.drawEllipse(x, y, 2, 2)
        qp.end()

    def save(self):
        if not self.path:
            text, ok = QInputDialog.getText(self, "Save Window", "Enter name for this window:")
            if ok and text:
                self.path = os.path.join(BOARDS_DIR, f"{text}.draw")
                self.title.setText(text)
        if self.path:
            save_board(self.c.strokes, self.mode, self.path)

    def close_board(self):
        if self in self.tb.boards: self.tb.boards.remove(self)
        self.deleteLater()


class LoadWindow(QWidget):
    def __init__(self, tb):
        super().__init__(tb.c)
        self.tb = tb

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.offset = None

        self.setGeometry(int(tb.geometry().right() + 20), int(tb.geometry().top()), 420, 500)

        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(0, 0, 420, 500)
        self.main_frame.setStyleSheet(
            "QFrame { background: #2D2D2D; color: #FFF; border: 1px solid #444; border-radius: 8px; }")

        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(10, 10, 10, 10)

        header_layout = QHBoxLayout()
        title_lbl = QLabel("📂 Saved Boards")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #BB86FC; border: none;")
        header_layout.addWidget(title_lbl)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #888; font-weight: bold; font-size: 16px; border: none; } QPushButton:hover { color: #D32F2F; }")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        main_layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; background: #222; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #BB86FC; }
        """)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")

        self.list_layout = QVBoxLayout(self.content_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setContentsMargins(5, 5, 5, 5)
        self.list_layout.setSpacing(10)

        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll)

        self.refresh_list()

    def refresh_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        files = get_saved_files()
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        if not files:
            empty_lbl = QLabel("No saved boards found.")
            empty_lbl.setStyleSheet("color: #888; font-size: 14px; font-style: italic; border: none;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            return

        for f in files:
            name = os.path.basename(f).replace('.draw', '')
            mtime = os.path.getmtime(f)
            dt_str = datetime.datetime.fromtimestamp(mtime).strftime('%b %d, %Y • %I:%M %p')

            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #1E1E1E;
                    border: 1px solid #444;
                    border-radius: 10px;
                }
                QFrame:hover {
                    border: 1px solid #BB86FC;
                    background: #252529;
                }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(15, 12, 15, 12)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            title_lbl = QLabel(name)
            title_lbl.setStyleSheet(
                "color: #FFF; font-size: 15px; font-weight: bold; border: none; background: transparent;")

            date_lbl = QLabel(dt_str)
            date_lbl.setStyleSheet("color: #888; font-size: 11px; border: none; background: transparent;")

            info_layout.addWidget(title_lbl)
            info_layout.addWidget(date_lbl)

            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            btn_load = QPushButton("Load")
            btn_load.setStyleSheet("""
                QPushButton { background: #BB86FC; color: #000; font-weight: bold; border-radius: 6px; padding: 6px 14px; border: none; }
                QPushButton:hover { background: #9965D4; }
            """)
            btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_load.clicked.connect(lambda _, path=f: self.load_board(path))

            btn_edit = QPushButton("✎")
            btn_edit.setFixedSize(30, 30)
            btn_edit.setStyleSheet(
                "QPushButton { background: #444; color: #FFF; border-radius: 6px; border: none; } QPushButton:hover { background: #666; }")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setToolTip("Rename")
            btn_edit.clicked.connect(lambda _, old=f: self.rename_file(old))

            btn_del = QPushButton("🗑")
            btn_del.setFixedSize(30, 30)
            btn_del.setStyleSheet(
                "QPushButton { background: #D32F2F; color: #FFF; border-radius: 6px; border: none; } QPushButton:hover { background: #B71C1C; }")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setToolTip("Delete")
            btn_del.clicked.connect(lambda _, path=f: self.delete_file(path))

            card_layout.addWidget(btn_load)
            card_layout.addWidget(btn_edit)
            card_layout.addWidget(btn_del)

            self.list_layout.addWidget(card)

    def load_board(self, path):
        data = load_board(path)
        if data:
            self.tb.add_board(data['mode'], data['strokes'], path)
        self.close()

    def rename_file(self, old_path):
        old_name = os.path.basename(old_path).replace('.draw', '')
        new_name, ok = QInputDialog.getText(self, "Rename Window", "Enter new name:", text=old_name)
        if ok and new_name:
            rename_board(old_path, new_name)
            self.refresh_list()

    def delete_file(self, path):
        os.remove(path)
        self.refresh_list()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if hasattr(self, 'offset') and self.offset:
            self.move(e.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, e):
        self.offset = None