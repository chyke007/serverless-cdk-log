import logging
import random
import time
from datetime import datetime
from fastapi import FastAPI, Request
import threading
import uvicorn

# Configure standard logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)
logger = logging.getLogger("sample_logger")

LOG_LEVELS = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
LOG_LEVEL_NAMES = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
SAMPLE_MESSAGES = [
    "User login succeeded",
    "User login failed",
    "File uploaded successfully",
    "File upload failed",
    "Database connection established",
    "Database connection lost",
    "Cache miss",
    "Cache hit",
    "API request received",
    "API request failed",
    "Background job started",
    "Background job completed",
    "Unexpected exception occurred"
]

app = FastAPI()

def random_log():
    while True:
        level = random.choice(LOG_LEVELS)
        level_name = LOG_LEVEL_NAMES[LOG_LEVELS.index(level)]
        msg = random.choice(SAMPLE_MESSAGES)
        logger.log(level, f"[{level_name}] {msg}")
        time.sleep(30)

@app.get("/")
async def index(request: Request):
    now = datetime.utcnow().isoformat()
    client_host = request.client.host
    logger.info(f"[INFO] Web endpoint visited at {now} from {client_host}. Deployed with Github workflow")
    return {"message": f"Logger app running. Visit time: {now}. Deployed with Github workflow"}

if __name__ == "__main__":
    t = threading.Thread(target=random_log, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8080) 
