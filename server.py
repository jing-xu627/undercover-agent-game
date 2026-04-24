"""
Standalone server entry point for game.

This is a thin wrapper around the api module.
For development, use:
    python server.py

For production, use:
    uvicorn api.main:create_app --host 0.0.0.0 --port 8124
"""

from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    # Run server with import string for reload support
    uvicorn.run(
        "game.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8124,
        reload=True,
        log_level="info",
    )
