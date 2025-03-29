# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

import math

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    create_new_nodegroup,
    set_socket_defvalue,
    get_all_nodes,
)


def evaluate_strip_volume(strip, frame, fps, depsgraph):
    """evaluate a stip volume at given frame"""

    #skip if the frame is outside of the strip range
    if not (strip.frame_final_start < frame < strip.frame_final_end):
        return 0

    time_from = (frame - 1 - strip.frame_start) / fps
    time_to = (frame - strip.frame_start) / fps

    sound = strip.sound
    audio = sound.evaluated_get(depsgraph).factory
    chunk = audio.limit(time_from, time_to).data()

    #sometimes the chunks cannot be read properly, try to read 2 frames instead
    if (len(chunk)==0):
        time_from_temp = (frame - 2 - strip.frame_start) / fps
        chunk = audio.limit(time_from_temp, time_to).data()

    #chunk still couldnt be read...
    if (len(chunk)==0):
        return 0

    cmax, cmin = abs(chunk.max()), abs(chunk.min())
    value = cmax if (cmax > cmin) else cmin

    return value

def evaluate_smoothed_volume(strip, frame, fps, depsgraph, smoothing, smoothing_type):
    """Smoothed volume using Gaussian weights or average of values."""

    half_window = smoothing // 2
    values = []

    match smoothing_type:

        case 'LINEAR':

            for offset in range(-half_window, half_window + 1):
                f = frame + offset
                values.append(evaluate_strip_volume(strip, f, fps, depsgraph))

            smoothed = sum(values) / len(values)

        case 'GUASSIAN':

            weights = []
            sigma = smoothing / 3  # standard deviation controls falloff

            for offset in range(-half_window, half_window + 1):
                f = frame + offset
                value = evaluate_strip_volume(strip, f, fps, depsgraph)
                weight = math.exp(-0.5 * (offset / sigma) ** 2)
                values.append(value * weight)
                weights.append(weight)

            smoothed = sum(values) / sum(weights) if weights else 0

    return smoothed

def evaluate_sequencer_volume(frame_offset=0, at_sound=None, smoothing=0,):
    """evaluate the sequencer volume source
    this fct was possible thanks to tintwotin https://github.com/snuq/VSEQF/blob/3ac717e1fa8c7371ec40503428bc2d0d004f0b35/vseqf.py#L142"""

    scene = bpy.context.scene
    vse = scene.sequence_editor
    if (vse is None):
        return 0

    sequences = vse.sequences_all
    depsgraph = bpy.context.evaluated_depsgraph_get()
    fps = scene.render.fps / scene.render.fps_base
    frame = scene.frame_current + frame_offset

    #define sequences we are working with, either all sound, or a specific sound data
    sound_sequences = [s for s in sequences if (s.type=='SOUND') and (not s.mute)]
    if (at_sound):
        sound_sequences = [s for s in sequences if (s.sound==at_sound)]

    total = 0

    #for every strips..
    for s in sound_sequences:

        #get our strip volume
        if (smoothing > 1):
              value = evaluate_smoothed_volume(s, frame, fps, depsgraph, smoothing, 'GUASSIAN')
        else: value = evaluate_strip_volume(s, frame, fps, depsgraph)

        # TODO: for later? get fade curve https://github.com/snuq/VSEQF/blob/8487c256db536eb2e9288a16248fe394d06dfb74/fades.py#L57
        # fcurve = get_fade_curve(bpy.context, s, create=False)
        # if (fcurve):
        #       volume = fcurve.evaluate(frame)
        # else: volume = s.volume

        volume = s.volume
        total += (value * volume)
        continue 

    return float(total)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():
    
    bl_idname = "NodeBoosterSequencerVolume"
    bl_label = "Sequencer Volume"
    bl_description = """Custom Nodgroup: Evaluate the active sound level of the VideoSequencer editor.
    • Expect the value to be automatically updated on each on depsgraph post signals"""
    auto_update = {'FRAME_PRE','DEPS_POST',}
    tree_type = "*ChildrenDefined*"

    # frame_delay : bpy.props.IntProperty()

    def sound_datablock_poll(self, sound):
        """Poll function: only allow sounds that are used in the current scene’s VSE."""
        vse = bpy.context.scene.sequence_editor
        if (vse is None):
            return False
        for s in vse.sequences_all:
            if (s.type=='SOUND' and s.sound==sound):
                return True
        return False

    def update_signal(self,context):
        self.update()
        return None 

    sample_context : bpy.props.EnumProperty(
        name= "Sound Target",
        description= "Specify how to sample",
        default= 'ALL',
        items= [('ALL',    "All",       "Sample all sound sequence",),
                 ('SPECIFY', "Specific", "Sample a one only the sequences with the given sound data",),],
        update= update_signal,
        )
    offset : bpy.props.IntProperty(
        default= 0,
        name= "Offset",
        description= "Offset the sampled frame by a given number",
        )
    smoothing : bpy.props.IntProperty(
        default= 0,
        min= 0,
        soft_max= 10,
        name= "Smoothing",
        description= "Smooth out the result",
        )
    sound : bpy.props.PointerProperty(
        name= "Sound Datablock",
        description= "Select a sound datablock used in the VSE (from sound sequences)",
        type= bpy.types.Sound,
        poll= sound_datablock_poll,
        )
    
    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self,context,):        
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={"Volume" : "NodeSocketFloat",},)

        ng = ng.copy() #always using a copy of the original ng

        self.node_tree = ng
        self.width = 130
        self.label = self.bl_label

        return None 

    def copy(self,node,):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None 
    
    def update(self):
        """generic update function"""
        
        #deny update if output not used. Can be heavy to calculate.        
        if (not self.outputs['Volume'].links):
            return None

        ng = self.node_tree

        if ((self.sample_context=='SPECIFIC') and (not self.sound)):
            volume = 0
        else:
            volume = evaluate_sequencer_volume(
                frame_offset=self.offset,
                smoothing=self.smoothing,
                at_sound=self.sound,
                )

        set_socket_defvalue(ng, 0, value=volume,)

        return None
    
    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self,context,layout,):
        """node interface drawing"""

        layout.prop(self, "sample_context", expand=True,)
        
        row = layout.row(align=True)
        prop = row.row(align=True)
        prop.active = self.sample_context=='SPECIFY'
        prop.prop(self, "sound", text="", icon="SOUND",)

        col = layout.column()
        # col.use_property_split = True
        # col.use_property_decorate = False
        col.prop(self, "offset",)
        col.prop(self, "smoothing",)

        return None 

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
    
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):
            
            row = panel.row(align=True)
            row.prop(self, "sample_context", expand=True,)
            
            row = panel.row(align=True)
            prop = row.row(align=True)
            prop.active = self.sample_context=='SPECIFY'
            prop.prop(self, "sound", text="", icon="SOUND",)

            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, "offset",)
            col.prop(self, "smoothing", text="Smooth",)

        header, panel = layout.panel("doc_panelid", default_closed=True,)
        header.label(text="Documentation",)
        if (panel):
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description,
                )
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free"

        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False

            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")

        return None

    @classmethod
    def update_all_instances(cls, from_autoexec=False,):
        """search for all nodes of this type and update them"""

        #TODO we call update_all_instances for a lot of nodes from depsgraph & we need to optimize this, because func below may recur a LOT of nodes
        # could pass a from_nodes arg in this function
        for n in get_all_nodes(
            geometry=True, compositing=True, shader=True, 
            ignore_ng_name="NodeBooster", match_idnames={cls.bl_idname},
            ): 
            n.update()

        return None

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_SequencerVolume(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_SequencerVolume(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_SequencerVolume(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname