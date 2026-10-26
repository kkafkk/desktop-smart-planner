import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import asyncio
from datetime import datetime, timedelta

app = FastAPI()

# --- НАСТРОЙКИ TELEGRAM ---
TG_BOT_TOKEN = "8854436377:AAF4jAbLY4UvLDM1Rt21rhp_P5akWFK1YxQ" 
TG_CHAT_ID = "1012369416"

# База данных задач (в оперативной памяти)
tasks_db = []
current_id = 1

class TaskCreate(BaseModel):
    title: str
    time: str  # Формат "HH:MM"
    color: str

# Фоновая задача для отправки уведомлений
async def telegram_notifier():
    while True:
        now = datetime.now()
        target_time = (now + timedelta(minutes=10)).strftime("%H:%M")
        
        for task in tasks_db:
            if not task["completed"] and not task.get("notified") and task["time"] == target_time:
                msg = f"⏳ Reminder: Task '{task['title']}' starts in 10 minutes!"
                url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    try:
                        await client.get(url, params={"chat_id": TG_CHAT_ID, "text": msg})
                        task["notified"] = True
                    except:
                        pass
        await asyncio.sleep(30) # Проверяем каждые 30 секунд

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telegram_notifier())

# --- API ДЛЯ ВЕБ-САЙТА ---
@app.get("/api/tasks")
def get_all_tasks():
    # Сортируем по времени
    return sorted(tasks_db, key=lambda x: x["time"])

@app.post("/api/tasks")
def add_task(task: TaskCreate):
    global current_id
    new_task = {
        "id": current_id,
        "title": task.title,
        "time": task.time,
        "color": task.color,
        "completed": False,
        "notified": False
    }
    tasks_db.append(new_task)
    current_id += 1
    return {"status": "ok"}

# --- API ДЛЯ ESP32 (Твоя плата стучится сюда) ---
@app.get("/api/task")
def get_current_task():
    active_tasks = [t for t in tasks_db if not t["completed"]]
    if active_tasks:
        # Отдаем самую ближайшую активную задачу
        sorted_tasks = sorted(active_tasks, key=lambda x: x["time"])
        return sorted_tasks[0]
    return None

@app.post("/api/task/{task_id}/complete")
def complete_task(task_id: int):
    for task in tasks_db:
        if task["id"] == task_id:
            task["completed"] = True
            return {"status": "completed"}
    return {"error": "Not found"}

# --- ВЕБ-ИНТЕРФЕЙС (Frontend) ---
@app.get("/", response_class=HTMLResponse)
def serve_web_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Task Manager</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f7f6; margin: 0; padding: 20px; color: #333; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
            h1 { text-align: center; color: #2c3e50; font-weight: 600; margin-bottom: 30px; }
            .form-group { display: flex; gap: 10px; margin-bottom: 25px; }
            input[type="text"] { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; outline: none; }
            input[type="time"], input[type="color"] { padding: 10px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; }
            button { background: #3498db; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; transition: background 0.3s; font-weight: 500; }
            button:hover { background: #2980b9; }
            .task-list { display: flex; flex-direction: column; gap: 12px; }
            .task-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; border-radius: 8px; border-left: 6px solid; background: #fdfdfd; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
            .task-time { font-weight: bold; color: #7f8c8d; width: 60px; }
            .task-title { flex: 1; margin-left: 15px; font-size: 16px; font-weight: 500; }
            .status { font-size: 13px; padding: 4px 8px; border-radius: 12px; }
            .status.active { background: #e8f8f5; color: #1abc9c; }
            .status.completed { background: #ebedef; color: #95a5a6; text-decoration: line-through; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Daily Schedule</h1>
            
            <div class="form-group">
                <input type="text" id="taskTitle" placeholder="What needs to be done?" required>
                <input type="time" id="taskTime" required>
                <input type="color" id="taskColor" value="#3498db">
                <button onclick="addTask()">Add</button>
            </div>

            <div class="task-list" id="taskList">
                <!-- Задачи будут загружаться сюда -->
            </div>
        </div>

        <script>
            async function fetchTasks() {
                const res = await fetch('/api/tasks');
                const tasks = await res.json();
                const list = document.getElementById('taskList');
                list.innerHTML = '';
                
                tasks.forEach(task => {
                    const el = document.createElement('div');
                    el.className = 'task-item';
                    el.style.borderLeftColor = task.color.replace('0x', '#');
                    
                    const statusClass = task.completed ? 'status completed' : 'status active';
                    const statusText = task.completed ? 'Done' : 'Active';
                    
                    el.innerHTML = `
                        <span class="task-time">${task.time}</span>
                        <span class="task-title">${task.title}</span>
                        <span class="${statusClass}">${statusText}</span>
                    `;
                    list.appendChild(el);
                });
            }

            async function addTask() {
                const title = document.getElementById('taskTitle').value;
                const time = document.getElementById('taskTime').value;
                const hexColor = document.getElementById('taskColor').value;
                
                if(!title || !time) return alert("Please enter title and time!");
                
                // Конвертируем HTML HEX (#3498db) в формат ESP32 (0x...) для экрана
                const espColor = "0x" + hexColor.substring(1).toUpperCase();

                await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, time, color: espColor})
                });
                
                document.getElementById('taskTitle').value = '';
                fetchTasks();
            }

            fetchTasks();
            setInterval(fetchTasks, 3000); // Автообновление списка каждые 3 секунды
        </script>
    </body>
    </html>
    """
    return html_content
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)