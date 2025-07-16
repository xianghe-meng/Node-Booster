# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
import os
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np
import math # Add math import for calculations

from ... import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.bezier2d_utils import (
    hash_bezsegs,
    sample_bezsegs,
)
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    import_new_nodegroup, 
    set_node_socketattr,
    get_node_socket_by_name,
    socket_intersections,
    cache_booster_nodes_parent_tree,
)

# TODO Interpolation graph:
# - Add option for Extend extrapolated. or Extend horizontal for fill preview..
# TODO GPU Drawing Improvements:
# IMPORTANT: 
# - f.CACHE for the fill calculation too. Too intensive right now.
#   Will need to calculate everything in local, and map to screen ath the end.
# - dpi scaling is not ok with graph.. disapear if resolution scale is above 1.33, why???
# BONUS:
# - Line width do not scale well with zoom
# - Would be nice to have some ideas of start and end anchor units.

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 


# NOTE for some reasons i was not able to store the numpy value 
# as a self.preview_data directly.. weird. So we store this in a global here..0
# dict keys will be the node name.
PREVIEW_DATA = {}

class NODEBOOSTER_ND_2DCurvePreview(bpy.types.Node):

    bl_idname = "NodeBooster2DCurvePreview"
    bl_label = "2D Curve Preview"
    bl_description = """Preview a 2D curve."""
    bl_width_min = 157
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    # NOTE this node is the end of the line for our a socket type, 
    # it has a special evaluator responsability for socket.nodebooster_socket_type == 'INTERPOLATION'.
    evaluator_properties = {'INTERPOLATION_OUTPUT',}

    preview_lock : bpy.props.BoolProperty(
        name="Preview Lock",
        description="Lock the preview scale with the width of the node",
        default=False,
        )
    preview_scale : bpy.props.EnumProperty(
        name="Graph Scale",
        description="How to fit the graph",
        items=(
            ('POS', "Positive", "Graph in 0/1 range"),
            ('NEG', "Negative", "Graph in -1/-1 range"),
            ('FIT', "Fit Curve", "Graph will fit the curve min/maxrange"),
            ('CUSTOM', "Custom", "Graph will use the custom bounds"),
            ),
        default='FIT',
        )
    draw_handles : bpy.props.BoolProperty(
        name="Handles",
        description="Draw the handles of the curve",
        default=False,
        )
    draw_fill : bpy.props.BoolProperty(
        name="Interpolation Fill",
        description="Draw the fill of the curve",
        default=False,
        )
    grid_tick : bpy.props.FloatProperty(
        name="Grid Tick",
        description="The tick of the grid",
        default=0.25,
        min=0.01,
        soft_max=1.0,
        )
    draw_grid : bpy.props.BoolProperty(
        name="Grid",
        description="Draw the grid of the curve",
        default=True,
        )
    draw_anchor : bpy.props.BoolProperty(
        name="Anchors",
        description="Draw the anchors of the curve",
        default=True,
        )
    draw_curve : bpy.props.BoolProperty(
        name="Curve",
        description="Draw the curve of the curve",
        default=True,
        )
    bounds_custom : bpy.props.FloatVectorProperty(
        name="Graph Bound",
        description="The bounds of the graph",
        default=(-1,0,1,1),
        soft_min=-10,
        soft_max=10,
        size=4,
        )
    bounds_fitcurve : bpy.props.FloatVectorProperty(
        name="Graph Bound",
        description="The bounds of the graph",
        default=(0,0,1,1), #Defined in evaluator()
        size=4,
        )
    bounds_positive : bpy.props.FloatVectorProperty(
        name="Graph Bound", #Informative purpose for user
        description="The bounds of the graph",
        default=(0,0,1,1),
        size=4,
        )
    bounds_negative : bpy.props.FloatVectorProperty(
        name="Graph Bound", #Informative purpose for user
        description="The bounds of the graph",
        default=(-1,-1,1,1),
        size=4,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        self.inputs.new('NodeBoosterCustomSocketInterpolation', "2D Curve")

        self.width = 240

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        return None

    def update(self):
        """generic update function"""
        
        cache_booster_nodes_parent_tree(self.id_data)
        self.evaluator()

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Preview'
        return self.label

    def evaluator(self,)->None:
        """evaluator the node required for the output evaluator"""

        result = evaluate_upstream_value(self.inputs[0],
            match_evaluator_properties={'INTERPOLATION_NODE',},
            set_link_invalid=True,
            )

        # Find the bounds of the curve data to fit it in the view. Store this info in the node properties.
        if (result is not None) and (isinstance(result, np.ndarray)) and (result.size > 0):
            
            # Extract x and y coordinates from bezier segments
            curvepts = sample_bezsegs(result, 100)
            x_coords = curvepts[:, 0]  # Extract x coordinates
            y_coords = curvepts[:, 1]  # Extract y coordinates

            # Calculate min/max with small padding
            x_min, x_max = np.min(x_coords), np.max(x_coords)
            y_min, y_max = np.min(y_coords), np.max(y_coords)

            # Add 5% padding
            padding = 0.15
            x_pad = (x_max - x_min) * padding
            y_pad = (y_max - y_min) * padding

            # Ensure we have some minimum bounds even for flat curves
            x_pad = max(x_pad, 0.1)
            y_pad = max(y_pad, 0.1)
            
            self.bounds_fitcurve = (
                x_min - x_pad,
                y_min - y_pad,
                x_max + x_pad,
                y_max + y_pad,
                )

        # Store the result in this preview data dict.
        PREVIEW_DATA[f"Preview{self.name}"] = result

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row(align=True)

        roww = row.row(align=True)
        roww.alignment = 'LEFT'

        roww = row.row(align=True)
        roww.alignment = 'RIGHT'
        roww.context_pointer_set("pass_nodecontext", self)
        roww.popover("NODEBOOSTER_PT_2DCurvePreviewOptions", text="", icon='OPTIONS')
        roww.prop(self, 'preview_scale', text="",)
        roww.prop(self, 'preview_lock', text="", icon='LOCKED' if self.preview_lock else 'UNLOCKED')

        layout.separator(factor=self.width/5.5 if self.preview_lock else 35.0)

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


class NODEBOOSTER_PT_2DCurvePreviewOptions(bpy.types.Panel):

    bl_idname      = "NODEBOOSTER_PT_2DCurvePreviewOptions"
    bl_label       = "Draw Preferences"
    bl_description = "Choose how to draw your preview"
    bl_category    = ""
    bl_space_type  = "NODE_EDITOR"
    bl_region_type = "HEADER" #Hide this panel? not sure how to hide them...

    def draw(self, context):
        layout = self.layout
        node = context.pass_nodecontext
        
        col = layout.column(align=True, heading="Drawing")
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(node, 'draw_curve')
        col.prop(node, 'draw_fill')
        col.prop(node, 'draw_anchor')
        col.prop(node, 'draw_handles')
        col.prop(node, 'draw_grid')

        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.active = node.draw_grid
        col.prop(node, 'grid_tick')

        layout.separator(type='LINE')

        col = layout.column(heading="Bounds")
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(node, 'preview_scale', expand=True,)

        match node.preview_scale:
            case 'CUSTOM': data = 'bounds_custom'   ; enabled = True
            case 'POS':    data = 'bounds_positive' ; enabled = False
            case 'NEG':    data = 'bounds_negative' ; enabled = False
            case 'FIT':    data = 'bounds_fitcurve' ; enabled = False

        subcol = col.column(align=True)
        subcol.enabled = enabled
        subcol.prop(node,data, index=0, text="Start")
        subcol.prop(node,data, index=1, text=" ")

        subcol = col.column(align=True)
        subcol.enabled = enabled
        subcol.prop(node,data, index=2, text="End")
        subcol.prop(node,data, index=3, text=" ")

        return None

#   .oooooo.                           
#  d8P'  `Y8b                          
# 888           oo.ooooo.  oooo  oooo  
# 888            888' `88b `888  `888  
# 888     ooooo  888   888  888   888  
# `88.    .88'   888   888  888   888  
#  `Y8bood8P'    888bod8P'  `V88V"V8P' 
#                888                   
#               o888o                  


def draw_rectangle(shader, view2d, location, dimensions,
    bounds=((0.0,0.0),(1.0,1.0)), tick_interval=0.25,
    rectangle_color=(0.0, 0.0, 0.0, 0.3), 
    grid_color=(0.5, 0.5, 0.5, 0.05), grid_line_width=1.0,
    axis_color=(0.8, 0.8, 0.8, 0.15), axis_line_width=2.0,
    border_color=(0.1, 0.1, 0.1, 0.5), border_width=1.0,
    draw_grid=True, dpi=1.0, zoom=1.0):
    """Draw transparent black box with grid, axes, and border, mapping data bounds to the box."""

    nlocx, nlocy = location
    ndimx, ndimy = dimensions

    # Convert to screen space
    x1, y1 = view2d.view_to_region(nlocx, nlocy, clip=False)
    x2, y2 = view2d.view_to_region(nlocx + ndimx, nlocy, clip=False)
    x3, y3 = view2d.view_to_region(nlocx + ndimx, nlocy - ndimy, clip=False)
    x4, y4 = view2d.view_to_region(nlocx, nlocy - ndimy, clip=False)

    # Draw simple rectangle
    vertices = [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    indices = [(0,1,2), (0,2,3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.uniform_float("color", rectangle_color)
    batch.draw(shader)

    if (bounds is not None):

        x_min, x_max = bounds[0][0], bounds[1][0]
        y_min, y_max = bounds[0][1], bounds[1][1]

        # Raw Grid Lines
        screen_width = x2 - x1
        screen_height = y1 - y4 # Assuming y1 > y4 (top > bottom)
        data_width = x_max - x_min
        data_height = y_max - y_min

        # Small epsilon for floating point comparison near zero
        epsilon = 1e-6 

        # Helper to map data value to screen coordinate
        def map_x_to_screen(data_x):
            if abs(data_width) < epsilon: return x1 # Avoid division by zero
            return x1 + ((data_x - x_min) / data_width) * screen_width
        
        def map_y_to_screen(data_y):
            if abs(data_height) < epsilon: return y4 # Avoid division by zero
            return y4 + ((data_y - y_min) / data_height) * screen_height # Map from bottom (y4) up

        # Calculate scaled line widths
        scaled_grid_width = grid_line_width * dpi * zoom
        scaled_axis_width = axis_line_width * dpi * zoom

        # Vertical Grid Lines (X ticks)
        if (draw_grid):
            if (abs(data_width) > epsilon) and (tick_interval > epsilon) and (scaled_grid_width > 0):
                start_x_tick = math.ceil(x_min / tick_interval) * tick_interval
                current_x_tick = start_x_tick
                while current_x_tick <= x_max + epsilon:
                    # Skip zero axis (drawn separately) and boundary lines if they are zero
                    if abs(current_x_tick) < epsilon or \
                    (abs(x_min) < epsilon and abs(current_x_tick - x_min) < epsilon) or \
                    (abs(x_max) < epsilon and abs(current_x_tick - x_max) < epsilon):
                        current_x_tick += tick_interval
                        continue

                    x_pos = map_x_to_screen(current_x_tick)
                    v_vertices = [(x_pos, y1), (x_pos, y4)]
                    batch = batch_for_shader(shader, 'LINES', {"pos": v_vertices})
                    gpu.state.line_width_set(scaled_grid_width)
                    shader.uniform_float("color", grid_color)
                    batch.draw(shader)
                    gpu.state.line_width_set(1.0) # Reset
                    current_x_tick += tick_interval
                    continue

        # Horizontal Grid Lines (Y ticks)
        if (draw_grid):
            if (abs(data_height) > epsilon) and (tick_interval > epsilon) and (scaled_grid_width > 0):
                start_y_tick = math.ceil(y_min / tick_interval) * tick_interval
                current_y_tick = start_y_tick
                while current_y_tick <= y_max + epsilon:
                    # Skip zero axis (drawn separately) and boundary lines if they are zero
                    if abs(current_y_tick) < epsilon or \
                    (abs(y_min) < epsilon and abs(current_y_tick - y_min) < epsilon) or \
                    (abs(y_max) < epsilon and abs(current_y_tick - y_max) < epsilon):
                        current_y_tick += tick_interval
                        continue

                    y_pos = map_y_to_screen(current_y_tick)
                    h_vertices = [(x1, y_pos), (x2, y_pos)]
                    batch = batch_for_shader(shader, 'LINES', {"pos": h_vertices})
                    gpu.state.line_width_set(scaled_grid_width)
                    shader.uniform_float("color", grid_color)
                    batch.draw(shader)
                    gpu.state.line_width_set(1.0) # Reset
                    current_y_tick += tick_interval
                    continue

        # Draw Y Axis (X=0)
        if (scaled_axis_width > 0) and (x_min < -epsilon) and (x_max > epsilon):
            x_pos_zero = map_x_to_screen(0.0)
            axis_vertices = [(x_pos_zero, y1), (x_pos_zero, y4)]
            batch = batch_for_shader(shader, 'LINES', {"pos": axis_vertices})
            gpu.state.line_width_set(scaled_axis_width)
            shader.uniform_float("color", axis_color)
            batch.draw(shader)
            gpu.state.line_width_set(1.0) # Reset

        # Draw X Axis (Y=0)
        if (scaled_axis_width > 0) and (y_min < -epsilon) and (y_max > epsilon):
            y_pos_zero = map_y_to_screen(0.0)
            axis_vertices = [(x1, y_pos_zero), (x2, y_pos_zero)]
            batch = batch_for_shader(shader, 'LINES', {"pos": axis_vertices})
            gpu.state.line_width_set(scaled_axis_width)
            shader.uniform_float("color", axis_color)
            batch.draw(shader)
            gpu.state.line_width_set(1.0) # Reset

    # Draw Border
    scaled_border_width = border_width * dpi * zoom
    if (scaled_border_width > 0) and (border_color is not None):
         border_indices = [(0, 1), (1, 2), (2, 3), (3, 0)]
         border_batch = batch_for_shader(shader, 'LINES', {"pos": vertices}, indices=border_indices)
         gpu.state.line_width_set(scaled_border_width)
         shader.uniform_float("color", border_color)
         border_batch.draw(shader)
         gpu.state.line_width_set(1.0) # Reset

    return vertices


def draw_bezpoints(shader, recverts, bezsegs,
    bounds=((0.0,0.0),(1.0,1.0)),
    anchor_color=(0.2, 0.2, 0.2, 0.8), anchor_size=40,
    handle_color=(0.5, 0.5, 0.5, 0.8), handle_size=10,
    handle_line_color=(0.4, 0.4, 0.4, 0.5), handle_line_thickness=2.0,
    draw_handle_pts=True, draw_handle_lines=True, draw_anchor=True,
    dpi=1.0, zoom=1.0,
    ):
    """Draw anchor points, handle points, and lines for bezier segments, mapping from bounds."""

    # Nothing to draw?
    if (bezsegs is None) \
        or (not isinstance(bezsegs, np.ndarray)) \
        or (bezsegs.ndim != 2) \
        or (bezsegs.shape[1] != 8) \
        or (bezsegs.shape[0] == 0):
        return None

    # NOTE Coordinate Mapping Setup
    # Find min/max screen coordinates from the rectangle vertices
    all_x = [v[0] for v in recverts]
    all_y = [v[1] for v in recverts]
    screen_min_x, screen_max_x = min(all_x), max(all_x)
    screen_min_y, screen_max_y = min(all_y), max(all_y)

    screen_width = screen_max_x - screen_min_x
    screen_height = screen_max_y - screen_min_y # Assuming screen Y increases upwards

    data_min_x, data_max_x = bounds[0][0], bounds[1][0]
    data_min_y, data_max_y = bounds[0][1], bounds[1][1]

    data_width = data_max_x - data_min_x
    data_height = data_max_y - data_min_y

    # Check for degenerate rectangle or data range
    if (screen_width <= 0) \
        or (screen_height <= 0) \
        or (abs(data_width) < 1e-6) \
        or (abs(data_height) < 1e-6):
        return None

    def map_point_to_screen(data_point):
        """Maps a point from data bounds space to screen space within the rectangle."""
        # Normalize data point coordinates (0 to 1)
        norm_x = (data_point[0] - data_min_x) / data_width
        norm_y = (data_point[1] - data_min_y) / data_height
        # Map normalized coordinates to screen space
        screen_x = screen_min_x + norm_x * screen_width
        screen_y = screen_min_y + norm_y * screen_height 
        return screen_x, screen_y

    def draw_point_square(pos, size, color):
        """Draws a small square centered at pos."""
        sx, sy = pos
        s = size / 2.0
        verts = [(sx - s, sy + s), (sx + s, sy + s), (sx + s, sy - s), (sx - s, sy - s)]
        indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.uniform_float("color", color)
        batch.draw(shader)
        return None

    anchors, handles = [], []

    # Scale sizes based on dpi and zoom
    scaled_anchor_size = anchor_size * dpi * zoom
    scaled_handle_size = handle_size * dpi * zoom
    scaled_handle_line_thickness = handle_line_thickness * dpi * zoom

    for i in range(bezsegs.shape[0]):

        P0s = map_point_to_screen(bezsegs[i, 0:2])
        P1s = map_point_to_screen(bezsegs[i, 2:4])
        P2s = map_point_to_screen(bezsegs[i, 4:6])
        P3s = map_point_to_screen(bezsegs[i, 6:8])

        if (draw_handle_lines and scaled_handle_line_thickness > 0):
            batch_lines = batch_for_shader(shader, 'LINES',
                {"pos":[P0s, P1s, P2s, P3s]}, indices=[(0, 1), (2, 3)])
            shader.uniform_float("color", handle_line_color)
            gpu.state.line_width_set(scaled_handle_line_thickness)
            batch_lines.draw(shader)
            gpu.state.line_width_set(1.0)

        if (draw_handle_pts):
            handles.append([P1s, scaled_handle_size, handle_color])
            handles.append([P2s, scaled_handle_size, handle_color])

        if (draw_anchor):   
            if (i==0):
                anchors.append([P0s, scaled_anchor_size, anchor_color])
            anchors.append([P3s, scaled_anchor_size, anchor_color])
        continue

    for point in handles:
        if point[1] > 0: # Only draw if size is positive
            draw_point_square(point[0], point[1], point[2])
        continue

    for point in anchors:
        if point[1] > 0: # Only draw if size is positive
            draw_point_square(point[0], point[1], point[2])
        continue

    return None


def draw_curve_fill(shader, recverts, preview_data, bounds, fill_color, num_steps=20):
    """Draws the filled area under the bezier curve, extending with tangents."""
    
    # NOTE this function is AI generated slop.
    # TODO 
    # - needs a big clean up. 
    # - need to make use of sample_bezsegs and calculate it in local space.
    # - need f.CACHE optimization like in draw_bezcurve, store local space pts in there. evaluate_segment need to go..

    if (fill_color is None) \
        or (preview_data is None) \
        or (not isinstance(preview_data, np.ndarray)) \
        or (preview_data.ndim != 2) \
        or (preview_data.shape[1] != 8) \
        or (preview_data.shape[0] == 0):
        return None

    # Coordinate Mapping Setup (copied from draw_bezcurve)
    all_x = [v[0] for v in recverts]
    all_y = [v[1] for v in recverts]
    screen_min_x, screen_max_x = min(all_x), max(all_x)
    screen_min_y, screen_max_y = min(all_y), max(all_y)
    screen_width = screen_max_x - screen_min_x
    screen_height = screen_max_y - screen_min_y
    if (screen_width <= 0) or (screen_height <= 0):
        return None
    data_min_x, data_max_x = bounds[0][0], bounds[1][0]
    data_min_y, data_max_y = bounds[0][1], bounds[1][1]
    data_width = data_max_x - data_min_x
    data_height = data_max_y - data_min_y
    if (abs(data_width) < 1e-6) or (abs(data_height) < 1e-6):
        return None

    def map_point_to_screen(data_point):
        norm_x = (data_point[0] - data_min_x) / data_width if data_width else 0.5
        norm_y = (data_point[1] - data_min_y) / data_height if data_height else 0.5
        screen_x = screen_min_x + norm_x * screen_width
        screen_y = screen_min_y + norm_y * screen_height
        return screen_x, screen_y
    
    def evaluate_segment(P0, P1, P2, P3, t):
        omt = 1.0 - t; omt2 = omt * omt; omt3 = omt2 * omt
        t2 = t * t; t3 = t2 * t
        return (P0 * omt3) + (P1 * 3.0 * omt2 * t) + (P2 * 3.0 * omt * t2) + (P3 * t3)

    # Generate Curve Points
    curve_points_screen = []
    for i in range(preview_data.shape[0]):
        P0 = np.array(preview_data[i, 0:2], dtype=float)
        P1 = np.array(preview_data[i, 2:4], dtype=float)
        P2 = np.array(preview_data[i, 4:6], dtype=float)
        P3 = np.array(preview_data[i, 6:8], dtype=float)
        start_idx = 1 if (i > 0) else 0

        for j in range(start_idx, num_steps + 1):
            t = j / num_steps
            data_point = evaluate_segment(P0, P1, P2, P3, t)
            screen_point = map_point_to_screen(data_point)
            if not (curve_points_screen and np.allclose(screen_point, curve_points_screen[-1])):
                curve_points_screen.append(screen_point)
            continue

        continue

    if (len(curve_points_screen) < 2):
        return None

    # Calculate Tangent Intersections
    P0_data = np.array(preview_data[0, 0:2], dtype=float)
    P1_data = np.array(preview_data[0, 2:4], dtype=float)
    P2_last_data = np.array(preview_data[-1, 4:6], dtype=float)
    P3_last_data = np.array(preview_data[-1, 6:8], dtype=float)
    P0s = map_point_to_screen(P0_data)
    P1s = map_point_to_screen(P1_data)
    P2s_last = map_point_to_screen(P2_last_data)
    P3s_last = map_point_to_screen(P3_last_data)
    Tx_start, Ty_start = P1s[0] - P0s[0], P1s[1] - P0s[1]
    Tx_end, Ty_end = P3s_last[0] - P2s_last[0], P3s_last[1] - P2s_last[1]

    # Define the intersection helper function *within* draw_curve_fill
    def _get_rect_intersection(point, tangent, screen_min_x, screen_max_x, screen_min_y, screen_max_y):
        P = np.array(point)
        T = np.array(tangent)
        min_t = float('inf')
        intersect = P # Default to original point
        epsilon = 1e-6
        # Check Left Edge (x = screen_min_x)
        if abs(T[0]) > epsilon:
            t = (screen_min_x - P[0]) / T[0]
            if t >= -epsilon: 
                y = P[1] + t * T[1]
                if screen_min_y - epsilon <= y <= screen_max_y + epsilon:
                    if t < min_t:
                        min_t = t
                        intersect = (screen_min_x, y)
        # Check Right Edge (x = screen_max_x)
        if abs(T[0]) > epsilon:
            t = (screen_max_x - P[0]) / T[0]
            if t >= -epsilon:
                y = P[1] + t * T[1]
                if screen_min_y - epsilon <= y <= screen_max_y + epsilon:
                     if t < min_t:
                        min_t = t
                        intersect = (screen_max_x, y)
        # Check Bottom Edge (y = screen_min_y)
        if abs(T[1]) > epsilon:
            t = (screen_min_y - P[1]) / T[1]
            if t >= -epsilon:
                x = P[0] + t * T[0]
                if screen_min_x - epsilon <= x <= screen_max_x + epsilon:
                    if t < min_t:
                        min_t = t
                        intersect = (x, screen_min_y)
        # Check Top Edge (y = screen_max_y)
        if abs(T[1]) > epsilon:
            t = (screen_max_y - P[1]) / T[1]
            if t >= -epsilon:
                x = P[0] + t * T[0]
                if screen_min_x - epsilon <= x <= screen_max_x + epsilon:
                     if t < min_t:
                        min_t = t
                        intersect = (x, screen_max_y)
        # Final clamp 
        intersect = (max(screen_min_x, min(screen_max_x, intersect[0])),
                     max(screen_min_y, min(screen_max_y, intersect[1])))
        return intersect

    intersect_start = _get_rect_intersection(P0s, (-Tx_start, -Ty_start), screen_min_x, screen_max_x, screen_min_y, screen_max_y)
    intersect_end = _get_rect_intersection(P3s_last, (Tx_end, Ty_end), screen_min_x, screen_max_x, screen_min_y, screen_max_y)

    # Construct vertices for TRI_STRIP fill
    fill_vertices = []
    fill_vertices.append((intersect_start[0], screen_min_y)) # Bottom start
    fill_vertices.append(intersect_start)                    # Top start
    for point in curve_points_screen:
        fill_vertices.append((point[0], screen_min_y))     # Bottom mid
        fill_vertices.append(point)                        # Top mid (curve)
    fill_vertices.append((intersect_end[0], screen_min_y)) # Bottom end
    fill_vertices.append(intersect_end)                    # Top end

    # Draw main fill area
    fill_batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": fill_vertices})
    shader.uniform_float("color", fill_color)
    fill_batch.draw(shader)

    # Draw Corner Rectangles if Intersection Hit Top Edge
    epsilon_y = 1e-4
    corner_rect_indices = [(0, 1, 2), (0, 2, 3)]
    epsilon = 1e-6 # Added epsilon for x comparison

    if (abs(intersect_start[1] - screen_max_y) < epsilon_y) \
        and (intersect_start[0] > screen_min_x + epsilon):
        left_corner_verts = [(screen_min_x, screen_min_y), (screen_min_x, screen_max_y),
                             (intersect_start[0], screen_max_y), (intersect_start[0], screen_min_y)]
        corner_batch = batch_for_shader(shader, 'TRIS', {"pos": left_corner_verts}, indices=corner_rect_indices)
        shader.uniform_float("color", fill_color)
        corner_batch.draw(shader)

    if (abs(intersect_end[1] - screen_max_y) < epsilon_y) \
        and (intersect_end[0] < screen_max_x - epsilon):
        right_corner_verts = [(intersect_end[0], screen_min_y), (intersect_end[0], screen_max_y),
                             (screen_max_x, screen_max_y), (screen_max_x, screen_min_y)]
        corner_batch = batch_for_shader(shader, 'TRIS', {"pos": right_corner_verts}, indices=corner_rect_indices)
        shader.uniform_float("color", fill_color)
        corner_batch.draw(shader)

    return None


def draw_bezcurve(
    shader, recverts, preview_data:np.ndarray,
    bounds=((0.0,0.0),(1.0,1.0)),
    line_color=(0.9, 0.9, 0.9, 0.9), # Removed fill_color
    thickness=2.0, num_steps=20
    ):
    """Draw only the bezier curve line, mapping from bounds."""

    # Nothing to draw?
    if (preview_data is None) \
        or (not isinstance(preview_data, np.ndarray)) \
        or (preview_data.ndim != 2) \
        or (preview_data.shape[1] != 8) \
        or (preview_data.shape[0] == 0):
        return None

    #1: Get the curve points.

    # Initiate function cache
    f = draw_bezcurve
    if not hasattr(f,'CACHE'):
        f.CACHE = {}

    # get the curve points. might be harnessed from cache.
    hash = hash_bezsegs(preview_data)
    if (hash in f.CACHE):
        curvepts = f.CACHE[hash]
    else:
        curvepts = sample_bezsegs(preview_data, num_steps)
        f.CACHE[hash] = curvepts

    if (len(curvepts) < 2):
        return None

    #2: We map our curve points to screen space.

    # Coordinate Mapping Setup
    all_x = [v[0] for v in recverts]
    all_y = [v[1] for v in recverts]
    screen_min_x, screen_max_x = min(all_x), max(all_x)
    screen_min_y, screen_max_y = min(all_y), max(all_y)
    screen_width = screen_max_x - screen_min_x
    screen_height = screen_max_y - screen_min_y

    # Check for degenerate rectangle first
    if (screen_width <= 0) or (screen_height <= 0):
        return None

    # get screen bounds data for mapping the curve data in screen space
    data_min_x, data_max_x = bounds[0][0], bounds[1][0]
    data_min_y, data_max_y = bounds[0][1], bounds[1][1]
    data_width = data_max_x - data_min_x
    data_height = data_max_y - data_min_y

    # Check for degenerate data range
    if (abs(data_width) < 1e-6) or (abs(data_height) < 1e-6):
        return None

    def map_point_to_screen(data_point):
        norm_x = (data_point[0] - data_min_x) / data_width if (data_width) else 0.5
        norm_y = (data_point[1] - data_min_y) / data_height if (data_height) else 0.5
        screen_x = screen_min_x + norm_x * screen_width
        screen_y = screen_min_y + norm_y * screen_height
        return screen_x, screen_y

    # map the curve points to screen space
    curvepts_screen = [map_point_to_screen(pt) for pt in curvepts]

    # Draw Curve Line Only
    gpu.state.line_width_set(thickness)
    line_batch = batch_for_shader(shader, 'LINE_STRIP', {"pos":curvepts_screen,})
    shader.uniform_float("color", line_color)
    line_batch.draw(shader)
    gpu.state.line_width_set(1.0)

    return None

def draw_interpolation_preview(node_tree, view2d, dpi, zoom):
    """Draw transparent black box on preview nodes with custom margins"""

    nd_to_draw = [n for n in node_tree.nodes if (not n.hide) and ('NodeBooster2DCurvePreview' in n.bl_idname)]
    if (not nd_to_draw):
        return None

    # Save global states we might modify
    original_blend = gpu.state.blend_get()

    # Set up shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    # NOTE we need to cut drawing out of preview area.
    # Save states we modify within the loop
    original_scissor_box = gpu.state.scissor_get()

    for node in nd_to_draw:
        cwidth = 3.5 if (node.draw_handles) else 2.75

        # Set states needed for this node's drawing
        gpu.state.blend_set('ALPHA') 
        
        # Get node location and properly apply DPI scaling
        nlocx, nlocy = node.location
        nlocx *= dpi
        nlocy *= dpi

        # Get node dimensions
        ndimx, ndimy = node.dimensions.x, node.dimensions.y

        # define margins. Scaling based on dpi.
        margin_top = 50 * dpi
        margin_bottom = 27 * dpi
        margin_left = 9.5 * dpi
        margin_right = 9.5 * dpi

        # Define our rectangle locaiton and dimensions.
        locx = nlocx + margin_left
        loxy = nlocy - margin_top
        dimx = ndimx - (margin_left + margin_right)
        dimy = ndimy - (margin_top + margin_bottom)

        # get the bounds
        match node.preview_scale:
            case 'POS':    data_bounds = ((node.bounds_positive[0], node.bounds_positive[1]), (node.bounds_positive[2], node.bounds_positive[3]))
            case 'NEG':    data_bounds = ((node.bounds_negative[0], node.bounds_negative[1]), (node.bounds_negative[2], node.bounds_negative[3]))
            case 'CUSTOM': data_bounds = ((node.bounds_custom[0], node.bounds_custom[1]), (node.bounds_custom[2], node.bounds_custom[3]))
            case 'FIT':    data_bounds = ((node.bounds_fitcurve[0], node.bounds_fitcurve[1]), (node.bounds_fitcurve[2], node.bounds_fitcurve[3]))

        # get the data to draw the bezier curve and anchors/handles ect..
        preview_data = PREVIEW_DATA.get(f"Preview{node.name}")
        is_valid = (preview_data is not None) and (not node.mute)
        if (not is_valid):
            data_bounds = ((0,0), (0,0))

        # draw a background rectangle and get screen origin
        recverts = draw_rectangle(shader, view2d, (locx, loxy), (dimx, dimy),
            bounds=data_bounds, tick_interval=node.grid_tick,
            rectangle_color=(0.0, 0.0, 0.0, 0.3), grid_color=(0.5, 0.5, 0.5, 0.04), grid_line_width=1.0,
            axis_color=(0.6, 0.6, 0.6, 0.1), axis_line_width=1.2,
            border_color=(0.0, 0.0, 0.0, 0.6), border_width=1.0,
            draw_grid=node.draw_grid, dpi=dpi, zoom=zoom,
            )

        if (is_valid):

            # NOTE Scissor for Clipping out of preview area
            # in case the drawing below goes out of bounds..
            # Find screen bounds from recverts
            all_x = [v[0] for v in recverts]
            all_y = [v[1] for v in recverts]
            min_sx, max_sx = min(all_x), max(all_x)
            min_sy, max_sy = min(all_y), max(all_y)
            scissor_x = int(min_sx)
            scissor_y = int(min_sy)
            scissor_w = int(max_sx - min_sx)
            scissor_h = int(max_sy - min_sy)

            # Ensure valid width/height before setting scissor
            if (scissor_w > 0) and (scissor_h > 0):
                # Enable scissor test and set the box
                gpu.state.scissor_test_set(True)
                gpu.state.scissor_set(scissor_x, scissor_y, scissor_w, scissor_h)
            else:
                # If dimensions are invalid, ensure test is off
                gpu.state.scissor_test_set(False)

            # Draw the fill first
            if (node.draw_fill):
                draw_curve_fill(shader, recverts, preview_data,
                    bounds=data_bounds, fill_color=(0, 0, 0, 0.25), num_steps=20,
                    )
            # Then draw the curve line
            if (node.draw_curve):
                draw_bezcurve(shader, recverts, preview_data, 
                    bounds=data_bounds, line_color=(0.1, 0.1, 0.1, 1.0),
                    thickness=cwidth * dpi * zoom, num_steps=20,
                    )

            #draw the handles
            draw_bezpoints(shader, recverts, preview_data, 
                bounds=data_bounds,
                anchor_color=(1, 1, 1, 1.0),
                handle_color=(0.6, 0.3, 0.3, 1.0),
                handle_line_color=(0.7, 0.4, 0.4, 0.2),
                handle_line_thickness=1.0,
                anchor_size=4.75,
                handle_size=3.5,
                draw_anchor=node.draw_anchor,
                draw_handle_pts=node.draw_handles,
                draw_handle_lines=node.draw_handles,
                dpi=dpi, zoom=zoom,
                )

        # Restore original scissor box and disable test
        gpu.state.scissor_set(*original_scissor_box) # Unpack tuple for arguments
        gpu.state.scissor_test_set(False) # Disable test for this node
        # Restore other states modified for this node
        gpu.state.blend_set(original_blend) # Restore original blend state

        continue

    # Final state clipping restoration.
    # It's possible the loop didn't run, so restore global state here too
    gpu.state.blend_set(original_blend)
    
    return None

