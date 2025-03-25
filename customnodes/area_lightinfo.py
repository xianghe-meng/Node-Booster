# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.), Andrew Stevenson
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import create_new_nodegroup, set_socket_defvalue


class NODEBOOSTER_NG_area_lightinfo(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodegroup: Gather informations about any area light.
    • Expect updates on each depsgraph post and frame_pre update signals"""

    bl_idname = "GeometryNodeNodeBoosterAreaLightInfo"
    bl_label = "Area Light Info"

    def light_obj_poll(self, obj):
        return obj.type == 'LIGHT' and obj.data.type == 'AREA'

    light_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=light_obj_poll,
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
                out_sockets={
                    "Area Light" : "NodeSocketObject",
                    "Color" : "NodeSocketColor",
                    "Power" : "NodeSocketFloat",
                    "Shape" : "NodeSocketString",
                    "Size X" : "NodeSocketFloat",
                    "Size Y" : "NodeSocketFloat",
                    "Beam Spread" : "NodeSocketFloat",
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
        light_obj = self.light_obj

        if (light_obj and light_obj.type == 'LIGHT' and light_obj.data and light_obj.data.type == 'AREA'):
            set_socket_defvalue(self.node_tree, 0, value=light_obj)
            set_socket_defvalue(self.node_tree, 1, value=[light_obj.data.color[0], light_obj.data.color[1], light_obj.data.color[2], 1.0])
            set_socket_defvalue(self.node_tree, 2, value=light_obj.data.energy)
            set_socket_defvalue(self.node_tree, 3, value=light_obj.data.shape)
            set_socket_defvalue(self.node_tree, 4, value=light_obj.data.size)
            set_socket_defvalue(self.node_tree, 5, value=light_obj.data.size_y)
            set_socket_defvalue(self.node_tree, 6, value=light_obj.data.spread)
        else:
            set_socket_defvalue(self.node_tree, 0, value=None)
            set_socket_defvalue(self.node_tree, 1, value=[0.0, 0.0, 0.0, 0.0])
            set_socket_defvalue(self.node_tree, 2, value=0.0)
            set_socket_defvalue(self.node_tree, 3, value="")
            set_socket_defvalue(self.node_tree, 4, value=0.0)
            set_socket_defvalue(self.node_tree, 5, value=0.0)
            set_socket_defvalue(self.node_tree, 6, value=0.0)

        return None

    def draw_label(self,):
        """node label"""

        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row(align=True)
        sub = row.row(align=True)

        sub.prop(self, "light_obj", text="", icon="LIGHT_AREA")

        return None

    @classmethod
    def update_all_instances(cls, from_depsgraph=False,):
        """search for all nodes of this type and update them"""

        all_instances = [n for ng in bpy.data.node_groups for n in ng.nodes if (n.bl_idname==cls.bl_idname)]
        for n in all_instances:
            n.update()

        return None
