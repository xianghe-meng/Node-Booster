# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 


class NODEBOOSTER_AddonPref(bpy.types.AddonPreferences):

    from .. import __package__ as base_package
    bl_idname = base_package

    debug : bpy.props.BoolProperty(
        name="Debug Mode",
        default=False,
        )
    debug_depsgraph : bpy.props.BoolProperty(
        name="Depsgraph Debug",
        default=False,
        )
    #not exposed
    ui_word_wrap_max_char_factor : bpy.props.FloatProperty(
        default=1.0,
        soft_min=0.3,
        soft_max=3,
        description="ui 'word_wrap' layout funciton, max characters per lines",
        )
    ui_word_wrap_y : bpy.props.FloatProperty(
        default=0.8,
        soft_min=0.1,
        soft_max=3,
        description="ui 'word_wrap' layout funciton, max height of the lines",
        )
    
    #minimap
    auto_launch_minimap_navigation : bpy.props.BoolProperty(
        default=True,
        name="Auto Enable",
        description="Automatically launch the minimap navigation modal when loading the addon and loading new .blend files.",
        )

    def draw(self,context):
        
        layout = self.layout
        
        layout.prop(self,"debug",)
        layout.prop(self,"debug_depsgraph",)
        
        return None
