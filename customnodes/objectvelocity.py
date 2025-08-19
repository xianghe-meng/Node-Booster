# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# TODO
# - BUG timeline reset is behaving weirdly. I have no idea why. Spend 1h on this, i give up.
# - Verify accuracy. 
#      Is the math correct? There's a little bit of a delay. Pehraps the node could be 
#      ameliorated to be more reactive? Need an expert to verify, i don't actually know of these things 
#      are properly calculated.
# - bonus:
#   - add option for smoothing the data? == control over how many history steps perhaps? don't know..
#   - enable object damping, make it work.
#   - support option to analyze rotation/scale. Use an EnumProperty. Algo should be simpler for checking scale change
#     unsure what kind of unit standard should apply tho.. There's no distance.


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

DEBUG = False

def init_objvelocities():
    """Initialize object velocities dictionary on WindowManager"""
    if not hasattr(bpy.types.WindowManager, "objvelocities"):
        bpy.types.WindowManager.objvelocities = {}
    return None

def calculate_object_metrics(history: list) -> tuple:
    """Calculate object velocity, acceleration and stopping power in 3D space.
    Expects a history list with [(location, rotation, scale, frame_time), ...]
    Returns a tuple with (direction vector, velocity magnitude, acceleration, stopping power)"""

    if (not history) or (len(history) < 2):
        return (0.0, 0.0, 0.0), 0.0, 0.0, 0.0

    # Get the oldest and newest positions
    oldest_entry, newest_entry = history[0], history[-1]
    middle_entry = None

    # Calculate time difference in seconds (frame_time is in seconds)
    time_diff = newest_entry[3] - oldest_entry[3]
    
    if (time_diff <= 0):
        return (0.0, 0.0, 0.0), 0.0, 0.0, 0.0

    # Calculate distance moved
    dx = newest_entry[0][0] - oldest_entry[0][0]
    dy = newest_entry[0][1] - oldest_entry[0][1]
    dz = newest_entry[0][2] - oldest_entry[0][2]
    distance = math.sqrt(dx*dx + dy*dy + dz*dz)

    # Calculate velocity in m/s
    velocity_magnitude = distance / time_diff

    # Calculate normalized direction vector
    direction = (0.0, 0.0, 0.0) 
    if (distance > 0.0):
        direction = (dx/distance, dy/distance, dz/distance)

    # Calculate acceleration and stopping power
    acceleration = 0.0
    stopping_power = 0.0

    # We need at least 3 history points to calculate acceleration
    if (len(history) >= 3):
        middle_entry = history[len(history) // 2]

        # Calculate velocity at the middle point
        middle_time_diff = middle_entry[3] - oldest_entry[3]
        if (middle_time_diff > 0):

            mdx = middle_entry[0][0] - oldest_entry[0][0]
            mdy = middle_entry[0][1] - oldest_entry[0][1]
            mdz = middle_entry[0][2] - oldest_entry[0][2]
            middle_distance = math.sqrt(mdx*mdx + mdy*mdy + mdz*mdz)
            middle_velocity = middle_distance / middle_time_diff

            # Calculate velocity at the newest point
            newest_time_diff = newest_entry[3] - middle_entry[3]
            if (newest_time_diff > 0):

                ndx = newest_entry[0][0] - middle_entry[0][0]
                ndy = newest_entry[0][1] - middle_entry[0][1]
                ndz = newest_entry[0][2] - middle_entry[0][2]
                newest_distance = math.sqrt(ndx*ndx + ndy*ndy + ndz*ndz)
                newest_velocity = newest_distance / newest_time_diff

                # Calculate acceleration and stopping power
                velocity_diff = newest_velocity - middle_velocity

                # If velocity is increasing, it's acceleration
                if (velocity_diff > 0):
                    acceleration = velocity_diff / (newest_entry[3] - middle_entry[3])
                # If velocity is decreasing, it's stopping power
                elif (velocity_diff < 0):
                    stopping_power = -velocity_diff / (newest_entry[3] - middle_entry[3])

    if (DEBUG):
        print(f" -oldest_entry: {oldest_entry}")
        print(f" -newest_entry: {newest_entry}")
        print(f" -middle_entry: {middle_entry}")
        print(f" -time_diff: {time_diff}")

    return direction, velocity_magnitude, acceleration, stopping_power

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterObjectVelocity"
    bl_label = "Object Velocity"
    bl_description = """Track an object's velocity, acceleration, and stopping power.
    • Monitors the selected object's position, rotation, and scale.
    • Calculates velocity, acceleration, and stopping power in real-time.
    • Provides damping controls to smooth the motion data."""
    auto_upd_flags = {'FRAME_PRE',}
    tree_type = "*ChildrenDefined*"
    
    target_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Target Object",
        description="Object to track velocity"
        )
    use_velocity_damping: bpy.props.BoolProperty(
        name="Velocity Damping",
        description="Enable or disable velocity damping. When disabled, velocity will stop immediately.",
        default=True
        )
    damping_factor: bpy.props.FloatProperty(
        name="Damping Factor",
        description="Factor to dampen object velocity (0.0 to 1.0)",
        min=0.0,
        max=1.0,
        default=0.7
        )
    damping_speed: bpy.props.FloatProperty(
        name="Damping Speed",
        description="Time in seconds before velocity damping is applied",
        min=0.01,
        soft_max=3.0,
        default=0.1,
        precision=2,
        subtype='TIME',
        unit='TIME'
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True
    
    def init(self, context):
        """this fct run when appending the node for the first time"""
        name = f".{self.bl_idname}"

        # Define socket types
        sockets = {
            "Direction": "NodeSocketVector",
            "Velocity": "NodeSocketFloat",
            "Acceleration": "NodeSocketFloat",
            "Stopping Power": "NodeSocketFloat",
            }
        descriptions = {
            "Direction": "Normalized direction vector of the object's movement",
            "Velocity": "Object velocity magnitude in meters per second (m/s)",
            "Acceleration": "Rate of velocity increase in meters per second squared (m/s²)",
            "Stopping Power": "Rate of velocity decrease in meters per second squared (m/s²)"
            }

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name, tree_type=self.tree_type,
                out_sockets=sockets, sockets_description=descriptions)

        ng = ng.copy()  # always using a copy of the original ng
        self.node_tree = ng

        self.width = 150

        # Initialize velocity dictionary
        init_objvelocities()

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

    def sync_out_values(self):
        """sync output socket values with data"""

        context = bpy.context
        wm = context.window_manager

        ng = self.node_tree
        if (not self.target_obj):
            set_ng_socket_defvalue(ng, socket_name="Direction", value=(0.0, 0.0, 0.0))
            set_ng_socket_defvalue(ng, socket_name="Velocity", value=0.0)
            set_ng_socket_defvalue(ng, socket_name="Acceleration", value=0.0)
            set_ng_socket_defvalue(ng, socket_name="Stopping Power", value=0.0)
            return None
        
        # Initialize object entry if it doesn't exist
        if not hasattr(wm, "objvelocities"):
            init_objvelocities()

        # Store object transformsg
        loc = tuple(self.target_obj.location)
        rot = tuple(self.target_obj.rotation_euler)
        sca = tuple(self.target_obj.scale)

        #get the object data, where we store the object transforms per frame
        if (self.target_obj.name not in wm.objvelocities):
            wm.objvelocities[self.target_obj.name] = {}
        OBJVEL = wm.objvelocities[self.target_obj.name]
        
        # Get current frame info
        current_frame = context.scene.frame_current
        current_time = context.scene.frame_current / context.scene.render.fps
        
        #if the timeline reset, we clear everything
        if (current_frame == context.scene.frame_start):
            OBJVEL.clear()

        # Store the current frame information
        OBJVEL[current_frame] = {
            "location": loc,
            "rotation": rot,
            "scale": sca,
            "time": current_time,
            }

        # Build history list for velocity calculation

        history = []
        maxhist = 10
        stored_frames = set(sorted(OBJVEL.keys()))
        frame_to_cover = [f for f in range(max(current_frame-maxhist,0), current_frame+1) if f in stored_frames]
        
        for frame in frame_to_cover:
            frame_data = OBJVEL[frame]
            history.append((
                frame_data["location"],
                frame_data["rotation"],
                frame_data["scale"],
                frame_data["time"]
                ))

        if (DEBUG):
            print("--------------------------------")
            print("current_frame", current_frame)
            print("stored_frames", stored_frames)
            print("frame_to_cover", frame_to_cover)
            print("calculate_object_metrics() start")
        # Calculate metrics
        direction, velocity_magnitude, acceleration, stopping_power = calculate_object_metrics(history)

        if (DEBUG):
            print("calculate_object_metrics() done")
            print(" -direction", direction)
            print(" -velocity_magnitude", velocity_magnitude)
            print(" -acceleration", acceleration)
            print(" -stopping_power", stopping_power)

        # # Only apply damping if explicitly enabled
        # if (self.use_velocity_damping and len(history) >= 2):
        #     pass
        #     # Get scene frame rate for time conversion
        #     fps = context.scene.render.fps
            
        #     # Check if the object hasn't moved for a frame
        #     if len(stored_frames) >= 2 and stored_frames[-1] > stored_frames[-2] + 1:
        #         # Object didn't move for at least one frame, apply damping
        #         time_since_last_movement = (stored_frames[-1] - stored_frames[-2]) / fps
                
        #         if time_since_last_movement > 0.01:  # Small threshold
        #             # Apply damping with the configured settings
        #             mult = self.damping_factor ** (time_since_last_movement / self.damping_speed)
                    
        #             # Direction stays normalized, only velocity gets damped
        #             velocity_magnitude *= mult
        #             acceleration *= mult
        #             stopping_power *= mult
                    
        #             # Set to zero if below threshold
        #             if velocity_magnitude < 0.01:  # 1cm/s threshold
        #                 direction = (0.0, 0.0, 0.0)
        #                 velocity_magnitude = 0.0
        #                 acceleration = 0.0
        #                 stopping_power = 0.0
        
        # Update node outputs
        set_ng_socket_defvalue(ng, socket_name="Direction", value=direction)
        set_ng_socket_defvalue(ng, socket_name="Velocity", value=velocity_magnitude)
        set_ng_socket_defvalue(ng, socket_name="Acceleration", value=acceleration)
        set_ng_socket_defvalue(ng, socket_name="Stopping Power", value=stopping_power)
        
        return None

    def draw_label(self):
        """node label"""
        if (self.label==''):
            return 'Object Velocity'
        return self.label

    def draw_buttons(self, context, layout):
        """node interface drawing"""
        
        col = layout.column()
        col.prop(self, "target_obj", text="")
        
        # col.separator(factor=0.5)
        # row = col.row()
        # row.prop(self, "use_velocity_damping", text="Use Damping",)
        
        # if (self.use_velocity_damping):
        #     col = layout.column()
        #     col.use_property_split = True
        #     col.use_property_decorate = False
        #     col.prop(self, "damping_factor", text="Factor", slider=True)
        #     col.prop(self, "damping_speed", text="Speed")
            
        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:

            col = panel.column(align=True)
            col.prop(self, "target_obj", text="")

            # header, panel = panel.panel("velocity_damping_panelid", default_closed=False)
            # header.prop(self, "use_velocity_damping", text="Velocity Damping")
            # if panel:
            #     col = panel.column()
            #     col.use_property_split = True
            #     col.use_property_decorate = False
            #     col.enabled = self.use_velocity_damping
            #     col.prop(self, "damping_factor", text="Factor", slider=True)
            #     col.prop(self, "damping_speed", text="Speed (sec)")

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
            
            # Debug info
            if hasattr(bpy.types.WindowManager, "objvelocities") and self.target_obj:
                wm = context.window_manager
                if self.target_obj.name in wm.objvelocities:
                    OBJVEL = wm.objvelocities[self.target_obj.name]
                    
                    col = panel.column(align=True)
                    col.label(text="Object Data:")
                    
                    box = col.box().column(align=True)
                    box.label(text=f"Tracked Frames: {len(OBJVEL.keys())}")
                    
                    # Show current frame velocity if available
                    current_frame = context.scene.frame_current
                    if current_frame in OBJVEL:
                        box.label(text=f"Current Frame: {current_frame}")
                        box.label(text=f"Location: {OBJVEL[current_frame]['location']}")
                    
                    # Show output socket values
                    box.separator(type='LINE')
                    box.label(text="Output Values:")
                    
                    for output in self.outputs:
                        value = self.node_tree.nodes["Group Output"].inputs[output.name].default_value
                        if output.type == 'VECTOR':
                            box.label(text=f"{output.name}: ({value[0]:.2f}, {value[1]:.2f}, {value[2]:.2f})")
                        else:
                            box.label(text=f"{output.name}: {value:.2f}")

        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """update all instances of this node in all node trees"""
        
        # Update all object velocity nodes
        for node in get_booster_nodes(by_idnames={
            NODEBOOSTER_NG_GN_ObjectVelocity.bl_idname,
            NODEBOOSTER_NG_SH_ObjectVelocity.bl_idname,
            NODEBOOSTER_NG_CP_ObjectVelocity.bl_idname,
            }):
            node.sync_out_values()

        return None


#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_ObjectVelocity(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_ObjectVelocity(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_ObjectVelocity(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname

