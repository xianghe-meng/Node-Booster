# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# ---------------------------------------------------------------------------------------------

# TODO v2.0 release
#  - Actually, we don’t need triple CustomNodeGroup! not needed! Could use context.space_data to guess type. One class only. 
#     - change the menu.py system then.
#  - Custom operator shortcuts are not saved, they reset on each blender sessions.
#  - Functions should always check if a value or type isn't already set before setting it. 
#    I believe the tool is currently sending a lot of useless update signals by setting the same values 
#    (see compositor refresh, perhaps it's because of node.update()?? need to investigate)
#  - Finalize NexScript for Shader/compositor. Need to overview functions..
#  - Codebase review for extension.. Ask AI to do a big check.
#  - Velocity Node: Better history calculations just doing last middle first is not precise enough. 
#  - Experiment with custom Socket Types:
#     - For this to work in geometry node, we'll need this PR to get accepted 
#       https://projects.blender.org/blender/blender/pulls/136968
#     - Experimental Interpolation
#       - supported nested ng? or not.
#       - Document why it crash on blender reload. Specific to geomtry node not supporting custom NodeSocket. 
#         Report once the proof of concept is done. devs need to see it's worth it.
#       - Why is there a triple update signal when adding a new node?
#       - Implement transform curves evaluators. 
#            - Better structure for the node_tree evaluator system? Centralized the functions in one place maybe?
#              Do more tests with InterpolationSocket transformers.
#              what about storing the evaluated values somewhere, and only recalculate when needed? maybe add a is_dirty flag?
#              maybe could simply store a 'StringProperty' .evaluator_cache per sockets?
#       - if possible, then we can cross the todo in  'Change to C blender code' for custom socket types.
#          - Start with custom interpolation types. See if MapRange can be ported. Could linearmaprange to 01 then use the FloatMapCurve then map range to custom values. 
#            The final nodes would simply do the evaluation. would not be nodegroup compatible tho. Problem:

# ---------------------------------------------------------------------------------------------

# NOTE Ideas for changes of blender C source code:
#  - There's a little message box above a node in GN, how can we write one via python API? 
#  - Color of some nodes should'nt be red. sometimes blue for converter (math expression) or script color..
#    Unfortunately the API si not Exposed. It would be nice to have custom colors for our nodes.. Or at least choose in existing colortype list.
#  - Eval socket_value API??? ex `my_node.inputs[0].eval_value()` would return a single value, or a numpy array (if possible?)
#    So far in this plugin we can only pass information to a socket, or arrange nodes.
#    What would be an extremely useful functionality, woould be to sample a socket value from a socket.evaluate_value()
#    integrated directly in blender. Unfortunately there are no plans to implement such API.
#  - CustomSocketTypes API? 
#    https://projects.blender.org/blender/blender/pulls/136968
#  - Nodes Consistencies: Generally speaking, nodes are not consistent from one editor to another.
#    For example ShaderNodeValue becomes CompositorNodeValue. Ect.. a lot of Native socket types could be ported to 
#    all editors as well. For example, SocketBool can be in the compositor.
#  - NodeSocket position should definitely be exposed for custom noodle drawing. or socket overdrawings.

# ---------------------------------------------------------------------------------------------

# TODO To Improve:
# - CustomSocket Evaluation system:
#   - timer that check is_dirty flag of all evaluator nodes and update the output when dirty.
#   - is dirty should only refresh concerned nodes outputs. right now an update signal is sent to all output evaluators.
#   - curve 2d input and interpolation input need a way to check if the data is modified.
#   - check for muted status as well? doesn't send a native update signal it seems.
#
# ---------------------------------------------------------------------------------------------

# TODO Ideas:
#
# Generic Functionalities Ideas:
#  - Maybe copy some nodewrangler functionality such as quick mix so user stick to our extrusion style workflow?
#  - Could have an operator for quickly editing a frame description?  Either full custom python editor, or popup a new small window.
#  - Could implement background reference image. there's even a special drawing method for that in the API.
#  - could implement a tab switch in the header for quickly switching between different the big 3 editors?
#  - favorite system improvements:
#     - could take a snapshot of the view location and zoom level.
#     - could have a global list of favorites, and directly change nodetree or editor to reach it from one click!!!!! cross editor/ng favorites that way from Npanel..
#    
# Nodes Ideas:
# - Could design portal node. There are ways to hide sockets, even from user CTRL+H, this node could simply pass hidden sockets around? 
#   Do some tests. Note: would only be nice if we draw a heavy 'portal line' effect from node A to node B. Bonus: animation of the direction.
# - Material Info node? gather informations about the material? if so, what?
# - Transform Is rendered view into a View3D info node, where user can get info about a or active 3Dview informations. Optional index to select which 3Dview he's talking about.
# - Color Palette Node? easily swap between color palettes?
# - Armature/Bone nodes? Will need to learn about rigging to do that tho..
# - File IO: For geometry node, could create a mesh on the fly from a file and set up as field attributes.
# - View3D Info node: Like camera info, but for the 3d view (location/rotation/fov/clip/)
#   Problem: what if there are many? Perhaps should use context.
# - MetaBall Info node?
# - Evaluate sequencer images? Possible to feed the sequencer render to the nodes? Hmm
# - SoundData Info Node: Sample the sound? Generate a sound geometry curve? Evaluate Sound at time? If we work based on sound, perhaps it's for the best isn't it?
# - See if it's possible to imitate a multi-socket like the geometry join node, in customNode, and in customNodegroup. multi math ect would be nice.
# - IF CustomSocketTypes works with NativeSockets:
#     - we could port the interpolation nodes from AnimationNodes?
#       problem is: how do apply the interpolation, to what kind of data, and how?
#         we could use Float/Vector Curve.
#         for geometry node we can even make a curve. 
#         problem is, what about map range?? see how it's internally calculated.
#     - We could have some sort of gamelogic nodes?
#     - mess with multi sockets like the join node. Check if we can use a native socket with this option?? 
#       how could we possibly do that?
#       then we could do multi-math / multi Bool logic. Min/Max All Any, all eq, in between ect..
#     - We could re-implement 
#     - We could have a Shader PBR material
#     - Could have a sprite sheet socket type. random sprite selection.
# - See inspirations from other softs: AnimationNodes/Svershock/Houdini/Ue5/MayaFrost/ect.. see what can be extending GeoNode/Shader/Compositor.
# - MaterialMaker/ SubstanceDesigner import/livelink would be nice. 

# ---------------------------------------------------------------------------------------------

# TODO Bugs:
# To Fix:
#  - copy/pasting a node with ctrlc/v is not working, even crashing. Unsure it's us tho. Maybe it's blender bug.
# Known:
#  - You might stumble into this crash when hot-reloading (enable/disable) the plugin on blender 4.2/4.2
#    https://projects.blender.org/blender/blender/issues/134669 Has been fixed in 4.4. 
#    Only impacts developers hotreloading.
#  - BugFix when adding a lot of nodes while animation is playing. Quite random, can't reproduce. must be related to depsgraph implementation?
#    seems that all_3d_viewports trigger this but it might be a coincidence..
#    ConsolePrints:
#        RecursionError: maximum recursion depth exceeded
#        Error in bpy.app.handlers.depsgraph_update_post[1]:
#        Traceback (most recent call last):
#          File "D:\Work\NodeBooster\nodebooster\handlers.py", line 106, in nodebooster_handler_depspost
#          File "D:\Work\NodeBooster\nodebooster\handlers.py", line 32, in upd_all_custom_nodes
#          File "D:\Work\NodeBooster\nodebooster\utils\node_utils.py", line 72, in get_all_nodes
#        RecursionError: maximum recursion depth exceeded while calling a Python object
#    It seems to trigger a depsgraph chain reaction with other addons.
#        Error in bpy.app.handlers.depsgraph_update_post[0]:
#        Traceback (most recent call last):
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\handlers\handlers.py", line 118, in scatter5_depsgraph
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\handlers\handlers.py", line 540, in shading_type_callback
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\utils\extra_utils.py", line 156, in is_rendered_view
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\utils\extra_utils.py", line 150, in all_3d_viewports_shading_type
#        RecursionError: maximum recursion depth exceeded
#        Error in bpy.app.handlers.depsgraph_update_post[1]:
#        Traceback (most recent call last):
#          File "D:\Work\NodeBooster\nodebooster\handlers.py", line 106, in nodebooster_handler_depspost
#          File "D:\Work\NodeBooster\nodebooster\handlers.py", line 32, in upd_all_custom_nodes
#          File "D:\Work\NodeBooster\nodebooster\utils\node_utils.py", line 72, in get_all_nodes
#        RecursionError: maximum recursion depth exceeded while calling a Python object
#        Error in bpy.app.handlers.depsgraph_update_post[0]:
#        Traceback (most recent call last):
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\handlers\handlers.py", line 118, in scatter5_depsgraph
#            shading_type_callback()
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\handlers\handlers.py", line 540, in shading_type_callback
#            is_rdr = is_rendered_view()
#                     ^^^^^^^^^^^^^^^^^^
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\utils\extra_utils.py", line 156, in is_rendered_view
#            return 'RENDERED' in all_3d_viewports_shading_type()
#                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\utils\extra_utils.py", line 150, in all_3d_viewports_shading_type
#            for space in all_3d_viewports():
#          File "D:\Work\Geo-Scatter\vLatest\geo_scatter\gpl_script\utils\extra_utils.py", line 140, in all_3d_viewports
#            for window in bpy.context.window_manager.windows:
#                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

