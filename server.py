import asyncio
import websockets
import sqlite3
import json
from datetime import datetime

# Инициализация умной БД
def init_db():
    conn = sqlite3.connect("telegram_chat.db")
    cursor = conn.cursor()
    # Добавили поле room для разделения категорий/чатов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            text TEXT,
            timestamp TEXT,
            room TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(username, text, room):
    conn = sqlite3.connect("telegram_chat.db")
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%H:%M")
    cursor.execute(
        "INSERT INTO messages (username, text, timestamp, room) VALUES (?, ?, ?, ?)",
        (username, text, timestamp, room)
    )
    conn.commit()
    conn.close()
    return timestamp

def get_history(room):
    conn = sqlite3.connect("telegram_chat.db")
    cursor = conn.cursor()
    # Фильтруем сообщения по конкретной комнате
    cursor.execute("SELECT username, text, timestamp, room FROM messages WHERE room = ? ORDER BY id DESC LIMIT 50", (room,))
    rows = cursor.fetchall()
    conn.close()
    return reversed(rows)

CLIENTS = set()

async def chat_handler(websocket):
    CLIENTS.add(websocket)
    
    try:
        async for message in websocket:
            data = json.loads(message)
            req_type = data.get("type")
            room = data.get("room", "Общий чат")
            
            # Если пользователь переключил чат, шлем ему историю этого чата
            if req_type == "request_history":
                history = get_history(room)
                history_data = [{"username": r[0], "text": r[1], "time": r[2], "room": r[3]} for r in history]
                await websocket.send(json.dumps({"type": "history", "data": history_data}))
            
            # Если это новое сообщение
            elif req_type == "new_msg":
                username = data.get("username", "Аноним")
                text = data.get("text", "")
                
                if text.strip():
                    timestamp = save_message(username, text, room)
                    
                    broadcast_data = json.dumps({
                        "type": "msg",
                        "username": username,
                        "text": text,
                        "time": timestamp,
                        "room": room
                    })
                    
                    # Рассылаем всем в сети
                    for client in CLIENTS:
                        await client.send(broadcast_data)
                        
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CLIENTS.remove(websocket)

async def main():
    init_db()
    async with websockets.serve(chat_handler, "0.0.0.0", 8765):
        print("Красивый Telegram-сервер запущен на порту 8765...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())