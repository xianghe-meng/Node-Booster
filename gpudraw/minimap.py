# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# TODO important
# - take into cons panels sides, find why sometimes they are visible sometimes not in theme settings. see the impact on the minimap.
# - navigation system, click to automatically transport view. 
#   implement it via a special shortcut operator?? or a modal. so we detect if touching, automatically? 
#   could even change mouse look on hover, or change side with corner.
# - stress test, optimize code if needed.

# TODO bonus
# - BUG dpi scaling is not perfect. if ui_scale is above 1.35 it starts to jump. unsure why.
# - per area properties? could use a global dict of properties based on area.as_pointer() id. some settings would be per area then (padding size..)
# - support Y favorite star system. draw little stars.
# - support zone repeat/foreach/simulation nodes. API is a mess..
# - per area size! and should be able to resize it by hovering on top/right or corner
# - choose between the 4 locations. minimap_emplacement
# - draw the cursor location in the minimap, as a red point.
# - fixed size vs %, choose between minimap_width_percentage or minimap_width_pixels with a new enum

import bpy
import gpu
import time
import numpy as np
from mathutils import Vector
from math import sin, cos, pi
from gpu_extras.batch import batch_for_shader

from ..__init__ import get_addon_prefs
from ..utils.nbr_utils import map_positions
from ..utils.node_utils import (
    get_node_absolute_location,
    get_node_bounds,
    get_nodes_bounds,
)


#Global dict of minimap bounds being draw, key is the area as_pointer() memory adress as str
MINIMAP_BOUNDS = {}
MINIMAP_VIEWBOUNDS = {}
NAVIGATION_EVENT = {'panning':False,}

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


def draw_minimap(node_tree, area, window_region, view2d, space, dpi_fac, zoom,):
    """draw a minimap of the node_tree in the node_editor area"""

    area_key = str(area.as_pointer())
    scene_sett = bpy.context.scene.nodebooster
    padding = scene_sett.minimap_padding

    # Do we even want to show the minimap?
    if (not node_tree) or \
       (not node_tree.nodes) or \
       (not scene_sett.minimap_show) or \
       (scene_sett.minimap_auto_tool_panel_collapse and (not space.show_region_toolbar)
        ):
        MINIMAP_BOUNDS[area_key] = (Vector((0,0)), Vector((0,0)))
        MINIMAP_VIEWBOUNDS[area_key] = (Vector((0,0)), Vector((0,0)))
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
    
    #the rescaling of the minimap based on user preferences
    rescale_factor = sum(scene_sett.minimap_width_percentage[:])/2

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

    match scene_sett.minimap_auto_aspect_ratio:

        # Auto aspect ratio: Calculate based on node bounds and clamp to max percentages
        case True:
            width_percentage, height_percentage_max = scene_sett.minimap_width_percentage
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

        # Fixed aspect ratio: Use width/height percentages directly
        case False:
            width_percentage, height_percentage = scene_sett.minimap_width_percentage
            minimap_pixel_width = view_width * width_percentage
            minimap_pixel_height = view_height * height_percentage

            # Clamp to available view space minus padding
            minimap_pixel_width = min(minimap_pixel_width, view_width - 2 * padding[0])
            minimap_pixel_height = min(minimap_pixel_height, view_height - 2 * padding[1])

    # 2.2 place the minimap on cornets
    mode = 'BOTTOM_LEFT'
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
        # case 'TOP_LEFT':
        #     pass
        # case 'TOP_RIGHT':
        #     pass
        # case 'BOTTOM_RIGHT':
        #     pass

    # 3. Draw the Minimap Background Rectangle

    bounds_minimap_background = (pixel_bottom_left_bound, pixel_top_right_bound)
    draw_beveled_rectangle(
        bounds_minimap_background,
        fill_color=scene_sett.minimap_fill_color,
        outline_color=scene_sett.minimap_outline_color,
        outline_width=scene_sett.minimap_outline_width,
        border_radius=scene_sett.minimap_border_radius,
        )
    
    # communicate the bounds with the navigation operator
    MINIMAP_BOUNDS[area_key] = bounds_minimap_background
    
    # 3.1 Also get the bouds of the nodetree zone of the minimap 
    # (might not be the same as the minimap bounds if the crop aspect ration is enabled)
    
    bounds_mapping_target = bounds_minimap_background
    
    if (scene_sett.minimap_auto_aspect_ratio==False):

        minimap_aspect = minimap_pixel_width / minimap_pixel_height if minimap_pixel_height > 0 else 1
        nodetree_aspect = node_tree_width / node_tree_height if node_tree_height > 0 else 1

        map_min_x, map_min_y = bounds_minimap_background[0]
        map_max_x, map_max_y = bounds_minimap_background[1]
        target_min_x, target_min_y = map_min_x, map_min_y
        target_max_x, target_max_y = map_max_x, map_max_y

        if abs(minimap_aspect - nodetree_aspect) > 1e-5: # Check if aspect ratios differ significantly
            if minimap_aspect > nodetree_aspect: # Minimap wider than node tree
                target_width = minimap_pixel_height * nodetree_aspect
                offset_x = (minimap_pixel_width - target_width) / 2
                target_min_x = map_min_x + offset_x
                target_max_x = map_max_x - offset_x
            else: # Minimap taller than node tree
                target_height = minimap_pixel_width / nodetree_aspect
                offset_y = (minimap_pixel_height - target_height) / 2
                target_min_y = map_min_y + offset_y
                target_max_y = map_max_y - offset_y
            
            bounds_mapping_target = (Vector((target_min_x, target_min_y)), Vector((target_max_x, target_max_y)))

    # we add padding to the mapping target bounds
    inner_padding = 15,15
    bounds_minimap_nodetree = (
        Vector((bounds_mapping_target[0].x + inner_padding[0], bounds_mapping_target[0].y + inner_padding[1])),
        Vector((bounds_mapping_target[1].x - inner_padding[0], bounds_mapping_target[1].y - inner_padding[1]))
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

    # gather bounds positions and map them 2x bounds loc per node
    all_bounds = [loc for node in all_nodes for loc in get_node_bounds(node)] 
    all_positions = map_positions(np.array(all_bounds), bounds_nodetree, bounds_minimap_nodetree,)

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
            #define header height..
            header_height = scene_sett.minimap_node_header_height
            header_height *= min(1, dezoom_factor) #influeced by dezoom
            header_height *= rescale_factor
            header_height = max(header_height, scene_sett.minimap_node_header_minheight)
            header_color = node_color
            node_color = scene_sett.minimap_node_body_color
                
        #using custom color?
        if (node.use_custom_color and scene_sett.minimap_node_draw_customcolor):
            node_color = (*node.color[:3], 0.9)

        #pack item
        #       0   1        2            3            4               5              6              7
        item = [i, node, node_color, node_bounds, outline_width, outline_color, header_height, header_color,]
        if (node.type == 'FRAME'):
            frame_to_draw.append(item)
            continue
        node_to_draw.append(item)
        continue

    #draw node and frame elements
    for item in frame_to_draw + node_to_draw:
        draw_simple_rectangle(
            item[3],
            fill_color=item[2],
            outline_color=item[5],
            outline_width=item[4],
            header_height=item[6],
            header_color=item[7],
            )
    
    # 5. draw the view zone area

    # 5.1 get the view zone in node space

    # NOTE Getting the view zone translated into node space is complicated..
    # .. as unfortunately the view2d is being offseted by the user resoltution scale
    # view2d.region_to_view() cannot be trusted. We need to reproduce the offsetting behavior
    # with the dpi scale ourselves. try to see the zoom behavior of preferences.ui_scale...

    # Get the first node locations, unafacted by dpi.
    v0_apparent = Vector(view2d.region_to_view(0, 0))
    v1_apparent = Vector(view2d.region_to_view(view_width, view_height))
    center_apparent = Vector(view2d.region_to_view(view_width / 2, view_height / 2))

    # Calculate the apparent span
    span_apparent_vx = v1_apparent.x - v0_apparent.x
    span_apparent_vy = v1_apparent.y - v0_apparent.y

    # Correct the center and span affected my the dpi scale factor
    center_vx = center_apparent.x / dpi_fac
    center_vy = center_apparent.y / dpi_fac
    span_vx = span_apparent_vx / dpi_fac
    span_vy = span_apparent_vy / dpi_fac

    # Calculate the dpi offset.
    view_min_x = center_vx - span_vx / 2
    view_min_y = center_vy - span_vy / 2
    view_max_x = center_vx + span_vx / 2
    view_max_y = center_vy + span_vy / 2

    # 5.2 we remap the view zone to fit the minimap bounds.

    # Map view bounds from node space to minimap pixel space
    bounds_view_nodetree = (Vector((view_min_x, view_min_y)), Vector((view_max_x, view_max_y)))
    mapped_view_bounds = map_positions(
        np.array(bounds_view_nodetree), 
        bounds_nodetree,
        bounds_minimap_nodetree,
        )

    # communicate the bounds with the navigation operator
    MINIMAP_VIEWBOUNDS[area_key] = (Vector(mapped_view_bounds[0]), Vector(mapped_view_bounds[1]))

    # 5.3 we draw the view zone, as a rectangle, line, or as a corner.

    # Check for overlap, when the view is fully within the minimap bounds..
    min_map_x, min_map_y = bounds_minimap_background[0]
    max_map_x, max_map_y = bounds_minimap_background[1]
    
    mapped_view_min_x, mapped_view_min_y = mapped_view_bounds[0]
    mapped_view_max_x, mapped_view_max_y = mapped_view_bounds[1]

    # change minimap color if panning
    if (NAVIGATION_EVENT['panning']==True):
        view_fill = scene_sett.minimap_view_outline_color[:3]+(0.025,)
        view_width = scene_sett.minimap_view_outline_width * 1.75
    else:
        view_fill = scene_sett.minimap_view_fill_color[:]
        view_width = scene_sett.minimap_view_outline_width
    
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
                fill_color=view_fill,
                outline_width=view_width,
                outline_color=scene_sett.minimap_view_outline_color,
                border_radius=scene_sett.minimap_view_border_radius,
                border_sides=7,
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
    
    # # 7. Draw Cursor Indicator
    if False:
        ...
        #TODO later, need to find the API to get the cursor location in node space..
        if scene_sett.minimap_cursor_show:
        
            win_mouse_x = bpy.context.window.mouse_x
            win_mouse_y = bpy.context.window.mouse_y
            mouse_region_x = win_mouse_x - window_region.x
            mouse_region_y = win_mouse_y - window_region.y

            map_min_x, map_min_y = bounds_minimap_background[0]
            map_max_x, map_max_y = bounds_minimap_background[1]

            # Check if mouse coords are valid and inside the minimap bounds
            is_valid = mouse_region_x >= 0 and mouse_region_y >= 0
            is_inside = is_valid and (map_min_x <= mouse_region_x <= map_max_x and
                                    map_min_y <= mouse_region_y <= map_max_y)

            if is_inside:
                draw_circle(
                    center_pos=(mouse_region_x, mouse_region_y),
                    radius=scene_sett.minimap_cursor_radius,
                    color=scene_sett.minimap_cursor_color,
                    segments=12 # Lower segment count for small circle
                    )
    
    return None


# ooooo      ooo                        o8o                           .    o8o                        
# `888b.     `8'                        `"'                         .o8    `"'                        
#  8 `88b.    8   .oooo.   oooo    ooo oooo   .oooooooo  .oooo.   .o888oo oooo   .ooooo.  ooo. .oo.   
#  8   `88b.  8  `P  )88b   `88.  .8'  `888  888' `88b  `P  )88b    888   `888  d88' `88b `888P"Y88b  
#  8     `88b.8   .oP"888    `88..8'    888  888   888   .oP"888    888    888  888   888  888   888  
#  8       `888  d8(  888     `888'     888  `88bod8P'  d8(  888    888 .  888  888   888  888   888  
# o8o        `8  `Y888""8o     `8'     o888o `8oooooo.  `Y888""8o   "888" o888o `Y8bod8P' o888o o888o 
#                                            d"     YD                                                
#                                            "Y88888P'                                                


#NOTE need to clean up this operator, it's a mess.. modals..


class NODEBOOSTER_OT_MinimapInteraction(bpy.types.Operator):
    """Handles mouse interaction within the minimap area."""

    bl_idname = "nodebooster.minimap_interaction"
    bl_label = "Node Booster Minimap Interaction"
    bl_options = {'REGISTER', 'INTERNAL'} # Internal prevents it showing in search

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = None
        self._cursor_modified = None
        self._last_click_time = 0 #for double click
        self._second_last_click_time = 0 # for triple click
        self._action_rescaling_edge = None
        self._is_panning = False
        self._pan_start_mouse = None
        self._last_mouse_pos = None
        self._clicks = []

    def find_region_under_mouse(self, context, event):

        found_area, found_region, region_mouse_x, region_mouse_y = None, None, 0, 0

        for area in context.window.screen.areas:

            # Is mouse within this area's bounds?
            if (area.x <= event.mouse_x < area.x + area.width and
                area.y <= event.mouse_y < area.y + area.height):

                # Is it a Node Editor?
                if (area.type == 'NODE_EDITOR'):
                    for region in area.regions:

                        # Is mouse within this region's bounds?
                        if (region.x <= event.mouse_x < region.x + region.width and
                            region.y <= event.mouse_y < region.y + region.height):
                            
                            # Is it the main Window region?
                            if (region.type == 'WINDOW'):
                                found_area = area
                                found_region = region
                                region_mouse_x = event.mouse_x - region.x
                                region_mouse_y = event.mouse_y - region.y
                                # Found the correct region in this area
                                break

                    # Found the correct area and region
                    if (found_region):
                        break

        return found_area, found_region, region_mouse_x, region_mouse_y
                        
                        
    def restore_cursor(self, context):
        if (self._cursor_modified is not None):
            context.window.cursor_modal_restore()
            self._cursor_modified = None
        return None

    def modal(self, context, event):

        win_sett = context.window_manager.nodebooster
        scene_sett = context.scene.nodebooster

        # Stop condition, we ONLY do that when this boolean is toggled off. 
        # this modal is always active, except if the user manually disables it.

        if (not win_sett.minimap_modal_operator_is_active):
            self.cancel(context)
            print("Minimap interaction modal stopped.")
            return {'CANCELLED'}

        # deduce region and area from window mouse position.
        area, region, mouse_x, mouse_y = self.find_region_under_mouse(context, event)
        if (area is None or region is None):
            self.restore_cursor(context)
            NAVIGATION_EVENT['panning'] = False
            # Reset panning if mouse leaves the area
            if self._is_panning:
                self._is_panning = False
                self._pan_start_mouse = None
                self._last_mouse_pos = None
            return {'PASS_THROUGH'}
        
        area_key = str(area.as_pointer())
        current_mouse_pos = Vector((mouse_x, mouse_y))

        # Triple click event - View All (CHECK THIS FIRST!)
        is_third_click = False
        if (event.type == 'LEFTMOUSE' and event.value == 'PRESS'): # Check Press again for click timing
            current_time = time.time()
            click_threshold = 0.2 # seconds
            self._clicks.append(current_time)
            if (len(self._clicks)>3):
                if (self._clicks[-1] - self._clicks[-2] < click_threshold) and (self._clicks[-2] - self._clicks[-3] < click_threshold):
                    is_third_click = True

        # Handle Panning Gesture
        if (self._is_panning):
            if (event.type == 'MOUSEMOVE'):
                if (self._last_mouse_pos and area_key in MINIMAP_VIEWBOUNDS):
                    view_min_screen, view_max_screen = MINIMAP_VIEWBOUNDS[area_key]
                    view_rect_width_screen = view_max_screen.x - view_min_screen.x
                    view_rect_height_screen = view_max_screen.y - view_min_screen.y

                    zoom_x = region.width / view_rect_width_screen if view_rect_width_screen > 1e-5 else 0
                    zoom_y = region.height / view_rect_height_screen if view_rect_height_screen > 1e-5 else 0

                    mouse_move_delta = current_mouse_pos - self._last_mouse_pos

                    pan_delta_x = mouse_move_delta.x * zoom_x
                    pan_delta_y = mouse_move_delta.y * zoom_y

                    if abs(pan_delta_x) > 0 or abs(pan_delta_y) > 0:
                        with context.temp_override(area=area, region=region):
                            bpy.ops.view2d.pan(deltax=round(pan_delta_x), deltay=round(pan_delta_y))

                    self._last_mouse_pos = current_mouse_pos
                return {'RUNNING_MODAL'}

            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self._is_panning = False
                NAVIGATION_EVENT['panning'] = False
                self._pan_start_mouse = None
                self._last_mouse_pos = None
                # Cursor restoration will be handled below based on position
                # Force redraw to update view if needed
                area.tag_redraw()
                # Re-evaluate cursor state immediately after stopping pan
                # Fall through to the cursor check logic below

            elif event.type == 'ESC': # Cancel panning on ESC
                 self._is_panning = False
                 self._pan_start_mouse = None
                 self._last_mouse_pos = None
                 self.restore_cursor(context)
                 NAVIGATION_EVENT['panning'] = False
                 area.tag_redraw()
                 return {'RUNNING_MODAL'}

        #handle rescaling gesture
        if (self._action_rescaling_edge is not None):
            
            #quit gesture?
            if (event.type == 'LEFTMOUSE' and event.value == 'RELEASE'):
                self._action_rescaling_edge = None
                print("Rescaling finished")
                return {'RUNNING_MODAL'}
            
            #get some minimap info
            min_b, max_b = MINIMAP_BOUNDS[str(area.as_pointer())]
            minimap_width = max_b.x - min_b.x
            minimap_height = max_b.y - min_b.y
            aspect_ratio = 'VERTICAL' if (minimap_width / minimap_height < 1) else 'HORIZONTAL'
            
            #get movement direction info and determine the movements ratio

            direction = self._action_rescaling_edge['direction']
            match direction:
                case 'TOP':
                    axis = 1
                    start_pos = self._action_rescaling_edge['start_mouse'][1]
                    current_pos = mouse_y
                    target_pos = MINIMAP_BOUNDS[str(area.as_pointer())][0][1]
                    ratio = 1 - (current_pos - start_pos) / (target_pos - start_pos)
                case 'RIGHT':
                    axis = 0
                    start_pos = self._action_rescaling_edge['start_mouse'][0]
                    current_pos = mouse_x
                    target_pos = MINIMAP_BOUNDS[str(area.as_pointer())][0][0]
                    ratio = 1 - (current_pos - start_pos) / (target_pos - start_pos)
            
            # assign the value depending on the aspect ratio

            if (scene_sett.minimap_auto_aspect_ratio):
                axis = 0 if (aspect_ratio=='HORIZONTAL') else 1
            start_value = self._action_rescaling_edge['start_value'][axis]
            new_value = start_value * ratio

            if (scene_sett.minimap_auto_aspect_ratio):
                  scene_sett.minimap_width_percentage = new_value, new_value
            else: scene_sett.minimap_width_percentage[axis] = new_value
            
            #give it a redraw kick
            area.tag_redraw()
            
            # print(f'start_pos: {start_pos}, current_pos: {current_pos}, target_pos: {target_pos}, ratio: {ratio}')
            return {'RUNNING_MODAL'}
        
        #special case for pan passthrough (if not already panning)
        if (not self._is_panning and event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE','T','N',}):
            self.restore_cursor(context)
            return {'PASS_THROUGH'}

        #check if the cursor is hovering

        is_on_edge = None
        is_over_minimap = False

        if (area_key in MINIMAP_BOUNDS):
            min_b, max_b = MINIMAP_BOUNDS[area_key]

            # hovering on the minimap?
            is_over_minimap = (min_b.x <= mouse_x <= max_b.x and
                               min_b.y <= mouse_y <= max_b.y)
            # hovering on it's edge (only top/right for resizing)?
            if (is_over_minimap and not self._is_panning): # Only check edge if over and not panning
                if ((-5.5 <= max_b.y - mouse_y <= 5.5)):
                    is_on_edge = 'TOP'
                elif ((-5.5 <= max_b.x - mouse_x <= 5.5)):
                    is_on_edge = 'RIGHT'

        # Update Cursor style (only if not panning, panning cursor is set during pan start)
        if not self._is_panning:
            if (is_on_edge == 'TOP'):
                if (self._cursor_modified != 'MOVE_Y'):
                    context.window.cursor_modal_set('MOVE_Y')
                    self._cursor_modified = 'MOVE_Y'
            elif (is_on_edge == 'RIGHT'):
                if (self._cursor_modified != 'MOVE_X'):
                    context.window.cursor_modal_set('MOVE_X')
                    self._cursor_modified = 'MOVE_X'
            elif (is_over_minimap):
                if (self._cursor_modified != 'HAND'):
                    context.window.cursor_modal_set('HAND') # Use HAND for potential pan
                    self._cursor_modified = 'HAND'
            else:
                self.restore_cursor(context)

        # Initiate or launch an action from events..

        if (is_on_edge and not self._is_panning): # Only allow resize start if not panning

            # Click event.
            if (event.type == 'LEFTMOUSE' and event.value == 'PRESS'):
                print("User want to resize the minimap.")
                self._action_rescaling_edge = {
                    'direction': is_on_edge,
                    'start_mouse':(mouse_x, mouse_y),
                    'start_value':scene_sett.minimap_width_percentage[:],
                    }
                return {'RUNNING_MODAL'}

            return {'RUNNING_MODAL'}

        elif (is_over_minimap): # Only allow pan/zoom start if not panning/resizing

            if is_third_click:
                print("Triple click detected - running view_all()")
                with context.temp_override(area=area, region=region):
                    bpy.ops.node.view_all()
                # Reset click times fully to prevent immediate re-triggering
                self._last_click_time = 0
                self._second_last_click_time = 0
                # Consume the event after triple click
                return {'RUNNING_MODAL'}

            # Click event - Initiate Panning (Only if not a triple click)
            # Check press again, and ensure it wasn't just consumed by triple click logic
            if (event.type == 'LEFTMOUSE' and event.value == 'PRESS'):
                # We already updated click times above, check if it was the *first* click in a potential sequence
                # by seeing if second_last_click_time was reset by a successful triple click or is still 0
                #is_potentially_first_click = (self._second_last_click_time == 0 and self._last_click_time != 0)

                if area_key in MINIMAP_VIEWBOUNDS:
                    view_min_screen, view_max_screen = MINIMAP_VIEWBOUNDS[area_key]
                    view_rect_width_screen = view_max_screen.x - view_min_screen.x
                    view_rect_height_screen = view_max_screen.y - view_min_screen.y

                    # Check if view bounds are valid before starting pan
                    if view_rect_width_screen > 1e-5 and view_rect_height_screen > 1e-5:
                        zoom_x = region.width / view_rect_width_screen
                        zoom_y = region.height / view_rect_height_screen

                        view_center_screen = (view_min_screen + view_max_screen) / 2.0

                        delta_x = (current_mouse_pos.x - view_center_screen.x) * zoom_x
                        delta_y = (current_mouse_pos.y - view_center_screen.y) * zoom_y

                        # Perform initial pan to center on the clicked point
                        with context.temp_override(area=area, region=region):
                            bpy.ops.view2d.pan(deltax=round(delta_x), deltay=round(delta_y))

                        self._is_panning = True
                        NAVIGATION_EVENT['panning'] = True
                        self._pan_start_mouse = current_mouse_pos
                        self._last_mouse_pos = current_mouse_pos
                        context.window.cursor_modal_set('SCROLL_XY') # Set pan cursor
                        self._cursor_modified = 'SCROLL_XY'
                        print("Minimap panning started.")
                        area.tag_redraw()
                        # Reset click times because we started panning
                        self._last_click_time = 0
                        self._second_last_click_time = 0
                        return {'RUNNING_MODAL'}
                    else:
                        print("Minimap pan failed: Invalid view bounds.")
                        # Reset click times if pan failed
                        self._last_click_time = 0
                        self._second_last_click_time = 0
                # elif is_potentially_first_click: # Failed because area_key not in MINIMAP_VIEWBOUNDS
                #     print("Minimap pan failed: View bounds not found.")
                #     # Reset click times if pan failed
                #     self._last_click_time = 0
                #     self._second_last_click_time = 0
                # If not is_potentially_first_click, it means it was the 2nd click,
                # or triple click logic handled it, so we don't start panning.

            # If we get here, it was either not a LEFTMOUSE press, or it was handled
            # (triple click) or failed to start panning, or was a 2nd click.
            return {'RUNNING_MODAL'}

        # Allow other events (keyboard shortcuts, etc.) to pass through if not handled above
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
            
        # Initialize cursor state flag
        self._cursor_modified = False

        # initialize a timr
        if (self._timer is None):
            self._timer = context.window_manager.event_timer_add(0.05, window=context.window) # Check frequently
        context.window_manager.modal_handler_add(self)

        print("Minimap interaction modal started.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):

        # Ensure cursor is restored on cancellation
        self.restore_cursor(context)
        
        # Reset internal states
        self._is_panning = False
        NAVIGATION_EVENT['panning'] = False
        self._action_rescaling_edge = None

        # Clean up timer when the modal stops
        if (self._timer):
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        
        print("Minimap interaction modal cancelled.")
        return None


