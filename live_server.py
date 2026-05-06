import asyncio
import json
import websockets
import os

# Dictionary to store all active rooms and their current state
ROOMS = {}


# Helper function to broadcast messages to everyone in a room
async def broadcast(room_code, message):
    if room_code in ROOMS:
        for client in list(ROOMS[room_code]["clients"].keys()):
            try:
                await client.send(json.dumps(message))
            except:
                pass


async def handler(websocket):
    current_room = None
    user_id = None

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "join":
                current_room = data.get("room")
                user_id = data.get("user_id")

                # If room doesn't exist, this user is the Original Host
                if current_room not in ROOMS:
                    ROOMS[current_room] = {
                        "original_host": user_id,
                        "current_host": user_id,
                        "clients": {}
                    }

                # Add the new client to the room
                ROOMS[current_room]["clients"][websocket] = user_id

                # HOST MIGRATION: If original host returns, they take back the crown
                if user_id == ROOMS[current_room]["original_host"]:
                    ROOMS[current_room]["current_host"] = user_id

                # Tell everyone in the room who the host is right now
                await broadcast(current_room, {
                    "action": "system",
                    "type": "host_update",
                    "host": ROOMS[current_room]["current_host"]
                })


            elif action in ["draw", "erase", "undo", "clear"] and current_room:
                # Route the drawing data to everyone else in the room
                for client in list(ROOMS[current_room]["clients"].keys()):
                    if client != websocket:
                        try:
                            await client.send(message)
                        except:
                            pass

            elif action == "close_room" and current_room:
                # Only the current host is allowed to close the room permanently
                if user_id == ROOMS[current_room]["current_host"]:
                    await broadcast(current_room, {"action": "system", "type": "room_closed"})
                    del ROOMS[current_room]

            elif action == "ping":
                # Invisible heartbeat to keep the Render connection alive
                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # When a user disconnects, loses WiFi, or exits the app
        if current_room and current_room in ROOMS and websocket in ROOMS[current_room]["clients"]:
            del ROOMS[current_room]["clients"][websocket]

            # If the room is completely empty, delete it from the server RAM
            if len(ROOMS[current_room]["clients"]) == 0:
                del ROOMS[current_room]
            else:
                # HOST MIGRATION: If the person who left was the host, promote the next person
                if user_id == ROOMS[current_room]["current_host"]:
                    new_host_ws = list(ROOMS[current_room]["clients"].keys())[0]
                    new_host_id = ROOMS[current_room]["clients"][new_host_ws]
                    ROOMS[current_room]["current_host"] = new_host_id

                    # Tell the room about the new host
                    await broadcast(current_room, {
                        "action": "system",
                        "type": "host_update",
                        "host": new_host_id
                    })


async def main():
    # Render assigns a dynamic port via environment variables
    port = int(os.environ.get("PORT", 8765))
    print(f"🚀 ScreenDraw Server listening on port {port}...")

    # 0.0.0.0 allows the server to accept external internet connections
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())