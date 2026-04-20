import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QApplication, QFrame)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices


class SetupWindow(QWidget):
    def __init__(self, on_success_callback):
        super().__init__()
        self.on_success = on_success_callback

        # Frameless and transparent base for smooth rounded corners
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(450, 360)

        # Center the window on the primary screen
        screen_center = QApplication.primaryScreen().geometry().center()
        self.move(screen_center.x() - self.width() // 2, screen_center.y() - self.height() // 2)

        # Main styled container
        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(0, 0, 450, 360)
        self.main_frame.setStyleSheet("QFrame { background: #1E1E1E; border: 2px solid #BB86FC; border-radius: 15px; }")

        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title = QLabel("✨ Welcome to ScreenDraw AI")
        title.setStyleSheet("color: #BB86FC; font-size: 22px; font-weight: bold; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "To use the AI Tutor and Image Generation features, you need a free Google Gemini API Key.\n\nYour key is stored locally on your computer and is never shared with anyone else.")
        desc.setStyleSheet("color: #DDD; font-size: 14px; border: none;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # Button that opens their web browser directly to Google's key page
        link_btn = QPushButton("🌐 Click here to get your free API Key")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.setStyleSheet("""
            QPushButton { background: #2D2D2D; color: #4DAAFE; font-size: 14px; font-weight: bold; border: 1px solid #444; border-radius: 8px; padding: 10px; }
            QPushButton:hover { background: #3D3D3D; border: 1px solid #4DAAFE; }
        """)
        link_btn.clicked.connect(self.open_google_studio)
        layout.addWidget(link_btn)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your GEMINI_API_KEY here...")
        self.key_input.setStyleSheet("""
            QLineEdit { background: #000; color: #FFF; border: 1px solid #555; border-radius: 8px; padding: 12px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #BB86FC; }
        """)
        layout.addWidget(self.key_input)

        self.start_btn = QPushButton("Save & Launch 🚀")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton { background: #BB86FC; color: #000; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; padding: 12px; }
            QPushButton:hover { background: #9965D4; }
        """)
        self.start_btn.clicked.connect(self.save_and_start)
        layout.addWidget(self.start_btn)

        self.offset = None

    def open_google_studio(self):
        # Opens the default OS web browser directly to the API key generator
        QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey"))

    def save_and_start(self):
        api_key = self.key_input.text().strip()

        # Shake/Red effect if they try to launch without typing anything
        if not api_key:
            self.key_input.setStyleSheet(
                "QLineEdit { background: #330000; color: #FFF; border: 1px solid #FF4B4B; border-radius: 8px; padding: 12px; font-size: 14px; }")
            return

        # Python automatically creates the .env file and saves the key securely
        with open(".env", "w") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")

        # Trigger the main app to launch and close this window
        self.on_success()
        self.close()

    # Dragging mechanics for the frameless window
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if hasattr(self, 'offset') and self.offset:
            self.move(e.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, e):
        self.offset = None