# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
import re, ast

from .mathexpression import (
    AstTranformer as _MathAstTransformer,
    ast_function_caller,
    Base as _MathBase,
    replace_superscript_exponents,
    DIGITS,
    ALPHABET,
    IRRATIONALS,
    SUPERSCRIPTS,
    USER_FNAMES,
)
from ..utils.str_utils import (
    match_exact_tokens,
    replace_exact_tokens,
    is_float_compatible,
)
from ..utils.node_utils import (
    create_new_nodegroup,
    create_ng_socket,
    remove_ng_socket,
    create_ng_constant_node,
)

class VecAstTranformer(_MathAstTransformer):
    """AST Transformer supporting list syntax for vectors."""
    def visit_List(self, node):
        self.generic_visit(node)
        if len(node.elts) != 3:
            raise Exception("Vector must have exactly 3 elements")
        return ast.Call(
            func=ast.Name(id='combixyz', ctx=ast.Load()),
            args=node.elts,
            keywords=[],
        )

class Base(_MathBase):
    bl_idname = "NodeBoosterArrayVector"
    bl_label = "Array Vector"
    bl_description = """Evaluate a vector equation and create sockets from given variables on the fly.\nUse [x, y, z] notation to build vectors."""

    def init(self, context):
        name = f".{self.bl_idname}"
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            ng = create_new_nodegroup(
                name,
                tree_type=self.tree_type,
                out_sockets={"Result": "NodeSocketVector"},
            )
        ng = ng.copy()
        self.node_tree = ng
        self.width = 250
        return None

    def digest_user_expression(self, expression) -> str:
        authorized_symbols = ALPHABET + DIGITS + '/*-+%.,()[]'
        expression = expression.replace(' ', '')
        expression = expression.replace('       ', '')

        for char in expression:
            if char in SUPERSCRIPTS.keys():
                expression = replace_superscript_exponents(
                    expression,
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
                    if e not in USER_FNAMES:
                        if match_exact_tokens(expression, f'{e}('):
                            expression = replace_exact_tokens(expression, {f'{e}(' : f'{e}*('})
                        if match_exact_tokens(expression, f'){e}'):
                            expression = replace_exact_tokens(expression, {f'){e}' : f')*{e}'})
            case False:
                expression = re.sub(r"(\d+(?:\.\d+)?)(\()", r"\1*\2", expression)

        self.elemFct = set()
        self.elemConst = set()
        self.elemVar = set()
        self.elemComp = set()

        match self.use_algrebric_multiplication:
            case True:
                for e in self.elemTotal:
                    if e in USER_FNAMES:
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue
                    if e.replace('.', '').isdigit():
                        if not is_float_compatible(e):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue
                    if len(e) == 1 and (e in ALPHABET):
                        self.elemVar.add(e)
                        continue
                    for c in list(e):
                        if c not in list(authorized_symbols) + list(IRRATIONALS.keys()):
                            raise Exception(f"Unauthorized Symbol '{c}'")
                    self.elemComp.add(e)
                    esplit = [m for match in re.finditer(r'(\d+\.\d+|\d+)|([a-zA-Z])', e) for m in match.groups() if m]
                    for esub in esplit:
                        if esub.replace('.', '').isdigit():
                            self.elemConst.add(esub)
                        elif esub.isalpha() and len(esub) == 1:
                            self.elemVar.add(esub)
                        else:
                            msg = f"Unknown Element '{esub}' of Composite '{e}'"
                            print(f"Exception: digest_user_expression():\n{msg}")
                            raise Exception(msg)
                    expression = replace_exact_tokens(expression, {e: '*'.join(esplit)})
                    continue
            case False:
                for e in self.elemTotal:
                    if e in USER_FNAMES:
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue
                    if e.replace('.', '').isdigit():
                        if not is_float_compatible(e):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue
                    if all(c in ALPHABET for c in list(e)):
                        if e in USER_FNAMES:
                            raise Exception(f"Variable '{e}' is Taken")
                        self.elemVar.add(e)
                        continue
                    for c in list(e):
                        if c not in list(authorized_symbols) + list(IRRATIONALS.keys()):
                            raise Exception(f"Unauthorized Symbol '{c}'")
                    raise Exception(f"Unauthorized Variable '{e}'")

        self.elemVar = sorted(self.elemVar)

        for char in expression:
            if char not in authorized_symbols:
                raise Exception(f"Unauthorized Symbol '{char}'")

        return expression

    def apply_user_expression(self) -> None:
        if self.use_macros:
            new = self.apply_macros(self.user_mathexp)
            if new is not None:
                self.user_mathexp = new
                return None

        ng = self.node_tree
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]
        self.error_message = self.debug_sanatized = self.debug_fctexp = ""
        self.store_equation(self.user_mathexp)

        try:
            r = self.digest_user_expression(self.user_mathexp)
        except Exception as e:
            self.error_message = str(e)
            self.debug_sanatized = 'Failed'
            return None

        digested_expression = self.debug_sanatized = r
        elemVar, elemConst = self.elemVar, self.elemConst

        for node in list(ng.nodes).copy():
            if node.name not in {"Group Input", "Group Output", "EquationStorage"}:
                ng.nodes.remove(node)

        if elemVar:
            current_vars = [s.name for s in in_nod.outputs]
            for var in elemVar:
                if var not in current_vars:
                    create_ng_socket(ng, in_out='INPUT', socket_type="NodeSocketFloat", socket_name=var)

        idx_to_del = []
        for idx, socket in enumerate(in_nod.outputs):
            if (socket.type != 'CUSTOM') and (socket.name not in elemVar):
                idx_to_del.append(idx)
        for idx in reversed(idx_to_del):
            remove_ng_socket(ng, idx, in_out='INPUT')

        vareq, consteq = dict(), dict()
        if elemVar:
            for var_sock in in_nod.outputs:
                if var_sock.name in elemVar:
                    vareq[var_sock.name] = var_sock

        if elemConst:
            xloc, yloc = in_nod.location.x, in_nod.location.y - 330
            for const in elemConst:
                nodetype = 'CompositorNodeValue' if (self.tree_type == 'CompositorNodeTree') else 'ShaderNodeValue'
                con_sck = create_ng_constant_node(ng, nodetype, float(const), f"C|{const}", location=(xloc, yloc))
                yloc -= 90
                consteq[const] = con_sck

        self.update()
        if not (elemVar or elemConst):
            return None

        try:
            transformer = VecAstTranformer()
            astfctexp = transformer.get_function_expression(digested_expression)
        except Exception as e:
            self.error_message = str(e)
            self.debug_fctexp = 'Failed'
            return None

        fctexp = str(ast.unparse(astfctexp))
        self.debug_fctexp = fctexp
        ng.nodes.active = in_nod
        try:
            ast_function_caller(astfctexp, node_tree=ng, vareq=vareq, consteq=consteq)
        except Exception as e:
            self.error_message = str(e)
            return None

        self.debug_nodes_quantity = len(ng.nodes)
        return None

    def draw_label(self):
        if self.label == '':
            return 'Array Vector'
        return self.label

class NODEBOOSTER_NG_GN_ArrayVector(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_ArrayVector(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_ArrayVector(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname

