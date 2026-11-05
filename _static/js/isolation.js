/*
 * Register the cross-origin isolation service worker (see coi-sw.js) and
 * reload once so the simulator gets SharedArrayBuffer.
 */
(function () {
    "use strict";
    if (window.crossOriginIsolated || !window.isSecureContext || !("serviceWorker" in navigator)) return;
    const root = new URL("coi-sw.js", document.baseURI);
    navigator.serviceWorker.register(root).then((registration) => {
        const reloadOnce = () => {
            if (sessionStorage.getItem("coiReloaded")) return;
            sessionStorage.setItem("coiReloaded", "1");
            window.location.reload();
        };
        if (registration.active && !navigator.serviceWorker.controller) reloadOnce();
        navigator.serviceWorker.addEventListener("controllerchange", reloadOnce);
    }).catch((err) => console.warn("COI service worker:", err));
})();
