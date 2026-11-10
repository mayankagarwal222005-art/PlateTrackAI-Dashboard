import os
import uuid
import base64
import numpy as np
import cv2
from datetime import datetime
from typing import Dict, Any, List, Optional
from ultralytics import YOLO

from ocr_helper import PlateReader
from database import record_detection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "best.pt")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
CROPS_DIR = os.path.join(BASE_DIR, "crops")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CROPS_DIR, exist_ok=True)

class PlateTrackModelService:
    def __init__(self):
        print(f"[MODEL] Loading YOLO from {MODEL_PATH}...")
        self.yolo_model = YOLO(MODEL_PATH)
        print("[MODEL] Initializing PlateReader...")
        self.reader = PlateReader()
        print("[MODEL] Model service initialized successfully.")

    def _save_crop(self, crop: np.ndarray, prefix: str = "plate") -> tuple[str, str]:
        filename = f"{prefix}_{uuid.uuid4().hex[:10]}.jpg"
        filepath = os.path.join(CROPS_DIR, filename)
        cv2.imwrite(filepath, crop)
        # Generate base64 data URL
        _, buffer = cv2.imencode(".jpg", crop)
        b64 = base64.b64encode(buffer).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"
        return filename, data_url

    def _save_annotated_image(self, image: np.ndarray, prefix: str = "annotated") -> tuple[str, str]:
        filename = f"{prefix}_{uuid.uuid4().hex[:10]}.jpg"
        filepath = os.path.join(UPLOADS_DIR, filename)
        cv2.imwrite(filepath, image)
        _, buffer = cv2.imencode(".jpg", image)
        b64 = base64.b64encode(buffer).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"
        return filename, data_url

    def detect_frame(self, frame: np.ndarray, mode: str = "AUTO") -> Dict[str, Any]:
        """
        Runs YOLO number plate detection and OCR on a single frame (from image upload or webcam).
        """
        if frame is None or frame.size == 0:
            return {"success": False, "message": "Invalid or empty image frame.", "detections": []}

        h, w = frame.shape[:2]
        results = self.yolo_model(frame, conf=0.15, verbose=False)
        annotated_frame = frame.copy()

        detections = []
        found_any = False

        if results and len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = (
                results[0].boxes.conf.cpu().numpy()
                if results[0].boxes.conf is not None
                else [0.0] * len(boxes)
            )

            for idx, (box, yolo_conf) in enumerate(zip(boxes, confs)):
                found_any = True
                track_key = f"DET_{uuid.uuid4().hex[:8]}"
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                plate_text = self.reader.extract_plate_number(frame, box, track_key, single_frame=True)
                ocr_conf = self.reader.get_cached_confidence(track_key)
                best_crop = self.reader.best_crops.get(track_key)

                if best_crop is None and x2 > x1 and y2 > y1:
                    best_crop = frame[y1:y2, x1:x2]

                crop_filename, crop_data_url = (None, None)
                if best_crop is not None and best_crop.size > 0:
                    crop_filename, crop_data_url = self._save_crop(best_crop)

                # Combined confidence
                final_conf = float(ocr_conf if ocr_conf > 0 else yolo_conf)

                # Draw bounding box and label
                box_color = (34, 197, 94) if plate_text != "SCANNING" else (234, 88, 12)
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                label_text = f"{plate_text} ({final_conf:.2f})"
                cv2.putText(
                    annotated_frame,
                    label_text,
                    (x1, max(24, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    box_color,
                    2,
                )

                # Log to DB if recognized
                log_result = None
                if plate_text != "SCANNING":
                    log_result = record_detection(
                        plate_number=plate_text,
                        mode=mode,
                        confidence=final_conf,
                        crop_path=crop_filename,
                        image_path=None
                    )

                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "plate_number": plate_text,
                    "yolo_confidence": float(yolo_conf),
                    "ocr_confidence": float(ocr_conf),
                    "confidence": final_conf,
                    "crop_url": crop_data_url,
                    "crop_filename": crop_filename,
                    "log_result": log_result
                })

        # Fallback: if YOLO found no plate box, the uploaded image itself may be a zoomed plate crop
        if not found_any or all(d["plate_number"] == "SCANNING" for d in detections):
            fallback_key = f"FALLBACK_{uuid.uuid4().hex[:8]}"
            plate_text = self.reader.extract_plate_number(frame, [0, 0, w, h], fallback_key, single_frame=True)
            ocr_conf = self.reader.get_cached_confidence(fallback_key)
            if plate_text != "SCANNING":
                crop_filename, crop_data_url = self._save_crop(frame)
                log_result = record_detection(
                    plate_number=plate_text,
                    mode=mode,
                    confidence=float(ocr_conf),
                    crop_path=crop_filename,
                    image_path=None
                )
                cv2.rectangle(annotated_frame, (4, 4), (w - 4, h - 4), (34, 197, 94), 2)
                cv2.putText(
                    annotated_frame,
                    f"{plate_text} ({ocr_conf:.2f})",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (34, 197, 94),
                    2
                )
                detections = [d for d in detections if d["plate_number"] != "SCANNING"]
                detections.append({
                    "bbox": [0, 0, w, h],
                    "plate_number": plate_text,
                    "yolo_confidence": 0.0,
                    "ocr_confidence": float(ocr_conf),
                    "confidence": float(ocr_conf),
                    "crop_url": crop_data_url,
                    "crop_filename": crop_filename,
                    "log_result": log_result
                })

        # Save annotated image
        annotated_filename, annotated_data_url = self._save_annotated_image(annotated_frame)

        # Update image_path on log records if saved
        for d in detections:
            if d.get("log_result") and d["log_result"].get("record"):
                rec_id = d["log_result"]["record"]["id"]
                from database import get_connection
                conn = get_connection()
                conn.cursor().execute(
                    "UPDATE vehicle_logs SET vehicle_image_path = ? WHERE id = ?",
                    (annotated_filename, rec_id)
                )
                conn.commit()
                conn.close()

        # Sort detections so successfully recognized plates appear first
        detections.sort(key=lambda d: 1 if d["plate_number"] != "SCANNING" else 0, reverse=True)

        return {
            "success": True,
            "detections": detections,
            "annotated_image_url": annotated_data_url,
            "annotated_filename": annotated_filename,
            "plate_count": len([d for d in detections if d["plate_number"] != "SCANNING"]),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def process_video_file(self, video_path: str, mode: str = "AUTO") -> Dict[str, Any]:
        """
        Processes an uploaded video file frame-by-frame using YOLO + ByteTrack + OCR.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"success": False, "message": "Failed to open video file.", "detections": []}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        output_filename = f"processed_{uuid.uuid4().hex[:8]}.mp4"
        output_filepath = os.path.join(UPLOADS_DIR, output_filename)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_filepath, fourcc, min(fps, 30.0), (frame_width, frame_height))

        line_y = int(frame_height * 0.65)
        raw_to_event = {}
        events = {}
        next_event_number = 1
        frame_idx = 0
        logged_plates = set()
        video_logs = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_idx += 1

                # Sample frames: run full YOLO track on every frame or every 2nd frame
                results = self.yolo_model.track(
                    source=frame,
                    conf=0.15,
                    persist=True,
                    verbose=False
                )

                if results and len(results) > 0 and results[0].boxes is not None:
                    boxes = results[0].boxes
                    if boxes.id is not None and len(boxes) > 0:
                        coords = boxes.xyxy.cpu().numpy()
                        track_ids = boxes.id.int().cpu().tolist()
                        confidences = (
                            boxes.conf.cpu().tolist()
                            if boxes.conf is not None
                            else [0.0] * len(track_ids)
                        )

                        for box_val, raw_id, det_conf in zip(coords, track_ids, confidences):
                            raw_id = int(raw_id)
                            x1, y1, x2, y2 = map(int, box_val)
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(frame_width, x2), min(frame_height, y2)
                            if x2 <= x1 or y2 <= y1:
                                continue

                            box = [float(x1), float(y1), float(x2), float(y2)]
                            event_id = raw_to_event.get(raw_id)
                            if not event_id:
                                event_id = f"EVENT_{next_event_number:05d}"
                                next_event_number += 1
                                raw_to_event[raw_id] = event_id
                                events[event_id] = {
                                    "id": event_id,
                                    "plate": "SCANNING",
                                    "confidence": 0.0,
                                    "last_ocr_frame": -5,
                                    "box": box,
                                    "crop": None
                                }

                            state = events[event_id]
                            state["box"] = box
                            center_y = (y1 + y2) / 2.0
                            prev_y = state.get("last_center_y")
                            state["last_center_y"] = center_y

                            # Extract OCR every 3 frames if not yet recognized or confidence below 0.85
                            if frame_idx - state["last_ocr_frame"] >= 3 and (state["plate"] == "SCANNING" or state["confidence"] < 0.85):
                                state["last_ocr_frame"] = frame_idx
                                self.reader.extract_plate_number(frame, box, event_id, single_frame=False)
                                cached_plate = self.reader.get_cached_plate(event_id)
                                cached_conf = self.reader.get_cached_confidence(event_id)
                                if cached_plate != "SCANNING" and cached_conf > state["confidence"]:
                                    state["plate"] = cached_plate
                                    state["confidence"] = cached_conf
                                    state["crop"] = self.reader.best_crops.get(event_id)

                            # Crossing detection
                            crossed = False
                            if prev_y is not None:
                                if prev_y < line_y and center_y >= line_y:
                                    crossed = True
                                elif prev_y > line_y and center_y <= line_y:
                                    crossed = True

                            curr_plate = state["plate"]
                            if curr_plate != "SCANNING" and (crossed or curr_plate not in logged_plates):
                                crop_fn = None
                                if state.get("crop") is not None:
                                    crop_fn, _ = self._save_crop(state["crop"])
                                log_res = record_detection(
                                    plate_number=curr_plate,
                                    mode=mode,
                                    confidence=state["confidence"],
                                    crop_path=crop_fn
                                )
                                logged_plates.add(curr_plate)
                                video_logs.append({
                                    "plate_number": curr_plate,
                                    "confidence": state["confidence"],
                                    "crop_path": crop_fn,
                                    "result": log_res
                                })

                            # Draw annotation
                            color = (34, 197, 94) if state["plate"] != "SCANNING" else (234, 88, 12)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(
                                frame,
                                f"{state['plate']} ({state['confidence']:.2f})",
                                (x1, max(20, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                color,
                                2
                            )

                # Draw tripwire guide line
                cv2.line(frame, (0, line_y), (frame_width, line_y), (0, 0, 255), 2)
                writer.write(frame)

        finally:
            cap.release()
            writer.release()

        return {
            "success": True,
            "total_frames": frame_idx,
            "processed_video_filename": output_filename,
            "video_logs": video_logs,
            "plates_detected": list(logged_plates)
        }

# Global singleton
model_service = None

def get_model_service() -> PlateTrackModelService:
    global model_service
    if model_service is None:
        model_service = PlateTrackModelService()
    return model_service
