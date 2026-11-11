from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Placeholder endpoint – real backend runs separately."}
