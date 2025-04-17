# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# TODO important
# - BUGFIX view bounds is buggy and i'm unsure why.. API region_to_view is problematic?
# - take into cons panels sides, find why sometimes they are visible sometimes not in theme settings. see the impact on the minimap.
# - navigation system, click to automatically transport view. 
#   implement it via a special shortcut operator?? or a modal. so we detect if touching, automatically? 
#   could even change mouse look on hover, or change side with corner.
# - stress test, optimize code if needed.

# TODO bonus
# - per area properties? could use a global dict of properties based on area.as_pointer() id. some settings would be per area then (padding size..)
# - support Y favorite star system. draw little stars.
# - support zone repeat/foreach/simulation nodes. API is a mess..
# - per area size! and should be able to resize it by hovering on top/right or corner
# - choose between the 4 locations. minimap_emplacement
# - draw the cursor location in the minimap, as a red point.


import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np
from mathutils import Vector
from math import sin, cos, pi

from ..utils.nbr_utils import map_positions
from ..utils.node_utils import (
    get_node_absolute_location,
    get_node_bounds,
    get_nodes_bounds,
)


#Global dict of minimap bounds being draw, key is the area as_pointer() memory adress as str
MINIMAP_BOUNDS = {}

COLOR_TAG_TO_THEME_API = {
    'NONE':'group_socket_node',
    'ATTRIBUTE':'attribute_node',
    'COLOR':'color_node',
    'CONVERTER':'converter_node',
    'DISTORT':'distor_node',
    'FILTER':'filter_node',
    'GEOMETRY':'geometry_node',
    'INPUT':'input_node',
    'MATTE':'matte_node',
    'OUTPUT':'output_node',
    'SCRIPT':'script_node',
    'SHADER':'shader_node',
    'TEXTURE':'texture_node',
    'VECTOR':'vector_node',
    'PATTERN':'pattern_node',
    'INTERFACE':'group_socket_node',
    'GROUP':'group_node',
    #'FOREACH':
    #'SIMULATION':
    #'REPEAT':
}

def get_theme_color(node):
    """get the color of the node from the theme"""

    user_theme = bpy.context.preferences.themes.get('Default')
    node_theme = user_theme.node_editor

    color = tuple(getattr(node_theme, COLOR_TAG_TO_THEME_API[node.color_tag]))
    if len(color) == 3:
        color = (*color, 1.0)

    return color

# ooooooooo.                           .                                    oooo            
# `888   `Y88.                       .o8                                    `888            
#  888   .d88'  .ooooo.   .ooooo.  .o888oo  .oooo.   ooo. .oo.    .oooooooo  888   .ooooo.  
#  888ooo88P'  d88' `88b d88' `"Y8   888   `P  )88b  `888P"Y88b  888' `88b   888  d88' `88b 
#  888`88b.    888ooo888 888         888    .oP"888   888   888  888   888   888  888ooo888 
#  888  `88b.  888    .o 888   .o8   888 . d8(  888   888   888  `88bod8P'   888  888    .o 
# o888o  o888o `Y8bod8P' `Y8bod8P'   "888" `Y888""8o o888o o888o `8oooooo.  o888o `Y8bod8P' 
#                                                                d"     YD                  
#                                                                "Y88888P'                  

