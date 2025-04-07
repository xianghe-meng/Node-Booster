# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
import os
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np
import math # Add math import for calculations

from ...__init__ import get_addon_prefs
from ...utils.str_utils import word_wrap
from ...utils.interpolation_utils import bezsegs_to_curvemapping, reset_curvemapping
from ..evaluator import evaluate_upstream_value
from ...utils.node_utils import (
    import_new_nodegroup, 
    set_node_socketattr,
    get_node_socket_by_name,
    parcour_node_tree,
)


# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 


PREVIEW_DATA = {}


class Base():

    bl_idname = "NodeBoosterInterpolationPreview"
    bl_label = "2D Curve Preview"
    bl_description = """Preview the result of a 2D curve."""
    bl_width_min = 157
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    # NOTE this node is the end of the line for our a socket type, 
    # it has a special evaluator responsability for socket.nodebooster_socket_type == 'INTERPOLATION'.
    evaluator_properties = {'INTERPOLATION_OUTPUT',}

    show_handles : bpy.props.BoolProperty(
        name="Show Handle Lines",
        description="Show the lines of the handles",
        default=False,
        )
    preview_lock : bpy.props.BoolProperty(
        name="Preview Lock",
        description="Lock the preview scale with the width of the node",
        default=False,
        )
    preview_scale : bpy.props.EnumProperty(
        name="Graph Scale",
        description="How to fit the graph",
        items=[
            ("POS", "Positive", "Graph in 0/1 range"),
            ("NEG", "Negative", "Graph in -1/-1 range"),
            ("FIT", "Fit Curve", "Graph fit the curve range"),
            ],
        default="POS",
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
            # Assume nodegroup exists in the blend file
            blendfile = os.path.join(os.path.dirname(__file__), "interpolation_nodegroups.blend")
            ng = import_new_nodegroup(blendpath=blendfile, ngname=self.bl_idname,)

            # set the name of the ng
            ng.name = name

        ng = ng.copy() # always using a copy of the original ng

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
        
        print("DEBUG: InterpolationPreview update")
        self.evaluator()
        print("evaluator done")

        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def evaluator(self,)->None:
        """evaluator the node required for the output evaluator"""

        PREVIEW_DATA[f"Preview{self.name}"] = evaluate_upstream_value(self.inputs[0], self.node_tree,
            match_evaluator_properties={'INTERPOLATION_NODE',},
            set_link_invalid=True,
            )

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row(align=True)
        rowl = row.row(align=True)
        rowl.alignment = 'LEFT'
        rowl.prop(self, 'preview_lock', text="", icon='LOCKED' if self.preview_lock else 'UNLOCKED')
        rowl.prop(self, 'preview_scale', text="",)
        rowr = row.row(align=True)
        rowr.alignment = 'RIGHT'
        rowr.prop(self, 'show_handles', text="", icon='HANDLE_ALIGNED')
        layout.separator(factor=self.width / 7 if self.preview_lock else 35.0)

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        # header, panel = layout.panel("params_panelid", default_closed=False)
        # header.label(text="Parameters")
        # if panel:
        #     panel.separator(factor=1.0)

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

#   .oooooo.                           
#  d8P'  `Y8b                          
# 888           oo.ooooo.  oooo  oooo  
# 888            888' `88b `888  `888  
# 888     ooooo  888   888  888   888  
# `88.    .88'   888   888  888   888  
#  `Y8bood8P'    888bod8P'  `V88V"V8P' 
#                888                   
#               o888o                  

#TODO:
# - Points or curve can go out of the rectangle area
# - detail: line width do not scale well with zoom
# - important: dpi scaling is not ok with graph..


def draw_rectangle(shader, view2d, location, dimensions,
    bounds=((0.0,0.0),(1.0,1.0),), tick_interval=0.25,
    rectangle_color=(0.0, 0.0, 0.0, 0.3), 
    grid_color=(0.5, 0.5, 0.5, 0.05), grid_line_width=1.0,
    axis_color=(0.8, 0.8, 0.8, 0.15), axis_line_width=2.0,
    border_color=(0.1, 0.1, 0.1, 0.5), border_width=1.0,
    dpi=1.0, zoom=1.0):
    """Draw transparent black box with grid, axes, and border, mapping data bounds to the box."""

    nlocx, nlocy = location
    ndimx, ndimy = dimensions

    # Convert to screen space
    x1, y1 = view2d.view_to_region(nlocx, nlocy, clip=False)
    x2, y2 = view2d.view_to_region(nlocx + ndimx, nlocy, clip=False)
    x3, y3 = view2d.view_to_region(nlocx + ndimx, nlocy - ndimy, clip=False)
    x4, y4 = view2d.view_to_region(nlocx, nlocy - ndimy, clip=False)

    # Create rectangle vertices
    vertices = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
    indices = [(0, 1, 2), (0, 2, 3)]

    # Create batch and draw
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.uniform_float("color", rectangle_color)
    batch.draw(shader)

    if (bounds is not None):

        x_min, x_max = bounds[0][0], bounds[1][0]
        y_min, y_max = bounds[0][1], bounds[1][1]

        # raw Grid Lines
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
            # Map from bottom (y4) up
            return y4 + ((data_y - y_min) / data_height) * screen_height

        # Calculate scaled line widths
        scaled_grid_width = grid_line_width * dpi * zoom
        scaled_axis_width = axis_line_width * dpi * zoom

        # Vertical Grid Lines (X ticks)
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

        # Horizontal Grid Lines (Y ticks)
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
    draw_handle_pts=True, draw_handle_lines=True,
    dpi=1.0, zoom=1.0,
    ):
    """Draw anchor points, handle points, and lines for bezier segments, mapping from bounds."""

    # Nothing to draw?
    if (bezsegs is None) or not isinstance(bezsegs, np.ndarray) \
        or (bezsegs.ndim != 2) or (bezsegs.shape[1] != 8) or (bezsegs.shape[0] == 0):
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
    if (screen_width <= 0) or (screen_height <= 0) or abs(data_width) < 1e-6 or abs(data_height) < 1e-6:
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

    anchors = []
    handles = []

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

def draw_bezcurve(shader, recverts, preview_data,
    bounds=((0.0,0.0),(1.0,1.0)),
    color=(0.9, 0.9, 0.9, 0.9), thickness=2.0, num_steps=20
    ):
    """Draw the bezier curve represented by the preview_data, mapping from bounds."""

    # Nothing to draw?
    if preview_data is None or not isinstance(preview_data, np.ndarray) \
        or preview_data.ndim != 2 or preview_data.shape[1] != 8 or preview_data.shape[0] == 0:
        return None

    # Coordinate Mapping Setup
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
    if (screen_width <= 0) or (screen_height <= 0) or abs(data_width) < 1e-6 or abs(data_height) < 1e-6:
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

    # Local Bezier Evaluation Function
    # Avoids external dependency, uses only numpy
    def evaluate_segment(P0, P1, P2, P3, t):
        """Evaluates a single cubic bezier segment at t."""
        omt = 1.0 - t
        omt2 = omt * omt
        omt3 = omt2 * omt
        t2 = t * t
        t3 = t2 * t
        return (P0 * omt3) + (P1 * 3.0 * omt2 * t) + (P2 * 3.0 * omt * t2) + (P3 * t3)

    # Generate Curve Points
    curve_points_screen = []
    for i in range(preview_data.shape[0]):
        # Extract control points for the current segment
        # Ensure they are numpy arrays for calculations
        P0 = np.array(preview_data[i, 0:2], dtype=float)
        P1 = np.array(preview_data[i, 2:4], dtype=float)
        P2 = np.array(preview_data[i, 4:6], dtype=float)
        P3 = np.array(preview_data[i, 6:8], dtype=float)

        # Evaluate points along the segment
        for j in range(num_steps + 1):
            t = j / num_steps
            data_point = evaluate_segment(P0, P1, P2, P3, t)
            # Map the data point to screen coordinates
            screen_point = map_point_to_screen(data_point)
            
            # Add to list, but avoid adding the start point of subsequent segments
            # if it's identical to the previous end point (prevents duplicate verts in line strip)
            if i > 0 and j == 0: 
                # Check if close to the last point added
                if curve_points_screen:
                    last_pt = curve_points_screen[-1]
                    if abs(screen_point[0] - last_pt[0]) < 0.1 and abs(screen_point[1] - last_pt[1]) < 0.1:
                         continue # Skip adding duplicate start point
            
            curve_points_screen.append(screen_point)

    if not curve_points_screen:
        # print("DEBUG draw_bezcurve: No screen points generated.")
        return None

    # Draw Curve
    # Set line width (Note: might not be supported by all drivers/GPUs consistently)
    try:
        gpu.state.line_width_set(thickness)
    except:
        print("Warning: Could not set line width.") # Fallback if unsupported

    # Create batch for the line strip
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": curve_points_screen})
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Reset line width to default if it was set
    try:
        gpu.state.line_width_set(1.0) 
    except:
        pass # Ignore if reset fails

    return None

