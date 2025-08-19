# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this node has a lot of potential to be copied, and transformed into a
# game controller input node, or MIDI controllers.
# I have no idea how to do that. Maybe someone will implement that one day.

# BUG When an animation is running, the modal operator and timer is junky. why?
# See velocity calculation.while active animation. it jumps everywhere.

# TODO
# - we need to record the user activity, and store the data somewhere in blender. 
#   Perhaps as a GraphEditor curve? that way users could record in real time and save it for later.
#   if we do that, would be nice that the user is able to swap between various recordings.
# bonus:
# - instead of using a string reprenting the user keys, blender has a system for keys properties, we could add up to 25 or so 
#   bpy.props.string with that special property to catch event perhaps? see prop(full_event=True)
# - the Mouse direction and Velocity could benefit from some sort of smoothing? as option in the N panel?
# - Could add a mouse projected location in the XY plane?
# - Storing velocity damping global settings like this will lead to a a reset of user values on each blender session.
#   we should use plugin preferences instead.
# - user feedback:
#      Please make ID registration unique. Right now, if you connect a USB numpad to the PC and 
#      you have a regular keyboard, If you press "5" blender doesn't know if it came from the USB numpad or the keyboard numpad. 
#      ID devices HID registration is required, please"""
#     Unfortunately this implementation is using bpy.types.Event so i'm not sure we can achieve that. Perhaps a more generic 'Devince Input'
#     note that cover any kind of device connected to the PC like gamepad, MIDI controllers, etc.


