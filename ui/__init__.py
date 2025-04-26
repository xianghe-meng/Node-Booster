# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from .menus import (
    NODEBOOSTER_MT_addmenu_general,
    NODEBOOSTER_MT_textemplate, 
    )

from .panels import (
    NODEBOOSTER_PT_tool_search,
    NODEBOOSTER_PT_tool_color_palette,
    NODEBOOSTER_PT_tool_frame,
    NODEBOOSTER_PT_minimap,
    NODEBOOSTER_PT_shortcuts_memo,
    NODEBOOSTER_PT_active_node,
    )

classes = (

    NODEBOOSTER_MT_addmenu_general,
    NODEBOOSTER_MT_textemplate,
    NODEBOOSTER_PT_tool_search,
    NODEBOOSTER_PT_tool_color_palette,
    NODEBOOSTER_PT_shortcuts_memo,
    NODEBOOSTER_PT_tool_frame,
    NODEBOOSTER_PT_minimap,
    NODEBOOSTER_PT_active_node,

    )


from .menus import append_menus, remove_menus
from ..operators.favorites import draw_favorites_popover_button

def load_ui():

    #add the menus to the nodes shift a menu
    append_menus()

    #add the favorite popover
    bpy.types.NODE_HT_header.append(draw_favorites_popover_button)

    return None

def unload_ui():

    #remove the menus from the nodes shift a menu
    remove_menus()

    #remove the favorite popover
    bpy.types.NODE_HT_header.remove(draw_favorites_popover_button)

    return None
