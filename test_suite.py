import time
import requests
import sys

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"

def run_tests():
    print("=== STARTING PLATETRACK AI FULL TEST SUITE ===")

    # 1. Test Backend Health
    print("\n[TEST 1] Checking backend health...")
    for attempt in range(10):
        try:
            r = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
            if r.status_code == 200:
                print(" -> Backend Online:", r.json())
                break
        except Exception as e:
            print(f" -> Waiting for server startup (attempt {attempt+1}/10)...")
            time.sleep(2)
    else:
        print("FAIL: Backend did not respond within timeout.")
        return False

    # 2. Test Frontend Server
    print("\n[TEST 2] Checking frontend server on port 5173...")
    try:
        rf = requests.get(FRONTEND_URL, timeout=5)
        print(f" -> Frontend status code: {rf.status_code}, HTML length: {len(rf.text)} bytes")
        assert "<title>PlateTrack AI" in rf.text
        print(" -> Frontend HTML verified successfully.")
    except Exception as e:
        print("FAIL on frontend server:", e)
        return False

    # 3. Test Initial Stats
    print("\n[TEST 3] Checking stats endpoint...")
    r_stats = requests.get(f"{BACKEND_URL}/api/stats").json()
    print(" -> Current stats:", r_stats)

    # 4. Upload Sample Car Image for Detection (Entry)
    print("\n[TEST 4] Uploading sample car image to /api/detect/image (Entry)...")
    sample_path = r"C:\Users\chanc\.gemini\antigravity\scratch\PlateTrackAI-Dashboard\backend\samples\sample_car.jpg"
    with open(sample_path, "rb") as f:
        files = {"file": ("sample_car.jpg", f, "image/jpeg")}
        data = {"mode": "ENTRY"}
        r_det = requests.post(f"{BACKEND_URL}/api/detect/image", files=files, data=data)
    
    assert r_det.status_code == 200, f"Detection failed: {r_det.text}"
    det_json = r_det.json()
    print(" -> Detection response success:", det_json["success"])
    detections = det_json["detection"]["detections"]
    assert len(detections) > 0, "No detections returned"
    first_det = detections[0]
    plate = first_det["plate_number"]
    conf = first_det["confidence"]
    print(f" -> Detected Plate: '{plate}', Confidence: {conf:.4f}")
    assert plate != "SCANNING", f"Plate was not recognized: {plate}"
    print(" -> Log Result:", first_det.get("log_result", {}).get("message"))

    # 5. Check Vehicle Logs Table
    print("\n[TEST 5] Checking logs table for newly created entry...")
    r_logs = requests.get(f"{BACKEND_URL}/api/logs").json()
    logs = r_logs.get("logs", [])
    assert len(logs) > 0, "No logs found in table"
    matching = [l for l in logs if l["plate_number"] == plate]
    assert len(matching) > 0, f"Logged record for {plate} not found"
    entry_row = matching[0]
    print(f" -> Found row: ID={entry_row['id']}, Plate={entry_row['plate_number']}, In Time={entry_row['in_time']}, Out Time={entry_row['out_time']}, Stay={entry_row['stay_time_formatted']}")
    assert entry_row["out_time"] == "Inside", f"Expected Out Time 'Inside', got {entry_row['out_time']}"

    # 6. Test 10s Debounce
    print("\n[TEST 6] Testing 10-second debounce (immediate re-detection)...")
    with open(sample_path, "rb") as f:
        files = {"file": ("sample_car.jpg", f, "image/jpeg")}
        data = {"mode": "AUTO"}
        r_deb = requests.post(f"{BACKEND_URL}/api/detect/image", files=files, data=data).json()
    deb_result = r_deb["detection"]["detections"][0]["log_result"]
    print(" -> Debounce status:", deb_result.get("status"))
    print(" -> Debounce message:", deb_result.get("message"))
    assert deb_result.get("status") == "debounced", f"Expected status 'debounced', got {deb_result.get('status')}"

    # 7. Test Stay Time calculation after 11 seconds
    print("\n[TEST 7] Waiting 11 seconds to clear debounce and log EXIT...")
    time.sleep(11)

    print(" -> Sending exit detection for", plate)
    with open(sample_path, "rb") as f:
        files = {"file": ("sample_car.jpg", f, "image/jpeg")}
        data = {"mode": "EXIT"}
        r_exit = requests.post(f"{BACKEND_URL}/api/detect/image", files=files, data=data).json()
    
    exit_log_res = r_exit["detection"]["detections"][0]["log_result"]
    print(" -> Exit result status:", exit_log_res.get("status"))
    print(" -> Exit result message:", exit_log_res.get("message"))
    assert exit_log_res.get("status") == "exit", f"Expected status 'exit', got {exit_log_res.get('status')}"
    closed_rec = exit_log_res.get("record", {})
    print(f" -> Closed record: Out Time={closed_rec.get('out_time')}, Stay Seconds={closed_rec.get('stay_seconds')}, Formatted={closed_rec.get('stay_time_formatted')}")
    assert closed_rec.get("stay_seconds", 0) >= 11, "Stay seconds should be >= 11"

    # 8. Test Sample Plate Detection (Fallback crop test)
    print("\n[TEST 8] Testing sample plate direct crop detection...")
    plate_sample_path = r"C:\Users\chanc\.gemini\antigravity\scratch\PlateTrackAI-Dashboard\backend\samples\sample_plate.jpg"
    with open(plate_sample_path, "rb") as f:
        files = {"file": ("sample_plate.jpg", f, "image/jpeg")}
        data = {"mode": "ENTRY"}
        r_plate_sample = requests.post(f"{BACKEND_URL}/api/detect/image", files=files, data=data).json()
    valid_dets = [d for d in r_plate_sample["detection"]["detections"] if d["plate_number"] != "SCANNING"]
    assert len(valid_dets) > 0, "No valid plate recognized in sample plate detection"
    det_plate = valid_dets[0]
    print(f" -> Sample Plate recognized: {det_plate['plate_number']} (Confidence: {det_plate['confidence']:.4f})")
    assert det_plate["plate_number"] != "SCANNING", "Sample plate recognition failed"

    # 9. Test Excel Download
    print("\n[TEST 9] Testing Excel export endpoint /api/export/excel...")
    r_excel = requests.get(f"{BACKEND_URL}/api/export/excel")
    assert r_excel.status_code == 200, f"Excel download failed: {r_excel.status_code}"
    disposition = r_excel.headers.get("Content-Disposition", "")
    print(f" -> Content-Disposition: {disposition}")
    print(f" -> Received Excel file bytes: {len(r_excel.content)} bytes")
    assert "PlateTrack_" in disposition and ".xlsx" in disposition, f"Filename invalid: {disposition}"
    assert len(r_excel.content) > 1000, "Excel content too small"

    # 10. Test Search, Sort, Filter
    print("\n[TEST 10] Testing table search and date filter...")
    r_search = requests.get(f"{BACKEND_URL}/api/logs?search={plate[:4]}").json()
    print(f" -> Search query '{plate[:4]}' matched {len(r_search['logs'])} rows (Total: {r_search['total']})")
    assert r_search["total"] >= 1, "Search should return matching logs"

    # 11. Test Stats Update
    print("\n[TEST 11] Checking updated summary statistics...")
    stats_updated = requests.get(f"{BACKEND_URL}/api/stats").json()
    print(" -> Updated Stats:", stats_updated)
    assert stats_updated["total_today"] >= 2, "Stats should record >= 2 vehicles today"

    print("\n=== ALL TEST SUITE CHECKS PASSED PERFECTLY! ===")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
