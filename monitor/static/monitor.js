// Guard: fail gracefully if Vue didn't load
if (!window.Vue) {
  console.error("[Monitor] Vue failed to load. Check /static/vendor/vue.global.prod.js and CSP.");
  const el = document.getElementById("monitor-app");
  if (el) {
    el.innerHTML =
      '<div class="status-box" style="border-color:#b00;color:#b00">Vue failed to load. Ensure /static/vendor/vue.global.prod.js is present and permitted by CSP.</div>';
  }
} else {
  const { createApp } = Vue;

  const app = createApp({
    data() {
      return {
        tab: "ApacheTab",
        fileList: [],
        previewContent: "",
        selectedFiles: [],
        status: {
          cpu_load: 0,
          ram_usage: 0,
          temp_c: 0,
          cpu_percent: 0,
          ram_percent: 0,
          temp_percent: 0,
          cpu_color: "#aaa",
          ram_color: "#aaa",
          temp_color: "#aaa",
          apache_status: "",
          logs: ""
        },

        /* ---- STATIC OPTION LISTS ---- */
        STATIC: {
          SSID_OPTIONS: ["BetaBox1", "BetaBox2", "LearningLab", "HomeAP"],
          LMS_PORTS: [80, 8080, 8000, 3000, 35373],
          LMS_DIRS: [
            "/var/www/lms",
            "/var/www/html",
            "/AP_mode_wordpress_launcher/www/captive-portal",
            "/AP_mode_wordpress_launcher/www/wordpress"
          ]
        },

        /* Settings form (seeded later via /status) */
        form: {
          USE_LOCAL: false,
          FAST_LAUNCH: false,
          VERBOSE: false,
          STARTUP: false,
          CAPTIVEPORTAL: false,
          FTI: false,
          SSID: "",
          SSID_SELECT: "",
          WAP_PASSPHRASE: ""
        },

        /* LMS form */
        lmsForm: {
          lms_port: "",
          lms_dir: "",
          portChoice: "",
          dirChoice: ""
        },

        logs: "",
        followLogs: true
      };
    },

    computed: {
      effectiveSSID() {
        return this.form.SSID_SELECT === "__custom__"
          ? this.form.SSID || ""
          : this.form.SSID_SELECT;
      },
      effectiveLmsPort() {
        return this.lmsForm.portChoice === "__custom__"
          ? this.lmsForm.lms_port || ""
          : this.lmsForm.portChoice;
      },
      effectiveLmsDir() {
        return this.lmsForm.dirChoice === "__custom__"
          ? this.lmsForm.lms_dir || ""
          : this.lmsForm.dirChoice;
      }
    },

    methods: {
      setTab(t) {
        this.tab = t;
      },
      handleUpload(e) {
        this.selectedFiles = Array.from(e.target.files);
      },

      async clear() {
        if (confirm("Are you sure you want to delete all captive portal files?")) {
          await fetch("/api/captive/clear", { method: "POST" });
          this.loadFiles();
        }
      },

      async upload() {
        if (!this.selectedFiles.length) return;
        const form = new FormData();
        this.selectedFiles.forEach((f) => form.append("files", f));
        await fetch("/api/captive/upload", { method: "POST", body: form });
        this.loadFiles();
      },

      async preview(filename) {
        try {
          const res = await fetch(
            `/api/captive/preview?file=${encodeURIComponent(filename)}`
          );
          const json = await res.json();
          this.previewContent = json.content || "[Error loading preview]";
        } catch {
          this.previewContent = "[Preview failed]";
        }
      },

      async restore() {
        await fetch("/api/captive/restore", { method: "POST" });
        this.loadFiles();
      },

      async loadFiles() {
        try {
          const res = await fetch("/api/captive/list");
          this.fileList = await res.json();
        } catch (e) {
          console.error("[Monitor] loadFiles failed:", e);
          this.fileList = [];
        }
      },

      async fetchStatus() {
        try {
          const res = await fetch("/status");
          if (!res.ok) return;
          const d = await res.json();
          this.status = d;

          // Sync form fields
          if (typeof d.USE_LOCAL !== "undefined")
            this.form.USE_LOCAL = !!d.USE_LOCAL;
          if (typeof d.FAST_LAUNCH !== "undefined")
            this.form.FAST_LAUNCH = !!d.FAST_LAUNCH;
          if (typeof d.VERBOSE !== "undefined")
            this.form.VERBOSE = !!d.VERBOSE;
          if (typeof d.STARTUP !== "undefined")
            this.form.STARTUP = !!d.STARTUP;
          if (typeof d.CAPTIVEPORTAL !== "undefined")
            this.form.CAPTIVEPORTAL = !!d.CAPTIVEPORTAL;
          if (typeof d.FTI !== "undefined") this.form.FTI = !!d.FTI;
          if (typeof d.SSID !== "undefined") this.applySsidDefault(d.SSID);
          if (typeof d.WAP_PASSPHRASE !== "undefined")
            this.form.WAP_PASSPHRASE = d.WAP_PASSPHRASE;

          if (typeof d.LMS_PORT !== "undefined")
            this.applyPortDefault(String(d.LMS_PORT));
          if (typeof d.LMS_DIR !== "undefined") this.applyDirDefault(d.LMS_DIR);

          if (!this.logs && d.logs) {
            this.logs = d.logs;
            this.$nextTick(this.autoscroll);
          }
        } catch (err) {
          console.error("[Monitor] Error fetching status:", err);
        }
      },

      applySsidDefault(cur) {
        if (this.STATIC.SSID_OPTIONS.includes(cur)) {
          this.form.SSID_SELECT = cur;
          this.form.SSID = "";
        } else {
          this.form.SSID_SELECT = "__custom__";
          this.form.SSID = cur || "";
        }
      },

      applyPortDefault(cur) {
        if (this.STATIC.LMS_PORTS.map(String).includes(cur)) {
          this.lmsForm.portChoice = cur;
          this.lmsForm.lms_port = cur;
        } else {
          this.lmsForm.portChoice = "__custom__";
          this.lmsForm.lms_port = cur || "";
        }
      },

      applyDirDefault(cur) {
        if (this.STATIC.LMS_DIRS.includes(cur)) {
          this.lmsForm.dirChoice = cur;
          this.lmsForm.lms_dir = cur;
        } else {
          this.lmsForm.dirChoice = "__custom__";
          this.lmsForm.lms_dir = cur || "";
        }
      },

      async refreshLogs() {
        try {
          const r = await fetch("/logs");
          if (!r.ok) return;
          const j = await r.json();
          this.logs = j.logs || "";
          this.$nextTick(this.autoscroll);
        } catch {}
      },

      autoscroll() {
        if (!this.followLogs) return;
        const box = this.$refs.logbox;
        if (box) box.scrollTop = box.scrollHeight;
      }
    },

    mounted() {
      this.applySsidDefault(this.form.SSID);
      this.applyPortDefault(String(this.lmsForm.lms_port));
      this.applyDirDefault(this.lmsForm.lms_dir);

      this.loadFiles();
      this.fetchStatus();
      setInterval(this.fetchStatus, 1500);
      this.refreshLogs();
      setInterval(() => this.refreshLogs(), 3000);
    }
  });

  app.mount("#monitor-app");
}
