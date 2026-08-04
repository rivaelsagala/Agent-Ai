import os
import uvicorn
from loguru import logger

if __name__ == "__main__":
    host = os.getenv("HOST", os.getenv("FLASK_RUN_HOST", "127.0.0.1"))
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Zimbo AI FastAPI Server at http://{host}:{port}")
    logger.info(f"Interactive API docs (Swagger UI) available at http://{host}:{port}/docs")
    uvicorn.run("app:create_app", host=host, port=port, factory=True, reload=False)

