# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this node has a lot of potential to be copy and transformed into a
# game controller input node. I have no idea how to do that. 
# Maybe someone will implement that one day.

# BUG When an animation is running, the modal operator and timer is junky. why?
# See velocity calculation.while active animation. it jumps everywhere.

# TODO bonus: blender has a system for keys, we could add up to 25 or so 
# bpy.props.string with that special property to catch event perhaps? see prop(full_event=True)
# TODO bonus: the Mouse direction and Velocity could benefit from some sort of smoothing? as option in the N panel?

import bpy
import time
import math

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..resources import cust_icon
from ..utils.node_utils import (
    create_new_nodegroup,
    set_socket_defvalue,
    get_all_nodes,
    create_socket,
    remove_socket,
)


POSSIBLE_EVENTS = {
    "NONE", "LEFTMOUSE", "MIDDLEMOUSE", "RIGHTMOUSE", "BUTTON4MOUSE", "BUTTON5MOUSE",
    "BUTTON6MOUSE", "BUTTON7MOUSE", "PEN", "ERASER", "MOUSEMOVE", "INBETWEEN_MOUSEMOVE",
    "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM", "WHEELUPMOUSE",
    "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE", "A", "B", "C", "D", "E", "F",
    "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V",
    "W", "X", "Y", "Z", "ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN",
    "EIGHT", "NINE", "LEFT_CTRL", "LEFT_ALT", "LEFT_SHIFT", "RIGHT_ALT", "RIGHT_CTRL",
    "RIGHT_SHIFT", "OSKEY", "APP", "GRLESS", "ESC", "TAB", "RET", "SPACE", "LINE_FEED",
    "BACK_SPACE", "DEL", "SEMI_COLON", "PERIOD", "COMMA", "QUOTE", "ACCENT_GRAVE",
    "MINUS", "PLUS", "SLASH", "BACK_SLASH", "EQUAL", "LEFT_BRACKET", "RIGHT_BRACKET",
    "LEFT_ARROW", "DOWN_ARROW", "RIGHT_ARROW", "UP_ARROW", "NUMPAD_2", "NUMPAD_4",
    "NUMPAD_6", "NUMPAD_8", "NUMPAD_1", "NUMPAD_3", "NUMPAD_5", "NUMPAD_7", "NUMPAD_9",
    "NUMPAD_PERIOD", "NUMPAD_SLASH", "NUMPAD_ASTERIX", "NUMPAD_0", "NUMPAD_MINUS",
    "NUMPAD_ENTER", "NUMPAD_PLUS", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8",
    "F9", "F10", "F11", "F12", "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20",
    "F21", "F22", "F23", "F24", "PAUSE", "INSERT", "HOME", "PAGE_UP", "PAGE_DOWN", "END",
    }

class EVENTLIB:
    is_listening = False
    mouse_history = [] # Store mouse position history: [(x, y, timestamp), ...]
    history_max_length = 10 # Maximum number of history entries to keep
    custom_event_types = set() # Store custom event types that user has added, we need to update event_data with their values.
    execution_counter = 0 # Counter for tracking execution cycles (for UI animation)
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
        'mouse_velocity': 0.0,
        'mouse_direction_x': 0.0,
        'mouse_direction_y': 0.0,
        }

def calculate_mouse_metrics(history, current_pos):
    """Calculate mouse velocity and direction"""

    if (not history or len(history) < 2):
        return 0.0, (0.0, 0.0)

    # Get the oldest and newest positions
    oldest_entry, newest_entry = history[0], history[-1]

    # Calculate time difference in seconds
    time_diff = newest_entry[2] - oldest_entry[2]
    if (time_diff <= 0):
        return 0.0, (0.0, 0.0)

    # Calculate distance moved
    dx = newest_entry[0] - oldest_entry[0]
    dy = newest_entry[1] - oldest_entry[1]
    distance = math.sqrt(dx*dx + dy*dy)

    # Calculate velocity (1k pixels per second)
    velocity = (distance / time_diff) / 1000

    # Calculate direction (normalized vector)
    if (distance > 0):
          direction = (dx/distance, dy/distance)
    else: direction = (0.0, 0.0)

    return velocity, direction

