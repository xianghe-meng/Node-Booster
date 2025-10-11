# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

import re
import os

from ..__init__ import get_addon_prefs


class NODEBOOSTER_MT_textemplate(bpy.types.Menu):
    bl_idname = "NODEBOOSTER_MT_textemplate"
    bl_label  = "Booster Nodes"

    def draw(self, context):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        external_dir = os.path.join(parent_dir, "resources")

        file_path = os.path.join(external_dir, "NexDemo.py")
        layout = self.layout 
        layout.separator()
        op = layout.operator("nodebooster.import_template", text=os.path.basename(file_path),)
        op.filepath = file_path

        return None

#       .o.             .o8        .o8    ooo        ooooo                                   
#      .888.           "888       "888    `88.       .888'                                   
#     .8"888.      .oooo888   .oooo888     888b     d'888   .ooooo.  ooo. .oo.   oooo  oooo  
#    .8' `888.    d88' `888  d88' `888     8 Y88. .P  888  d88' `88b `888P"Y88b  `888  `888  
#   .88ooo8888.   888   888  888   888     8  `888'   888  888ooo888  888   888   888   888  
#  .8'     `888.  888   888  888   888     8    Y     888  888    .o  888   888   888   888  
# o88o     o8888o `Y8bod88P" `Y8bod88P"   o8o        o888o `Y8bod8P' o888o o888o  `V88V"V8P' 

from ..customnodes import allcustomnodes

#list of menus class we are about to create
PROCEDURAL_ADDMENUS = []
#list of nodes or menus to call from 'draw_booster_nodes_add_menu'
MAIN_LAYOUT_CONTENT = []

def auto_register_submenus(self, context):
    """all our nodes have a 'nb_menu_path', being lists of strings. 
    The last element of the list is the name of the node, to call `layout.operator("node.add_node")` with
    all other elements are submenus, we need to procedurally create and register these menus and drawing functions with branching menus"""

    global PROCEDURAL_ADDMENUS, MAIN_LAYOUT_CONTENT

    # reset any previous content
    PROCEDURAL_ADDMENUS = []
    MAIN_LAYOUT_CONTENT = []

    def make_class_name_from_path(path_tuple):
        def sanitize_token(token: str) -> str:
            t = re.sub(r"[^0-9a-zA-Z]+", "_", str(token)).strip("_")
            if (not t): t = "UNNAMED"
            return t.upper()
        tokens = [sanitize_token(p) for p in path_tuple]
        return "NODEBOOSTER_MT_SUBMENU_" + "_".join(tokens)

    # Collect all menu paths and node attachments
    menu_paths_set = set()  # set[tuple[str,...]] of submenu paths
    menu_label_map = {}     # path_tuple -> label (last token)
    node_map = {}           # parent_menu_path_tuple -> list[(cls, node_label)]

    for cls in allcustomnodes:
        if (not hasattr(cls, 'nb_menu_path')):
            print("WARNING: Node", getattr(cls, 'bl_label', getattr(cls, '__name__', str(cls))), "has no nb_menu_path")
            continue
        menu_paths = getattr(cls, 'nb_menu_path', [])
        if (len(menu_paths) == 0):
            print("WARNING: Node", getattr(cls, 'bl_label', getattr(cls, '__name__', str(cls))), "has empty nb_menu_path")
            continue

        # If it's a single path element, directly display this node in main layout
        if (len(menu_paths) == 1):
            cls.nb_menu_path = menu_paths[0]
            MAIN_LAYOUT_CONTENT.append(cls)
            continue

        # All prefixes (except the final node label) form the submenu hierarchy
        menus, node_operator_label = menu_paths[:-1], menu_paths[-1]

        # Track all submenu prefixes
        for i in range(1, len(menus)+0):  # +0 explicit; up to full submenu path
            prefix = tuple(menus[:i])
            if len(prefix) == 0:
                continue
            if prefix not in menu_paths_set:
                menu_paths_set.add(prefix)
                menu_label_map[prefix] = prefix[-1]

        full_menu_path = tuple(menus)
        if full_menu_path:
            menu_paths_set.add(full_menu_path)
            menu_label_map[full_menu_path] = full_menu_path[-1]

        # Attach node to its direct parent submenu path
        parent_path = tuple(menus)
        node_map.setdefault(parent_path, []).append((cls, node_operator_label))

    # Build direct-children mapping for submenus
    children_menus_map = {}  # parent_path_tuple (or ()) -> set(child_path_tuple)
    for path in menu_paths_set:
        parent = tuple(path[:-1])
        children_menus_map.setdefault(parent, set()).add(path)

    # Create classes for each submenu path
    path_to_class = {}
    # Sort paths for deterministic creation order
    for path in sorted(menu_paths_set, key=lambda p: (len(p), [str(x).lower() for x in p])):
        class_name = make_class_name_from_path(path)
        bl_label = menu_label_map.get(path, path[-1] if path else "Menu")

        #procedurally gen the draw function
        def draw(self, context):
            layout = self.layout
            # Draw submenu entries first
            for cls in getattr(self, 'children_menus', []):
                if (cls.bl_label=='Experimental' and not get_addon_prefs().experimental_mode):
                    continue
                layout.menu(cls.bl_idname)
            # Then draw node entries
            for cls, node_label in getattr(self, 'children_nodes', []):
                if (not hasattr(cls, 'tree_type')):
                    print(f"WARNING: Node '{cls.bl_label}' has no attribute 'tree_type'")
                    continue
                elif (cls.tree_type in {context.space_data.tree_type,'AnyNodeTree'}): #filter add node operator depending on the editor type..
                    op = layout.operator("node.add_node", text=node_label)
                    op.type = cls.bl_idname
                    op.use_transform = True
            return None

        #build the class from attributes
        attrs = {
            'bl_idname': class_name,
            'bl_label': bl_label,
            'bl_description': "",
            'children_menus': [],
            'children_nodes': [],
            'draw': draw, }
        NewMenuClass = type(class_name, (bpy.types.Menu,), attrs)

        #mark for registration
        path_to_class[path] = NewMenuClass
        PROCEDURAL_ADDMENUS.append(NewMenuClass)

    # Wire children relationships for each submenu class
    for path, MenuClass in path_to_class.items():
        # child menus (direct children only)
        child_paths = sorted(children_menus_map.get(path, []), key=lambda p: menu_label_map.get(p, p[-1]).lower())
        MenuClass.children_menus = [path_to_class[p] for p in child_paths if p in path_to_class]

        # child nodes under this submenu
        node_entries = sorted(node_map.get(path, []), key=lambda e: str(e[1]).lower())
        MenuClass.children_nodes = node_entries

    # Add root-level menus to the main layout
    top_level_menu_paths = sorted(children_menus_map.get((), []), key=lambda p: menu_label_map.get(p, p[-1]).lower())
    for p in top_level_menu_paths:
        if p in path_to_class:
            MAIN_LAYOUT_CONTENT.append(path_to_class[p])
    
    return None

