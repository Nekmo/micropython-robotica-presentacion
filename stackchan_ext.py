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
<div class="micropython-demo" data-demo="{name}">
  <pre class="demo-source" style="display: none">{code}</pre>
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
        markup = DEMO_HTML.format(
            name=html.escape(self.options.get('name', default_name)),
            code=html.escape(code),
            height=html.escape(self.options.get('height', '580px')),
        )
        return [nodes.raw('', markup, format='html')]


class StackChan3D(Directive):
    """three.js Stack-chan. Modes: ``anatomy`` (labelled parts), ``servos``
    (yaw/pitch sliders) and ``mirror`` (follows the emulator state)."""
    option_spec = {
        'mode': lambda arg: directives.choice(arg, ('anatomy', 'servos', 'mirror')),
        'height': directives.unchanged,
        'file': directives.unchanged,
    }

    def run(self):
        mode = self.options.get('mode', 'anatomy')
        height = html.escape(self.options.get('height', '560px'))
        source = ''
        if 'file' in self.options:   # program the mirror mode can run
            env = self.state.document.settings.env
            rel, path = env.relfn2path(self.options['file'])
            env.note_dependency(rel)
            with open(path, encoding='utf-8') as fh:
                source = f'<pre class="sc3d-source" style="display: none">{html.escape(fh.read())}</pre>'
        markup = (
            f'<div class="stackchan-3d" data-mode="{mode}" style="height: {height}">'
            f'{source}<canvas></canvas><div class="sc3d-labels"></div>'
            '<div class="sc3d-controls"></div></div>'
        )
        return [nodes.raw('', markup, format='html')]


FACE_HTML = '''
<div class="sc-face {size}" aria-hidden="true">
  <div class="sc-eye left"><div class="sc-lid"></div></div>
  <div class="sc-eye right"><div class="sc-lid"></div></div>
  <div class="sc-mouth"></div>
</div>
'''


class StackChanFace(Directive):
    option_spec = {
        'size': lambda arg: directives.choice(arg, ('hero', 'small')),
    }

    def run(self):
        size = self.options.get('size', 'hero')
        return [nodes.raw('', FACE_HTML.format(size=size), format='html')]


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
    """Expose a hash of the 3D model so browsers never reuse a stale export."""
    import hashlib
    src = app.srcdir
    with open(os.path.join(src, '_static', 'models', 'stackchan.glb'), 'rb') as fh:
        digest = hashlib.md5(fh.read()).hexdigest()[:10]
    with open(os.path.join(src, '_static', 'js', 'model-version.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.STACKCHAN_MODEL_VERSION = "%s";\n' % digest)


def setup(app):
    app.connect('builder-inited', build_simulator_bundle)
    app.connect('builder-inited', write_model_version)
    app.add_directive('micropython-demo', MicroPythonDemo)
    app.add_directive('stackchan-3d', StackChan3D)
    app.add_directive('stackchan-face', StackChanFace)
    app.add_directive('camera-view', CameraView)
    return {
        'version': '2.0',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
