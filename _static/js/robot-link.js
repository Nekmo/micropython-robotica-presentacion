/*
 * Connection to the robot. Two interchangeable backends:
 *
 *  - SerialLink: the real Stack-chan over Web Serial, using the MicroPython
 *    raw REPL (Ctrl+A, code, Ctrl+D).
 *  - SimulatorLink: the in-browser simulator (_static/sim), MicroPython
 *    compiled to WebAssembly with the Stack-chan hardware shims.
 *
 * Both expose connect(), disconnect(), run(code), stop(), restart() and
 * emit "status" / "output" events through window.robotLink.
 */
(function () {
    "use strict";

    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    class Emitter {
        constructor() { this.handlers = {}; }
        on(name, fn) { (this.handlers[name] = this.handlers[name] || []).push(fn); }
        emit(name, ...args) { (this.handlers[name] || []).forEach((fn) => fn(...args)); }
    }

    class SerialLink {
        constructor(events) {
            this.events = events;
            this.port = null;
            this.writer = null;
            this.reader = null;
            this.buffer = "";
        }

        get connected() { return !!this.writer; }

        async connect() {
            if (!("serial" in navigator)) {
                throw new Error("Este navegador no soporta Web Serial. Usa Chrome o Edge.");
            }
            const known = await navigator.serial.getPorts();
            this.port = known.length ? known[0] : await navigator.serial.requestPort();
            try {
                await this.port.open({baudRate: 115200});
            } catch (err) {
                if (!/already open/i.test(err.message)) throw err;
            }
            const decoder = new TextDecoderStream();
            this.port.readable.pipeTo(decoder.writable).catch(() => {});
            this.reader = decoder.readable.getReader();
            const encoder = new TextEncoderStream();
            encoder.readable.pipeTo(this.port.writable).catch(() => {});
            this.writer = encoder.writable.getWriter();
            this.readLoop();
            // Interrupt whatever main.py is doing (UIFlow boots into it), and
            // stop its LVGL loop: its timer outlives main.py and, while a demo
            // blocks (camera, microphone), fills the schedule queue
            await this.run(STOP_LVGL);
            await delay(400);
            await this.write("\x02");         // back to the friendly REPL
            this.events.emit("output", "Conectado al Stack-chan por USB\n");
        }

        async readLoop() {
            while (this.reader) {
                let chunk;
                try {
                    chunk = await this.reader.read();
                } catch (err) {
                    break;
                }
                if (chunk.done) break;
                this.events.emit("output", this.clean(chunk.value));
            }
        }

        // Hide raw REPL protocol noise, keep program output
        clean(text) {
            return text
                .replace(/raw REPL; CTRL-B to exit\r?\n>?/g, "")
                .replace(/^OK/gm, "")
                .replace(/\x04>?/g, "")
                .replace(/\r/g, "");
        }

        async write(text) {
            if (!this.writer) throw new Error("No hay conexión con el robot");
            await this.writer.write(text);
        }

        async run(code) {
            await this.write("\r\x03\x03");   // stop the running program
            await delay(120);
            await this.write("\x01");          // raw REPL
            await delay(80);
            // Send in chunks: the USB CDC buffer of the ESP32-S3 is small
            for (let i = 0; i < code.length; i += 256) {
                await this.write(code.slice(i, i + 256));
                await delay(8);
            }
            await this.write("\x04");          // execute
        }

        // Stop the program and let the servos go (torque off), in case a
        // previous run left them holding a pose
        async stop() {
            await this.run(RELEASE_SERVOS);
            await delay(250);
            await this.write("\x02");         // back to the friendly REPL
            this.events.emit("output", "Servos liberados\n");
        }

        async restart() {
            await this.run(RELEASE_SERVOS + "import machine\nmachine.reset()\n");
            this.events.emit("output", "Reiniciando el robot...\n");
            await delay(300);
            await this.disconnect();
            await delay(3000);
            await this.connect();
        }

        async disconnect() {
            const reader = this.reader;
            const writer = this.writer;
            this.reader = null;
            this.writer = null;
            try { await writer.write("\x02"); } catch (err) { /* already gone */ }
            try { await reader.cancel(); } catch (err) { /* ignore */ }
            try { await writer.close(); } catch (err) { /* ignore */ }
            try { await this.port.close(); } catch (err) { /* ignore */ }
            this.port = null;
        }
    }

    // UIFlow's LVGL event loop (m5ui), started by the robot's main.py
    const STOP_LVGL = [
        "try:",
        "    import m5ui",
        "    if m5ui.event_loop.is_initialized():",
        "        m5ui.deinit()",
        "except Exception:",
        "    pass",
        "",
    ].join("\n");

    // Torque off on Stack-chan's two bus servos (Feetech SCS on UART1, IDs
    // 1 and 2): WRITE register 40 = 0. Plain UART, no robot library.
    const RELEASE_SERVOS = [
        "from machine import UART",
        "_u = UART(1, baudrate=1000000, tx=6, rx=7)",
        "for _id in (1, 2):",
        "    _b = bytes([_id, 4, 3, 40, 0])",
        "    _u.write(b'\\xff\\xff' + _b + bytes([~sum(_b) & 255]))",
        "",
    ].join("\n");

    // Load the in-browser simulator (ES module) on demand
    // Versioned by the build (js/model-version.js), like the 3D model
    const SIMULATOR_URL = new URL("../sim/simulator.mjs", document.currentScript.src);
    let simulatorPromise = null;
    window.loadSimulator = () => (simulatorPromise = simulatorPromise || (() => {
        SIMULATOR_URL.search = "v=" + (window.STACKCHAN_SIM_VERSION || "dev");
        return import(SIMULATOR_URL.href).then((module) => module.simulator);
    })());

    class SimulatorLink {
        constructor(events) {
            this.events = events;
            this.sim = null;
        }

        get connected() { return !!this.sim; }

        async connect() {
            this.sim = await window.loadSimulator();
            if (!this.sim.linked) {
                this.sim.linked = true;
                this.sim.on("stdout", (text) => this.sim === null || this.events.emit("output", text));
            }
            this.events.emit("output", "Simulador de Stack-chan listo (MicroPython en el navegador)\n");
        }

        async run(code) {
            this.sim.run(code);
        }

        async stop() {
            this.sim.stop();
        }

        async restart() {
            this.sim.reset();
            this.events.emit("output", "Simulador reiniciado\n");
        }

        async disconnect() {
            this.sim.stop(true);
            this.sim = null;
        }
    }

    class RobotLink extends Emitter {
        constructor() {
            super();
            this.backends = {serial: new SerialLink(this), simulator: new SimulatorLink(this)};
            const saved = localStorage.getItem("robotTarget");
            this.target = saved === "simulator" ? "simulator" : "serial";
        }

        get backend() { return this.backends[this.target]; }
        get connected() { return this.backend.connected; }

        async setTarget(target) {
            if (target === this.target) return;
            if (this.connected) await this.disconnect();
            this.target = target;
            localStorage.setItem("robotTarget", target);
            this.emit("status");
        }

        async guarded(action) {
            try {
                await action();
            } catch (err) {
                console.error(err);
                this.emit("output", "Error: " + err.message + "\n");
            }
            this.emit("status");
        }

        connect() { return this.guarded(() => this.backend.connect()); }
        disconnect() { return this.guarded(() => this.backend.disconnect()); }
        toggle() { return this.connected ? this.disconnect() : this.connect(); }
        run(code) { return this.guarded(() => this.backend.run(code)); }
        stop() { return this.guarded(() => this.backend.stop()); }
        restart() { return this.guarded(() => this.backend.restart()); }
    }

    window.robotLink = new RobotLink();
})();
