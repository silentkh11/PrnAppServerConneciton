import os
import requests
import random
import string
import json
import websocket
from PyQt6.QtCore import QThread, pyqtSignal

FIREBASE_URL = "https://screendrawai-default-rtdb.firebaseio.com"


# ==========================================
# ENGINE 1: FIREBASE (Version Control & Storage)
# ==========================================
class NetworkManager:
    def __init__(self):
        self.user_id = None
        self.db = FIREBASE_URL

    def host_study_room(self, board_data):
        # Generate a random 6-digit code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        url = f"{self.db}/rooms/{code}/Original_Board.json"

        payload = {
            "data": board_data,
            "host": self.user_id
        }

        try:
            r = requests.put(url, json=payload)
            if r.status_code == 200:
                return code
        except Exception as e:
            print(f"Firebase Host Error: {e}")
        return None

    def join_study_room(self, code):
        url = f"{self.db}/rooms/{code}.json"
        try:
            r = requests.get(url)
            if r.status_code == 200 and r.json():
                return r.json()
        except Exception as e:
            print(f"Firebase Join Error: {e}")
        return None

    def submit_revision(self, code, updated_json):
        url = f"{self.db}/rooms/{code}/Update_from_{self.user_id}.json"
        payload = {
            "data": updated_json,
            "author": self.user_id
        }
        try:
            r = requests.put(url, json=payload)
            return r.status_code == 200
        except:
            return False

    def send_to_inbox(self, target, board_data):
        url = f"{self.db}/inbox/{target}.json"
        payload = {
            "board_data": board_data,
            "sender": self.user_id
        }
        try:
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                return True, f"Sent to {target} successfully!"
        except Exception as e:
            return False, str(e)
        return False, "Network error."

    def check_inbox(self):
        url = f"{self.db}/inbox/{self.user_id}.json"
        try:
            r = requests.get(url)
            data = r.json()
            if data:
                # Grab the first message in the inbox
                key = list(data.keys())[0]
                msg = data[key]
                # Delete it from Firebase so they don't open it twice
                requests.delete(f"{self.db}/inbox/{self.user_id}/{key}.json")
                return msg
        except:
            pass
        return None


# ==========================================
# ENGINE 2: WEBSOCKETS (Real-Time Render Cloud)
# ==========================================
class LiveNetworkManager(QThread):
    point_received = pyqtSignal(dict)
    system_event = pyqtSignal(dict)  # NEW: Signal for UI updates

    def __init__(self):
        super().__init__()
        self.user_id = None
        self.room_code = None
        self.ws = None
        self.is_connected = False
        self.should_run = False

        self.server_url = "wss://screendraw-live.onrender.com"

    def connect_to_room(self, room_code):
        self.room_code = room_code
        self.should_run = True
        self.start()

    def run(self):
        import time
        while self.should_run:
            try:
                self.ws = websocket.WebSocket()
                self.ws.connect(self.server_url, timeout=5.0)
                self.is_connected = True

                # NEW: Pass the user_id so the server knows who is joining
                self.ws.send(json.dumps({
                    "action": "join",
                    "room": self.room_code,
                    "user_id": self.user_id
                }))

                self.ws.settimeout(5.0)

                while self.is_connected and self.should_run:
                    try:
                        msg = self.ws.recv()
                        if msg:
                            data = json.loads(msg)
                            # NEW: Route system events differently than drawing events
                            if data.get("action") == "system":
                                self.system_event.emit(data)
                            else:
                                self.point_received.emit(data)

                    except websocket.WebSocketTimeoutException:
                        try:
                            self.ws.send(json.dumps({"action": "ping"}))
                        except:
                            break

            except Exception as e:
                self.is_connected = False
                if self.should_run:
                    time.sleep(2)

    def send_draw_point(self, tool, x, y, color, width, is_new_stroke):
        if self.is_connected and self.ws:
            payload = {"action": "draw", "user_id": self.user_id, "tool": tool, "x": x, "y": y, "color": color,
                       "width": width, "is_new_stroke": is_new_stroke}
            try:
                self.ws.send(json.dumps(payload))
            except:
                self.is_connected = False

    def send_erase_point(self, x, y):
        if self.is_connected and self.ws:
            payload = {"action": "erase", "x": x, "y": y}
            try:
                self.ws.send(json.dumps(payload))
            except:
                self.is_connected = False

    def close_room_globally(self):
        # NEW: Send the kill switch to the server
        if self.is_connected and self.ws:
            try:
                self.ws.send(json.dumps({"action": "close_room"}))
            except:
                pass

    def disconnect_from_room(self):
        self.should_run = False
        self.is_connected = False
        if self.ws:
            self.ws.close()