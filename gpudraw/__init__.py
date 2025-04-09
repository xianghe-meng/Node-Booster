# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from ..utils.draw_utils import get_dpifac
from ..customnodes.interpolation.spline2dpreview import draw_interpolation_preview


def draw_nodeeditor_overlay():
    
    # Exit early if we don't have proper context
    if not bpy.context:
        return None

    # check if we are in node editor and overlays are enabled
    space = bpy.context.space_data
    if (not space) or (space.type!='NODE_EDITOR'):
        return None
        
    # Get the active node tree
    node_tree = space.edit_tree if space.edit_tree else space.node_tree
    if (not node_tree):
        return None


    # Get DPI factor
    dpi_fac = get_dpifac()
    view2d = bpy.context.region.view2d
    zoom = abs((view2d.view_to_region(0, 0, clip=False)[0] - view2d.view_to_region(10, 10, clip=False)[0]) / 10)

    #draw our interpolation preview
    draw_interpolation_preview(node_tree, view2d, dpi_fac, zoom)

    return None


DRAW_HANDLER = None

def register_gpu_drawcalls():
    
    if (bpy.app.background) or (bpy.context.window is None):
        return None
    
    global DRAW_HANDLER
    
    if (DRAW_HANDLER is None):
        DRAW_HANDLER = bpy.types.SpaceNodeEditor.draw_handler_add(
            draw_nodeeditor_overlay, (), 'WINDOW', 'POST_PIXEL'
            )
    
    return None

def unregister_gpu_drawcalls():
    
    global DRAW_HANDLER
    
    if (DRAW_HANDLER is not None):
        bpy.types.SpaceNodeEditor.draw_handler_remove(DRAW_HANDLER, 'WINDOW')
        DRAW_HANDLER = None
    
    return None