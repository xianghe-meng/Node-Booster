# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from .minimap import draw_minimap

from ..utils.draw_utils import get_dpifac
from ..customnodes.interpolation.spline2dpreview import draw_interpolation_preview


def get_draw_function_handler(mode='OVERLAY'):
    """function factory for draw functions, overlay or underlay mode.."""
    
    def draw_function():

        # Exit early if we don't have proper context
        context = bpy.context
        if not context:
            return None

        # check if we are in node editor and overlays are enabled
        space_data = context.space_data
        if (not space_data) or (space_data.type!='NODE_EDITOR'):
            return None

        # Get the active node tree
        node_tree = space_data.edit_tree if space_data.edit_tree else space_data.node_tree
        if (not node_tree):
            return None

        # Find the main region
        area = context.area
        window_region = None
        for r in area.regions:
            if (r.type == 'WINDOW'):
                window_region = r
                break
        if (not window_region):
            print("ERROR: draw_minimap(): Could not find 'WINDOW' region in the provided space.")
            return None

        # Get DPI factor
        region = context.region
        view2d = region.view2d
        dpi_fac = get_dpifac()
        zoom = abs((view2d.view_to_region(0, 0, clip=False)[0] - view2d.view_to_region(10, 10, clip=False)[0]) / 10)

        match mode:
            case 'OVERLAY':

                #draw our interpolation preview
                draw_interpolation_preview(node_tree, view2d, dpi_fac, zoom)

                #draw our minimap
                if (context.scene.nodebooster.minimap_draw_type == 'OVERLAY'):
                    draw_minimap(node_tree, area, window_region, view2d, space_data, dpi_fac, zoom)
            
            case 'UNDERLAY':

                #draw our minimap
                if (context.scene.nodebooster.minimap_draw_type == 'UNDERLAY'):
                    draw_minimap(node_tree, area, window_region, view2d, space_data, dpi_fac, zoom)

        return None

    return draw_function


OVELAY_FCT, UNDERLAY_FCT = None, None

def register_gpu_drawcalls():

    if (bpy.app.background) or (bpy.context.window is None):
        return None

    global OVELAY_FCT
    if (OVELAY_FCT is None):
        OVELAY_FCT = bpy.types.SpaceNodeEditor.draw_handler_add(
            get_draw_function_handler(mode='OVERLAY'),
            (), 'WINDOW', 'POST_PIXEL', )

    global UNDERLAY_FCT
    if (UNDERLAY_FCT is None):
        UNDERLAY_FCT = bpy.types.SpaceNodeEditor.draw_handler_add(
            get_draw_function_handler(mode='UNDERLAY'),
            (), 'WINDOW', 'BACKDROP', )

    return None

def unregister_gpu_drawcalls():
    
    global OVELAY_FCT, UNDERLAY_FCT

    if (OVELAY_FCT is not None):
        bpy.types.SpaceNodeEditor.draw_handler_remove(OVELAY_FCT, 'WINDOW')
        OVELAY_FCT = None

    if (UNDERLAY_FCT is not None):
        bpy.types.SpaceNodeEditor.draw_handler_remove(UNDERLAY_FCT, 'WINDOW')
        UNDERLAY_FCT = None

    return None