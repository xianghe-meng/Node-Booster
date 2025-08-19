# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import bezsegs_to_curvemapping, reset_curvemapping
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    import_new_nodegroup, 
    set_node_socketattr,
    set_all_sockets_enabled,
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

    bl_idname = "NodeBoosterInterpolationRemap"
    bl_label = "Interpolation Remap"
    bl_description = """Remap values from a chosen interpolation curve."""
    auto_upd_flags = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_OUTPUT',}

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="Which kind of data do we process ?",
        default='FLOAT',
        items=(('FLOAT', "Float", "Float interpolation"),
               ('VECTOR', "Vector", "Vector interpolation"),),
        update= lambda self, context: self.update(),
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

        self.width = 160

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
        self.evaluator()

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Remap Values'
        return self.label

    def evaluator(self,)->None:
        """evaluator the node required for the output evaluator"""
        
        set_all_sockets_enabled(self, inputs=True, outputs=True) #reset all sockets enabled status

        #1: We make some sockets invisible depending on user mode and tree type

        # NOTE commented out. normally remap node has no factor option.
        # match self.tree_type:
        #     case 'GeometryNodeTree' | 'ShaderNodeTree':
        #         set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=True, in_out='INPUT',)
        #     case 'CompositorNodeTree':
        #         if (self.mode == "VECTOR"):
        #               set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=False, in_out='INPUT',)
        #         else: set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=True, in_out='INPUT',)
        set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=False, in_out='INPUT',)

        #hide some sockets depending on the mode
        match self.mode:

            case "FLOAT":
                set_node_socketattr(self, socket_name="Interpolation", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation X", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Y", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Z", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=True, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='OUTPUT',)
                self.inputs[6].enabled = True
                self.inputs[7].enabled = True
                self.inputs[8].enabled = True
                self.inputs[9].enabled = True
                self.inputs[11].enabled = False
                self.inputs[12].enabled = False
                self.inputs[13].enabled = False
                self.inputs[14].enabled = False
                
                sock_to_evaluate = {
                    'Interpolation':self.node_tree.nodes['float_map'].mapping.curves[0],
                    }

            case "VECTOR":
                set_node_socketattr(self, socket_name="Interpolation", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation X", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Y", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Z", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=True, in_out='OUTPUT',)
                self.inputs[6].enabled = False
                self.inputs[7].enabled = False
                self.inputs[8].enabled = False
                self.inputs[9].enabled = False
                self.inputs[11].enabled = True
                self.inputs[12].enabled = True
                self.inputs[13].enabled = True
                self.inputs[14].enabled = True
            
                sock_to_evaluate = {
                    'Interpolation X':self.node_tree.nodes['vector_map'].mapping.curves[0],
                    'Interpolation Y':self.node_tree.nodes['vector_map'].mapping.curves[1],
                    'Interpolation Z':self.node_tree.nodes['vector_map'].mapping.curves[2],
                    }

        #get all nodes connected to the value socket
        cache = {}
        for k,c in sock_to_evaluate.items():
            sock = self.inputs[k]
            # retrieve the value from the node behind.
            # the node might do a similar operation, and so on.
            val = evaluate_upstream_value(sock,
                match_evaluator_properties={'INTERPOLATION_NODE',},
                set_link_invalid=True,
                cached_values=cache,
                )
            # if the evaluator system failed to retrieve a value, we reset the curve to default..
            # else we set the points.
            if (val is None):
                  reset_curvemapping(c)
            else: bezsegs_to_curvemapping(c, val)
            continue

        # NOTE unfortunately python API for curve mapping is meh..
        # we need to send an update trigger. Maybe there's a solution for this?.
        for nd in self.node_tree.nodes:
            if nd.name in {'float_map', 'vector_map'}:
                #send a hard refresh trigger. 
                nd.mapping.update()
                nd.mute = not nd.mute
                nd.mute = not nd.mute
                nd.update()
                continue

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, 'mode' ,text="")
        
        col = layout.column().box()
        word_wrap(layout=col, alert=False, active=True, max_char=self.width/6.65, 
            string="Geometry-Node is not very tolerent to unrecognized sockets currently, see PR #136968.",
            )

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:

            panel.prop(self, 'mode', text="")

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


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_InterpolationRemap(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNodeNodeBoosterInterpolationRemap"

class NODEBOOSTER_NG_SH_InterpolationRemap(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNodeNodeBoosterInterpolationRemap"

class NODEBOOSTER_NG_CP_InterpolationRemap(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNodeNodeBoosterInterpolationRemap"
