# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE WARNING TO DO CHANGE bl_idname or class name in here. can break user files.


import bpy


class Base():

    bl_idname = "*ChildrenDefined*"
    bl_label = "*ChildrenDefined*"
    bl_description = "Custom Datatype"
    
    nodebooster_socket_type = "*ChildrenDefined*"

    default_value : bpy.props.FloatProperty(
        default=0.0,
        )
    socket_color : bpy.props.FloatVectorProperty(
        subtype='COLOR',
        default=(0.8, 0.2, 0.2, 1),
        size=4,
        )
    socket_label : bpy.props.StringProperty(
        default="",
        )
    display_label : bpy.props.BoolProperty(
        default=False,
        name="Display Label",
        description="do we display the socket_label or the native socket name attribute?"
        )

    def draw(self, context, layout, node, text):

        if (self.display_label):
              layout.label(text=self.socket_label)
        else: layout.label(text=self.name)

        return None

    def draw_color(self, context, node):

        return self.socket_color


class NODEBOOSTER_SK_Interpolation(Base, bpy.types.NodeSocket):

    # NOTE technically speaking, this type can be used for generic curvesn as it manipualtes a list of points coordinates with handles info.
    # the name has been chosen like that, and it's too late to change it to something like NODEBOOSTER_SK_Curve anyway.
    # that doesn't change the fact that we can use it in other context, just using another label and 
    # we should be good, the user will never know.. it's just a class name..

    bl_idname = "NodeBoosterCustomSocketInterpolation"
    bl_label = "Interpolation"
    bl_description = "Interpolation Data Type"
    
    nodebooster_socket_type = "INTERPOLATION"

    socket_color : bpy.props.FloatVectorProperty(
        subtype='COLOR',
        default=[0.713274, 0.432440, 0.349651, 10000.000000],
        size=4,
        )
    socket_label : bpy.props.StringProperty(
        default="Interpolation",
        )
    
class NODEBOOSTER_ND_CustomSocketUtility(bpy.types.Node):

    bl_idname = "CustomSocketUtility"
    bl_label = "Socket Utility"
    bl_description = "an internal utility node, for creating our customgroups"
    bl_icon = 'NODE'
    auto_update = {'NONE',}

    def init(self, context):
        self.inputs.new('NodeBoosterCustomSocketInterpolation', "Interpolation")
        self.outputs.new('NodeBoosterCustomSocketInterpolation', "Interpolation")
        return None

    def update(self):

        return None

    def draw_buttons(self, context, layout):
        
        col = layout.column(align=True)
        col.label(text="Outputs")
        col.prop(self.outputs[0], "display_label")
        col.prop(self.outputs[0], "socket_label", text="")
        col.prop(self.outputs[0], "socket_color", text="")
        
        col = layout.column(align=True)
        col.label(text="Inputs")
        col.prop(self.outputs[0], "display_label")
        col.prop(self.inputs[0], "socket_label", text="")
        col.prop(self.inputs[0], "socket_color", text="")

        return None

    def draw_label(self):

        return 'SocketUtility'
