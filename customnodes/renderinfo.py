# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
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

    bl_idname = "NodeBoosterRenderInfo"
    bl_label = "Render Info"
    bl_description  = """Custom Nodgroup: Gather informations about your active scene render info.
    • Expect updates on each depsgraph post and frame_pre update signals"""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST',}
    tree_type = "*ChildrenDefined*"

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
                    "Resolution X" : "NodeSocketInt",
                    "Resolution Y" : "NodeSocketInt",
                    "Resolution %" : "NodeSocketFloat",
                    "Aspect X" : "NodeSocketFloat",
                    "Aspect Y" : "NodeSocketFloat",
                    "Frame Start" : "NodeSocketInt",
                    "Frame End" : "NodeSocketInt",
                    "Frame Step" : "NodeSocketInt",
                    },
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

        set_ng_socket_defvalue(self.node_tree, 0, value=scene.render.resolution_x)
        set_ng_socket_defvalue(self.node_tree, 1, value=scene.render.resolution_y)
        set_ng_socket_defvalue(self.node_tree, 2, value=scene.render.resolution_percentage)
        set_ng_socket_defvalue(self.node_tree, 3, value=scene.render.pixel_aspect_x)
        set_ng_socket_defvalue(self.node_tree, 4, value=scene.render.pixel_aspect_y)
        set_ng_socket_defvalue(self.node_tree, 5, value=scene.frame_start)
        set_ng_socket_defvalue(self.node_tree, 6, value=scene.frame_end)
        set_ng_socket_defvalue(self.node_tree, 7, value=scene.frame_step)

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Render Info'
        return self.label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

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

class NODEBOOSTER_NG_GN_RenderInfo(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_RenderInfo(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_RenderInfo(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname