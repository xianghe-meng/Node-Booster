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

import bpy, math, numpy as np

# def amplitude_to_db(amplitude):
#     """Convert a linear amplitude (0–1) to decibels (dBFS).
#     In our digital domain, 1.0 is 0 dBFS. If the amplitude is very small (i.e. silence), we return 0."""
#     if (amplitude < 1e-10):
#         return 0
#     return 20 * math.log10(amplitude)

def evaluate_strip_audio_features(strip, frame, fps, depsgraph,
    volume=False, pitch=False, bass=False, treble=False, channel='CENTER', fade=1.0,):
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
      bass      : (bool) if True, compute bass level (RMS in 20–250Hz, linear amplitude).
      treble    : (bool) if True, compute treble level (RMS above 4000Hz, linear amplitude).
      channel   : 'LEFT', 'RIGHT', or 'CENTER' (averaged) channel selection.
      fade      : precomputed fade multiplier (from animated volume or fade-in/out).
      
    Returns:
      dict with keys for each requested feature.
      If no data is available or frame is out of range, all features default to 0.
    """
    ret = {}
    # If frame is not within the final range of the strip, return defaults (0)
    if not (strip.frame_final_start < frame < strip.frame_final_end):
        if volume: ret['volume'] = 0
        if pitch:  ret['pitch']  = 0
        if bass:   ret['bass']   = 0
        if treble: ret['treble'] = 0
        return ret

    # Calculate the time window (in seconds) for the current frame
    time_from = (frame - 1 - strip.frame_start) / fps
    time_to   = (frame - strip.frame_start) / fps

    sound = strip.sound
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
    signal = signal * fade
    
    #TODO support sound.pan if use_mono

    # Compute requested features
    # Volume: compute peak absolute amplitude (store in linear domain)
    if (volume):
        amp = np.max(np.abs(signal))
        ret['volume'] = amp

    # For frequency-based features, perform FFT analysis only if needed.
    if (pitch or bass or treble):
        fft_result = np.fft.rfft(signal)
        freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)
        magnitudes = np.abs(fft_result)

        # Pitch estimation: find the frequency peak between 50–5000 Hz.
        if (pitch):
            valid = (freqs > 50) & (freqs < 5000)
            if np.any(valid):
                  idx = np.argmax(magnitudes[valid])
                  ret['pitch'] = freqs[valid][idx]
            else: ret['pitch'] = 0

        # Bass: compute RMS of magnitudes in the 20–250 Hz band (linear value)
        if (bass):
            bass_range = (freqs > 20) & (freqs < 250)
            if np.any(bass_range):
                  bass_rms = np.sqrt(np.mean(magnitudes[bass_range]**2))
                  ret['bass'] = bass_rms
            else: ret['bass'] = 0

        # Treble: compute RMS of magnitudes above 4000 Hz (linear value)
        if (treble):
            treble_range = freqs > 4000
            if np.any(treble_range):
                  treble_rms = np.sqrt(np.mean(magnitudes[treble_range]**2))
                  ret['treble'] = treble_rms
            else: ret['treble'] = 0

    return ret

def evaluate_smoothed_audio_features(strip, frame, fps, depsgraph, smoothing, smoothing_type,
    volume=False, pitch=False, bass=False, treble=False, channel='CENTER', fade=1.0,):
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

    features_sum = { key: 0 for key in keys }
    weights = []

    match smoothing_type.upper():

        case "LINEAR":
            for offset in range(-half_window, half_window + 1):

                f = frame + offset
                weight = 1
                weights.append(weight)

                feats = evaluate_strip_audio_features(strip, f, fps, depsgraph,
                    volume=volume, pitch=pitch, bass=bass, treble=treble, channel=channel, fade=fade,)

                for key in keys:
                    features_sum[key] += feats.get(key, 0)

        case "GAUSSIAN":
            sigma = smoothing / 3.0  # standard deviation controls falloff
            for offset in range(-half_window, half_window + 1):
                
                f = frame + offset
                weight = math.exp(-0.5 * (offset / sigma) ** 2)
                weights.append(weight)

                feats = evaluate_strip_audio_features(strip, f, fps, depsgraph,
                    volume=volume, pitch=pitch, bass=bass, treble=treble, channel=channel, fade=fade,)

                for key in keys:
                    features_sum[key] += feats.get(key, 0) * weight

    total_weight = sum(weights)
    smoothed = {}
    for key in keys:
        smoothed[key] = features_sum[key] / total_weight

    return smoothed

def local_get_fade(strip, frame):
    """
    Compute fade multiplier based on animated volume (F-Curve) or audio fade properties.
    If an F-Curve for 'volume' exists, return its value;
    otherwise, if audio_fadein/audio_fadeout are available, compute linear fade;
    else, return the strip's base volume.
    """

    if (strip.animation_data and strip.animation_data.action):
        for fc in strip.animation_data.action.fcurves:
            if (fc.data_path=='volume'):
                return fc.evaluate(frame)

    if (hasattr(strip,'audio_fadein') and hasattr(strip,'audio_fadeout')):
        fade = 1.0
        if (strip.audio_fadein > 0 and frame < (strip.frame_start + strip.audio_fadein)):
            fade = (frame - strip.frame_start) / strip.audio_fadein
        elif (strip.audio_fadeout > 0 and frame > (strip.frame_final_end - strip.audio_fadeout)):
            fade = (strip.frame_final_end - frame) / strip.audio_fadeout
        return fade * strip.volume

    return strip.volume

def aggregate_feature_values(feature_list, feature_type):
    """
    Aggregate a list of (value, weight) pairs for a feature.
    For 'pitch', we compute a weighted linear average.
    For amplitude-based features (denoted by 'db'), we assume values are linear

    Parameters:
      feature_list : list of tuples (value, weight)
      feature_type : either 'pitch' or 'db'

    Returns the aggregated value. If total weight is 0, returns 0.
    """

    #TODO perhaps we do a bad job at aggregation. Adding sound together 
    # is not linear... Someone specialized need to understand that a bit better.
    
    total_weight = sum(w for (_, w) in feature_list)
    if (total_weight==0):
        return 0

    match feature_type:
        case 'pitch':
            return sum(val * w for (val, w) in feature_list) / total_weight
        case 'db':
            # Values are in linear domain; compute weighted average and convert to dB.
            linear_avg = sum(val * w for (val, w) in feature_list) / total_weight
            return linear_avg
        case _:
            raise Exception('Wront feature type')

def evaluate_sequencer_audio_features(frame_offset=0, at_sound=None, smoothing=0, 
    smoothing_type='GAUSSIAN', volume=False, pitch=False, bass=False, treble=False, channel='CENTER'):
    """
    Evaluate aggregated audio features from all non-muted sound strips in the sequencer.
    Fade logic is computed here (using animated volume or fade-in/out), and then features
    (stored in linear) are aggregated using the helper.

    Parameters:
      frame_offset   : offset added to the current scene frame.
      at_sound       : if provided, only consider strips with this sound data.
      smoothing      : smoothing window size (if <= 1, no smoothing is applied).
      smoothing_type : 'LINEAR' or 'GAUSSIAN' smoothing.
      volume, pitch, bass, treble : booleans for which features to compute.
      channel        : 'LEFT', 'RIGHT', or 'CENTER' for channel selection.

    Returns:
      dict with aggregated features. For amplitude-based features, the final result is
      converted to decibels; pitch remains in Hz.

    This function computes a fade multiplier per strip (using animated volume or fade-in/out)
    and then evaluates (optionally smoothed) features per strip. Finally, it aggregates the
    results using aggregate_feature_values.
    """
    scene = bpy.context.scene
    vse = scene.sequence_editor
    if ((vse is None) or not (volume or pitch or bass or treble)):
        return {'volume':0, 'pitch':0, 'bass':0, 'treble':0,}

    sequences = vse.sequences_all
    depsgraph = bpy.context.evaluated_depsgraph_get()
    fps = scene.render.fps / scene.render.fps_base
    frame = scene.frame_current + frame_offset

    # Filter for non-muted sound strips; if at_sound is provided, restrict to those.
    sound_sequences = [s for s in sequences if (s.type == 'SOUND') and (not s.mute)]
    if (at_sound):
        sound_sequences = [s for s in sound_sequences if (s.sound==at_sound)]

    # Determine which features to aggregate.
    keys = []
    if volume: keys.append('volume')
    if pitch:  keys.append('pitch')
    if bass:   keys.append('bass')
    if treble: keys.append('treble')
    
    # Dictionary to hold aggregated (value, weight) pairs.
    aggregated = {key:[] for key in keys}

    # Loop through each sound strip.
    for s in sound_sequences:

        # Compute effective fade for this strip at the target frame.
        # effective_fade = local_get_fade(s, frame)
        effective_fade = 1

        # Evaluate features (with smoothing if requested).
        kwargs = {'volume':volume, 'pitch':pitch, 'bass':bass, 'treble':treble, 'channel':channel, 'fade':effective_fade,}
        if smoothing > 1:
              feats = evaluate_smoothed_audio_features(s, frame, fps, depsgraph, smoothing, smoothing_type, **kwargs)
        else: feats = evaluate_strip_audio_features(s, frame, fps, depsgraph, **kwargs)

        # Use effective_fade as the weight (can be adjusted if needed).
        effective_weight = effective_fade
        for key in keys:
            aggregated[key].append((feats.get(key, 0), effective_weight))

    # Aggregate values for each feature using the helper.
    result = {}
    for key in keys:
        mode = 'pitch' if (key=='pitch') else 'db'
        result[key] = aggregate_feature_values(aggregated[key], mode)

    return result

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
        items= [('ALL',     "All Sounds",     "Sample all sound strips",),
                ('SPECIFY', "Specific Sound", "Sample a only the strips assigned to the given sound data",),],
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
    sound : bpy.props.PointerProperty(
        name= "Sound Datablock",
        description= "Select a sound datablock used in the VSE (from sound sequences)",
        type= bpy.types.Sound,
        poll= sound_datablock_poll,
        update=update_signal,
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
                    "Pitch": "NodeSocketFloat",
                    "Bass": "NodeSocketFloat",
                    "Treble": "NodeSocketFloat",
                    },
                )

        ng = ng.copy() #always using a copy of the original ng

        self.node_tree = ng
        self.width = 140
        self.label = self.bl_label

        return None 

    def copy(self,node,):
        """fct run when dupplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None 
    
    def update(self):
        """generic update function"""

        ng = self.node_tree
        vse = bpy.context.scene.sequence_editor
            
        evalvolume = bool(self.outputs['Volume'].links)
        evalpitch  = bool(self.outputs['Pitch'].links)
        evalbass   = bool(self.outputs['Bass'].links)
        evaltreble = bool(self.outputs['Treble'].links)

        if (not (evalvolume or evalpitch or evalbass or evaltreble)) \
            or ((self.target=='SPECIFIC') and (not self.sound)) \
            or (vse is None):
            set_socket_defvalue(ng, socket_name='Volume',value=0,)
            set_socket_defvalue(ng, socket_name='Pitch',value=0,)
            set_socket_defvalue(ng, socket_name='Bass',value=0,)
            set_socket_defvalue(ng, socket_name='Treble',value=0,)
            return None

        data = evaluate_sequencer_audio_features(
            frame_offset=self.offset,
            smoothing=self.smoothing,
            at_sound=self.sound,
            volume=evalvolume,
            pitch=evalpitch,
            bass=evalbass,
            treble=evaltreble,
            channel=self.channel,
            )

        print(data)

        if (evalvolume):
              set_socket_defvalue(ng, socket_name='Volume',value=data['volume'],)
        else: set_socket_defvalue(ng, socket_name='Volume',value=0,)

        if (evalpitch):
              set_socket_defvalue(ng, socket_name='Pitch',value=data['pitch'],)
        else: set_socket_defvalue(ng, socket_name='Pitch',value=0,)

        if (evalbass):
              set_socket_defvalue(ng, socket_name='Bass',value=data['bass'],)
        else: set_socket_defvalue(ng, socket_name='Bass',value=0,)

        if (evaltreble):
              set_socket_defvalue(ng, socket_name='Treble',value=data['treble'],)
        else: set_socket_defvalue(ng, socket_name='Treble',value=0,)

        return None
    
    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self,context,layout,):
        """node interface drawing"""

        layout.prop(self, "channel", text="")
        layout.prop(self, "target", text="")

        row = layout.row(align=True)
        prop = row.row(align=True)
        if (self.target=='SPECIFY'):
            prop.prop(self, "sound", text="", icon="SOUND",)

        col = layout.column()
        col.prop(self, "offset",)
        col.prop(self, "smoothing",)

        return None 

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
    
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):
            
            panel.prop(self, "channel", text="")
            panel.prop(self, "target", text="")

            row = panel.row(align=True)
            prop = row.row(align=True)
            if (self.target=='SPECIFY'):
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