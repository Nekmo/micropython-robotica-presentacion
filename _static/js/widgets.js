/*
 * Interactive explainers (``.. widget:: <name>``):
 *
 *   pwm       move the angle: pulse width, duty cycle and the servo horn
 *   pcontrol  move the gain: how a proportional controller tracks a face,
 *             slow with low gain, oscillating with high gain
 */
(function () {
    "use strict";

    const INK = "#1F2A44", NEON = "#FF4F9A", LED = "#39D0D8", SHELL = "#E9EEF2";

    function setupCanvas(canvas) {
        const ratio = Math.min(window.devicePixelRatio, 2);
        const w = canvas.clientWidth, h = canvas.clientHeight;
        canvas.width = w * ratio;
        canvas.height = h * ratio;
        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return {ctx, w, h};
    }

    // ---- PWM: 50 Hz, 0.5 ms (0°) .. 2.5 ms (180°) ----
    function pwm(root) {
        root.innerHTML = `
          <label class="w-row">Ángulo <input type="range" min="0" max="180" value="90"> <output></output></label>
          <canvas class="w-pulse"></canvas>
          <canvas class="w-horn"></canvas>
          <pre class="w-code"></pre>`;
        const input = root.querySelector("input");
        const output = root.querySelector("output");
        const code = root.querySelector(".w-code");
        let shown = 90;

        function draw() {
            if (!root.clientWidth) return;   // slide not laid out yet
            const angle = +input.value;
            shown += (angle - shown) * 0.2;
            const pulseUs = 500 + angle * 2000 / 180;
            output.textContent = `${angle}°`;
            code.textContent = `angle(${angle})\n# pulso ${(pulseUs / 1000).toFixed(2)} ms cada 20 ms` +
                `\n# duty_ns(${Math.round(pulseUs * 1000).toLocaleString("es")})`;

            // pulse train: two 20 ms periods
            const p = setupCanvas(root.querySelector(".w-pulse"));
            const {ctx, w, h} = p;
            ctx.clearRect(0, 0, w, h);
            const base = h - 18, top = 18, period = (w - 20) / 2;
            ctx.strokeStyle = INK;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(10, base);
            for (let i = 0; i < 2; i++) {
                const x0 = 10 + i * period, x1 = x0 + period * pulseUs / 20000;
                ctx.lineTo(x0, base); ctx.lineTo(x0, top); ctx.lineTo(x1, top); ctx.lineTo(x1, base);
            }
            ctx.lineTo(w - 10, base);
            ctx.stroke();
            ctx.fillStyle = NEON;
            ctx.font = "600 14px 'JetBrains Mono', monospace";
            ctx.fillText(`${(pulseUs / 1000).toFixed(2)} ms`, 14, top - 4 + 16);
            ctx.fillStyle = INK;
            ctx.fillText("20 ms", 10 + period - 46, base + 14);

            // servo horn
            const q = setupCanvas(root.querySelector(".w-horn"));
            const hc = q.ctx, cx = q.w / 2, cy = q.h - 20, r = Math.max(10, Math.min(q.w / 2, q.h) - 30);
            hc.clearRect(0, 0, q.w, q.h);
            hc.strokeStyle = "rgba(31, 42, 68, 0.3)";
            hc.lineWidth = 2;
            hc.beginPath();
            hc.arc(cx, cy, r, Math.PI, 0);
            hc.stroke();
            hc.fillStyle = INK;
            hc.fillRect(cx - 40, cy - 14, 80, 30);
            const rad = Math.PI - shown * Math.PI / 180;
            hc.strokeStyle = NEON;
            hc.lineWidth = 12;
            hc.lineCap = "round";
            hc.beginPath();
            hc.moveTo(cx, cy);
            hc.lineTo(cx + Math.cos(rad) * r * 0.85, cy - Math.sin(rad) * r * 0.85);
            hc.stroke();
            if (Math.abs(shown - angle) > 0.2) requestAnimationFrame(draw);
        }
        input.addEventListener("input", draw);
        root.addEventListener("keydown", (e) => e.stopPropagation());
        return draw;
    }

    // ---- Proportional control: yaw follows a face that jumps ----
    function pcontrol(root) {
        root.innerHTML = `
          <label class="w-row">Ganancia <input type="range" min="0.01" max="0.6" step="0.01" value="0.05"> <output></output></label>
          <canvas class="w-plot"></canvas>
          <p class="w-verdict"></p>`;
        const input = root.querySelector("input");
        const output = root.querySelector("output");
        const verdict = root.querySelector(".w-verdict");

        function simulate(gain) {
            // the camera sees the face one frame late (latency) -> overshoot
            const yaw = [0], target = 60;
            let previousError = target;
            for (let k = 1; k < 80; k++) {
                const error = target - yaw[k - 1];
                yaw.push(yaw[k - 1] + gain * (k > 1 ? previousError : error) * 2);
                previousError = error;
            }
            return {yaw, target};
        }

        function draw() {
            if (!root.clientWidth) return;   // slide not laid out yet
            const gain = +input.value;
            output.textContent = gain.toFixed(2);
            const {yaw, target} = simulate(gain);
            const {ctx, w, h} = setupCanvas(root.querySelector(".w-plot"));
            ctx.clearRect(0, 0, w, h);
            const sx = (k) => 10 + k * (w - 20) / (yaw.length - 1);
            const sy = (v) => h - 20 - v * (h - 40) / 110;
            ctx.strokeStyle = LED;
            ctx.setLineDash([6, 6]);
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(10, sy(target));
            ctx.lineTo(w - 10, sy(target));
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.strokeStyle = NEON;
            ctx.lineWidth = 3;
            ctx.beginPath();
            yaw.forEach((v, k) => (k ? ctx.lineTo(sx(k), sy(Math.max(-10, Math.min(110, v)))) : ctx.moveTo(sx(k), sy(v))));
            ctx.stroke();
            ctx.fillStyle = INK;
            ctx.font = "600 13px 'JetBrains Mono', monospace";
            ctx.fillText("cara", w - 48, sy(target) - 6);
            const peak = Math.max(...yaw), end = yaw[yaw.length - 1];
            const settled = yaw.findIndex((v, k) => yaw.slice(k).every((u) => Math.abs(u - target) < 3));
            if (Math.abs(end - target) > 10) verdict.textContent = "Oscila sin control: ganancia demasiado alta.";
            else if (peak > target + 6) verdict.textContent = `Se pasa ${Math.round(peak - target)}° y oscila antes de llegar.`;
            else if (settled < 0 || settled > 50) verdict.textContent = "Llega tarde: ganancia demasiado baja.";
            else verdict.textContent = `Centrado en ${settled} fotogramas.`;
        }
        input.addEventListener("input", draw);
        root.addEventListener("keydown", (e) => e.stopPropagation());
        return draw;
    }

    const WIDGETS = {pwm, pcontrol};

    function onSlide(slide) {
        slide.querySelectorAll(".widget").forEach((root) => {
            if (!root.redraw) root.redraw = WIDGETS[root.dataset.widget](root);
            requestAnimationFrame(root.redraw);
        });
    }

    function start() {
        onSlide(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => onSlide(event.currentSlide));
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
