# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import ast

import bpy

from ..utils.node_utils import (
    create_new_nodegroup,
    create_ng_socket,
    remove_ng_socket,
    link_sockets,
    create_ng_constant_node,
    get_ng_socket_by_name,
    set_ng_socket_defvalue,
)
from ..nex.nodesetter import (
    get_nodesetter_functions,
    containsVecs,
    sepaxyz,
    combixyz,
)
from .mathexpression import (
    Base as MathExpressionBase,
)
from .vectorexpression import (
    VectorAstTranformer,
)


def is_vector_like(value) -> bool:
    return containsVecs(value)


def evaluate_expression_ast(visited, node_tree=None, vareq: dict = None, consteq: dict = None, warning_messages: list | None = None):
    """Evaluate the transformed AST tree and return the resulting socket/value."""

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
                return node.value

            case ast.Tuple():
                raise Exception("Wrong use of '( , )' Synthax")

            case _:
                raise Exception(f"Unknown ast type '{type(node).__name__}'.")

    return caller(visited)


class Base(MathExpressionBase):

    bl_idname = "NodeBoosterExpression"
    bl_label = "Expression"
    bl_description = """Evaluate an expression and automatically expose either a Float or Vector result socket.\n
    • The output type is inferred from the final expression result.\n
    • Float and vector pinned variables are supported using separate fields.\n
    • Supports vector functions, vector component access, and vector literals '[x, y, z]'.\n
    • The raw expression text is also exposed as a string output in Geometry Nodes."""
    nb_menu_path = ['NodeBooster', 'Expressions', bl_label,]
    tree_type = "GeometryNodeTree"

    warning_message: bpy.props.StringProperty(
        description="User interface warning message"
    )
    debug_output_socket: bpy.props.StringProperty(
        description="Detected output socket type"
    )

    def init(self, context,):
        """This fct run when appending the node for the first time."""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={
                    "Result": "NodeSocketFloat",
                    self.expression_text_socket_name: "NodeSocketString",
                },
            )

        ng = ng.copy()
        self.node_tree = ng
        self.width = 250

        return None

    def sync_output_sockets(self, socket_type: str):
        """Ensure the node group outputs are in the expected order and types."""

        ng = self.node_tree
        out_nod = ng.nodes["Group Output"]
        desired = [
            ("Result", socket_type),
            (self.expression_text_socket_name, "NodeSocketString"),
        ]

        current = [(socket.name, socket.bl_idname) for socket in out_nod.inputs if (socket.type != 'CUSTOM')]
        if (current == desired):
            return None

        idx_to_del = []
        for idx, socket in enumerate(out_nod.inputs):
            if (socket.type != 'CUSTOM'):
                idx_to_del.append(idx)
        for idx in reversed(idx_to_del):
            remove_ng_socket(ng, idx, in_out='OUTPUT')

        for socket_name, out_type in desired:
            create_ng_socket(ng,
                in_out='OUTPUT',
                socket_type=out_type,
                socket_name=socket_name,
            )

        return None

    def apply_user_expression(self) -> None:
        """Transform the generic expression into sockets and nodes arrangements."""

        if (self.use_macros):
            new = self.apply_macros(self.user_mathexp)
            if (new is not None):
                self.user_mathexp = new
                return None

        ng = self.node_tree
        assert ng is not None, "apply_user_expression(): 'self.node_tree' must'nt be None"
        in_nod = ng.nodes["Group Input"]

        self.sync_output_sockets("NodeSocketFloat")
        out_nod = ng.nodes["Group Output"]

        expression_socket = get_ng_socket_by_name(ng, self.expression_text_socket_name, in_out='OUTPUT')
        if (expression_socket is None):
            self.sync_output_sockets("NodeSocketFloat")
            expression_socket = get_ng_socket_by_name(ng, self.expression_text_socket_name, in_out='OUTPUT')
        if (expression_socket is not None):
            set_ng_socket_defvalue(ng, socket=expression_socket, in_out='OUTPUT', value=self.user_mathexp)

        self.error_message = ""
        self.warning_message = ""
        self.debug_sanatized = ""
        self.debug_fctexp = ""
        self.debug_output_socket = ""

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

        if (elemConst):
            xloc, yloc = in_nod.location.x, in_nod.location.y - 330
            for const in elemConst:
                con_sck = create_ng_constant_node(ng, 'ShaderNodeValue', float(const), f"C|{const}", location=(xloc, yloc),)
                yloc -= 90
                consteq[const] = con_sck

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

        self.debug_fctexp = str(ast.unparse(astfctexp))
        ng.nodes.active = in_nod

        warnings = []
        try:
            final_socket = evaluate_expression_ast(astfctexp, node_tree=ng, vareq=vareq, consteq=consteq, warning_messages=warnings,)
        except Exception as e:
            self.warning_message = "\n".join(warnings)
            self.error_message = str(e)
            return None

        output_socket_type = "NodeSocketVector" if is_vector_like(final_socket) else "NodeSocketFloat"
        self.debug_output_socket = output_socket_type
        self.sync_output_sockets(output_socket_type)
        out_nod = ng.nodes["Group Output"]
        expression_socket = get_ng_socket_by_name(ng, self.expression_text_socket_name, in_out='OUTPUT')
        if (expression_socket is not None):
            set_ng_socket_defvalue(ng, socket=expression_socket, in_out='OUTPUT', value=self.user_mathexp)

        try:
            last = ng.nodes.active
            out_nod.location = (last.location.x + last.width + 70, last.location.y - 120,)
            link_sockets(final_socket, out_nod.inputs[0])
        except Exception as e:
            self.warning_message = "\n".join(warnings)
            self.error_message = f"Error on Final Link. See console."
            print(f"{type(e).__name__} FinalLinkError: Expression.apply_user_expression():\n  {e}")
            return None

        self.warning_message = "\n".join(warnings)
        self.debug_nodes_quantity = len(ng.nodes)
        self.update()

        return None

    def draw_label(self,):
        if (self.label == ''):
            return 'Expression'
        return self.label


class NODEBOOSTER_NG_GN_Expression(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname
