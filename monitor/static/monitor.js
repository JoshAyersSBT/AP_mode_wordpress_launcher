// static/monitor.js
document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".tablink");
  const tabContents = document.querySelectorAll(".tab-content");

  // --- Tabs ---
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-tab");
      tabs.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(target).classList.add("active");
    });
  });

  // DOM refs
  const cpuCircle = document.getElementById("cpu-circle");
  const ramCircle = document.getElementById("ram-circle");
  const tempCircle = document.getElementById("temp-circle");
  const cpuText = document.getElementById("cpu-text");
  const ramText = document.getElementById("ram-text");
  const tempText = document.getElementById("temp-text");
  const apacheStatus = document.getElementById("apache-status");

  const logsBox = document.getElementById("logs-box");
  const followLogs = document.getElementById("followLogs");
  const refreshLogsBtn = document.getElementById("refresh-logs");

  const captiveFileList = document.getElementById("captive-file-list");
  const captiveFilesInput = document.getElementById("captive-files");
  const captiveUploadBtn = document.getElementById("captive-upload");
  const captiveRestoreBtn = document.getElementById("captive-restore");
  const captiveClearBtn = document.getElementById("captive-clear");
  const captivePreviewBox = document.getElementById("captive-preview-box");
  const captivePreview = document.getElementById("captive-preview");

  let selectedFiles = [];

  // --- Status polling ---
  async function fetchStatus() {
    try {
      const r = await fetch("/status");
      if (!r.ok) return;
      const d = await r.json();

      // Gauges
      if (cpuCircle) {
        cpuCircle.setAttribute("stroke", d.cpu_color || "#aaa");
        cpuCircle.setAttribute("stroke-dasharray", (d.cpu_percent || 0) + ", 100");
      }
      if (cpuText) {
        cpuText.textContent = d.cpu_load || "0%";
      }

      if (ramCircle) {
        ramCircle.setAttribute("stroke", d.ram_color || "#aaa");
        ramCircle.setAttribute("stroke-dasharray", (d.ram_percent || 0) + ", 100");
      }
      if (ramText) {
        ramText.textContent = d.ram_usage || "0%";
      }

      if (tempCircle) {
        tempCircle.setAttribute("stroke", d.temp_color || "#aaa");
        tempCircle.setAttribute("stroke-dasharray", (d.temp_percent || 0) + ", 100");
      }
      if (tempText) {
        tempText.textContent = d.temp_c || "0°C";
      }

      if (apacheStatus) {
        apacheStatus.textContent = d.apache_status || "";
      }

      // Also use status to tick launcher checkboxes if user didn't load page via POST
      const useLocal = document.getElementById("use_local");
      if (useLocal && typeof d.USE_LOCAL !== "undefined") useLocal.checked = !!d.USE_LOCAL;
      const fastLaunch = document.getElementById("fast_launch");
      if (fastLaunch && typeof d.FAST_LAUNCH !== "undefined") fastLaunch.checked = !!d.FAST_LAUNCH;
      const verbose = document.getElementById("verbose");
      if (verbose && typeof d.VERBOSE !== "undefined") verbose.checked = !!d.VERBOSE;
      const startup = document.getElementById("startup");
      if (startup && typeof d.STARTUP !== "undefined") startup.checked = !!d.STARTUP;
      const captiveportal = document.getElementById("captiveportal");
      if (captiveportal && typeof d.CAPTIVEPORTAL !== "undefined") captiveportal.checked = !!d.CAPTIVEPORTAL;
      const fti = document.getElementById("fti");
      if (fti && typeof d.FTI !== "undefined") fti.checked = !!d.FTI;
      const ssid = document.getElementById("ssid");
      if (ssid && typeof d.SSID !== "undefined") ssid.value = d.SSID || "";
      const wpass = document.getElementById("wap_passphrase");
      if (wpass && typeof d.WAP_PASSPHRASE !== "undefined") wpass.value = d.WAP_PASSPHRASE || "";

      const lmsPort = document.getElementById("lms_port");
      if (lmsPort && typeof d.LMS_PORT !== "undefined") lmsPort.value = d.LMS_PORT;
      const lmsDir = document.getElementById("lms_dir");
      if (lmsDir && typeof d.LMS_DIR !== "undefined") lmsDir.value = d.LMS_DIR;
    } catch (e) {
      console.error("[monitor] status fetch failed", e);
    }
  }

  // --- Logs ---
  async function refreshLogs() {
    try {
      const r = await fetch("/logs");
      if (!r.ok) return;
      const j = await r.json();
      logsBox.textContent = j.logs || "";
      if (followLogs.checked) {
        logsBox.scrollTop = logsBox.scrollHeight;
      }
    } catch (e) {
      console.error("[monitor] log fetch failed", e);
    }
  }

  refreshLogsBtn.addEventListener("click", refreshLogs);

  // --- Captive Portal ---
  async function loadCaptiveFiles() {
    try {
      const r = await fetch("/api/captive/list");
      const files = await r.json();
      captiveFileList.innerHTML = "";
      if (Array.isArray(files)) {
        files.forEach(fname => {
          const li = document.createElement("li");
          li.textContent = fname + " ";
          const btn = document.createElement("button");
          btn.textContent = "Preview";
          btn.addEventListener("click", () => previewCaptive(fname));
          li.appendChild(btn);
          captiveFileList.appendChild(li);
        });
      }
    } catch (e) {
      console.error("[monitor] captive list failed", e);
    }
  }

  async function previewCaptive(name) {
    try {
      const r = await fetch("/api/captive/preview?file=" + encodeURIComponent(name));
      const j = await r.json();
      if (j.content) {
        captivePreview.textContent = j.content;
        captivePreviewBox.style.display = "block";
      } else {
        captivePreview.textContent = "[Preview failed]";
        captivePreviewBox.style.display = "block";
      }
    } catch (e) {
      captivePreview.textContent = "[Preview failed]";
      captivePreviewBox.style.display = "block";
    }
  }

  captiveFilesInput.addEventListener("change", (e) => {
    selectedFiles = Array.from(e.target.files);
  });

  captiveUploadBtn.addEventListener("click", async () => {
    if (!selectedFiles.length) return;
    const form = new FormData();
    selectedFiles.forEach(f => form.append("files", f));
    await fetch("/api/captive/upload", { method: "POST", body: form });
    selectedFiles = [];
    captiveFilesInput.value = "";
    loadCaptiveFiles();
  });

  captiveRestoreBtn.addEventListener("click", async () => {
    await fetch("/api/captive/restore", { method: "POST" });
    loadCaptiveFiles();
  });

  captiveClearBtn.addEventListener("click", async () => {
    if (!confirm("Clear all captive portal files?")) return;
    await fetch("/api/captive/clear", { method: "POST" });
    loadCaptiveFiles();
  });

  // initial
  fetchStatus();
  loadCaptiveFiles();
  refreshLogs();

  // intervals
  setInterval(fetchStatus, 1500);
  setInterval(refreshLogs, 3000);
});
