/**
 * PlateTrack AI — Full Stack Dashboard Client
 */

// Determine API base URL (FastAPI backend runs on port 8000)
const API_BASE = window.location.port === "8000" ? window.location.origin : "http://localhost:8000";

// State
let currentMode = "AUTO"; // AUTO, ENTRY, EXIT
let logs = [];
let currentPage = 1;
let perPage = 10;
let totalPages = 1;
let totalLogs = 0;
let sortBy = "id";
let sortOrder = "desc";
let searchQuery = "";
let dateFilter = "";

let selectedFile = null;
let webcamStream = null;
let autoScanTimer = null;
let liveTickerTimer = null;

// DOM Elements
const modeAutoBtn = document.getElementById("mode-auto");
const modeEntryBtn = document.getElementById("mode-entry");
const modeExitBtn = document.getElementById("mode-exit");

const themeToggleBtn = document.getElementById("theme-toggle");
const themeIconSun = document.getElementById("theme-icon-sun");
const themeIconMoon = document.getElementById("theme-icon-moon");

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const fileInfoPill = document.getElementById("file-info-pill");
const fileNameText = document.getElementById("file-name-text");

const btnRunDetect = document.getElementById("btn-run-detect");
const btnRunEntry = document.getElementById("btn-run-entry");
const btnRunExit = document.getElementById("btn-run-exit");
const btnSampleTest = document.getElementById("btn-sample-test");
const btnSamplePlate = document.getElementById("btn-sample-plate");

const tabUploadBtn = document.getElementById("tab-upload-btn");
const tabWebcamBtn = document.getElementById("tab-webcam-btn");
const tabUploadContent = document.getElementById("tab-upload-content");
const tabWebcamContent = document.getElementById("tab-webcam-content");

const webcamVideo = document.getElementById("webcam-video");
const webcamCanvas = document.getElementById("webcam-canvas");
const webcamPlaceholder = document.getElementById("webcam-placeholder");
const btnWebcamStart = document.getElementById("btn-webcam-start");
const btnWebcamStop = document.getElementById("btn-webcam-stop");
const btnWebcamCapture = document.getElementById("btn-webcam-capture");
const btnWebcamAuto = document.getElementById("btn-webcam-auto");
const autoScanLabel = document.getElementById("auto-scan-label");

const previewImage = document.getElementById("preview-image");
const previewPlaceholder = document.getElementById("preview-placeholder");
const previewPlateBadge = document.getElementById("preview-plate-badge");
const previewConfidence = document.getElementById("preview-confidence");
const previewCropImg = document.getElementById("preview-crop-img");
const cropThumbnailPlaceholder = document.getElementById("crop-thumbnail-placeholder");
const detectionStatusPill = document.getElementById("detection-status-pill");
const detectionMsgBanner = document.getElementById("detection-msg-banner");
const detectionMsgText = document.getElementById("detection-msg-text");
const detectionMsgIcon = document.getElementById("detection-msg-icon");
const inferenceTime = document.getElementById("inference-time");
const btnExpandImage = document.getElementById("btn-expand-image");

const logsTbody = document.getElementById("logs-tbody");
const filterSearch = document.getElementById("filter-search");
const filterDate = document.getElementById("filter-date");
const btnDateToday = document.getElementById("btn-date-today");
const btnDateClear = document.getElementById("btn-date-clear");
const selectPerPage = document.getElementById("select-per-page");

const btnPrevPage = document.getElementById("btn-prev-page");
const btnNextPage = document.getElementById("btn-next-page");
const pageNumbersContainer = document.getElementById("page-numbers");
const paginationSummary = document.getElementById("pagination-summary");

const btnExportExcel = document.getElementById("btn-export-excel");
const btnExportExcelTop = document.getElementById("btn-export-excel-top");
const btnRefreshLogs = document.getElementById("btn-refresh-logs");
const btnClearLogs = document.getElementById("btn-clear-logs");

const modalClearConfirm = document.getElementById("modal-clear-confirm");
const btnCancelClear = document.getElementById("btn-cancel-clear");
const btnConfirmClear = document.getElementById("btn-confirm-clear");

const modalLightbox = document.getElementById("modal-image-lightbox");
const lightboxImage = document.getElementById("lightbox-image");
const lightboxTitle = document.getElementById("lightbox-title");
const btnCloseLightbox = document.getElementById("btn-close-lightbox");

const toastContainer = document.getElementById("toast-container");

