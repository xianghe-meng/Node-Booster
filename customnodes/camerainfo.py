# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.), Andrew Stevenson
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    create_new_nodegroup,
    set_ng_socket_defvalue,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterCameraInfoV2"
    bl_label = "Camera Info"
    bl_description = """Gather informations about any camera.
    • By default the camera will always use the active camera.
    • Expect updates on each depsgraph post and frame_pre update signals"""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST',}
    tree_type = "*ChildrenDefined*"

    def update_signal(self,context):
        self.sync_out_values()
        return None 

    use_scene_cam: bpy.props.BoolProperty(
        default=True,
        name="Use Active Camera",
        description="Automatically update the pointer to the active scene camera",
        update=update_signal,
        )

    def camera_obj_poll(self, obj):
        return (obj.type == 'CAMERA')

    camera_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=camera_obj_poll,
        update=update_signal,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        match self.tree_type:
            case 'GeometryNodeTree':
                sockets = {
                    "Object":        "NodeSocketObject",
                    "Field of View": "NodeSocketFloat",
                    "Shift X":       "NodeSocketFloat",
                    "Shift Y":       "NodeSocketFloat",
                    "Clip Start":    "NodeSocketFloat",
                    "Clip End":      "NodeSocketFloat",
                    "Sensor Type":   "NodeSocketString",
                    "Sensor Width":  "NodeSocketFloat",
                    "Sensor Height": "NodeSocketFloat",
                    }

            case 'ShaderNodeTree' | 'CompositorNodeTree':
                sockets = {
                    "Location":      "NodeSocketVector", #object transforms instead.
                    "Rotation":      "NodeSocketVector", #object transforms instead.
                    "Scale":         "NodeSocketVector", #object transforms instead.
                    "Field of View": "NodeSocketFloat",
                    "Shift X":       "NodeSocketFloat",
                    "Shift Y":       "NodeSocketFloat",
                    "Clip Start":    "NodeSocketFloat",
                    "Clip End":      "NodeSocketFloat",
                    "Sensor Type":   "NodeSocketInt", #int instead
                    "Sensor Width":  "NodeSocketFloat",
                    "Sensor Height": "NodeSocketFloat",
                    }

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets=sockets,
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

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
        
    def sync_out_values(self):
        """sync output socket values with data"""
        
        scene = bpy.context.scene
        co = scene.camera if (self.use_scene_cam) else self.camera_obj
        cd = co.data if co else None
        valid = (co and cd)

        values = {
            "Field of View": cd.angle         if (valid) else 0.0,
            "Shift X":       cd.shift_x       if (valid) else 0.0,
            "Shift Y":       cd.shift_y       if (valid) else 0.0,
            "Clip Start":    cd.clip_start    if (valid) else 0.0,
            "Clip End":      cd.clip_end      if (valid) else 0.0,
            "Sensor Width":  cd.sensor_width  if (valid) else 0.0,
            "Sensor Height": cd.sensor_height if (valid) else 0.0,
            }

        #different behavior and sockets depending on editor type
        match self.tree_type:

            case 'GeometryNodeTree':
                values["Sensor Type"] = cd.sensor_fit if (valid) else ""
                #Support for old socket name, previous version of node.
                camvalue = co if (valid) else None
                if ("Camera Object" in self.outputs):
                    values["Camera Object"] = camvalue
                elif ("Object" in self.outputs):
                    values["Object"] = camvalue

            case 'ShaderNodeTree' | 'CompositorNodeTree':
                values["Location"] = co.location        if (valid) else (0,0,0)
                values["Rotation"] = co.rotation_euler  if (valid) else (0,0,0)
                values["Scale"]    = co.scale           if (valid) else (0,0,0)
                values["Sensor Type"] = 0 if (cd.sensor_fit=='AUTO') else 2 if (cd.sensor_fit=='HORIZONTAL') else 3

        for k,v in values.items():
            set_ng_socket_defvalue(self.node_tree, socket_name=k, value=v,)

        return None

    def draw_label(self,):
        """node label"""

        if (self.label==''):
            return 'Camera Info'

        return self.label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row(align=True)
        sub = row.row(align=True)

        if (self.use_scene_cam):
              sub.enabled = False
              sub.prop(bpy.context.scene, "camera", text="", icon="CAMERA_DATA")
        else: sub.prop(self, "camera_obj", text="", icon="CAMERA_DATA")

        row.prop(self, "use_scene_cam", text="", icon="SCENE_DATA")

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):
                
            row = panel.row(align=True)
            sub = row.row(align=True)

            if (n.use_scene_cam):
                    sub.enabled = False
                    sub.prop(bpy.context.scene, "camera", text="", icon="CAMERA_DATA")
            else: sub.prop(n, "camera_obj", text="", icon="CAMERA_DATA")

            panel.prop(n, "use_scene_cam",)

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
            n.sync_out_values()
            
        return None 

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_CameraInfo(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_CameraInfo(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_CameraInfo(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname
