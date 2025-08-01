const app = Vue.createApp({
    data() {
      return {
        tab: 'ApacheTab',
        fileList: [],
        previewContent: '',
        selectedFiles: [],
        status: {
          cpu_load: 0,
          ram_usage: 0,
          temp_c: 0,
          cpu_percent: 0,
          ram_percent: 0,
          temp_percent: 0,
          cpu_color: '#aaa',
          ram_color: '#aaa',
          temp_color: '#aaa',
          apache_status: '',
          logs: '',
          use_local: false,
          fast_launch: false,
          lms_port: '',
          lms_dir: ''
        }
      };
    },
    methods: {
      setTab(t) { this.tab = t; },
      handleUpload(e) { this.selectedFiles = Array.from(e.target.files); },
      async upload() {
        const form = new FormData();
        this.selectedFiles.forEach(f => form.append("files", f));
        await fetch("/api/captive/upload", { method: "POST", body: form });
        this.loadFiles();
      },
      async preview(file) {
        const res = await fetch("/status");
        const json = await res.json();
        this.previewContent = json.content;
      },
      async restore() {
        await fetch("/api/captive/restore", { method: "POST" });
        this.loadFiles();
      },
      async loadFiles() {
        const res = await fetch("/api/captive/list");
        this.fileList = await res.json();
      },
      async fetchStatus() {
        const res = await fetch("/status");
        const data = await res.json();
        this.status = { ...this.status, ...data };

        for (const metric of ['cpu', 'ram', 'temp']) {
          const valueEl = document.getElementById(`${metric}-value`);
          const circleEl = document.getElementById(`${metric}-circle`);
          if (valueEl) {
            valueEl.textContent = metric === 'temp' ? data.temp_c : data[`${metric}_load`];
          }
          if (circleEl) {
            circleEl.setAttribute("stroke-dasharray", `${data[`${metric}_percent`]}, 100`);
            circleEl.setAttribute("stroke", data[`${metric}_color`]);
          }
        }

        const apacheEl = document.getElementById("apache-status");
        if (apacheEl) apacheEl.textContent = data.apache_status;

        const logEl = document.querySelector(".log-content");
        if (logEl) logEl.textContent = data.logs;
      }
    },
    mounted() {
      this.loadFiles();
      this.fetchStatus();
      setInterval(this.fetchStatus, 1000);
    }
  });

  app.mount("#monitor-app");