# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this node has a lot of potential to be copy and transformed into a
# game controller input node. I have no idea how to do that. 
# Maybe someone will implement that one day.

# TODO support other events
# user could have a string property where he can define his own event types separated by a comma.
# example with A, B, RET, SPACE or whatever
# we'll need to implement that at a node level. we pass all the info we need anyway.

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

# Global storage for event listener state
class GlobalBridge:
    is_listening = False
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
        'LEFTMOUSE': False,
        'RIGHTMOUSE': False,
        'MIDDLEMOUSE': False,
        'WHEELUPMOUSE': False,
        'WHEELDOWNMOUSE': False,
        }

# Modal operator that listens for input events
class NODEBOOSTER_OT_DeviceInputEventListener(Operator):
    """Modal operator that listens for input events and updates DeviceInput nodes"""

    bl_idname = "nodebooster.device_input_listener"
    bl_label = "Listen for Input Events"
    bl_options = {'INTERNAL'}

    def modal(self, context, event):

        # Check if we should stop the operator
        if (not GlobalBridge.is_listening):
            return {'FINISHED'}
        
        # GLobal dict of passed events
        PassedE = GlobalBridge.event_data

        # Check if the active area is a 3D View
        is_in_viewport3d = False
        for area in context.screen.areas:
            if ((area.type == 'VIEW_3D') and 
                (area.x <= event.mouse_x <= area.x + area.width) and
                (area.y <= event.mouse_y <= area.y + area.height)):

                is_in_viewport3d = True
                break

        # Only process events when in the 3D viewport
        if (is_in_viewport3d):

            # catch mouse click events.
            for et in {'LEFTMOUSE','RIGHTMOUSE','MIDDLEMOUSE'}:
                ispush = PassedE[et]
                if (et == event.type):
                    PassedE[et] = event.value in {'PRESS','CLICK_DRAG'}
                if (ispush and event.type != et):
                    PassedE[et] = False

            # catch mouse wheel events.
            if (event.type != 'MOUSEMOVE'):
                PassedE['WHEELUPMOUSE'] = (event.type == 'WHEELUPMOUSE' and event.value == 'PRESS')
                PassedE['WHEELDOWNMOUSE'] = (event.type == 'WHEELDOWNMOUSE' and event.value == 'PRESS')

            # Pass the data
            PassedE.update({
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
                })

            # Debug print
            print(f"DeviceInput Event: {PassedE}")

            # Update all nodes
            for node in get_all_nodes(exactmatch_idnames={
                NODEBOOSTER_NG_GN_DeviceInput.bl_idname,
                NODEBOOSTER_NG_SH_DeviceInput.bl_idname,
                NODEBOOSTER_NG_CP_DeviceInput.bl_idname,
                },): node.pass_event_info(PassedE)

        # NOTE We don't escape User can use the node interface to ecape.
        # if (event.type== 'ESC' and event.value == 'PRESS'):
        #     self.execute(context)
        #     return {'FINISHED'}

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
    • First, starts the modal operator that captures all input events of the 3D active Viewport.
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
            "Mouse X": "NodeSocketInt",
            "Mouse Y": "NodeSocketInt",
            "Left Click": "NodeSocketBool",
            "Right Click": "NodeSocketBool",
            "Middle Click": "NodeSocketBool",
            "Wheel Up": "NodeSocketBool",
            "Wheel Down": "NodeSocketBool",
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
        self.bl_description = self.bl_description
        
        return None
    
    def copy(self, node):
        """fct run when duplicating the node"""

        self.node_tree = node.node_tree.copy()

        return None

    def update(self):
        """generic update function"""

        return None

    def free(self):
        """Remove node from update list when deleted"""
        
        return None

    def pass_event_info(self, event_data):
        """Update node outputs based on event data - we'll expand this later"""

        ng = self.node_tree

        # Update node outputs based on event data
        set_socket_defvalue(ng, socket_name="Mouse X", value=event_data['mouse_region_x'])
        set_socket_defvalue(ng, socket_name="Mouse Y", value=event_data['mouse_region_y'])
        set_socket_defvalue(ng, socket_name="Ctrl", value=event_data['ctrl'])
        set_socket_defvalue(ng, socket_name="Shift", value=event_data['shift'])
        set_socket_defvalue(ng, socket_name="Alt", value=event_data['alt'])
        set_socket_defvalue(ng, socket_name="Left Click", value=event_data['LEFTMOUSE'])
        set_socket_defvalue(ng, socket_name="Right Click", value=event_data['RIGHTMOUSE'])
        set_socket_defvalue(ng, socket_name="Middle Click", value=event_data['MIDDLEMOUSE'])
        set_socket_defvalue(ng, socket_name="Wheel Up", value=event_data['WHEELUPMOUSE'])
        set_socket_defvalue(ng, socket_name="Wheel Down", value=event_data['WHEELDOWNMOUSE'])

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

        return None

    @classmethod
    def update_all_instances(cls, using_nodes=None, signal_from_handlers=False,):
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