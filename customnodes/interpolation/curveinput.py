# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import numpy as np

from ...utils.interpolation_utils import reverseengineer_curvemapping_to_bezsegs
from ...utils.str_utils import word_wrap # Added for draw_panel
from ...utils.node_utils import (
    import_new_nodegroup,
    )

class Base():

    bl_idname = "NodeBoosterInterpolationCurveObject" 
    bl_label = "2D Curve"
    bl_description = "Generates 2D curve data from a 3D Curve Object's axis."
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    evaluator_properties = {'INTERPOLATION_NODE',}

    curve_object: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Curve Object",
        description="Select the 3D Curve object to sample",
        poll=lambda self, object: object.type == 'CURVE', 
        update=lambda self, context: self.update_trigger()
        )
    axis_source: bpy.props.EnumProperty(
        items=[
            ('X', 'X', 'Use world X axis for Y value'),
            ('Y', 'Y', 'Use world Y axis for Y value'),
            ('Z', 'Z', 'Use world Z axis for Y value')
            ],
        name="Source Axis",
        description="Which axis of the 3D curve points maps to the 2D curve's Y value",
        default='Z',
        update=lambda self, context: self.update_trigger()
        )
    spline_index: bpy.props.IntProperty(
        name="Spline Index",
        description="Index of the spline to use within the curve object",
        default=0,
        min=0,
        update=lambda self, context: self.update_trigger()
        )
    space: bpy.props.EnumProperty(
        name="Space",
        description="Evaluate curve points in Local (Original) or World (Relative) space",
        items=[
            ('LOCAL', 'Original', 'Use curve points relative to the object origin'),
            ('WORLD', 'Relative', 'Use curve points in world space')
            ],
        default='LOCAL',
        update=lambda self, context: self.update_trigger()
        )

    @classmethod
    def poll(cls, context):
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
        self.width = 150
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None

    def update(self):
        """generic update function"""

        return None

    def update_trigger(self,):
        """send an update trigger by unlinking and relinking"""

        out = self.outputs[0]
        if (not out.links):
            return {'FINISHED'} 

        links_data = []
        for link in out.links:
            links_data.append((link.to_socket, link.to_node))
        
        # Get the node tree the node belongs to
        node_tree = self.id_data 
        if not hasattr(node_tree, 'links'):
             print(f"Error: Could not access links from {type(node_tree)}")
             return None
        
        # Perform unlink/relink
        links_to_remove = list(out.links)
        for link in links_to_remove:
            node_tree.links.remove(link)
        
        for to_socket, to_node in links_data:
            node_tree.links.new(out, to_socket)

        return None

    def draw_buttons(self, context, layout):
    
        layout.prop(self, "curve_object", text="")
        
        # Check if spline_index is valid and set alert if not
        alert_spline = False
        curve_obj = self.curve_object
        if curve_obj and curve_obj.type == 'CURVE' and curve_obj.data.splines:
            if self.spline_index >= len(curve_obj.data.splines):
                alert_spline = True
        elif curve_obj and curve_obj.type == 'CURVE' and not curve_obj.data.splines:
             alert_spline = True # No splines exist, so index 0 is invalid
            
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        coll = col.column(align=True)
        coll.alert = alert_spline # Set alert state for the col
        coll.prop(self, "spline_index", text="Spline")
        col.prop(self, "axis_source", text="Axis")

        row = layout.row(align=True)
        row.prop(self, "space", expand=True)

    def draw_panel(self, layout, context):
        pass

    def evaluator(self, socket_output)->list:

        curve_obj = self.curve_object
        if (not curve_obj or curve_obj.type != 'CURVE'):
            return None

        curve_data = curve_obj.data
        if (not curve_data.splines or self.spline_index >= len(curve_data.splines)):
            return None

        spline = curve_data.splines[self.spline_index]

        if (spline.type != 'BEZIER' or not spline.bezier_points):
            print(f"Warning: Spline {self.spline_index} in '{curve_obj.name}' is not a Bezier spline. Cannot extract handle data.")
            return None

        bezier_points = spline.bezier_points
        if (len(bezier_points) < 2):
            return None

        # Get the transformation matrix based on selected space
        transform_matrix = curve_obj.matrix_world if (self.space == 'WORLD') else None

        # Determine which axes map to 2D X and Y
        match self.axis_source:
            case 'X': idx_2d_x, idx_2d_y = 1, 2 # Use World Y, Z
            case 'Y': idx_2d_x, idx_2d_y = 0, 2 # Use World X, Z
            case 'Z': idx_2d_x, idx_2d_y = 0, 1 # Use World X, Y

        # Build Bezier Segment Array Directly
        bezsegs_list = []
        num_segments = len(bezier_points) - 1
        for i in range(num_segments):
            bp_i = bezier_points[i]
            bp_i1 = bezier_points[i+1]

            # Get the 4 relevant 3D world-space points for the segment
            P0_3d = bp_i.co
            P1_3d = bp_i.handle_right
            P2_3d = bp_i1.handle_left
            P3_3d = bp_i1.co

            # Apply transform if needed
            if (transform_matrix):
                P0_3d = transform_matrix @ P0_3d
                P1_3d = transform_matrix @ P1_3d
                P2_3d = transform_matrix @ P2_3d
                P3_3d = transform_matrix @ P3_3d

            # Extract the chosen 2 axes for each point
            P0 = np.array([P0_3d[idx_2d_x], P0_3d[idx_2d_y]])
            P1 = np.array([P1_3d[idx_2d_x], P1_3d[idx_2d_y]])
            P2 = np.array([P2_3d[idx_2d_x], P2_3d[idx_2d_y]])
            P3 = np.array([P3_3d[idx_2d_x], P3_3d[idx_2d_y]])

            segment = np.concatenate((P0, P1, P2, P3))
            bezsegs_list.append(segment)
            
            continue

        if (not bezsegs_list):
             return None
        return np.array(bezsegs_list, dtype=float)


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_2DCurve(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNodeNodeBooster2DCurve"

class NODEBOOSTER_NG_SH_2DCurve(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNodeNodeBooster2DCurve"

class NODEBOOSTER_NG_CP_2DCurve(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNodeNodeBooster2DCurve"