# ---------------------------------------------------------------------------------------------

import bpy

#This is only here for supporting blender 4.1
bl_info = {
    "name": "Node Booster (Experimental 4.1+)",
    "author": "BD3D DIGITAL DESIGN (Dorian B.)",
    "version": (0, 0, 0),
    "blender": (4, 1, 0),
    "location": "Node Editor",
    "description": "Please install this addon as a blender extension instead of a legacy addon!",
    "warning": "",
    "doc_url": "https://blenderartists.org/t/node-booster-extending-blender-node-editors",
    "category": "Node",
}

def get_addon_prefs():
    """get preferences path from base_package, __package__ path change from submodules"""
    return bpy.context.preferences.addons[__package__].preferences

def isdebug():
    return get_addon_prefs().debug

def dprint(thing):
    if isdebug():
        print(thing)

def cleanse_modules():
    """remove all plugin modules from sys.modules for a clean uninstall (dev hotreload solution)"""
    # See https://devtalk.blender.org/t/plugin-hot-reload-by-cleaning-sys-modules/20040 fore more details.

    import sys

    all_modules = sys.modules
    all_modules = dict(sorted(all_modules.items(),key= lambda x:x[0])) #sort them

    for k,v in all_modules.items():
        if k.startswith(__package__):
            del sys.modules[k]

    return None


def get_addon_classes(revert=False):
    """gather all classes of this plugin that have to be reg/unreg"""

    from .properties import classes as sett_classes
    from .operators import classes as ope_classes
    from .customnodes import classes as nodes_classes
    from .ui import classes as ui_classes

    classes = sett_classes + ope_classes + nodes_classes + ui_classes

    if (revert):
        return reversed(classes)

    return classes


def register():
    """main addon register"""

    from .resources import load_icons
    load_icons() 

    #register every single addon classes here
    for cls in get_addon_classes():
        bpy.utils.register_class(cls)

    from .properties import load_properties
    load_properties()

    from .customnodes.deviceinput import register_listener
    register_listener()

    from .handlers import load_handlers    
    load_handlers()

    from .ui import load_ui
    load_ui()

    from .operators import load_operators_keymaps
    load_operators_keymaps()

    return None


def unregister():
    """main addon un-register"""

    from .operators import unload_operators_keymaps
    unload_operators_keymaps()

    from .ui import unload_ui
    unload_ui()

    from .handlers import unload_handlers  
    unload_handlers()

    from .gpudraw import unregister_gpu_drawcalls
    unregister_gpu_drawcalls()

    from .properties import unload_properties
    unload_properties()

    #unregister every single addon classes here
    for cls in get_addon_classes(revert=True):
        bpy.utils.unregister_class(cls)
        
    from .customnodes.deviceinput import unregister_listener
    unregister_listener()
    
    from .resources import unload_icons
    unload_icons() 

    cleanse_modules()

    return None