def draw_interpolation_preview(node_tree, view2d, dpi, zoom,
    margin_top=65, margin_bottom=40, margin_left=13.5, margin_right=13.5,):
    """Draw transparent black box on InterpolationPreview nodes with custom margins"""

    nd_to_draw = [n for n in node_tree.nodes if (not n.hide) and ('NodeBoosterInterpolationPreview' in n.bl_idname)]
    if (not nd_to_draw):
        return None

    # Set up drawing state
    gpu.state.blend_set('ALPHA')

    # Set up shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    for node in nd_to_draw:
        cwidth = 3.5 if node.show_handles else 2.75
        
        # Get node location and properly apply DPI scaling
        nlocx, nlocy = node.location
        nlocx *= dpi
        nlocy *= dpi

        # Get node dimensions
        ndimx, ndimy = node.dimensions.x, node.dimensions.y

        # Apply custom margins
        nlocx += margin_left
        nlocy -= margin_top
        ndimx -= (margin_left + margin_right)
        ndimy -= (margin_top + margin_bottom)

        # draw the bezier curve
        preview_data = PREVIEW_DATA.get(f"Preview{node.name}")

        # Define bounds once
        data_bounds = None
        match node.preview_scale:
            case 'POS':
                data_bounds = ((0,0),(1,1),)
            case 'NEG':
                data_bounds = ((-1,-1),(1,1),)
            case 'FIT':
                # Find the bounds of the curve data to fit it in the view
                if (preview_data is not None) and (isinstance(preview_data, np.ndarray)) and (preview_data.size > 0):
                    # Extract x and y coordinates from bezier segments
                    x_coords = preview_data[:, [0, 2, 4, 6]].flatten()  # All x coordinates (P0x, P1x, P2x, P3x)
                    y_coords = preview_data[:, [1, 3, 5, 7]].flatten()  # All y coordinates (P0y, P1y, P2y, P3y)

                    # Calculate min/max with small padding
                    x_min, x_max = np.min(x_coords), np.max(x_coords)
                    y_min, y_max = np.min(y_coords), np.max(y_coords)

                    # Add 5% padding
                    x_pad = (x_max - x_min) * 0.05
                    y_pad = (y_max - y_min) * 0.05

                    # Ensure we have some minimum bounds even for flat curves
                    x_pad = max(x_pad, 0.1)
                    y_pad = max(y_pad, 0.1)
                    
                    data_bounds = ((x_min - x_pad, y_min - y_pad), (x_max + x_pad, y_max + y_pad))

        # draw a background rectangle and get screen origin
        recverts = draw_rectangle(shader, view2d, (nlocx, nlocy), (ndimx, ndimy),
            bounds=data_bounds, tick_interval=0.25,
            rectangle_color=(0.0, 0.0, 0.0, 0.3), grid_color=(0.5, 0.5, 0.5, 0.04), grid_line_width=1.0,
            axis_color=(0.6, 0.6, 0.6, 0.1), axis_line_width=1.2,
            border_color=(0.0, 0.0, 0.0, 0.6), border_width=1.0,
            dpi=dpi, zoom=zoom,
            )
        
        if (preview_data is not None):
            # draw the curve
            draw_bezcurve(shader, recverts, preview_data, bounds=data_bounds,
                color=(0.0, 0.0, 0.0, 0.45),
                thickness=cwidth * dpi * zoom,
                )
            #draw the handles
            draw_bezpoints(shader, recverts, preview_data, bounds=data_bounds,
                anchor_color=(1, 1, 1, 1.0),
                handle_color=(0.5, 0.3, 0.3, 1.0),
                handle_line_color=(0.6, 0.4, 0.4, 0.2),
                handle_line_thickness=1.0,
                anchor_size=4.75,
                handle_size=3.5,
                draw_handle_pts=node.show_handles,
                draw_handle_lines=node.show_handles,
                dpi=dpi, zoom=zoom,
                )
            
        continue

    # Reset blend mode
    gpu.state.blend_set('NONE')
    
    return None


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_InterpolationPreview(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNodeNodeBoosterInterpolationPreview"

class NODEBOOSTER_NG_SH_InterpolationPreview(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNodeNodeBoosterInterpolationPreview"

class NODEBOOSTER_NG_CP_InterpolationPreview(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNodeNodeBoosterInterpolationPreview"
