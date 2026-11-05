/*
 * Simulator worker: runs the user's program on MicroPython (WebAssembly)
 * with the Stack-chan hardware shims. Blocking calls (sleep, inputs,
 * camera, microphone) use shared memory so the program can run
 * synchronously, exactly like on the robot.
 */
import {loadMicroPython} from "../vendor/micropython/micropython.mjs";
import {IDX, MIC_RATE, MIC_SAMPLES} from "./layout.js";

let control, mic, camera;

function post(msg, transfer) {
    self.postMessage(msg, transfer || []);
}

function sleep(ms) {
    if (typeof SharedArrayBuffer !== "undefined" && control.buffer instanceof SharedArrayBuffer) {
        Atomics.wait(control, IDX.SLEEP, 0, ms);
    } else {
        const end = performance.now() + ms;
        while (performance.now() < end) { /* no shared memory: busy wait */ }
    }
}

function f(i) { return control[i] / 1000; }

function makeHost(mp) {
    const FS = mp.FS;
    let lastHand = 0;
    return {
        inputs() {
            const hand = control[IDX.HAND];
            const data = {
                touch: control[IDX.TOUCH], tx: control[IDX.TX], ty: control[IDX.TY],
                pwr: control[IDX.PWR],
                head: [control[IDX.HEAD0], control[IDX.HEAD1], control[IDX.HEAD2]],
                accel: [f(IDX.AX), f(IDX.AY), f(IDX.AZ)],
                gyro: [f(IDX.GX), f(IDX.GY), f(IDX.GZ)],
                lux: f(IDX.LUX), prox: control[IDX.PROX], battery: control[IDX.BATTERY],
                hand: hand !== lastHand ? [f(IDX.HAND_X), f(IDX.HAND_Y)] : null,
            };
            lastHand = hand;
            return JSON.stringify(data);
        },
        sleep,
        frame(path, w, h) {
            const data = FS.readFile(path);
            post({t: "frame", w, h, data}, [data.buffer]);
        },
        state(json) { post({t: "state", json}); },
        log(level, msg) { post({t: "log", level, msg}); },
        event(json) { post({t: "event", json}); },
        tone(freq, ms, volume) { post({t: "tone", freq, ms, volume}); },
        audio(path) {
            const data = FS.readFile(path);
            post({t: "audio", data}, [data.buffer]);
        },
        mic(path, frames, rate) {
            if (!control[IDX.MIC_ON]) return 0;
            const need = Math.ceil(frames * MIC_RATE / rate);
            const end = control[IDX.MIC_WRITE];
            const out = new Int16Array(frames);
            for (let i = 0; i < frames; i++) {
                const j = Math.floor(i * MIC_RATE / rate);
                out[i] = mic[(end - need + j + MIC_SAMPLES * 4) % MIC_SAMPLES];
            }
            FS.writeFile(path, new Uint8Array(out.buffer));
            return frames;
        },
        camera(path) {
            if (!control[IDX.CAM_FRAME]) return 0;
            FS.writeFile(path, new Uint8Array(camera));   // copy out of shared memory
            return 1;
        },
        http(method, url, headersJson, body) {
            try {
                const xhr = new XMLHttpRequest();
                xhr.open(method, url, false);
                for (const [k, v] of Object.entries(JSON.parse(headersJson))) xhr.setRequestHeader(k, v);
                xhr.send(body || null);
                return JSON.stringify({status: xhr.status, text: xhr.responseText});
            } catch (err) {
                return JSON.stringify({error: String(err.message || err)});
            }
        },
    };
}

function writeTree(FS, files) {
    for (const [path, b64] of Object.entries(files)) {
        const dir = path.slice(0, path.lastIndexOf("/"));
        FS.mkdirTree(dir);
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        FS.writeFile(path, bytes);
    }
}

self.onmessage = async (event) => {
    const msg = event.data;
    if (msg.t !== "run") return;
    control = new Int32Array(msg.control);
    mic = new Int16Array(msg.mic);
    camera = new Uint8Array(msg.camera);
    try {
        const bundle = await (await fetch(msg.bundleUrl)).json();
        const mp = await loadMicroPython({
            heapsize: 8 * 1024 * 1024,
            pystack: 8 * 1024,
            stdout: (line) => post({t: "stdout", text: line + "\n"}),
            stderr: (line) => post({t: "stdout", text: line + "\n"}),
        });
        writeTree(mp.FS, bundle);
        mp.FS.mkdirTree("/tmp");
        mp.FS.mkdirTree("/flash");
        for (const [name, text] of Object.entries(msg.files || {})) {
            mp.FS.writeFile("/flash/" + name, text);
        }
        mp.FS.writeFile("/flash/main.py", msg.code);
        mp.registerJsModule("simhost", makeHost(mp));
        post({t: "started"});
        mp.runPython([
            "import sys",
            "sys.path.insert(0, '/sim')",
            "import simhost",
            "from stackchan_sim import runner",
            "runner.run(simhost, '/flash/main.py')",
        ].join("\n"));
    } catch (err) {
        post({t: "stdout", text: "[simulador] " + (err.message || err) + "\n"});
    }
    post({t: "done"});
};
