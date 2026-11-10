import requests
import json

BASE = "http://127.0.0.1:8000"

print("--- Testing Hourly Stats ---")
r_hourly = requests.get(f"{BASE}/api/stats/hourly").json()
print("Hourly traffic data:", json.dumps(r_hourly, indent=2))

print("\n--- Testing Manual Entry Log ---")
r_manual = requests.post(f"{BASE}/api/logs/manual", json={"plate_number": "MH12AB9999", "mode": "AUTO"}).json()
print("Manual log response:", r_manual.get("result", {}).get("message"))

print("\n--- Testing Video Sample Inference ---")
r_video = requests.post(f"{BASE}/api/detect/sample?type=video&mode=AUTO").json()
print("Video sample response:", r_video.get("success"), "Total frames:", r_video.get("result", {}).get("total_frames"))

print("\n--- Testing Excel Export ---")
r_excel = requests.get(f"{BASE}/api/export/excel")
print("Excel status:", r_excel.status_code, "Bytes:", len(r_excel.content), "Filename:", r_excel.headers.get("Content-Disposition"))

print("\n--- Testing Table Fetch ---")
r_logs = requests.get(f"{BASE}/api/logs?page=1&per_page=10").json()
print(f"Total entries: {r_logs.get('total')}, Page: {r_logs.get('page')}/{r_logs.get('total_pages')}")
for item in r_logs.get("logs", [])[:4]:
    print(f"  Row {item['id']}: Plate={item['plate_number']}, In={item['in_time']}, Out={item['out_time']}, Stay={item['stay_time_formatted']}")

print("\nALL VERIFICATION STEPS COMPLETE!")
