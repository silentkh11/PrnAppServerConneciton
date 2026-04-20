import os
import json
import pickle
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QPixmap, QImage

# --- THE SOURCE OF TRUTH FOR PATHS ---
APP_DATA_PATH = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ScreenDrawData')
BOARDS_DIR = os.path.join(APP_DATA_PATH, 'saved_boards')
NOTES_FILE = os.path.join(APP_DATA_PATH, 'sticky_notes.json')

# Silently create the folders if they don't exist yet
os.makedirs(BOARDS_DIR, exist_ok=True)


# ==========================================
# STICKY NOTES LOGIC
# ==========================================
def save_sticky_notes(notes_data):
    try:
        with open(NOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, indent=4)
    except Exception as e:
        print(f"Failed to save sticky notes: {e}")


def load_sticky_notes():
    if not os.path.exists(NOTES_FILE): return []
    try:
        with open(NOTES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return []


# ==========================================
# DRAWING BOARD LOGIC (Upgraded for Deep Serialization!)
# ==========================================
def save_board(strokes, mode, filepath):
    try:
        serialized_strokes = []

        for s in strokes:
            # We must create a copy so we don't accidentally destroy the live canvas!
            stroke_copy = s.copy()

            if stroke_copy.get('type') == 'image':
                # 1. Convert the visual QPixmap into a raw PNG byte array
                if 'pixmap' in stroke_copy:
                    ba = QByteArray()
                    buff = QBuffer(ba)
                    buff.open(QIODevice.OpenModeFlag.WriteOnly)
                    stroke_copy['pixmap'].save(buff, "PNG")
                    stroke_copy['pixmap_bytes'] = ba.data()
                    del stroke_copy['pixmap']  # Delete the un-saveable C++ object

                # 2. If it's an AI Stamp, convert the background QImage brain into bytes too!
                if stroke_copy.get('is_ai_stamp') and 'ai_qimage' in stroke_copy:
                    ba_ai = QByteArray()
                    buff_ai = QBuffer(ba_ai)
                    buff_ai.open(QIODevice.OpenModeFlag.WriteOnly)
                    stroke_copy['ai_qimage'].save(buff_ai, "PNG")
                    stroke_copy['ai_qimage_bytes'] = ba_ai.data()
                    del stroke_copy['ai_qimage']  # Delete the un-saveable C++ object

            serialized_strokes.append(stroke_copy)

        with open(filepath, 'wb') as f:
            pickle.dump({'mode': mode, 'strokes': serialized_strokes}, f)

    except Exception as e:
        print(f"Failed to save board: {e}")


def load_board(filepath):
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        deserialized_strokes = []
        for s in data.get('strokes', []):
            if s.get('type') == 'image':
                # 1. Resurrect the visual QPixmap from the raw bytes
                if 'pixmap_bytes' in s:
                    pix = QPixmap()
                    pix.loadFromData(s['pixmap_bytes'])
                    s['pixmap'] = pix
                    del s['pixmap_bytes']

                # 2. Resurrect the AI's QImage brain from the raw bytes
                if s.get('is_ai_stamp') and 'ai_qimage_bytes' in s:
                    img = QImage.fromData(s['ai_qimage_bytes'])
                    s['ai_qimage'] = img
                    del s['ai_qimage_bytes']

            deserialized_strokes.append(s)

        data['strokes'] = deserialized_strokes
        return data

    except Exception as e:
        print(f"Failed to load board: {e}")
        return None


def get_saved_files():
    if not os.path.exists(BOARDS_DIR): return []
    return [os.path.join(BOARDS_DIR, f) for f in os.listdir(BOARDS_DIR) if f.endswith('.draw')]


def rename_board(old_path, new_name):
    try:
        new_path = os.path.join(BOARDS_DIR, f"{new_name}.draw")
        os.rename(old_path, new_path)
    except Exception as e:
        print(f"Failed to rename board: {e}")