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
 *   chip        a microcontroller on a PCB: traces, passives, signals into the chip
 *
 *   lcd         face slides: glows behind the robot's screen, twinkling pixels
 *   boot        opening slide: like lcd, plus pixels rising from the floor
 *
 * Animations always run, even if the desktop asks for reduced motion (KDE
 * can switch that on system-wide): they are part of the talk.
 */
(function () {
    "use strict";

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
                ctx.strokeStyle = `rgba(${c.line}, ${c.soft * 0.8})`;
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
            // PCB traces enter from both edges along fixed lanes. Every trace
            // jogs down by half a lane at 45°, so neighbours never touch.
            init(w, h, slide) {
                let seed = 11;
                const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
                const lane = 30, top = h * 0.12, bottom = h * 0.88;
                // on text slides the left traces stay inside the margin
                const text = slide.dataset.scene === "sheet";
                const leftReach = text ? 0.07 : 0.17, rightReach = text ? 0.1 : 0.18;
                const traces = [];
                // the same lanes on both sides (balanced), each side with its
                // own lengths and jogs so it does not look mirrored
                const lanes = [];
                for (let y = top; y < bottom; y += lane) if (rand() >= 0.3) lanes.push(y);
                [-1, 1].forEach((side) => {
                    for (const y of lanes) {
                        const inward = -side;
                        const edge = side < 0 ? -10 : w + 10;
                        const reach = w * (side < 0 ? leftReach : rightReach) * (0.45 + rand() * 0.55);
                        const jog = reach * (0.3 + rand() * 0.3);
                        traces.push({
                            pts: [[edge, y], [edge + inward * jog, y],
                                [edge + inward * (jog + lane / 2), y + lane / 2],
                                [edge + inward * reach, y + lane / 2]],
                            phase: rand(),
                            speed: 0.05 + rand() * 0.05,
                        });
                    }
                });
                traces.forEach((trace) => {
                    trace.lengths = trace.pts.slice(1).map(([x, y], i) =>
                        Math.hypot(x - trace.pts[i][0], y - trace.pts[i][1]));
                    trace.total = trace.lengths.reduce((a, b) => a + b, 0);
                });
                return {traces};
            },
            draw(ctx, w, h, t, s, c) {
                ctx.lineWidth = 3;
                ctx.lineJoin = "round";
                s.traces.forEach((trace) => {
                    const near = trace.pts.some(([x, y]) => Math.hypot(pointer.x - x, pointer.y - y) < 90);
                    ctx.strokeStyle = near ? `rgba(${c.accent}, 0.75)` : `rgba(${c.line}, ${c.soft * 1.2})`;
                    ctx.beginPath();
                    trace.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
                    ctx.stroke();
                    const [ex, ey] = trace.pts[trace.pts.length - 1];
                    ctx.beginPath();
                    ctx.arc(ex, ey, 6, 0, Math.PI * 2);
                    ctx.stroke();
                    // the electron travels to the pad and starts again
                    let d = ((t * trace.speed * (near ? 3 : 1)) + trace.phase * trace.total) % trace.total;
                    for (let i = 0; i < trace.lengths.length; i++) {
                        if (d <= trace.lengths[i]) {
                            const [ax, ay] = trace.pts[i], [bx, by] = trace.pts[i + 1];
                            const k = d / trace.lengths[i];
                            ctx.fillStyle = `rgba(${c.accent}, 0.95)`;
                            ctx.beginPath();
                            ctx.arc(ax + (bx - ax) * k, ay + (by - ay) * k, 4, 0, Math.PI * 2);
                            ctx.fill();
                            break;
                        }
                        d -= trace.lengths[i];
                    }
                });
            },
        },

        chip: {
            // A QFP microcontroller soldered on a PCB, half off the right edge
            // (the board continues beyond the screen, the text column stays
            // clear): copper traces fan out from its pins to vias, a couple
            // of passives sit next to it and signals travel into the chip,
            // which glows with activity.
            init(w, h) {
                const s = Math.min(w, h) * 0.46;              // package size
                const cx = w * 1.02, cy = h * 0.62;
                const n = 12, pitch = s / (n + 1), lead = s * 0.07;
                const traces = [];
                let seed = 3;
                const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
                // four sides: outward normal (nx, ny) and the along-side axis (ax, ay)
                [[1, 0, 0, 1], [-1, 0, 0, 1], [0, -1, 1, 0], [0, 1, 1, 0]].forEach(([nx, ny, ax, ay]) => {
                    for (let i = 0; i < n; i++) {
                        const k = (i + 1) * pitch - s / 2;           // offset along the side
                        const x0 = cx + nx * (s / 2 + lead) + ax * k;
                        const y0 = cy + ny * (s / 2 + lead) + ay * k;
                        const fan = k / (s / 2);                    // -1..1, spreads outwards
                        const out1 = 30 + rand() * 30;
                        const spread = fan * (40 + rand() * 30);
                        // left traces stop early: the text column lives there
                        const reach = nx < 0 ? 20 + rand() * 50 : 140 + rand() * 260;
                        const p1 = [x0 + nx * out1, y0 + ny * out1];
                        const p2 = [p1[0] + nx * Math.abs(spread) + ax * spread, p1[1] + ny * Math.abs(spread) + ay * spread];
                        const p3 = [p2[0] + nx * reach, p2[1] + ny * reach];
                        traces.push({pts: [[x0, y0], p1, p2, p3], via: rand() < 0.75});
                    }
                });
                traces.forEach((trace) => {
                    trace.lengths = trace.pts.slice(1).map(([x, y], i) => Math.hypot(x - trace.pts[i][0], y - trace.pts[i][1]));
                    trace.total = trace.lengths.reduce((a, b) => a + b, 0);
                });
                // decoupling caps above the package, clear of title and title block
                const parts = [
                    {x: cx - s * 0.18, y: cy - s * 0.78, w: 26, h: 14},
                    {x: cx - s * 0.02, y: cy - s * 0.9, w: 14, h: 26},
                ];
                return {s, cx, cy, n, pitch, lead, traces, parts, pulses: [], heat: 0, last: 0};
            },
            draw(ctx, w, h, t, st, c) {
                const {s, cx, cy, n, pitch, lead} = st;
                const now = performance.now();
                // copper traces and vias
                ctx.lineWidth = 3;
                ctx.lineJoin = "round";
                ctx.lineCap = "round";
                st.traces.forEach((trace) => {
                    const near = trace.pts.some(([x, y]) => Math.hypot(pointer.x - x, pointer.y - y) < 60);
                    ctx.strokeStyle = near ? `rgba(${c.accent}, 0.6)` : `rgba(${c.line}, ${c.soft * 1.15})`;
                    ctx.beginPath();
                    trace.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
                    ctx.stroke();
                    if (trace.via) {
                        const [vx, vy] = trace.pts[3];
                        ctx.beginPath();
                        ctx.arc(vx, vy, 6, 0, Math.PI * 2);
                        ctx.stroke();
                    }
                });
                // a signal every few frames, travelling from a via into a pin
                if (now - st.last > 120) {
                    st.pulses.push({trace: st.traces[Math.floor(Math.random() * st.traces.length)], born: now});
                    st.last = now;
                }
                st.pulses = st.pulses.filter((p) => {
                    const k = (now - p.born) / 900;
                    if (k >= 1) { st.heat = Math.min(1, st.heat + 0.12); return false; }
                    let d = (1 - k) * p.trace.total;
                    for (let i = 0; i < p.trace.lengths.length; i++) {
                        if (d <= p.trace.lengths[i]) {
                            const [ax, ay] = p.trace.pts[i], [bx, by] = p.trace.pts[i + 1];
                            const f = d / p.trace.lengths[i];
                            ctx.fillStyle = `rgba(${c.accent}, 0.95)`;
                            ctx.beginPath();
                            ctx.arc(ax + (bx - ax) * f, ay + (by - ay) * f, 3.5, 0, Math.PI * 2);
                            ctx.fill();
                            break;
                        }
                        d -= p.trace.lengths[i];
                    }
                    return true;
                });
                st.heat *= 0.96;
                // ceramic capacitors with tinned ends
                st.parts.forEach((part) => {
                    ctx.fillStyle = "#b9935f";
                    ctx.strokeStyle = "rgba(31, 42, 68, 0.35)";
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.roundRect(part.x - part.w / 2, part.y - part.h / 2, part.w, part.h, 2);
                    ctx.fill();
                    ctx.stroke();
                    ctx.fillStyle = "#d9dde2";
                    const e = 6;
                    if (part.h > part.w) {
                        ctx.fillRect(part.x - part.w / 2, part.y - part.h / 2, part.w, e);
                        ctx.fillRect(part.x - part.w / 2, part.y + part.h / 2 - e, part.w, e);
                    } else {
                        ctx.fillRect(part.x - part.w / 2, part.y - part.h / 2, e, part.h);
                        ctx.fillRect(part.x + part.w / 2 - e, part.y - part.h / 2, e, part.h);
                    }
                });
                // gull-wing leads on the four sides
                ctx.fillStyle = "#b8bdc6";
                for (let i = 0; i < n; i++) {
                    const k = (i + 1) * pitch - s / 2;
                    const pw = pitch * 0.45;
                    ctx.fillRect(cx + s / 2, cy + k - pw / 2, lead, pw);
                    ctx.fillRect(cx - s / 2 - lead, cy + k - pw / 2, lead, pw);
                    ctx.fillRect(cx + k - pw / 2, cy - s / 2 - lead, pw, lead);
                    ctx.fillRect(cx + k - pw / 2, cy + s / 2, pw, lead);
                }
                // package body: black epoxy with a soft highlight
                const body = ctx.createLinearGradient(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2);
                body.addColorStop(0, "#2b2e35");
                body.addColorStop(1, "#15171b");
                ctx.fillStyle = body;
                ctx.beginPath();
                ctx.roundRect(cx - s / 2, cy - s / 2, s, s, 6);
                ctx.fill();
                // activity glow from the die
                const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, s * 0.5);
                glow.addColorStop(0, `rgba(${c.accent}, ${0.08 + st.heat * 0.35})`);
                glow.addColorStop(1, `rgba(${c.accent}, 0)`);
                ctx.fillStyle = glow;
                ctx.fillRect(cx - s / 2, cy - s / 2, s, s);
                // pin 1 dot and laser marking on the visible half
                ctx.fillStyle = "rgba(255, 255, 255, 0.18)";
                ctx.beginPath();
                ctx.arc(cx - s / 2 + 16, cy - s / 2 + 16, 6, 0, Math.PI * 2);
                ctx.fill();
                const tx = cx - s * 0.42;
                ctx.fillStyle = "rgba(233, 238, 242, 0.75)";
                ctx.font = `700 ${Math.round(s * 0.11)}px 'JetBrains Mono', monospace`;
                ctx.fillText("ESP32-S3", tx, cy - s * 0.04);
                ctx.fillStyle = "rgba(233, 238, 242, 0.45)";
                ctx.font = `500 ${Math.round(s * 0.055)}px 'JetBrains Mono', monospace`;
                ctx.fillText("Xtensa LX7", tx, cy + s * 0.08);
                ctx.fillText("2526  N8R8", tx, cy + s * 0.16);
            },
        },

        // Neon section slides: a manga sunburst behind Stack-chan. The rays
        // unfold as the robot lands (stackchan3d.js "peek"), then turn slowly
        // among twinkling sparkles; a click throws a burst of sparkles.
        stage: {
            init: (w, h, slide) => ({
                born: performance.now(),
                // centre behind the robot when there is one, else the corner
                cx: slide.querySelector('.stackchan-3d[data-mode="peek"]') ? 0.82 : 0.9,
                cy: 0.62,
                sparkles: Array.from({length: 26}, () => ({
                    x: Math.random(), y: Math.random(), size: 6 + Math.random() * 14,
                    phase: Math.random() * Math.PI * 2, speed: 0.6 + Math.random() * 1.4,
                })),
                bursts: [],
            }),
            click(s, x, y) {
                for (let i = 0; i < 22; i++) {
                    const a = Math.random() * Math.PI * 2, v = 7 + Math.random() * 9;
                    s.bursts.push({x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 2,
                        size: 8 + Math.random() * 14, life: 1});
                }
            },
            draw(ctx, w, h, t, s) {
                const age = (performance.now() - s.born) / 1000;
                const cx = s.cx * w, cy = s.cy * h;
                const reach = Math.hypot(w, h);
                // rays unfold just as the robot lands (~0.85 s), with overshoot
                const p = Math.min(1, Math.max(0, (age - 0.7) / 0.9));
                const open = p === 0 ? 0 : 1 + 2.4 * Math.pow(p - 1, 3) + 1.4 * Math.pow(p - 1, 2);
                const rays = 18, turn = age * 0.05;
                const sweep = Math.PI / rays * Math.max(0, open);
                ctx.fillStyle = "rgba(255, 255, 255, 0.11)";
                for (let i = 0; i < rays; i++) {
                    const a = turn + i * Math.PI * 2 / rays;
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.arc(cx, cy, reach, a - sweep / 2, a + sweep / 2);
                    ctx.closePath();
                    ctx.fill();
                }
                // warm halo that breathes behind the robot
                const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, h * (0.55 + 0.04 * Math.sin(age * 1.6)));
                halo.addColorStop(0, `rgba(255, 236, 246, ${0.55 * Math.min(1, open)})`);
                halo.addColorStop(1, "rgba(255, 236, 246, 0)");
                ctx.fillStyle = halo;
                ctx.fillRect(0, 0, w, h);
                // darker vignette on the edges gives depth to the flat pink
                const vignette = ctx.createRadialGradient(w * 0.4, h * 0.45, h * 0.3, w * 0.5, h * 0.5, reach * 0.62);
                vignette.addColorStop(0, "rgba(120, 10, 70, 0)");
                vignette.addColorStop(1, "rgba(120, 10, 70, 0.32)");
                ctx.fillStyle = vignette;
                ctx.fillRect(0, 0, w, h);

                const star = (x, y, r, alpha) => {
                    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
                    ctx.beginPath();
                    ctx.moveTo(x, y - r);
                    ctx.quadraticCurveTo(x, y, x + r * 0.8, y);
                    ctx.quadraticCurveTo(x, y, x, y + r);
                    ctx.quadraticCurveTo(x, y, x - r * 0.8, y);
                    ctx.quadraticCurveTo(x, y, x, y - r);
                    ctx.fill();
                };
                const fadeIn = Math.min(1, Math.max(0, age - 1.2));
                s.sparkles.forEach((sp) => {
                    const twinkle = Math.max(0, Math.sin(age * sp.speed * 2 + sp.phase));
                    const y = ((sp.y - age * 0.006 * sp.speed) % 1 + 1) % 1;
                    star(sp.x * w, y * h, sp.size * (0.4 + 0.6 * twinkle), 0.7 * twinkle * fadeIn);
                });
                s.bursts = s.bursts.filter((b) => {
                    b.x += b.vx; b.y += b.vy; b.vy += 0.18; b.life -= 0.022;
                    if (b.life > 0) star(b.x, b.y, b.size * b.life, b.life);
                    return b.life > 0;
                });
            },
        },

        lcd: {
            init(w, h) {
                let seed = 5;
                const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
                const pixels = Array.from({length: 70}, () => ({
                    x: rand() * w, y: rand() * h, size: 3 + Math.floor(rand() * 3) * 2,
                    phase: rand() * Math.PI * 2, speed: 0.6 + rand(), pink: rand() < 0.35,
                }));
                return {pixels, rising: []};
            },
            draw(ctx, w, h, t, s) {
                // two glows orbiting behind the face, nudged by the pointer
                const px = pointer.x > 0 ? (pointer.x / w - 0.5) : 0;
                const py = pointer.y > 0 ? (pointer.y / h - 0.5) : 0;
                [["255, 79, 154", 0], ["57, 208, 216", Math.PI]].forEach(([rgb, offset]) => {
                    const a = t / 5200 + offset;
                    const gx = w * (0.5 + 0.22 * Math.cos(a) + px * 0.08);
                    const gy = h * (0.45 + 0.16 * Math.sin(a) + py * 0.08);
                    const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, Math.max(w, h) * 0.38);
                    g.addColorStop(0, `rgba(${rgb}, 0.22)`);
                    g.addColorStop(1, `rgba(${rgb}, 0)`);
                    ctx.fillStyle = g;
                    ctx.fillRect(0, 0, w, h);
                });
                // twinkling pixels, like a screen waking up
                s.pixels.forEach((p) => {
                    const alpha = 0.15 + 0.35 * (0.5 + 0.5 * Math.sin(t / 700 * p.speed + p.phase));
                    ctx.fillStyle = p.pink ? `rgba(255, 79, 154, ${alpha})` : `rgba(233, 238, 242, ${alpha * 0.7})`;
                    ctx.fillRect(p.x, p.y, p.size, p.size);
                });
                // slow scanline band
                const band = (t / 18) % (h + 200) - 100;
                const g = ctx.createLinearGradient(0, band - 60, 0, band + 60);
                g.addColorStop(0, "rgba(255,255,255,0)");
                g.addColorStop(0.5, "rgba(255,255,255,0.035)");
                g.addColorStop(1, "rgba(255,255,255,0)");
                ctx.fillStyle = g;
                ctx.fillRect(0, band - 60, w, 120);
            },
        },
    };

    // the opening slide: lcd plus pixels rising like bubbles
    effects.boot = {
        init: (w, h) => effects.lcd.init(w, h),
        draw(ctx, w, h, t, s, c) {
            effects.lcd.draw(ctx, w, h, t, s, c);
            if (s.rising.length < 40 && Math.random() < 0.2) {
                s.rising.push({x: Math.random() * w, y: h + 10, v: 0.4 + Math.random() * 1.2,
                    size: 4 + Math.floor(Math.random() * 3) * 2, pink: Math.random() < 0.5});
            }
            s.rising = s.rising.filter((p) => {
                p.y -= p.v;
                p.x += Math.sin((t + p.y * 7) / 900) * 0.3;
                const alpha = Math.min(1, p.y / h) * 0.6;
                ctx.fillStyle = p.pink ? `rgba(255, 79, 154, ${alpha})` : `rgba(57, 208, 216, ${alpha})`;
                ctx.fillRect(p.x, p.y, p.size, p.size);
                return p.y > -20;
            });
        },
    };

    const SCENE_DEFAULTS = {face: "lcd", boot: "boot", neon: "stage"};

    // ---------------------------------------------------------------- lifecycle

    function attach(slide) {
        const name = slide.dataset.fx || SCENE_DEFAULTS[slide.dataset.scene];
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
        return {slide, canvas, ctx, effect, w, h, colors: palette(slide), state: effect.init ? effect.init(w, h, slide) : {}};
    }

    function frame(t) {
        if (!active) return;
        const {ctx, w, h, effect, state, colors} = active;
        ctx.clearRect(0, 0, w, h);
        effect.draw(ctx, w, h, t, state, colors);
        requestAnimationFrame(frame);
    }

    function show(slide) {
        if (active && active.canvas) active.ctx.clearRect(0, 0, active.w, active.h);
        active = (slide.dataset.fx || SCENE_DEFAULTS[slide.dataset.scene]) ? attach(slide) : null;
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
