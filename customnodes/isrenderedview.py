# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    create_new_nodegroup,
    set_ng_socket_defvalue,
    cache_booster_nodes_parent_tree,
)

def all_3d_viewports():
    """return generator of all 3d view space"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if (area.type == 'VIEW_3D'):
                for space in area.spaces:
                    if (space.type == 'VIEW_3D'):
                        yield space

def all_3d_viewports_shading_type():
    """return generator of all shading type str"""
    for space in all_3d_viewports():
        yield space.shading.type

def is_rendered_view():
    """check if is rendered view in a 3d view somewhere"""
    for shading_type in all_3d_viewports_shading_type():
        if (shading_type == 'RENDERED'):
            return True
    return False


# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class NODEBOOSTER_NG_GN_IsRenderedView(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodgroup: Evaluate if any 3Dviewport is in rendered view mode.
    • The value is evaluated from depsgraph post update signals"""

    bl_idname = "GeometryNodeNodeBoosterIsRenderedView"
    bl_label = "Is Rendered View"
    auto_upd_flags = {'*CUSTOM_IMPLEMENTATION*',} #NOTE: This node is manually implemented at a handler level.

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context,):        
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name, 
                out_sockets={
                    "Is Rendered View" : "NodeSocketBool",
                },
            )

        self.node_tree = ng

        set_ng_socket_defvalue(ng, 0, value=is_rendered_view(),)
        return None 

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None
    
    # def sync_out_values(self):
    #     """sync output socket values with data"""
    #     set_ng_socket_defvalue(self.node_tree, 0, value=is_rendered_view(),)
    #     return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Is Rendered View'
        return self.label

    def draw_buttons(self, context, layout,):
        """node interface drawing"""
        
        return None 

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("doc_panelid", default_closed=True,)
        header.label(text="Documentation",)
        if (panel):
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description,
                )
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"
            
        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False
                            
            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")
        
        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """search for all node instances of this type and refresh them. Will be called automatically if .auto_upd_flags's are defined"""
        
        # actually we don't need to update all instances. 
        # for this special node who always use the same node_tree for all nodes, 
        # we simply have to update one nodetree.
        
        name = f".{cls.bl_idname}"
        ng = bpy.data.node_groups.get(name)
        if (ng):
            set_ng_socket_defvalue(ng, 0, value=is_rendered_view(),)
            
        return None
    