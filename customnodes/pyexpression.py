# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from ..__init__ import get_addon_prefs
from ..resources import cust_icon
from ..nex.pytonode import py_to_Sockdata
from ..utils.str_utils import word_wrap
from ..utils.node_utils import (
    crosseditor_socktype_adjust,
    create_new_nodegroup,
    set_ng_socket_defvalue,
    set_ng_socket_type,
    set_ng_socket_label,
    get_node_objusers,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterPyExpression"
    bl_label = "Python Expression"
    bl_description = """Evaluate a python expression as a single value output.
    • The evaluated values can be of type 'float', 'int', 'Vector', 'Color', 'Quaternion', 'Matrix', 'String', 'Object', 'Collection', 'Material' & 'list/tuple/set' up to len 16.
    • For more advanced python expression, try out the 'Nex Script' node!"""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST','AUTORIZATION_REQUIRED',}
    tree_type = "*ChildrenDefined*"
    # bl_icon = 'SCRIPT'

    error_message : bpy.props.StringProperty(
        description="user interface error message",
        )
    debug_evaluation_counter : bpy.props.IntProperty(
        name="Execution Counter",
        default=0,
        )
    user_pyexpression : bpy.props.StringProperty(
        update=lambda self, context: self.evaluate_python_expression(assign_socketype=True),
        description="type the expression you wish to evaluate right here",
        )
    execute_at_depsgraph : bpy.props.BoolProperty(
        name="Automatically Refresh",
        description="Synchronize the python values with the outputs values on each depsgraph frame and interaction. By toggling this option, your script will be executed constantly.",
        default=True,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context,):        
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={
                    "Waiting for Input" : "NodeSocketFloat",
                    "Error" : "NodeSocketBool",
                    },
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

        self.width = 250

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

    def evaluate_python_expression(self, assign_socketype=False,):
        """evaluate the user string and assign value to output node"""

        ng = self.node_tree
        self.debug_evaluation_counter += 1 # potential issue with int limit here? idk how blender handle this

        #we reset the Error status back to false
        set_ng_socket_label(ng,1, label="NoErrors",)
        set_ng_socket_defvalue(ng,1, value=False,)
        self.error_message = ''

        #check if string is empty first, perhaps user didn't input anything yet 
        if (self.user_pyexpression==""):
            set_ng_socket_label(ng,0, label="Waiting for Input" ,)
            set_ng_socket_label(ng,1, label="EmptyFieldError",)
            set_ng_socket_defvalue(ng,1, value=True,)
            return None

        to_evaluate = self.user_pyexpression

        #define user namespace
        namespace = {}
        namespace["bpy"] = bpy
        namespace["D"] = bpy.data
        namespace["C"] = bpy.context
        namespace["context"] = bpy.context
        namespace["scene"] = bpy.context.scene
        namespace.update(vars(__import__('random')))
        namespace.update(vars(__import__('mathutils')))
        namespace.update(vars(__import__('math')))

        #support for macros
        if ('#frame' in to_evaluate):
            to_evaluate = to_evaluate.replace('#frame','scene.frame_current')

        #'self' as object using this node? only if valid and not ambiguous
        node_obj_users = get_node_objusers(self)
        if (len(node_obj_users)==1):
            namespace["self"] = list(node_obj_users)[0]

        #evaluated the user expression
        try:
            #NOTE, maybe the execution needs to check for some sort of blender checks before allowing execution?
            # a little like the driver python expression, there's a global setting for that. Unsure if it's needed.
            evaluated_pyvalue = eval(to_evaluate, {}, namespace,)

        except Exception as e:
            print(f"{self.bl_idname} Evaluation Exception '{type(e).__name__}':\n{e}")
            msg = str(e)
            if ("name 'self' is not defined" in msg):
                msg = "'self' not Available in this Context."
            #display error to user
            self.error_message = msg
            set_ng_socket_label(ng,0, label=type(e).__name__,)
            set_ng_socket_label(ng,1, label="ExecutionError",)
            set_ng_socket_defvalue(ng,1, value=True,)
            return None

        #python to actual values we can use
        try:
            set_value, set_label, socktype = py_to_Sockdata(evaluated_pyvalue)
        except Exception as e:
            print(f"{self.bl_idname} Parsing Exception '{type(e).__name__}':\n{e}")
            #display error to user
            self.error_message = str(e)
            set_ng_socket_label(ng,0, label=type(evaluated_pyvalue).__name__.title(),)
            set_ng_socket_label(ng,1, label="SocketTypeError",)
            set_ng_socket_defvalue(ng,1, value=True,)
            return None

        #cross editor compatibility
        if crosseditor_socktype_adjust(socktype,ng.type).startswith('Unavailable'):
            #display error to user
            self.error_message = f"{socktype.replace('NodeSocket','')} sockets are not available in {ng.type.title()}."
            set_ng_socket_label(ng,0, label=set_label,)
            set_ng_socket_label(ng,1, label="TypeAvailabilityError",)
            set_ng_socket_defvalue(ng,1, value=True,)
            return None

        #set values
        if (assign_socketype):
            set_ng_socket_type(ng,0, socket_type=socktype,)
        set_ng_socket_label(ng,0, label=set_label ,)
        set_ng_socket_defvalue(ng,0, value=set_value ,)

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Python Expression'
        return self.label

    def draw_buttons(self, context, layout,):
        """node interface drawing"""

        sett_win = context.window_manager.nodebooster
        is_error = bool(self.error_message)
        animated_icon = f"W_TIME_{self.debug_evaluation_counter%8}"

        col = layout.column(align=True)
        row = col.row(align=True)

        field = row.row(align=True)
        field.alert = is_error
        field.prop(self, "user_pyexpression", placeholder="C.object.location", text="",)

        prop = row.row(align=True)
        prop.enabled = sett_win.authorize_automatic_execution
        prop.prop(self, "execute_at_depsgraph", text="", icon_value=cust_icon(animated_icon),)

        if (not sett_win.authorize_automatic_execution):
            col.separator(factor=0.75)
            col.prop(sett_win,"authorize_automatic_execution")
        
        if (is_error):
            col = col.column(align=True)
            col.separator(factor=2)
            word_wrap(layout=col, alert=True, active=True, max_char=self.width/5.65, string=self.error_message,)

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""

        n = self
        sett_win = context.window_manager.nodebooster

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):

            is_error = bool(n.error_message)
            col = panel.column(align=True)
            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "user_pyexpression", placeholder="C.object.location", text="",)

            if (is_error):
                lbl = col.row()
                lbl.alert = is_error
                lbl.label(text=n.error_message)

            panel.prop(sett_win,"authorize_automatic_execution")

            prop = panel.column()
            prop.enabled = sett_win.authorize_automatic_execution
            prop.prop(n,"execute_at_depsgraph")

        header, panel = layout.panel("prefs_panelid", default_closed=True,)
        header.label(text="Namespace",)
        if (panel):

            panel.separator(factor=0.3)

            col = panel.column(align=True)
            for info in (
                "import bpy",
                "from random import *",
                "from mathutils import *",
                "from math import *",
                "context = bpy.context",
                "scene = context.scene",
                "#frame = scene.frame_current",
                "D = bpy.data ; C = bpy.context",
                "self = NodeUserObject",
                ):
                row = col.row(align=True).box()
                row.scale_y = 0.65
                row.label(text=info)

            panel.separator(factor=0.6)

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
            
            col = panel.column(align=True)
            col.label(text="Execution Count:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_evaluation_counter", text="",)

        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """search for all node instances of this type and refresh them. Will be called automatically if .auto_upd_flags's are defined"""

        if (using_nodes is None):
              nodes = get_booster_nodes(by_idnames={cls.bl_idname},)
        else: nodes = [n for n in using_nodes if (n.bl_idname==cls.bl_idname)]

        for n in nodes:
            if (signal_from_handlers and not n.execute_at_depsgraph):
                continue
            if (n.mute):
                continue
            n.evaluate_python_expression(assign_socketype=False)
            continue

        return None

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_PyExpression(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_PyExpression(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_PyExpression(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname
