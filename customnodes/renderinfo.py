# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import create_new_nodegroup, set_socket_defvalue


class NODEBOOSTER_NG_renderinfo(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodgroup: Gather informations about your active scene render info.
    • Expect updates on each depsgraph post and frame_pre update signals"""

    bl_idname = "GeometryNodeNodeBoosterRenderInfo"
    bl_label = "Render Info"

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
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None

    def update(self):
        """generic update function"""

        scene = bpy.context.scene

        set_socket_defvalue(self.node_tree, 0, value=scene.render.resolution_x)
        set_socket_defvalue(self.node_tree, 1, value=scene.render.resolution_y)
        set_socket_defvalue(self.node_tree, 2, value=scene.render.resolution_percentage)
        set_socket_defvalue(self.node_tree, 3, value=scene.render.pixel_aspect_x)
        set_socket_defvalue(self.node_tree, 4, value=scene.render.pixel_aspect_y)
        set_socket_defvalue(self.node_tree, 5, value=scene.frame_start)
        set_socket_defvalue(self.node_tree, 6, value=scene.frame_end)
        set_socket_defvalue(self.node_tree, 7, value=scene.frame_step)

        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        return None
        
    @classmethod
    def update_all_instances(cls, from_depsgraph=False,):
        """search for all nodes of this type and update them"""
        
        all_instances = [n for ng in bpy.data.node_groups for n in ng.nodes if (n.bl_idname==cls.bl_idname)]
        for n in all_instances:
            n.update()
            
        return None 