// ============================================================
// THEME MANAGEMENT (DARK / LIGHT)
// ============================================================
function initTheme() {
  const savedTheme = localStorage.getItem("platetrack_theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  
  if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
    document.documentElement.classList.add("dark");
    themeIconSun.classList.remove("hidden");
    themeIconMoon.classList.add("hidden");
  } else {
    document.documentElement.classList.remove("dark");
    themeIconSun.classList.add("hidden");
    themeIconMoon.classList.remove("hidden");
  }
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle("dark");
  localStorage.setItem("platetrack_theme", isDark ? "dark" : "light");
  if (isDark) {
    themeIconSun.classList.remove("hidden");
    themeIconMoon.classList.add("hidden");
  } else {
    themeIconSun.classList.add("hidden");
    themeIconMoon.classList.remove("hidden");
  }

  if (typeof trafficChartInstance !== "undefined" && trafficChartInstance) {
    const textColor = isDark ? "#94a3b8" : "#64748b";
    const gridColor = isDark ? "rgba(51, 65, 85, 0.4)" : "rgba(226, 232, 240, 0.8)";
    trafficChartInstance.options.scales.x.ticks.color = textColor;
    trafficChartInstance.options.scales.y.ticks.color = textColor;
    trafficChartInstance.options.scales.y.grid.color = gridColor;
    trafficChartInstance.options.plugins.tooltip.backgroundColor = isDark ? "#1e293b" : "#ffffff";
    trafficChartInstance.options.plugins.tooltip.titleColor = isDark ? "#f8fafc" : "#0f172a";
    trafficChartInstance.options.plugins.tooltip.bodyColor = isDark ? "#cbd5e1" : "#334155";
    trafficChartInstance.options.plugins.tooltip.borderColor = isDark ? "#334155" : "#e2e8f0";
    trafficChartInstance.update();
  }
}

// ============================================================
// MODE SWITCHER
// ============================================================
function setMode(mode) {
  currentMode = mode;
  [modeAutoBtn, modeEntryBtn, modeExitBtn].forEach(btn => {
    btn.classList.remove("active");
  });
  if (mode === "AUTO") modeAutoBtn.classList.add("active");
  else if (mode === "ENTRY") modeEntryBtn.classList.add("active");
  else if (mode === "EXIT") modeExitBtn.classList.add("active");
  showToast(`Operating mode set to: ${mode}`, "info");
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "toast-animate p-3 rounded-xl shadow-lg border text-xs font-medium flex items-center space-x-2 text-white pointer-events-auto";
  
  let bg = "bg-slate-900 border-slate-700";
  let icon = "info";
  if (type === "success") {
    bg = "bg-emerald-600 border-emerald-500";
    icon = "check-circle";
  } else if (type === "warning") {
    bg = "bg-amber-600 border-amber-500";
    icon = "alert-circle";
  } else if (type === "error") {
    bg = "bg-rose-600 border-rose-500";
    icon = "alert-triangle";
  }

  toast.className += ` ${bg}`;
  toast.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4 shrink-0"></i><span>${message}</span>`;
  toastContainer.appendChild(toast);
  lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ============================================================
// TIME FORMATTING & LIVE STAY TICKER
// ============================================================
function formatStayTime(seconds) {
  if (seconds === null || seconds === undefined || seconds < 0) return "0h 0m 0s";
  seconds = Math.floor(seconds);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remSeconds = seconds % 60;
  return `${hours}h ${minutes}m ${remSeconds}s`;
}

function parseDate(timestr) {
  if (!timestr) return new Date();
  return new Date(timestr.replace(" ", "T"));
}

function startLiveStayTicker() {
  if (liveTickerTimer) clearInterval(liveTickerTimer);
  liveTickerTimer = setInterval(() => {
    const liveSpans = document.querySelectorAll(".live-stay-span");
    const now = Date.now();
    liveSpans.forEach(span => {
      const inTimeStr = span.getAttribute("data-in-time");
      if (inTimeStr) {
        const inMs = parseDate(inTimeStr).getTime();
        const diffSeconds = Math.max(0, Math.floor((now - inMs) / 1000));
        span.textContent = formatStayTime(diffSeconds);
      }
    });
  }, 1000);
}

// ============================================================
// FETCH STATS & LOGS
// ============================================================
async function fetchSummaryStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error("Failed to fetch stats");
    const data = await res.json();
    document.getElementById("stat-total-today").textContent = data.total_today ?? 0;
    document.getElementById("stat-unique-today").textContent = data.unique_plates_today ?? 0;
    document.getElementById("stat-currently-inside").textContent = data.currently_inside ?? 0;
    document.getElementById("stat-avg-stay").textContent = data.avg_stay_formatted ?? "0h 0m 0s";
    document.getElementById("stat-longest-stay").textContent = data.longest_stay_formatted ?? "0h 0m 0s";
  } catch (err) {
    console.error("Stats fetch error:", err);
  }
}

async function fetchLogs() {
  try {
    const params = new URLSearchParams({
      search: searchQuery,
      date_filter: dateFilter,
      sort_by: sortBy,
      sort_order: sortOrder,
      page: currentPage,
      per_page: perPage
    });

    const res = await fetch(`${API_BASE}/api/logs?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch logs");
    const data = await res.json();

    logs = data.logs || [];
    totalLogs = data.total || 0;
    totalPages = data.total_pages || 1;
    currentPage = data.page || 1;

    renderLogsTable();
    renderPagination();
    fetchSummaryStats();
  } catch (err) {
    console.error("Logs fetch error:", err);
    logsTbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-6 text-center text-rose-500">
          Failed to connect to backend server at ${API_BASE}. Ensure the FastAPI server is running.
        </td>
      </tr>
    `;
  }
}

// ============================================================
// RENDER VEHICLE LOG TABLE
// ============================================================
function renderLogsTable() {
  if (!logs || logs.length === 0) {
    logsTbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-8 text-center text-slate-400">
          <div class="flex flex-col items-center space-y-2">
            <i data-lucide="inbox" class="w-8 h-8 text-slate-300 dark:text-slate-600"></i>
            <p>No vehicle logs matching your filter.</p>
          </div>
        </td>
      </tr>
    `;
    lucide.createIcons();
    return;
  }

  const startSNo = (currentPage - 1) * perPage + 1;

  logsTbody.innerHTML = logs.map((log, index) => {
    const sNo = startSNo + index;
    const isInside = !log.out_time || log.out_time === "Inside";
    
    // Status Badge & Stay Time
    let outTimeHtml = "";
    let stayTimeHtml = "";

    if (isInside) {
      outTimeHtml = `
        <span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
          <span>Inside</span>
        </span>
      `;
      stayTimeHtml = `
        <span class="live-stay-span stay-time-live font-mono font-bold text-indigo-600 dark:text-indigo-400" data-in-time="${log.in_time}">
          ${log.stay_time_formatted || "0h 0m 0s"}
        </span>
      `;
    } else {
      outTimeHtml = `<span class="text-slate-700 dark:text-slate-300 font-mono">${log.out_time}</span>`;
      stayTimeHtml = `<span class="font-mono text-slate-700 dark:text-slate-300 font-semibold">${log.stay_time_formatted || "0h 0m 0s"}</span>`;
    }

    // Crop Thumbnail
    const cropImgUrl = log.plate_crop_path ? `${API_BASE}/crops/${log.plate_crop_path}` : null;
    const cropHtml = cropImgUrl ? `
      <div class="flex items-center space-x-2">
        <button class="w-12 h-7 rounded border border-slate-300 dark:border-slate-700 overflow-hidden bg-slate-100 dark:bg-slate-800 hover:scale-110 transition-transform btn-view-crop" data-src="${cropImgUrl}" data-plate="${log.plate_number}" title="View crop">
          <img src="${cropImgUrl}" alt="${log.plate_number}" class="w-full h-full object-cover">
        </button>
        <span class="text-[10px] text-slate-500 font-mono">${(log.confidence * 100).toFixed(0)}%</span>
      </div>
    ` : `<span class="text-slate-400 text-[10px]">N/A</span>`;

    return `
      <tr class="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
        <td class="py-3 px-4 font-mono text-slate-500">${sNo}</td>
        <td class="py-3 px-4">
          <span class="number-plate-pill cursor-pointer" onclick="openLightboxForPlate('${log.plate_number}', '${cropImgUrl || ''}')">
            ${log.plate_number}
          </span>
        </td>
        <td class="py-3 px-4 text-slate-700 dark:text-slate-300 font-mono">${log.in_time}</td>
        <td class="py-3 px-4">${outTimeHtml}</td>
        <td class="py-3 px-4">${stayTimeHtml}</td>
        <td class="py-3 px-4">${cropHtml}</td>
        <td class="py-3 px-4 text-right">
          ${isInside ? `
            <button class="px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 dark:hover:bg-rose-900/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900 transition-colors btn-exit-row mr-1.5 inline-flex items-center space-x-1" data-plate="${log.plate_number}" title="Check out / record exit">
              <i data-lucide="log-out" class="w-3 h-3"></i>
              <span>Exit</span>
            </button>
          ` : ""}
          <button class="p-1 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors btn-delete-row" data-id="${log.id}" title="Delete record">
            <i data-lucide="trash" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `;
  }).join("");

  lucide.createIcons();

  // Attach delete buttons
  document.querySelectorAll(".btn-delete-row").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-id");
      if (confirm(`Delete vehicle record #${id}?`)) {
        await deleteSingleLog(id);
      }
    });
  });

  // Attach exit buttons
  document.querySelectorAll(".btn-exit-row").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const plate = btn.getAttribute("data-plate");
      try {
        const res = await fetch(`${API_BASE}/api/logs/manual`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plate_number: plate, mode: "EXIT" })
        });
        if (!res.ok) throw new Error("Failed to record vehicle exit.");
        const data = await res.json();
        if (data.result) {
          showDetectionEventMessage(data.result);
        }
        fetchLogs();
        fetchSummaryStats();
        updateTrafficChart();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // Attach crop view buttons
  document.querySelectorAll(".btn-view-crop").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const src = btn.getAttribute("data-src");
      const plate = btn.getAttribute("data-plate");
      openLightbox(src, `Cropped Plate: ${plate}`);
    });
  });
}

function openLightboxForPlate(plate, cropUrl) {
  if (cropUrl) {
    openLightbox(cropUrl, `Plate Crop: ${plate}`);
  }
}

// ============================================================
// PAGINATION
// ============================================================
function renderPagination() {
  const start = totalLogs === 0 ? 0 : (currentPage - 1) * perPage + 1;
  const end = Math.min(currentPage * perPage, totalLogs);
  paginationSummary.textContent = `Showing ${start} to ${end} of ${totalLogs} entries`;

  btnPrevPage.disabled = currentPage <= 1;
  btnNextPage.disabled = currentPage >= totalPages;

  pageNumbersContainer.innerHTML = "";
  for (let i = 1; i <= Math.min(totalPages, 5); i++) {
    const pageBtn = document.createElement("button");
    pageBtn.className = `px-3 py-1.5 rounded-lg text-xs font-semibold ${
      i === currentPage
        ? "bg-indigo-600 text-white"
        : "border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
    }`;
    pageBtn.textContent = i;
    pageBtn.addEventListener("click", () => {
      currentPage = i;
      fetchLogs();
    });
    pageNumbersContainer.appendChild(pageBtn);
  }
}

// ============================================================
// DETECTION EXECUTION (IMAGE & VIDEO)
// ============================================================
async function executeDetection(modeOverride = null) {
  if (!selectedFile) {
    showToast("Please choose or drop an image or video file first.", "warning");
    fileInput.click();
    return;
  }

  const modeToUse = modeOverride || currentMode;
  const isVideo = selectedFile.type.startsWith("video/") || selectedFile.name.match(/\.(mp4|avi|mov|mkv)$/i);
  const endpoint = isVideo ? `${API_BASE}/api/detect/video` : `${API_BASE}/api/detect/image`;

  setDetectionLoading(true);
  const startTime = performance.now();

  try {
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("mode", modeToUse);

    const res = await fetch(endpoint, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Detection failed on server.");
    }

    const data = await res.json();
    const duration = ((performance.now() - startTime) / 1000).toFixed(2);
    inferenceTime.textContent = `${duration}s`;

    if (isVideo) {
      handleVideoDetectionResult(data);
    } else {
      handleImageDetectionResult(data.detection);
    }

    fetchLogs();
    fetchSummaryStats();
  } catch (err) {
    console.error("Detection error:", err);
    showToast(`Error: ${err.message}`, "error");
    detectionStatusPill.textContent = "Error";
    detectionStatusPill.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700";
  } finally {
    setDetectionLoading(false);
  }
}

function setDetectionLoading(isLoading) {
  btnRunDetect.disabled = isLoading;
  btnRunEntry.disabled = isLoading;
  btnRunExit.disabled = isLoading;
  if (isLoading) {
    detectionStatusPill.textContent = "Processing...";
    detectionStatusPill.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 animate-pulse";
  }
}

function handleImageDetectionResult(det) {
  const previewVideo = document.getElementById("preview-video");
  if (previewVideo) {
    previewVideo.pause();
    previewVideo.classList.add("hidden");
  }

  if (!det || !det.success) {
    showToast("No valid detection output.", "warning");
    return;
  }

  // Annotated image preview
  if (det.annotated_image_url) {
    previewImage.src = det.annotated_image_url;
    previewImage.classList.remove("hidden");
    previewPlaceholder.classList.add("hidden");
    btnExpandImage.classList.remove("hidden");
  }

  const detections = det.detections || [];
  const validDets = detections.filter(d => d.plate_number !== "SCANNING");

  if (validDets.length > 0) {
    const topDet = validDets[0];
    previewPlateBadge.textContent = topDet.plate_number;
    previewConfidence.textContent = `${(topDet.confidence * 100).toFixed(1)}%`;

    if (topDet.crop_url) {
      previewCropImg.src = topDet.crop_url;
      previewCropImg.classList.remove("hidden");
      cropThumbnailPlaceholder.classList.add("hidden");
    }

    // Status pill
    detectionStatusPill.textContent = "Recognized";
    detectionStatusPill.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800";

    // Handle log status
    const logRes = topDet.log_result;
    if (logRes) {
      showDetectionEventMessage(logRes);
    }
  } else {
    previewPlateBadge.textContent = "NO PLATE FOUND";
    previewConfidence.textContent = "0.0%";
    detectionStatusPill.textContent = "No Plate";
    detectionStatusPill.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800";
    showToast("No license plate detected in this image.", "warning");
  }
}