def draw_beveled_rectangle(bounds,
    fill_color=(0.1, 0.1, 0.1, 0.8),
    outline_color=None,
    outline_width=0,
    border_radius=0,
    border_sides='AUTO',
    ):
    """Draw a filled rectangle an optional outline and border radius. expected a bound in location bottom left and top right"""
    original_blend = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')

    x1, y1 = bounds[0]
    x2, y2 = bounds[1]
    width, height = x2 - x1, y2 - y1

    if ((width <= 0) or (height <= 0)):
        return # Cannot draw zero or negative size rectangle

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    radius = border_radius
    if (border_sides == 'AUTO'):
        border_sides = max(3,int(radius/1.2))
    segments_per_corner = max(1,border_sides // 4)
    total_verts = (segments_per_corner + 1) * 4

    fill_verts = []
    outline_verts = []

    # Calculate vertices for the rounded corners and straight edges
    corners = [
        (x1 + radius, y1 + radius, pi, 3 * pi / 2),     # Bottom Left
        (x2 - radius, y1 + radius, 3 * pi / 2, 2 * pi), # Bottom Right
        (x2 - radius, y2 - radius, 0, pi / 2),          # Top Right
        (x1 + radius, y2 - radius, pi / 2, pi)          # Top Left
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
    if (outline_color and (outline_width > 0)):
        
        gpu.state.line_width_set(outline_width)

        # Close the outline loop
        if (outline_verts):
            outline_verts.append(outline_verts[0])

        shader.uniform_float("color", outline_color)
        batch_outline = batch_for_shader(shader, 'LINE_STRIP', {"pos": outline_verts})
        batch_outline.draw(shader)
        gpu.state.line_width_set(1.0) # Reset line width

    # Restore State
    gpu.state.blend_set(original_blend)
    
    return None


def draw_line(point1, point2, color, width):
    """Draw a simple line between two points."""

    original_blend = gpu.state.blend_get()
    original_line_width = gpu.state.line_width_get()

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.uniform_float("color", color)
    batch = batch_for_shader(shader, 'LINES', {"pos": [point1, point2]})
    batch.draw(shader)

    # Restore state
    gpu.state.line_width_set(original_line_width)
    gpu.state.blend_set(original_blend)

    return None


def draw_spline(points, color, width):
    """Draw a spline between two points."""

    return None


def draw_simple_rectangle(bounds,
    fill_color=(0.1, 0.1, 0.1, 0.8),
    outline_color=None,
    outline_width=0,
    header_height=None,
    header_color=None,
    ):
    """Draw a filled rectangle an optional outline and colored header. expected a bound in location bottom left and top right"""

    original_blend = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')

    x1, y1 = bounds[0]
    x2, y2 = bounds[1]
    width, height = x2 - x1, y2 - y1

    if ((width <= 0) or (height <= 0)):
        return # Cannot draw zero or negative size rectangle

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    # Fill
    vertices = ((x1, y1), (x2, y1), (x1, y2), (x2, y2),)
    indices = ((0, 1, 2), (1, 3, 2),)
    shader.uniform_float("color", fill_color)
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    batch.draw(shader)

    # Header?
    if (header_height and (header_height > 0) and header_color):

        # Fill
        header_y = y2 - header_height
        vertices = ((x1, header_y), (x2, header_y), (x1, y2), (x2, y2),)
        indices = ((0, 1, 2), (1, 3, 2),)
        shader.uniform_float("color", header_color)
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        batch.draw(shader)

    # Outline?
    if (outline_color and (outline_width > 0)):

        # Note: Simple line drawing, width isn't accurate pixel width
        gpu.state.line_width_set(outline_width)
        outline_vertices = ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1),)
        shader.uniform_float("color", outline_color)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": outline_vertices})
        batch.draw(shader)
        gpu.state.line_width_set(1.0) # Reset line width

    # Restore State
    gpu.state.blend_set(original_blend)

    return None

def draw_circle(center_pos, radius, color, segments=16):
    
    original_blend = gpu.state.blend_get()
    gpu.state.blend_set('ALPHA')

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    verts = [center_pos]
    for i in range(segments + 1):
        angle = 2 * pi * i / segments
        verts.append((center_pos[0] + cos(angle) * radius, center_pos[1] + sin(angle) * radius))

    shader.uniform_float("color", color)
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
    batch.draw(shader)

    gpu.state.blend_set(original_blend)

    return None


# ooo        ooooo  o8o               o8o                                         
# `88.       .888'  `"'               `"'                                         
#  888b     d'888  oooo  ooo. .oo.   oooo  ooo. .oo.  .oo.    .oooo.   oo.ooooo.  
#  8 Y88. .P  888  `888  `888P"Y88b  `888  `888P"Y88bP"Y88b  `P  )88b   888' `88b 
#  8  `888'   888   888   888   888   888   888   888   888   .oP"888   888   888 
#  8    Y     888   888   888   888   888   888   888   888  d8(  888   888   888 
# o8o        o888o o888o o888o o888o o888o o888o o888o o888o `Y888""8o  888bod8P' 
#                                                                       888       
#                                                                      o888o      


