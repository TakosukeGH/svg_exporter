import math
import svgwrite
import bpy
import logging
import io
import mathutils
import operator

logger = logging.getLogger("svg_exporter")

class SvgExporter(bpy.types.Operator):
    bl_idname = "svg.exporter"
    bl_label = "Export SVG"

    def __init__(self):
        logger.info("start")

        self.objs = []
        self.uses = []
        self.duplicate_objs = []

        self.scale = 0.0

        logger.info("end")

    def invoke(self, context, event):
        logger.info("start")

        svg_scene_properties = context.scene.svg_scene_properties
        export_path = bpy.path.abspath(svg_scene_properties.export_path)
        width = svg_scene_properties.width
        height = svg_scene_properties.height
        self.scale = svg_scene_properties.scale

        # self.svg = svgwrite.Drawing(filename=export_path, size=(width,height), profile='tiny')
        self.svg = svgwrite.Drawing(filename=export_path, size=(width,height))
        self.svg.viewbox(minx=-width/2, miny=-height/2, width=width, height=height)

        if svg_scene_properties.use_background:
            background_color = svg_scene_properties.background_color
            rect = self.svg.rect(insert=(-width/2, -height/2), size=('100%', '100%'), rx=None, ry=None, fill=self.get_color(background_color), opacity=background_color[3])
            self.svg.add(rect)

        self.get_objects()
        self.add_defs()
        self.create_uses()
        self.sort_uses()
        self.add_uses()

        logger.debug("save: start")
        self.svg.save()
        logger.debug("save: end")

        logger.info("end")

        return {'FINISHED'}

    def get_objects(self):
        for obj in bpy.data.objects:
            if not obj.is_visible(bpy.context.scene):
                continue

            if obj.type != 'CURVE':
                continue

            curve = obj.data

            if curve.dimensions != '2D':
                logger.info("This curve is not 2D: " + str(obj.name))
                continue

            if len(curve.materials) <= 0:
                logger.info("This data has no material: " + str(obj.name))
                continue

            material = curve.materials[0]

            if material is None:
                logger.info("This material slot has no material: " + str(obj.name))
                return

            self.objs.append(obj)

    def add_defs(self):
        for obj in self.objs:
            group = self.svg.g(id=obj.name)
            self.add_curve_data(obj, group)
            self.svg.defs.add(group)

    def add_curve_data(self, obj, group):
        logger.debug("add data: " + str(obj.name))
        color = self.get_diffuse_color(obj)
        alpha = self.get_alpha(obj)
        curve = obj.data
        matrix_world = obj.matrix_world
        scale = bpy.context.scene.svg_scene_properties.scale

        for spline in curve.splines:
            if spline.type != 'BEZIER':
                logger.info("Spline type is not BEZIER")
                continue

            # ループしているかの判定。使うかどうか検討中。
            is_loop = spline.use_cyclic_u

            svg_path = SVGPath(spline, matrix_world, scale)

            # self.svg.add(self.svg.path(d=svg_path.d, fill=color, opacity=alpha, stroke=color))
            group.add(self.svg.path(d=svg_path.d, fill=color, opacity=alpha, stroke=color))

    def get_diffuse_color(self, obj):
        material = obj.data.materials[0]
        diffuse_color = material.diffuse_color
        return self.get_color(diffuse_color)

    def get_color(self, color):
        gamma = 2.2
        r = 255 * pow(color[0], 1/gamma)
        g = 255 * pow(color[1], 1/gamma)
        b = 255 * pow(color[2], 1/gamma)
        return svgwrite.rgb(r,g,b)

    def get_alpha(self, obj):
        material = obj.data.materials[0]
        return material.alpha

    def create_uses(self):
        for obj in self.objs:
            use = SVGUse(obj.name, mathutils.Vector(obj.location) * self.scale)
            use.y = -use.y
            uses = []
            uses.append(use)
            self.duplicate_use(obj, uses)
            self.uses.extend(uses)
            # self.svg.add(self.svg.use(svg_id, insert=(i, i), size=(100,100)))

    def duplicate_use(self, obj, uses):
        for index in range(2):
            if len(obj.modifiers) <= index:
                continue

            mod = obj.modifiers[index]
            if mod.type != 'ARRAY':
                continue

            if mod.show_viewport is False:
                continue

            if mod.count <= 1:
                continue

            # if not mod.use_constant_offset and not mod.use_relative_offset and not mod.use_object_offset:
            if not mod.use_constant_offset:
                continue

            # self.duplicate_objs.append(obj)
            self.duplicate_by_array_modifire(obj.name, mod, uses)

    def duplicate_by_array_modifire(self, id, mod, uses):
        for use in uses[:]:
            for i in range(1, mod.count):
                duplicate_use = SVGUse(id, use.get_location() + mathutils.Vector(mod.constant_offset_displace) * i * self.scale)
                logger.debug(duplicate_use.get_location())
                uses.append(duplicate_use)

    def sort_uses(self):
        self.uses.sort(key=lambda use: use.z)

    def add_uses(self):
        for use in self.uses:
            logger.debug("check")
            self.svg.add(self.svg.use(self.svg.symbol(id=use.id), insert=(use.x, use.y), size=(100,100)))

    def test(self):
        svg_id = self.svg.symbol(id='himeporu')
        group = self.svg.g(id='himeporu')
        circle = self.svg.circle(center=(0, 0), r=100, fill=svgwrite.rgb(100,100,100))
        group.add(circle)
        self.svg.defs.add(group)

        for i in range(1):
            self.svg.add(self.svg.use(svg_id, insert=(float(i), float(i)), size=(100,100)))