# Modal operator that listens for input events
class NODEBOOSTER_OT_DeviceInputEventListener(bpy.types.Operator):
    """Modal operator that listens for input events and updates DeviceInput nodes"""

    bl_idname = "nodebooster.device_input_listener"
    bl_label = "Listen for Input Events"
    bl_options = {'INTERNAL'}
    
    _timer = None  # Store the timer reference
    
    def process_timer_event(self, context):
        """Process timer events to update velocity calculations"""

        # GLobal dict of passed events
        PassedE = EVENTLIB.event_data

        # If we have mouse history but no recent movement, calculate a decreasing velocity
        if EVENTLIB.mouse_history and len(EVENTLIB.mouse_history) >= 2:
            # Get the most recent entry and check its timestamp
            last_entry = EVENTLIB.mouse_history[-1]
            current_time = time.time()

            # If it's been more than a short time since the last movement, calculate decaying velocity
            if current_time - last_entry[2] > 0.1:  # 100ms threshold

                # Simulate a decreasing velocity if mouse isn't moving
                current_velocity = PassedE['mouse_velocity']
                if (current_velocity > 0):

                    # Apply a damping factor (reduce by ~30% per update)
                    damped_velocity = current_velocity * 0.7
                    if damped_velocity < 1.0:  # Threshold below which we consider velocity zero
                        damped_velocity = 0

                    PassedE['mouse_velocity'] = damped_velocity

                    # Update nodes with the new velocity value
                    for node in get_all_nodes(exactmatch_idnames={
                        NODEBOOSTER_NG_GN_DeviceInput.bl_idname,
                        NODEBOOSTER_NG_SH_DeviceInput.bl_idname,
                        NODEBOOSTER_NG_CP_DeviceInput.bl_idname,
                    }): node.pass_event(PassedE)

        # Only redraw UI if there are changes to display
        if PassedE['mouse_velocity'] != 0:
            for area in context.screen.areas:
                area.tag_redraw()
        
        return None

    def modal(self, context, event):

        # Check if we should stop the operator
        if (not EVENTLIB.is_listening):
            self.cancel(context)
            return {'FINISHED'}

        # Increment execution counter for UI animation
        EVENTLIB.execution_counter += 1
        
        # Process timer events to update velocity calculations
        if (event.type == 'TIMER'):
            self.process_timer_event(context)
            return {'PASS_THROUGH'}

        # Check if the active area is a 3D View
        is_in_viewport3d = False
        for area in context.screen.areas:
            if ((area.type == 'VIEW_3D') and 
                (area.x <= event.mouse_x <= area.x + area.width) and
                (area.y <= event.mouse_y <= area.y + area.height)):
                is_in_viewport3d = True
                break

        # Only process events when in the 3D viewport
        if (not is_in_viewport3d):
            return {'PASS_THROUGH'}

        # GLobal dict of passed events
        PassedE = EVENTLIB.event_data

        region = (event.mouse_region_x, event.mouse_region_y)
        velocity, direction = calculate_mouse_metrics(EVENTLIB.mouse_history, region)

        # We don't want to catch mousemove events.
        # except for passing the velocity and direction.
        if not (event.type in {'MOUSEMOVE','INBETWEEN_MOUSEMOVE'}):
            PassedE.update({
                'mouse_velocity': velocity,
                'mouse_direction_x': direction[0],
                'mouse_direction_y': direction[1],})
            return {'PASS_THROUGH'}

        # catch mouse and user defined events.
        events_to_catch = {'LEFTMOUSE','RIGHTMOUSE','MIDDLEMOUSE'}
        events_to_catch.update(EVENTLIB.custom_event_types)
        for et in events_to_catch:
            if (et == event.type):
                PassedE[et] = event.value in {'PRESS','CLICK_DRAG'}
                
        # catch mouse wheel events.
        PassedE['WHEELUPMOUSE'] = (event.type == 'WHEELUPMOUSE')
        PassedE['WHEELDOWNMOUSE'] = (event.type == 'WHEELDOWNMOUSE')

        # Update mouse history
        current_time = time.time()
        mouse_pos = (event.mouse_region_x, event.mouse_region_y, current_time)
        
        # Only add new position if it's different from the last one
        if not EVENTLIB.mouse_history or mouse_pos[:2] != EVENTLIB.mouse_history[-1][:2]:
            EVENTLIB.mouse_history.append(mouse_pos)
            # Keep history to the maximum length
            if len(EVENTLIB.mouse_history) > EVENTLIB.history_max_length:
                EVENTLIB.mouse_history.pop(0)

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
            'mouse_velocity': velocity,
            'mouse_direction_x': direction[0],
            'mouse_direction_y': direction[1],
            })

        # Debug print (can be commented out for production)
        # print(f"DeviceInput Event: {PassedE}")

        # Update all nodes
        for node in get_all_nodes(exactmatch_idnames={
            NODEBOOSTER_NG_GN_DeviceInput.bl_idname,
            NODEBOOSTER_NG_SH_DeviceInput.bl_idname,
            NODEBOOSTER_NG_CP_DeviceInput.bl_idname,
            },): node.pass_event(PassedE)

        # NOTE We don't escape User can use the node interface to ecape.
        # if (event.type== 'ESC' and event.value == 'PRESS'):
        #     self.execute(context)
        #     return {'FINISHED'}

        # Block all shortcuts and clicks except for viewport navigation with MMB
        if (event.type in {'MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE'}):
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        """execute the operator"""

        # Toggle listening state
        if (EVENTLIB.is_listening):
            # Stop listening
            EVENTLIB.is_listening = False
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
            # Will call cancel() automatically and remove the timer
            return {'FINISHED'}
        else:
            # Start listening
            EVENTLIB.is_listening = True
            # Clear mouse history
            EVENTLIB.mouse_history = []
            # Start the modal operator
            context.window_manager.modal_handler_add(self)
            # Add timer for consistent updates - 30fps (0.033s interval)
            self._timer = context.window_manager.event_timer_add(0.033, window=context.window)
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

    bl_idname = "NodeBoosterDeviceInput"
    bl_label = "Keyboard & Mouse Info"
    bl_description = """Custom Nodegroup: Listen for input device events and provide them as node outputs.
    • First, starts the modal operator that captures all input events of the 3D active Viewport.
    • Provides various data about input events (mouse, keyboard, etc.)
    • You can add custom key event types by entering them in a comma-separated list (e.g., "A,B,SPACE,RET"). See blender 'Event Type Items' documentation to know which kewords are supported."""
    auto_update = {'NONE',}
    tree_type = "*ChildrenDefined*"
    
    error_message : bpy.props.StringProperty()

    def update_custom_events(self, context):
        """Update the sockets based on custom event types"""

        # Process the custom event types string - split by commas and strip whitespace
        event_types = [et.strip().upper() for et in self.user_event_types.split(',') if et.strip()]
        
        valids = set()
        invalids = set()

        for et in event_types:
            if (et in POSSIBLE_EVENTS):
                  valids.add(et)
            else: invalids.add(et)
        
        # Compose error message if there are invalid event types
        if (invalids):
              self.error_message = f"Invalid Key: {', '.join(invalids)}"
        else: self.error_message = ""
        
        # Update the EVENTLIB custom event types
        
        # Add new event types to the event_data dictionary if they don't exist
        for et in valids:
            if (et not in EVENTLIB.event_data):
                EVENTLIB.custom_event_types.add(et)
            if (et not in EVENTLIB.event_data):
                EVENTLIB.event_data[et] = False

        # Update sockets in the node tree
        ng = self.node_tree
        
        # First, get current sockets
        current_sockets = [s.name for s in ng.nodes["Group Output"].inputs]
        
        # Add sockets for new event types
        for et in valids:
            socket_name = f"{et} Key"
            if (socket_name not in current_sockets):
                create_socket(ng, in_out='OUTPUT', socket_type="NodeSocketBool", socket_name=socket_name)
        
        # Remove sockets for event types that are no longer in the list
        # We need to identify custom event sockets (ones that end with " Key")
        sockets_to_remove = []
        for idx, socket in enumerate(ng.nodes["Group Output"].inputs):
            # Check if this is a custom event socket
            if (socket.name.endswith(" Key") and socket.name not in [f"{et} Key" for et in valids]):
                sockets_to_remove.append(idx)

        # Remove sockets in reverse order to avoid index shifting issues
        for idx in reversed(sorted(sockets_to_remove)):
            remove_socket(ng, idx, in_out='OUTPUT')

        # Refresh the node
        self.update()
    
        return None
    
    # Property for custom event types
    user_event_types: bpy.props.StringProperty(
        name="Custom Event Types",
        description="List of custom event types to track, separated by commas (e.g., 'A, B, SPACE,RET').\nSee blender 'Event Type Items' documentation to know which kewords are supported.",
        default="",
        update=update_custom_events
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True
    
    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        # Define socket types - we'll handle this later, minimal setup for now
        sockets = {
            "Mouse Location": "NodeSocketVector",
            "Mouse Direction": "NodeSocketVector",
            "Mouse Velocity": "NodeSocketFloat",
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
                out_sockets=sockets,)

        ng = ng.copy()  # always using a copy of the original ng

        self.node_tree = ng
        self.width = 156
        self.label = self.bl_label

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

    def pass_event(self, event_data):
        """Update node outputs based on event data"""

        ng = self.node_tree

        # Update node outputs based on event data
        set_socket_defvalue(ng, socket_name="Mouse Location", value=(event_data['mouse_region_x'], event_data['mouse_region_y'], 0.0))
        set_socket_defvalue(ng, socket_name="Mouse Direction", value=(event_data['mouse_direction_x'], event_data['mouse_direction_y'], 0.0))
        set_socket_defvalue(ng, socket_name="Mouse Velocity", value=event_data['mouse_velocity'])
        set_socket_defvalue(ng, socket_name="Ctrl", value=event_data['ctrl'])
        set_socket_defvalue(ng, socket_name="Shift", value=event_data['shift'])
        set_socket_defvalue(ng, socket_name="Alt", value=event_data['alt'])
        set_socket_defvalue(ng, socket_name="Left Click", value=event_data['LEFTMOUSE'])
        set_socket_defvalue(ng, socket_name="Right Click", value=event_data['RIGHTMOUSE'])
        set_socket_defvalue(ng, socket_name="Middle Click", value=event_data['MIDDLEMOUSE'])
        set_socket_defvalue(ng, socket_name="Wheel Up", value=event_data['WHEELUPMOUSE'])
        set_socket_defvalue(ng, socket_name="Wheel Down", value=event_data['WHEELDOWNMOUSE'])

        # Update custom event outputs
        user_keys = [k.name for k in self.outputs if k.name.endswith(" Key")]
        for k in user_keys:
            data = k.replace(" Key", "")
            value = event_data.get(data, False)
            set_socket_defvalue(ng, socket_name=k, value=value)
            if (not value):
                EVENTLIB.custom_event_types.add(data)

        return None

    def draw_label(self):
        """node label"""

        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""
        
        col = layout.column(align=True)
        col.label(text="Keys:")
        col.prop(self, "user_event_types", text="", placeholder="A, B, SPACE")
        if (self.error_message):
            box = col.box()
            word_wrap(layout=box, alert=True, active=True, max_char=self.width/6, string=self.error_message)
            col.separator(factor=0.5)

        col = layout.column(align=True)
        row = col.row(align=True)

        if (EVENTLIB.is_listening):
              animated_icon = f"W_TIME_{(EVENTLIB.execution_counter//4)%8}"
              row.operator("nodebooster.device_input_listener", text="Stop Listening", depress=True, icon_value=cust_icon(animated_icon),)
        else: row.operator("nodebooster.device_input_listener", text="Start Listening", icon='PLAY')

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:

            row = panel.row()

            if (EVENTLIB.is_listening):
                animated_icon = f"W_TIME_{(EVENTLIB.execution_counter//4)%8}"
                row.operator("nodebooster.device_input_listener", text="Stop Listening", depress=True, icon_value=cust_icon(animated_icon),)
            else: row.operator("nodebooster.device_input_listener", text="Start Listening", icon='PLAY')

            col = panel.column(align=True)
            col.label(text="Custom Keys")
            col.prop(self, "user_event_types", text="", placeholder="A, B, SPACE")

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
            
            #debug event content
            PassedE = EVENTLIB.event_data
            dir_x = PassedE['mouse_direction_x']
            dir_y = PassedE['mouse_direction_y']

            col = panel.column(align=True)
            col.label(text="Inputs Debug:")

            box = col.box().column(align=True)
            box.label(text=f"Value: {PassedE['value']}")
            box.label(text=f"Type: {PassedE['type']}")
            box.separator(type='LINE')
            box.label(text="Mouse Metrics:")
            box.label(text=f"Velocity: {PassedE['mouse_velocity']:.1f} px/s")
            box.label(text=f"Direction: ({dir_x:.2f}, {dir_y:.2f}, 0.00)")
            box.label(text=f"History: {len(EVENTLIB.mouse_history)}")

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
    EVENTLIB.is_listening = False
    
    bpy.utils.unregister_class(NODEBOOSTER_OT_DeviceInputEventListener) 
    return None