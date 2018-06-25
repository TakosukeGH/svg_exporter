import bpy
import logging
import itertools
import math
import mathutils
import os
import bgl
from . exporter import SvgExporter
from bpy.props import PointerProperty, StringProperty, CollectionProperty, IntProperty, BoolProperty, IntVectorProperty, FloatVectorProperty, FloatProperty, EnumProperty, BoolVectorProperty
from bpy.app.translations import pgettext
from bpy.types import Panel, Operator, SpaceView3D, PropertyGroup

logger = logging.getLogger("svg_exporter")

# Properties
class SVGSceneProperties(PropertyGroup):
    height = IntProperty(name="Height", min=4, max=65536, default=1080)
    width = IntProperty(name="Width", min=4, max=65536, default=1920)
    scale = FloatProperty(name="Scale", min=0.00001, max=100000.0, step=1, default=100.0, precision=3)
    export_path = StringProperty(name="Export path", subtype='FILE_PATH', description="Export path", default="//sample.svg")
    draw_area = BoolProperty(default=False)
    slide = FloatProperty(name="Slide", step=10, default=0.1)
    use_background = BoolProperty(name="Use backGround", default=False)
    background_color = FloatVectorProperty(name="Background Color", subtype='COLOR', size=4, min=0, max=1, default=[0.8, 0.8, 0.8, 0.8])
    script_is_executed = BoolProperty(default=False)
    lock_init_project = BoolProperty(default=False)

# Operator
class InitProjectOperator(bpy.types.Operator):
    bl_idname = "svg.init_project_operator"
    bl_label = "Init Project"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        logger.info("start")

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        self.screen_setting(context)
        self.scene_setting(context.scene)
        self.area_setting()

        context.scene.svg_scene_properties.script_is_executed = True

        logger.info("end")

        return {'FINISHED'}

    def screen_setting(self, context):
        screens = bpy.data.screens

        screen_names = ["3D View Full", "Game Logic", "Motion Tracking", "Video Editing"]

        for screen_name in screen_names:
            if screen_name in screens:
                bpy.ops.screen.delete({'screen': screens[screen_name]})

        context.window.screen = screens['Default']

    def scene_setting(self, scene):
        scene.render.engine = 'CYCLES'

    def area_setting(self):
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    override = bpy.context.copy()
                    override["window"] = bpy.context.window
                    override["screen"] = screen
                    override["area"] = area
                    bpy.ops.view3d.view_persportho(override)
                    bpy.ops.view3d.viewnumpad(override, type='TOP')

                    logger.debug("area_setting in:" + screen.name)

                    for space in area.spaces:
                        space.use_occlude_geometry = False
                        # space.lens = 50

# UI
class SVGToolPanel(Panel):
    bl_idname = "OBJECT_PT_svg"
    bl_label = "SVG Exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'SVG'

    def draw(self, context):
        svg_scene_properties = context.scene.svg_scene_properties

        layout = self.layout

        split = layout.split(percentage=0.85)
        col = split.column()
        col.operator(InitProjectOperator.bl_idname, text=pgettext(InitProjectOperator.bl_label))

        if svg_scene_properties.lock_init_project:
            col.enabled = False

        col = split.column()
        if svg_scene_properties.lock_init_project:
            icon = 'LOCKED'
        else:
            icon = 'UNLOCKED'
        col.prop(svg_scene_properties, "lock_init_project", text="", icon=icon)

        if svg_scene_properties.script_is_executed:
            split.enabled = False

        row = layout.row()
        if svg_scene_properties.draw_area is False:
            icon = 'PLAY'
            txt = 'Display border'
        else:
            icon = "PAUSE"
            txt = 'Hide border'

        row.operator("svg.runopenglbutton", text=txt, icon=icon)

        # layout.prop(svg_scene_properties, "property_type", expand=True)
        col = layout.column(align=True)
        col.prop(svg_scene_properties, "height")
        col.prop(svg_scene_properties, "width")
        col.prop(svg_scene_properties, "scale")

        row = layout.row()
        row.prop(svg_scene_properties, "use_background", text="Use background")

        row = layout.row()
        if svg_scene_properties.use_background:
            row.prop(svg_scene_properties, "background_color", text="")

        row = layout.row()
        row.label("Export Path")
        row = layout.row()
        row.prop(svg_scene_properties, "export_path", text="")
        row = layout.row()
        row.operator(OpenSvg.bl_idname, icon='FILE_FOLDER')

        layout.row().separator()

        row = layout.row()
        row.operator(AddCurveTool.bl_idname, icon='CURVE_BEZCIRCLE')

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(UpObject.bl_idname, icon='TRIA_UP')
        row.operator(DownObject.bl_idname, icon='TRIA_DOWN')
        col.prop(svg_scene_properties, "slide")
        col.operator(ResetObject.bl_idname, icon='X')

        layout.row().separator()

        if context.object is not None:
            obj = context.object
            if obj.type == 'CURVE':
                row = layout.row()
                row.prop(obj.data, "resolution_u")
                if len(obj.data.materials) > 0:
                    mat = obj.data.materials[0]
                    col = layout.column(align=True)
                    col.label("Viewport Color:")
                    col.prop(mat, "diffuse_color", text="")
                    col.prop(mat, "alpha")

        layout.row().separator()

        row = layout.row()
        row.scale_y = 2.0
        row.operator(SvgExporter.bl_idname, icon='EXPORT')

