/*
 * Camera box: shows the robot to the audience during demos.
 *
 * Sources (cycled with the "Cámara" button of the demos or the C key):
 *   camera     live webcam pointed at Stack-chan
 *   simulator  screen of the in-browser simulator, with its sensor controls
 *
 * It floats in a corner on demo slides and docks into ``camera-view``
 * slots. Ctrl+F11 toggles fullscreen.
 */
(function () {
    "use strict";

    const SOURCES = ["camera", "simulator"];
    const LABELS = {camera: "Cámara", simulator: "Simulador"};

    class CameraBox {
        constructor() {
            this.source = localStorage.getItem("cameraSource") === "simulator" ? "simulator" : "camera";
            this.stream = null;
            this.simTimer = null;
            this.build();
        }

        build() {
            document.body.insertAdjacentHTML("beforeend", `
              <div id="camera-box" class="hidden" data-source="${this.source}">
                <video class="cam-live" autoplay muted playsinline></video>
                <div class="cam-sim">
                  <div class="sim-controls" aria-label="Sensores del simulador">
                    <span class="sim-group">Cabeza
                      <button data-head="0">Delante</button><button data-head="1">Centro</button><button data-head="2">Detrás</button>
                    </span>
                    <button class="sim-shake">Agitar</button>
                    <label>Inclinar <input type="range" class="sim-tilt" min="-1" max="1" step="0.05" value="0"></label>
                    <label>Proximidad <input type="range" class="sim-prox" min="0" max="2047" step="1" value="0"></label>
                    <button class="sim-mic" aria-pressed="false">Micrófono</button>
                  </div>
                </div>
                <p class="cam-empty">Activa la cámara en el panel de ajustes</p>
                <span class="cam-badge"></span>
              </div>
              <div id="camera-controls" class="collapsed">
                <button class="cam-toggle-panel" aria-label="Ajustes de cámara">Ajustes</button>
                <div class="cam-panel">
                  <button class="cam-power">Activar cámara</button>
                  <label>Dispositivo <select class="cam-device"></select></label>
                  <label>Fuente <select class="cam-source">
                    <option value="camera">Cámara</option>
                    <option value="simulator">Simulador</option>
                  </select></label>
                  <label><input type="checkbox" class="cam-mirror"> Espejo</label>
                  <label>Zoom <input type="range" class="cam-zoom" min="1" max="3" step="0.1" value="1"></label>
                  <label>Clave API (simulador) <input type="password" class="cam-api-key" autocomplete="off" placeholder="sk-ant-..."></label>
                </div>
              </div>`);
            this.box = document.getElementById("camera-box");
            this.live = this.box.querySelector(".cam-live");
            this.sim = this.box.querySelector(".cam-sim");
            this.badge = this.box.querySelector(".cam-badge");
            this.controls = document.getElementById("camera-controls");
            this.home = document.body;

            const q = (sel) => this.controls.querySelector(sel);
            q(".cam-toggle-panel").addEventListener("click", () => this.controls.classList.toggle("collapsed"));
            q(".cam-power").addEventListener("click", () => this.togglePower());
            q(".cam-device").addEventListener("change", (e) => this.stream && this.start(e.target.value));
            q(".cam-source").value = this.source;
            q(".cam-source").addEventListener("change", (e) => this.setSource(e.target.value));
            q(".cam-mirror").addEventListener("change", (e) => this.box.classList.toggle("mirror", e.target.checked));
            q(".cam-zoom").addEventListener("input", (e) => this.box.style.setProperty("--zoom", e.target.value));
            q(".cam-api-key").value = localStorage.getItem("anthropicKey") || "";
            q(".cam-api-key").addEventListener("change", (e) => localStorage.setItem("anthropicKey", e.target.value.trim()));
            q(".cam-api-key").addEventListener("keydown", (e) => e.stopPropagation());
            this.setupSimulatorControls();
            this.makeDraggable();
            this.updateBadge();
        }

        async listDevices() {
            const select = this.controls.querySelector(".cam-device");
            const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
            const current = localStorage.getItem("cameraDevice");
            select.innerHTML = "";
            devices.forEach((device, i) => {
                const option = new Option(device.label || `Cámara ${i + 1}`, device.deviceId);
                option.selected = device.deviceId === current;
                select.add(option);
            });
        }

        async start(deviceId) {
            this.stopStream();
            const video = deviceId ? {deviceId: {exact: deviceId}} : {width: {ideal: 1920}, height: {ideal: 1080}};
            try {
                this.stream = await navigator.mediaDevices.getUserMedia({video, audio: false});
            } catch (err) {
                if (deviceId) return this.start(null);   // stored device is gone
                this.box.querySelector(".cam-empty").textContent = "No se pudo abrir la cámara: " + err.message;
                return;
            }
            if (deviceId) localStorage.setItem("cameraDevice", deviceId);
            this.live.srcObject = this.stream;
            this.controls.querySelector(".cam-power").textContent = "Desactivar cámara";
            this.box.classList.add("has-stream");
            await this.listDevices();
        }

        stopStream() {
            if (this.stream) this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
            this.live.srcObject = null;
            this.box.classList.remove("has-stream");
            this.controls.querySelector(".cam-power").textContent = "Activar cámara";
        }

        togglePower() {
            if (this.stream) this.stopStream();
            else this.start(this.controls.querySelector(".cam-device").value || localStorage.getItem("cameraDevice"));
        }

        setSource(source) {
            this.source = source;
            localStorage.setItem("cameraSource", source);
            this.box.dataset.source = source;
            this.controls.querySelector(".cam-source").value = source;
            this.updateBadge();
            this.syncSimulator();
        }

        cycleSource() {
            const next = SOURCES[(SOURCES.indexOf(this.source) + 1) % SOURCES.length];
            this.setSource(next);
        }

        updateBadge() {
            this.badge.textContent = LABELS[this.source];
            document.querySelectorAll(".toggle-video").forEach((button) => {
                button.textContent = LABELS[this.source];
            });
        }

        // Show the simulated robot (3D, with its screen) while visible
        async syncSimulator() {
            const wanted = this.source === "simulator" && !this.box.classList.contains("hidden");
            if (wanted && !this.mirror) {
                this.mirror = "loading";
                await window.loadSimulator();
                this.mirror = await window.createRobotMirror(this.box.querySelector(".cam-sim"));
            }
            if (this.mirror && this.mirror !== "loading") {
                if (wanted) this.mirror.start(); else this.mirror.stop();
            }
        }

        setupSimulatorControls() {
            const panel = this.box.querySelector(".sim-controls");
            const withSim = (fn) => window.loadSimulator().then(fn);
            panel.addEventListener("pointerdown", (e) => e.stopPropagation());
            panel.addEventListener("keydown", (e) => e.stopPropagation());
            panel.querySelectorAll("[data-head]").forEach((button) => {
                const zone = +button.dataset.head;
                const set = (down) => withSim((sim) => sim.setHead(zone, down));
                button.addEventListener("pointerdown", () => set(true));
                button.addEventListener("pointerup", () => set(false));
                button.addEventListener("pointerleave", () => set(false));
            });
            panel.querySelector(".sim-shake").addEventListener("click", () => withSim((sim) => sim.shake()));
            panel.querySelector(".sim-tilt").addEventListener("input", (e) => withSim((sim) => sim.setAccel(+e.target.value, 0)));
            panel.querySelector(".sim-prox").addEventListener("input", (e) => withSim((sim) => sim.setProximity(+e.target.value)));
            const mic = panel.querySelector(".sim-mic");
            mic.addEventListener("click", () => withSim(async (sim) => {
                const on = mic.getAttribute("aria-pressed") !== "true";
                try {
                    if (on) await sim.enableMic(); else sim.disableMic();
                    mic.setAttribute("aria-pressed", String(on));
                } catch (err) {
                    console.warn(err);
                }
            }));
        }

        onSlide(slide) {
            const slot = slide.querySelector(".camera-slot");
            const demo = slide.querySelector(".micropython-demo");
            if (slot) {
                slot.appendChild(this.box);
                this.box.className = this.box.className.replace(/\bdock-\w+/g, "");
                this.box.classList.add("docked", "dock-" + slot.dataset.mode);
                this.box.style.left = this.box.style.top = "";
            } else {
                this.home.appendChild(this.box);
                this.box.classList.remove("docked", "dock-full", "dock-side");
            }
            const visible = !!(slot || demo);
            slide.classList.toggle("has-camera", !!demo && !slot);
            this.box.classList.toggle("hidden", !visible);
            this.controls.classList.toggle("hidden", !visible);
            this.syncSimulator();
        }

        makeDraggable() {
            let start = null;
            this.box.addEventListener("pointerdown", (e) => {
                if (this.box.classList.contains("docked")) return;
                start = {x: e.clientX - this.box.offsetLeft, y: e.clientY - this.box.offsetTop};
                this.box.setPointerCapture(e.pointerId);
            });
            this.box.addEventListener("pointermove", (e) => {
                if (!start) return;
                this.box.style.left = e.clientX - start.x + "px";
                this.box.style.top = e.clientY - start.y + "px";
                this.box.style.right = this.box.style.bottom = "auto";
            });
            this.box.addEventListener("pointerup", () => { start = null; });
        }
    }

    function init() {
        const camera = new CameraBox();
        window.cameraBox = camera;
        camera.onSlide(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => camera.onSlide(event.currentSlide));
        // Reopen the camera automatically if permission was already granted
        navigator.permissions && navigator.permissions.query({name: "camera"}).then((status) => {
            if (status.state === "granted") camera.start(localStorage.getItem("cameraDevice"));
        }).catch(() => {});
        document.addEventListener("keyup", (e) => {
            if (e.ctrlKey && e.key === "F11") {
                e.preventDefault();
                camera.box.classList.toggle("full-screen");
            }
        });
        Reveal.addKeyBinding({keyCode: 67, key: "C", description: "Cambiar fuente de la cámara"}, () => camera.cycleSource());
    }

    // reveal.js loads after this file: wait for the DOM, then for Reveal
    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) init(); else Reveal.on("ready", init);
    });
})();
