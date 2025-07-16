# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import os
import numpy as np

from ...utils.bezier2d_utils import reverseengineer_curvemapping_to_bezsegs
from ...utils.str_utils import word_wrap # Added for draw_panel
from ...utils.node_utils import (
    send_refresh_signal,
    cache_booster_nodes_parent_tree,
    )


class NODEBOOSTER_ND_2DCurveInput(bpy.types.Node):

    bl_idname = "NodeBooster2DCurveInput" 
    bl_label = "2D Curve Input"
    bl_description = "Interpret a spline of a 3D curve object into a 2D curve depending on the chosen axis."
    auto_upd_flags = {'NONE',}
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

        self.outputs.new('NodeBoosterCustomSocketInterpolation', "2D Curve")

        self.width = 150

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        return None

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def update_trigger(self,):
        """send an update trigger to the whole node_tree"""

        send_refresh_signal(self.outputs[0])

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return '2D Curve'
        return self.label

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

