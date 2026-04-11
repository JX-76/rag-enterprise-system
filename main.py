"""
Compatibility launcher for the official FastAPI entry.

Official API entry: `src.main:app`
Recommended dev start:
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

This root-level script is kept as a lightweight convenience wrapper.
"""
import uvicorn

from src.core.config import settings
from src.main import app  # re-export for tools that expect `main:app`


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
    )
