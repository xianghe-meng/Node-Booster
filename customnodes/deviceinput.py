# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.types import Node, Operator
from bpy.props import BoolProperty

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    create_new_nodegroup,
    set_socket_defvalue,
    get_all_nodes,
)

# Global storage for event listener state and nodes
class GlobalBridge:
    is_listening = False
    nodes = []  # List of nodes to update
    event_data = {
        'type': '',
        'value': '',
        'mouse_x': 0.0,
        'mouse_y': 0.0,
        'mouse_region_x': 0.0,
        'mouse_region_y': 0.0,
        'pressure': 0.0,
        'shift': False,
        'ctrl': False,
        'alt': False,
    }

# Modal operator that listens for input events
class NODEBOOSTER_OT_DeviceInputEventListener(Operator):
    """Modal operator that listens for input events and updates DeviceInput nodes"""

    bl_idname = "nodebooster.device_input_listener"
    bl_label = "Listen for Input Events"
    
    def modal(self, context, event):
        # Check if we should stop the operator
        if not GlobalBridge.is_listening:
            return {'FINISHED'}

        # Check if the active area is a 3D View
        is_in_viewport3d = False
        for area in context.screen.areas:
            if area.type == 'VIEW_3D' and area.x <= event.mouse_x <= area.x + area.width and area.y <= event.mouse_y <= area.y + area.height:
                is_in_viewport3d = True
                break

        # Only process events when in the 3D viewport
        if is_in_viewport3d:
            # Process event data
            GlobalBridge.event_data = {
                'type': event.type,
                'value': event.value,
                'mouse_x': event.mouse_x,
                'mouse_y': event.mouse_y,
                'mouse_region_x': event.mouse_region_x,
                'mouse_region_y': event.mouse_region_y,
                'pressure': getattr(event, 'pressure', 0.0),
                'shift': event.shift,
                'ctrl': event.ctrl,
                'alt': event.alt,
            }

            # Debug print
            print(f"DeviceInput Event: {GlobalBridge.event_data}")

            # Update all nodes
            for node in GlobalBridge.nodes:
                node.pass_event_info(GlobalBridge.event_data)

        # Check for ESC to cancel
        if (event.type == 'ESC' and event.value == 'PRESS'):
            self.execute(context)
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        """execute the operator"""

        # Toggle listening state
        if (GlobalBridge.is_listening):
            # Stop listening
            GlobalBridge.is_listening = False
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
        else:
            # Start listening
            GlobalBridge.is_listening = True
            # Start the modal operator
            context.window_manager.modal_handler_add(self)
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
            return {'RUNNING_MODAL'}

        return {'FINISHED'}


# Base class for DeviceInput node
class Base():
    bl_idname = "NodeBoosterDeviceInput"
    bl_label = "Device Input"
    bl_description = """Custom Nodegroup: Listen for input device events and provide them as node outputs.
    • First, starts the modal operator that captures all input events.
    • Provides various data about input events (mouse, keyboard, etc.)"""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True
    
    def init(self, context):
        """this fct run when appending the node for the first time"""
        
        name = f".{self.bl_idname}"
        
        # Define socket types - we'll handle this later, minimal setup for now
        sockets = {
            "Mouse": "NodeSocketVector",
            "Ctrl": "NodeSocketBool",
            "Shift": "NodeSocketBool",
            "Alt": "NodeSocketBool",
        }
        
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets=sockets,
            )
            
        ng = ng.copy()  # always using a copy of the original ng
        
        self.node_tree = ng
        self.label = self.bl_label
        
        # Register this node to receive updates
        if self not in GlobalBridge.nodes:
            GlobalBridge.nodes.append(self)
        
        return None
    
    def copy(self, node):
        """fct run when duplicating the node"""

        self.node_tree = node.node_tree.copy()

        # Register this node to receive updates
        if self not in GlobalBridge.nodes:
            GlobalBridge.nodes.append(self)

        return None

    def update(self):
        """generic update function"""

        return None

    def free(self):
        """Remove node from update list when deleted"""
        if self in GlobalBridge.nodes:
            GlobalBridge.nodes.remove(self)

    def pass_event_info(self, event_data):
        """Update node outputs based on event data - we'll expand this later"""

        ng = self.node_tree
        # Update node outputs based on event data
        set_socket_defvalue(ng, socket_name="Mouse", value=(event_data['mouse_region_x'], event_data['mouse_region_y'], 0.0))
        set_socket_defvalue(ng, socket_name="Ctrl", value=event_data['ctrl'])
        set_socket_defvalue(ng, socket_name="Shift", value=event_data['shift'])
        set_socket_defvalue(ng, socket_name="Alt", value=event_data['alt'])

        return None

    def draw_label(self):
        """node label"""

        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row()
        text = "Stop Listening" if GlobalBridge.is_listening else "Start Listening"
        row.operator("nodebooster.device_input_listener", text=text, icon='PLAY' if not GlobalBridge.is_listening else 'PAUSE')

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:
            row = panel.row()
            text = "Stop Listening" if GlobalBridge.is_listening else "Start Listening"
            row.operator("nodebooster.device_input_listener", text=text, icon='PLAY' if not GlobalBridge.is_listening else 'PAUSE')

        header, panel = layout.panel("doc_panelid", default_closed=True)
        header.label(text="Documentation")
        if panel:
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description)
            panel.operator("wm.url_open", text="Documentation").url = "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free"

        header, panel = layout.panel("dev_panelid", default_closed=True)
        header.label(text="Development")
        if panel:
            panel.active = False
            
            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")
            
            row = panel.row()
            row.label(text=f"Active Nodes: {len(GlobalBridge.nodes)}")

        return None
    def update_all_instances():
        """update all instances of this node in all node trees"""

        # Nothing to execute for DeviceInput nodes
        # everything is handled by the modal operator

        return None


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_DeviceInput(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_DeviceInput(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_DeviceInput(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname



def register_listener():
    """register the modal operator"""

    bpy.utils.register_class(NODEBOOSTER_OT_DeviceInputEventListener)
    return None

def unregister_listener():
    """unregister the modal operator"""

    # Make sure the modal operator is stopped when unregistering
    GlobalBridge.is_listening = False
    
    bpy.utils.unregister_class(NODEBOOSTER_OT_DeviceInputEventListener) 
    return None