class SVGPath():
    svg_matrix = mathutils.Matrix((
        [1.0, 0.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]))

    def __init__(self, spline, matrix_world, scale):
        self.spline = spline
        self.matrix_world = matrix_world
        self.scale = scale
        self.ds = []

        self.append_move_to()
        self.append_bezier_curve()
        self.append_end()

        self.d = ' '.join(self.ds)

    def append_move_to(self):
        m = self.get_global_pos(self.spline.bezier_points[0].co)
        self.ds.append("M{0},{1}".format(m.x, m.y))

    def append_bezier_curve(self):
        for i in range(len(self.spline.bezier_points) - 1):
            p1 = self.spline.bezier_points[i]
            p2 = self.spline.bezier_points[i + 1]

            c1 = self.get_global_pos(p1.handle_right)
            c2 = self.get_global_pos(p2.handle_left)
            c = self.get_global_pos(p2.co)

            self.ds.append("C {0},{1} {2},{3} {4},{5}".format(c1.x, c1.y, c2.x, c2.y, c.x, c.y))

    def append_end(self):
        start_point = self.spline.bezier_points[0]
        end_point = self.spline.bezier_points[-1]

        c1 = self.get_global_pos(end_point.handle_right)
        c2 = self.get_global_pos(start_point.handle_left)
        c = self.get_global_pos(start_point.co)

        self.ds.append("C {0},{1} {2},{3} {4},{5}".format(c1.x, c1.y, c2.x, c2.y, c.x, c.y))

    # def get_global_pos(self, vec):
    #     v = vec.copy()
    #     v.resize_4d()

    #     w = self.svg_matrix * self.matrix_world * v
    #     w = w * self.scale
    #     w.resize_3d()
    #     return w

    def get_global_pos(self, vec):
        v = vec.copy()
        v.resize_4d()

        w = self.svg_matrix * v
        w = w * self.scale
        w.resize_3d()
        return w

class SVGUse():
    def __init__(self, id, location):
        self.id = id
        self.x = location[0]
        self.y = location[1]
        self.z = location[2]

    def get_location(self):
        return mathutils.Vector((self.x, self.y, self.z))








