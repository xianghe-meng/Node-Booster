# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# TODO v2.0 release
#  - Custom operator shortcuts are not saved, they reset on each blender sessions.
#  - Functions should always check if a value or type isn't already set before setting it. 
#    I believe the tool is currently sending a lot of useless update signals by setting the same values 
#    (see compositor refresh, perhaps it's because of node.update()?? need to investigate)
#  - Finalize NexScript for Shader/compositor. Need to overview functions..
#  - Codebase review for extension.. Ask AI to do a big check.

# NOTE Change to C blender code:
#  - Would be great to display error messages for context nodes who use them like the native node. 
#    API is not exposed th
#  - Color of some nodes should'nt be red. sometimes blue for converter (math expression) or script color..
#    Unfortunately the API si not Exposed
#  - Sample socket value API?
#    So far in this plugin we can only pass information to a socket, or arrange nodes.
#    What would be an extremely useful functionality, woould be to sample a socket value from a socket.evaluate_value()
#    integrated directly in blender. Unfortunately there are no plans to implement such API.
#  - CustomSocketTypes API?
#    If we could create custom SocketTypes, we could create nodes that process specific data before sending it 
#    to the native blender SocketTypes. A lot of new CustomNodes could be implemented that way for each editors.
#    It would greatly improve how extensible existing editors are. A lot of nodes from Animation nodes for example
#    could be implemented on for all editors types, and be directly use within these native editors without the need
#    of a separate nodetree interface.
#  - Nodes Consistencies: Generally speaking, nodes are not consistent from one editor to another.
#    For example ShaderNodeValue becomes CompositorNodeValue. Ect.. a lot of Native socket types could be ported to 
#    all editors as well. For example, SocketBool can be in the compositor.

# TODO Ideas:
#
# Generic Functionalities Ideas:
#  - Maybe copy some nodewrangler functionality such as quick mix so user stick to our extrusion style workflow?
#
# Nodes Ideas:
# - Material Info node? gather informations about the material? if so, what?
# - Color Palette Node? easily swap between color palettes?
# - Armature/Bone nodes? Will need to learn about rigging to do that tho..
# - File IO: For geometry node, could create a mesh on the fly from a file and set up as field attributes.
# - View3D Info node: Like camera info, but for the 3d view (location/rotation/fov/clip/)
#   Problem: what if there are many? Perhaps should use context.
# - Animation Nodes/ Svershock inspiration: See wich nodes can be ported.
# - MetaBall Info node?
# - Evaluate sequencer images? Possible to feed the sequencer render to the nodes?
# - Sound Info Node: sound sampling? Sound curve? Evaluate Sound at time? If we work based on sound, perhaps it's for the best isn't it?

# TODO Bugs:
# To Fix:
#  - copy/pasting a node with ctrlc/v is not working, even crashing. Unsure it's us tho. Maybe it's blender bug.
# Known:
#  - You might stumble into this crash when hot-reloading (enable/disable) the plugin on blender 4.2/4.2
#    https://projects.blender.org/blender/blender/issues/134669 Has been fixed in 4.4. 
#    Only impacts developers hotreloading.

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
    "doc_url": "https://blenderartists.org/t/nodebooster-new-nodes-and-functionalities-for-node-wizards-for-free",
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
