# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import reverseengineer_curvemapping_to_bezsegs
from ...utils.node_utils import (
    import_new_nodegroup, 
    send_refresh_signal,
    cache_booster_nodes_parent_tree,
)

# TODO
# - IMPORTANT: Support hidden blender feature:
#   - Either the interpolation graph is in 'Extend extrapolated' or in 'Extend horizontal'... 
#     need to support this.. how? 
#   - Could simply create two new segment if in horizontal mode, that's it would work.
# - Lifeupdate feature: Add a EnumOperator that apply various presets.
# - No update button. Automatic update on graph interaction with graph. 
#   How? which callback? will msgbus work for once? ehm..
#   Could store a cache of numpy hash in the node, and check if new graph val is same.

class NODEBOOSTER_OT_interpolation_input_update(bpy.types.Operator):
    """Update the interpolation output. Cheap trick: we unlink and relink"""
    
    bl_idname = "nodebooster.update_interpolation"
    bl_label = "Update Interpolation"
    bl_description = "Apply the new graph values"
    bl_options = {'REGISTER', 'INTERNAL'}

    node_name : bpy.props.StringProperty()

    def execute(self, context):
        context.space_data.edit_tree.nodes[self.node_name].update_trigger()
        return {'FINISHED'}

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterInterpolationInput"
    bl_label = "Interpolation Input"
    bl_description = """Create a 2D curve from an interpolation curve mapping graph"""
    auto_upd_flags = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    graph_type : bpy.props.EnumProperty(
        name="Graph Type",
        description="Which kind of data do we process ?",
        items=[
            ("float_mapping", "Unsigned Values", "Delimit your graph to unsigned values, ranging from 0 to 1"),
            ("vector_mapping", "Signed Values", "Delimit your graph to signed values, ranging from -1 to 1"),
            ],
        default="float_mapping",
        update=lambda self, context: self.update_trigger(),
        ) #item names are name of internal nodes as well.

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):

            # NOTE we cannot create a new ng with custom socket types for now unfortunately.
            # it's possible to do it with the link_drag operator on a socketcustom to the grey 
            # input/output sockets of a ng, but not via the python API.
            # see notes in 'node_utils.create_ng_socket'. This solution is a workaround, hopefully, temporary..
            blendfile = os.path.join(os.path.dirname(__file__), "interpolation_nodegroups.blend")
            ng = import_new_nodegroup(blendpath=blendfile, ngname=self.bl_idname,)

            # set the name of the ng
            ng.name = name

        
        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

        self.width = 240

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

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Interpolation'
        return self.label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, 'graph_type', text="")

        data = self.node_tree.nodes[self.graph_type]
        layout.template_curve_mapping(data, "mapping", type='NONE',)

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("nodebooster.update_interpolation", text="Apply",).node_name = self.name

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:

            panel.prop(self, 'graph_type', text="")

            data = self.node_tree.nodes[self.graph_type]
            panel.template_curve_mapping(data, "mapping", type='NONE',)
            panel.operator("nodebooster.update_interpolation", text="Apply",).node_name = self.name
            panel.separator(factor=0.3)

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

    def update_trigger(self,):
        """send an update trigger to the whole node_tree"""

        send_refresh_signal(self.outputs[0])

        return None

    def evaluator(self, socket_output)->list: 
        """evaluator the node required for the output evaluator"""

        # NOTE the evaluator works based on socket output passed in args. 
        # but here, there's only one output..(simpler)

        result = reverseengineer_curvemapping_to_bezsegs(self.node_tree.nodes[self.graph_type].mapping.curves[0])

        return result

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_InterpolationInput(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNodeNodeBoosterInterpolationInput"

class NODEBOOSTER_NG_SH_InterpolationInput(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNodeNodeBoosterInterpolationInput"

class NODEBOOSTER_NG_CP_InterpolationInput(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNodeNodeBoosterInterpolationInput"
