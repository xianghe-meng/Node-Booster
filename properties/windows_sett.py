# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy


class NODEBOOSTER_PR_Window(bpy.types.PropertyGroup):
    """sett_win = bpy.context.window_manager.nodebooster"""
    #Properties in there will always be temporary and reset to their default values on each blender startup

    #for python nodes
    authorize_automatic_execution : bpy.props.BoolProperty(
        default=False,
        name="Allow Automatic Executions",
        description="Automatically running a foreign python script is dangerous. Do you know the content of this .blend file? If not, do you trust the authors? When this button is enabled python expressions or scripts from the nodebooster plugin will never execute automatically, you will need to engage with the node properties to trigger an execution",
        )

    #for minimap modal navitation
    
    def launch_minimap_modal_operator(self, context):
        """lauch a modal navigation operator on each window"""

        if (self.minimap_modal_operator_is_active):
            wm = context.window_manager
            for win in wm.windows:
                with context.temp_override(window=win, screen=win.screen):
                    bpy.ops.nodebooster.minimap_interaction('INVOKE_DEFAULT',) #modal are tied per windows.

        return None

    minimap_modal_operator_is_active : bpy.props.BoolProperty(
        default=False,
        name="Modal Navigations",
        description="When enabled, the minimap modal operator will be active. This will allow you to move the minimap around the node editor area with your mouse when hovering over the minimap.",
        update=launch_minimap_modal_operator,
        )

