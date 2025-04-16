# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from math import sin, cos, pi

from ..utils.node_utils import (
    get_node_absolute_location,
    get_node_absolute_bounds,
)

#Global dict of minimap bounds being draw, key is the area as_pointer() memory adress as str
MINIMAP_BOUNDS = {}


def draw_full_rectangle(
    bottom_left_pos,
    top_right_pos,
    fill_color=(0.1, 0.1, 0.1, 0.8),
    outline_color=(1.0, 1.0, 1.0, 0.5),
    outline_width=1,
    border_radius=5,
    border_sides='AUTO',
    ):
    """Draw a filled rectangle an optional outline and border radius"""

    original_blend = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')

    x1, y1 = bottom_left_pos
    x2, y2 = top_right_pos
    width = x2 - x1
    height = y2 - y1

    if width <= 0 or height <= 0:
        return # Cannot draw zero or negative size rectangle

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    # --- Draw Simple Rectangle (No Radius or radius too large) ---
    if border_radius <= 0 or border_radius * 2 > min(width, height):
        
        # Fill
        vertices = ((x1, y1), (x2, y1), (x1, y2), (x2, y2),)
        indices = ((0, 1, 2), (1, 3, 2),)
        shader.uniform_float("color", fill_color)
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        batch.draw(shader)

        # Outline?
        if outline_color and outline_width > 0:

            # Note: Simple line drawing, width isn't accurate pixel width
            gpu.state.line_width_set(outline_width)
            outline_vertices = (
                (x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)
            )
            shader.uniform_float("color", outline_color)
            batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": outline_vertices})
            batch.draw(shader)
            gpu.state.line_width_set(1.0) # Reset line width

    # --- Draw Fancy Rounded Rectangle ---
    else:
        # --- Refactored Rounded Rectangle Drawing using a single TRIANGLES batch ---

        radius = border_radius
        if (border_sides == 'AUTO'):
            border_sides = max(3,int(radius/1.2))
        segments_per_corner = max(1,border_sides // 4)
        total_verts = (segments_per_corner + 1) * 4

        fill_verts = []
        outline_verts = []

        # Calculate vertices for the rounded corners and straight edges
        corners = [
            (x1 + radius, y1 + radius, pi, 3 * pi / 2),        # Bottom Left
            (x2 - radius, y1 + radius, 3 * pi / 2, 2 * pi),    # Bottom Right
            (x2 - radius, y2 - radius, 0, pi / 2),           # Top Right
            (x1 + radius, y2 - radius, pi / 2, pi)            # Top Left
            ]

        for cx, cy, start_angle, end_angle in corners:
            for i in range(segments_per_corner + 1):
                angle = start_angle + (end_angle - start_angle) * i / segments_per_corner
                vx = cx + cos(angle) * radius
                vy = cy + sin(angle) * radius
                fill_verts.append((vx, vy))
                outline_verts.append((vx, vy))

        # Create indices for the fill triangles (using a fan from the center)
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        fill_verts.append((center_x, center_y)) # Add center vertex
        center_index = len(fill_verts) - 1

        fill_indices = []
        for i in range(total_verts):
            idx1 = i
            idx2 = (i + 1) % total_verts # Wrap around
            fill_indices.append((center_index, idx1, idx2))

        # Draw Fill
        shader.uniform_float("color", fill_color)
        batch_fill = batch_for_shader(shader, 'TRIS', {"pos": fill_verts}, indices=fill_indices)
        batch_fill.draw(shader)

        # Outline?
        if outline_color and outline_width > 0:
            
            gpu.state.line_width_set(outline_width)

            # Close the outline loop
            if outline_verts:
                outline_verts.append(outline_verts[0])

            shader.uniform_float("color", outline_color)
            batch_outline = batch_for_shader(shader, 'LINE_STRIP', {"pos": outline_verts})
            batch_outline.draw(shader)
            gpu.state.line_width_set(1.0) # Reset line width

    # --- Restore State ---
    gpu.state.blend_set(original_blend)

    return None

def draw_minimap(node_tree, area, window_region, view2d, dpi_fac, zoom, 
    mode='BOTTOM_LEFT', padding=20,):
    """draw a minimap of the node_tree in the node_editor area"""

    # Do we even have some nodes to draw?
    if ((not node_tree) or (not node_tree.nodes)):
        return None

    scene_sett = bpy.context.scene.nodebooster
    width_percentage, height_percentage_max = scene_sett.minimap_width_percentage
    padding = scene_sett.minimap_padding

    # do we even want to show the minimap?
    if (not scene_sett.minimap_show):
        return None
    
    # 1. Find the minimap bounds from the nodetree.nodes

    #rassemble all nodes bounds
    node_pts = []
    for node in node_tree.nodes:
        node_pts.extend(get_node_absolute_bounds(node))
        continue

    #find the minimap bounds
    min_x = min(vec.x for vec in node_pts)
    min_y = min(vec.y for vec in node_pts)
    max_x = max(vec.x for vec in node_pts)
    max_y = max(vec.y for vec in node_pts)
    
    bound_nodetree_bottomleft =Vector((min_x, min_y))
    bound_nodetree_topright = Vector((max_x, max_y))
    node_tree_width = bound_nodetree_topright.x - bound_nodetree_bottomleft.x
    node_tree_height = bound_nodetree_topright.y - bound_nodetree_bottomleft.y

    #zero width/height? that's an error..
    if ((node_tree_width <= 0) or (node_tree_height <= 0)):
        print(f"ERROR: draw_minimap(): node_tree_width or node_tree_height is less than 0: {node_tree_width}, {node_tree_height}")
        return None

    #calculate the minimap aspect ratio
    nodesbounds_aspect_ratio = node_tree_width / node_tree_height

    # 2. Calculate Available View Area (in pixels, accounting for panels)

    view_width, view_height = window_region.width, window_region.height
    view_bottom, view_left = 0, 0

    # Subtract panel widths if they are visible
    # if (space.show_region_toolbar):
    #     toolbar_region = next((r for r in space.regions if r.type == 'TOOLS'), None)
    #     if (toolbar_region):
    #         view_left += toolbar_region.width
    #         view_width -= toolbar_region.width
    # if (space.show_region_ui):
    #     ui_region = next((r for r in space.regions if r.type == 'UI'), None)
    #     if (ui_region):
    #         view_width -= ui_region.width # UI panel is typically on the right

    # Calculate Minimap Dimensions and Position in Pixel Space
    # --- Calculate Minimap Dimensions based on Width and Max Height Percentages ---
    target_width = view_width * width_percentage
    target_height = target_width / nodesbounds_aspect_ratio

    max_allowed_height = view_height * height_percentage_max

    if target_height <= max_allowed_height:
        # Height constraint is met, use target width and calculated height
        minimap_pixel_width = target_width
        minimap_pixel_height = target_height
    else:
        # Height constraint exceeded, clamp height and recalculate width
        minimap_pixel_height = max_allowed_height
        minimap_pixel_width = minimap_pixel_height * nodesbounds_aspect_ratio

    # Ensure width doesn't exceed available view width (safety clamp)
    minimap_pixel_width = min(minimap_pixel_width, view_width - 2 * padding)
    minimap_pixel_height = minimap_pixel_width / nodesbounds_aspect_ratio # Recalculate height if width was clamped

    match mode:
        case 'BOTTOM_LEFT':
            #bound bottom left
            x = view_left + padding
            y = view_bottom + padding
            pixel_bottom_left_bound = Vector((x, y))
            #bound top right
            x = pixel_bottom_left_bound.x + minimap_pixel_width
            y = pixel_bottom_left_bound.y + minimap_pixel_height
            pixel_top_right_bound = Vector((x, y))

        case 'TOP_LEFT':
            pass
            # pixel_bottom_left_x = view_left + padding
            # pixel_bottom_left_y = view_height - minimap_pixel_height - padding
        case 'TOP_RIGHT':
            pass
            # pixel_bottom_left_x = view_left + view_width - minimap_pixel_width - padding
            # pixel_bottom_left_y = view_height - minimap_pixel_height - padding
        case 'BOTTOM_RIGHT':
            pass
            # pixel_bottom_left_x = view_left + view_width - minimap_pixel_width - padding
            # pixel_bottom_left_y = view_bottom + padding

    # 4. Draw the Minimap Background Rectangle
    draw_full_rectangle(
        pixel_bottom_left_bound,
        pixel_top_right_bound,
        fill_color=scene_sett.minimap_fill_color,
        outline_color=scene_sett.minimap_outline_color,
        outline_width=scene_sett.minimap_outline_width,
        border_radius=scene_sett.minimap_border_radius,
        )

    # TODO draw nodes within minimap
    # This requires scaling node positions from pixel_bottom_left_boundn, pixel_top_right_bound space to minimap pixel space.

    # TODO Draw Viewport Rectangle within Minimap
    # This requires getting view2d bounds, converting to node space, then scaling to minimap space.
    # Example (Conceptual - Needs correct view coordinate mapping):
    # view_rect_nodespace = view2d.view_to_region(...) # Get view bounds in region coords, map to node coords
    # view_rect_minimap_bl_x = pixel_bottom_left_x + (view_rect_nodespace.min_x - min_x) / nodespace_width * minimap_pixel_width
    # ... similar for other corners ...
    # draw_full_rectangle(view_rect_minimap_bl, view_rect_minimap_tr, fill_color=(0,0,0,0), outline_color=(1,1,0,0.8), outline_width=1)

    # NOTE store the minimap bounds in a global dict. 
    # might need to be accessed by other tools..
    MINIMAP_BOUNDS[str(area.as_pointer())] = (pixel_bottom_left_bound, pixel_top_right_bound)
    
    return None
