# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os
import numpy as np

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import extend_bezsegs
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    send_refresh_signal,
)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 


class NODEBOOSTER_ND_2DCurveExtend(bpy.types.Node):

    bl_idname = "NodeBooster2DCurveExtend"
    bl_label = "Extend 2D Curve"
    bl_description = """Extend a 2D curve at a specific X location."""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="The mode to use for the extension",
        items=(('HANDLE', 'Segment', 'Extend the curve as the continuation of the last segment'),
               ('HORIZONTAL', 'Horizontal', 'Extend the curve horizontally'),
              ),
        default='HANDLE',
        update=lambda self, context: self.update_trigger()
        )
    xloc : bpy.props.FloatProperty(
        name="Location",
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

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        return None

    def update(self):
        """generic update function"""
        
        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Extend'
        return self.label

    def update_trigger(self,):
        """send an update trigger to the whole node_tree"""

        send_refresh_signal(self.outputs[0])

        return None

    def evaluator(self, socket_output)->None:
        """evaluator the node required for the output evaluator"""

        val = evaluate_upstream_value(self.inputs[0],
            match_evaluator_properties={'INTERPOLATION_NODE',},
            set_link_invalid=True,
            )
        if (val is None):
            return None

        return extend_bezsegs(val, self.xloc, mode=self.mode,)

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, "mode", text="",)
        layout.prop(self, "xloc")

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
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free"

        # header, panel = layout.panel("dev_panelid", default_closed=True,)
        # header.label(text="Development",)
        # if (panel):
        #     panel.active = False

        #     col = panel.column(align=True)
        #     col.label(text="NodeTree:")
        #     col.template_ID(n, "node_tree")

        return None
