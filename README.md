# 🚘 PlateTrack AI Dashboard

An intelligent full-stack AI Number Plate Recognition (ANPR) and Vehicle Entry-Exit Monitoring Dashboard running on `localhost`.

Powered by **YOLO11** (trained number plate detector weights), **PaddleOCR** (text recognition), **FastAPI**, **SQLite**, and a modern, responsive web dashboard with Dark/Light mode, live stay time tickers, webcam capture, and Excel export.

---

## 🌟 Key Features

1. **Vehicle Log Table**:
   - Columns: **S.No** (1-based), **Car Number Plate**, **In Time**, **Out Time** (or *"Inside"* badge), and **Stay Time** (`Xh Ym Zs`).
   - Vehicles currently inside display a **live-updating stay time** ticker ticking every second.
   - Clickable plate pills and thumbnails to preview cropped plate images in a high-resolution lightbox.

2. **Smart Entry / Exit Logic & 10s Debounce**:
   - First detection creates an entry record with timestamp.
   - Subsequent detection while open records the exit timestamp and computes total stay time.
   - Built-in **10-second debounce** prevents accidental duplicate logs if a vehicle lingers in front of the camera.
   - Mode selector supporting **Auto Mode**, **Entry Only**, and **Exit Only**.
   - Persistent storage in **SQLite** (`plate_track.db`).

3. **Multi-Modal Model Inputs**:
   - **Image Upload**: Upload any car photo (JPEG, PNG).
   - **Video Upload**: Processes video files frame-by-frame with tracking.
   - **Live Webcam**: Stream your webcam in-browser, capture snapshots on demand, or enable **Auto-Scan (every 2.5s)** with virtual tripwire visualizer.
   - **Sample One-Click Tests**: Includes built-in buttons for testing sample car and plate images.

4. **Excel Export (.xlsx)**:
   - One-click **"Download Excel"** button exporting all vehicle activity.
   - Columns: `S.No`, `Plate Number`, `In Time`, `Out Time`, `Stay Time`.
   - Bold header row, professional styling, auto-fitted column widths, and timestamped filename (e.g. `PlateTrack_YYYY-MM-DD.xlsx`).

5. **Dark / Light Mode**:
   - Navbar toggle with sun/moon icon.
   - Defaults to your operating system's color scheme and persists your preference in `localStorage`.

6. **Dashboard Extras**:
   - **4 Summary Cards**: Total Vehicles Today, Currently Inside, Average Stay Time, Longest Stay.
   - **Real-Time Search**: Instant filtering by license plate number.
   - **Date Filter**: Filter records by date or click "Today".
   - **Column Sorting & Pagination**: Sort by S.No, Plate, In Time, Out Time, or Stay Time with customizable rows per page (5, 10, 25, 50).
   - **Delete & Clear Controls**: Delete individual records or clear all logs with a confirmation dialog.

---

## 📁 Project Structure

```text
PlateTrackAI-Dashboard/
├── backend/
│   ├── best.pt              # Trained YOLO11 model weights
│   ├── database.py          # SQLite schema, CRUD operations & debounce logic
│   ├── excel_service.py     # openpyxl Excel generator with bold headers & auto-fit
│   ├── main.py              # FastAPI application & REST endpoints
│   ├── model_service.py     # YOLO + PaddleOCR inference wrapper
│   ├── ocr_helper.py        # PlateReader & OCR character extraction
│   ├── requirements.txt     # Python backend dependencies
│   ├── crops/               # Saved plate crops
│   ├── uploads/             # Annotated inference outputs
│   └── samples/             # Sample images for testing
├── frontend/
│   ├── index.html           # Dashboard interface (Tailwind CSS + Lucide Icons)
│   ├── app.js               # Reactive client state, live ticker & webcam
│   ├── style.css            # Custom animations & plate styling
│   ├── package.json         # Vite dev configuration
│   └── vite.config.js       # Vite proxy configuration
├── test_suite.py            # Automated end-to-end verification script
└── README.md
```

---

## 🚀 Setup & Running Locally

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Node.js (optional; Python's built-in server can also serve the frontend)

---

### Step 1: Install Backend Dependencies

Open a terminal and navigate to the `backend` folder:

```bash
cd backend
pip install -r requirements.txt
```

*(Note: dependencies include `fastapi`, `uvicorn[standard]`, `ultralytics`, `opencv-python`, `paddleocr`, `paddlepaddle`, `openpyxl`, and `python-multipart`)*

---

### Step 2: Start the Backend Server

Run Uvicorn from the `backend` directory:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The FastAPI backend will start at:
- **API Base**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Step 3: Start the Frontend

You can run the frontend using either **Vite** (Node.js) or **Python**:

#### Option A: Using Vite (Node.js)
```bash
cd frontend
npm install
npm run dev
```

#### Option B: Using Python (Zero-configuration, no Node required)
```bash
cd frontend
python -m http.server 5173
```

*(The backend also serves the frontend directly at `http://localhost:8000`)*

---

## 🌐 Final URLs

| Service | Localhost URL |
| :--- | :--- |
| **PlateTrack AI Dashboard (Frontend)** | [http://localhost:5173](http://localhost:5173) *(or [http://localhost:8000](http://localhost:8000))* |
| **FastAPI Backend & REST API** | [http://localhost:8000](http://localhost:8000) |
| **Interactive API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) |

---

## 🧪 Automated End-to-End Testing

You can run the full automated verification test suite anytime:

```bash
python test_suite.py
```

This verifies:
1. Backend health check & connectivity.
2. Frontend server response.
3. Live car image upload & plate detection (`AS04V9983`, ~99.8% confidence).
4. Entry record logging in SQLite (`Out Time = Inside`).
5. 10-second duplicate debounce logic.
6. Exit record update and stay duration calculation (`0h 0m 18s`).
7. Crop plate detection (`KA02NN1826`).
8. Excel export generation (`PlateTrack_YYYY-MM-DD.xlsx`).
9. Search, date filtering, and pagination.
10. Metric summary calculation.