# op
class AddCurveTool(Operator):
    bl_idname = "svg.addcurve"
    bl_label = "Add curve"

    def invoke(self, context, event):
        loc=(0.0, 0.0, 0.0)
        if len(context.selected_objects) > 0:
            loc = (context.object.location[0], context.object.location[1], context.object.location[2] + 0.1)

        bpy.ops.curve.primitive_bezier_circle_add(location=loc)
        obj = context.object

        obj.lock_location[2] = True

        curve = obj.data

        curve.dimensions = '2D'
        curve.resolution_u = 5

        mat = bpy.data.materials.new(name="svg_material")
        mat.diffuse_color = (1.0, 1.0, 1.0)
        curve.materials.append(mat)

        return {'FINISHED'}

class UpObject(Operator):
    bl_idname = "svg.upobject"
    bl_label = "Up"

    def invoke(self, context, event):
        slide = context.scene.svg_scene_properties.slide
        for obj in context.selected_objects:
            obj.location[2] += slide

        return {'FINISHED'}

class DownObject(Operator):
    bl_idname = "svg.downobject"
    bl_label = "Down"

    def invoke(self, context, event):
        slide = context.scene.svg_scene_properties.slide
        for obj in context.selected_objects:
            obj.location[2] -= slide

        return {'FINISHED'}

class ResetObject(Operator):
    bl_idname = "svg.resetobject"
    bl_label = "Reset"

    def invoke(self, context, event):
        for obj in context.selected_objects:
            obj.location[2] = 0.0

        return {'FINISHED'}

class OpenSvg(Operator):
    bl_idname = "svg.opensvg"
    bl_label = "Open SVG"

    def invoke(self, context, event):
        file_path = bpy.path.abspath(context.scene.svg_scene_properties.export_path)
        try: bpy.ops.wm.url_open(url=file_path)
        except: pass
        return{'FINISHED'}

        return {'FINISHED'}

class RunHintDisplayButton(Operator):
    bl_idname = "svg.runopenglbutton"
    bl_label = "Display hint data manager"

    _handle_3d = None

    def invoke(self, context, event):
        if context.scene.svg_scene_properties.draw_area is False:
            logger.debug("check 1")
            if context.area.type == 'VIEW_3D':
                args = (self, context)
                RunHintDisplayButton._handle_3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_3d, args, 'WINDOW', 'POST_VIEW')
                context.scene.svg_scene_properties.draw_area = True
                context.area.tag_redraw()
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "View3D not found, cannot run operator")
                return {'CANCELLED'}
        else:
            logger.debug("check 2")
            logger.debug(context.scene.svg_scene_properties.draw_area)
            if RunHintDisplayButton._handle_3d is not None:
                logger.debug(type(RunHintDisplayButton._handle_3d))
                bpy.types.SpaceView3D.draw_handler_remove(RunHintDisplayButton._handle_3d, 'WINDOW')
                context.scene.svg_scene_properties.draw_area = False
                context.area.tag_redraw()
            else:
                context.scene.svg_scene_properties.draw_area = False
            return {'FINISHED'}

def draw_callback_3d(self, context):
    bgl.glEnable(bgl.GL_BLEND)

    height = context.scene.svg_scene_properties.height
    width = context.scene.svg_scene_properties.width
    scale = context.scene.svg_scene_properties.scale

    draw_line_3d((-width/2/scale, height/2/scale, 0.0), (width/2/scale, height/2/scale, 0.0))
    draw_line_3d((width/2/scale, height/2/scale, 0.0), (width/2/scale, -height/2/scale, 0.0))
    draw_line_3d((width/2/scale, -height/2/scale, 0.0), (-width/2/scale, -height/2/scale, 0.0))
    draw_line_3d((-width/2/scale, -height/2/scale, 0.0), (-width/2/scale, height/2/scale, 0.0))

    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)

def draw_line_3d(start, end, width=1):
    bgl.glLineWidth(width)
    bgl.glColor4f(1.0, 1.0, 0.0, 0.5)
    bgl.glBegin(bgl.GL_LINES)
    bgl.glVertex3f(*start)
    bgl.glVertex3f(*end)
    bgl.glEnd()

translations = {
    "ja_JP": {
        ("*", "Base Settings"): "基本設定",
        ("*", "Export SVG"): "Export SVG",
        ("*", "Use background"): "背景色を使用",
    }
}

def register():
    bpy.types.Scene.svg_scene_properties = PointerProperty(type=SVGSceneProperties)

    bpy.app.translations.register(__name__, translations)

def unregister():
    bpy.app.translations.unregister(__name__)
    del bpy.types.Scene.svg_scene_properties

