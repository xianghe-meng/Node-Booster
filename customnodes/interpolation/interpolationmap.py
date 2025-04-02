# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 
import os

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.curve_utils import points_to_curve, reset_curve
from ...utils.node_utils import (
    import_new_nodegroup, 
    set_node_socketattr,
    get_node_socket_by_name,
    set_node_socketattr,
    parcour_node_tree,
)


# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterInterpolationMap"
    bl_label = "Interpolated Map"
    bl_description = """Map a value to an interpolation curve. Similar to the 'Curve Mapping' node."""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    # NOTE this node is the end of the line for our a socket type, 
    # it has a special evaluator responsability for socket.nodebooster_socket_type == 'INTERPOLATION'.
    evaluator_properties = {'INTERPOLATION_OUTPUT',}

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="Which kind of data do we process ?",
        items=[
            ("FLOAT", "Float", "Float interpolation"),
            ("COLOR", "Color", "Color interpolation"),
            ("VECTOR", "Vector", "Vector interpolation"),
            ],
        default="FLOAT",
        update= lambda self, context: self.evaluator(),
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
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None

    def update(self):
        """generic update function"""
        
        print("DEBUG: InterpolationMap update")
        self.evaluator()
        
        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def evaluator(self,)->None:
        """evaluator the node required for the output evaluator"""

        #compositor node has no factor socket for vector curves for some reasons.
        match self.tree_type:
            case 'GeometryNodeTree' | 'ShaderNodeTree':
                set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=True, in_out='INPUT',)
            case 'CompositorNodeTree':
                if (self.mode == "VECTOR"):
                      set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='INPUT',)
                else: set_node_socketattr(self, socket_name="Factor", attribute='enabled', value=True, in_out='INPUT',)

        #hide some sockets depending on the mode
        match self.mode:

            case "FLOAT":
                set_node_socketattr(self, socket_name="Interpolation", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation X", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Y", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Z", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation C", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation R", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation G", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation B", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=True, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=False, in_out='OUTPUT',)

                value_socket = get_node_socket_by_name(self, socket_name="Float", in_out='INPUT',)
                interp_sockets = {
                    'Interpolation':self.node_tree.nodes['float_map'].mapping.curves[0],
                    }

            case "VECTOR":
                set_node_socketattr(self, socket_name="Interpolation", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation X", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Y", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Z", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation C", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation R", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation G", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation B", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=True, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=False, in_out='OUTPUT',)

                value_socket = get_node_socket_by_name(self, socket_name="Vector", in_out='INPUT',)
                interp_sockets = {
                    'Interpolation X':self.node_tree.nodes['vector_map'].mapping.curves[0],
                    'Interpolation Y':self.node_tree.nodes['vector_map'].mapping.curves[1],
                    'Interpolation Z':self.node_tree.nodes['vector_map'].mapping.curves[2],
                    }

            case "COLOR":
                set_node_socketattr(self, socket_name="Interpolation", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation X", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Y", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation Z", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation C", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation R", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation G", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Interpolation B", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Float", attribute='enabled', value=False, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Vector", attribute='enabled', value=False, in_out='OUTPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=True, in_out='INPUT',)
                set_node_socketattr(self, socket_name="Color", attribute='enabled', value=True, in_out='OUTPUT',)

                value_socket = get_node_socket_by_name(self, socket_name="Color", in_out='INPUT',)
                interp_sockets = {
                    'Interpolation C':self.node_tree.nodes['color_map'].mapping.curves[3],
                    'Interpolation R':self.node_tree.nodes['color_map'].mapping.curves[0],
                    'Interpolation G':self.node_tree.nodes['color_map'].mapping.curves[1],
                    'Interpolation B':self.node_tree.nodes['color_map'].mapping.curves[2],
                    }

        # Nodetree evaluator logic:
        # we need to evaluate the curve interpolation data, and feed it to our curve mapping node.

        already_calculated = {}
        
        #get all nodes connected to the value socket
        for k,c in interp_sockets.items():
            sock = self.inputs[k]

            #nothing links?
            if (not sock.links):
                reset_curve(c)
                continue

            #get colliding nodes on the left in {socket:links}
            parcour_info = parcour_node_tree(self.node_tree.nodes, sock, direction='LEFT')
            print(f"DEBUG: parcour_info: {parcour_info}, len: {len(parcour_info)}")

            #nothing hit?
            if (len(parcour_info)==0):
                print("DEBUG: no parcour info. resetting curve.")
                reset_curve(c)
                continue

            #get our colliding socket. when parcouring right to left, we expect only one collision.
            assert len(parcour_info) == 1, f"It should not be possible to collide with more than one socket type, when parcouring from right to left. how did you manage that?\n{parcour_info}"

            # Extract the first (and only) item from the dictionary
            colliding_socket = list(parcour_info.keys())[0]
            colliding_node = colliding_socket.node
            parcoured_links = parcour_info[colliding_socket]

            #we are expecting to collide with specific socket types!
            if not hasattr(colliding_node,'evaluator_properties') \
               or ('INTERPOLATION_NODE' not in colliding_node.evaluator_properties):
                print("DEBUG: parcour not successful. resetting curve.")
                reset_curve(c)
                first_link = parcoured_links[0]
                first_link.is_valid = False
                continue

            #the interpolation socket type always return a list of points.
            if (colliding_node.name in already_calculated):
                  pts = already_calculated[colliding_node.name]
            else: pts = colliding_node.evaluator(colliding_socket)
            points_to_curve(c, pts)
            already_calculated[colliding_node.name] = pts
            continue
        
        # NOTE unfortunately python API for curve mapping is meh..
        # we need to send an update trigger. Maybe there's a solution for this?.
        for nd in self.node_tree.nodes:
            if nd.name in {'float_map', 'vector_map', 'color_map'}:
                nd.mapping.update()
                nd.update()
                continue

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        layout.prop(self, 'mode' ,text="")

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
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free"

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

class NODEBOOSTER_NG_GN_InterpolationMap(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNodeNodeBoosterInterpolationMap"

class NODEBOOSTER_NG_SH_InterpolationMap(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNodeNodeBoosterInterpolationMap"

class NODEBOOSTER_NG_CP_InterpolationMap(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNodeNodeBoosterInterpolationMap"
