"""Climb-agent API — FastAPI application."""

from fastapi import FastAPI

app = FastAPI(title="climb-agent", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Planned endpoints (v1) ---
# @app.post("/plan")      # Generate a week plan
# @app.post("/resolve")   # Resolve a planned day into concrete sessions
# @app.post("/replan")    # Apply events and replan the week
# @app.post("/progress")  # Apply progression feedback
# @app.post("/log")       # Log a resolved day result
# @app.get("/state")      # Return current user state
# @app.get("/catalog")    # List available sessions / exercises
