# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

import math
import numpy as np

from ..__init__ import get_addon_prefs
from ..utils.nbr_utils import map_range
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    create_new_nodegroup,
    set_ng_socket_defvalue,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
)


# NOTE use of AI
# These functions below were generated thanks to GPT 03-mini-high. I am no sound engineer...
# If you know more about sound than i do, don't hesitate to correct potential mistakes in the code below.

# TODO
# - bug if sound.use_mono
#   - when fixed need to support for mono pan as well..
# - Fix sum of sound, the we we add sounds together right now is false.

def evaluate_strip_audio_features(strip, frame, fps, depsgraph,
    volume=False, pitch=False, bass=False, treble=False, channel='CENTER', fade=1.0, frequencies=None,):
    """
    Evaluate audio features for a single sound strip at a given frame.
    Features (volume, bass, treble) are stored in the linear domain,
    and pitch (in Hz) remains linear.
    A precomputed 'fade' multiplier is applied to the raw audio before analysis.
    
    Parameters:
      strip     : the sound strip from the sequencer.
      frame     : current frame number.
      fps       : scene frames per second.
      depsgraph : dependency graph for evaluated data.
      volume    : (bool) if True, compute overall volume (as linear amplitude).
      pitch     : (bool) if True, estimate pitch (in Hz).
      bass      : (bool) if True, compute bass level (RMS linear amplitude).
      treble    : (bool) if True, compute treble level (RMS linear amplitude).
      channel   : 'LEFT', 'RIGHT', or 'CENTER' (averaged) channel selection.
      fade      : precomputed fade multiplier (from animated volume or fade-in/out).

    Returns:
      dict with keys for each requested feature.
      If no data is available or frame is out of range, all features default to 0.
    """

    sound = strip.sound
    ret = {}

    # If frame is not within the final range of the strip, return defaults (0)
    if (not (strip.frame_final_start < frame < strip.frame_final_end)) or (not sound):
        if volume: ret['volume'] = 0
        if pitch:  ret['pitch']  = 0
        if bass:   ret['bass']   = 0
        if treble: ret['treble'] = 0
        return ret

    # Calculate the time window (in seconds) for the current frame
    time_from = (frame - 1 - strip.frame_start) / fps
    time_to   = (frame - strip.frame_start) / fps

    audio = sound.evaluated_get(depsgraph).factory
    chunk = audio.limit(time_from, time_to).data()

    # If the audio chunk is empty, try a fallback by reading one extra frame
    if len(chunk) == 0:
        time_from_temp = (frame - 2 - strip.frame_start) / fps
        chunk = audio.limit(time_from_temp, time_to).data()

    # If still no data, return defaults (0)
    if len(chunk) == 0:
        if volume: ret['volume'] = 0
        if pitch:  ret['pitch']  = 0
        if bass:   ret['bass']   = 0
        if treble: ret['treble'] = 0
        return ret

    # Determine sample rate; default to 44100 Hz if not provided.
    sample_rate = 44100
    if hasattr(sound, "info") and "samplerate" in sound.info:
        sample_rate = sound.info["samplerate"]
    elif hasattr(sound, "samplerate"):
        sample_rate = sound.samplerate

    # Select the signal based on channel selection using match-case.
    if (chunk.ndim == 1 or sound.use_mono):
        signal = chunk
    else:
        match channel.upper():
            case 'LEFT':
                signal = chunk[:,0]
            case 'RIGHT':
                signal = chunk[:,1] if chunk.shape[1] > 1 else chunk[:,0]
            case _:
                # Default to CENTER: average of left and right channels.
                left  = chunk[:,0]
                right = chunk[:,1] if chunk.shape[1] > 1 else left
                signal = (left + right) / 2.0

    # Apply the fade multiplier (precomputed externally)
    volumeboost = strip.volume
    signal = signal * fade
    
    # Compute requested features
    # Volume: compute peak absolute amplitude (store in linear domain)
    if (volume):
        amp = np.max(np.abs(signal))
        amp *= volumeboost
        ret['volume'] = amp

    # For frequency-based features, perform FFT analysis only if needed.
    if (pitch or bass or treble):

        # Compute FFT and normalize by number of samples
        fft_result = np.fft.rfft(signal)
        N = len(signal)
        fft_result = fft_result / N
        freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)
        magnitudes = np.abs(fft_result)

        # Bass: compute RMS of magnitudes in the 20–250 Hz band (linear value)
        if (bass):
            minmax = frequencies['bass']
            freqrange = (freqs > minmax[0]) & (freqs < minmax[1])
            if np.any(freqrange):
                  value_rms = np.sqrt(np.mean(magnitudes[freqrange]**2))
                  value_rms *= volumeboost
                  ret['bass'] = value_rms * 5
            else: ret['bass'] = 0

        # Pitch estimation: find the frequency peak between 50–5000 Hz.
        if (pitch):
            minmax = frequencies['pitch']
            freqrange = (freqs > minmax[0]) & (freqs < minmax[1])
            if np.any(freqrange):
                  idx = np.argmax(magnitudes[freqrange])
                  value_hz = freqs[freqrange][idx]
                  value_hz = map_range(value_hz, minmax[0], minmax[1], 0,1,) #normalize
                  value_hz *= min(volumeboost,1)
                  ret['pitch'] = value_hz
            else: ret['pitch'] = 0

        # Treble: compute RMS of magnitudes above 4000 Hz (linear value)
        if (treble):
            minmax = frequencies['treble']
            freqrange = (freqs > minmax[0]) & (freqs < minmax[1])
            if np.any(freqrange):
                  value_rms = np.sqrt(np.mean(magnitudes[freqrange]**2))
                  value_rms *= min(volumeboost,1)
                  ret['treble'] = value_rms * 500
            else: ret['treble'] = 0

    return ret

