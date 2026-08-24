#!/usr/bin/env python
"""Run script for Daily Inspiration application."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app", "core", "models", "routers", "services", "schemas"]
    )