import bpy
import time
import math

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..resources import cust_icon
from ..utils.node_utils import (
    create_new_nodegroup,
    set_ng_socket_defvalue,
    set_ng_socket_description,
    create_ng_socket,
    remove_ng_socket,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
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

class STORAGE:
    is_listening = False
    mouse_history = [] # Store mouse position history: [(x, y, timestamp), ...]
    history_max_length = 10 # Maximum number of history entries to keep
    custom_event_types = set() # Store custom event types that user has added, we need to update event_data with their values.
    execution_counter = 0 # Counter for tracking execution cycles (for UI animation)
    use_velocity_damping = True  # Global toggle for velocity damping
    damping_factor = 0.7  # Global damping factor for mouse velocity
    damping_speed = 0.1  # Global threshold in seconds before velocity damping is applied
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

def calculate_mouse_metrics(history:list) -> tuple:
    """Calculate mouse velocity and direction. pass a location history with time indication (x, y, timestamp)
    returns a tuple with velocity and direction"""

    if (not history or len(history) < 2):
        return 0.0, (0.0, 0.0)

    # Get the oldest and newest positions
    # NOTE should'nt we smooth out and take the whole of the history into consideration?
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

class NODEBOOSTER_OT_KeyboardAndMouseEventListener(bpy.types.Operator):

    bl_idname = "nodebooster.keyboard_input_listener"
    bl_description = "Listen for input events and update KeyboardAndMouse nodes. The viewport shortcuts will not be accessible while this operator is running."
    bl_label = "Listen for Input Events"
    bl_options = {'INTERNAL'}

    _timer = None  # Store the timer reference

    def process_mouse_event(self, context, event):
        """Process mouse events to update velocity calculations"""

        # Update mouse history
        current_time = time.time()
        mouse_pos = (event.mouse_region_x, event.mouse_region_y, current_time)

        # Only add new position if it's different from the last one
        if not STORAGE.mouse_history or mouse_pos[:2] != STORAGE.mouse_history[-1][:2]:
            STORAGE.mouse_history.append(mouse_pos)
            
            # Keep history to the maximum length
            if len(STORAGE.mouse_history) > STORAGE.history_max_length:
                STORAGE.mouse_history.pop(0)

        # calculate velocity and direction
        velocity, direction = calculate_mouse_metrics(STORAGE.mouse_history)

        STORAGE.event_data.update({
            'mouse_x': event.mouse_x,
            'mouse_y': event.mouse_y,
            'mouse_region_x': event.mouse_region_x,
            'mouse_region_y': event.mouse_region_y,
            'mouse_velocity': velocity,
            'mouse_direction_x': direction[0],
            'mouse_direction_y': direction[1],
            })

        return None

    def process_mouse_tamping(self, context):
        """Process timer events to update velocity calculations"""

        # Global dict of passed events
        STOREVENT = STORAGE.event_data

        # If we have mouse history, check if we need to apply damping
        if STORAGE.mouse_history and len(STORAGE.mouse_history) >= 2:
            # Get the most recent entry and check its timestamp
            last_entry = STORAGE.mouse_history[-1]
            current_time = time.time()
            time_since_last_movement = current_time - last_entry[2]

            # Current velocity
            current_velocity = STOREVENT['mouse_velocity']

            # If mouse hasn't moved recently and velocity is still > 0, apply damping
            if time_since_last_movement > 0.01:  # Small threshold to ensure we're not moving

                # Apply a damping factor based on time passed
                dampfac = STORAGE.damping_factor if (STORAGE.use_velocity_damping) else 0.0
                dampspeed = STORAGE.damping_speed if (STORAGE.use_velocity_damping) else 0.01
            
                damping_multiplier = dampfac ** (time_since_last_movement / dampspeed)
                damped_velocity = current_velocity * damping_multiplier
                
                # Set to zero if below threshold
                if damped_velocity < 0.1:  # Threshold below which we consider velocity zero
                    damped_velocity = 0.0
                
                # Update the velocity in storage
                STOREVENT['mouse_velocity'] = damped_velocity
                
                # Update the node outputs with the new damped velocity
                self.pass_event_to_nodes(context)

        return None

    def pass_event_to_nodes(self, context,):
        """Pass the event data to the nodes"""

        for node in get_booster_nodes(by_idnames={
            NODEBOOSTER_NG_GN_KeyboardAndMouse.bl_idname,
            NODEBOOSTER_NG_SH_KeyboardAndMouse.bl_idname,
            NODEBOOSTER_NG_CP_KeyboardAndMouse.bl_idname,
            }):
            node.sync_out_event(STORAGE.event_data)
            continue

        return None

    def process_keyboard_event(self, context, event):
        """Process keyboard events"""

        STOREVENT = STORAGE.event_data

        # catch mouse and user defined events.
        keys_to_catch = {'LEFTMOUSE','RIGHTMOUSE','MIDDLEMOUSE'}
        keys_to_catch.update(STORAGE.custom_event_types)
        for et in keys_to_catch:
            if (et == event.type):
                STOREVENT[et] = event.value in {'PRESS','CLICK_DRAG'}

        # catch mouse wheel events.
        STOREVENT['WHEELUPMOUSE'] = (event.type == 'WHEELUPMOUSE')
        STOREVENT['WHEELDOWNMOUSE'] = (event.type == 'WHEELDOWNMOUSE')

        # Pass the data
        STOREVENT.update({
            'type': event.type,
            'value': event.value,
            'pressure': getattr(event, 'pressure', 0.0),
            'shift': event.shift,
            'ctrl': event.ctrl,
            'alt': event.alt,
            })

        # Update all nodes
        self.pass_event_to_nodes(context)

        return None

    def modal(self, context, event):

        # Check if we should stop the operator
        if (not STORAGE.is_listening):
            self.cancel(context)
            return {'FINISHED'}

        # Only process events when in the 3D viewport
        # Check if the active area is a 3D View
        is_in_viewport3d = False
        for area in context.screen.areas:
            if ((area.type == 'VIEW_3D') and 
                (area.x <= event.mouse_x <= area.x + area.width) and
                (area.y <= event.mouse_y <= area.y + area.height)):
                is_in_viewport3d = True
                break
        if (not is_in_viewport3d):
            return {'PASS_THROUGH'}

        # Increment execution counter for UI animation
        STORAGE.execution_counter += 1

        #### Process mouse events:

        # process velocity and direction from mouse
        self.process_mouse_event(context, event)

        # Process timer events to update velocity calculations
        if (event.type == 'TIMER'):
            self.process_mouse_tamping(context)
            self.pass_event_to_nodes(context)
            return {'PASS_THROUGH'}

        # except for passing the velocity and direction.
        if (event.type in {'MOUSEMOVE','INBETWEEN_MOUSEMOVE'}):
            return {'PASS_THROUGH'}

        # Process keyboard events
        self.process_keyboard_event(context, event)

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
        if (STORAGE.is_listening):
            # Stop listening
            STORAGE.is_listening = False
            # Update UI
            for area in context.screen.areas:
                area.tag_redraw()
            # Will call cancel() automatically and remove the timer
            return {'FINISHED'}
        else:
            # Start listening
            STORAGE.is_listening = True
            # Clear mouse history
            STORAGE.mouse_history = []
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

    bl_idname = "NodeBoosterKeyboardAndMouse"
    bl_label = "Keyboard & Mouse"
    bl_description = """Listen for your keyboard and mouse input events and provide them as node outputs.
    • First, starts the modal listener operator, this operator will capture all events within the *3D Viewport*!
    • Provides various data about input events (mouse, keyboard, etc.)
    • You can add custom key event types by entering them in a comma-separated list (e.g., "A,B,SPACE,RET"). See blender 'Event Type Items' documentation to know which kewords are supported.
    • Control the global velocity damping behavior to smooth out the mouse movement in 'N Panle > NodeBooster > Active Node > Parameters'."""
    auto_upd_flags = {'*CUSTOM_IMPLEMENTATION*',} #NOTE: This node uses a listener modal operator for the updates.
    tree_type = "*ChildrenDefined*"

    def get_velocity_damping(self):
        return STORAGE.use_velocity_damping

    def set_velocity_damping(self, value):
        STORAGE.use_velocity_damping = value
        return None

    use_velocity_damping: bpy.props.BoolProperty(
        name="Velocity Damping",
        description="Enable or disable velocity damping. When disabled, velocity will stop immediately.",
        default=True,
        get=get_velocity_damping,
        set=set_velocity_damping
    )

    def get_damping_factor(self):
        return STORAGE.damping_factor

    def set_damping_factor(self, value):
        STORAGE.damping_factor = value
        return None

    damping_factor: bpy.props.FloatProperty(
        name="Damping Factor",
        description="Factor to dampen mouse velocity (0.0 to 1.0). Global value, applies to all instances of this node.",
        min=0.0,
        max=1.0,
        default=0.7,
        get=get_damping_factor,
        set=set_damping_factor
        )

    def get_damping_speed(self):
        return STORAGE.damping_speed

    def set_damping_speed(self, value):
        STORAGE.damping_speed = value
        return None

    damping_speed: bpy.props.FloatProperty(
        name="Damping Speed",
        description="Time in seconds before velocity damping is applied. Global value, applies to all instances of this node.",
        min=0.01,
        soft_max=3.0,
        default=0.1,
        precision=2,
        subtype='TIME',
        unit='TIME',
        get=get_damping_speed,
        set=set_damping_speed
        )

    error_message : bpy.props.StringProperty(
        default=""
        )

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
        
        # Update the STORAGE custom event types
        
        # Add new event types to the event_data dictionary if they don't exist
        for et in valids:
            if (et not in STORAGE.event_data):
                STORAGE.custom_event_types.add(et)
            if (et not in STORAGE.event_data):
                STORAGE.event_data[et] = False

        # Update sockets in the node tree
        ng = self.node_tree
        
        # First, get current sockets
        current_sockets = [s.name for s in ng.nodes["Group Output"].inputs]
        
        # Add sockets for new event types
        for et in valids:
            socket_name = f"{et} Key"
            if (socket_name not in current_sockets):
                create_ng_socket(ng, in_out='OUTPUT', socket_type="NodeSocketBool", socket_name=socket_name)
        
        # Remove sockets for event types that are no longer in the list
        # We need to identify custom event sockets (ones that end with " Key")
        sockets_to_remove = []
        for idx, socket in enumerate(ng.nodes["Group Output"].inputs):
            # Check if this is a custom event socket
            if (socket.name.endswith(" Key") and socket.name not in [f"{et} Key" for et in valids]):
                sockets_to_remove.append(idx)

        # Remove sockets in reverse order to avoid index shifting issues
        for idx in reversed(sorted(sockets_to_remove)):
            remove_ng_socket(ng, idx, in_out='OUTPUT')

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
            "Mouse Position": "NodeSocketVector",
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
        descriptions = {
            "Mouse Position": "ScreenSpace Mouse position in pixels.",
            "Mouse Direction": "ScreenSpace Mouse direction normalized vector.",
            "Mouse Velocity": "Speed Unit is calculated in 1k pixels / second.",
            }

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name, tree_type=self.tree_type,
                out_sockets=sockets, sockets_description=descriptions,)

        ng = ng.copy()  # always using a copy of the original ng
        self.node_tree = ng

        self.width = 150

        return None

    def copy(self, node):
        """fct run when duplicating the node"""

        #NOTE: copy/paste can cause crashes, we use a timer to delay the action
        def delayed_copy():
            self.node_tree = node.node_tree.copy()
        bpy.app.timers.register(delayed_copy, first_interval=0.01)

        return None

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def sync_out_event(self, event_data):
        """Update node outputs based on event data"""

        ng = self.node_tree

        # Update node outputs based on event data
        set_ng_socket_defvalue(ng, socket_name="Mouse Position", value=(event_data['mouse_region_x'], event_data['mouse_region_y'], 0.0))
        set_ng_socket_defvalue(ng, socket_name="Mouse Direction", value=(event_data['mouse_direction_x'], event_data['mouse_direction_y'], 0.0))
        set_ng_socket_defvalue(ng, socket_name="Mouse Velocity", value=event_data['mouse_velocity'])
        set_ng_socket_defvalue(ng, socket_name="Ctrl", value=event_data['ctrl'])
        set_ng_socket_defvalue(ng, socket_name="Shift", value=event_data['shift'])
        set_ng_socket_defvalue(ng, socket_name="Alt", value=event_data['alt'])
        set_ng_socket_defvalue(ng, socket_name="Left Click", value=event_data['LEFTMOUSE'])
        set_ng_socket_defvalue(ng, socket_name="Right Click", value=event_data['RIGHTMOUSE'])
        set_ng_socket_defvalue(ng, socket_name="Middle Click", value=event_data['MIDDLEMOUSE'])
        set_ng_socket_defvalue(ng, socket_name="Wheel Up", value=event_data['WHEELUPMOUSE'])
        set_ng_socket_defvalue(ng, socket_name="Wheel Down", value=event_data['WHEELDOWNMOUSE'])

        # Update custom event outputs
        user_keys = [k.name for k in self.outputs if k.name.endswith(" Key")]
        for k in user_keys:
            data = k.replace(" Key", "")
            value = event_data.get(data, False)
            set_ng_socket_defvalue(ng, socket_name=k, value=value)
            if (not value):
                STORAGE.custom_event_types.add(data)

        return None

    def draw_label(self):
        """node label"""
        if (self.label==''):
            return 'Keyboard & Mouse'
        return self.label

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

        if (STORAGE.is_listening):
              animated_icon = f"W_TIME_{(STORAGE.execution_counter//4)%8}"
              row.operator("nodebooster.keyboard_input_listener", text="Stop Listening", depress=True, icon_value=cust_icon(animated_icon),)
        else: row.operator("nodebooster.keyboard_input_listener", text="Listen to Inputs", icon='PLAY')

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:

            col = panel.column(align=True)
            col.label(text="Custom Keys:")
            col.prop(self, "user_event_types", text="", placeholder="A, B, SPACE")
            col.separator(factor=0.5)

        header, panel = layout.panel("damping_panelid", default_closed=False)
        header.prop(self, "use_velocity_damping", text="Velocity Damping",)
        if (panel):
            
            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.enabled = STORAGE.use_velocity_damping
            col.prop(self, "damping_factor", text="Factor", slider=True,)
            col.prop(self, "damping_speed", text="Speed (sec)",)

        header, panel = layout.panel("doc_panelid", default_closed=True)
        header.label(text="Documentation")
        if panel:
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description)
            panel.operator("wm.url_open", text="Documentation").url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"

        header, panel = layout.panel("dev_panelid", default_closed=True)
        header.label(text="Development")
        if panel:
            panel.active = False
            
            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")
            
            #debug event content
            STOREVENT = STORAGE.event_data
            dir_x = STOREVENT['mouse_direction_x']
            dir_y = STOREVENT['mouse_direction_y']

            col = panel.column(align=True)
            col.label(text="Inputs Debug:")

            box = col.box().column(align=True)
            box.label(text=f"Executions: {STORAGE.execution_counter}")
            box.label(text=f"Value: {STOREVENT['value']}")
            box.label(text=f"Type: {STOREVENT['type']}")
            box.separator(type='LINE')
            box.label(text="Mouse Metrics:")
            box.label(text=f"Velocity: {STOREVENT['mouse_velocity']:.1f} 1000px/s")
            box.label(text=f"Direction: ({dir_x:.2f}, {dir_y:.2f}, 0.00)")
            box.label(text=f"History: {len(STORAGE.mouse_history)}")

        layout.separator(factor=0.5)
        
        if (STORAGE.is_listening):
              animated_icon = f"W_TIME_{(STORAGE.execution_counter//4)%8}"
              layout.operator("nodebooster.keyboard_input_listener", text="Stop Listening", depress=True, icon_value=cust_icon(animated_icon),)
        else: layout.operator("nodebooster.keyboard_input_listener", text="Listen to Inputs", icon='PLAY')
        
        layout.separator(factor=0.5)

        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """update all instances of this node in all node trees"""

        # Nothing to execute for KeyboardAndMouse nodes
        # everything is handled by the modal operator

        return None


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_KeyboardAndMouse(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_KeyboardAndMouse(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_KeyboardAndMouse(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname



def register_listener():
    """register the modal operator"""

    bpy.utils.register_class(NODEBOOSTER_OT_KeyboardAndMouseEventListener)
    return None

def unregister_listener():
    """unregister the modal operator"""

    # Make sure the modal operator is stopped when unregistering
    STORAGE.is_listening = False
    
    bpy.utils.unregister_class(NODEBOOSTER_OT_KeyboardAndMouseEventListener) 
    return None