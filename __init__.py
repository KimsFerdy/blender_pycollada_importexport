##### BEGIN GPL LICENSE BLOCK #####
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "COLLADA format",
    "author": "Tim Knip, Dusan Maliarik, Lawrence D'Oliveiro, Kims Ferdy",
    "version": (1, 0, 1),
    "blender": (5, 0, 0),
    "location": "File > Import, File > Export",
    "description": "Import/Export COLLADA",
    "pip_dependencies": ["pycollada"],  # Declared for PDV auto-detection
    "category": "Import-Export",
}

import os
import sys
import subprocess
import bpy
import importlib
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    StringProperty,
)
from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper,
)

# Get user modules path reliably using script_paths (compatible with Blender 5.0+)
user_script_paths = bpy.utils.script_paths(subdir="modules")
if user_script_paths:
    modules_path = user_script_paths[0]
else:
    # Very unlikely fallback
    modules_path = os.path.join(
        os.path.expanduser("~"),
        "AppData",
        "Roaming",
        "Blender Foundation",
        "Blender",
        "5.0",
        "scripts",
        "modules",
    )

os.makedirs(modules_path, exist_ok=True)

if modules_path not in sys.path:
    sys.path.append(modules_path)
import site

site.addsitedir(modules_path)

if "import_collada" in locals():
    importlib.reload(import_collada)
if "export_collada" in locals():
    importlib.reload(export_collada)

# ===== DEPENDENCY CHECK =====
try:
    import collada

    HAS_COLLADA = True
except ImportError:
    HAS_COLLADA = False


class IMPORT_OT_collada(bpy.types.Operator, ImportHelper):
    """COLLADA import operator."""

    bl_idname = "import_scene.collada"
    bl_label = "Import COLLADA"
    bl_options = {"UNDO"}

    filter_glob: StringProperty(
        default="*.dae;*.zae;*.kmz",
        options={"HIDDEN"},
    )
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )
    directory: StringProperty(
        subtype="DIR_PATH",
    )

    recognize_blender_extensions: BoolProperty(
        name="Recognize Blender Extensions",
        description="Recognize extra info specific to Blender",
        default=True,
    )
    transformation: EnumProperty(
        name="Transformations",
        items=(
            ("MUL", "Multiply", ""),
            ("PARENT", "Parenting", ""),
            ("APPLY", "Apply", ""),
        ),
        default="MUL",
    )

    def execute(self, context):
        if not HAS_COLLADA:
            self.report(
                {"ERROR"}, "pycollada not installed! Install via Preferences > Add-ons."
            )
            return {"CANCELLED"}
        from . import import_collada

        kwargs = self.as_keywords(ignore=("filter_glob", "files"))
        if not os.path.isfile(kwargs["filepath"]):
            self.report(
                {"ERROR"}, f"COLLADA import failed, not a file: {kwargs['filepath']}"
            )
            return {"CANCELLED"}
        return import_collada.load(
            self, context, self.filepath.endswith(".zae"), **kwargs
        )

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {"RUNNING_MODAL"}


class EXPORT_OT_collada(bpy.types.Operator, ExportHelper):
    """COLLADA export operator."""

    bl_idname = "export_scene.collada"
    bl_label = "Export COLLADA"
    bl_options = {"UNDO"}

    filename_ext = ".dae"
    filter_glob: StringProperty(
        default="*.dae",
        options={"HIDDEN"},
    )
    directory: StringProperty(
        subtype="DIR_PATH",
    )

    collada_version: EnumProperty(
        name="Collada Version",
        description="version number to set in output Collada file",
        items=(
            ("1.4.1", "1.4.1", ""),
            ("1.5.0", "1.5.0", ""),
        ),
        default="1.4.1",
    )
    add_blender_extensions: BoolProperty(
        name="Add Blender Extensions",
        description="Include extra info specific to Blender",
        default=True,
    )
    export_as: EnumProperty(
        name="Export as",
        items=(
            ("dae", "DAE", ""),
            ("zae", "ZAE", ""),
        ),
        description="DAE separate file or ZAE all-in-one archive",
        default="dae",
    )
    export_textures: BoolProperty(
        name="Export Textures",
        description="Include texture image files",
        default=False,
    )
    up_axis: EnumProperty(
        name="Up",
        items=(
            ("X_UP", "X Up", ""),
            ("Y_UP", "Y Up", ""),
            ("Z_UP", "Z Up", ""),
        ),
        default="Z_UP",
    )
    use_selection: BoolProperty(
        name="Selection Only",
        description="Export selected objects only",
        default=False,
    )

    def check(self, context):
        filepath_changed = False
        out_ext = ".zae" if self.export_as == "zae" else ".dae"
        if not self.filepath.endswith(out_ext):
            self.filepath = os.path.splitext(self.filepath)[0] + out_ext
            filepath_changed = True
            self.export_textures = self.export_as == "zae"
        return filepath_changed

    def execute(self, context):
        if not HAS_COLLADA:
            self.report(
                {"ERROR"}, "pycollada not installed! Install via Preferences > Add-ons."
            )
            return {"CANCELLED"}
        from . import export_collada

        kwargs = self.as_keywords(ignore=("filter_glob",))
        if os.path.exists(self.filepath) and not os.path.isfile(self.filepath):
            self.report(
                {"ERROR"}, f"COLLADA export failed, not a file: {kwargs['filepath']}"
            )
            return {"CANCELLED"}
        return export_collada.save(self, context, **kwargs)


class BCryAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__  # CRITICAL FIX: Must be __name__, not undefined 'name'

    def draw(self, context):
        layout = self.layout
        py_path = sys.executable

        # Get path using same reliable method as installer
        user_path = bpy.utils.resource_path("USER")
        modules_path_display = os.path.join(user_path, "scripts", "modules")
        os.makedirs(modules_path_display, exist_ok=True)

        box = layout.box()
        box.label(text="Module Path (User-Writable):", icon="FILE_FOLDER")
        box.label(text=modules_path_display, icon="INFO")

        if not HAS_COLLADA:
            layout.label(text="⚠️ 'pycollada' module not found!", icon="ERROR")
            layout.label(text="Required for COLLADA import/export", icon="INFO")

            box = layout.box()
            box.label(text="Install via Pip Dependency Verifier:", icon="IMPORT")
            row = box.row()
            row.operator("pipdep.scan_addons", text="Scan Add-ons for Dependencies")
            row = box.row()
            row.operator("pipdep.install_all_missing", text="Install All Missing Dependencies")

            box = layout.box()
            box.label(text="Manual Install (if needed):", icon="CONSOLE")
            box.label(text="Run in PowerShell (Admin not required):")
            # Show properly formatted command for user to copy
            cmd_text = f'& "{py_path}" -m pip install --upgrade --target "{modules_path_display}" pycollada'
            box.label(text=cmd_text, icon="COPY_ID")
        else:
            import collada

            version = getattr(collada, "__version__", "unknown")
            layout.label(text="✓ pycollada installed!", icon="CHECKMARK")
            layout.label(text=f"Version: {version}", icon="INFO")
            layout.label(text=f"Path: {modules_path_display}", icon="FILE_FOLDER")


classes = (
    IMPORT_OT_collada,
    EXPORT_OT_collada,
    BCryAddonPreferences,
)


def menu_func_import(self, context):
    if HAS_COLLADA:
        self.layout.operator(
            IMPORT_OT_collada.bl_idname, text="COLLADA (py) (.dae, .kmz)"
        )
    else:
        row = self.layout.row()
        row.enabled = False
        row.operator(
            IMPORT_OT_collada.bl_idname, text="COLLADA (py) [requires pycollada]"
        )


def menu_func_export(self, context):
    if HAS_COLLADA:
        self.layout.operator(
            EXPORT_OT_collada.bl_idname, text="COLLADA (py) (.dae, .kmz)"
        )
    else:
        row = self.layout.row()
        row.enabled = False
        row.operator(
            EXPORT_OT_collada.bl_idname, text="COLLADA (py) [requires pycollada]"
        )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()