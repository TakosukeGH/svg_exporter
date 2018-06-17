bl_info= {
    "name": "PMX Exporter",
    "author": "Takosuke",
    "version": (0, 1, 1),
    "blender": (2, 74, 0),
    "location": "Properties",
    "description": "Export PMX file.",
    "support": "COMMUNITY",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": 'Object'}

if "bpy" in locals():
    import imp
    imp.reload(properties)
    imp.reload(tools)
    imp.reload(exporter)
    imp.reload(structs)
    imp.reload(const)
    imp.reload(logutils)
    imp.reload(fileutils)
    imp.reload(meshutils)
    imp.reload(checker)
    imp.reload(nameutils)
    imp.reload(init_project)
else:
    from . import properties, tools, exporter, structs, const, logutils, checker, nameutils, fileutils, init_project

import bpy
import logging

logger = logging.getLogger("pmx_exporter")

if not logger.handlers:
    hdlr = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-7s %(asctime)s %(message)s (%(module)s %(funcName)s)", datefmt="%H:%M:%S")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG) # DEBUG, INFO, WARNING, ERROR, CRITICAL

logger.debug("init logger") # debug, info, warning, error, critical

def register():
    bpy.utils.register_module(__name__)
    properties.register()
    tools.register()

def unregister():
    tools.unregister()
    properties.unregister()
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