def evaluate_smoothed_audio_features(strip, frame, fps, depsgraph, smoothing, smoothing_type,
    volume=False, pitch=False, bass=False, treble=False, channel='CENTER', fade=1.0, frequencies=None,):
    """
    Evaluate smoothed features over a window of frames using linear or Gaussian weighting.
    This function calls evaluate_strip_audio_features for each frame in the window.
    The features are stored in linear domain, then converted to dB during aggregation
    
    Parameters:
      smoothing      : number of frames in the window (ideally an odd number)
      smoothing_type : 'LINEAR' or 'GAUSSIAN'
      Other parameters are passed to evaluate_strip_audio_features.
      fade           : fade multiplier (assumed constant over the smoothing window)
      
    Returns a dict with the smoothed features. For amplitude-based features (volume, bass, treble),
    the values remain in linear form here.
    """
    half_window = smoothing // 2
    keys = []
    if volume: keys.append('volume')
    if pitch:  keys.append('pitch')
    if bass:   keys.append('bass')
    if treble: keys.append('treble')

    kwargs = {'volume':volume, 'pitch':pitch, 'bass':bass, 'treble':treble, 'channel':channel, 'fade':fade, 'frequencies':frequencies,}
    features_sum = { key: 0 for key in keys }
    weights = []

    match smoothing_type.upper():

        case "LINEAR":
            for offset in range(-half_window, half_window + 1):
                f = frame + offset
                weights.append(1)
                feats = evaluate_strip_audio_features(strip, f, fps, depsgraph, **kwargs)
                for key in keys:
                    features_sum[key] += feats.get(key, 0)

        case "GAUSSIAN":
            sigma = smoothing / 3.0  # standard deviation controls falloff
            for offset in range(-half_window, half_window + 1):
                f = frame + offset
                weight = math.exp(-0.5 * (offset / sigma) ** 2)
                weights.append(weight)
                feats = evaluate_strip_audio_features(strip, f, fps, depsgraph, **kwargs)
                for key in keys:
                    features_sum[key] += feats.get(key, 0) * weight

    total_weight = sum(weights)
    smoothed = {}
    for key in keys:
        smoothed[key] = features_sum[key] / total_weight

    return smoothed

# NOTE work in decibel? unsure if it makes sense in a digital space.
# def amplitude_to_db(amplitude):
#     """Convert a linear amplitude (0–1) to decibels (dBFS).
#     In our digital domain, 1.0 is 0 dBFS. If the amplitude is very small (i.e. silence), we return 0."""
#     if (amplitude < 1e-10):
#         return 0
#     return 20 * math.log10(amplitude)