function handleVideoDetectionResult(data) {
  const res = data.result || {};
  const plates = res.plates_detected || [];
  previewPlateBadge.textContent = plates.length > 0 ? plates.join(", ") : "NO PLATES";
  previewConfidence.textContent = `${plates.length} plates detected`;
  detectionStatusPill.textContent = "Video Processed";
  detectionStatusPill.className = "text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800";
  showToast(`Video processed successfully. Detected: ${plates.length} vehicles.`, "success");

  // Show processed video playback if available
  if (res.processed_video_filename) {
    const videoUrl = `${API_BASE}/uploads/${res.processed_video_filename}`;
    const previewVideo = document.getElementById("preview-video");
    if (previewVideo) {
      previewVideo.src = videoUrl;
      previewVideo.classList.remove("hidden");
      previewImage.classList.add("hidden");
      previewPlaceholder.classList.add("hidden");
      previewVideo.play().catch(() => {});
    }
  }
}

function showDetectionEventMessage(logRes) {
  detectionMsgBanner.classList.remove("hidden");
  detectionMsgText.textContent = logRes.message || "Event recorded.";

  if (logRes.status === "entry") {
    detectionMsgBanner.className = "p-3 rounded-xl text-xs font-medium border flex items-center space-x-2 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800";
    showToast(`🟢 ${logRes.message}`, "success");
  } else if (logRes.status === "exit") {
    detectionMsgBanner.className = "p-3 rounded-xl text-xs font-medium border flex items-center space-x-2 bg-rose-50 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800";
    showToast(`🔴 ${logRes.message}`, "success");
  } else if (logRes.status === "debounced") {
    detectionMsgBanner.className = "p-3 rounded-xl text-xs font-medium border flex items-center space-x-2 bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800";
    showToast(`⏳ ${logRes.message}`, "warning");
  } else {
    detectionMsgBanner.className = "p-3 rounded-xl text-xs font-medium border flex items-center space-x-2 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700";
    showToast(logRes.message, "info");
  }
}

// ============================================================
// WEBCAM STREAMING & CAPTURE
// ============================================================
async function startWebcam() {
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" }
    });
    webcamVideo.srcObject = webcamStream;
    webcamPlaceholder.classList.add("hidden");
    btnWebcamStart.classList.add("hidden");
    btnWebcamStop.classList.remove("hidden");
    btnWebcamCapture.disabled = false;
    showToast("Webcam started successfully.", "success");
  } catch (err) {
    console.error("Webcam error:", err);
    showToast("Could not access webcam. Check browser camera permissions.", "error");
  }
}

function stopWebcam() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  webcamVideo.srcObject = null;
  webcamPlaceholder.classList.remove("hidden");
  btnWebcamStart.classList.remove("hidden");
  btnWebcamStop.classList.add("hidden");
  btnWebcamCapture.disabled = true;
  stopAutoScan();
}

function captureWebcamFrame() {
  if (!webcamStream) return null;
  const ctx = webcamCanvas.getContext("2d");
  webcamCanvas.width = webcamVideo.videoWidth || 640;
  webcamCanvas.height = webcamVideo.videoHeight || 480;
  ctx.drawImage(webcamVideo, 0, 0, webcamCanvas.width, webcamCanvas.height);
  return webcamCanvas.toDataURL("image/jpeg", 0.9);
}

