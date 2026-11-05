/*
 * Screens of the small Stack-chans on "Dos formas de dibujar"
 * (``.. screen-robot:: :mode: gfx|lvgl``), 320x240 like the real screen.
 *
 *   gfx   M5GFX: primitives appear one by one, each with its call, then the
 *         whole screen is cleared and drawn again ("paint and forget")
 *   lvgl  LVGL: objects animate and a pink box marks the only area redrawn
 *   mail  the author's face; letters fly into the robot and each one pops
 *         up as a notification on its screen
 *
 * And the two AI paths of "Dos caminos" (``.. path-anim:: :mode:``):
 *
 *   chip   a face tracked by the camera, all of it inside the ESP32-S3
 *   cloud  a question travels to a large model and the answer comes back
 */
(function () {
    "use strict";

    const PINK = "#FF4F9A", CYAN = "#39D0D8", AMBER = "#FFC44D", WHITE = "#E9EEF2";
    const MONO = "'JetBrains Mono', monospace";

    // ---- M5GFX: a list of drawing calls, replayed one by one
    const GFX_STEPS = [
        ["fillScreen(BLACK)", () => {}],
        ["fillRect(20, 20, 280, 60, PINK)", (c) => { c.fillStyle = PINK; c.fillRect(20, 20, 280, 60); }],
        ["drawString('Hola', 120, 36)", (c) => {
            c.fillStyle = "#1F2A44"; c.font = "800 30px " + MONO; c.fillText("Hola", 120, 62);
        }],
        ["fillCircle(100, 140, 22, WHITE)", (c) => { c.fillStyle = WHITE; disc(c, 100, 140, 22); }],
        ["fillCircle(220, 140, 22, WHITE)", (c) => { c.fillStyle = WHITE; disc(c, 220, 140, 22); }],
        ["drawLine(120, 196, 200, 196)", (c) => {
            c.strokeStyle = WHITE; c.lineWidth = 8; c.beginPath(); c.moveTo(120, 196); c.lineTo(200, 196); c.stroke();
        }],
        ["drawRect(8, 8, 304, 224, CYAN)", (c) => { c.strokeStyle = CYAN; c.lineWidth = 3; c.strokeRect(8, 8, 304, 224); }],
    ];

    function disc(c, x, y, r) {
        c.beginPath();
        c.arc(x, y, r, 0, Math.PI * 2);
        c.fill();
    }

    function caption(c, text, color = AMBER) {
        c.fillStyle = "rgba(0, 0, 0, 0.75)";
        c.fillRect(0, 214, 320, 26);
        c.fillStyle = color;
        c.font = "600 14px " + MONO;
        c.fillText(text, 10, 232);
    }

    function drawGfx(c, t) {
        const step = Math.floor(t / 650) % (GFX_STEPS.length + 3);   // + a pause at the end
        c.fillStyle = "#000";
        c.fillRect(0, 0, 320, 240);
        const shown = Math.min(step, GFX_STEPS.length - 1);
        for (let i = 0; i <= shown; i++) GFX_STEPS[i][1](c);
        if (step === 0) {                      // the whole screen flashes: everything is drawn again
            c.fillStyle = "rgba(255, 255, 255, 0.12)";
            c.fillRect(0, 0, 320, 240);
        }
        caption(c, step < GFX_STEPS.length ? "lcd." + GFX_STEPS[step][0] : "…y vuelta a empezar");
    }

    // ---- LVGL: objects that change on their own; only their area is redrawn
    function drawLvgl(c, t) {
        const s = t / 1000;
        c.fillStyle = "#000";
        c.fillRect(0, 0, 320, 240);
        c.fillStyle = WHITE;
        c.font = "800 22px " + MONO;
        c.fillText("lv.label", 20, 40);

        const value = 0.5 + 0.45 * Math.sin(s * 1.3);   // slider
        c.fillStyle = "#2b3346";
        roundRect(c, 20, 70, 280, 14, 7);
        c.fillStyle = CYAN;
        roundRect(c, 20, 70, 280 * value, 14, 7);
        c.fillStyle = WHITE;
        disc(c, 20 + 280 * value, 77, 13);

        const arc = (s * 0.8) % 1;                       // arc
        c.strokeStyle = "#2b3346";
        c.lineWidth = 12;
        c.beginPath(); c.arc(80, 150, 38, 0, Math.PI * 2); c.stroke();
        c.strokeStyle = PINK;
        c.beginPath(); c.arc(80, 150, 38, -Math.PI / 2, -Math.PI / 2 + arc * Math.PI * 2); c.stroke();

        const press = Math.sin(s * 2.2) > 0.7;           // button
        c.fillStyle = press ? AMBER : "#3a4256";
        roundRect(c, 160, 124, 130, 52, 12);
        c.fillStyle = press ? "#1F2A44" : WHITE;
        c.font = "700 18px " + MONO;
        c.fillText("lv.button", 172, 156);

        // dirty areas: what LVGL repaints this frame
        c.strokeStyle = PINK;
        c.lineWidth = 2;
        c.setLineDash([6, 4]);
        c.strokeRect(10 + 280 * value - 6, 60, 32, 34);
        c.strokeRect(32, 102, 96, 96);
        if (Math.abs(Math.sin(s * 2.2) - 0.7) < 0.12) c.strokeRect(154, 118, 142, 64);
        c.setLineDash([]);
        caption(c, "solo repinta lo que cambia", PINK);
    }

    function roundRect(c, x, y, w, h, r) {
        c.beginPath();
        c.roundRect(x, y, Math.max(h, w), h, r);
        c.fill();
    }

    // ---- mail: the author's face; a notification pops up when a letter lands
    const face = new Image();
    face.src = "_images/cara.svg";
    const ENVELOPE = '<svg viewBox="0 0 40 28"><rect x="1.5" y="1.5" width="37" height="25" rx="3" ' +
        'fill="#E9EEF2" stroke="#FF4F9A" stroke-width="2.5"/><path d="M3 4 L20 16 L37 4" fill="none" ' +
        'stroke="#FF4F9A" stroke-width="2.5" stroke-linejoin="round"/></svg>';

    function envelope(c, x, y, w) {
        const h = w * 0.7;
        c.fillStyle = WHITE;
        c.strokeStyle = PINK;
        c.lineWidth = 3;
        c.beginPath(); c.roundRect(x, y, w, h, 4); c.fill(); c.stroke();
        c.beginPath(); c.moveTo(x + 3, y + 4); c.lineTo(x + w / 2, y + h * 0.58); c.lineTo(x + w - 3, y + 4); c.stroke();
    }

    function drawMail(c, t, robot) {
        c.fillStyle = "#E9EEF2";
        c.fillRect(0, 0, 320, 240);
        if (face.complete && face.naturalWidth) c.drawImage(face, 70, 10, 180, 180);
        c.fillStyle = "#1F2A44";
        c.font = "800 22px " + MONO;
        c.textAlign = "center";
        c.fillText("Nekmo", 160, 222);
        c.textAlign = "left";
        const since = t - (robot.notifiedAt || -1e9);
        if (since < 2200) {                    // the banner slides down, then up
            const k = Math.min(1, since / 250, (2200 - since) / 250);
            const y = -64 + 74 * k;
            c.fillStyle = "rgba(31, 42, 68, 0.92)";
            c.beginPath(); c.roundRect(14, y, 292, 56, 12); c.fill();
            envelope(c, 26, y + 11, 46);
            c.fillStyle = WHITE;
            c.font = "700 18px " + MONO;
            c.fillText("Nuevo mensaje", 86, y + 26);
            c.fillStyle = PINK;
            c.font = "600 14px " + MONO;
            c.fillText(robot.notifyText || "", 86, y + 46);
        }
        if (robot.mailCount) {                 // unread badge
            c.fillStyle = PINK;
            disc(c, 292, 214, 18);
            c.fillStyle = WHITE;
            c.font = "800 18px " + MONO;
            c.textAlign = "center";
            c.fillText(String(robot.mailCount), 292, 220);
            c.textAlign = "left";
        }
    }

    const SENDERS = ["@nekmocom", "contacto@nekmo.com", "t.me/nekmo", "nekmo@nekmo.org", "nekmo.com"];

    // a letter flies from somewhere on the left into the robot's screen
    function sendLetter(robot) {
        const letter = document.createElement("div");
        letter.className = "mail-letter";
        letter.innerHTML = ENVELOPE;
        const angle = (Math.random() * 0.9 + 0.55) * Math.PI;   // from the left half
        const reach = 320 + Math.random() * 180;
        letter.style.setProperty("--from-x", `${Math.cos(angle) * reach}px`);
        letter.style.setProperty("--from-y", `${-Math.abs(Math.sin(angle)) * reach * 0.6 - 40}px`);
        letter.style.setProperty("--spin", `${(Math.random() - 0.5) * 70}deg`);
        robot.appendChild(letter);
        letter.addEventListener("animationend", () => {
            letter.remove();
            robot.notifiedAt = performance.now();
            robot.mailCount = (robot.mailCount || 0) % 9 + 1;
            robot.notifyText = SENDERS[Math.floor(Math.random() * SENDERS.length)];
        });
    }

    // ---- "Dos caminos": on the chip
    function drawChip(c, t) {
        const s = t / 1000;
        c.clearRect(0, 0, 480, 240);
        // a moving face and its detection box
        const fx = 105 + 50 * Math.sin(s * 0.9), fy = 104 + 14 * Math.sin(s * 1.7);
        c.fillStyle = AMBER;
        disc(c, fx, fy, 26);
        c.fillStyle = "#1F2A44";
        disc(c, fx - 9, fy - 6, 4); disc(c, fx + 9, fy - 6, 4);
        c.fillRect(fx - 9, fy + 9, 18, 3);
        c.strokeStyle = PINK;
        c.lineWidth = 3;
        c.strokeRect(fx - 32, fy - 32, 64, 64);
        // chip with pins and neurons firing inside
        const cx = 360, cy = 104;
        c.fillStyle = "#1F2A44";
        c.beginPath(); c.roundRect(cx - 62, cy - 62, 124, 124, 10); c.fill();
        c.fillStyle = "#8a93a6";
        for (let i = 0; i < 6; i++) {
            const o = -50 + i * 20;
            c.fillRect(cx + o - 3, cy - 74, 6, 12); c.fillRect(cx + o - 3, cy + 62, 6, 12);
            c.fillRect(cx - 74, cy + o - 3, 12, 6); c.fillRect(cx + 62, cy + o - 3, 12, 6);
        }
        for (let i = 0; i < 9; i++) {
            const nx = cx - 36 + (i % 3) * 36, ny = cy - 36 + Math.floor(i / 3) * 36;
            const on = Math.sin(s * 5 + i * 1.3) > 0.4;
            c.fillStyle = on ? CYAN : "#3a4256";
            disc(c, nx, ny, on ? 9 : 7);
        }
        // the picture goes into the chip, the answer stays there
        const k = (s * 0.9) % 1;
        c.fillStyle = PINK;
        disc(c, 196 + (cx - 70 - 196) * k, cy, 6);
        c.strokeStyle = "rgba(31, 42, 68, 0.4)";
        c.setLineDash([6, 6]);
        c.lineWidth = 2;
        c.beginPath(); c.moveTo(196, cy); c.lineTo(cx - 70, cy); c.stroke();
        c.setLineDash([]);
        noWifi(c, 448, 26);
    }

    // ---- "Dos caminos": in the cloud
    function drawCloud(c, t) {
        const s = t / 1000;
        c.clearRect(0, 0, 480, 240);
        // a tiny Stack-chan
        const rx = 70, ry = 150;
        c.fillStyle = "#d7dade";
        c.beginPath(); c.roundRect(rx - 48, ry - 40, 96, 74, 16); c.fill();
        c.fillStyle = "#000";
        c.beginPath(); c.roundRect(rx - 38, ry - 32, 76, 54, 6); c.fill();
        const phase = (s % 4) / 4;              // ask, think, answer
        c.fillStyle = WHITE;
        disc(c, rx - 14, ry - 10, 5); disc(c, rx + 14, ry - 10, 5);
        const talking = phase > 0.72 && Math.sin(s * 22) > 0;
        c.fillRect(rx - 10, ry + 6, 20, talking ? 7 : 3);
        c.fillStyle = "#4a4d52";
        c.fillRect(rx - 34, ry + 34, 68, 14);
        // the cloud
        const kx = 370, ky = 70;
        c.fillStyle = "#1F2A44";
        disc(c, kx - 44, ky + 10, 30); disc(c, kx, ky - 8, 42); disc(c, kx + 46, ky + 10, 30);
        c.fillRect(kx - 44, ky + 10, 90, 30);
        c.fillStyle = WHITE;
        c.font = "700 16px " + MONO;
        c.textAlign = "center";
        c.fillText(phase > 0.35 && phase < 0.62 ? ".".repeat(1 + Math.floor(s * 4) % 3) : "LLM", kx, ky + 22);
        c.textAlign = "left";
        // the question goes up, the answer comes back down the same arc
        const arc = (k) => {
            const x0 = rx + 40, y0 = ry - 46, x1 = kx - 60, y1 = ky + 20;
            const mx = (x0 + x1) / 2, my = Math.min(y0, y1) - 60;
            const u = 1 - k;
            return [u * u * x0 + 2 * u * k * mx + k * k * x1, u * u * y0 + 2 * u * k * my + k * k * y1];
        };
        c.strokeStyle = "rgba(31, 42, 68, 0.35)";
        c.setLineDash([6, 6]);
        c.lineWidth = 2;
        c.beginPath();
        for (let i = 0; i <= 20; i++) { const [x, y] = arc(i / 20); i ? c.lineTo(x, y) : c.moveTo(x, y); }
        c.stroke();
        c.setLineDash([]);
        if (phase < 0.35) {
            const [x, y] = arc(phase / 0.35); c.fillStyle = PINK; disc(c, x, y, 7);
        } else if (phase > 0.62) {
            const [x, y] = arc(1 - (phase - 0.62) / 0.38); c.fillStyle = CYAN; disc(c, x, y, 7);
        }
        wifi(c, rx + 64, ry - 54);
    }

    function wifi(c, x, y, color = "#1F2A44") {
        c.strokeStyle = color;
        c.lineWidth = 3;
        for (let r = 8; r <= 24; r += 8) {
            c.beginPath(); c.arc(x, y, r, -Math.PI * 0.75, -Math.PI * 0.25); c.stroke();
        }
        c.fillStyle = color;
        disc(c, x, y, 3);
    }

    function noWifi(c, x, y) {
        wifi(c, x, y + 10, "rgba(31, 42, 68, 0.5)");
        c.strokeStyle = PINK;
        c.lineWidth = 3;
        c.beginPath(); c.moveTo(x - 20, y - 14); c.lineTo(x + 20, y + 14); c.stroke();
    }

    const DRAW = {gfx: drawGfx, lvgl: drawLvgl, mail: drawMail};
    const PATHS = {chip: drawChip, cloud: drawCloud};
    let running = false;

    function frame(t) {
        const slide = document.querySelector(".reveal .slides section.present");
        const robots = slide ? slide.querySelectorAll(".screen-robot") : [];
        const paths = slide ? slide.querySelectorAll(".path-anim") : [];
        if (!robots.length && !paths.length) { running = false; return; }
        robots.forEach((robot) => {
            if (robot.dataset.mode === "mail" && t > (robot.nextLetter || 0)) {
                robot.nextLetter = t + 1800 + Math.random() * 1600;
                sendLetter(robot);
            }
            DRAW[robot.dataset.mode](robot.querySelector("canvas").getContext("2d"), t, robot);
        });
        paths.forEach((canvas) => PATHS[canvas.dataset.mode](canvas.getContext("2d"), t));
        requestAnimationFrame(frame);
    }

    function onSlide() {
        if (running) return;
        running = true;
        requestAnimationFrame(frame);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const start = () => { onSlide(); Reveal.on("slidechanged", onSlide); };
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
