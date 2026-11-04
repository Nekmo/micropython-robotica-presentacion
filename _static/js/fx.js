/*
 * Animated, pointer-reactive slide backgrounds.
 *
 * A section opts in with ``:data-fx: <name>``. The effect is drawn on a
 * canvas inside the slide background, only while that slide is visible,
 * and follows the pointer, so the presenter can "play" with it:
 *
 *   wave        audio waveform; reacts to the microphone (press M)
 *   protractor  servo protractor whose horn points at the pointer
 *   ripples     touch / proximity rings spawned by the pointer
 *   viewfinder  camera viewfinder with a detection box chasing the pointer
 *   pixels      LCD pixel grid lit by the pointer, fading like a trail
 *   neural      small neural network with signals; nodes near the pointer fire
 *   circuit     PCB traces with travelling electrons, lit near the pointer
 *
 * With prefers-reduced-motion a single still frame is drawn.
 */
(function () {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pointer = {x: -1000, y: -1000, moved: 0};
    let active = null;            // {slide, canvas, ctx, effect, state}
    let mic = null;               // {analyser, data} when the microphone is on

    document.addEventListener("pointermove", (e) => {
        pointer.x = e.clientX;
        pointer.y = e.clientY;
        pointer.moved = performance.now();
    });
    document.addEventListener("pointerdown", (e) => {
        if (active && active.effect.click) active.effect.click(active.state, e.clientX, e.clientY);
    });

    // Colours follow the slide scene: ink on light sheets, LED cyan on dark
    function palette(slide) {
        const scene = slide.dataset.scene;
        if (scene === "sheet") return {line: "31, 42, 68", accent: "255, 79, 154", soft: 0.16};
        if (scene === "neon") return {line: "31, 42, 68", accent: "233, 238, 242", soft: 0.22};
        return {line: "57, 208, 216", accent: "255, 79, 154", soft: 0.22};
    }

    function micLevel() {
        if (!mic) return 0;
        mic.analyser.getByteTimeDomainData(mic.data);
        let peak = 0;
        for (let i = 0; i < mic.data.length; i++) peak = Math.max(peak, Math.abs(mic.data[i] - 128));
        return Math.min(1, peak / 64);
    }

    async function toggleMic() {
        if (mic) {
            mic.stream.getTracks().forEach((t) => t.stop());
            mic.context.close();
            mic = null;
            return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const context = new AudioContext();
        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        context.createMediaStreamSource(stream).connect(analyser);
        mic = {stream, context, analyser, data: new Uint8Array(analyser.fftSize)};
    }

    // ---------------------------------------------------------------- effects

    const effects = {
        wave: {
            init: () => ({level: 0}),
            draw(ctx, w, h, t, s, c) {
                const target = mic ? micLevel() : 0.25 + 0.15 * Math.sin(t / 900);
                s.level += (target - s.level) * 0.15;
                const py = pointer.y > 0 ? pointer.y / h : 0.5;
                const freq = 1.5 + py * 5;            // pointer height changes the pitch
                const mid = h * 0.86;              // below the text, above the title block
                for (let layer = 0; layer < 4; layer++) {
                    ctx.beginPath();
                    const amp = h * (0.035 + s.level * 0.14) * (1 - layer * 0.2);
                    for (let x = 0; x <= w; x += 6) {
                        const k = x / w;
                        const envelope = Math.sin(Math.PI * k);
                        const y = mid + amp * envelope *
                            Math.sin(k * Math.PI * 2 * freq + t / (420 + layer * 160) + layer * 1.3);
                        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }
                    ctx.strokeStyle = layer === 0 ? `rgba(${c.accent}, 0.55)` : `rgba(${c.line}, ${c.soft * (1 - layer * 0.2)})`;
                    ctx.lineWidth = layer === 0 ? 3 : 2;
                    ctx.stroke();
                }
                if (mic) {
                    ctx.fillStyle = `rgba(${c.accent}, 0.8)`;
                    ctx.font = "600 14px 'JetBrains Mono', monospace";
                    ctx.fillText("● micrófono", 34, h - 34);
                }
            },
        },

        protractor: {
            init: () => ({angle: 90}),
            draw(ctx, w, h, t, s, c) {
                const cx = w * 0.84, cy = h * 0.9, r = Math.min(w, h) * 0.24;
                // pointer angle, clamped to the servo's 0..180 range
                let target = 90 + 40 * Math.sin(t / 1600);
                if (performance.now() - pointer.moved < 4000) {
                    target = Math.atan2(cy - pointer.y, cx - pointer.x) * 180 / Math.PI;
                    target = 180 - Math.max(0, Math.min(180, target));
                }
                s.angle += (target - s.angle) * 0.08;      // a servo eases into position
                ctx.lineWidth = 2;
                ctx.strokeStyle = `rgba(${c.line}, ${c.soft * 1.6})`;
                ctx.beginPath();
                ctx.arc(cx, cy, r, Math.PI, 0);
                ctx.stroke();
                for (let a = 0; a <= 180; a += 10) {
                    const rad = Math.PI - a * Math.PI / 180;
                    const inner = a % 30 === 0 ? r * 0.88 : r * 0.93;
                    ctx.beginPath();
                    ctx.moveTo(cx + Math.cos(rad) * inner, cy - Math.sin(rad) * inner);
                    ctx.lineTo(cx + Math.cos(rad) * r, cy - Math.sin(rad) * r);
                    ctx.stroke();
                }
                const rad = Math.PI - s.angle * Math.PI / 180;
                ctx.strokeStyle = `rgba(${c.accent}, 0.85)`;
                ctx.lineWidth = 6;
                ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.lineTo(cx + Math.cos(rad) * r * 0.8, cy - Math.sin(rad) * r * 0.8);
                ctx.stroke();
                ctx.fillStyle = `rgba(${c.accent}, 0.9)`;
                ctx.beginPath();
                ctx.arc(cx, cy, 10, 0, Math.PI * 2);
                ctx.fill();
                ctx.font = "600 22px 'JetBrains Mono', monospace";
                ctx.fillStyle = `rgba(${c.line}, 0.7)`;
                ctx.fillText(`${Math.round(s.angle)}°`, cx - 24, cy - r - 18);
            },
        },

        ripples: {
            init: () => ({rings: [], last: 0}),
            click(s, x, y) { s.rings.push({x, y, born: performance.now(), strong: true}); },
            draw(ctx, w, h, t, s, c) {
                const now = performance.now();
                if (now - pointer.moved < 200 && now - s.last > 140) {
                    s.rings.push({x: pointer.x, y: pointer.y, born: now});
                    s.last = now;
                }
                if (now - s.last > 1400) {    // idle: the robot "senses" on its own
                    s.rings.push({x: w * 0.8, y: h * 0.7, born: now});
                    s.last = now;
                }
                s.rings = s.rings.filter((ring) => now - ring.born < 2200);
                s.rings.forEach((ring) => {
                    const age = (now - ring.born) / 2200;
                    ctx.beginPath();
                    ctx.arc(ring.x, ring.y, 8 + age * (ring.strong ? 260 : 160), 0, Math.PI * 2);
                    ctx.strokeStyle = ring.strong ? `rgba(${c.accent}, ${0.7 * (1 - age)})`
                        : `rgba(${c.line}, ${c.soft * 2 * (1 - age)})`;
                    ctx.lineWidth = ring.strong ? 3 : 2;
                    ctx.stroke();
                });
            },
        },

        viewfinder: {
            init: () => ({x: 0.7, y: 0.6, conf: 0.9}),
            draw(ctx, w, h, t, s, c) {
                const m = 46, len = 46;
                ctx.strokeStyle = `rgba(${c.line}, ${c.soft * 2})`;
                ctx.lineWidth = 3;
                [[m, m, 1, 1], [w - m, m, -1, 1], [m, h - m, 1, -1], [w - m, h - m, -1, -1]].forEach(([x, y, dx, dy]) => {
                    ctx.beginPath();
                    ctx.moveTo(x, y + dy * len);
                    ctx.lineTo(x, y);
                    ctx.lineTo(x + dx * len, y);
                    ctx.stroke();
                });
                // scanline
                const sy = (t / 12) % h;
                ctx.fillStyle = `rgba(${c.line}, ${c.soft * 0.5})`;
                ctx.fillRect(0, sy, w, 2);
                // detection box chasing the pointer, like the face tracker
                const tracking = performance.now() - pointer.moved < 4000;
                const tx = tracking ? pointer.x / w : 0.8 + 0.05 * Math.sin(t / 1300);
                const ty = tracking ? pointer.y / h : 0.76 + 0.03 * Math.cos(t / 1100);
                s.x += (tx - s.x) * 0.1;
                s.y += (ty - s.y) * 0.1;
                s.conf += ((tracking ? 0.97 : 0.88) - s.conf) * 0.05;
                const bw = 130, bh = 150, bx = s.x * w - bw / 2, by = s.y * h - bh / 2;
                ctx.strokeStyle = `rgba(${c.accent}, 0.8)`;
                ctx.strokeRect(bx, by, bw, bh);
                ctx.fillStyle = `rgba(${c.accent}, 0.85)`;
                ctx.fillRect(bx, by - 26, 118, 26);
                ctx.fillStyle = "#fff";
                ctx.font = "600 15px 'JetBrains Mono', monospace";
                ctx.fillText(`cara ${s.conf.toFixed(2)}`, bx + 8, by - 8);
            },
        },

        pixels: {
            init: () => ({cells: new Map()}),
            draw(ctx, w, h, t, s, c) {
                const size = 22;
                const now = performance.now();
                if (now - pointer.moved < 100) {
                    const gx = Math.floor(pointer.x / size), gy = Math.floor(pointer.y / size);
                    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
                        s.cells.set(`${gx + dx},${gy + dy}`, now - (Math.abs(dx) + Math.abs(dy)) * 120);
                    }
                }
                // ambient: a tiny pixel face blinking in the corner
                const face = ["01100110", "01100110", "00000000", "00111100"];
                const blink = Math.floor(t / 2600) % 4 === 0 && (t % 2600) < 160;
                face.forEach((row, ry) => [...row].forEach((bit, rx) => {
                    if (bit === "1" && !(blink && ry < 2)) s.cells.set(`${Math.floor(w / size) - 12 + rx},${Math.floor(h / size) - 8 + ry}`, now);
                }));
                ctx.strokeStyle = `rgba(${c.line}, ${c.soft * 0.35})`;
                ctx.lineWidth = 1;
                s.cells.forEach((born, key) => {
                    const age = (now - born) / 1800;
                    if (age > 1) { s.cells.delete(key); return; }
                    const [x, y] = key.split(",").map(Number);
                    ctx.fillStyle = `rgba(${c.accent}, ${0.55 * (1 - age)})`;
                    ctx.fillRect(x * size + 2, y * size + 2, size - 4, size - 4);
                });
            },
        },

        neural: {
            init(w, h) {
                const layers = [4, 6, 6, 3];
                const nodes = [];
                layers.forEach((count, li) => {
                    for (let i = 0; i < count; i++) {
                        nodes.push({layer: li, x: w * (0.8 + li * 0.05), y: h * (0.22 + (i + 0.5) * 0.6 / count), fire: 0});
                    }
                });
                const edges = [];
                nodes.forEach((a) => nodes.forEach((b) => { if (b.layer === a.layer + 1) edges.push([a, b]); }));
                return {nodes, edges, pulses: [], last: 0};
            },
            draw(ctx, w, h, t, s, c) {
                const now = performance.now();
                if (now - s.last > 260) {
                    const edge = s.edges[Math.floor(Math.random() * s.edges.length)];
                    if (edge[0].layer === 0 || edge[0].fire > 0.3) s.pulses.push({edge, born: now});
                    s.last = now;
                }
                ctx.lineWidth = 1;
                ctx.strokeStyle = `rgba(${c.line}, ${c.soft * 0.6})`;
                s.edges.forEach(([a, b]) => {
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                });
                s.pulses = s.pulses.filter((p) => {
                    const k = (now - p.born) / 700;
                    if (k >= 1) { p.edge[1].fire = 1; return false; }
                    const [a, b] = p.edge;
                    ctx.fillStyle = `rgba(${c.accent}, 0.9)`;
                    ctx.beginPath();
                    ctx.arc(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k, 4, 0, Math.PI * 2);
                    ctx.fill();
                    return true;
                });
                s.nodes.forEach((n) => {
                    if (Math.hypot(pointer.x - n.x, pointer.y - n.y) < 70) n.fire = 1;
                    n.fire *= 0.95;
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, 9 + n.fire * 6, 0, Math.PI * 2);
                    ctx.fillStyle = n.fire > 0.05 ? `rgba(${c.accent}, ${0.25 + n.fire * 0.6})` : `rgba(${c.line}, ${c.soft})`;
                    ctx.fill();
                });
            },
        },

        circuit: {
            init(w, h) {
                // deterministic PCB-like traces along the right half
                let seed = 7;
                const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
                const traces = [];
                // traces enter from the right edge, clear of the text column
                for (let i = 0; i < 14; i++) {
                    const pts = [[w + 10, h * (0.14 + i * 0.055)]];
                    for (let j = 0; j < 4; j++) {
                        const [x, y] = pts[pts.length - 1];
                        pts.push(j % 2 === 0 ? [x - 20 - rand() * w * 0.06, y] : [x - 24, y + (rand() - 0.5) * 60]);
                    }
                    traces.push({pts, phase: rand()});
                }
                return {traces};
            },
            draw(ctx, w, h, t, s, c) {
                ctx.lineWidth = 3;
                ctx.lineJoin = "round";
                s.traces.forEach((trace) => {
                    const near = trace.pts.some(([x, y]) => Math.hypot(pointer.x - x, pointer.y - y) < 90);
                    ctx.strokeStyle = near ? `rgba(${c.accent}, 0.7)` : `rgba(${c.line}, ${c.soft})`;
                    ctx.beginPath();
                    trace.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
                    ctx.stroke();
                    const [ex, ey] = trace.pts[trace.pts.length - 1];
                    ctx.beginPath();
                    ctx.arc(ex, ey, 6, 0, Math.PI * 2);
                    ctx.stroke();
                    // an electron travelling along the trace
                    const lengths = trace.pts.slice(1).map(([x, y], i) => Math.hypot(x - trace.pts[i][0], y - trace.pts[i][1]));
                    const total = lengths.reduce((a, b) => a + b, 0);
                    let d = ((t / (near ? 4 : 14) + trace.phase * total) % total);
                    for (let i = 0; i < lengths.length; i++) {
                        if (d <= lengths[i]) {
                            const [ax, ay] = trace.pts[i], [bx, by] = trace.pts[i + 1];
                            const k = d / lengths[i];
                            ctx.fillStyle = `rgba(${c.accent}, 0.9)`;
                            ctx.beginPath();
                            ctx.arc(ax + (bx - ax) * k, ay + (by - ay) * k, 4, 0, Math.PI * 2);
                            ctx.fill();
                            break;
                        }
                        d -= lengths[i];
                    }
                });
            },
        },
    };

    // ---------------------------------------------------------------- lifecycle

    function attach(slide) {
        const name = slide.dataset.fx;
        const effect = effects[name];
        if (!effect) return null;
        const background = Reveal.getSlideBackground(slide);
        let canvas = background.querySelector("canvas.fx");
        if (!canvas) {
            canvas = document.createElement("canvas");
            canvas.className = "fx fx-" + name;
            background.appendChild(canvas);
        }
        const ratio = Math.min(window.devicePixelRatio, 2);
        const w = window.innerWidth, h = window.innerHeight;
        canvas.width = w * ratio;
        canvas.height = h * ratio;
        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return {slide, canvas, ctx, effect, w, h, colors: palette(slide), state: effect.init ? effect.init(w, h) : {}};
    }

    function frame(t) {
        if (!active) return;
        const {ctx, w, h, effect, state, colors} = active;
        ctx.clearRect(0, 0, w, h);
        effect.draw(ctx, w, h, t, state, colors);
        if (!reducedMotion) requestAnimationFrame(frame);
    }

    function show(slide) {
        if (active && active.canvas) active.ctx.clearRect(0, 0, active.w, active.h);
        active = slide.dataset.fx ? attach(slide) : null;
        if (active) requestAnimationFrame(frame);
    }

    function start() {
        show(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => show(event.currentSlide));
        window.addEventListener("resize", () => show(Reveal.getCurrentSlide()));
        // M: the wave background listens to the presenter's microphone
        Reveal.addKeyBinding({keyCode: 77, key: "M", description: "Micrófono para el fondo de onda"},
            () => toggleMic().catch((err) => console.warn(err)));
    }

    // reveal.js loads after this file: wait for the DOM, then for Reveal
    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
