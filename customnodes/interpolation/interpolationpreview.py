# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
import os
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np

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
    bl_label = "Interpolation Preview"
    bl_description = """Preview the result of an interpolation curve."""
    bl_width_min = 157
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    # NOTE this node is the end of the line for our a socket type, 
    # it has a special evaluator responsability for socket.nodebooster_socket_type == 'INTERPOLATION'.
    evaluator_properties = {'INTERPOLATION_OUTPUT',}

    # preview_type : bpy.props.EnumProperty(
    #     name="Preview Type",
    #     description="How to display the interpolation preview",
    #     items=[
    #         ("LINE", "Line", "Display as a line"),
    #         ("BARS", "Bars", "Display as vertical bars"),
    #         ("DOTS", "Dots", "Display as dots"),
    #         ],
    #     default="LINE",
    #     update= lambda self, context: self.evaluator(),
    #     )

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

        val = evaluate_upstream_value(self.inputs[0], self.node_tree,
            match_evaluator_properties={'INTERPOLATION_NODE',},
            set_link_invalid=True,
            )
        print(val)
        PREVIEW_DATA[f"Preview{self.name}"] = val
        print("--------------------------------")

        return None

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        # layout.prop(self, 'preview_type', text="")
        layout.separator(factor=34.30)

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        # header, panel = layout.panel("params_panelid", default_closed=False)
        # header.label(text="Parameters")
        # if panel:
        #     panel.prop(self, 'preview_type', text="Preview Style")
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

#TODO bonus:
# - What if interpolation goes beyond 0-1 range? what if beyond -1/1 range? 
#   perhaps we should first arrange the graph data, then resize it to fit box.
# - Points on 00-11 are going out of the box clip area.

def draw_rectangle(shader, view2d, location, dimensions, area_width,
    rectangle_color=(0.0, 0.0, 0.0, 0.3), grid_color=(0.5, 0.5, 0.5, 0.05),):
    """Draw transparent black box on InterpolationPreview nodes with custom margins"""

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

    # Draw grid lines every quarter
    for i in range(5):

        # Horizontal
        y_pos = y1 - (i * (y1 - y4) / 4)
        h_vertices = [(x1, y_pos), (x2, y_pos)]
        batch = batch_for_shader(shader, 'LINES', {"pos": h_vertices})
        shader.uniform_float("color", grid_color)
        batch.draw(shader)

        # Vertical
        x_pos = x1 + (i * (x2 - x1) / 4)
        v_vertices = [(x_pos, y1), (x_pos, y4)]
        batch = batch_for_shader(shader, 'LINES', {"pos": v_vertices})
        shader.uniform_float("color", grid_color)
        batch.draw(shader)

        continue

    return vertices    

def draw_bezhandles(shader, view2d, recverts, bezsegs,
    anchor_color=(0.2, 0.2, 0.2, 0.8), anchor_size=40,
    handle_color=(0.5, 0.5, 0.5, 0.8), handle_size=10,
    handle_line_color=(0.4, 0.4, 0.4, 0.5), handle_line_thickness=2.0,
    ):
    """Draw anchor points, handle points, and lines for bezier segments."""

    # Nothing to draw?
    if (bezsegs is None) or not isinstance(bezsegs, np.ndarray) \
        or (bezsegs.ndim != 2) or (bezsegs.shape[1] != 8) or (bezsegs.shape[0] == 0):
        return None

    # NOTE Coordinate Mapping Setup
    # recverts = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)] -> screen space corners
    # (x1, y1) = Top-left, (x4, y4) = Bottom-left (usually)
    # Important: Need to handle potential flipped y-coordinates depending on view_to_region results.
    # Let's assume standard screen coordinates where Y increases downwards for now,
    # but usually, view_to_region gives bottom-left origin.

    # Find min/max screen coordinates from the rectangle vertices
    all_x = [v[0] for v in recverts]
    all_y = [v[1] for v in recverts]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    width = max_x - min_x
    height = max_y - min_y

    # Check for degenerate rectangle
    if (width <= 0) or (height <= 0):
        return None

    def map_point_to_screen(point_01):
        """Maps a point from 0-1 space to screen space within the rectangle.
        Assuming Y=0 is bottom, Y=1 is top in normalized space"""
        screen_x = min_x + point_01[0] * width
        screen_y = min_y + point_01[1] * height 
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

    # first we draw the handle lines
    for i in range(bezsegs.shape[0]):

        # Map points to screen coordinates
        P0s = map_point_to_screen(bezsegs[i, 0:2])
        P1s = map_point_to_screen(bezsegs[i, 2:4])
        P2s = map_point_to_screen(bezsegs[i, 4:6])
        P3s = map_point_to_screen(bezsegs[i, 6:8])

        # Draw Handle Lines (P0->P1 and P2->P3)
        batch_lines = batch_for_shader(shader, 'LINES',
            {"pos":[P0s, P1s, P2s, P3s]}, indices=[(0, 1), (2, 3)])
        shader.uniform_float("color", handle_line_color)
        gpu.state.line_width_set(handle_line_thickness)
        batch_lines.draw(shader)
        gpu.state.line_width_set(1.0)

        # Draw Handle Points (P1 and P2)
        handles.append([P1s, handle_size, handle_color])
        handles.append([P2s, handle_size, handle_color])

        # Draw Anchor Points (P0 and P3)
        # Draw P0 only for the first segment
        if (i==0):
            anchors.append([P0s, anchor_size, anchor_color])
        # Draw P3 for every segment (as it's the end anchor)
        anchors.append([P3s, anchor_size, anchor_color])
        continue

    #then we draw the points
    for point in handles:
        draw_point_square(point[0], point[1], point[2])
        continue
    for point in anchors:
        draw_point_square(point[0], point[1], point[2])
        continue

    return None

def draw_bezcurve(shader, view2d, recverts, preview_data,
    color=(0.9, 0.9, 0.9, 0.9), thickness=2.0, num_steps=20
    ):
    """Draw the bezier curve represented by the preview_data."""

    # --- Input Validation ---
    if preview_data is None or not isinstance(preview_data, np.ndarray) or preview_data.ndim != 2 or preview_data.shape[1] != 8 or preview_data.shape[0] == 0:
        # print("DEBUG draw_bezcurve: Invalid or empty preview_data")
        return None

    # --- Coordinate Mapping Setup ---
    all_x = [v[0] for v in recverts]
    all_y = [v[1] for v in recverts]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    width = max_x - min_x
    height = max_y - min_y

    if width <= 0 or height <= 0:
        # print("DEBUG draw_bezcurve: Degenerate rectangle")
        return None

    def map_point_to_screen(point_01):
        screen_x = min_x + point_01[0] * width
        screen_y = min_y + point_01[1] * height 
        return screen_x, screen_y

    # --- Local Bezier Evaluation Function ---
    # Avoids external dependency, uses only numpy
    def evaluate_segment(P0, P1, P2, P3, t):
        """Evaluates a single cubic bezier segment at t."""
        omt = 1.0 - t
        omt2 = omt * omt
        omt3 = omt2 * omt
        t2 = t * t
        t3 = t2 * t
        return (P0 * omt3) + (P1 * 3.0 * omt2 * t) + (P2 * 3.0 * omt * t2) + (P3 * t3)

    # --- Generate Curve Points ---
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
            point_01 = evaluate_segment(P0, P1, P2, P3, t)
            # Map the 0-1 point to screen coordinates
            screen_point = map_point_to_screen(point_01)
            
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

    # --- Draw Curve ---
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
    margin_top=38, margin_bottom=35, margin_left=13.5, margin_right=13.5,):
    """Draw transparent black box on InterpolationPreview nodes with custom margins"""

    nd_to_draw = [n for n in node_tree.nodes if (not n.hide) and ('NodeBoosterInterpolationPreview' in n.bl_idname)]
    if (not nd_to_draw):
        return None

    # Set up drawing state
    gpu.state.blend_set('ALPHA')

    # Set up shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    # Area width for clipping
    awidth = bpy.context.area.width

    for node in nd_to_draw:
        
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

        # draw a background rectangle
        recverts = draw_rectangle(shader, view2d, (nlocx, nlocy), (ndimx, ndimy), awidth,
            rectangle_color=(0.0, 0.0, 0.0, 0.3), grid_color=(0.5, 0.5, 0.5, 0.05),)
        
        # draw the bezier curve
        preview_data = PREVIEW_DATA.get(f"Preview{node.name}")
        if (preview_data is None):
            continue
        
        # draw the handles
        draw_bezcurve(shader, view2d, recverts, preview_data,
            color=(0.0, 0.0, 0.0, 0.45),
            thickness=4.0 * dpi * zoom,
            )
        #draw the handles
        draw_bezhandles(shader, view2d, recverts, preview_data,
            anchor_color=(1, 1, 1, 1.0),
            handle_color=(0.3, 0.3, 0.3, 1.0),
            handle_line_color=(0.4, 0.4, 0.4, 0.2),
            handle_line_thickness=1.0 * dpi * zoom,
            anchor_size=4.5 * dpi * zoom,
            handle_size=4.0 * dpi * zoom,
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
