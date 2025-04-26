# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

from ..utils.draw_utils import ensure_mouse_cursor, popup_menu
from ..utils.str_utils import word_wrap


#NOTE more of this module: see properties/scene_sett.py/NODEBOOSTER_PR_scene_favorites_data
#NOTE perhaps we shoudln't work with Reroutes anymore, but store a 2D location instead, and draw a custom star with the gpu module?


FAVORITEUNICODE = "★" #\u2605


def get_favorites(ng, at_index=None,):
    """get the favorite reroutes in the current node tree"""

    favs = []
    for n in ng.nodes:
        if n.name.startswith(FAVORITEUNICODE):
            favs.append(n)
        continue

    favs.sort(key=lambda e:e.name)

    if (at_index is not None):
        for i,n in enumerate(favs):
            if (i==at_index):
                return n
        return None 

    return favs


class NODEBOOSTER_OT_favorite_add(bpy.types.Operator):

    bl_idname = "nodebooster.favorite_add"
    bl_label = "Add New Favorites Reroute"
    bl_description = "Add New Favorites Reroute"

    @classmethod
    def poll(cls, context):
        return (context.space_data.type=='NODE_EDITOR') and (context.space_data.node_tree is not None)

    def invoke(self, context, event):

        ng = context.space_data.edit_tree
        sett_scene = context.scene.nodebooster

        idx = 1
        name = f"{FAVORITEUNICODE}{idx:02}"
        while name in [n.name for n in ng.nodes]:
            idx +=1
            name = f"{FAVORITEUNICODE}{idx:02}"

        if (idx>50):
            popup_menu([f"You reached {idx-1} favorites.","That's too many!.",],"Max Favorites!","ORPHAN_DATA")
            return {"FINISHED"}

        rr = ng.nodes.new("NodeReroute")
        rr.name = rr.label = name
        ensure_mouse_cursor(context, event)
        rr.location = context.space_data.cursor_location
        rr["is_active_favorite"] = False

        #add to favorites reference list
        favdat = sett_scene.favorites_data.add()
        favdat.name = name
        
        #Note material.node_tree can't be assigned to NodeTree pointer property for some reasons..
        try:
            favdat.nodetree_reference = ng
        except:
            for mat in bpy.data.materials:
                if mat.use_nodes and mat.node_tree == ng:
                    favdat.material_reference = mat
                    break

        self.report({'INFO'}, f"Added Favorite '{rr.label}'",)

        return {"FINISHED"}


class NODEBOOSTER_OT_favorite_teleport(bpy.types.Operator):

    bl_idname = "nodebooster.favorite_teleport"
    bl_label = "Teleport to Favorite"
    bl_description = "Teleport to Favorite"

    mode : bpy.props.EnumProperty(
        name="Mode",
        description="Mode",
        items=[
            ("LOOP", "Loop", "Loop"),
            ("TELEPORT", "Teleport", "Teleport"),
            ],
        default="LOOP",
        options={'SKIP_SAVE'},
        )
    teleport_ngmat_name : bpy.props.StringProperty(
        name="Teleport NodeGroup (or Material) Name",
        description="Teleport NodeGroup (or Material) Name",
        default="",
        options={'SKIP_SAVE'},
        )
    teleport_to_editor_type : bpy.props.EnumProperty(
        name="Teleport to Editor Type",
        description="Teleport to Editor Type",
        items=[
            ("SHADER", "Shader", "Shader"),
            ("GEOMETRY", "Geometry", "Geometry"),
            ("COMPOSITOR", "Compositor", "Compositor"),
            ],
        default="GEOMETRY",
        options={'SKIP_SAVE'},
        )
    teleport_node_name : bpy.props.StringProperty(
        name="Teleport Node Name",
        description="Teleport Node Name",
        default="",
        options={'SKIP_SAVE'},
        )
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type=='NODE_EDITOR') and (context.space_data.node_tree is not None)

    def execute(self, context):
        
        space_data = context.space_data
        ng = space_data.edit_tree
        sett_scene = context.scene.nodebooster

        match self.mode:

            case 'LOOP':
                
                all_favorites = [n for n in ng.nodes if n.name.startswith(FAVORITEUNICODE)]
                if (not all_favorites):
                    self.report({'INFO'}, "No Favorites Found")
                    return {"CANCELLED"}

                #sort alphabetically
                all_favorites.sort(key=lambda e:e.name)

                #get the current active favorite
                current_active = None
                for fav in all_favorites:
                    if ("is_active_favorite" in fav) and (fav["is_active_favorite"]):
                        current_active = fav
                        break
                
                #if there's no active favorites here, we start from scratch..
                if current_active is None:
                    current_active = all_favorites[0]
                else:
                    #else we get the next element of the list, loop back to first if is at end of the list
                    current_active = all_favorites[(all_favorites.index(current_active)+1)%len(all_favorites)]

                #get the next favorite in the loop
                nodetoteleport = current_active

            case 'TELEPORT':

                #swap to the correct editor type?
                if (ng.type!=self.teleport_to_editor_type):
                    match self.teleport_to_editor_type:
                        case 'SHADER':
                            context.area.ui_type = 'ShaderNodeTree'
                        case 'GEOMETRY':
                            context.area.ui_type = 'GeometryNodeTree'
                        case 'COMPOSITOR':
                            context.area.ui_type = 'CompositorNodeTree'

                if (ng.name!=self.teleport_ngmat_name):

                    if self.teleport_ngmat_name.startswith('MATERIAL:'):
                          target_ng = bpy.data.materials.get(self.teleport_ngmat_name.replace('MATERIAL:','')).node_tree
                    else: target_ng = bpy.data.node_groups.get(self.teleport_ngmat_name)

                    if (target_ng):
                        space_data.pin = True
                        space_data.node_tree = target_ng
                        ng = target_ng
                    else:
                        self.report({'WARNING'}, f"Node group '{self.teleport_ngmat_name}' not found")
                        return {"CANCELLED"}

                nodetoteleport = ng.nodes.get(self.teleport_node_name)
                if (not nodetoteleport):
                    self.report({'WARNING'}, f"Node '{self.teleport_node_name}' not found in node group")
                    return {"CANCELLED"}

        #save current state
        save_active = ng.nodes.active
        save_selected = [n for n in ng.nodes if n.select]

        #deselect all
        for n in save_selected:
            n.select = False

        #teleport view
        ng.nodes.active = nodetoteleport
        nodetoteleport.select = True
        match self.mode:
            case 'LOOP':
                bpy.ops.node.view_selected()
            case 'TELEPORT':
                with context.temp_override(space=context.space_data,):
                    bpy.ops.node.view_selected('INVOKE_DEFAULT')

        #restore state
        for n in save_selected:
            n.select = True
        ng.nodes.active = save_active

        #change the .active prop
        for favdata in sett_scene.favorites_data:
            favdata.active = favdata.name == nodetoteleport.name and favdata.get_ng() == ng
        #also custom proeprty, handy..
        for n in ng.nodes:
            if n.name.startswith(FAVORITEUNICODE):
                n["is_active_favorite"] = n==nodetoteleport

        self.report({'INFO'}, f"Teleporting to Favorite '{nodetoteleport.label}'")

        return {"FINISHED"}



class NODEBOOSTER_OT_favorite_remove(bpy.types.Operator):

    bl_idname = "nodebooster.favorite_remove"
    bl_label = "Remove Favorite"
    bl_description = "Remove Favorite"

    favorite_name : bpy.props.StringProperty(
        name="Favorite Name",
        description="Favorite Name",
        default="",
        )
    editor_type : bpy.props.EnumProperty(
        name="Editor Type",
        description="Editor Type",
        items=[
            ("SHADER", "Shader", "Shader"),
            ("GEOMETRY", "Geometry", "Geometry"),
            ("COMPOSITOR", "Compositor", "Compositor"),
            ],
        default="GEOMETRY",
        )
    ngmat_name : bpy.props.StringProperty(
        name="Node Group Name",
        description="Node Group or Material name",
        default="",
        )

    def invoke(self, context, event):

        # Find nodegroup based on editor type and name
        match self.editor_type:
            #NOTE do we need different behavior per types??
            case "SHADER":
                if self.ngmat_name.startswith('MATERIAL:'):
                      ng = bpy.data.materials.get(self.ngmat_name.replace('MATERIAL:','')).node_tree
                else: ng = bpy.data.node_groups.get(self.ngmat_name)
            case "GEOMETRY":
                ng = bpy.data.node_groups.get(self.ngmat_name)
            case "COMPOSITOR":
                ng = bpy.data.node_groups.get(self.ngmat_name)

        if not ng:
            self.report({'WARNING'}, f"Nodegroup or material '{self.ngmat_name}' not found")
            return {"CANCELLED"}

        # Remove the favorite from the scene settings
        sett_scene = context.scene.nodebooster
        for i, fav in enumerate(sett_scene.favorites_data):
            if fav.name == self.favorite_name and fav.get_ng() == ng:
                sett_scene.favorites_data.remove(i)
                break

        # Find the node with matching label and delete it
        rr = ng.nodes.get(self.favorite_name)
        if not rr:
            self.report({'WARNING'}, f"Favorite '{self.favorite_name}' not found in node group")
            return {"CANCELLED"}

        ng.nodes.remove(rr)
        self.report({'INFO'}, f"Removed Favorite '{self.favorite_name}'",)

        return {"FINISHED"}


class NODEBOOSTER_PT_favorites_popover(bpy.types.Panel):

    bl_label = "Favorites"
    bl_idname = "NODEBOOSTER_PT_favorites_popover"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'WINDOW' # Content for popover
    bl_ui_units_x = 12

    def draw(self, context):

        layout = self.layout
        sett_scene = context.scene.nodebooster
        favorites = sett_scene.favorites_data

        if (not favorites):
            word_wrap(layout=layout, alignment="CENTER", max_char=35, active=True, scale_y=1.0, icon='INFO',
                      string="No Favorites Found.",)
            word_wrap(layout=layout.box(), alignment="CENTER", max_char=35, active=True, scale_y=1.0,
                      string="Use the default shortcut 'CTRL+Y' to add a new favorite.\n*SEPARATOR_LINE*\nUse the default shortcut 'Y' to loop through your favorites.",)
            return None

        # Group favorites by nodetree
        grouped_favorites = {}
        for fav in favorites:
            ng = fav.get_ng()
            if ng:
                if (ng not in grouped_favorites):
                    grouped_favorites[ng] = []
                grouped_favorites[ng].append(fav)

        # Sort nodetrees by name and type
        sorted_nodetrees = sorted(grouped_favorites.keys(), key=lambda ng: ng.name)
        allowed_ng_types = sett_scene.favorite_show_filter.split(',')
        sorted_nodetrees = [ng for ng in sorted_nodetrees if (ng.type in allowed_ng_types)]

        #draw the filter prop & icon..
        
        filter_row = layout.row(align=True)
        filter_props = filter_row.row(align=True)
        filter_props.alignment = 'RIGHT'

        match sett_scene.favorite_show_filter:
            case 'SHADER':
                icon = 'NODE_MATERIAL'
                filter_props.label(text='', icon='FILTER')
            case 'GEOMETRY':
                icon = 'GEOMETRY_NODES'
                filter_props.label(text='', icon='FILTER')
            case 'COMPOSITOR':
                icon = 'NODE_COMPOSITING'
                filter_props.label(text='', icon='FILTER')
            case _:
                icon = 'FILTER'

        filter_props.prop(sett_scene, "favorite_show_filter", text="", icon=icon, icon_only=True,)

        #draw the favorite list

        # NOTE UI list would be nice, instead of that longboi of a layout..
        # it's a pain to implement tho. 
        # would be nice to have some sort API like layout.scrollbox(height=10, use_ative_row_system=False).. would be really nice..

        ui_list = layout.box().column()

        ngidx = None
        for ngidx, ng in enumerate(sorted_nodetrees):

            favs = grouped_favorites[ng]
            if (not favs):
                continue

            # Determine nodetree type and icon

            match ng.bl_idname.split('NodeTree')[0]:

                case 'Shader':
                    material = None
                    ngtype = 'SHADER'
                    headericon = 'NODE_MATERIAL'
                    headername = ng.name
                    if (headername=='Shader Nodetree'):
                        for mat in bpy.data.materials:
                            if mat.use_nodes and mat.node_tree == ng:
                                headericon = 'MATERIAL'
                                headername = mat.name
                                material = mat
                                break

                case 'Geometry':
                    material = None
                    ngtype = 'GEOMETRY'
                    headericon = 'GEOMETRY_NODES'
                    headername = ng.name

                case 'Compositor':
                    material = None
                    ngtype = 'COMPOSITOR'
                    headericon = 'NODE_COMPOSITING'
                    headername = ng.name

            # Draw Nodetree Header

            headercol = ui_list.column(align=True)
            if (ngidx>0):
                headercol.separator(type='LINE')
            header_row = headercol.row(align=True)
            header_row.label(text=headername, icon=headericon)
            headercol.separator(type='LINE')

            # Draw Favorites for this Nodetree

            for favidx,fav in enumerate(favs):
                favidx += 1

                fav_row = ui_list.row(align=True)
                fav_row.separator(factor=2.0)

                depress_state = {'emboss':fav.active, 'depress':fav.active}

                # Teleport Button
                for i,string in enumerate((fav.name, fav.get_label(),)):
                    
                    fav_op = fav_row.row(align=True)

                    if (i==0):
                        fav_op.scale_x = 0.35
                        string = f"{favidx:02}"
                    
                    op = fav_op.operator(
                        NODEBOOSTER_OT_favorite_teleport.bl_idname, text=string, **depress_state)
                    op.mode = 'TELEPORT'
                    op.teleport_ngmat_name = 'MATERIAL:'+material.name if material else ng.name
                    op.teleport_node_name = fav.name
                    op.teleport_to_editor_type = ngtype

                # Remove Button
                fav_op = fav_row.row(align=True)
                fav_op.alignment = 'RIGHT'
                op = fav_op.operator(
                    NODEBOOSTER_OT_favorite_remove.bl_idname, text="", icon='TRASH', **depress_state)
                op.favorite_name = fav.name
                op.ngmat_name = 'MATERIAL:'+material.name if material else ng.name
                op.editor_type = ngtype
                continue
            
            continue

        if (ngidx is None):
            ui_list.label(text="...",)
            layout.label(text="Nothing Found with current filter", icon='INFO')

        return None


def favorite_popover_draw_header(self, context):

    if (context.space_data.type == 'NODE_EDITOR'
        and context.space_data.node_tree is not None
        and context.space_data.tree_type in {'ShaderNodeTree', 'GeometryNodeTree', 'CompositorNodeTree'}
        ):
        self.layout.popover(
            panel=NODEBOOSTER_PT_favorites_popover.bl_idname, text="", icon='SOLO_ON',)

    return None
