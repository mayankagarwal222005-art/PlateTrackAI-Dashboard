# src/main.py – placeholder FastAPI app for Vercel

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def health_check():
    """Simple health‑check endpoint that Vercel can use as the entrypoint.
    The real API is hosted elsewhere (Render, Railway, …).
    """
    return {"status": "ok", "message": "Placeholder endpoint – real backend runs separately."}
