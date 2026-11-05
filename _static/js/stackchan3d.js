/*
 * three.js model of Stack-chan, loaded from models/stackchan.glb (exported
 * from the Blender model by models/export_stackchan.py, which adds the
 * yaw/pitch pivots, the face plane, the LEDs and the touch zones).
 *
 * Modes (``.. stackchan-3d:: :mode:``):
 *   anatomy  slowly orbits, with labels on each component
 *   mirror   follows the in-browser simulator (servos, LEDs and screen)
 *   board    an ESP32-S3 development board with labelled parts
 *   servo    a hobby servo seen through its case (labelled parts), then
 *            a PWM demo and a serial bus servo (UART) answering packets
 *   peek     section slides: Stack-chan jumps in from the bottom of the
 *            screen, wakes up, looks at the title and then follows the
 *            pointer; a click makes it happy
 *
 * Drag to orbit. Rendering only runs while the slide is visible.
 */
(function () {
    "use strict";

    // three.js 0.187 and its glTF loader are vendored (see _static/vendor/three)
    const BASE = document.currentScript.src;
    const THREE_URL = new URL("../vendor/three/three.module.js", BASE).href;
    const LOADER_URL = new URL("../vendor/three/addons/loaders/GLTFLoader.js", BASE).href;
    // Versioned by the build (js/model-version.js) so browsers never reuse a stale export
    const MODEL_URL = new URL("../models/stackchan.glb?v=" + (window.STACKCHAN_MODEL_VERSION || "dev"), BASE).href;
    const MODEL_HEIGHT = 3.0;      // scene units, the camera framing relies on it
    const LED_OFF = 0xC4C7CB;     // diffuser window when the LED is off
    let assetsPromise = null;
    const scenes = [];

    const loadAssets = () => (assetsPromise = assetsPromise || (async () => {
        const THREE = await import(THREE_URL);
        const {GLTFLoader} = await import(LOADER_URL);
        const gltf = await new GLTFLoader().loadAsync(MODEL_URL);
        return {THREE, template: gltf.scene};
    })());

    // Screen texture: the Stack-chan face, or the simulator screen
    class FaceTexture {
        constructor(THREE) {
            this.canvas = document.createElement("canvas");
            this.canvas.width = 320;
            this.canvas.height = 240;
            this.ctx = this.canvas.getContext("2d");
            this.texture = new THREE.CanvasTexture(this.canvas);
            this.texture.colorSpace = THREE.SRGBColorSpace;
            this.blinkUntil = 0;
            this.nextBlink = performance.now() + 2000;
            this.image = null;
            this.emotion = "neutral";   // neutral | sleep | happy
        }

        draw(now, look) {
            const c = this.ctx;
            if (this.image) {
                c.drawImage(this.image, 0, 0, 320, 240);
                this.texture.needsUpdate = true;
                return;
            }
            if (now > this.nextBlink) {
                this.blinkUntil = now + 130;
                this.nextBlink = now + 2500 + Math.random() * 3500;
            }
            c.fillStyle = "#000";
            c.fillRect(0, 0, 320, 240);
            c.fillStyle = c.strokeStyle = "#fff";
            const dx = look * 10;
            if (this.emotion !== "neutral") {
                // sleep: closed eyes and a small mouth; happy: ^ ^ and a smile
                const happy = this.emotion === "happy";
                c.lineWidth = 7;
                c.lineCap = "round";
                [100, 220].forEach((x) => {
                    c.beginPath();
                    if (happy) c.arc(x + dx, 116, 18, Math.PI * 1.15, Math.PI * 1.85);
                    else { c.moveTo(x - 16 + dx, 108); c.lineTo(x + 16 + dx, 108); }
                    c.stroke();
                });
                c.beginPath();
                if (happy) c.arc(160 + dx / 2, 140, 30, Math.PI * 0.2, Math.PI * 0.8);
                else { c.moveTo(150 + dx / 2, 162); c.lineTo(170 + dx / 2, 162); }
                c.stroke();
                this.texture.needsUpdate = true;
                return;
            }
            [100, 220].forEach((x) => {
                if (now < this.blinkUntil) c.fillRect(x - 16 + dx, 104, 32, 6);
                else {
                    c.beginPath();
                    c.arc(x + dx, 106, 14, 0, Math.PI * 2);
                    c.fill();
                }
            });
            c.fillRect(132 + dx / 2, 158, 56, 6);
            this.texture.needsUpdate = true;
        }
    }

    function buildRobot(THREE, template, face) {
        const model = template.clone(true);
        const node = (name) => model.getObjectByName(name);

        // Front of the model is -Z in glTF: turn it to face the camera (+Z),
        // then scale and centre it so it stands on the floor at the origin
        const robot = new THREE.Group();
        const wrapper = new THREE.Group();
        wrapper.rotation.y = Math.PI;
        wrapper.add(model);
        robot.add(wrapper);
        const box = new THREE.Box3().setFromObject(wrapper);
        const size = box.getSize(new THREE.Vector3());
        const scale = MODEL_HEIGHT / size.y;
        wrapper.scale.setScalar(scale);
        const centre = box.getCenter(new THREE.Vector3());
        wrapper.position.set(-centre.x * scale, -box.min.y * scale, -centre.z * scale);

        // The modelled face is replaced by the live face texture
        ["eye_left", "eye_right", "mouth"].forEach((name) => { node(name).visible = false; });
        const texture = face.texture;
        texture.flipY = false;   // glTF UV convention
        node("screen_face").material = new THREE.MeshBasicMaterial({map: texture});

        // Touch zones are a print on the top face: draw them over the shell
        // without z-fighting instead of as raised panels
        const touches = [], touchMeshes = [];
        for (let i = 0; i < 3; i++) {
            const zone = node("touch_" + i);
            zone.userData.touchZone = i;
            touchMeshes.push(zone);
            zone.material = zone.material.clone();
            Object.assign(zone.material, {polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1});
            touches.push(zone.material);
        }

        const leds = [];
        for (let i = 0; i < 12; i++) {
            const material = new THREE.MeshStandardMaterial({color: LED_OFF, roughness: 0.3, emissive: 0x000000});
            node("led_" + i).material = material;
            leds.push(material);
        }

        // Label anchors: points on the surface of each part, stored in the
        // part's local space so they follow the head while it moves. Parts
        // that live inside the robot are pointed at on the side facing the
        // camera at rest (+X), so occlusion tests work for them too.
        robot.updateMatrixWorld(true);
        const anchorAt = (name, pick) => {
            const part = node(name);
            const box = new THREE.Box3().setFromObject(part);
            const world = pick ? pick(box) : box.getCenter(new THREE.Vector3());
            return {node: part, local: part.worldToLocal(world.clone())};
        };
        const side = (heightFraction) => (box) => new THREE.Vector3(
            box.max.x, box.min.y + (box.max.y - box.min.y) * heightFraction, (box.min.z + box.max.z) / 2);
        const anchors = {
            screen: anchorAt("screen_face"),
            camera: anchorAt("camera_lens"),
            touch: anchorAt("touch_1"),
            leds: anchorAt("led_8"),   // row on the label's side
            mcu: anchorAt("head_frame", side(0.62)),
            pitch: anchorAt("head_frame", side(0.12)),
            // battery: front of the base (the plate's sides sit under the head)
            base: anchorAt("body", (box) => new THREE.Vector3(
                box.min.x + (box.max.x - box.min.x) * 0.3, box.min.y + (box.max.y - box.min.y) * 0.55, box.max.z)),
            yaw: anchorAt("body", side(0.4)),
        };
        return {robot, yaw: node("yaw"), pitch: node("pitch"), leds, touches, touchMeshes, anchors};
    }

    const LABELS = {
        screen: "Pantalla táctil 320×240",
        camera: "Cámara GC0308",
        touch: "Sensor táctil (3 zonas)",
        leds: "12 LEDs RGB",
        mcu: "ESP32-S3, IMU, micro y altavoz",
        pitch: "Servo de inclinación",
        yaw: "Servo de giro",
        base: "Batería",
    };

    // Column of each label: same side as its anchor, so leader lines do not
    // cross in front of the robot (side anchors are on the right, +X)
    const LABEL_SIDE = {
        leds: "left", touch: "left", screen: "left", base: "left",
        mcu: "right", pitch: "right", camera: "right", yaw: "right",
    };

    // ---------------------------------------------------------------- ESP32-S3 board
    //
    // Procedural ESP32-S3 development board (DevKitC-like): PCB, pin headers,
    // the WROOM module with its printed antenna and engraved shield, a
    // regulator, an LED, BOOT/RST buttons and two USB-C connectors.
    // Units: 1 = 100 px of the original 2D drawing (board 3.4 x 5.3).

    const BOARD_LABELS = {
        wifi: "🛜 WiFi y 📡 Bluetooth LE",
        cores: "💪 Doble núcleo a 240 MHz",
        memory: "🧠 512 KB SRAM y 8 MB PSRAM",
        vector: "🧮 Instrucciones vectoriales",
        gpio: "📍 45 GPIO programables",
        usb: "🔌 USB nativo",
    };
    const BOARD_SIDE = {wifi: "left", cores: "left", vector: "left", usb: "left", memory: "right", gpio: "right"};

    function shieldTexture(THREE) {
        const canvas = document.createElement("canvas");
        canvas.width = 512;
        canvas.height = 512;
        const c = canvas.getContext("2d");
        const g = c.createLinearGradient(0, 0, 512, 512);
        g.addColorStop(0, "#e6e9ed");
        g.addColorStop(1, "#a3a9b2");
        c.fillStyle = g;
        c.fillRect(0, 0, 512, 512);
        c.fillStyle = "#8d939c";
        c.beginPath();
        c.arc(40, 40, 12, 0, Math.PI * 2);
        c.fill();
        c.fillStyle = "#3a3f47";
        c.textAlign = "center";
        c.font = "700 72px 'JetBrains Mono', monospace";
        c.fillText("ESP32-S3", 256, 230);
        c.font = "600 50px 'JetBrains Mono', monospace";
        c.fillStyle = "#555b64";
        c.fillText("WROOM-1", 256, 300);
        c.fillText("N8R8", 256, 360);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        return texture;
    }

    function buildBoard(THREE) {
        const mat = (color, extra = {}) => new THREE.MeshStandardMaterial(Object.assign({color, roughness: 0.6}, extra));
        const box = (w, h, d, material, x, y, z) => {
            const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
            mesh.position.set(x, y, z);
            return mesh;
        };
        // 2D drawing coordinates -> board coordinates (centre 590,285; y up)
        const X = (x) => (x - 590) / 100;
        const Y = (y) => -(y - 285) / 100;

        const robot = new THREE.Group();   // named like the robot so the scene code is shared
        const board = new THREE.Group();
        board.position.y = MODEL_HEIGHT / 2;
        board.rotation.x = -0.25;          // tilted back, like lying on a desk
        robot.add(board);

        const pcb = mat(0x1f2533, {roughness: 0.75});
        const gold = mat(0xd8b46a, {metalness: 0.8, roughness: 0.3});
        const metal = mat(0xc9ced5, {metalness: 0.75, roughness: 0.32});
        const black = mat(0x15171b, {roughness: 0.5});
        const white = mat(0xe9eef2);

        board.add(box(3.4, 5.3, 0.08, pcb, 0, 0, 0));
        [[444, 44], [736, 44], [444, 526], [736, 526]].forEach(([x, y]) => {
            const hole = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.01, 24), white);
            hole.rotation.x = Math.PI / 2;
            hole.position.set(X(x), Y(y), 0.045);
            board.add(hole);
        });

        // pin headers: black plastic strip with 22 gold pins each
        [437, 743].forEach((x) => {
            board.add(box(0.22, 4.3, 0.12, black, X(x), Y(309), 0.1));
            for (let i = 0; i < 22; i++) {
                board.add(box(0.07, 0.07, 0.34, gold, X(x), Y(103 + i * 19), 0.24));
            }
        });

        // WROOM module: its own PCB, the meander antenna and the shield can
        board.add(box(2.24, 3.0, 0.05, mat(0x20293a), 0, Y(184), 0.065));
        const meander = [[498, 104], [498, 56], [520, 56], [520, 96], [542, 96], [542, 56], [564, 56], [564, 96],
            [586, 96], [586, 56], [608, 56], [608, 96], [630, 96], [630, 56], [652, 56], [652, 96], [674, 96],
            [674, 56], [684, 56]];
        meander.slice(1).forEach(([x, y], i) => {
            const [px, py] = meander[i];
            const len = Math.hypot(x - px, y - py) / 100 + 0.05;
            const seg = box(px === x ? 0.05 : len, px === x ? len : 0.05, 0.01, gold, X((x + px) / 2), Y((y + py) / 2), 0.095);
            board.add(seg);
        });
        const shieldMaterials = Array(6).fill(metal);
        shieldMaterials[4] = new THREE.MeshStandardMaterial({map: shieldTexture(THREE), metalness: 0.55, roughness: 0.35});
        const shield = new THREE.Mesh(new THREE.BoxGeometry(2.0, 2.04, 0.22), shieldMaterials);
        shield.position.set(0, Y(220), 0.2);
        board.add(shield);

        // regulator, LED, buttons and USB-C connectors
        board.add(box(0.46, 0.34, 0.1, black, X(549), Y(377), 0.09));
        board.add(box(0.2, 0.2, 0.06, white, X(636), Y(376), 0.07));
        const led = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 10), mat(0xff4f9a, {emissive: 0xff4f9a, emissiveIntensity: 0.8}));
        led.position.set(X(636), Y(376), 0.11);
        board.add(led);
        [512, 668].forEach((x) => {
            board.add(box(0.44, 0.34, 0.12, metal, X(x), Y(457), 0.1));
            const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.08, 20), black);
            cap.rotation.x = Math.PI / 2;
            cap.position.set(X(x), Y(457), 0.19);
            board.add(cap);
        });
        [537, 643].forEach((x) => board.add(box(0.58, 0.32, 0.22, metal, X(x), Y(540), 0.15)));

        // label anchors in board space
        const at = (x, y, z) => ({node: board, local: new THREE.Vector3(X(x), Y(y), z)});
        const anchors = {
            wifi: at(520, 80, 0.1),
            cores: at(530, 176, 0.32),
            memory: at(660, 230, 0.32),
            vector: at(540, 270, 0.32),
            gpio: at(743, 400, 0.42),
            usb: at(537, 552, 0.3),
        };
        return {robot, anchors};
    }


    // ---------------------------------------------------------------- servos
    //
    // A micro hobby servo (SG90-like, 1 unit = 10 mm) with a see-through
    // case, and a serial bus servo (Feetech SCS0009-like) for the UART demo.

    const SERVO_LABELS = {
        motor: "🌀 Motor",
        gears: "⚙️ Reductora",
        pot: "📏 Sensor de posición",
        pcb: "🧠 Circuito de control",
    };
    const SERVO_SIDE = {motor: "left", gears: "left", pot: "right", pcb: "right"};
    const SERVO_PARTS = Object.keys(SERVO_LABELS).length;

    function labelTexture(THREE, lines) {
        const canvas = document.createElement("canvas");
        canvas.width = 512;
        canvas.height = 256;
        const c = canvas.getContext("2d");
        c.fillStyle = "#16181d";
        c.fillRect(0, 0, 512, 256);
        c.fillStyle = "#e9eef2";
        c.textAlign = "center";
        c.font = "800 78px 'JetBrains Mono', monospace";
        c.fillText(lines[0], 256, 118);
        c.font = "600 50px 'JetBrains Mono', monospace";
        c.fillStyle = "#39d0d8";
        c.fillText(lines[1], 256, 196);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        return texture;
    }

    function buildServos(THREE) {
        const mat = (color, extra = {}) => new THREE.MeshStandardMaterial(Object.assign({color, roughness: 0.55}, extra));
        const add = (parent, geometry, material, x, y, z) => {
            const mesh = new THREE.Mesh(geometry, material);
            mesh.position.set(x, y, z);
            parent.add(mesh);
            return mesh;
        };
        const boxG = (w, h, d) => new THREE.BoxGeometry(w, h, d);
        const cylG = (r, h, n = 32) => new THREE.CylinderGeometry(r, r, h, n);
        const ghost = (mesh) => { mesh.raycast = () => {}; return mesh; };   // labels see through it

        const white = mat(0xf2f2ee, {roughness: 0.45});
        const metal = mat(0xc7ccd3, {metalness: 0.8, roughness: 0.3});
        const dark = mat(0x22252b);
        const wires = [mat(0x6b3b22), mat(0xd23b3b), mat(0xf29b30)];   // GND, V+, signal

        const robot = new THREE.Group();
        const gear = (parent, r, h, teeth, x, y, z, material = white) => {
            const g = new THREE.Group();
            g.position.set(x, y, z);
            add(g, cylG(r, h), material, 0, 0, 0);
            for (let i = 0; i < teeth; i++) {
                const a = i / teeth * Math.PI * 2;
                const t = add(g, boxG(0.07, h, 0.07), material, Math.cos(a) * r, 0, Math.sin(a) * r);
                t.rotation.y = -a;
            }
            parent.add(g);
            return g;
        };
        const cable = (from, to, bend, material, radius = 0.045) => {
            const curve = new THREE.CatmullRomCurve3([from, from.clone().add(bend), to.clone().sub(bend), to]);
            const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, radius, 10), material);
            mesh.raycast = () => {};
            return {mesh, curve};
        };

        // ---- hobby servo (PWM): blue see-through case and its insides
        const pwm = new THREE.Group();
        pwm.position.y = 0.45;
        robot.add(pwm);
        const shell = mat(0x2f6fd6, {transparent: true, opacity: 0.2, depthWrite: false, roughness: 0.3});
        const edge = new THREE.LineBasicMaterial({color: 0x2f6fd6, transparent: true, opacity: 0.55});
        const casePart = (w, h, d, x, y, z) => {
            const mesh = ghost(add(pwm, boxG(w, h, d), shell, x, y, z));
            const lines = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), edge);
            lines.raycast = () => {};
            mesh.add(lines);
        };
        casePart(2.3, 2.0, 1.2, 0, 1.0, 0);          // body
        casePart(3.2, 0.12, 1.2, 0, 1.55, 0);        // mounting ears
        casePart(1.3, 0.42, 1.2, 0.5, 2.21, 0);      // top cap over the gear train

        const motor = add(pwm, cylG(0.42, 1.25), metal, -0.45, 0.8, 0);
        add(pwm, cylG(0.1, 0.2, 16), metal, -0.45, 1.52, 0);
        const gears = new THREE.Group();
        pwm.add(gears);
        const g1 = gear(gears, 0.22, 0.12, 10, -0.45, 1.7, 0);
        const g2 = gear(gears, 0.42, 0.1, 18, 0.05, 1.9, 0);
        const g3 = gear(gears, 0.3, 0.12, 14, 0.5, 2.1, 0.08);
        const pot = add(pwm, cylG(0.3, 0.55), dark, 0.5, 1.0, 0);
        add(pwm, cylG(0.12, 0.3, 16), metal, 0.5, 1.4, 0);
        const pcb = add(pwm, boxG(2.0, 0.06, 1.0), mat(0x1f7a4a), 0, 0.12, 0);
        add(pwm, boxG(0.4, 0.08, 0.4), dark, 0.35, 0.19, 0);
        // output shaft and horn
        const pwmShaft = new THREE.Group();
        pwmShaft.position.set(0.5, 2.42, 0);
        pwm.add(pwmShaft);
        add(pwmShaft, cylG(0.16, 0.3), white, 0, 0.1, 0);
        const arm = add(pwmShaft, boxG(1.9, 0.08, 0.26), white, 0.5, 0.27, 0);
        add(pwmShaft, cylG(0.2, 0.08), white, 0, 0.27, 0);
        add(pwmShaft, cylG(0.13, 0.08), white, 1.45, 0.27, 0);
        // three wires out of the side, towards the microcontroller
        const pwmWires = wires.map((m, i) => {
            const z = (i - 1) * 0.1;
            const c = cable(new THREE.Vector3(-1.15, 0.35, z), new THREE.Vector3(-4.6, -0.6, z), new THREE.Vector3(-0.9, 0, 0), m);
            pwm.add(c.mesh);
            return c;
        });

        // ---- serial bus servo (UART): black, labelled, two connectors
        const bus = new THREE.Group();
        bus.position.y = 0.45;
        bus.scale.setScalar(0.001);
        robot.add(bus);
        const black = mat(0x1a1c21, {roughness: 0.4});
        const faces = Array(6).fill(black);
        faces[4] = new THREE.MeshStandardMaterial({map: labelTexture(THREE, ["SCS0009", "ID 1  ·  UART"]), roughness: 0.4});
        add(bus, boxG(2.3, 2.0, 1.2), faces, 0, 1.0, 0);
        add(bus, boxG(3.2, 0.12, 1.2), black, 0, 1.55, 0);
        add(bus, boxG(1.3, 0.42, 1.2), black, 0.5, 2.21, 0);
        const busShaft = new THREE.Group();
        busShaft.position.set(0.5, 2.42, 0);
        bus.add(busShaft);
        add(busShaft, cylG(0.62, 0.1, 48), metal, 0, 0.1, 0);
        add(busShaft, boxG(0.9, 0.04, 0.12), dark, 0.3, 0.17, 0);   // index mark: shows the angle
        [[-1.18, -0.3], [-1.18, 0.3]].forEach(([x, z]) => add(bus, boxG(0.12, 0.3, 0.42), white, x, 0.4, z));
        const busIn = cable(new THREE.Vector3(-1.24, 0.4, -0.3), new THREE.Vector3(-4.6, -0.6, -0.3),
            new THREE.Vector3(-0.9, 0, 0), mat(0x30343c), 0.07);
        const busNext = cable(new THREE.Vector3(-1.24, 0.4, 0.3), new THREE.Vector3(-2.6, -0.6, 2.2),
            new THREE.Vector3(-0.5, 0, 0.5), mat(0x30343c, {transparent: true, opacity: 0.45}), 0.07);
        bus.add(busIn.mesh, busNext.mesh);

        // data travelling on the wires
        const pulse = (color) => {
            const m = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 10),
                new THREE.MeshBasicMaterial({color}));
            m.raycast = () => {};
            m.visible = false;
            robot.add(m);
            return m;
        };
        const pulses = {
            pwm: Array.from({length: 4}, () => pulse(0xff4f9a)),
            out: Array.from({length: 8}, () => pulse(0xff4f9a)),
            back: Array.from({length: 8}, () => pulse(0x39d0d8)),
        };

        const at = (node, x, y, z) => ({node, local: new THREE.Vector3(x, y, z)});
        const anchors = {
            motor: at(motor, -0.42, 0, 0),
            gears: at(g2, 0, 0.05, 0.42),
            pot: at(pot, 0.3, 0, 0),
            pcb: at(pcb, 1.0, 0, 0),
        };
        return {robot, anchors, servo: {pwm, bus, pwmShaft, busShaft, gears: [g1, g2, g3], arm,
            pwmCable: pwmWires[2], busIn, pulses}};
    }

    const hex = (bytes) => bytes.map((b) => b.toString(16).toUpperCase().padStart(2, "0"));
    function scsPacket(id, instruction, params) {
        const body = [id, params.length + 2, instruction, ...params];
        return [0xFF, 0xFF, ...body, ~body.reduce((a, b) => a + b, 0) & 0xFF];
    }

    class RobotScene {
        constructor(THREE, template, root) {
            this.THREE = THREE;
            this.root = root;
            this.mode = root.dataset.mode;
            this.canvas = root.querySelector("canvas");
            this.renderer = new THREE.WebGLRenderer({canvas: this.canvas, antialias: true, alpha: true});
            this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            this.scene = new THREE.Scene();
            this.camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
            this.mini = root.classList.contains("mini");
            this.orbit = this.mini ? {theta: 0.45, phi: 1.1, radius: 7.2}
                : {theta: 0.6, phi: 1.25, radius: this.mode === "anatomy" ? 8.2 : 8.4};
            this.target = {yaw: 0, pitch: 0};
            this.current = {yaw: 0, pitch: 0};
            this.isBoard = this.mode === "board";
            this.isPeek = this.mode === "peek";
            this.isServo = this.mode === "servo";

            this.lookAtY = MODEL_HEIGHT / 2;
            if (this.isPeek) {
                // seen from the right, so at rest it is turned towards the title
                this.orbit = {theta: 0.42, phi: 1.36, radius: 10.5};
                this.lookAtY = MODEL_HEIGHT * 0.78;
            }
            if (this.isServo) {
                Object.assign(this, buildServos(THREE));
                this.labelDefs = SERVO_LABELS;
                this.labelSide = SERVO_SIDE;
                this.orbit = {theta: 0.5, phi: 1.2, radius: 10};
                this.lookAtY = 1.2;
            } else if (this.isBoard) {
                Object.assign(this, buildBoard(THREE));
                this.labelDefs = BOARD_LABELS;
                this.labelSide = BOARD_SIDE;
                this.orbit = {theta: 0, phi: 1.2, radius: 12.5};
            } else {
                this.face = new FaceTexture(THREE);
                Object.assign(this, buildRobot(THREE, template, this.face));
                this.labelDefs = LABELS;
                this.labelSide = LABEL_SIDE;
            }
            this.scene.add(this.robot);
            // Light grey shell: soft fill from the sky, a key light for the planes
            // and a faint cool rim so the shell stands out from light slides
            this.scene.add(new THREE.HemisphereLight(0xffffff, 0x6b7894, 1.5));
            const key = new THREE.DirectionalLight(0xffffff, 1.6);
            key.position.set(3, 6, 5);
            this.scene.add(key);
            const rim = new THREE.DirectionalLight(0x9ee8ec, 0.8);
            rim.position.set(-4, 3, -5);
            this.scene.add(rim);
            this.running = false;
            this.setupInput();
            this.setupMode();
            new ResizeObserver(() => this.resize()).observe(root);
            this.resize();
        }

        resize() {
            const {clientWidth: w, clientHeight: h} = this.canvas;
            if (!w || !h) return;
            this.renderer.setSize(w, h, false);
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
        }

        setupInput() {
            if (this.isPeek) return;   // it lives in the background: see setupMode
            let last = null;
            this.canvas.addEventListener("pointerdown", (e) => {
                e.stopPropagation();   // do not drag the camera box
                // Mirror of the simulator: press the head's touch zones on the model
                const zone = this.sim ? this.touchZoneAt(e) : -1;
                if (zone >= 0) {
                    this.pressed = zone;
                    this.sim.setHead(zone, true);
                    this.canvas.setPointerCapture(e.pointerId);
                    return;
                }
                last = {x: e.clientX, y: e.clientY};
                this.canvas.setPointerCapture(e.pointerId);
                this.userOrbit = true;
            });
            const release = () => {
                if (this.pressed === undefined) return;
                this.sim.setHead(this.pressed, false);
                this.pressed = undefined;
            };
            this.canvas.addEventListener("pointerup", release);
            this.canvas.addEventListener("pointercancel", release);
            this.canvas.addEventListener("pointermove", (e) => {
                if (this.sim && !last && this.pressed === undefined) {
                    this.canvas.style.cursor = this.touchZoneAt(e) >= 0 ? "pointer" : "";
                }
                if (!last) return;
                this.orbit.theta -= (e.clientX - last.x) * 0.008;
                this.orbit.phi = Math.max(0.4, Math.min(1.5, this.orbit.phi - (e.clientY - last.y) * 0.006));
                last = {x: e.clientX, y: e.clientY};
            });
            this.canvas.addEventListener("pointerup", () => { last = null; });
            this.canvas.addEventListener("wheel", (e) => {
                e.preventDefault();
                this.orbit.radius = Math.max(5, Math.min(16, this.orbit.radius + e.deltaY * 0.005));
            }, {passive: false});
        }

        setupMode() {
            const controls = this.root.querySelector(".sc3d-controls");
            if (this.isServo) {   // protocol panel of the PWM and UART demos
                this.panel = document.createElement("div");
                this.panel.className = "servo-panel";
                this.root.appendChild(this.panel);
                this.servoState = {phase: -1, angle: 90, from: 90, to: 90, moveAt: 0, swap: 0};
                this.panX = 0;
            }
            if (this.mode === "anatomy" || this.isBoard || this.isServo) {
                const labels = this.root.querySelector(".sc3d-labels");
                this.leaders = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                this.leaders.classList.add("sc3d-leaders");
                labels.appendChild(this.leaders);
                // Lines to parts hidden by the robot are drawn *behind* the
                // WebGL canvas: the model itself covers the hidden stretch
                this.leadersBack = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                this.leadersBack.classList.add("sc3d-leaders", "back");
                this.root.insertBefore(this.leadersBack, this.canvas);
                this.labels = Object.entries(this.labelDefs).map(([key, text]) => {
                    const label = document.createElement("span");
                    label.className = "sc3d-label";
                    label.textContent = text;
                    labels.appendChild(label);
                    return {key, label};
                });
            } else if (this.isPeek) {
                // landing shockwave
                for (let i = 0; i < 3; i++) {
                    const ring = document.createElement("i");
                    ring.className = "sc3d-ring";
                    ring.style.setProperty("--i", i);
                    this.root.appendChild(ring);
                }
                // the slides layer sits on top of the backgrounds: hit-test clicks
                document.addEventListener("pointerdown", (e) => {
                    if (!this.running || this.peekPhase() < 3.4) return;
                    const r = this.canvas.getBoundingClientRect();
                    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
                    if (x > 0.2 && x < 0.8 && y > 0.15 && y < 0.95) this.cheer();
                });
            } else if (this.mode === "mirror") {
                controls.innerHTML = `<span class="sc3d-status">Cargando el simulador…</span>`;
                window.loadSimulator().then((sim) => this.attachSimulator(sim));
            }
        }

        setLeds(colors) {
            colors.forEach((color, i) => {
                const c = new this.THREE.Color(color);
                const on = c.r + c.g + c.b > 0.05;
                this.leds[i].color.set(on ? c : LED_OFF);
                this.leds[i].emissive.set(on ? c : 0x000000);
            });
        }

        // Mirror the simulator: servos, LEDs and its screen
        attachSimulator(sim) {
            this.sim = sim;
            this.face.image = sim.canvas;
            const status = this.root.querySelector(".sc3d-status");
            const apply = (state) => {
                if (!state) {
                    this.target = {yaw: 0, pitch: 0};
                    this.setLeds(Array(12).fill(0));
                    status.textContent = "Ejecuta una demo en el simulador";
                    return;
                }
                const {servo, leds} = state;
                // Simulator domain: yaw 0..360 centred at 180, pitch 0..90 centred at 45
                this.target = {yaw: servo.x - 180, pitch: (servo.y - 45) * 0.6};
                this.setLeds(leds.map(([r, g, b]) => (r << 16) | (g << 8) | b));
                status.textContent = `X ${servo.x.toFixed(0)}°  Y ${servo.y.toFixed(0)}°`;
            };
            sim.on("state", apply);
            apply(sim.state);
            // Sensor controls of the camera box: shown on the model itself
            this.felt = {head: [0, 0, 0], accel: [0, 0, 1], prox: 0};
            this.tilt = 0;
            this.hand = document.createElement("span");
            this.hand.className = "sc3d-hand";
            this.hand.textContent = "\u270B";
            this.root.appendChild(this.hand);
            sim.on("input", (inputs) => { this.felt = inputs; });
            this.felt = sim.inputs();
        }

        // Index of the head touch zone under the pointer (-1: none)
        touchZoneAt(e) {
            const THREE = this.THREE;
            const rect = this.canvas.getBoundingClientRect();
            const ndc = new THREE.Vector2(
                (e.clientX - rect.left) / rect.width * 2 - 1,
                -((e.clientY - rect.top) / rect.height) * 2 + 1);
            this.raycaster = this.raycaster || new THREE.Raycaster();
            this.raycaster.setFromCamera(ndc, this.camera);
            // the zones are printed on the shell (coplanar): accept a zone hit
            // if nothing else on the robot is clearly in front of it
            const zone = this.raycaster.intersectObjects(this.touchMeshes, false)[0];
            if (!zone) return -1;
            const first = this.raycaster.intersectObject(this.robot, true)[0];
            return first.distance > zone.distance - 0.05 ? zone.object.userData.touchZone : -1;
        }

        // Touch zones glow, the body tilts and shakes with the IMU, and a
        // hand comes closer with the proximity sensor
        showInputs(now) {
            const {head, accel, prox} = this.felt;
            this.touches.forEach((material, i) => {
                material.emissive.set(head[i] ? 0xff4f9a : 0x000000);
                material.emissiveIntensity = head[i] ? 1.4 : 0;
            });
            this.tilt += (Math.max(-1, Math.min(1, accel[0])) * 0.35 - this.tilt) * 0.25;
            this.robot.rotation.z = -this.tilt;
            this.robot.position.x = Math.abs(accel[0]) > 1.2 ? Math.sin(now / 18) * 0.12 : 0;
            const near = prox / 2047;
            this.hand.style.opacity = near > 0.02 ? String(0.35 + 0.65 * near) : "0";
            this.hand.style.transform = `translate(-50%, -50%) scale(${0.5 + 0.9 * near})`;
        }

        peekPhase(now = performance.now()) {
            return (now - this.peekStart) / 1000;
        }

        cheer() {
            this.cheerAt = performance.now();
            try {
                this.audio = this.audio || new AudioContext();
                const osc = this.audio.createOscillator();
                const gain = this.audio.createGain();
                osc.type = "square";
                [988, 1319, 1976].forEach((f, i) => osc.frequency.setValueAtTime(f, this.audio.currentTime + i * 0.07));
                gain.gain.value = 0.04;
                osc.connect(gain).connect(this.audio.destination);
                osc.start();
                osc.stop(this.audio.currentTime + 0.24);
            } catch (err) { /* no audio */ }
        }

        // Entrance choreography, then the head follows the pointer
        animatePeek(now) {
            const t = this.peekPhase(now);
            const ease = (p) => {   // easeOutBack: overshoots, then settles
                const c1 = 2.2, c3 = c1 + 1;
                return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
            };
            const rise = Math.min(1, Math.max(0, (t - 0.25) / 0.75));
            let y = -MODEL_HEIGHT * 1.25 * (1 - ease(rise));
            let tilt = 0;
            if (t > 1 && t < 2.2) tilt = Math.sin((t - 1) * 18) * 0.07 * Math.exp(-(t - 1) * 3.5);
            if (!this.landed && t > 0.85) {
                this.landed = true;
                this.root.classList.remove("landed");
                void this.root.offsetWidth;
                this.root.classList.add("landed");
            }
            // a hop when it cheers
            const sinceCheer = (now - (this.cheerAt || -1e9)) / 1000;
            if (sinceCheer < 0.6) y += Math.sin(sinceCheer / 0.6 * Math.PI) * 0.45;
            this.robot.position.y = y;
            this.robot.rotation.z = tilt;

            this.face.emotion = sinceCheer < 1.6 ? "happy" : (t < 1.6 ? "sleep" : "neutral");
            if (t < 1.9) this.target = {yaw: 0, pitch: 8};                 // dozing
            else if (t < 2.9) this.target = {yaw: -38, pitch: -4};          // reads the title
            else if (t < 3.15) this.target = {yaw: 0, pitch: 12};           // nods to the audience
            else if (t < 3.4) this.target = {yaw: 0, pitch: -6};
            else {
                const r = this.canvas.getBoundingClientRect();
                const cx = r.left + r.width / 2, cy = r.top + r.height * 0.35;
                const px = this.pointer ? this.pointer.x : cx - 400, py = this.pointer ? this.pointer.y : cy;
                this.target = {
                    yaw: Math.max(-60, Math.min(45, (px - cx) / (window.innerWidth / 2) * 70)),
                    pitch: Math.max(-14, Math.min(22, (py - cy) / (window.innerHeight / 2) * 26)),
                };
            }

            // LEDs: off, then a chase as it wakes, then a slow breathing glow
            const colors = Array(12).fill(0);
            if (sinceCheer < 1.2) {
                for (let i = 0; i < 12; i++) {
                    const c = new this.THREE.Color().setHSL(((i / 12) + sinceCheer * 2) % 1, 1, 0.6);
                    colors[i] = c.getHex();
                }
            } else if (t > 1.6 && t < 3.6) {
                const head = Math.floor((t - 1.6) * 14) % 12;
                for (let k = 0; k < 4; k++) colors[(head - k + 12) % 12] = k === 0 ? 0xffffff : 0xff4f9a;
            } else if (t >= 3.6) {
                const glow = 0.5 + 0.5 * Math.sin(t * 2.4);
                for (let i = 0; i < 12; i++) {
                    const c = new this.THREE.Color(i % 2 ? 0xff4f9a : 0x39d0d8).multiplyScalar(0.35 + 0.65 * glow);
                    colors[i] = c.getHex();
                }
            }
            this.setLeds(colors);
        }

        // ---- servo slide: parts, then PWM, then a serial bus servo
        servoPhase() {
            return this.root.querySelectorAll(".sc3d-step.visible").length;
        }

        // ease the horn towards a new angle, like the servo's own controller
        servoAngle(now, target, ms = 600) {
            const st = this.servoState;
            if (target !== st.to) {
                st.from = st.angle;
                st.to = target;
                st.moveAt = now;
            }
            const k = Math.min(1, (now - st.moveAt) / ms);
            const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
            const before = st.angle;
            st.angle = st.from + (st.to - st.from) * e;
            return st.angle - before;   // the motor and gears turn while it moves
        }

        placePulses(list, curve, t0s, now, forward = true, group = this.servo.pwm) {
            list.forEach((m, i) => {
                const t = t0s[i] === undefined ? -1 : (now - t0s[i]) / 700;
                m.visible = t >= 0 && t <= 1;
                if (!m.visible) return;
                const p = curve.getPoint(forward ? 1 - t : t);   // curves run servo -> far end
                m.position.copy(group.localToWorld(p.clone()));
            });
        }

        animateServo(now) {
            const THREE = this.THREE;
            const sv = this.servo, st = this.servoState;
            const phase = this.servoPhase();
            const pwmDemo = phase === SERVO_PARTS + 1, busDemo = phase >= SERVO_PARTS + 2;
            if (phase !== st.phase) {
                st.phase = phase;
                st.cycle = now;
                this.panel.innerHTML = pwmDemo ? this.pwmPanel() : (busDemo ? this.busPanel() : "");
                st.manual = false;
                st.shownTarget = null;
                const slider = this.panel.querySelector(".sp-slider");
                if (slider) {
                    slider.addEventListener("input", () => { st.manual = true; });
                    // arrows move the slider, not the presentation
                    slider.addEventListener("keydown", (e) => e.stopPropagation());
                }
                this.panel.classList.toggle("shown", pwmDemo || busDemo);
            }
            // swap the hobby servo for the bus servo
            st.swap += ((busDemo ? 1 : 0) - st.swap) * 0.08;
            sv.pwm.scale.setScalar(Math.max(0.001, 1 - st.swap));
            sv.bus.scale.setScalar(Math.max(0.001, st.swap));
            sv.pwm.visible = st.swap < 0.95;
            sv.bus.visible = st.swap > 0.05;
            // demos: pan so the servo sits left of the protocol panel
            this.panX += ((pwmDemo ? 0.25 : (busDemo ? 0.2 : 0)) - this.panX) * 0.08;
            sv.pwm.position.x = -st.swap * 3;
            sv.bus.position.x = (1 - st.swap) * 3;

            let turn = 0;
            Object.values(sv.pulses).flat().forEach((m) => { m.visible = false; });
            if (pwmDemo) {
                // the slider picks the angle; until it is touched, a new angle
                // every 2.4 s. A pulse every 20 ms travels the wire (slowed down)
                const slider = this.panel.querySelector(".sp-slider");
                const t = now - st.cycle;
                if (!st.manual) slider.value = [90, 20, 160, 60][Math.floor(t / 2400) % 4];
                const target = +slider.value;
                turn = this.servoAngle(now, target);
                const starts = sv.pulses.pwm.map((_, i) => now - ((t + i * 330) % 1320));
                this.placePulses(sv.pulses.pwm, sv.pwmCable.curve, starts, now);
                if (target !== st.shownTarget) {
                    st.shownTarget = target;
                    const ms = 0.5 + target / 180 * 2, w = ms * 18, period = 150;
                    this.panel.querySelector(".sp-deg").textContent = target + "°";
                    this.panel.querySelector(".sp-call").textContent = target;
                    this.panel.querySelector(".sp-ms").textContent = ms.toFixed(2).replace(".", ",") + " ms";
                    this.panel.querySelector(".sp-ms").setAttribute("x", (14 + w).toFixed(1));
                    this.panel.querySelector(".sp-wave path").setAttribute("d",
                        `M0 54 H10 V14 H${10 + w} V54 H${10 + period} V14 H${10 + period + w} V54 H320`);
                }
            } else if (busDemo) {
                // write a goal position, then ask where it is and hear the answer
                const goals = [600, 330, 460];
                const t = now - st.cycle;
                const n = Math.floor(t / 5200), k = t % 5200;
                const goal = goals[n % goals.length];
                if (st.busGoal !== goal) {
                    st.busGoal = goal;
                    this.panel.innerHTML = this.busPanel(goal);
                }
                const stepAt = (i, start) => start + i * 80;
                const rows = this.panel.querySelectorAll(".sp-row");
                rows.forEach((r) => r.classList.remove("active"));
                if (k < 1300) {
                    rows[0].classList.add("active");
                    this.placePulses(sv.pulses.out, sv.busIn.curve, sv.pulses.out.map((_, i) => stepAt(i, now - k)), now, true, sv.bus);
                } else if (k > 2000 && k < 3000) {
                    rows[1].classList.add("active");
                    this.placePulses(sv.pulses.out, sv.busIn.curve, sv.pulses.out.map((_, i) => stepAt(i, now - k + 2000)), now, true, sv.bus);
                } else if (k >= 3000 && k < 4300) {
                    rows[2].classList.add("active");
                    this.placePulses(sv.pulses.back, sv.busIn.curve, sv.pulses.back.map((_, i) => stepAt(i, now - k + 3000)), now, false, sv.bus);
                }
                // bytes light up as they travel
                const lit = (row, start) => row.querySelectorAll("span").forEach((b, i) => {
                    b.classList.toggle("sent", k >= start + i * 60);
                });
                lit(rows[0], 0);
                lit(rows[1], 2000);
                lit(rows[2], 3000);
                this.panel.querySelectorAll(".sp-meaning").forEach((m, i) => {
                    m.classList.toggle("shown", k >= [900, 2700, 3900][i]);
                });
                const degrees = (st.busGoal - 460) * 5 / 16;
                turn = this.servoAngle(now, k >= 900 ? degrees : (st.lastDegrees ?? 0));
                if (k >= 900) st.lastDegrees = degrees;
            } else {
                // parts: the controller hunts gently around its set point
                turn = this.servoAngle(now, 90 + 25 * Math.sign(Math.sin(now / 1800)), 900);
            }
            const shaft = busDemo ? sv.busShaft : sv.pwmShaft;
            shaft.rotation.y = THREE.MathUtils.degToRad((busDemo ? 0 : 90) - st.angle);
            // motor fast, gears slower: the gear train is the reduction
            sv.gears[0].rotation.y += turn * 0.6;
            sv.gears[1].rotation.y -= turn * 0.25;
            sv.gears[2].rotation.y += turn * 0.02;
        }

        pwmPanel() {
            const k = (t) => `<span class="hljs-keyword">${t}</span>`, n = (t) => `<span class="hljs-number">${t}</span>`;
            const c = (t) => `<span class="hljs-comment">${t}</span>`;
            return `<div class="sp-title"><b>PWM</b> · 50 Hz · servo de modelismo · <b>solo ida</b></div>
                <label class="sp-control">Ángulo <input type="range" class="sp-slider" min="0" max="180" value="90">
                  <output class="sp-deg">90°</output></label>
                <pre class="sp-code"><code>${k("from")} machine ${k("import")} Pin, PWM
servo = PWM(Pin(${n(5)}), freq=${n(50)})    ${c("# a pulse every 20 ms")}

${k("def")} angle(degrees):             ${c("# 0.5 ms = 0°, 2.5 ms = 180°")}
    servo.duty_ns(${n("500_000")} + degrees * ${n("2_000_000")} // ${n(180)})

angle(<span class="hljs-number sp-call">90</span>)</code></pre>
                <svg class="sp-wave" viewBox="0 0 320 76">
                  <path d="M0 54 H320"/>
                  <text class="sp-ms" x="41" y="30">1,50 ms</text>
                  <text class="sp-period" x="85" y="72">20 ms · 50 Hz</text>
                </svg>`;
        }

        busPanel(goal = 600) {
            const write = scsPacket(1, 0x03, [42, goal >> 8, goal & 0xFF, 0x01, 0x2C, 0, 0]);
            const read = scsPacket(1, 0x02, [56, 2]);
            const reply = scsPacket(1, 0x00, [goal >> 8, goal & 0xFF]);
            // each byte coloured by its role, like the words that explain it:
            // g framing (header, length, checksum, unused), id servo,
            // inst instruction and register, pos position, time duration
            const bytes = (list, roles) => hex(list).map((b, i) =>
                `<span class="r-${roles.split(" ")[i]}">${b}</span>`).join("");
            const w = (role, text) => `<b class="r-${role}">${text}</b>`;
            return `<div class="sp-title"><b>UART</b> · 1 Mbit/s · servo de bus serie</div>
                <div class="sp-term">
                  <div class="sp-row"><b class="sp-tx">TX</b> ${bytes(write, "g g id g inst inst pos pos time time g g g")}</div>
                  <div class="sp-meaning"># ${w("id", "servo 1")}: ${w("inst", "ve a la posición")} ${w("pos", goal)} en ${w("time", "300 ms")}</div>
                  <div class="sp-row"><b class="sp-tx">TX</b> ${bytes(read, "g g id g inst inst inst g")}</div>
                  <div class="sp-meaning"># ${w("id", "servo 1")}: ${w("inst", "¿dónde estás?")}</div>
                  <div class="sp-row"><b class="sp-rx">RX</b> ${bytes(reply, "g g id g inst pos pos g")}</div>
                  <div class="sp-meaning"># ${w("id", "servo 1")}: ${w("inst", "sin errores")}, estoy en ${w("pos", goal)}</div>
                </div>`;
        }

        frame(now) {
            if (!this.running) return;
            const THREE = this.THREE;
            if (this.isPeek) this.animatePeek(now);
            if (this.felt) this.showInputs(now);
            if (this.mode === "anatomy" && !this.userOrbit) this.orbit.theta += 0.003;
            if (this.isServo) this.animateServo(now);
            if ((this.isBoard || this.isServo) && !this.userOrbit) {
                // a board is flat: swing in front of it instead of going round
                this.orbit.theta = this.isServo ? 0.2 + 0.45 * Math.sin(now / 3600) : 0.75 * Math.sin(now / 3200);
                this.orbit.phi = 1.2 + 0.12 * Math.sin(now / 2300);
            }
            if (this.mode === "anatomy") {
                this.target.yaw = Math.sin(now / 2400) * 25;
                this.target.pitch = Math.sin(now / 1700) * 8;
            }
            if (!this.isBoard && !this.isServo) {
                // critically damped approach, like the firmware's springs
                ["yaw", "pitch"].forEach((axis) => {
                    this.current[axis] += (this.target[axis] - this.current[axis]) * 0.12;
                });
                this.yaw.rotation.y = THREE.MathUtils.degToRad(this.current.yaw);
                this.pitch.rotation.x = THREE.MathUtils.degToRad(this.current.pitch);
                this.face.draw(now, -this.current.yaw / 45);
            }

            const {theta, phi, radius} = this.orbit;
            this.camera.position.set(
                radius * Math.sin(phi) * Math.sin(theta),
                MODEL_HEIGHT / 2 + radius * Math.cos(phi),
                radius * Math.sin(phi) * Math.cos(theta));
            this.camera.lookAt(0, this.lookAtY, 0);
            if (this.isServo) {
                // shift the picture, not the camera: the servo keeps its size
                const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
                this.camera.setViewOffset(w, h, this.panX * w, 0, w, h);
            }
            this.renderer.render(this.scene, this.camera);
            if (this.labels) this.placeLabels();
            requestAnimationFrame((t) => this.frame(t));
        }

        // Labels sit in two columns, joined to their part by a leader line
        // True when the robot itself hides the point from the camera
        isOccluded(point) {
            const THREE = this.THREE;
            this.raycaster = this.raycaster || new THREE.Raycaster();
            const origin = this.camera.position;
            const direction = point.clone().sub(origin);
            const distance = direction.length();
            this.raycaster.set(origin, direction.normalize());
            this.raycaster.far = distance;
            const hits = this.raycaster.intersectObject(this.robot, true);
            const visible = (obj) => { for (let o = obj; o; o = o.parent) if (!o.visible) return false; return true; };
            return hits.some((hit) => visible(hit.object) && hit.distance < distance - 0.04);
        }

        placeLabels() {
            const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
            this.robot.updateMatrixWorld();
            const columns = {left: [], right: []};
            // with ":steps:" labels appear one by one, driven by fragments
            const steps = this.root.querySelectorAll(".sc3d-step");
            let shown = steps.length ? this.root.querySelectorAll(".sc3d-step.visible").length : Infinity;
            if (this.isServo && shown > SERVO_PARTS) shown = 0;   // demos: the panel explains
            this.labels.forEach((item, index) => {
                item.shown = index < shown;
                item.label.classList.toggle("pending", !item.shown);
                if (!item.shown) return;
                const anchor = this.anchors[item.key];
                const point = anchor.node.localToWorld(anchor.local.clone());
                item.hidden = this.isOccluded(point);
                const p = point.project(this.camera);
                item.x = (p.x + 1) / 2 * w;
                item.y = (1 - p.y) / 2 * h;
                columns[this.labelSide[item.key]].push(item);
            });
            const lines = [], hiddenLines = [];
            Object.entries(columns).forEach(([side, items]) => {
                items.sort((a, b) => a.y - b.y);
                let last = -Infinity;
                items.forEach((item) => {
                    const y = Math.max(item.y, last + 40);
                    last = y;
                    // keep right-hand labels inside the canvas, whatever their length
                    const x = side === "left" ? w * 0.2
                        : Math.min(w * 0.8, w - item.label.offsetWidth - 8);
                    item.label.style.transform = `translate(${x}px, ${y}px)`;
                    item.label.classList.toggle("left", side === "left");
                    const line = `<line x1="${x}" y1="${y}" x2="${item.x}" y2="${item.y}"/>` +
                        `<circle cx="${item.x}" cy="${item.y}" r="5"/>`;
                    (item.hidden ? hiddenLines : lines).push(line);
                });
            });
            this.leaders.setAttribute("viewBox", `0 0 ${w} ${h}`);
            this.leaders.innerHTML = lines.join("");
            this.leadersBack.setAttribute("viewBox", `0 0 ${w} ${h}`);
            this.leadersBack.innerHTML = hiddenLines.join("");
        }

        start() {
            if (this.running) return;
            this.running = true;
            if (this.isPeek) {
                this.peekStart = performance.now();
                this.landed = false;
                this.cheerAt = -1e9;
                this.root.classList.remove("landed");
                if (!this.pointerTracking) {
                    this.pointerTracking = true;
                    document.addEventListener("pointermove", (e) => { this.pointer = {x: e.clientX, y: e.clientY}; });
                }
            }
            this.resize();
            requestAnimationFrame((t) => this.frame(t));
        }

        stop() {
            this.running = false;
        }
    }

    // Robot mirror for the camera box (simulator source), outside any slide
    window.createRobotMirror = async (container) => {
        const {THREE, template} = await loadAssets();
        const root = document.createElement("div");
        root.className = "stackchan-3d mini";
        root.dataset.mode = "mirror";
        root.innerHTML = '<canvas></canvas><div class="sc3d-labels"></div><div class="sc3d-controls"></div>';
        container.prepend(root);
        const scene = new RobotScene(THREE, template, root);
        return scene;
    };

    async function onSlide(slide) {
        scenes.forEach((scene) => scene.stop());
        const background = Reveal.getSlideBackground(slide);
        const roots = [...slide.querySelectorAll(".stackchan-3d"),
            ...(background ? background.querySelectorAll(".stackchan-3d") : [])];
        if (!roots.length) return;
        const {THREE, template} = await loadAssets();
        roots.forEach((root) => {
            if (!root.robotScene) {
                root.robotScene = new RobotScene(THREE, template, root);
                scenes.push(root.robotScene);
            }
            root.robotScene.start();
        });
    }

    function init() {
        // peek robots live in the slide background, behind the content
        Reveal.getSlides().forEach((slide) => {
            slide.querySelectorAll('.stackchan-3d[data-mode="peek"]').forEach((root) => {
                Reveal.getSlideBackground(slide).appendChild(root);
            });
        });
        onSlide(Reveal.getCurrentSlide());
        Reveal.on("slidechanged", (event) => onSlide(event.currentSlide));
    }
    // reveal.js loads after this file: wait for the DOM, then for Reveal
    document.addEventListener("DOMContentLoaded", () => {
        if (Reveal.isReady()) init(); else Reveal.on("ready", init);
    });
})();
