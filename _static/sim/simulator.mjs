/*
 * Stack-chan simulator, main-thread side.
 *
 * Runs the program in a Web Worker (sim-worker.js) and owns everything the
 * presenter sees and touches: the robot's screen (a 320x240 canvas), the
 * hardware state (servos, LEDs) for the 3D model, sounds, and the inputs
 * (touch, head zones, IMU, proximity, microphone and webcam frames) shared
 * with the worker through SharedArrayBuffer.
 */
import {IDX, CONTROL_SLOTS, MIC_RATE, MIC_SAMPLES, CAM_W, CAM_H, CAM_BYTES} from "./layout.js";

const BASE = new URL(".", import.meta.url);
const SHARED = typeof SharedArrayBuffer !== "undefined" && self.crossOriginIsolated;

function makeBuffer(bytes) {
    return SHARED ? new SharedArrayBuffer(bytes) : new ArrayBuffer(bytes);
}

// The simulated /flash gets a secrets.py so network demos run; the API key
// (optional, set in the camera settings) never leaves this browser.
function defaultFiles() {
    const key = localStorage.getItem("anthropicKey") || "";
    return {
        "secrets.py": `WIFI_SSID = "PyConES"\nWIFI_PASSWORD = ""\nANTHROPIC_API_KEY = ${JSON.stringify(key)}\n`,
    };
}

class Simulator {
    constructor() {
        this.handlers = {};
        this.shared = SHARED;
        this.control = new Int32Array(makeBuffer(CONTROL_SLOTS * 4));
        this.micRing = new Int16Array(makeBuffer(MIC_SAMPLES * 2));
        this.camera = new Uint8Array(makeBuffer(CAM_BYTES));
        this.canvas = document.createElement("canvas");
        this.canvas.width = 320;
        this.canvas.height = 240;
        this.canvas.className = "sim-screen";
        this.ctx = this.canvas.getContext("2d");
        this.state = null;
        this.worker = null;
        this.running = false;
        this.audio = null;
        this.camTimer = null;
        this.resetInputs();
        this.clearScreen();
        this.bindTouch(this.canvas);
    }

    on(name, fn) { (this.handlers[name] = this.handlers[name] || []).push(fn); }
    emit(name, ...args) { (this.handlers[name] || []).forEach((fn) => fn(...args)); }

    // ---- inputs ----
    resetInputs() {
        const c = this.control;
        c.fill(0);
        c[IDX.AZ] = 1000;
        c[IDX.LUX] = 200000;
        c[IDX.BATTERY] = 80;
    }

    setTouch(down, x, y) {
        this.control[IDX.TX] = Math.round(x);
        this.control[IDX.TY] = Math.round(y);
        this.control[IDX.TOUCH] = down ? 1 : 0;
    }

    setHead(zone, down) { this.control[IDX.HEAD0 + zone] = down ? 1 : 0; }

    setAccel(ax, ay, az = 1) {
        this.control[IDX.AX] = Math.round(ax * 1000);
        this.control[IDX.AY] = Math.round(ay * 1000);
        this.control[IDX.AZ] = Math.round(az * 1000);
    }

    setProximity(value) { this.control[IDX.PROX] = Math.round(value); }

    setLight(lux) { this.control[IDX.LUX] = Math.round(lux * 1000); }

    setPower(down) { this.control[IDX.PWR] = down ? 1 : 0; }

    // Turn the head by hand (3D view), like moving a robot with torque off
    setHand(x, y) {
        this.control[IDX.HAND_X] = Math.round(x * 1000);
        this.control[IDX.HAND_Y] = Math.round(y * 1000);
        this.control[IDX.HAND] += 1;
    }

    async shake() {
        for (let i = 0; i < 8; i++) {
            this.setAccel(i % 2 ? 2.5 : -2.5, 0);
            await new Promise((resolve) => setTimeout(resolve, 120));
        }
        this.setAccel(0, 0);
    }

    bindTouch(canvas) {
        const point = (e) => {
            const rect = canvas.getBoundingClientRect();
            return [(e.clientX - rect.left) / rect.width * canvas.width,
                (e.clientY - rect.top) / rect.height * canvas.height];
        };
        let down = false;
        canvas.addEventListener("pointerdown", (e) => {
            down = true;
            canvas.setPointerCapture(e.pointerId);
            this.setTouch(true, ...point(e));
        });
        canvas.addEventListener("pointermove", (e) => down && this.setTouch(true, ...point(e)));
        canvas.addEventListener("pointerup", (e) => {
            down = false;
            this.setTouch(false, ...point(e));
        });
    }

