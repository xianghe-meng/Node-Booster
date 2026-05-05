# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy

import re, ast

from ..utils.str_utils import (
    word_wrap,
    match_exact_tokens,
    replace_exact_tokens,
    is_float_compatible,
)
from ..utils.node_utils import (
    create_new_nodegroup,
    create_ng_socket,
    remove_ng_socket,
    link_sockets,
    create_ng_constant_node,
    set_ng_socket_defvalue,
)
from ..nex.nodesetter import (
    get_nodesetter_functions,
    containsVecs,
    sepaxyz,
    combixyz,
)
from .mathexpression import (
    DIGITS,
    ALPHABET,
    IRRATIONALS,
    MACROS,
    SUPERSCRIPTS,
    MATHEXFUNCDOC,
    MATHNOTATIONDOC,
    USER_FNAMES,
    VECTOR_COMPONENT_FNS,
    replace_superscript_exponents,
    AstTranformer as MathAstTranformer,
    Base as MathExpressionBase,
)


VECTOR_LITERAL_FNS = {'vec'}
VECTORNOTATIONDOC = dict(MATHNOTATIONDOC)
VECTORNOTATIONDOC.update({
    '[x, y, z]': {
        'name': "Combine Vector.",
        'desc': "Combine three scalar expressions into a vector result.",
    },
    'name:vec': {
        'name': "Pinned Vector Input.",
        'desc': "Inside Pinned Variables, declare a persistent vector socket using syntax such as 'velocity:vec'.",
    },
})


def is_vector_like(value) -> bool:
    return containsVecs(value)


def vector_ast_function_caller(visited, node_tree=None, vareq: dict = None, consteq: dict = None, warning_messages: list | None = None):
    """Recursively evaluates the transformed AST tree and calls its functions with their arguments."""

    user_functions_partials = get_nodesetter_functions(tag='mathex', partialdefaults=(node_tree, None),)
    user_function_namespace = {f.func.__name__: f for f in user_functions_partials}

    base_add = user_function_namespace['add']

    def push_warning(message: str):
        if (warning_messages is None):
            return None
        if (message not in warning_messages):
            warning_messages.append(message)
        return None

    def add(a, b):
        if (is_vector_like(a) != is_vector_like(b)):
            push_warning("Vector + scalar broadcasts the scalar to all components.")
        return base_add(a, b)

    def getx(socket):
        return sepaxyz(node_tree, None, socket)[0]

    def gety(socket):
        return sepaxyz(node_tree, None, socket)[1]

    def getz(socket):
        return sepaxyz(node_tree, None, socket)[2]

    def vec(x, y, z):
        return combixyz(node_tree, None, x, y, z)

    user_function_namespace.update({
        'add': add,
        'getx': getx,
        'gety': gety,
        'getz': getz,
        'vec': vec,
    })

    def caller(node):

        match node:

            case ast.Call():

                evaluated_args = [caller(arg) for arg in node.args]

                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if (func_name not in user_function_namespace):
                        raise Exception(f"Function '{func_name}' not recognized.")

                    func = user_function_namespace[func_name]
                    return func(*evaluated_args)

                evaluated_func = caller(node.func)
                return evaluated_func(*evaluated_args)

            case ast.Name():
                if (vareq is not None and node.id in vareq):
                    return vareq[node.id]
                elif (consteq is not None and node.id in consteq):
                    return consteq[node.id]
                raise Exception(f"Element '{node.id}' not recognized.")

            case ast.Constant():
                key = str(node.value)
                if (consteq is not None and key in consteq):
                    return consteq[key]
                else:
                    return node.value

            case ast.Tuple():
                raise Exception("Wrong use of '( , )' Synthax")

            case _:
                raise Exception(f"Unknown ast type '{type(node).__name__}'.")

    final_socket = caller(visited)

    if (not is_vector_like(final_socket)):
        raise Exception("Vector Expression must evaluate to a vector. Use [x, y, z] to combine scalars.")

    try:
        last = node_tree.nodes.active
        out_node = node_tree.nodes['Group Output']
        out_node.location = (last.location.x + last.width + 70, last.location.y - 120,)
        link_sockets(final_socket, out_node.inputs[0])

    except Exception as e:
        print(f"{type(e).__name__} FinalLinkError: vector_ast_function_caller():\n  {e}")
        raise Exception("Error on Final Link. See console.")

    return None


class VectorAstTranformer(MathAstTranformer):
    """AST Transformer for converting vector expressions into function-call expressions."""

    def visit_List(self, node):
        self.generic_visit(node)

        if (len(node.elts) != 3):
            raise Exception("Vector literal must contain exactly 3 elements")

        return ast.Call(
            func=ast.Name(id='vec', ctx=ast.Load()),
            args=node.elts,
            keywords=[],
        )


class Base(MathExpressionBase):

    bl_idname = "NodeBoosterVectorExpression"
    bl_label = "Vector Expression"
    bl_description = """Evaluate a vector math equation and create sockets from given variables on the fly.\n
    • The output is a Vector socket and the expression must resolve to a vector value.\n
    • Variables default to Float sockets unless accessed as '.x/.y/.z' or declared as ':vec' in Pinned Variables.\n
    • Supported vector syntax includes scalar components, vector + scalar broadcast warnings, and vector literals '[x, y, z]'.\n
    • The raw expression text is also exposed as a string output in Geometry Nodes."""
    nb_menu_path = ['NodeBooster', 'Expressions', bl_label,]
    tree_type = "GeometryNodeTree"

    warning_message: bpy.props.StringProperty(
        description="User interface warning message"
    )

    def init(self, context,):
        """This fct run when appending the node for the first time."""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={
                    "Result": "NodeSocketVector",
                    self.expression_text_socket_name: "NodeSocketString",
                },
            )

        ng = ng.copy()
        self.node_tree = ng
        self.ensure_expression_text_output()

        self.width = 250

        return None

    def get_variable_socket_type(self, var_name: str) -> str:
        if (var_name in getattr(self, 'elemVec', ())):
            return "NodeSocketVector"
        if (var_name in getattr(self, 'elemManualVec', ())):
            return "NodeSocketVector"
        return "NodeSocketFloat"

    def digest_user_expression(self, expression) -> str:
        """Sanitize the user expression and collect variables/constants for socket creation."""

        authorized_symbols = ALPHABET + DIGITS + '/*-+%.,()[]'
        vector_component_pattern = r'(?<!\d)([A-Za-z][A-Za-z0-9]*)\.(x|y|z)\b'

        self.elemVec = set()

        for match in re.finditer(vector_component_pattern, expression):
            self.elemVec.add(match.group(1))

        expression = expression.replace(' ', '')
        expression = expression.replace('	', '')

        for char in expression:
            if char in SUPERSCRIPTS.keys():
                expression = replace_superscript_exponents(expression,
                    algebric_notation=self.use_algrebric_multiplication,
                )
                break

        mached = match_exact_tokens(expression, IRRATIONALS.keys())
        if any(mached):
            expression = replace_exact_tokens(expression, IRRATIONALS)

        elemTotal = expression
        for char in '/*-+%,()[]':
            elemTotal = elemTotal.replace(char, '|')
        self.elemTotal = set(e for e in elemTotal.split('|') if e != '')

        match self.use_algrebric_multiplication:

            case True:
                for e in self.elemTotal:
                    if (e not in USER_FNAMES):
                        if match_exact_tokens(expression, f'{e}('):
                            expression = replace_exact_tokens(expression, {f'{e}(': f'{e}*('})
                        if match_exact_tokens(expression, f'){e}'):
                            expression = replace_exact_tokens(expression, {f'){e}': f')*{e}'})

            case False:
                expression = re.sub(r"(\d+(?:\.\d+)?)([\(\[])", r"\1*\2", expression)

        self.elemFct = set()
        self.elemConst = set()
        self.elemVar = set()
        self.elemComp = set()

        match self.use_algrebric_multiplication:

            case True:
                for e in self.elemTotal:
                    vector_access = re.fullmatch(vector_component_pattern, e)
                    if (vector_access):
                        self.elemVar.add(vector_access.group(1))
                        self.elemVec.add(vector_access.group(1))
                        continue

                    if (e in getattr(self, 'elemManual', set())):
                        self.elemVar.add(e)
                        continue

                    if (e in USER_FNAMES):
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue

                    if (e.replace('.', '').isdigit()):
                        if (not is_float_compatible(e)):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue

                    if (len(e) == 1 and (e in ALPHABET)):
                        self.elemVar.add(e)
                        continue

                    for c in list(e):
                        if (c not in list(authorized_symbols) + list(IRRATIONALS.keys())):
                            raise Exception(f"Unauthorized Symbol '{c}'")

                    self.elemComp.add(e)

                    esplit = [m for match in re.finditer(r'(\d+\.\d+|\d+)|([a-zA-Z])', e) for m in match.groups() if m]

                    for esub in esplit:
                        if (esub.replace('.', '').isdigit()):
                            self.elemConst.add(esub)
                        elif (esub.isalpha() and len(esub) == 1):
                            self.elemVar.add(esub)
                        else:
                            msg = f"Unknown Element '{esub}' of Composite '{e}'"
                            print(f"Exception: digest_user_expression():\n{msg}")
                            raise Exception(msg)

                    expression = replace_exact_tokens(expression, {e: '*'.join(esplit)})
                    continue

            case False:
                for e in self.elemTotal:
                    vector_access = re.fullmatch(vector_component_pattern, e)
                    if (vector_access):
                        self.elemVar.add(vector_access.group(1))
                        self.elemVec.add(vector_access.group(1))
                        continue

                    if (e in getattr(self, 'elemManual', set())):
                        self.elemVar.add(e)
                        continue

                    if (e in USER_FNAMES):
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue

                    if (e.replace('.', '').isdigit()):
                        if (not is_float_compatible(e)):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue

                    if all(c in ALPHABET for c in list(e)):
                        if (e in USER_FNAMES or e in VECTOR_LITERAL_FNS):
                            raise Exception(f"Variable '{e}' is Taken")
                        self.elemVar.add(e)
                        continue

                    for c in list(e):
                        if (c not in list(authorized_symbols) + list(IRRATIONALS.keys())):
                            raise Exception(f"Unauthorized Symbol '{c}'")

                    raise Exception(f"Unauthorized Variable '{e}'")

        self.elemVar = sorted(self.elemVar)
        self.elemVec = set(v for v in self.elemVec if v in self.elemVar)

        for char in expression:
            if (char not in authorized_symbols):
                raise Exception(f"Unauthorized Symbol '{char}'")

        return expression

    def apply_user_expression(self) -> None:
        """Transform the vector expression into sockets and nodes arrangements."""

        if (self.use_macros):
            new = self.apply_macros(self.user_mathexp)
            if (new is not None):
                self.user_mathexp = new
                return None

        ng = self.node_tree
        assert ng is not None, "apply_user_expression(): 'self.node_tree' must'nt be None"
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]

        expression_socket = self.ensure_expression_text_output()
        if (expression_socket is not None):
            set_ng_socket_defvalue(ng, socket=expression_socket, in_out='OUTPUT', value=self.user_mathexp)

        self.error_message = ""
        self.warning_message = ""
        self.debug_sanatized = ""
        self.debug_fctexp = ""

        self.store_equation(self.user_mathexp)

        try:
            self.elemManual = self.digest_manual_variables()
        except Exception as e:
            self.error_message = str(e)
            self.debug_sanatized = 'Failed'
            return None

        try:
            r = self.digest_user_expression(self.user_mathexp)
        except Exception as e:
            self.error_message = str(e)
            self.debug_sanatized = 'Failed'
            return None

        digested_expression = self.debug_sanatized = r
        elemVar = sorted(set(self.elemVar) | self.elemManual)
        elemConst = self.elemConst
        self.elemVar = elemVar

        for node in list(ng.nodes).copy():
            if (node.name not in {"Group Input", "Group Output", "EquationStorage",}):
                ng.nodes.remove(node)

        if (elemVar):
            current_vars = [s.name for s in in_nod.outputs]
            for var in elemVar:
                if (var not in current_vars):
                    create_ng_socket(ng,
                        in_out='INPUT',
                        socket_type=self.get_variable_socket_type(var),
                        socket_name=var,
                    )

        idx_to_del = []
        for idx, socket in enumerate(in_nod.outputs):
            if ((socket.type != 'CUSTOM') and (socket.name not in elemVar)):
                idx_to_del.append(idx)
        for idx in reversed(idx_to_del):
            remove_ng_socket(ng, idx, in_out='INPUT')

        for socket in list(in_nod.outputs):
            if (socket.type == 'CUSTOM'):
                continue
            expected = self.get_variable_socket_type(socket.name)
            if (socket.bl_idname != expected):
                idx = next(i for i, s in enumerate(in_nod.outputs) if (s == socket))
                remove_ng_socket(ng, idx, in_out='INPUT')
                create_ng_socket(ng,
                    in_out='INPUT',
                    socket_type=expected,
                    socket_name=socket.name,
                )

        vareq, consteq = dict(), dict()

        if (elemVar):
            for var_sock in in_nod.outputs:
                if (var_sock.name in elemVar):
                    vareq[var_sock.name] = var_sock
                    continue

        if (elemConst):
            xloc, yloc = in_nod.location.x, in_nod.location.y - 330
            for const in elemConst:
                con_sck = create_ng_constant_node(ng, 'ShaderNodeValue', float(const), f"C|{const}", location=(xloc, yloc),)
                yloc -= 90
                consteq[const] = con_sck
                continue

        self.update()

        if (digested_expression == ""):
            return None

        if not (elemVar or elemConst):
            return None

        try:
            transformer = VectorAstTranformer()
            astfctexp = transformer.get_function_expression(digested_expression)
        except Exception as e:
            self.error_message = str(e)
            self.debug_fctexp = 'Failed'
            return None

        fctexp = str(ast.unparse(astfctexp))
        self.debug_fctexp = fctexp

        ng.nodes.active = in_nod

        warnings = []
        try:
            vector_ast_function_caller(astfctexp, node_tree=ng, vareq=vareq, consteq=consteq, warning_messages=warnings,)
        except Exception as e:
            self.warning_message = "\n".join(warnings)
            self.error_message = str(e)
            return None

        self.warning_message = "\n".join(warnings)
        self.debug_nodes_quantity = len(ng.nodes)

        return None

    def draw_label(self,):
        if (self.label == ''):
            return 'Vector Expression'
        return self.label

    def draw_buttons(self, context, layout,):
        is_error = bool(self.error_message)
        has_warning = bool(self.warning_message)

        col = layout.column(align=True)
        row = col.row(align=True)

        field = row.row(align=True)
        field.alert = is_error
        field.prop(self, "user_mathexp", placeholder="[x, y, z] + velocity", text="",)

        opt = row.row(align=True)
        opt.scale_x = 0.35
        opt.prop(self, "use_algrebric_multiplication", text="ab", toggle=True,)

        opt = row.row(align=True)
        opt.scale_x = 0.3
        opt.prop(self, "use_macros", text="蟺", toggle=True,)

        if (is_error):
            msgcol = col.column(align=True)
            msgcol.separator(factor=1)
            word_wrap(layout=msgcol, alert=True, active=True, max_char=self.width / 5.75, string=self.error_message,)

        if (has_warning):
            warncol = col.column(align=True)
            warncol.separator(factor=0.5)
            word_wrap(layout=warncol, alert=False, active=True, max_char=self.width / 5.95, string=self.warning_message,)

        row = col.row(align=True)
        row.prop(self, "user_variables_float", placeholder="speed, scale, bias", text="",)

        row = col.row(align=True)
        row.prop(self, "user_variables_vector", placeholder="velocity, normal, tangent", text="",)

        layout.separator(factor=0.75)

        return None

    def draw_panel(self, layout, context):
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):

            is_error = bool(n.error_message)
            has_warning = bool(n.warning_message)
            col = panel.column(align=True)
            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "user_mathexp", placeholder="[x, y, z] + velocity", text="",)

            if (is_error):
                lbl = col.row()
                lbl.alert = is_error
                lbl.label(text=n.error_message)

            if (has_warning):
                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=n.warning_message, alignment='LEFT',
                )

            panel.prop(n, "user_variables_float",)
            panel.prop(n, "user_variables_vector",)
            panel.prop(n, "use_algrebric_multiplication",)
            panel.prop(n, "use_macros",)

        header, panel = layout.panel("inputs_panelid", default_closed=True,)
        header.label(text="Inputs",)
        if (panel):

            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = True

            if n.inputs:
                for s in n.inputs:
                    row = col.row()
                    row.active = not any(s.links)
                    row.prop(s, 'default_value', text=s.name,)
            else:
                col.label(text="No Input Created")

        header, panel = layout.panel("doc_panelid", default_closed=True,)
        header.label(text="Documentation",)
        if (panel):
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description,
            )
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"

        header, panel = layout.panel("doc_glossid", default_closed=True,)
        header.label(text="Glossary",)
        if (panel):

            col = panel.column()

            for symbol, v in VECTORNOTATIONDOC.items():

                desc = v['name'] + '\n' + v['desc'] if v['desc'] else v['name']
                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=symbol,)

                col.separator(factor=0.5)

                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=desc, alignment='LEFT',
                )
                col.separator()

            for fname, fdoc in MATHEXFUNCDOC.items():

                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=fdoc['repr'],)

                col.separator(factor=0.5)

                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=fdoc['doc'], alignment='LEFT',
                )
                col.separator()

        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False

            col = panel.column(align=True)
            col.label(text="Sanatized Expression:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_sanatized", text="",)

            col = panel.column(align=True)
            col.label(text="Function Expression:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_fctexp", text="",)

            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")

            col = panel.column(align=True)
            col.label(text="NodesCreated:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_nodes_quantity", text="",)

        col = layout.column(align=True)
        op = col.operator("extranode.bake_customnode", text="Convert to Group",)
        op.nodegroup_name = n.node_tree.name
        op.node_name = n.name

        return None


class NODEBOOSTER_NG_GN_VectorExpression(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname
