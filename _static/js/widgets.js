/*
 * Interactive explainers (``.. widget:: <name>``):
 *
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

    const WIDGETS = {pcontrol};

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