def evaluate_sequencer_audio_data(frame_offset=0, at_sequence_name=None, smoothing=0, 
    smoothing_type='GAUSSIAN', volume=False, pitch=False, bass=False, treble=False, channel='CENTER', frequencies=None,):
    """
    Evaluate aggregated audio features from all non-muted sound strips in the sequencer.
    Fade logic is computed here (using animated volume or fade-in/out), and then features
    (stored in linear) are aggregated using the helper.

    Parameters:
      frame_offset     : offset added to the current scene frame.
      at_sequence_name : if provided (string), only consider the sequence with this name.
      smoothing        : smoothing window size (if <= 1, no smoothing is applied).
      smoothing_type   : 'LINEAR' or 'GAUSSIAN' smoothing.
      volume, pitch, bass, treble : booleans for which features to compute.
      channel          : 'LEFT', 'RIGHT', or 'CENTER' for channel selection.

    Returns:
      dict with aggregated features. For amplitude-based features, the final result is
      converted to decibels; pitch remains in Hz.

    This function computes a fade multiplier per strip (using animated volume or fade-in/out)
    and then evaluates (optionally smoothed) features per strip. Finally, it aggregates the
    results using aggregate_sounds.
    """
    scene = bpy.context.scene
    vse = scene.sequence_editor
    if ((vse is None) or not (volume or pitch or bass or treble)):
        return {'volume':0, 'pitch':0, 'bass':0, 'treble':0,}

    sequences = vse.sequences_all
    depsgraph = bpy.context.evaluated_depsgraph_get()
    fps = scene.render.fps / scene.render.fps_base
    frame = scene.frame_current + frame_offset

    # Filter for non-muted sound strips; if at_sequence_name is provided, restrict to that sequence.
    sound_sequences = [s for s in sequences if (s.type == 'SOUND')]
    if (at_sequence_name):
        sound_sequences = [s for s in sound_sequences if (s.name == at_sequence_name)]

    # Determine which features to aggregate.
    keys = []
    if volume: keys.append('volume')
    if pitch:  keys.append('pitch')
    if bass:   keys.append('bass')
    if treble: keys.append('treble')
    
    # Dictionary to hold aggregated (value, weight) pairs.
    total = {k:[] for k in keys}

    # Loop through each sound strip.
    for s in sound_sequences:
        
        #ignore if muted or no sound
        if (s.mute):
            continue
        if (not s.sound):
            continue
        
        # Compute effective fade for this strip at the target frame?
        # effective_fade = local_get_fade(s, frame)
        effective_fade = 1

        # Evaluate features (with smoothing if requested).
        kwargs = {'volume':volume, 'pitch':pitch, 'bass':bass, 'treble':treble, 'channel':channel, 'fade':effective_fade, 'frequencies':frequencies,}
        if (smoothing > 1):
              feats = evaluate_smoothed_audio_features(s, frame, fps, depsgraph, smoothing, smoothing_type, **kwargs,)
        else: feats = evaluate_strip_audio_features(s, frame, fps, depsgraph, **kwargs)

        # Use effective_fade as the weight (can be adjusted if needed).
        effective_weight = effective_fade
        for k in keys:
            total[k].append((feats.get(k,0), effective_weight))

    # Make value total. 
    # TODO i'm almost sure that's not how we add up sounds together.. Need a specialist.
    sumtotal = {}
    for k in keys:
        total_weight = sum(w for (_, w) in total[k])
        if (total_weight==0):
            sumtotal[k] = 0
            continue
        tot = sum(val * w for (val, w) in total[k]) / total_weight
        sumtotal[k] = tot
        continue

    return sumtotal

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():
    
    bl_idname = "NodeBoosterSequencerSound"
    bl_label = "Sequencer Sound"
    bl_description = """Analyze the active sound of the VideoSequencer editor.
    • Get the Generic Sound volume, the Bass/Pitch/Treble tones as well.
    • Bass/Pitch/Treble Tones components fall within define frequencies in Hz units.
    • If you wish to view or customize these Bass/Pitch/Treble frequencies go in 'N panel > Node Booster > Active node > Parameters'.
    • Expect the value to be automatically updated on each on depsgraph post signals"""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST',}
    tree_type = "*ChildrenDefined*"


    def update_signal(self,context):
        self.sync_out_values()
        return None 

    channel : bpy.props.EnumProperty(
        name= "Sound Channels",
        description= "Specify which channel to sample",
        default= 'CENTER',
        items= [('LEFT',   "Stereo Left",  "Sample the left stereo channel",),
                ('RIGHT',  "Stereo Right", "Sample the right stereo channel",),
                ('CENTER', "Mono",         "Sample the file as a mono channel",),],
        update= update_signal,
        )
    target : bpy.props.EnumProperty(
        name= "Sound Target",
        description= "Specify how to sample",
        default= 'ALL',
        items= [('ALL',     "All Sequences",  "Sample all sound strips",),
                ('SPECIFY', "Chosen Sequence", "Sample a only the strips assigned to the given sound data",),],
        update= update_signal,
        )
    offset : bpy.props.IntProperty(
        default= 0,
        name= "Offset",
        description= "Offset the sampled frame by a given number",
        update=update_signal,
        )
    smoothing : bpy.props.IntProperty(
        default= 0,
        min= 0,
        soft_max= 10,
        name= "Smoothing",
        description= "Smooth out the result",
        update=update_signal,
        )
    sequence_name : bpy.props.StringProperty(
        name= "Sound Sequence",
        description= "Select a sound sequence from the VSE",
        default="",
        update=update_signal,
        search=lambda self,context,text:  [s.name for s in context.scene.sequence_editor.sequences_all if (s.type=='SOUND') and (text in s.name)],
        search_options={'SUGGESTION','SORT'},
        )
    deffreq : bpy.props.BoolProperty(
        default=False,
        name= "Custom Frequencies",
        description= "Define Custom Frequencies for the various channels",
        update=update_signal,
        )
    freqbass : bpy.props.IntVectorProperty(
        name="Bass",
        description="Bass Frequencies min/max range.",
        default=(20, 250),
        size=2,
        soft_min=0,
        soft_max=25_000,
        update=update_signal,
        )
    freqpitch : bpy.props.IntVectorProperty(
        name="Pitch",
        description="Pitch Frequencies min/max range.",
        default=(200, 5_000),
        size=2,
        soft_min=0,
        soft_max=25_000,
        update=update_signal,
        )
    freqtreble : bpy.props.IntVectorProperty(
        name="Treble",
        description="Treble Frequencies min/max range.",
        default=(4_000, 25_000),
        size=2,
        soft_min=0,
        soft_max=25_000,
        update=update_signal,
        )
    #default.. to show user defaults
    defafreqbass : bpy.props.IntVectorProperty(
        name="Bass",
        description="Bass Frequencies min/max range.",
        default=(20, 250),
        size=2,
        )
    defafreqpitch : bpy.props.IntVectorProperty(
        name="Pitch",
        description="Pitch Frequencies min/max range.",
        default=(200, 5_000),
        size=2,
        )
    defafreqtreble : bpy.props.IntVectorProperty(
        name="Treble",
        description="Treble Frequencies min/max range.",
        default=(4_000, 25_000),
        size=2,
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
                out_sockets={
                    "Volume": "NodeSocketFloat",
                    "Bass": "NodeSocketFloat",
                    "Pitch": "NodeSocketFloat",
                    "Treble": "NodeSocketFloat",
                    },
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

        self.width = 140

        return None 

    def copy(self,node,):
        """fct run when dupplicating the node"""
        
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

        ng = self.node_tree
        vse = bpy.context.scene.sequence_editor

        # check user links, this node is a bit expensive to evaluate.
        # so let's not evaluate if not needed.
        evalvolume = bool(self.outputs['Volume'].links)
        evalpitch  = bool(self.outputs['Pitch'].links)
        evalbass   = bool(self.outputs['Bass'].links)
        evaltreble = bool(self.outputs['Treble'].links)
        valid = (evalvolume or evalpitch or evalbass or evaltreble) and (vse is not None)

        # Check if the target is a specific sound sequence
        at_sequence_name = None
        if (self.target == 'SPECIFY'):
            target_seq = vse.sequences_all.get(self.sequence_name) if (vse) else None
            if ((target_seq is None) or (target_seq.type != 'SOUND')):
                valid = False
            else:
                at_sequence_name = self.sequence_name

        # If not valid circumpstance, no evaluation & go back to default.
        if (not valid):
            set_ng_socket_defvalue(ng, socket_name='Volume',value=0,)
            set_ng_socket_defvalue(ng, socket_name='Pitch',value=0,)
            set_ng_socket_defvalue(ng, socket_name='Bass',value=0,)
            set_ng_socket_defvalue(ng, socket_name='Treble',value=0,)
            return None

        #update frequencies range?
        if (self.deffreq):
              frequencies = {'bass':self.freqbass[:],'pitch':self.freqpitch[:],'treble':self.freqtreble[:],}
        else: frequencies = {'bass':self.defafreqbass[:],'pitch':self.defafreqpitch[:],'treble':self.defafreqtreble[:],}

        data = evaluate_sequencer_audio_data(
            frame_offset=self.offset,
            smoothing=self.smoothing,
            at_sequence_name=at_sequence_name,
            volume=evalvolume,
            pitch=evalpitch,
            bass=evalbass,
            treble=evaltreble,
            channel=self.channel,
            frequencies=frequencies,
            )

        if (evalvolume):
              set_ng_socket_defvalue(ng, socket_name='Volume',value=data['volume'],)
        else: set_ng_socket_defvalue(ng, socket_name='Volume',value=0,)

        if (evalpitch):
              set_ng_socket_defvalue(ng, socket_name='Pitch',value=data['pitch'],)
        else: set_ng_socket_defvalue(ng, socket_name='Pitch',value=0,)

        if (evalbass):
              set_ng_socket_defvalue(ng, socket_name='Bass',value=data['bass'],)
        else: set_ng_socket_defvalue(ng, socket_name='Bass',value=0,)

        if (evaltreble):
              set_ng_socket_defvalue(ng, socket_name='Treble',value=data['treble'],)
        else: set_ng_socket_defvalue(ng, socket_name='Treble',value=0,)

        return None
    
    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Sequencer Sound'
        return self.label

    def draw_buttons(self,context,layout,):
        """node interface drawing"""

        vse = bpy.context.scene.sequence_editor
        
        layout.prop(self, "channel", text="")
        layout.prop(self, "target", text="")

        if (self.target=='SPECIFY'):
            prop = layout.column(align=True)
            prop.prop(self, "sequence_name", text="", icon='SEQ_SEQUENCER')
            # if (vse and vse.sequences_all.get(self.sequence_name)):
            #     seq = vse.sequences_all[self.sequence_name]
            #     if (seq.type != 'SOUND') or (not hasattr(seq,'sound')) or (not seq.sound):
            #         label = prop.box()
            #         label.scale_y = 0.5
            #         label.alert = True
            #         label.label(text="No sound data.",)
            #     elif (seq.mute):
            #         label = prop.box()
            #         label.scale_y = 0.5
            #         label.alert = True
            #         label.label(text="Strip is muted.",)
            #     else:
            #         prop.template_ID(seq, "sound", open="sound.open")
            prop.separator(factor=0.333)

        col = layout.column()
        col.prop(self, "offset",)
        col.prop(self, "smoothing",)

        return None 

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
    
        n = self
        vse = bpy.context.scene.sequence_editor

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):
            
            panel.prop(self, "channel", text="")
            panel.prop(self, "target", text="")

            if (self.target=='SPECIFY'):
                prop = panel.column(align=True)
                prop.prop(self, "sequence_name", text="", icon='SEQ_SEQUENCER')
                prop.separator(factor=0.333)

            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, "offset",)
            col.prop(self, "smoothing", text="Smooth",)

            col = panel.column(heading="Tones")
            col.use_property_split = True
            col.use_property_decorate = False            
            col.prop(self, "deffreq",text="Custom")

            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.enabled = self.deffreq
            col.prop(self, f"{'' if self.deffreq else 'defa'}freqbass",)
            col.prop(self, f"{'' if self.deffreq else 'defa'}freqpitch",)
            col.prop(self, f"{'' if self.deffreq else 'defa'}freqtreble",)

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

        if (using_nodes is None):
              nodes = get_booster_nodes(by_idnames={cls.bl_idname},)
        else: nodes = [n for n in using_nodes if (n.bl_idname==cls.bl_idname)]

        for n in nodes:
            if (n.mute):
                continue
            n.sync_out_values()

        return None

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_SequencerSound(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_SequencerSound(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_SequencerSound(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname