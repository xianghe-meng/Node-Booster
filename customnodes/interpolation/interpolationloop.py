# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os
import numpy as np

from ... import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import looped_offset_bezsegs
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    send_refresh_signal,
)


#TODO IMPORTANT:
# - fix when cut occurs right in a anchor. will create a None graph suddenly.. see todo in 'looped_offset_bezsegs'
# - we'll need to improve the evaluation system for supporting animation mode

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 


class NODEBOOSTER_ND_InterpolationLoop(bpy.types.Node):

    bl_idname = "NodeBooster2DCurveLoop"
    bl_label = "Loop Interpolation"
    bl_description = """Loop an interpolation 2D curve from a given offset or speed. If the passed 2D curve is not monotonic, we'll make it monotonic first."""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="Loop an interpolation 2D curve from a given offset or speed.",
        items=(('OFFSET', 'Offset', 'Loop-Offset the curve by a given amount'),
               ('ANIMATION', 'Animation', 'Loop an animation curve'),
              ),
        default='OFFSET',
        update=lambda self, context: self.update_trigger()
        )
    offset : bpy.props.FloatProperty(
        name="Offset",
        description="The offset to loop the curve by",
        default=0.0,
        update=lambda self, context: self.update_trigger()
        )
    speed : bpy.props.FloatProperty(
        name="Speed",
        description="The speed to loop the curve at, scaling the current framerate",
        default=1.0,
        soft_min=-10.0,
        soft_max=10.0,
        update=lambda self, context: self.update_trigger()
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        self.inputs.new('NodeBoosterCustomSocketInterpolation', "Interpolation")
        self.outputs.new('NodeBoosterCustomSocketInterpolation', "Interpolation")

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
            return 'Loop'
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
        
        match self.mode:
            case 'OFFSET':
                offset = self.offset
            case 'ANIMATION':
                offset = self.speed * (bpy.context.scene.frame_current / bpy.context.scene.render.fps)

        return looped_offset_bezsegs(val, offset=offset)

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, "mode", text="",)
        if (self.mode == 'OFFSET'):
              layout.prop(self, "offset")
        else: layout.prop(self, "speed")

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
