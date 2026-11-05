/*
 * Live MicroPython editors (Monaco) wired to window.robotLink.
 * Editors are created lazily the first time their slide is shown.
 */
(function () {
    "use strict";

    // Monaco 0.57 is vendored (see _static/vendor/monaco)
    const MONACO_BASE = new URL("../vendor/monaco", document.currentScript.src).href;
    const link = window.robotLink;
    let monacoPromise = null;
    let fontSize = parseInt(localStorage.getItem("editorFontSize") || "22", 10);
    const editors = new Map();

    function loadMonaco() {
        if (monacoPromise) return monacoPromise;
        monacoPromise = new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = `${MONACO_BASE}/vs/loader.js`;
            script.onerror = () => reject(new Error("No se pudo cargar Monaco"));
            script.onload = () => {
                window.require.config({paths: {vs: `${MONACO_BASE}/vs`}});
                window.require(["vs/editor/editor.main"], () => {
                    defineTheme(window.monaco);
                    resolve(window.monaco);
                }, reject);
            };
            document.head.appendChild(script);
        });
        return monacoPromise;
    }

    // Colours from the presentation palette (see _static/_tokens.scss)
    function defineTheme(monaco) {
        monaco.editor.defineTheme("stackchan", {
            base: "vs-dark",
            inherit: true,
            rules: [
                {token: "comment", foreground: "8C9BB8", fontStyle: "italic"},
                {token: "keyword", foreground: "FF4F9A"},
                {token: "string", foreground: "FFC44D"},
                {token: "number", foreground: "39D0D8"},
                {token: "identifier", foreground: "E9EEF2"},
            ],
            colors: {
                "editor.background": "#1F2A44",
                "editor.lineHighlightBackground": "#26345466",
                "editorLineNumber.foreground": "#5A6A8C",
                "editorCursor.foreground": "#FF4F9A",
                "editor.selectionBackground": "#39D0D855",
            },
        });
    }

    function terminalOf(slide) {
        return slide && slide.querySelector(".micropython-demo .terminal");
    }

    // Output goes to the terminal of the visible slide
    link.on("output", (text) => {
        const terminal = terminalOf(Reveal.getCurrentSlide());
        if (!terminal) return;
        terminal.textContent = (terminal.textContent + text).slice(-20000);
        terminal.scrollTop = terminal.scrollHeight;
    });

    link.on("status", updateToolbars);

    function updateToolbars() {
        const connected = link.connected;
        document.querySelectorAll(".micropython-demo").forEach((root) => {
            const indicator = root.querySelector(".status-indicator");
            indicator.classList.toggle("on", connected);
            indicator.title = connected ? "Conectado" : "Desconectado";
            root.querySelector(".connect").textContent = connected ? "Desconectar" : "Conectar";
            root.querySelector(".demo-target").value = link.target;
            ["send", "stop", "restart"].forEach((name) => {
                root.querySelector("." + name).disabled = !connected;
            });
        });
    }

    function applyFontSize() {
        localStorage.setItem("editorFontSize", fontSize);
        editors.forEach((editor) => editor.updateOptions({fontSize}));
        document.querySelectorAll(".micropython-demo .terminal").forEach((terminal) => {
            terminal.style.fontSize = Math.round(fontSize * 0.8) + "px";
        });
    }

    async function setup(root) {
        if (root.dataset.ready) return;
        root.dataset.ready = "1";
        const monaco = await loadMonaco();
        const source = root.querySelector(".demo-source").textContent;
        const editor = monaco.editor.create(root.querySelector(".editor"), {
            value: source,
            language: "python",
            theme: "stackchan",
            automaticLayout: true,
            fontSize,
            fontFamily: "'JetBrains Mono', monospace",
            minimap: {enabled: false},
            scrollBeyondLastLine: false,
            renderLineHighlight: "line",
            padding: {top: 12},
        });
        editors.set(root, editor);
        const run = () => link.run(editor.getValue());
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, run);

        const toolbar = root.querySelector(".demo-toolbar");
        toolbar.querySelector(".connect").addEventListener("click", () => link.toggle());
        toolbar.querySelector(".send").addEventListener("click", run);
        toolbar.querySelector(".stop").addEventListener("click", () => link.stop());
        toolbar.querySelector(".restart").addEventListener("click", () => link.restart());
        toolbar.querySelector(".demo-target").addEventListener("change", (e) => link.setTarget(e.target.value));
        toolbar.querySelector(".font-up").addEventListener("click", () => { fontSize += 2; applyFontSize(); });
        toolbar.querySelector(".font-down").addEventListener("click", () => { fontSize = Math.max(10, fontSize - 2); applyFontSize(); });
        toolbar.querySelector(".toggle-video").addEventListener("click", () => window.cameraBox && window.cameraBox.cycleSource());
        // Do not let Reveal steal the keys while typing
        root.addEventListener("keydown", (e) => e.stopPropagation());
        setupResizer(root, editor);
        updateToolbars();
        applyFontSize();
        applyStep(root);
    }

    // ---- Step-by-step line highlights (":steps: 2-4|6|8-10") ----
    function parseSteps(text) {
        return (text || "").split("|").map((part) => part.trim()).filter(Boolean).map((part) =>
            part.split(",").map((range) => {
                const [a, b] = range.split("-").map((n) => parseInt(n, 10));
                return [a, b || a];
            }));
    }

    function currentStep(root) {
        return root.querySelectorAll(".code-step.visible").length - 1;   // -1: no highlight
    }

    function applyStep(root) {
        const editor = editors.get(root);
        if (!editor) return;
        const monaco = window.monaco;
        const steps = parseSteps(root.dataset.steps);
        const step = currentStep(root);
        const lines = editor.getModel().getLineCount();
        const decorations = [];
        if (step >= 0 && steps[step]) {
            const ranges = steps[step];
            const inStep = (line) => ranges.some(([a, b]) => line >= a && line <= b);
            for (let line = 1; line <= lines; line++) {
                decorations.push({
                    range: new monaco.Range(line, 1, line, 1),
                    options: inStep(line)
                        ? {isWholeLine: true, className: "code-step-line", linesDecorationsClassName: "code-step-gutter"}
                        : {isWholeLine: true, inlineClassName: "code-step-dim"},
                });
            }
            editor.revealLinesInCenterIfOutsideViewport(ranges[0][0], ranges[ranges.length - 1][1]);
        }
        root.stepDecorations = editor.deltaDecorations(root.stepDecorations || [], decorations);
    }

    function onFragment(event) {
        if (!event.fragment.classList.contains("code-step")) return;
        const root = event.fragment.closest(".micropython-demo");
        if (root) applyStep(root);
    }

    function setupResizer(root, editor) {
        const body = root.querySelector(".demo-body");
        const editorEl = root.querySelector(".editor");
        const resizer = root.querySelector(".resizer");
        let dragging = false;
        resizer.addEventListener("pointerdown", (e) => {
            dragging = true;
            resizer.setPointerCapture(e.pointerId);
        });
        resizer.addEventListener("pointermove", (e) => {
            if (!dragging) return;
            const scale = Reveal.getScale();
            const top = body.getBoundingClientRect().top;
            const height = (e.clientY - top) / scale;
            const max = body.clientHeight - 60;
            editorEl.style.flexBasis = Math.max(80, Math.min(height, max)) + "px";
            editor.layout();
        });
        resizer.addEventListener("pointerup", () => { dragging = false; });
    }

    function onSlide(slide) {
        slide.querySelectorAll(".micropython-demo").forEach(setup);
    }

    function start() {
        onSlide(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => onSlide(event.currentSlide));
        Reveal.on("fragmentshown", onFragment);
        Reveal.on("fragmenthidden", onFragment);
    }
    // reveal.js loads after this file: wait for the DOM, then for Reveal
    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) start(); else Reveal.on("ready", start);
    });
})();
