# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from collections.abc import Iterable

from ..gpudraw import register_gpu_drawcalls
from ..__init__ import get_addon_prefs, dprint
from ..operators.palette import msgbus_palette_callback
from ..utils.node_utils import get_booster_nodes, cache_all_booster_nodes_parent_trees
from ..customnodes import allcustomnodes
from ..customnodes import NODEBOOSTER_NG_GN_IsRenderedView


# oooooooooo.                                                   
# `888'   `Y8b                                                  
#  888     888 oooo  oooo   .oooo.o  .oooo.o  .ooooo.   .oooo.o 
#  888oooo888' `888  `888  d88(  "8 d88(  "8 d88' `88b d88(  "8 
#  888    `88b  888   888  `"Y88b.  `"Y88b.  888ooo888 `"Y88b.  
#  888    .88P  888   888  o.  )88b o.  )88b 888    .o o.  )88b 
# o888bood8P'   `V88V"V8P' 8""888P' 8""888P' `Y8bod8P' 8""888P' 
                                                            

MSGBUSOWNER_VIEWPORT_SHADING = object()
MSGBUSOWNER_PALETTE =  object()

def msgbus_viewportshading_callback(*args):

    if (get_addon_prefs().debug_depsgraph):
        print("msgbus_viewportshading_callback(): msgbus signal")

    NODEBOOSTER_NG_GN_IsRenderedView.update_all(signal_from_handlers=True)

    return None 

def register_msgbusses():
    
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.View3DShading, "type"),
        owner=MSGBUSOWNER_VIEWPORT_SHADING,
        notify=msgbus_viewportshading_callback,
        args=(None,),
        options={"PERSISTENT"},
        )
    bpy.msgbus.subscribe_rna(
        key=bpy.types.PaletteColor,
        owner=MSGBUSOWNER_PALETTE,
        notify=msgbus_palette_callback,
        args=(None,),
        options={"PERSISTENT"},
        )

    return None

def unregister_msgbusses():

    bpy.msgbus.clear_by_owner(MSGBUSOWNER_VIEWPORT_SHADING)
    bpy.msgbus.clear_by_owner(MSGBUSOWNER_PALETTE)

    return None


def on_plugin_installation():
    """is executed either right after plugin installation (when user click on install checkbox),
    or when blender is booting, it will also load plugin"""
        
    def wait_restrict_state_timer():
        """wait until bpy.context is not bpy_restrict_state._RestrictContext anymore
            BEWARE: this is a function from a bpy.app timer, context is trickier to handle"""
        
        dprint(f"HANDLER: on_plugin_installation(): Still in restrict state?",)

        #don't do anything until context is cleared out
        if (str(bpy.context).startswith("<bpy_restrict_state")): 
            return 0.01
        
        dprint(f"HANDLER: on_plugin_installation(): Loading Plugin: Running few functions..",)
        
        #register gpu drawing functions
        register_gpu_drawcalls()
        
        #start the minimap navigation automatically?
        if (get_addon_prefs().auto_launch_minimap_navigation):
            bpy.context.window_manager.nodebooster.minimap_modal_operator_is_active = True

        #on init we find all booster nodes parent trees, to save perfs at runtime.
        cache_all_booster_nodes_parent_trees()

        return None

    bpy.app.timers.register(wait_restrict_state_timer)

    return None


# ooooo   ooooo                             .o8  oooo                              
# `888'   `888'                            "888  `888                              
#  888     888   .oooo.   ooo. .oo.    .oooo888   888   .ooooo.  oooo d8b  .oooo.o 
#  888ooooo888  `P  )88b  `888P"Y88b  d88' `888   888  d88' `88b `888""8P d88(  "8 
#  888     888   .oP"888   888   888  888   888   888  888ooo888  888     `"Y88b.  
#  888     888  d8(  888   888   888  888   888   888  888    .o  888     o.  )88b 
# o888o   o888o `Y888""8o o888o o888o `Y8bod88P" o888o `Y8bod8P' d888b    8""888P' 
                                                                                 

def windows_changed():
    """check if a new window has been opened"""

    wincount = len(bpy.context.window_manager.windows)
    _f = windows_changed
    if (not hasattr(_f, 'wincount')):
        _f.wincount = wincount

    state = wincount!=_f.wincount
    _f.wincount = wincount
    return state


def upd_all_custom_nodes(classes:list):
    """automatically run the update_all() function of all custom nodes passed"""

    # NOTE function below will simply collect all instances of 'NodeBooster' nodes.
    # NOTE there's a lot of classes, and this functions might loop over a lot of data.
    # for optimization purpose, instead of each cls using the function, we create it once
    # here, then pass the list to the update functions with the 'using_nodes' param.

    if (not classes):
        return None

    matching_blid = [cls.bl_idname for cls in classes]
    nodes = get_booster_nodes(by_idnames=matching_blid,)
    # print("upd_all_custom_nodes().nodes:", matching_blid, nodes, )

    #cls with 'auto_upd_flags' property are eligible for automatic execution.
    auto_update_nodes = [n for n in nodes if (hasattr(n,'update_all')) and (hasattr(n,'auto_upd_flags'))]

    for n in auto_update_nodes:
        #automatic re-evaluation of the Python Expression and Python Nex Nodes, for security reasons, only if the user allows it expressively.
        if ('AUTORIZATION_REQUIRED' in n.auto_upd_flags) and \
           (not bpy.context.window_manager.nodebooster.authorize_automatic_execution):
            continue
        n.update_all(signal_from_handlers=True, using_nodes=nodes)
        continue

    return None


DEPSPOST_UPD_NODES = [cls for cls in allcustomnodes if ('DEPS_POST' in cls.auto_upd_flags)]

@bpy.app.handlers.persistent
def nodebooster_handler_depspost(scene,desp):
    """update on depsgraph change"""

    if (get_addon_prefs().debug_depsgraph):
        print("nodebooster_handler_depspost(): depsgraph signal")

    if (get_addon_prefs().auto_launch_minimap_navigation):
        if (windows_changed()):
            win_sett = bpy.context.window_manager.nodebooster
            # we are forced to restart the modal navigation when a window is opened.
            # a modal op is tied per window, so if we need to support our nav widget
            # for this window, we need to relaunch our multi window modal.
            win_sett.minimap_modal_operator_is_active = False
            win_sett.minimap_modal_operator_is_active = True

    #updates for our custom nodes
    upd_all_custom_nodes(DEPSPOST_UPD_NODES)
    return None

FRAMEPRE_UPD_NODES = [cls for cls in allcustomnodes if ('FRAME_PRE' in cls.auto_upd_flags)]

@bpy.app.handlers.persistent
def nodebooster_handler_framepre(scene,desp):
    """update on frame change"""

    if (get_addon_prefs().debug_depsgraph):
        print("nodebooster_handler_framepre(): frame_pre signal")

    #updates for our custom nodes
    upd_all_custom_nodes(FRAMEPRE_UPD_NODES)
    return None

LOADPOST_UPD_NODES = [cls for cls in allcustomnodes if ('LOAD_POST' in cls.auto_upd_flags)]

@bpy.app.handlers.persistent
def nodebooster_handler_loadpost(scene,desp):
    """Handler function when user is loading a file"""
    
    if (get_addon_prefs().debug_depsgraph):
        print("nodebooster_handler_framepre(): frame_pre signal")

    #need to add message bus on each blender load
    register_msgbusses()

    #register gpu drawing functions
    register_gpu_drawcalls()

    #start the minimap navigation automatically? only if the user enabled it.
    if (get_addon_prefs().auto_launch_minimap_navigation):
        bpy.context.window_manager.nodebooster.minimap_modal_operator_is_active = True
            
    #updates for our custom nodes
    upd_all_custom_nodes(LOADPOST_UPD_NODES)
    return None


# ooooooooo.                        
# `888   `Y88.                      
#  888   .d88'  .ooooo.   .oooooooo 
#  888ooo88P'  d88' `88b 888' `88b  
#  888`88b.    888ooo888 888   888  
#  888  `88b.  888    .o `88bod8P'  
# o888o  o888o `Y8bod8P' `8oooooo.  
#                        d"     YD  
#                        "Y88888P'  
                                  
def all_handlers(name=False):
    """return a list of handler stored in .blend""" 

    for oh in bpy.app.handlers:
        if isinstance(oh, Iterable):
            for h in oh:
                yield h

def load_handlers():
    
    # special timer 'handler' for plugin installation.
    # if we need to do things on plugin init, but there's an annoying restrict state.
    on_plugin_installation()
    
    handler_names = [h.__name__ for h in all_handlers()]

    if ('nodebooster_handler_depspost' not in handler_names):
        bpy.app.handlers.depsgraph_update_post.append(nodebooster_handler_depspost)

    if ('nodebooster_handler_framepre' not in handler_names):
        bpy.app.handlers.frame_change_pre.append(nodebooster_handler_framepre)

    if ('nodebooster_handler_loadpost' not in handler_names):
        bpy.app.handlers.load_post.append(nodebooster_handler_loadpost)
        
    return None 

def unload_handlers():

    for h in all_handlers():

        if(h.__name__=='nodebooster_handler_depspost'):
            bpy.app.handlers.depsgraph_update_post.remove(h)

        if(h.__name__=='nodebooster_handler_framepre'):
            bpy.app.handlers.frame_change_pre.remove(h)

        if(h.__name__=='nodebooster_handler_loadpost'):
            bpy.app.handlers.load_post.remove(h)

    return None
