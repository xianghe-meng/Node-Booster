import bpy

from .arrayvector import Base as _ArrayBase
from .mathexpression import MATHEXFUNCDOC, MATHNOTATIONDOC
from ..utils.str_utils import word_wrap


class Base(_ArrayBase):
    bl_idname = "NodeBoosterVecExpression"
    bl_label = "Vector Expression"
    bl_description = """Evaluate three expressions (X, Y, Z) and output the resulting vector."""

    def update_signal(self, context):
        self.user_mathexp = f"[{self.x_expr}, {self.y_expr}, {self.z_expr}]"
        self.apply_user_expression()
        return None

    active_field: bpy.props.IntProperty(default=0, options={'HIDDEN'})

    x_expr: bpy.props.StringProperty(name="X", default="", update=update_signal, options={'TEXTEDIT_UPDATE'})
    y_expr: bpy.props.StringProperty(name="Y", default="", update=update_signal, options={'TEXTEDIT_UPDATE'})
    z_expr: bpy.props.StringProperty(name="Z", default="", update=update_signal, options={'TEXTEDIT_UPDATE'})

    def draw_label(self):
        if self.label == "":
            return "Vector Expression"
        return self.label

    def draw_buttons(self, context, layout):
        is_error = bool(self.error_message)

        col = layout.column(align=True)

        row = col.row(align=True)
        row.alert = is_error
        row.prop(self, "x_expr", text="X")

        row = col.row(align=True)
        row.alert = is_error
        row.prop(self, "y_expr", text="Y")

        row = col.row(align=True)
        row.alert = is_error
        row.prop(self, "z_expr", text="Z")

        opt = col.row(align=True)
        opt.scale_x = 0.35
        opt.prop(self, "use_algrebric_multiplication", text="ab", toggle=True)

        opt = col.row(align=True)
        opt.scale_x = 0.3
        opt.prop(self, "use_macros", text="π", toggle=True)

        if is_error:
            col = col.column(align=True)
            col.separator(factor=1)
            word_wrap(
                layout=col,
                alert=True,
                active=True,
                max_char=self.width / 5.75,
                string=self.error_message,
            )

        layout.separator(factor=0.75)
        return None

    def draw_panel(self, layout, context):
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False)
        header.label(text="Parameters")
        if panel:
            is_error = bool(n.error_message)
            col = panel.column(align=True)

            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "x_expr", text="X")

            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "y_expr", text="Y")

            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "z_expr", text="Z")

            if is_error:
                lbl = col.row()
                lbl.alert = is_error
                lbl.label(text=n.error_message)

            panel.prop(n, "use_algrebric_multiplication")
            panel.prop(n, "use_macros")

        header, panel = layout.panel("inputs_panelid", default_closed=True)
        header.label(text="Inputs")
        if panel:
            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = True

            if n.inputs:
                for s in n.inputs:
                    row = col.row()
                    row.active = not any(s.links)
                    row.prop(s, "default_value", text=s.name)
            else:
                col.label(text="No Input Created")

        header, panel = layout.panel("doc_panelid", default_closed=True)
        header.label(text="Documentation")
        if panel:
            word_wrap(
                layout=panel,
                alert=False,
                active=True,
                max_char="auto",
                char_auto_sidepadding=0.9,
                context=context,
                string=n.bl_description,
            )
            panel.operator(
                "wm.url_open", text="Documentation"
            ).url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"

        header, panel = layout.panel("doc_glossid", default_closed=True)
        header.label(text="Glossary")
        if panel:
            col = panel.column()

            for symbol, v in MATHNOTATIONDOC.items():
                desc = v["name"] + "\n" + v["desc"] if v["desc"] else v["name"]
                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=symbol)

                col.separator(factor=0.5)

                word_wrap(
                    layout=col,
                    alert=False,
                    active=True,
                    max_char="auto",
                    char_auto_sidepadding=0.95,
                    context=context,
                    string=desc,
                    alignment="LEFT",
                )
                col.separator()

            for fname, fdoc in MATHEXFUNCDOC.items():
                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=fdoc["repr"])

                col.separator(factor=0.5)

                word_wrap(
                    layout=col,
                    alert=False,
                    active=True,
                    max_char="auto",
                    char_auto_sidepadding=0.95,
                    context=context,
                    string=fdoc["doc"],
                    alignment="LEFT",
                )
                col.separator()

        header, panel = layout.panel("dev_panelid", default_closed=True)
        header.label(text="Development")
        if panel:
            panel.active = False

            col = panel.column(align=True)
            col.label(text="Sanatized Expression:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_sanatized", text="")

            col = panel.column(align=True)
            col.label(text="Function Expression:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_fctexp", text="")

            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")

            col = panel.column(align=True)
            col.label(text="NodesCreated:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_nodes_quantity", text="")

        col = layout.column(align=True)
        op = col.operator("extranode.bake_customnode", text="Convert to Group")
        op.nodegroup_name = n.node_tree.name
        op.node_name = n.name

        return None


class NODEBOOSTER_NG_GN_VecExpression(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname


class NODEBOOSTER_NG_SH_VecExpression(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname


class NODEBOOSTER_NG_CP_VecExpression(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname

