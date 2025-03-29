# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.), Ted Milker
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

from ..__init__ import get_addon_prefs
from ..utils.str_utils import word_wrap
from ..utils.node_utils import create_new_nodegroup, set_socket_defvalue


class NODEBOOSTER_NG_lightinfo(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodegroup: Gather informations about any lights.
    • Expect updates on each depsgraph post and frame_pre update signals"""

    bl_idname = "GeometryNodeNodeBoosterAreaLightInfo"
    bl_label = "Light Info"
    auto_update = {'FRAME_PRE','DEPS_POST',}

    def update_signal(self,context):
        self.update()
        return None 

    light_type : bpy.props.EnumProperty(
        name="Light Type",
        default='ANY',
        items=[
            ('ANY',   "Any Lights"    ,"", 'LIGHT',       0,),
            ('POINT', "Point Types Only"  ,"", 'LIGHT_POINT', 1,),
            ('SUN',   "Sun Types Only"    ,"", 'LIGHT_SUN',   2,),
            ('SPOT',  "Spot Types Only"   ,"", 'LIGHT_SPOT',  3,),
            ('AREA',  "Area Types Only"   ,"", 'LIGHT_AREA',  4,),
            ],
        update=update_signal,
        )

    def light_obj_poll(self, obj):
        if (self.light_type=='ANY'):
            return obj.type == 'LIGHT'
        return obj.type == 'LIGHT' and obj.data.type == self.light_type

    light_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=light_obj_poll,
        update=update_signal,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                out_sockets={
                    "Object" : "NodeSocketObject", #0:ANY
                    "Type" : "NodeSocketString", #1:ANY
                    "Color" : "NodeSocketColor", #2:ANY
                    "Power" : "NodeSocketFloat", #3:ANY
                    "Shape" : "NodeSocketString", #4:AREA only
                    "Size X" : "NodeSocketFloat", #5:AREA only
                    "Size Y" : "NodeSocketFloat", #6:AREA only
                    "Spread" : "NodeSocketFloat", #7:AREA only
                    "Soft Falloff" : "NodeSocketBool", #8:SPOT|POINT only
                    "Radius" : "NodeSocketFloat", #9:SPOT|POINT only
                    "Angle" : "NodeSocketFloat", #10:SUN only
                    "Size" : "NodeSocketFloat",#11:SPOT only
                    "Blend" : "NodeSocketFloat",#12:SPOT only
                    "Show Cone" : "NodeSocketBool",#13:SPOT only
                },
            )

        ng = ng.copy() #always using a copy of the original ng

        self.node_tree = ng
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when dupplicating the node"""

        self.node_tree = node.node_tree.copy()

        return None

    def update(self):
        """generic update function"""

        lo = self.light_obj

        if ((lo is None) or (lo.type!='LIGHT') or (lo.data is None)):
            set_socket_defvalue(self.node_tree, 0, value=None) #Object
            set_socket_defvalue(self.node_tree, 1, value="") #Type
            set_socket_defvalue(self.node_tree, 2, value=[0.0, 0.0, 0.0, 0.0]) #Color
            set_socket_defvalue(self.node_tree, 3, value=0.0) #Power
            self.outputs[4].enabled = False  #Shape
            self.outputs[5].enabled = False #Size X
            self.outputs[6].enabled = False #Size Y
            self.outputs[7].enabled = False #Spread
            self.outputs[8].enabled = False #Soft Falloff
            self.outputs[9].enabled = False #Radius
            self.outputs[10].enabled = False #Angle
            self.outputs[11].enabled = False #Size
            self.outputs[12].enabled = False #Blend
            self.outputs[13].enabled = False #Show Cone
            return None

        ld = lo.data

        match ld.type:
            case 'POINT':
                set_socket_defvalue(self.node_tree, 0, value=lo) #Object
                set_socket_defvalue(self.node_tree, 1, value=ld.type) #Type
                set_socket_defvalue(self.node_tree, 2, value=[ld.color[0], ld.color[1], ld.color[2], 1.0]) #Color
                set_socket_defvalue(self.node_tree, 3, value=ld.energy) #Power
                self.outputs[4].enabled = False #Shape
                self.outputs[5].enabled = False #Size X
                self.outputs[6].enabled = False #Size Y
                self.outputs[7].enabled = False #Spread
                set_socket_defvalue(self.node_tree, 8, value=ld.use_soft_falloff) #Soft Falloff
                set_socket_defvalue(self.node_tree, 9, value=ld.shadow_soft_size) #Radius
                self.outputs[10].enabled = False #Angle
                self.outputs[11].enabled = False #Size
                self.outputs[12].enabled = False #Blend
                self.outputs[13].enabled = False #Show Cone
            case 'SUN':
                set_socket_defvalue(self.node_tree, 0, value=lo) #Object
                set_socket_defvalue(self.node_tree, 1, value=ld.type) #Type
                set_socket_defvalue(self.node_tree, 2, value=[ld.color[0], ld.color[1], ld.color[2], 1.0]) #Color
                set_socket_defvalue(self.node_tree, 3, value=ld.energy) #Power
                self.outputs[4].enabled = False #Shape
                self.outputs[5].enabled = False #Size X
                self.outputs[6].enabled = False #Size Y
                self.outputs[7].enabled = False #Spread
                self.outputs[8].enabled = False #Soft Falloff
                self.outputs[9].enabled = False #Radius
                set_socket_defvalue(self.node_tree, 10, value=ld.angle) #Angle
                self.outputs[11].enabled = False #Size
                self.outputs[12].enabled = False #Blend
                self.outputs[13].enabled = False #Show Cone
            case 'SPOT':
                set_socket_defvalue(self.node_tree, 0, value=lo) #Object
                set_socket_defvalue(self.node_tree, 1, value=ld.type) #Type
                set_socket_defvalue(self.node_tree, 2, value=[ld.color[0], ld.color[1], ld.color[2], 1.0]) #Color
                set_socket_defvalue(self.node_tree, 3, value=ld.energy) #Power
                self.outputs[4].enabled = False #Shape
                self.outputs[5].enabled = False #Size X
                self.outputs[6].enabled = False #Size Y
                self.outputs[7].enabled = False #Spread
                set_socket_defvalue(self.node_tree, 8, value=ld.use_soft_falloff) #Soft Falloff
                set_socket_defvalue(self.node_tree, 9, value=ld.shadow_soft_size) #Radius
                self.outputs[10].enabled = False #Angle
                set_socket_defvalue(self.node_tree, 11, value=ld.spot_size) #Size
                set_socket_defvalue(self.node_tree, 12, value=ld.spot_blend) #Blend
                set_socket_defvalue(self.node_tree, 13, value=ld.show_cone) #Show Cone
            case 'AREA':
                set_socket_defvalue(self.node_tree, 0, value=lo) #Object
                set_socket_defvalue(self.node_tree, 1, value=ld.type) #Type
                set_socket_defvalue(self.node_tree, 2, value=[ld.color[0], ld.color[1], ld.color[2], 1.0]) #Color
                set_socket_defvalue(self.node_tree, 3, value=ld.energy) #Power
                set_socket_defvalue(self.node_tree, 4, value=ld.shape) #Shape
                set_socket_defvalue(self.node_tree, 5, value=ld.size) #Size X
                set_socket_defvalue(self.node_tree, 6, value=ld.size_y) #Size Y
                set_socket_defvalue(self.node_tree, 7, value=ld.spread) #Spread
                self.outputs[8].enabled = False #Soft Falloff
                self.outputs[9].enabled = False #Radius
                self.outputs[10].enabled = False #Angle
                self.outputs[11].enabled = False #Size
                self.outputs[12].enabled = False #Blend
                self.outputs[13].enabled = False #Show Cone
            case _:
                raise Exception(f'Was not expecting a light of type "{ld.type}"')
        return None

    def draw_label(self,):
        """node label"""

        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""

        row = layout.row(align=True)
        
        sub = row.row(align=True)
        ptr = sub.row(align=True)
        if (self.light_type!='ANY' and self.light_obj):
            ptr.alert = self.light_obj.data.type!=self.light_type
        ptr.prop(self, "light_obj", text="", 
            icon='LIGHT' if (self.light_obj is None) else f"LIGHT_{self.light_obj.data.type}" if self.light_obj.data else 'ERROR'
            )
        sub.prop(self, "light_type", text="", icon_only=True,)

        return None

    @classmethod
    def update_all_instances(cls, from_autoexec=False,):
        """search for all nodes of this type and update them"""

        all_instances = [n for ng in bpy.data.node_groups for n in ng.nodes if (n.bl_idname==cls.bl_idname)]
        for n in all_instances:
            n.update()

        return None
