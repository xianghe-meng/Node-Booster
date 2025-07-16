# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os
import numpy as np

from ... import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import casteljau_subdiv_bezsegs, cut_bezsegs, subdiv_project_bezsegs
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    send_refresh_signal,
    cache_booster_nodes_parent_tree,
)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 


class NODEBOOSTER_ND_2DCurveSubdiv(bpy.types.Node):

    bl_idname = "NodeBooster2DCurveSubdiv"
    bl_label = "Subdivide 2D Curve"
    bl_description = """Subdivide a 2D curve. Either by a specific number of subdivisions, or at a specific X location, or by projecting the curve along the reference curve tangent space."""
    auto_upd_flags = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="Subdivide a 2D curve with the given methods",
        items=(('CUT', 'Cut', 'Cut the curve at the X location'),
               ('SUBDIV', 'Subdivide', 'Subdivide the curve at N subdivisions levels'),
               ('PROJECT', 'Project', "Subdivide the chosen curve for every projected anchor of the reference curve along their relative tangent distance"),
               ),
        default='SUBDIV',
        update=lambda self, context: self.update_trigger()
        )
    subdiv_level : bpy.props.IntProperty(
        name="Level",
        description="The number of subdivisions to perform",
        default=1,
        min=1,
        soft_max=3,
        update=lambda self, context: self.update_trigger()
        )
    xloc : bpy.props.FloatProperty(
        name="X Location",
        description="The X location to cut the curve at",
        default=0.0,
        soft_min=-2.0,
        soft_max=2.0,
        update=lambda self, context: self.update_trigger()
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        self.inputs.new('NodeBoosterCustomSocketInterpolation', "2D Curve")
        self.outputs.new('NodeBoosterCustomSocketInterpolation', "2D Curve")

        self.inputs.new('NodeBoosterCustomSocketInterpolation', "Reference Curve")
        self.inputs[1].enabled = False

        self.width = 145

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        return None

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            match self.mode:
                case 'SUBDIV':  return 'Subdivide'
                case 'CUT':     return 'Subdivide Cut'
                case 'PROJECT': return 'Subdivide Project'
        return self.label

    def update_trigger(self,):
        """send an update trigger to the whole node_tree"""

        if (self.mode in {'SUBDIV', 'CUT'}):
            self.inputs[0].name = '2D Curve'
            self.inputs[1].enabled = False
        elif (self.mode == 'PROJECT'):
            self.inputs[0].name = 'To Subdivide'
            self.inputs[1].enabled = True

        send_refresh_signal(self.outputs[0])

        return None

    def evaluator(self, socket_output)->None:
        """evaluator the node required for the output evaluator"""

        if (self.mode in {'SUBDIV', 'CUT'}):

            val = evaluate_upstream_value(self.inputs[0],
                match_evaluator_properties={'INTERPOLATION_NODE',},
                set_link_invalid=True,
                )

            if (val is None):
                return None

            match self.mode:

                case 'SUBDIV':
                    for _ in range(self.subdiv_level):
                        t_map = np.full(len(val), 0.5)
                        val = casteljau_subdiv_bezsegs(val, t_map)
                        continue
                    return val

                case 'CUT':
                    return cut_bezsegs(val, self.xloc, sampling_rate=100,)

        elif (self.mode == 'PROJECT'):
            
            val1 = evaluate_upstream_value(self.inputs[0],
                match_evaluator_properties={'INTERPOLATION_NODE',},
                set_link_invalid=True,
                )
            val2 = evaluate_upstream_value(self.inputs[1],
                match_evaluator_properties={'INTERPOLATION_NODE',},
                set_link_invalid=True,
                )
            if (val1 is None) or (val2 is None):
                return None

            return subdiv_project_bezsegs(val1, val2)

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, "mode", text="",)
        match self.mode:
            case 'CUT':
                layout.prop(self, "xloc")
            case 'SUBDIV':
                layout.prop(self, "subdiv_level")
            case 'PROJECT':
                pass

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

        # header, panel = layout.panel("dev_panelid", default_closed=True,)
        # header.label(text="Development",)
        # if (panel):
        #     panel.active = False

        #     col = panel.column(align=True)
        #     col.label(text="NodeTree:")
        #     col.template_ID(n, "node_tree")

        return None