def draw_booster_nodes_add_menu(self, context):
    """append booster nodes to the main nodetree add menu common across all nodetrees editors"""

    if (context.space_data.tree_type not in {'GeometryNodeTree','ShaderNodeTree','CompositorNodeTree'}):
        return None
    layout = self.layout
    layout.separator()

    for cls in MAIN_LAYOUT_CONTENT:
        is_submenu, is_nd_node, is_ng_node = cls.__name__.startswith('NODEBOOSTER_MT_SUBMENU_'), cls.__name__.startswith('NODEBOOSTER_ND_'), cls.__name__.startswith('NODEBOOSTER_NG_')
        if (is_nd_node or is_ng_node):
            if (not hasattr(cls, 'tree_type')):
                print(f"WARNING: Node '{cls.bl_label}' has no attribute 'tree_type'")
                continue
            elif (cls.tree_type in {context.space_data.tree_type,'AnyNodeTree'}): #filter add node operator depending on the editor type..
                op = layout.operator("node.add_node", text=cls.bl_label,)
                op.type = cls.bl_idname
                op.use_transform = True
        elif (is_submenu):
            if (cls.bl_label=='Experimental' and not get_addon_prefs().experimental_mode):
                continue
            layout.menu(cls.bl_idname)
        else:
            print("WARNING: Node", cls.bl_label, "has an unknown type")

    return None

def append_menus():

    # Build dynamic submenu classes and main layout content
    auto_register_submenus(None, bpy.context)

    bpy.types.NODE_MT_add.append(draw_booster_nodes_add_menu)

    # Register dynamically generated submenu classes
    for cls in PROCEDURAL_ADDMENUS:
        bpy.utils.register_class(cls)

    return None

def remove_menus():

    # Unregister dynamically generated submenu classes first
    for cls in reversed(PROCEDURAL_ADDMENUS):
        bpy.utils.unregister_class(cls)

    bpy.types.NODE_MT_add.remove(draw_booster_nodes_add_menu)

    return None