def draw_minimap(node_tree, area, window_region, view2d, dpi_fac, zoom, 
    mode='BOTTOM_LEFT',):
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
    bounds_nodetree = get_nodes_bounds(node_tree.nodes)
    bound_nodetree_bottomleft, bound_nodetree_topright = bounds_nodetree
    node_tree_width = bound_nodetree_topright.x - bound_nodetree_bottomleft.x
    node_tree_height = bound_nodetree_topright.y - bound_nodetree_bottomleft.y

    #zero width/height? must be error..
    if ((node_tree_width <= 0) or (node_tree_height <= 0)):
        print(f"ERROR: draw_minimap(): node_tree_width or node_tree_height is less than 0: {node_tree_width}, {node_tree_height}")
        return None

    # 2. Calculate the minimap View Area
    
    view_bottom, view_left = 0, 0
    view_width, view_height = window_region.width, window_region.height

    #calculate the minimap aspect ratio
    aspect_ratio = node_tree_width / node_tree_height

    #arbitrary number between 0-1 that scales down when when dezoomed. 1 if zoom in level is ok
    dezoom_factor = min(1, (view_width / node_tree_width) /2)

    # Account side panel widths if they are visible?
    if False:
        ...
        #TODO need to find which theme option is drawing these panels transparently or not first..
        if (space.show_region_toolbar):
            toolbar_region = next((r for r in space.regions if r.type == 'TOOLS'), None)
            if (toolbar_region):
                view_left += toolbar_region.width
                view_width -= toolbar_region.width
        if (space.show_region_ui):
            ui_region = next((r for r in space.regions if r.type == 'UI'), None)
            if (ui_region):
                view_width -= ui_region.width # UI panel is typically on the right

    # 2.1 Calculate Minimap Dimensions and Position in Pixel Space

    # minimap dimension change depending on aspect ratio..
    # recalculate Dimensions based on Width and Max Height Percentages
    _target_width = view_width * width_percentage
    _target_height = _target_width / aspect_ratio
    _max_allowed_height = view_height * height_percentage_max

    if (_target_height <= _max_allowed_height):
        # Height constraint is met, use target width and calculated height
        minimap_pixel_width = _target_width
        minimap_pixel_height = _target_height
    else:
        # Height constraint exceeded, clamp height and recalculate width
        minimap_pixel_height = _max_allowed_height
        minimap_pixel_width = minimap_pixel_height * aspect_ratio

    # Ensure width doesn't exceed available view width (safety clamp)
    minimap_pixel_width = min(minimap_pixel_width, view_width - 2 * padding[0])
    
    # ensure height is adaptive if width was clamped..
    minimap_pixel_height = minimap_pixel_width / aspect_ratio

    # 2.2 place the minimap on cornets
    match mode:
        case 'BOTTOM_LEFT':
            #bound bottom left
            x = view_left + padding[0]
            y = view_bottom + padding[1]
            pixel_bottom_left_bound = Vector((x, y))
            #bound top right
            x = pixel_bottom_left_bound.x + minimap_pixel_width
            y = pixel_bottom_left_bound.y + minimap_pixel_height
            pixel_top_right_bound = Vector((x, y))

        case 'TOP_LEFT':
            pass
            # TODO
            # pixel_bottom_left_x = view_left + padding
            # pixel_bottom_left_y = view_height - minimap_pixel_height - padding

        case 'TOP_RIGHT':
            pass
            # TODO
            # pixel_bottom_left_x = view_left + view_width - minimap_pixel_width - padding
            # pixel_bottom_left_y = view_height - minimap_pixel_height - padding

        case 'BOTTOM_RIGHT':
            pass
            # TODO
            # pixel_bottom_left_x = view_left + view_width - minimap_pixel_width - padding
            # pixel_bottom_left_y = view_bottom + padding

    # 3. Draw the Minimap Background Rectangle
    bounds_area = (pixel_bottom_left_bound, pixel_top_right_bound)
    draw_beveled_rectangle(
        bounds_area,
        fill_color=scene_sett.minimap_fill_color,
        outline_color=scene_sett.minimap_outline_color,
        outline_width=scene_sett.minimap_outline_width,
        border_radius=scene_sett.minimap_border_radius,
        )

    # 4. draw nodes within minimap

    all_nodes = node_tree.nodes[:]

    # gather all nodes types for header color
    user_theme = bpy.context.preferences.themes.get('Default')
    node_theme = user_theme.node_editor
    active_theme = node_theme.node_active[:3] + (1,)
    select_theme = node_theme.node_selected[:3] + (1,)
    all_colors = [get_theme_color(n) for n in all_nodes]

    # gather select states
    all_select_states = [n.select for n in all_nodes]
    all_active_states = [n == node_tree.nodes.active for n in all_nodes]

    # we add padding to the bounds
    inner_padding = 15,15
    bounds_area_clamp = (
        Vector((bounds_area[0].x + inner_padding[0], bounds_area[0].y + inner_padding[1])),
        Vector((bounds_area[1].x - inner_padding[0], bounds_area[1].y - inner_padding[1]))
        )

    # gather bounds positions and map them
    all_bounds = [loc for node in all_nodes for loc in get_node_bounds(node, dimension_factor=scene_sett.minimap_node_dimension_factor)] #flatten. will be 2x the length
    all_positions = map_positions(np.array(all_bounds), bounds_nodetree, bounds_area_clamp,)

    # sort the element we are going to draw arranged with their draw args as well..
    frame_to_draw, node_to_draw = [], []

    for i in range(len(all_nodes)):        

        node = all_nodes[i]

        #we skip reroutes..
        if (node.type =='REROUTE'):
            continue

        #get the node main color
        node_color = all_colors[i]
        # does the user allows to draw a custom color tho?
        if (not scene_sett.minimap_node_draw_typecolor):
            node_color = scene_sett.minimap_node_body_color

        #special color if muted
        if (node.mute):
            node_color = (*node_color[:3], 0.15)
        #special color for frame, their alpha is faded..
        if (node.type == 'FRAME'):
            node_color = (*node_color[:3], 0.4)

        #selectin states
        select = all_select_states[i]
        active = all_active_states[i]
        if (not scene_sett.minimap_node_draw_selection):
            select = select and active

        #get bounds
        node_bounds = all_positions[i*2], all_positions[i*2+1]

        #define outline
        outline_width = scene_sett.minimap_node_outline_width if (select) else 0
        outline_color = active_theme if (active) else select_theme if (select) else None

        #header drawing?
        header_height, header_color = None, None
        if ((scene_sett.minimap_node_draw_header) and (not node.hide) and (node.type!='FRAME')):
            header_height = max(scene_sett.minimap_node_header_height * min(1, dezoom_factor), scene_sett.minimap_node_header_minheight)
            header_color = node_color
            node_color = scene_sett.minimap_node_body_color
                
        #using custom color?
        if (node.use_custom_color and scene_sett.minimap_node_draw_customcolor):
            node_color = (*node.color[:3], 0.9)

        #pack item
        item = [i, node, node_color, node_bounds, outline_width, outline_color, header_height, header_color,]

        if (node.type == 'FRAME'):
            frame_to_draw.append(item)
            continue
        node_to_draw.append(item)
        continue

    #draw node and frame elements
    for item in frame_to_draw + node_to_draw:
        #[i, node, node_color, node_bounds, outline_width, outline_color, header_height, header_color]
        # 0   1       2            3            4               5               6               7
        draw_simple_rectangle(
            item[3],
            fill_color=item[2],
            outline_color=item[5],
            outline_width=item[4],
            header_height=item[6],
            header_color=item[7],
            )
        
    # 5. draw the view zone area

    # Get view bounds in node space
    view_min_x, view_min_y = view2d.region_to_view(view_left, view_bottom)
    view_max_x, view_max_y = view2d.region_to_view(view_left + view_width, view_bottom + view_height)
    bounds_view_nodetree = (Vector((view_min_x, view_min_y)), Vector((view_max_x, view_max_y)))

    # Map view bounds from node space to minimap pixel space
    mapped_view_bounds = map_positions(
        np.array(bounds_view_nodetree), 
        bounds_nodetree,
        bounds_area,
        )

    # Check for overlap, when the view is fully within the minimap bounds..
    min_map_x, min_map_y = bounds_area[0]
    max_map_x, max_map_y = bounds_area[1]
    
    mapped_view_min_x, mapped_view_min_y = mapped_view_bounds[0]
    mapped_view_max_x, mapped_view_max_y = mapped_view_bounds[1]

    #overlapping, we draw the view rectangle!
    if (mapped_view_max_x > min_map_x and
        mapped_view_min_x < max_map_x and
        mapped_view_max_y > min_map_y and
        mapped_view_min_y < max_map_y):

        # Clamp the mapped view bounds to the minimap area
        clamped_view_min_x = max(min_map_x, mapped_view_min_x)
        clamped_view_min_y = max(min_map_y, mapped_view_min_y)
        clamped_view_max_x = min(max_map_x, mapped_view_max_x)
        clamped_view_max_y = min(max_map_y, mapped_view_max_y)

        # Ensure valid bounds after clamping
        if clamped_view_max_x > clamped_view_min_x and clamped_view_max_y > clamped_view_min_y:
            
            bounds_view_minimap = (
                (clamped_view_min_x, clamped_view_min_y),
                (clamped_view_max_x, clamped_view_max_y),
                )
            draw_beveled_rectangle(
                bounds_view_minimap,
                fill_color=scene_sett.minimap_view_fill_color,
                outline_color=scene_sett.minimap_view_outline_color,
                outline_width=scene_sett.minimap_view_outline_width,
                border_radius=scene_sett.minimap_view_border_radius,
                border_sides=6,
                )
    else:
        # No overlap: Draw collapsed lines on the border

        is_fully_left  = mapped_view_max_x <= min_map_x
        is_fully_right = mapped_view_min_x >= max_map_x
        is_fully_below = mapped_view_max_y <= min_map_y
        is_fully_above = mapped_view_min_y >= max_map_y

        corner_lines = None
        corner_lines_lenght = min(max_map_x - min_map_x, max_map_y - min_map_y) * 0.1 #min(map_width, map_height)

        # The bounding box is fully on corners?
        if (is_fully_left and is_fully_above): # Top Left Corner
            line1 = (min_map_x, max_map_y - corner_lines_lenght), (min_map_x, max_map_y)
            line2 = (min_map_x, max_map_y), (min_map_x + corner_lines_lenght, max_map_y)
            corner_lines = (line1, line2)

        elif (is_fully_right and is_fully_above): # Top Right Corner
            line1 = (max_map_x, max_map_y - corner_lines_lenght), (max_map_x, max_map_y)
            line2 = (max_map_x - corner_lines_lenght, max_map_y), (max_map_x, max_map_y)
            corner_lines = (line1, line2)

        elif (is_fully_left and is_fully_below): # Bottom Left Corner
            line1 = (min_map_x, min_map_y), (min_map_x, min_map_y + corner_lines_lenght)
            line2 = (min_map_x, min_map_y), (min_map_x + corner_lines_lenght, min_map_y)
            corner_lines = (line1, line2)

        elif (is_fully_right and is_fully_below): # Bottom Right Corner
            line1 = (max_map_x, min_map_y), (max_map_x, min_map_y + corner_lines_lenght)
            line2 = (max_map_x - corner_lines_lenght, min_map_y), (max_map_x, min_map_y)
            corner_lines = (line1, line2)
        
        if (corner_lines is not None):
            for line in corner_lines:
                draw_line(
                    *line,
                    scene_sett.minimap_view_outline_color,
                    scene_sett.minimap_view_outline_width,
                    )

        # The view box is fully on sides?
        if (corner_lines is None):

            # Clamp coordinates for line extent calculation
            y1_c, y2_c = max(min_map_y, mapped_view_min_y), min(max_map_y, mapped_view_max_y)
            x1_c, x2_c = max(min_map_x, mapped_view_min_x), min(max_map_x, mapped_view_max_x)

            lines = []
            if (is_fully_left and y2_c > y1_c):  lines.append([(min_map_x, y1_c), (min_map_x, y2_c)])
            if (is_fully_right and y2_c > y1_c): lines.append([(max_map_x, y1_c), (max_map_x, y2_c)])
            if (is_fully_below and x2_c > x1_c): lines.append([(x1_c, min_map_y), (x2_c, min_map_y)])
            if (is_fully_above and x2_c > x1_c): lines.append([(x1_c, max_map_y), (x2_c, max_map_y)])

            for line in lines:
                draw_line(
                    *line,
                    scene_sett.minimap_view_outline_color,
                    scene_sett.minimap_view_outline_width,
                    )

    # NOTE store the minimap bounds in a global dict. 
    # might need to be accessed by other tools..
    MINIMAP_BOUNDS[str(area.as_pointer())] = (pixel_bottom_left_bound, pixel_top_right_bound)
    
    # # 7. Draw Cursor Indicator
    # TODO later, need to find the API to get the cursor location in node space..
    # if scene_sett.minimap_cursor_show:
    
    #     win_mouse_x = bpy.context.window.mouse_x
    #     win_mouse_y = bpy.context.window.mouse_y
    #     mouse_region_x = win_mouse_x - window_region.x
    #     mouse_region_y = win_mouse_y - window_region.y

    #     map_min_x, map_min_y = bounds_area[0]
    #     map_max_x, map_max_y = bounds_area[1]

    #     # Check if mouse coords are valid and inside the minimap bounds
    #     is_valid = mouse_region_x >= 0 and mouse_region_y >= 0
    #     is_inside = is_valid and (map_min_x <= mouse_region_x <= map_max_x and
    #                                map_min_y <= mouse_region_y <= map_max_y)

    #     if is_inside:
    #         draw_circle(
    #             center_pos=(mouse_region_x, mouse_region_y),
    #             radius=scene_sett.minimap_cursor_radius,
    #             color=scene_sett.minimap_cursor_color,
    #             segments=12 # Lower segment count for small circle
    #         )
    
    return None
