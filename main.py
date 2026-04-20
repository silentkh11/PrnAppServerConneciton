import sys
import os
from PyQt6.QtWidgets import QApplication
from dotenv import load_dotenv

# Local imports
from windows import Overlay  # <--- THE FIX: Importing the specialized Overlay
from toolbar.core import Toolbar
from setup_window import SetupWindow

# Global references to keep the app alive in memory
c = None
t = None


def launch_main_app():
    global c, t
    # Force reload environment variables so ai_worker sees the newly saved key
    load_dotenv(override=True)

    # Launch the actual application
    c = Overlay()  # <--- THE FIX: Launching the Overlay instead of the basic canvas
    t = Toolbar(c)
    c.showFullScreen()
    t.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Try to load existing keys
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    # Check if the key is missing or blank
    if not api_key or api_key.strip() == "":
        # Pause the launch and show the setup screen instead
        setup = SetupWindow(on_success_callback=launch_main_app)
        setup.show()
    else:
        # Key exists! Boot directly into the transparent canvas
        launch_main_app()

    sys.exit(app.exec())