async function runWebcamDetection() {
  const dataUrl = captureWebcamFrame();
  if (!dataUrl) return;

  setDetectionLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/detect/webcam`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl, mode: currentMode })
    });
    if (!res.ok) throw new Error("Webcam detection failed on server.");
    const data = await res.json();
    handleImageDetectionResult(data.detection);
    fetchLogs();
    fetchSummaryStats();
  } catch (err) {
    console.error("Webcam inference error:", err);
  } finally {
    setDetectionLoading(false);
  }
}

function toggleAutoScan() {
  if (autoScanTimer) {
    stopAutoScan();
  } else {
    if (!webcamStream) {
      showToast("Start webcam first before activating Auto-Scan.", "warning");
      return;
    }
    autoScanTimer = setInterval(runWebcamDetection, 2500);
    autoScanLabel.textContent = "Auto-Scan: ON";
    btnWebcamAuto.classList.add("bg-indigo-600", "text-white");
    showToast("Auto-Scan enabled (scanning every 2.5s).", "info");
  }
}

function stopAutoScan() {
  if (autoScanTimer) {
    clearInterval(autoScanTimer);
    autoScanTimer = null;
    autoScanLabel.textContent = "Auto-Scan: OFF";
    btnWebcamAuto.classList.remove("bg-indigo-600", "text-white");
  }
}

// ============================================================
// EXCEL EXPORT
// ============================================================
function downloadExcel() {
  showToast("Generating Excel file with auto-fit columns...", "info");
  window.location.href = `${API_BASE}/api/export/excel`;
}

// ============================================================
// DELETE & CLEAR LOGS
// ============================================================
async function deleteSingleLog(id) {
  try {
    const res = await fetch(`${API_BASE}/api/logs/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete log");
    showToast(`Log #${id} deleted.`, "success");
    fetchLogs();
  } catch (err) {
    showToast(`Failed to delete log: ${err.message}`, "error");
  }
}

async function clearAllLogs() {
  try {
    const res = await fetch(`${API_BASE}/api/logs`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to clear logs");
    const data = await res.json();
    showToast(data.message || "All records cleared.", "success");
    modalClearConfirm.classList.add("hidden");
    fetchLogs();
  } catch (err) {
    showToast(`Failed to clear logs: ${err.message}`, "error");
  }
}

// ============================================================
// SAMPLE DATA SHORTCUTS
// ============================================================
async function loadSampleCar() {
  try {
    showToast("Loading test car sample...", "info");
    const res = await fetch(`${API_BASE}/runs/detect/predict/test_img.jpg`).catch(() => null);
    // If runs not mounted, fetch from repo/uploads or create a sample
    const sampleBlob = await fetch(`${API_BASE}/uploads/test_img.jpg`).catch(() => null);
    
    // We can directly call detection with a sample path or convert to file
    const sampleRes = await fetch(`${API_BASE}/api/detect/image`, {
      method: "POST",
      body: (() => {
        // We'll upload sample via file input simulation
        const fd = new FormData();
        return fd;
      })()
    }).catch(() => null);
  } catch (e) {}
}

// ============================================================
// LIGHTBOX MODAL
// ============================================================
function openLightbox(src, title = "Detection Full View") {
  lightboxImage.src = src;
  lightboxTitle.textContent = title;
  modalLightbox.classList.remove("hidden");
}

function closeLightbox() {
  modalLightbox.classList.add("hidden");
  lightboxImage.src = "";
}

// ============================================================
// EVENT LISTENERS INITIALIZATION
// ============================================================
function initEventListeners() {
  // Theme toggle
  themeToggleBtn.addEventListener("click", toggleTheme);

  // Mode switcher
  modeAutoBtn.addEventListener("click", () => setMode("AUTO"));
  modeEntryBtn.addEventListener("click", () => setMode("ENTRY"));
  modeExitBtn.addEventListener("click", () => setMode("EXIT"));

  // Tabs
  tabUploadBtn.addEventListener("click", () => {
    tabUploadBtn.classList.add("active", "border-indigo-600", "text-indigo-600", "dark:text-indigo-400");
    tabUploadBtn.classList.remove("border-transparent", "text-slate-500");
    tabWebcamBtn.classList.remove("active", "border-indigo-600", "text-indigo-600", "dark:text-indigo-400");
    tabWebcamBtn.classList.add("border-transparent", "text-slate-500");
    tabUploadContent.classList.remove("hidden");
    tabWebcamContent.classList.add("hidden");
  });

  tabWebcamBtn.addEventListener("click", () => {
    tabWebcamBtn.classList.add("active", "border-indigo-600", "text-indigo-600", "dark:text-indigo-400");
    tabWebcamBtn.classList.remove("border-transparent", "text-slate-500");
    tabUploadBtn.classList.remove("active", "border-indigo-600", "text-indigo-600", "dark:text-indigo-400");
    tabUploadBtn.classList.add("border-transparent", "text-slate-500");
    tabWebcamContent.classList.remove("hidden");
    tabUploadContent.classList.add("hidden");
  });

  // Dropzone file handling
  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      selectedFile = e.target.files[0];
      fileNameText.textContent = `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(0)} KB)`;
      fileInfoPill.classList.remove("hidden");
      fileInfoPill.classList.add("flex");
    }
  });

  ["dragenter", "dragover"].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add("border-indigo-500", "bg-indigo-50/40");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove("border-indigo-500", "bg-indigo-50/40");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectedFile = e.dataTransfer.files[0];
      fileNameText.textContent = `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(0)} KB)`;
      fileInfoPill.classList.remove("hidden");
      fileInfoPill.classList.add("flex");
    }
  });

  // Run detection buttons
  btnRunDetect.addEventListener("click", () => executeDetection());
  btnRunEntry.addEventListener("click", () => executeDetection("ENTRY"));
  btnRunExit.addEventListener("click", () => executeDetection("EXIT"));

  // Webcam buttons
  btnWebcamStart.addEventListener("click", startWebcam);
  btnWebcamStop.addEventListener("click", stopWebcam);
  btnWebcamCapture.addEventListener("click", runWebcamDetection);
  btnWebcamAuto.addEventListener("click", toggleAutoScan);

  // Sample tests
  btnSampleTest.addEventListener("click", async () => {
    try {
      showToast("Loading and detecting sample car...", "info");
      const res = await fetch(`${API_BASE}/api/sample-image?type=car`);
      if (res.ok) {
        const blob = await res.blob();
        selectedFile = new File([blob], "sample_car.jpg", { type: "image/jpeg" });
        fileNameText.textContent = `sample_car.jpg (${(selectedFile.size / 1024).toFixed(0)} KB)`;
        fileInfoPill.classList.remove("hidden");
        fileInfoPill.classList.add("flex");
        executeDetection();
      } else {
        triggerSample("car");
      }
    } catch (e) {
      triggerSample("car");
    }
  });

  btnSamplePlate.addEventListener("click", async () => {
    try {
      showToast("Loading and detecting sample plate...", "info");
      const res = await fetch(`${API_BASE}/api/sample-image?type=plate`);
      if (res.ok) {
        const blob = await res.blob();
        selectedFile = new File([blob], "sample_plate.jpg", { type: "image/jpeg" });
        fileNameText.textContent = `sample_plate.jpg (${(selectedFile.size / 1024).toFixed(0)} KB)`;
        fileInfoPill.classList.remove("hidden");
        fileInfoPill.classList.add("flex");
        executeDetection();
      } else {
        triggerSample("plate");
      }
    } catch (e) {
      triggerSample("plate");
    }
  });

  // Excel export buttons
  btnExportExcel.addEventListener("click", downloadExcel);
  btnExportExcelTop.addEventListener("click", downloadExcel);

  // Refresh logs
  btnRefreshLogs.addEventListener("click", () => {
    fetchLogs();
    showToast("Logs refreshed.", "info");
  });

  // Clear logs modal
  btnClearLogs.addEventListener("click", () => modalClearConfirm.classList.remove("hidden"));
  btnCancelClear.addEventListener("click", () => modalClearConfirm.classList.add("hidden"));
  btnConfirmClear.addEventListener("click", clearAllLogs);

  // Lightbox
  btnExpandImage.addEventListener("click", () => {
    if (previewImage.src) {
      openLightbox(previewImage.src, "Annotated Model Output");
    }
  });
  btnCloseLightbox.addEventListener("click", closeLightbox);
  modalLightbox.addEventListener("click", (e) => {
    if (e.target === modalLightbox) closeLightbox();
  });

  // Filters & Search
  filterSearch.addEventListener("input", (e) => {
    searchQuery = e.target.value.trim();
    currentPage = 1;
    fetchLogs();
  });

  filterDate.addEventListener("change", (e) => {
    dateFilter = e.target.value;
    currentPage = 1;
    fetchLogs();
  });

  btnDateToday.addEventListener("click", () => {
    const today = new Date().toISOString().split("T")[0];
    filterDate.value = today;
    dateFilter = today;
    currentPage = 1;
    fetchLogs();
  });

  btnDateClear.addEventListener("click", () => {
    filterDate.value = "";
    dateFilter = "";
    currentPage = 1;
    fetchLogs();
  });

  selectPerPage.addEventListener("change", (e) => {
    perPage = parseInt(e.target.value, 10);
    currentPage = 1;
    fetchLogs();
  });

  // Sortable headers
  document.querySelectorAll(".sortable-header").forEach(header => {
    header.addEventListener("click", () => {
      const col = header.getAttribute("data-col");
      if (sortBy === col) {
        sortOrder = sortOrder === "asc" ? "desc" : "asc";
      } else {
        sortBy = col;
        sortOrder = "desc";
      }
      fetchLogs();
    });
  });

  // Sample video button
  const btnSampleVideo = document.getElementById("btn-sample-video");
  if (btnSampleVideo) {
    btnSampleVideo.addEventListener("click", () => triggerSample("video"));
  }

  // Manual entry modal
  const modalManualEntry = document.getElementById("modal-manual-entry");
  const btnManualEntry = document.getElementById("btn-manual-entry");
  const btnCloseManual = document.getElementById("btn-close-manual");
  const btnCancelManual = document.getElementById("btn-cancel-manual");
  const btnSubmitManual = document.getElementById("btn-submit-manual");
  const manualPlateInput = document.getElementById("manual-plate-input");
  let manualSelectedMode = "AUTO";

  if (btnManualEntry) {
    btnManualEntry.addEventListener("click", () => {
      modalManualEntry.classList.remove("hidden");
      manualPlateInput.value = "";
      manualPlateInput.focus();
    });
    btnCloseManual.addEventListener("click", () => modalManualEntry.classList.add("hidden"));
    btnCancelManual.addEventListener("click", () => modalManualEntry.classList.add("hidden"));

    document.querySelectorAll(".manual-mode-opt").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".manual-mode-opt").forEach(b => {
          b.classList.remove("active", "border-indigo-500", "bg-indigo-50", "dark:bg-indigo-950/60", "text-indigo-600", "dark:text-indigo-300", "font-semibold");
          b.classList.add("border-slate-200", "dark:border-slate-700", "text-slate-600", "dark:text-slate-300");
        });
        btn.classList.add("active", "border-indigo-500", "bg-indigo-50", "dark:bg-indigo-950/60", "text-indigo-600", "dark:text-indigo-300", "font-semibold");
        manualSelectedMode = btn.getAttribute("data-mode");
      });
    });

    btnSubmitManual.addEventListener("click", async () => {
      const plate = manualPlateInput.value.trim().toUpperCase();
      if (!plate) {
        showToast("Please enter a license plate number.", "warning");
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/logs/manual`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plate_number: plate, mode: manualSelectedMode })
        });
        if (!res.ok) throw new Error("Failed to record manual log.");
        const data = await res.json();
        modalManualEntry.classList.add("hidden");
        if (data.result) {
          showDetectionEventMessage(data.result);
        }
        fetchLogs();
        fetchSummaryStats();
        updateTrafficChart();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }
}

// ============================================================
// TRAFFIC HOURLY CHART (CHART.JS)
// ============================================================
let trafficChartInstance = null;

async function initTrafficChart() {
  const ctx = document.getElementById("traffic-chart");
  if (!ctx || typeof Chart === "undefined") return;

  const isDark = document.documentElement.classList.contains("dark");
  const textColor = isDark ? "#94a3b8" : "#64748b";
  const gridColor = isDark ? "rgba(51, 65, 85, 0.4)" : "rgba(226, 232, 240, 0.8)";

  trafficChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"],
      datasets: [
        {
          label: "Vehicle Entries",
          data: [0, 0, 0, 0, 0, 0, 0, 0],
          backgroundColor: "#6366f1",
          borderRadius: 6,
          barThickness: 16
        },
        {
          label: "Vehicle Exits",
          data: [0, 0, 0, 0, 0, 0, 0, 0],
          backgroundColor: "#f43f5e",
          borderRadius: 6,
          barThickness: 16
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          titleColor: isDark ? "#f8fafc" : "#0f172a",
          bodyColor: isDark ? "#cbd5e1" : "#334155",
          borderColor: isDark ? "#334155" : "#e2e8f0",
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textColor, font: { size: 11, family: "'JetBrains Mono', monospace" } }
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: {
            stepSize: 1,
            color: textColor,
            font: { size: 11 }
          }
        }
      }
    }
  });

  updateTrafficChart();
}

async function updateTrafficChart() {
  if (!trafficChartInstance) return;
  try {
    const res = await fetch(`${API_BASE}/api/stats/hourly`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.hours && data.hours.length > 0) {
      trafficChartInstance.data.labels = data.hours;
      trafficChartInstance.data.datasets[0].data = data.entries || [];
      trafficChartInstance.data.datasets[1].data = data.exits || [];
      trafficChartInstance.update();
    }
  } catch (err) {
    console.warn("Could not update traffic chart:", err);
  }
}

// Sample trigger helper
async function triggerSample(type) {
  setDetectionLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/detect/sample?type=${type}&mode=${currentMode}`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to run sample detection.");
    const data = await res.json();
    if (type === "video") {
      handleVideoDetectionResult(data);
    } else {
      handleImageDetectionResult(data.detection);
    }
    fetchLogs();
    fetchSummaryStats();
    updateTrafficChart();
  } catch (err) {
    showToast(`Sample test: ${err.message}`, "error");
  } finally {
    setDetectionLoading(false);
  }
}

// ============================================================
// APPLICATION STARTUP
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initEventListeners();
  initTrafficChart();
  fetchLogs();
  fetchSummaryStats();
  startLiveStayTicker();
  lucide.createIcons();

  // Periodic refresh for summary cards and chart every 10s
  setInterval(() => {
    fetchSummaryStats();
    updateTrafficChart();
  }, 10000);
});
