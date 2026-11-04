/*
 * Opening hook (``.. stackchan-intro::``).
 *
 * Every time the slide is shown Stack-chan powers on, its screen prints the
 * MicroPython banner, someone types two lines in the REPL, the robot wakes
 * up (eyes open, LEDs run) and the title of the talk lands next to it.
 * Clicking the robot makes it happy: hearts, blush and a beep.
 */
(function () {
    "use strict";

    const BANNER = [
        "MicroPython v1.25.0 on ESP32-S3",
        "M5Stack StackChan with UIFlow 2",
        'Type "help()" for more information.',
    ];
    const TYPED = [">>> import stackchan", ">>> chan = stackchan.wake()"];
    let run = 0;           // cancels a sequence when the slide is left
    let audio = null;

    const wait = (ms, id) => new Promise((resolve, reject) =>
        setTimeout(() => (id === run ? resolve() : reject(new Error("cancelled"))), ms));

    async function sequence(intro) {
        const id = ++run;
        const repl = intro.querySelector(".intro-repl");
        intro.className = "sc-intro";
        repl.textContent = "";
        try {
            await wait(350, id);
            intro.classList.add("power");                 // CRT power-on flash
            await wait(450, id);
            for (const line of BANNER) {
                repl.textContent += line + "\n";
                await wait(140, id);
            }
            for (const line of TYPED) {
                for (let i = 0; i < line.length; i++) {
                    repl.textContent += line[i];
                    await wait(i < 4 ? 30 : 42 + Math.random() * 40, id);
                }
                repl.textContent += "\n";
                await wait(320, id);
            }
            intro.classList.add("awake");                 // face replaces the REPL
            await wait(700, id);
            intro.classList.add("titled");                // title lands
        } catch (err) {
            /* slide left: the next visit starts again */
        }
    }

    function beep() {
        try {
            audio = audio || new AudioContext();
            const osc = audio.createOscillator();
            const gain = audio.createGain();
            osc.type = "square";
            osc.frequency.setValueAtTime(880, audio.currentTime);
            osc.frequency.setValueAtTime(1320, audio.currentTime + 0.08);
            gain.gain.value = 0.05;
            osc.connect(gain).connect(audio.destination);
            osc.start();
            osc.stop(audio.currentTime + 0.18);
        } catch (err) { /* no audio: still happy */ }
    }

    function happy(intro) {
        if (!intro.classList.contains("awake")) return;
        const face = intro.querySelector(".sc-face");
        face.dataset.emotion = "happy";
        intro.classList.remove("love");
        void intro.offsetWidth;
        intro.classList.add("love");
        beep();
        clearTimeout(intro.happyTimer);
        intro.happyTimer = setTimeout(() => { face.dataset.emotion = "neutral"; }, 1800);
    }

    function setup(intro) {
        if (intro.dataset.ready) return;
        intro.dataset.ready = "1";
        const robot = intro.querySelector(".intro-robot");
        robot.addEventListener("click", () => happy(intro));
        robot.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); happy(intro); }
        });
    }

    function onSlide(slide) {
        const intro = slide.querySelector(".sc-intro");
        if (!intro) { run++; return; }
        setup(intro);
        sequence(intro);
    }

    function start() {
        onSlide(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => onSlide(event.currentSlide));
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
