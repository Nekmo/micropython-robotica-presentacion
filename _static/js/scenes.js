/*
 * Slide scenes and the living Stack-chan face.
 *
 * Sections declare ``:data-scene: face|sheet|blueprint|neon|video|boot``,
 * optionally ``:data-sheet: <text>`` (drawing title block) and
 * ``:data-big: <text>`` (giant number behind face slides).
 */
(function () {
    "use strict";

    // Animations are part of the talk: they run even when the desktop asks
    // for reduced motion (KDE can switch that on system-wide).

    function el(tag, className, parent, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text) node.textContent = text;
        if (parent) parent.appendChild(node);
        return node;
    }

    // Drawing title block for sheet/blueprint slides
    function addTitleBlock(background, slide, index) {
        const block = el("div", "title-block", background);
        el("span", "tb-label", block, "Stack-chan");
        el("span", "tb-sheet", block, slide.dataset.sheet || "Micropython");
        el("span", "tb-number", block, String(index).padStart(2, "0"));
        // registration marks on the four corners of the frame
        ["tl", "tr", "bl", "br"].forEach((corner) => el("i", "reg-mark " + corner, background));
    }

    // The 12 LEDs of the robot running around a neon slide
    function addLedStrips(background) {
        ["top", "bottom"].forEach((side) => {
            const strip = el("div", "led-strip " + side, background);
            for (let i = 0; i < 6; i++) el("i", "led", strip).style.setProperty("--i", i);
        });
    }

    function decorate() {
        const slides = Reveal.getSlides();
        slides.forEach((slide, index) => {
            const scene = slide.dataset.scene;
            if (!scene) return;
            const background = Reveal.getSlideBackground(slide);
            if (!background || background.dataset.decorated) return;
            background.dataset.decorated = "1";
            background.classList.add("scene", "scene-" + scene);
            slide.classList.add("on-" + scene);
            if (scene === "sheet" || scene === "blueprint") addTitleBlock(background, slide, index + 1);
            if (scene === "neon") addLedStrips(background);
            // Giant outlined challenge number behind the face ("01".."05")
            if (slide.dataset.big) el("div", "big-number", background, slide.dataset.big);
        });
    }

    // ---- Stack-chan face: looks at the pointer, blinks, talks on change ----
    const pointer = {x: window.innerWidth / 2, y: window.innerHeight / 2};
    document.addEventListener("pointermove", (e) => {
        pointer.x = e.clientX;
        pointer.y = e.clientY;
    });

    function animateFaces() {
        document.querySelectorAll(".reveal .present .sc-face").forEach((face) => {
            const rect = face.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = Math.max(-1, Math.min(1, (pointer.x - cx) / (window.innerWidth / 2)));
            const dy = Math.max(-1, Math.min(1, (pointer.y - cy) / (window.innerHeight / 2)));
            face.style.setProperty("--look-x", dx.toFixed(3));
            face.style.setProperty("--look-y", dy.toFixed(3));
        });
        requestAnimationFrame(animateFaces);
    }

    function scheduleBlink() {
        const wait = 2200 + Math.random() * 4200;
        setTimeout(() => {
            document.querySelectorAll(".sc-face").forEach((face) => {
                face.classList.add("blink");
                setTimeout(() => face.classList.remove("blink"), 140);
            });
            scheduleBlink();
        }, wait);
    }

    function talk(slide) {
        slide.querySelectorAll(".sc-face").forEach((face) => {
            face.classList.remove("talk");
            void face.offsetWidth; // restart the CSS animation
            face.classList.add("talk");
        });
    }

    function start() {
        decorate();
        animateFaces();
        scheduleBlink();
        talk(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => {
            talk(event.currentSlide);
            // Autoplay inline videos when their slide is shown
            event.currentSlide.querySelectorAll("video").forEach((video) => {
                if (video.paused) video.play().catch(() => {});
            });
        });
    }
    // reveal.js loads after this file: wait for the DOM, then for Reveal
    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
