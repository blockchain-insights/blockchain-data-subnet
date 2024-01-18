from fastapi import FastAPI
from api.dashboard.background_worker import run_scheduler
from routers import user, auth, hotkey
import threading

app = FastAPI()

# Include your routers
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(hotkey.router)

# Start the scheduler in a background thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()
