# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.interpolation_utils import curvemapping_to_bezsegs
from ...utils.node_utils import (
    import_new_nodegroup, 
)

# TODO
# - Add a EnumOperator that apply various presets.
# - would be nice to get rid of the update operator and find a callback.
#   if so, which callback? will msgbus work for once? ehm..

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
    bl_label = "Interpolation"
    bl_description = """Create an interpolation socket type from a define curvegraph."""
    auto_update = {'NONE',}
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
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None

    def update(self):
        """generic update function"""

        return None

    def draw_label(self,):
        """node label"""

        return self.bl_label

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
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free"

        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False

            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")

        return None

    def update_trigger(self,):
        """send an update trigger by unlinking and relinking"""

        out = self.outputs[0]
        if (not out.links):
            return {'FINISHED'} 

        links_data = []
        for link in out.links:
            links_data.append((link.to_socket, link.to_node))
        
        for link in out.links:
            self.id_data.links.remove(link)
        
        for to_socket, to_node in links_data:
            self.id_data.links.new(out, to_socket)
    
        return None

    def evaluator(self, socket_output)->list: 
        """evaluator the node required for the output evaluator"""

        # NOTE the evaluator works based on socket output passed in args. 
        # but here, there's only one output..(simpler)

        result = curvemapping_to_bezsegs(self.node_tree.nodes[self.graph_type].mapping.curves[0])
        print("OUT:", result)
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