    // ---- microphone: the presenter's real microphone ----
    async enableMic() {
        if (this.micContext) return;
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const context = new AudioContext({sampleRate: MIC_RATE});
        const source = context.createMediaStreamSource(stream);
        const processor = context.createScriptProcessor(1024, 1, 1);
        processor.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0);
            let w = this.control[IDX.MIC_WRITE];
            for (let i = 0; i < input.length; i++) {
                this.micRing[w] = Math.max(-1, Math.min(1, input[i])) * 32767;
                w = (w + 1) % MIC_SAMPLES;
            }
            this.control[IDX.MIC_WRITE] = w;
        };
        source.connect(processor);
        processor.connect(context.destination);
        this.micContext = {context, stream};
        this.control[IDX.MIC_ON] = 1;
    }

    disableMic() {
        if (!this.micContext) return;
        this.micContext.stream.getTracks().forEach((t) => t.stop());
        this.micContext.context.close();
        this.micContext = null;
        this.control[IDX.MIC_ON] = 0;
    }

    // ---- webcam -> camera module (RGB565 QVGA) ----
    startCameraFeed() {
        const canvas = document.createElement("canvas");
        canvas.width = CAM_W;
        canvas.height = CAM_H;
        const ctx = canvas.getContext("2d", {willReadFrequently: true});
        const view = new DataView(this.camera.buffer);
        this.camTimer = setInterval(() => {
            const video = window.cameraBox && window.cameraBox.stream && window.cameraBox.live;
            if (!video || video.readyState < 2) return;
            ctx.drawImage(video, 0, 0, CAM_W, CAM_H);
            const rgba = ctx.getImageData(0, 0, CAM_W, CAM_H).data;
            for (let i = 0, o = 0; i < rgba.length; i += 4, o += 2) {
                view.setUint16(o, ((rgba[i] & 0xF8) << 8) | ((rgba[i + 1] & 0xFC) << 3) | (rgba[i + 2] >> 3), true);
            }
            this.control[IDX.CAM_FRAME] += 1;
        }, 66);
    }

    // ---- output ----
    clearScreen() {
        this.ctx.fillStyle = "#000";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.emit("frame");
    }

    drawFrame(w, h, data) {
        if (this.canvas.width !== w || this.canvas.height !== h) {
            this.canvas.width = w;
            this.canvas.height = h;
        }
        const pixels = new Uint16Array(data.buffer, data.byteOffset, w * h);
        const image = this.ctx.createImageData(w, h);
        const out = image.data;
        for (let i = 0, o = 0; i < pixels.length; i++, o += 4) {
            const p = pixels[i];
            out[o] = ((p >> 11) & 0x1F) * 255 / 31;
            out[o + 1] = ((p >> 5) & 0x3F) * 255 / 63;
            out[o + 2] = (p & 0x1F) * 255 / 31;
            out[o + 3] = 255;
        }
        this.ctx.putImageData(image, 0, 0);
        this.emit("frame");
    }

    audioContext() {
        this.audio = this.audio || new AudioContext();
        if (this.audio.state === "suspended") this.audio.resume();
        return this.audio;
    }

    tone(freq, ms, volume) {
        const ctx = this.audioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = freq;
        gain.gain.value = 0.08 * volume / 255;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + ms / 1000);
    }

    async playWav(data) {
        const ctx = this.audioContext();
        const buffer = await ctx.decodeAudioData(data.buffer.slice(0));
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        source.start();
    }

    // ---- lifecycle ----
    run(code, files = {}) {
        files = Object.assign(defaultFiles(), files);
        this.stop(true);
        this.resetInputsKeepingSensors();
        const worker = new Worker(new URL("sim-worker.js", BASE), {type: "module"});
        this.worker = worker;
        this.running = true;
        worker.onmessage = (e) => this.onWorkerMessage(e.data);
        worker.onerror = (e) => this.emit("stdout", `[simulador] ${e.message}\n`);
        worker.postMessage({
            t: "run", code, files,
            bundleUrl: new URL("bundle.json", BASE).href,
            control: this.control.buffer, mic: this.micRing.buffer, camera: this.camera.buffer,
        });
        if (!this.shared) {
            this.emit("stdout", "[simulador] sin memoria compartida: las entradas no llegan al programa " +
                "mientras se ejecuta. Recarga la página para activarla.\n");
        }
        if (!this.camTimer) this.startCameraFeed();
        this.emit("status");
    }

    resetInputsKeepingSensors() {
        this.control[IDX.HAND] = 0;
        this.control[IDX.CAM_FRAME] = 0;
    }

    onWorkerMessage(msg) {
        switch (msg.t) {
            case "frame": this.drawFrame(msg.w, msg.h, msg.data); break;
            case "state":
                this.state = JSON.parse(msg.json);
                this.emit("state", this.state);
                break;
            case "stdout": this.emit("stdout", msg.text); break;
            case "log":
                if (msg.level !== "info") this.emit("stdout", `[${msg.level}] ${msg.msg}\n`);
                else console.debug("[sim]", msg.msg);
                break;
            case "tone": this.tone(msg.freq, msg.ms, msg.volume); break;
            case "audio": this.playWav(msg.data).catch(() => {}); break;
            case "event": {
                const event = JSON.parse(msg.json);
                if (event.t === "reset_request") this.emit("stdout", "[simulador] machine.reset()\n");
                break;
            }
            case "done":
                this.running = false;
                this.emit("status");
                break;
            default: break;
        }
    }

    stop(silent = false) {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
            if (!silent) this.emit("stdout", "[simulador] detenido\n");
        }
        this.running = false;
        this.emit("status");
    }

    reset() {
        this.stop(true);
        this.state = null;
        this.clearScreen();
        this.emit("state", null);
    }
}

export const simulator = new Simulator();
window.simulator = simulator;
