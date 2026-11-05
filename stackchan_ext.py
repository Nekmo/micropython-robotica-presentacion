"""Sphinx directives for the Stack-chan robotics presentation.

* ``micropython-demo``: live code editor (Monaco) that runs MicroPython on
  the robot over Web Serial, or on the in-browser simulator.
* ``stackchan-3d``: interactive three.js model of Stack-chan.
* ``stackchan-face``: the animated Stack-chan face used as hero element.
* ``camera-view``: placeholder where the live camera is docked.
"""
import base64
import html
import json
import os

from docutils import nodes
from docutils.parsers.rst import Directive, directives


DEMO_HTML = '''
<div class="micropython-demo" data-demo="{name}" data-steps="{steps}">
  <pre class="demo-source" style="display: none">{code}</pre>
  {fragments}
  <div class="demo-toolbar">
    <span class="demo-name">{name}</span>
    <span class="status-indicator" title="Desconectado"></span>
    <select class="demo-target" aria-label="Destino">
      <option value="serial">Robot (USB)</option>
      <option value="simulator">Simulador</option>
    </select>
    <button class="connect">Conectar</button>
    <button class="send" disabled>Ejecutar</button>
    <button class="stop" disabled>Parar</button>
    <button class="restart" disabled>Reiniciar</button>
    <span class="spacer"></span>
    <button class="font-down" aria-label="Reducir fuente">A-</button>
    <button class="font-up" aria-label="Aumentar fuente">A+</button>
    <button class="toggle-video" aria-label="Alternar cámara y simulador">Cámara</button>
  </div>
  <div class="demo-body" style="height: {height}">
    <div class="editor"></div>
    <div class="resizer"></div>
    <pre class="terminal"></pre>
  </div>
</div>
'''

class MicroPythonDemo(Directive):
    """Live MicroPython editor bound to the robot.

    Code comes from the directive body or from ``:file:`` (relative to the
    source dir), so the same file can be flashed or run in the emulator.
    """
    has_content = True
    option_spec = {
        'file': directives.unchanged,
        'height': directives.unchanged,
        'name': directives.unchanged,
        'steps': directives.unchanged,
    }

    def run(self):
        env = self.state.document.settings.env
        if 'file' in self.options:
            rel, path = env.relfn2path(self.options['file'])
            env.note_dependency(rel)
            with open(path, encoding='utf-8') as fh:
                code = fh.read().rstrip('\n')
            default_name = os.path.basename(os.path.dirname(path))
        else:
            self.assert_has_content()
            code = '\n'.join(self.content)
            default_name = 'demo'
        # Line highlights walked with the presentation's arrows (fragments),
        # like revealjs-code-block's data-line-numbers: "2-4|6|8-10"
        steps = self.options.get('steps', '').strip()
        count = len([part for part in steps.split('|') if part.strip()])
        fragments = ''.join(
            f'<span class="fragment code-step" data-step="{i}"></span>' for i in range(count))
        markup = DEMO_HTML.format(
            steps=html.escape(steps),
            fragments=fragments,
            name=html.escape(self.options.get('name', default_name)),
            code=html.escape(code),
            height=html.escape(self.options.get('height', '580px')),
        )
        return [nodes.raw('', markup, format='html')]


class StackChan3D(Directive):
    """three.js Stack-chan. Modes: ``anatomy`` (labelled parts), ``mirror``
    (follows the emulator state), ``board`` (ESP32-S3 board), ``peek`` (jumps
    into a section slide) and ``servo`` (how a servo works: PWM and UART)."""
    option_spec = {
        'mode': lambda arg: directives.choice(arg, ('anatomy', 'mirror', 'board', 'peek', 'servo')),
        'height': directives.unchanged,
        'steps': directives.nonnegative_int,
    }

    def run(self):
        mode = self.options.get('mode', 'anatomy')
        height = html.escape(self.options.get('height', '560px'))
        # labels revealed one by one with the presentation's arrows
        steps = ''.join('<span class="fragment sc3d-step"></span>'
                        for _ in range(self.options.get('steps', 0)))
        markup = (
            f'<div class="stackchan-3d" data-mode="{mode}" style="height: {height}">'
            f'{steps}<canvas></canvas><div class="sc3d-labels"></div>'
            '<div class="sc3d-controls"></div></div>'
        )
        return [nodes.raw('', markup, format='html')]


FACE_PARTS = '''
  <div class="sc-cheek left"></div><div class="sc-cheek right"></div>
  <div class="sc-eye left"><div class="sc-lid"></div></div>
  <div class="sc-eye right"><div class="sc-lid"></div></div>
  <div class="sc-mouth"></div>
'''

FACE_HTML = '''
<div class="sc-face {size}" data-emotion="{emotion}" aria-hidden="true">''' + FACE_PARTS + '''</div>
'''

EMOTIONS = ('neutral', 'happy', 'doubt', 'surprised', 'wink', 'ticklish', 'curious', 'love', 'thinking')


class StackChanFace(Directive):
    """Animated Stack-chan face: follows the pointer, blinks, shows an emotion."""
    option_spec = {
        'size': lambda arg: directives.choice(arg, ('hero', 'small')),
        'emotion': lambda arg: directives.choice(arg, EMOTIONS),
    }

    def run(self):
        size = self.options.get('size', 'hero')
        emotion = self.options.get('emotion', 'neutral')
        return [nodes.raw('', FACE_HTML.format(size=size, emotion=emotion), format='html')]


