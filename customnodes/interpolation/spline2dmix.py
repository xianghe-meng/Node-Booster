# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os
import numpy as np

from ... import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import lerp_bezsegs
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


class NODEBOOSTER_ND_2DCurvesMix(bpy.types.Node):

    bl_idname = "NodeBooster2DCurvesMix"
    bl_label = "Mix 2D Curves"
    bl_description = """Mix two 2D curves linearly. Ideally the numbers of segments should be similar. If not, we'll try to match them by subdividing more segments at projected locations."""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    mixfac: bpy.props.FloatProperty(
        name="Factor",
        default=0.5,
        min=0.0,
        max=1.0,
        step=0.01,
        update=lambda self, context: self.update_trigger(),
        )
    
    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        self.inputs.new('NodeBoosterCustomSocketInterpolation', "2D Curve")
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
            return 'Mix'
        return self.label

    def update_trigger(self,):
        """send an update trigger to the whole node_tree"""

        send_refresh_signal(self.outputs[0])

        return None

    def evaluator(self, socket_output)->None:
        """evaluator the node required for the output evaluator"""

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

        match self.mixfac:
            case 0.0: final = val1
            case 1.0: final = val2
            case _:   final = lerp_bezsegs(val1, val2, self.mixfac)
            
        return final

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, "mixfac")

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
