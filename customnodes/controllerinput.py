# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import time
import platform
import traceback

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.zethinput import devices, reload_devices
from ..resources import cust_icon
from ..utils.node_utils import (
    create_new_nodegroup,
    set_ng_socket_defvalue,
    set_ng_socket_description,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
    create_ng_socket,
    remove_ng_socket,
)

class CONTROLLER_STORAGE:
    is_listening = False
    execution_counter = 0
    controller_data = {
        'is_button_a_pushed': False,
        'is_button_b_pushed': False,
        'is_button_x_pushed': False,
        'is_button_y_pushed': False,
        'is_arrow_up_pushed': False,
        'is_arrow_down_pushed': False,
        'is_arrow_left_pushed': False,
        'is_arrow_right_pushed': False,
        'leftpad_x': 0.0,
        'leftpad_y': 0.0,
        'rightpad_x': 0.0,
        'rightpad_y': 0.0,
        'left_trigger': 0.0,
        'is_left_shoulder_button': False,
        'right_trigger': 0.0,
        'is_right_shoulder_button': False,
        }

def get_active_controller():
    """Get the first available controller"""
    try:
        if (devices.gamepads and len(devices.gamepads)>0):
            return devices.gamepads[0]
    except Exception as e:
        print(f"ERROR: get_active_controller(): {e}")
    return None

def reload_controllers():
    """Reload and detect controllers"""
    try:
        # Reload devices to detect new controllers
        reload_devices()
        from ..utils.zethinput import devices as _devices
        global devices
        devices = _devices
        return get_active_controller() is not None
    except Exception as e:
        print(f"Error reloading devices: {e}")
        return False


class NODEBOOSTER_OT_ReloadControllers(bpy.types.Operator):
    """Reload and detect controllers"""
    bl_idname = "nodebooster.reload_controllers"
    bl_label = "Reload Controllers"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        """Reload controllers"""

        success = reload_controllers()
        if (success):
            controller = get_active_controller()
            self.report({'INFO'}, f"Controller found: {controller.name}")
        else:
            self.report({'WARNING'}, "No controllers found")

        # Update UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}

class NODEBOOSTER_OT_ControllerInputListener(bpy.types.Operator):
    """Listen for controller input events"""
    bl_idname = "nodebooster.controller_input_listener"
    bl_label = "Controller Input Listener"
    bl_description = "Listen for controller input and update controller nodes"
    bl_options = {'INTERNAL'}

    _timer = None

    def update_controller_data(self):
        """Update controller data from gamepad using direct state reading (no lag)"""
        controller = get_active_controller()
        if not controller:
            return
        global CONTROLLER_STORAGE
        try:
            # Use the new lag-free get_current_state() function
            CONTROLLER_STORAGE.controller_data = controller.get_current_state().copy()  
        except Exception as e:
            print(f"Error reading controller state: {e}")

    def pass_data_to_nodes(self):
        """Pass controller data to all controller nodes"""
        for node in get_booster_nodes(by_idnames={
            NODEBOOSTER_NG_GN_XboxPadInput.bl_idname,
            NODEBOOSTER_NG_SH_XboxPadInput.bl_idname,
            NODEBOOSTER_NG_CP_XboxPadInput.bl_idname,
            }):
            node.sync_controller_data(CONTROLLER_STORAGE.controller_data)
            continue
        return None

    def modal(self, context, event):
        """Handle modal events"""
        # Check if we should stop the operator
        if (not CONTROLLER_STORAGE.is_listening):
            self.cancel(context)
            return {'FINISHED'}
        # Increment execution counter for UI animation
        CONTROLLER_STORAGE.execution_counter += 1
        # Process timer events
        if (event.type=='TIMER'):
            try:
                self.update_controller_data()
                self.pass_data_to_nodes()
            except Exception as e:
                print(f"Error in controller processing: {e}")
                traceback.print_exc()
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        """Execute the operator, toggle start/stop behavior"""
        # Toggle listening state
        if (CONTROLLER_STORAGE.is_listening):
            # Stop listening
            CONTROLLER_STORAGE.is_listening = False
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
            return {'FINISHED'}
        else:
            # Check if controller is available
            controller = get_active_controller()
            if (not controller):
                self.report({'ERROR'}, "No controller found. Please reload controllers first.")
                return {'CANCELLED'}
            # Listen to Inputs
            CONTROLLER_STORAGE.is_listening = True
            context.window_manager.modal_handler_add(self)
            # Add timer for consistent updates - more than 60fps
            self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
            return {'RUNNING_MODAL'}

    def cancel(self, context):
        """Called when the modal operator is stopped"""
        # Remove the timer
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        return None

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():
    bl_idname = "NodeBoosterXboxPadInput"
    bl_label = "Xbox Controller"
    bl_description = """Listen for a Xbox controller input and provide button and joystick data. Please note that this node is exclusive to WindowsOS and Xbox Controllers!"""
    auto_upd_flags = {'*CUSTOM_IMPLEMENTATION*'} #NOTE: This node uses a listener modal operator for the updates.
    tree_type = "*ChildrenDefined*"

    @classmethod
    def poll(cls, context):
        return True

    def init(self, context):
        """Initialize the node"""
        name = f".{self.bl_idname}"

        # Define basic sockets
        sockets = {
            "Arrow Up": "NodeSocketBool",
            "Arrow Down": "NodeSocketBool",
            "Arrow Left": "NodeSocketBool",
            "Arrow Right": "NodeSocketBool",
            "Left Stick": "NodeSocketVector",
            "Right Stick": "NodeSocketVector",
            "Button A": "NodeSocketBool",
            "Button B": "NodeSocketBool",
            "Button X": "NodeSocketBool",
            "Button Y": "NodeSocketBool",
            "Trigger LB": "NodeSocketBool",
            "Trigger LT": "NodeSocketFloat",
            "Trigger RB": "NodeSocketBool",
            "Trigger RT": "NodeSocketFloat",
            "Button Start": "NodeSocketBool",
        }
        descriptions = {}

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name, tree_type=self.tree_type,
                out_sockets=sockets, sockets_description=descriptions)

        ng = ng.copy()
        self.node_tree = ng
        self.width = 150

        return None

    def copy(self, node):
        """Function run when duplicating the node"""

        #NOTE: copy/paste can cause crashes, we use a timer to delay the action
        def delayed_copy():
            self.node_tree = node.node_tree.copy()
        bpy.app.timers.register(delayed_copy, first_interval=0.01)
        
        return None

    def update(self):
        """Generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def sync_controller_data(self, controller_data):
        """Update node outputs based on controller data"""
        ng = self.node_tree

        if (controller_data is None):
            empty_dict = {
                        'is_button_a_pushed': False,
                        'is_button_b_pushed': False,
                        'is_button_x_pushed': False,
                        'is_button_y_pushed': False,
                        'is_arrow_up_pushed': False,
                        'is_arrow_down_pushed': False,
                        'is_arrow_left_pushed': False,
                        'is_arrow_right_pushed': False,
                        'is_start_pushed': False,
                        'leftpad_x': 0.0,
                        'leftpad_y': 0.0,
                        'rightpad_x': 0.0,
                        'rightpad_y': 0.0,
                        'left_trigger': 0.0,
                        'is_left_shoulder_button': False,
                        'right_trigger': 0.0,
                        'is_right_shoulder_button': False,
                        }
            controller_data = empty_dict

        set_ng_socket_defvalue(ng, socket_name="Button A", value=controller_data['is_button_a_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Button B", value=controller_data['is_button_b_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Button X", value=controller_data['is_button_x_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Button Y", value=controller_data['is_button_y_pushed'])

        set_ng_socket_defvalue(ng, socket_name="Arrow Up", value=controller_data['is_arrow_up_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Arrow Down", value=controller_data['is_arrow_down_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Arrow Left", value=controller_data['is_arrow_left_pushed'])
        set_ng_socket_defvalue(ng, socket_name="Arrow Right", value=controller_data['is_arrow_right_pushed'])

        set_ng_socket_defvalue(ng, socket_name="Button Start", value=controller_data['is_start_pushed'])

        set_ng_socket_defvalue(ng, socket_name="Trigger LB", value=controller_data['is_left_shoulder_button'])
        set_ng_socket_defvalue(ng, socket_name="Trigger LT", value=controller_data['left_trigger'])
        set_ng_socket_defvalue(ng, socket_name="Trigger RB", value=controller_data['is_right_shoulder_button'])
        set_ng_socket_defvalue(ng, socket_name="Trigger RT", value=controller_data['right_trigger'])

        set_ng_socket_defvalue(ng, socket_name="Left Stick", value=(controller_data['leftpad_x'], controller_data['leftpad_y'], 0.0))
        set_ng_socket_defvalue(ng, socket_name="Right Stick", value=(controller_data['rightpad_x'], controller_data['rightpad_y'], 0.0))

        return None

    def draw_label(self):
        """Node label"""
        if self.label == '':
            return 'Xbox Controller'
        return self.label

    def draw_buttons(self, context, layout):
        """Node interface drawing"""

        col = layout.column(align=True)
        
        controller = get_active_controller()
        row = col.row(align=True)
        if (not controller):
              row.operator("nodebooster.reload_controllers", text="No GamePad Found", icon='FILE_REFRESH')
        else: row.operator("nodebooster.reload_controllers", text="GamePad Found", icon='FILE_REFRESH')

        # if os is not window, show a warning
        if (platform.system() != 'Windows'):
            row = col.row(align=True)
            row.label(text="MacOS/Linux Unsupported", icon='ERROR')

        # Listen button
        col = layout.column(align=True)
        if (controller or CONTROLLER_STORAGE.is_listening):
            if (CONTROLLER_STORAGE.is_listening):
                  col.operator("nodebooster.controller_input_listener", text="Stop Listening",  depress=True, icon_value=cust_icon(f"W_TIME_{(CONTROLLER_STORAGE.execution_counter//4)%8}"))
            else: col.operator("nodebooster.controller_input_listener", text="Listen to Inputs", icon='PLAY')

        return None

    def draw_panel(self, layout, context):
        """Draw in the nodebooster N panel 'Active Node'"""

        # Controller detection
        header, panel = layout.panel("controller_detection", default_closed=False)
        header.label(text="Controller Detection")
        if panel:
            controller = get_active_controller()
            if (not controller):
                panel.alert = True
                panel.label(text="No controller found", icon='ERROR')
                panel.operator("nodebooster.reload_controllers", text="Detect Controller", icon='FILE_REFRESH')
            else:
                collbl = panel.column(align=True)
                collbl.label(text=f"Controller: {controller.name}")
                panel.operator("nodebooster.reload_controllers", text="Reload Controller", icon='FILE_REFRESH')

            if (controller or CONTROLLER_STORAGE.is_listening):
                # Listen button
                panel.separator(type='LINE')
                if (controller):
                    if (CONTROLLER_STORAGE.is_listening):
                          panel.operator("nodebooster.controller_input_listener", text="Stop Listening", depress=True, icon_value=cust_icon(f"W_TIME_{(CONTROLLER_STORAGE.execution_counter//4)%8}"))
                    else: panel.operator("nodebooster.controller_input_listener", text="Listen to Inputs", icon='PLAY')
                else:
                    panel.alert = True
                    panel.label(text="No Controller Found", icon='ERROR')
                    
        # Controller data debug
        header, panel = layout.panel("controller_debug", default_closed=True)
        header.label(text="Controller Data")
        if panel:
            col = panel.column(align=True)
            col.label(text=f"Executions: {CONTROLLER_STORAGE.execution_counter}")
            col.separator()
            col.label(text="Current Values:")
            for k,v in CONTROLLER_STORAGE.controller_data.items():
                col.label(text=f"{k}: {v}")

        # Documentation
        header, panel = layout.panel("doc_panelid", default_closed=True)
        header.label(text="Documentation")
        if panel:
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=self.bl_description)

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False):
        """Update all instances of this node in all node trees"""
        # Nothing to execute for controller input nodes
        # everything is handled by the modal operator
        pass

# Per Node-Editor Children:
# Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_XboxPadInput(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_XboxPadInput(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_XboxPadInput(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname


def register_controller_listener():
    """Register the controller modal operator"""
    bpy.utils.register_class(NODEBOOSTER_OT_ControllerInputListener)
    bpy.utils.register_class(NODEBOOSTER_OT_ReloadControllers)
    return None

def unregister_controller_listener():
    """Unregister the controller modal operator"""
    # Make sure the modal operator is stopped when unregistering
    CONTROLLER_STORAGE.is_listening = False
    bpy.utils.unregister_class(NODEBOOSTER_OT_ControllerInputListener)
    bpy.utils.unregister_class(NODEBOOSTER_OT_ReloadControllers)
    return None