INTRO_HTML = '''
<div class="sc-intro">
  <div class="intro-robot" role="button" tabindex="0" aria-label="Saludar a Stack-chan">
    <div class="intro-head">
      <div class="intro-screen">
        <pre class="intro-repl"></pre>
        <div class="sc-face screen" data-emotion="neutral">''' + FACE_PARTS + '''</div>
        <div class="intro-flash"></div>
      </div>
      <div class="intro-camera"></div>
    </div>
    <div class="intro-base"></div>
    <div class="intro-heart" aria-hidden="true">&#9829;</div>
  </div>
  <div class="intro-title">
    <p class="intro-kicker">PyConES 2026</p>
    <p class="intro-heading"><span>Usando</span> <span>Micropython</span>
      <span class="intro-truth"><span class="intro-marker" aria-hidden="true"></span>de verdad<span
        class="intro-truth-glow" aria-hidden="true">de verdad</span></span></p>
    <p class="intro-sub">Bienvenidos a la robótica</p>
  </div>
</div>
'''


class StackChanIntro(Directive):
    """Opening hook: Stack-chan boots MicroPython, wakes up and presents the talk."""

    def run(self):
        return [nodes.raw('', INTRO_HTML, format='html')]


class ScreenRobot(Directive):
    """A small Stack-chan whose screen is drawn by screens.js: ``gfx`` (M5GFX
    primitives), ``lvgl`` (LVGL objects) or ``mail`` (the author's face,
    with letters flying in)."""
    option_spec = {'mode': lambda arg: directives.choice(arg, ('gfx', 'lvgl', 'mail'))}

    def run(self):
        mode = self.options.get('mode', 'gfx')
        markup = (
            f'<div class="screen-robot" data-mode="{mode}" aria-hidden="true">'
            '<div class="intro-head"><div class="intro-screen"><canvas width="320" height="240"></canvas></div>'
            '<div class="intro-camera"></div></div><div class="intro-base"></div></div>'
        )
        return [nodes.raw('', markup, format='html')]


class PathAnimation(Directive):
    """Animation of an AI path (screens.js): ``chip`` (on device) or
    ``cloud`` (a large model over the network)."""
    option_spec = {'mode': lambda arg: directives.choice(arg, ('chip', 'cloud'))}

    def run(self):
        mode = self.options.get('mode', 'chip')
        return [nodes.raw('', f'<canvas class="path-anim" data-mode="{mode}" width="480" height="240" '
                              'aria-hidden="true"></canvas>', format='html')]


class Widget(Directive):
    """Interactive explainer built by widgets.js (``pcontrol``)."""
    required_arguments = 1

    def run(self):
        name = directives.choice(self.arguments[0], ('pcontrol',))
        return [nodes.raw('', f'<div class="widget widget-{name}" data-widget="{name}"></div>',
                          format='html')]


class CameraView(Directive):
    """Dock the live camera into the slide (``full`` or ``side``)."""
    option_spec = {
        'mode': lambda arg: directives.choice(arg, ('full', 'side')),
    }

    def run(self):
        mode = self.options.get('mode', 'full')
        return [nodes.raw('', f'<div class="camera-slot" data-mode="{mode}"></div>',
                          format='html')]


def build_simulator_bundle(app):
    """Pack the simulator's Python files and the robot firmware into one
    JSON file ({device path: base64}) loaded by the simulator worker."""
    src = app.srcdir
    roots = [
        (os.path.join(src, '_static', 'sim', 'py'), '/sim'),
        (os.path.join(src, 'robot', 'libs'), '/flash/libs'),
        (os.path.join(src, 'robot', 'res'), '/flash/res'),
    ]
    bundle = {}
    for root, target in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for name in sorted(filenames):
                if name.endswith('.pyc'):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root).replace(os.sep, '/')
                with open(path, 'rb') as fh:
                    bundle[target + '/' + rel] = base64.b64encode(fh.read()).decode()
    out = os.path.join(src, '_static', 'sim', 'bundle.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(bundle, fh, separators=(',', ':'), sort_keys=True)


def write_model_version(app):
    """Expose hashes of the 3D model and the simulator modules so browsers
    never reuse a stale export (ES modules and workers skip Sphinx's ?v=)."""
    import hashlib
    src = app.srcdir
    with open(os.path.join(src, '_static', 'models', 'stackchan.glb'), 'rb') as fh:
        digest = hashlib.md5(fh.read()).hexdigest()[:10]
    sim = hashlib.md5()
    sim_dir = os.path.join(src, '_static', 'sim')
    for name in sorted(os.listdir(sim_dir)):
        if name.endswith(('.mjs', '.js', '.json')):   # bundle.json: simulator + robot Python
            with open(os.path.join(sim_dir, name), 'rb') as fh:
                sim.update(fh.read())
    with open(os.path.join(src, '_static', 'js', 'model-version.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.STACKCHAN_MODEL_VERSION = "%s";\n' % digest)
        fh.write('window.STACKCHAN_SIM_VERSION = "%s";\n' % sim.hexdigest()[:10])


def setup(app):
    app.connect('builder-inited', build_simulator_bundle)
    app.connect('builder-inited', write_model_version)
    app.add_directive('micropython-demo', MicroPythonDemo)
    app.add_directive('stackchan-3d', StackChan3D)
    app.add_directive('stackchan-face', StackChanFace)
    app.add_directive('stackchan-intro', StackChanIntro)
    app.add_directive('camera-view', CameraView)
    app.add_directive('widget', Widget)
    app.add_directive('screen-robot', ScreenRobot)
    app.add_directive('path-anim', PathAnimation)
    return {
        'version': '2.0',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
