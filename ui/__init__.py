# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy

from .menus import (
    #NOTE: menu is doing some procedural submenu cls registering
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
    NODEBOOSTER_MT_textemplate,
    NODEBOOSTER_PT_tool_search,
    NODEBOOSTER_PT_tool_color_palette,
    NODEBOOSTER_PT_shortcuts_memo,
    NODEBOOSTER_PT_tool_frame,
    NODEBOOSTER_PT_minimap,
    NODEBOOSTER_PT_active_node,
    )

from .menus import append_menus, remove_menus
from ..operators.favorites import favorite_popover_draw_header
from ..operators.stringswitch import draw_string_switch_context_menu

def load_ui():

    #add the menus to the nodes shift a menu
    append_menus()

    #add the favorite popover
    bpy.types.NODE_HT_header.append(favorite_popover_draw_header)

    bpy.types.NODE_MT_context_menu.append(draw_string_switch_context_menu)

    return None

def unload_ui():

    #remove the menus from the nodes shift a menu
    remove_menus()

    #remove the favorite popover
    bpy.types.NODE_HT_header.remove(favorite_popover_draw_header)

    bpy.types.NODE_MT_context_menu.remove(draw_string_switch_context_menu)

    return None
