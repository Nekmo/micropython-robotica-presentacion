/*
 * Background that follows the fragments of a slide.
 *
 * ``.. container:: fragment-images``: the n-th image is shown, large and
 * cut by the bottom-right corner, while the n-th fragment is the last one
 * revealed.
 *
 * ``.. container:: fragment-map``: an SVG map whose ``.map-pin`` elements
 * (``data-step``) light up with each fragment; a route is drawn from the
 * previous pin to the current one.
 */
(function () {
    "use strict";

    // The pictures live in the slide background, so they sit in the corner
    // of the screen whatever the height of the slide content
    function boxFor(slide) {
        if (!slide) return null;
        if (!slide.fragmentImages) {
            const box = slide.querySelector(".fragment-images, .fragment-map");
            if (!box) return null;
            Reveal.getSlideBackground(slide).appendChild(box);
            slide.fragmentImages = box;
        }
        return slide.fragmentImages;
    }

    function update(slide) {
        const box = boxFor(slide);
        if (!box) return;
        const shown = slide.querySelectorAll(".fragment.visible").length;
        box.querySelectorAll("img").forEach((img, i) => img.classList.toggle("active", i === shown - 1));
        if (box.classList.contains("fragment-map")) updateMap(box, shown - 1);
    }

    function pinPosition(pin) {
        const [x, y] = pin.getAttribute("transform").match(/-?[\d.]+/g).map(Number);
        return {x, y};
    }

    function updateMap(box, active) {
        const pins = [...box.querySelectorAll(".map-pin")];
        pins.forEach((pin) => {
            const step = +pin.dataset.step;
            pin.classList.toggle("active", step === active);
            pin.classList.toggle("visited", step < active);
        });
        const route = box.querySelector(".map-route");
        if (active < 1 || !pins[active]) {
            route.setAttribute("d", "");
            return;
        }
        // a curved hop from the previous event to the current one
        const a = pinPosition(pins[active - 1]), b = pinPosition(pins[active]);
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 - Math.hypot(b.x - a.x, b.y - a.y) * 0.3;
        route.setAttribute("d", `M${a.x} ${a.y} Q${mx} ${my} ${b.x} ${b.y}`);
        route.classList.remove("draw");
        void route.getBoundingClientRect();
        route.classList.add("draw");
    }

    function start() {
        update(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => update(event.currentSlide));
        Reveal.on("fragmentshown", () => update(Reveal.getCurrentSlide()));
        Reveal.on("fragmenthidden", () => update(Reveal.getCurrentSlide()));
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
