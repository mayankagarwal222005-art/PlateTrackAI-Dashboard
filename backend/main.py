import os
import io
import asyncio
import threading
import base64
import numpy as np
import cv2
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from database import (
    init_db,
    get_logs,
    get_summary_stats,
    get_hourly_traffic,
    delete_log,
    clear_all_logs,
    record_detection,
    DB_PATH
)
from excel_service import generate_excel_bytes
from model_service import get_model_service, UPLOADS_DIR, CROPS_DIR

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

app = FastAPI(
    title="PlateTrack AI Backend",
    description="Full-stack AI Number Plate Recognition and Parking/Vehicle Entry-Exit Monitoring System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folders for crops and uploads
app.mount("/crops", StaticFiles(directory=CROPS_DIR), name="crops")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

inference_lock = asyncio.Lock()

@app.on_event("startup")
def startup_event():
    print("[SERVER] Initializing database...")
    init_db()
    print("[SERVER] Pre-loading model service in background thread...")
    threading.Thread(target=get_model_service, daemon=True).start()

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "PlateTrack AI Backend",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/logs")
def api_get_logs(
    search: str = Query("", description="Search plate number"),
    date_filter: str = Query("", description="Filter by date YYYY-MM-DD"),
    sort_by: str = Query("id", description="Column to sort by"),
    sort_order: str = Query("desc", description="Sort direction asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page")
):
    try:
        result = get_logs(
            search=search,
            date_filter=date_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def api_get_stats():
    try:
        return get_summary_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/hourly")
def api_get_hourly_stats():
    try:
        return get_hourly_traffic()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/detect/image")
async def api_detect_image(
    file: UploadFile = File(...),
    mode: str = Form("AUTO")
):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

        service = get_model_service()
        async with inference_lock:
            detection_result = await asyncio.to_thread(service.detect_frame, img, mode)
        stats = get_summary_stats()
        return {
            "success": True,
            "filename": file.filename,
            "mode": mode,
            "detection": detection_result,
            "summary_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sample-image")
def api_get_sample_image(type: str = "car"):
    sample_file = "sample_car.jpg" if type == "car" else "sample_plate.jpg"
    sample_path = os.path.join(SAMPLES_DIR, sample_file)
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="Sample image not found.")
    return FileResponse(sample_path, media_type="image/jpeg", filename=sample_file)

@app.post("/api/detect/sample")
async def api_detect_sample(
    type: str = Query("car", description="Sample type: car, plate, or video"),
    mode: str = Query("AUTO", description="Entry/exit mode")
):
    try:
        service = get_model_service()
        if type == "video":
            sample_path = os.path.join(SAMPLES_DIR, "sample_video.mp4")
            if not os.path.exists(sample_path):
                raise HTTPException(status_code=404, detail="Sample video not found.")
            async with inference_lock:
                video_result = await asyncio.to_thread(service.process_video_file, sample_path, mode)
            stats = get_summary_stats()
            return {
                "success": True,
                "sample_type": "video",
                "mode": mode,
                "result": video_result,
                "summary_stats": stats
            }

        sample_file = "sample_car.jpg" if type == "car" else "sample_plate.jpg"
        sample_path = os.path.join(SAMPLES_DIR, sample_file)
        if not os.path.exists(sample_path):
            raise HTTPException(status_code=404, detail=f"Sample file {sample_file} not found.")
        img = cv2.imread(sample_path)
        if img is None:
            raise HTTPException(status_code=500, detail="Could not read sample image.")
        async with inference_lock:
            detection_result = await asyncio.to_thread(service.detect_frame, img, mode)
        stats = get_summary_stats()
        return {
            "success": True,
            "sample_type": type,
            "mode": mode,
            "detection": detection_result,
            "summary_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class WebcamFramePayload(BaseModel):
    image: str # Base64 data URL
    mode: Optional[str] = "AUTO"

@app.post("/api/detect/webcam")
async def api_detect_webcam(payload: WebcamFramePayload):
    try:
        raw_b64 = payload.image
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",")[1]

        image_bytes = base64.b64decode(raw_b64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid webcam image frame.")

        service = get_model_service()
        async with inference_lock:
            detection_result = await asyncio.to_thread(service.detect_frame, img, payload.mode or "AUTO")
        stats = get_summary_stats()
        return {
            "success": True,
            "mode": payload.mode,
            "detection": detection_result,
            "summary_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/detect/video")
async def api_detect_video(
    file: UploadFile = File(...),
    mode: str = Form("AUTO")
):
    try:
        temp_video_path = os.path.join(UPLOADS_DIR, f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        with open(temp_video_path, "wb") as f:
            f.write(await file.read())

        service = get_model_service()
        async with inference_lock:
            video_result = await asyncio.to_thread(service.process_video_file, temp_video_path, mode)
        stats = get_summary_stats()

        return {
            "success": True,
            "filename": file.filename,
            "mode": mode,
            "result": video_result,
            "summary_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ManualLogPayload(BaseModel):
    plate_number: str
    mode: Optional[str] = "AUTO"

@app.post("/api/logs/manual")
def api_manual_log(payload: ManualLogPayload):
    try:
        plate = payload.plate_number.strip().upper()
        if not plate:
            raise HTTPException(status_code=400, detail="Plate number cannot be empty.")
        res = record_detection(plate_number=plate, mode=payload.mode or "AUTO", confidence=1.0)
        stats = get_summary_stats()
        return {"success": True, "result": res, "summary_stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/excel")
def api_export_excel():
    try:
        file_bytes, filename = generate_excel_bytes()
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/logs/{log_id}")
def api_delete_log(log_id: int):
    success = delete_log(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="Log entry not found.")
    return {"success": True, "message": f"Log entry {log_id} deleted successfully."}

@app.delete("/api/logs")
def api_clear_all_logs():
    count = clear_all_logs()
    return {"success": True, "message": f"All {count} log entries have been cleared."}

# Serve frontend static assets if frontend/ folder is present
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
