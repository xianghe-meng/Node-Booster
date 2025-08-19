# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE no pyhon execution here, this node rely on resolve_id_data()
# NOTE we should be able to use.. 
# col.template_any_ID(self, "id_data", "id_type", text="")
# but for id_data: PointerProperty to bpy.types.ID seems to be exclusive to internal C API
# should fix C code source because this template is exclusive for internal use
        
import bpy

from .. import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    crosseditor_socktype_adjust,
    create_new_nodegroup,
    set_ng_socket_defvalue,
    set_ng_socket_type,
    set_ng_socket_label,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
)
from ..nex.pytonode import py_to_Sockdata


# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterRNAInfo"
    bl_label = "RNA Info"
    bl_description = """Gather informations about any ID data and their properties.
    • Expect the same behavior than setting up a driver variable in the driver editor.
    • Expect updates on each depsgraph post and frame_pre update signals"""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST',}
    tree_type = "*ChildrenDefined*"

    def update_signal(self,context):
        self.resolve_user_path(assign_socketype=True)
        return None 

    id_type : bpy.props.EnumProperty(
        name="ID Type",
        description="The type of ID datablock to get attributes from",
        items=[
                ('ACTION',         "Action",             "Animation data-block defining and containing F-curves",       'ACTION',                   0),
                ('ARMATURE',       "Armature",           "Armature data-block with bones",                              'ARMATURE_DATA',            1),
                ('BRUSH',          "Brush",              "Brush data-block for painting",                               'BRUSH_DATA',               2),
                ('CACHEFILE',      "CacheFile",          "External cache file data-block",                              'FILE_CACHE',               3),
                ('CAMERA',         "Camera",             "Camera data-block for storing camera settings",               'CAMERA_DATA',              4),
                ('COLLECTION',     "Collection",         "Collection of objects",                                       'COLLECTION_NEW',           5),
                ('CURVE',          "Curve",              "Curve data-block for storing curves",                         'CURVE_DATA',               6),
                ('CURVES',         "Curves",             "Hair curves data-block",                                      'CURVES_DATA',              7),
                ('LINESTYLE',      "FreestyleLineStyle", "Line style data-block for Freestyle line rendering",          'LINE_DATA',                8),
                ('GREASEPENCIL',   "GreasePencil",       "Grease Pencil data-block",                                    'GREASEPENCIL',             9),
                ('GREASEPENCIL_V3',"GreasePencilv3",     "Grease Pencil v3 data-block",                                 'OUTLINER_DATA_GREASEPENCIL',10),
                ('IMAGE',          "Image",              "Image data-block for pictures",                               'IMAGE_DATA',               11),
                ('KEY',            "Key",                "Key data-block for shape keys",                               'SHAPEKEY_DATA',            12),
                ('LATTICE',        "Lattice",            "Lattice data-block for storing deformation lattices",         'LATTICE_DATA',             13),
                ('LIBRARY',        "Library",            "Library data-block of externally linked data",                'LIBRARY_DATA_DIRECT',      14),
                ('LIGHT',          "Light",              "Light data-block for lighting",                               'LIGHT_DATA',               15),
                ('LIGHTPROBE',     "LightProbe",         "Light probe data-block for lighting",                         'OUTLINER_DATA_LIGHTPROBE', 16),
                ('MASK',           "Mask",               "Mask data-block for storing mask curves",                     'MOD_MASK',                 17),
                ('MATERIAL',       "Material",           "Material data-block for storing material settings",           'MATERIAL_DATA',            18),
                ('MESH',           "Mesh",               "Mesh data-block with faces, edges and vertices",              'MESH_DATA',                19),
                ('META',           "MetaBall",           "MetaBall data-block for storing metaballs",                   'META_DATA',                20),
                ('MOVIECLIP',      "MovieClip",          "Movie clip data-block for tracking",                          'TRACKER',                  21),
                ('NODETREE',       "NodeTree",           "Node tree data-block",                                        'NODETREE',                 22),
                ('OBJECT',         "Object",             "Object data-block for storing transformations",               'OBJECT_DATA',              23),
                ('PAINTCURVE',     "PaintCurve",         "Paint curve data-block for storing brush strokes",            'CURVE_BEZCURVE',           24),
                ('PALETTE',        "Palette",            "Palette data-block for storing color palettes",               'COLOR',                    25),
                ('PARTICLE',       "ParticleSettings",   "Particle settings data-block",                                'PARTICLES',                26),
                ('POINTCLOUD',     "PointCloud",         "Point cloud data-block",                                      'POINTCLOUD_DATA',          27),
                ('SCENE',          "Scene",              "Scene data-block for storing scenes",                         'SCENE_DATA',               28),
                ('SCREEN',         "Screen",             "Screen data-block for storing screen layouts",                'SCREEN_BACK',              29),
                ('SOUND',          "Sound",              "Sound data-block for storing sounds",                         'SOUND',                    30),
                ('SPEAKER',        "Speaker",            "Speaker data-block for 3D audio speaker objects",             'SPEAKER',                  31),
                ('TEXT',           "Text",               "Text data-block for storing text",                            'TEXT',                     32),
                ('TEXTURE',        "Texture",            "Texture data-block for storing textures",                     'TEXTURE_DATA',             33),
                ('FONT',           "VectorFont",         "Vector font data-block for storing fonts",                    'FONT_DATA',                34),
                ('VOLUME',         "Volume",             "Volume data-block for storing 3D volumes",                    'VOLUME_DATA',              35),
                ('WM',             "WindowManager",      "Window manager data-block for storing window configurations", 'WINDOW',                   36),
                ('WORKSPACE',      "WorkSpace",          "Workspace data-block for storing workspace configurations",   'WORKSPACE',                37),
                ('WORLD',          "World",              "World data-block for storing world environments",             'WORLD_DATA',               38),
            ],
        default='OBJECT',
        update=update_signal,
        )

    # id_data: bpy.props.PointerProperty(type=bpy.types.ID) does not work......
    # what a dumb fallback.. plus, it may lead to hidden extra user if the user is not careful.
    # see https://blender.stackexchange.com/questions/214045/making-an-anytype-pointer
    Action          : bpy.props.PointerProperty(type=bpy.types.Action)
    Armature        : bpy.props.PointerProperty(type=bpy.types.Armature)
    Brush           : bpy.props.PointerProperty(type=bpy.types.Brush)
    Cachefile       : bpy.props.PointerProperty(type=bpy.types.CacheFile)
    Camera          : bpy.props.PointerProperty(type=bpy.types.Camera)
    Collection      : bpy.props.PointerProperty(type=bpy.types.Collection)
    Curve           : bpy.props.PointerProperty(type=bpy.types.Curve)
    Curves          : bpy.props.PointerProperty(type=bpy.types.Curves)
    Linestyle       : bpy.props.PointerProperty(type=bpy.types.FreestyleLineStyle)
    Greasepencil    : bpy.props.PointerProperty(type=bpy.types.GreasePencil)
    Greasepencil_V3 : bpy.props.PointerProperty(type=bpy.types.GreasePencil)
    Image           : bpy.props.PointerProperty(type=bpy.types.Image)
    Key             : bpy.props.PointerProperty(type=bpy.types.Key)
    Lattice         : bpy.props.PointerProperty(type=bpy.types.Lattice)
    Library         : bpy.props.PointerProperty(type=bpy.types.Library)
    Light           : bpy.props.PointerProperty(type=bpy.types.Light)
    Lightprobe      : bpy.props.PointerProperty(type=bpy.types.LightProbe)
    Mask            : bpy.props.PointerProperty(type=bpy.types.Mask)
    Material        : bpy.props.PointerProperty(type=bpy.types.Material)
    Mesh            : bpy.props.PointerProperty(type=bpy.types.Mesh)
    Meta            : bpy.props.PointerProperty(type=bpy.types.MetaBall)
    Movieclip       : bpy.props.PointerProperty(type=bpy.types.MovieClip)
    Nodetree        : bpy.props.PointerProperty(type=bpy.types.NodeTree)
    Object          : bpy.props.PointerProperty(type=bpy.types.Object)
    Paintcurve      : bpy.props.PointerProperty(type=bpy.types.PaintCurve)
    Palette         : bpy.props.PointerProperty(type=bpy.types.Palette)
    Particle        : bpy.props.PointerProperty(type=bpy.types.ParticleSettings)
    Pointcloud      : bpy.props.PointerProperty(type=bpy.types.PointCloud)
    Scene           : bpy.props.PointerProperty(type=bpy.types.Scene)
    Screen          : bpy.props.PointerProperty(type=bpy.types.Screen)
    Sound           : bpy.props.PointerProperty(type=bpy.types.Sound)
    Speaker         : bpy.props.PointerProperty(type=bpy.types.Speaker)
    Text            : bpy.props.PointerProperty(type=bpy.types.Text)
    Texture         : bpy.props.PointerProperty(type=bpy.types.Texture)
    Font            : bpy.props.PointerProperty(type=bpy.types.VectorFont)
    Volume          : bpy.props.PointerProperty(type=bpy.types.Volume)
    Wm              : bpy.props.PointerProperty(type=bpy.types.WindowManager)
    Workspace       : bpy.props.PointerProperty(type=bpy.types.WorkSpace)
    World           : bpy.props.PointerProperty(type=bpy.types.World)

    pointer_types = [
        'Action', 'Armature', 'Brush', 'Cachefile', 'Camera', 'Collection', 
        'Curve', 'Curves', 'Linestyle', 'Greasepencil', 'Greasepencil_V3', 
        'Image', 'Key', 'Lattice', 'Library', 'Light', 'Lightprobe', 'Mask', 
        'Material', 'Mesh', 'Meta', 'Movieclip', 'Nodetree', 'Object', 
        'Paintcurve', 'Palette', 'Particle', 'Pointcloud', 'Scene', 
        'Screen', 'Sound', 'Speaker', 'Text', 'Texture', 'Font', 
        'Volume', 'Wm', 'Workspace', 'World',
        ]

    data_path: bpy.props.StringProperty(
        name="Data Path",
        description="RNA data path for the property (e.g. 'location.x', ['MyProp'], ect..)",
        default="",
        update=update_signal,
        )
    is_error: bpy.props.BoolProperty(
        default=False,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={
                    "Value" : "NodeSocketFloat",
                    "NoErrors" : "NodeSocketBool",
                    },
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

        self.width = 195

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        #NOTE: copy/paste can cause crashes, we use a timer to delay the action
        def delayed_copy():
            self.node_tree = node.node_tree.copy()
        bpy.app.timers.register(delayed_copy, first_interval=0.01)

        return None

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def resolve_user_path(self, assign_socketype=False):
        """resolve the data path and assign value to output socket"""

        ng = self.node_tree
        data_path = self.data_path

        # find the correct ptr based on the id_type
        ptrname = self.id_type.title()
        id_data = getattr(self, ptrname)

        # clean all unused pointers that aren't the id_data, to avoid ghost users.
        for pointer_type in self.pointer_types:
            if (pointer_type != ptrname):
                setattr(self, pointer_type, None)

        #reset to default
        self.is_error = False
        set_ng_socket_defvalue(ng, 1, value=False)
        set_ng_socket_label(ng, 0, label="Value")
        set_ng_socket_label(ng, 1, label="NoErrors")

        # check if the data path is valid
        if (not id_data):
            set_ng_socket_defvalue(ng, 1, value=True)
            set_ng_socket_label(ng, 1, label="EmptyDataError")
            return None
        if (not data_path):
            set_ng_socket_defvalue(ng, 1, value=True)
            set_ng_socket_label(ng, 1, label="EmptyPathError")
            return None

        # Try to evaluate the data path
        try:
            value = id_data.path_resolve(data_path)
        except Exception as e:
            set_ng_socket_defvalue(ng, 1, value=True)
            set_ng_socket_label(ng, 1, label="WrongPathError")
            self.is_error = True
            return None
        
        # Convert Python value to socket data
        try:
            set_value, set_label, socktype = py_to_Sockdata(value)
        except Exception as e:
            set_ng_socket_defvalue(ng, 1, value=True)
            set_ng_socket_label(ng, 1, label="UnsupportedTypeError")
            self.is_error = True
            return None

        # check if the socket type is supported in context editor.
        if crosseditor_socktype_adjust(socktype,ng.type).startswith('Unavailable'):
            set_ng_socket_defvalue(ng, 1, value=True)
            set_ng_socket_label(ng, 1, label="UnavailableSocketError")
            self.is_error = True
            return None
    
        # Set socket type and value
        #set values
        if (assign_socketype):
            set_ng_socket_type(ng, 0, socket_type=socktype)
        set_ng_socket_label(ng, 0, label=set_label)
        set_ng_socket_defvalue(ng, 0, value=set_value)

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'RNA Info'
        return self.label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        split = layout.split(factor=0.2, align=True)
        split.prop(self, "id_type", text="", icon_only=True)
        ptrname = self.id_type.title()
        split.prop(self, ptrname, text="")
        
        #use template? i doubt it's reliable..
        #layout.template_path_builder(self, "data_path", self.id_data, text="")

        row = layout.row(align=True)
        row.alert = self.is_error
        row.prop(self, "data_path", text="", icon='RNA')

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):

            panel.prop(self, "id_type", text="",)
            ptrname = self.id_type.title()
            panel.prop(self, ptrname, text="")

            row = panel.row(align=True)
            row.alert = self.is_error
            row.prop(self, "data_path", text="", icon='RNA')

        header, panel = layout.panel("doc_panelid", default_closed=True,)
        header.label(text="Documentation",)
        if (panel):
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description,
                )
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"

        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False

            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree") 
        
        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """search for all node instances of this type and refresh them. Will be called automatically if .auto_upd_flags's are defined"""
        
        if (using_nodes is None):
              nodes = get_booster_nodes(by_idnames={cls.bl_idname},)
        else: nodes = [n for n in using_nodes if (n.bl_idname==cls.bl_idname)]

        for n in nodes:
            if (n.mute):
                continue
            n.resolve_user_path(assign_socketype=False)
            continue

        return None 

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_RNAInfo(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_RNAInfo(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_RNAInfo(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname 