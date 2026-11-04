"""Export the Stack-chan Blender model to glTF for the presentation.

Run with Blender 5.0 (or the ``bpy`` 5.0 module)::

    blender --background --python models/export_stackchan.py -- \
        models/stackchan.blend _static/models/stackchan.glb

The script prepares the scene for the web without touching the source
file: it renames the parts, replaces the source materials (dark, with
unused texture sets) with the colours of the real StackChan,
adds the two servo pivots (``yaw`` and ``pitch``) so three.js can turn
the head, a ``screen_face`` plane for the live face texture, the 12 RGB
LEDs and the 3 touch zones set flush into the top of the head, then
exports only those objects with modifiers applied.
"""
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SOURCE = argv[0] if argv else "models/stackchan.blend"
TARGET = argv[1] if len(argv) > 1 else "_static/models/stackchan.glb"

bpy.ops.wm.open_mainfile(filepath=SOURCE, load_ui=False, use_scripts=False)
objects = bpy.data.objects

RENAME = {
    "Marco negro": "head_frame",
    "Pantalla": "screen",
    "camara 1": "camera_ring",
    "vamara 2": "camera_lens",
    "Base": "body",
    "base 2": "body_plate",
    "Circle.002": "eye_left",
    "Circle.001": "eye_right",
    "Plane.002": "mouth",
}
for old, new in RENAME.items():
    objects[old].name = new

def bounds(obj):
    """World-space (min, max) corners: origins in the model are not centred."""
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector([min(c[i] for c in corners) for i in range(3)])
    hi = Vector([max(c[i] for c in corners) for i in range(3)])
    return lo, hi


bpy.context.view_layer.update()
head_lo, head_hi = bounds(objects["head_frame"])
head_center = (head_lo + head_hi) / 2
head_bottom = head_lo.z
head_top = head_hi.z
front_y = head_hi.y
screen_lo, screen_hi = bounds(objects["screen"])
print("head", tuple(head_lo), tuple(head_hi), "screen", tuple(screen_lo), tuple(screen_hi))


def empty(name, location, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return obj


def reparent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def material(name, color, emission=None, roughness=0.5):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    return mat


def srgb(hex_color):
    """'#RRGGBB' -> linear RGB, as Blender expects for base colours."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_color[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def paint(name, mat):
    obj = objects[name]
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# Colours of the real M5Stack StackChan (product photos): light grey shell,
# black front bezel around the screen, orange camera ring and a two-tier
# dark grey base. The source materials are near-black everywhere.
shell = material("shell", srgb("#DADCDF"), roughness=0.5)
bezel = material("bezel", srgb("#1C1D20"), roughness=0.35)
glass = material("screen_glass", srgb("#050608"), roughness=0.12)
ring = material("camera_ring", srgb("#F08C2A"), roughness=0.4)
lens = material("camera_lens", srgb("#101114"), roughness=0.1)
base = material("base", srgb("#5B5E63"), roughness=0.55)
base_top = material("base_top", srgb("#43464B"), roughness=0.5)
paint("body", base)
paint("body_plate", base_top)
paint("screen", glass)
paint("camera_ring", ring)
paint("camera_lens", lens)

# Head: grey shell with the front face (+Y, towards the viewer) in black
head_mesh = objects["head_frame"].data
head_mesh.materials.clear()
head_mesh.materials.append(shell)
head_mesh.materials.append(bezel)
for poly in head_mesh.polygons:
    poly.material_index = 1 if poly.normal.y > 0.9 else 0

# Servo pivots: yaw turns around the vertical axis of the head, pitch tilts
# it around a horizontal axis at the bottom of the head (like the real neck)
yaw = empty("yaw", Vector((head_center.x, head_center.y, head_bottom)))
bpy.context.view_layer.update()
pitch = empty("pitch", Vector((head_center.x, head_center.y, head_bottom)))
bpy.context.view_layer.update()
reparent(pitch, yaw)
bpy.context.view_layer.update()
for name in ("head_frame", "screen", "camera_ring", "camera_lens",
             "eye_left", "eye_right", "mouth"):
    reparent(objects[name], pitch)

# Face plane over the screen: the presentation paints the live face on it
screen = objects["screen"]
bpy.ops.mesh.primitive_plane_add(size=1)
face = bpy.context.active_object
face.name = "screen_face"
face.rotation_euler = (1.5708, 0, 3.1416)   # stand up, facing +Y (front)
face.scale = ((screen_hi.x - screen_lo.x) * 0.94, (screen_hi.z - screen_lo.z) * 0.94, 1)
face.location = ((screen_lo.x + screen_hi.x) / 2, max(front_y, screen_hi.y) + 0.012,
                 (screen_lo.z + screen_hi.z) / 2)
face.data.materials.append(material("screen_face", (0, 0, 0), roughness=0.2))
bpy.context.view_layer.update()
reparent(face, pitch)

# 12 RGB LEDs on top of the head, 6 per side from front to back
# (physical order of the firmware: left 0-5, right 6-11)
# as flush diffuser windows (thin discs barely above the surface)
led_mat = material("led_off", srgb("#C4C7CB"), roughness=0.35)
for side, first in ((-1, 0), (1, 6)):
    for i in range(6):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.075, depth=0.004, vertices=24)
        led = bpy.context.active_object
        led.name = "led_%d" % (first + i)
        led.location = (head_center.x + side * 1.05,
                        front_y - 0.35 - i * 0.42, head_top + 0.0015)
        led.data.materials.append(led_mat)
        bpy.context.view_layer.update()
        reparent(led, pitch)

# Three capacitive touch zones (front, middle, back): on the real robot the
# touchpad sits under the shell, so they are only a flush, slightly darker
# print on the top face
touch_mat = material("touch", srgb("#CFD2D6"), roughness=0.5)
for i in range(3):
    bpy.ops.mesh.primitive_cube_add(size=1)
    zone = bpy.context.active_object
    zone.name = "touch_%d" % i
    zone.scale = (1.2, 0.62, 0.0004)   # inside the flat area, clear of the bevels
    zone.location = (head_center.x, front_y - 0.62 - i * 0.76, head_top + 0.0003)
    zone.data.materials.append(touch_mat)
    bpy.context.view_layer.update()
    reparent(zone, pitch)

export = ["yaw", "pitch", "body", "body_plate", "head_frame", "screen",
          "camera_ring", "camera_lens", "eye_left", "eye_right", "mouth",
          "screen_face"] + ["led_%d" % i for i in range(12)] + \
         ["touch_%d" % i for i in range(3)]
bpy.ops.object.select_all(action="DESELECT")
for name in export:
    objects[name].select_set(True)

bpy.ops.export_scene.gltf(
    filepath=TARGET,
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_yup=True,
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
    export_animations=False,
)
print("Exported", TARGET)
