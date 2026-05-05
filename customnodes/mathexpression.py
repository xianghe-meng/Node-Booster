# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


# NOTE How does it works?
# 1- Find the variables or constants with regex
# 2- dynamically remove/create sockets accordingly
# 3- transform the algebric expression into ast 'function expressions' using see 'get_function_expression()'
# 4- call the function using 'ast_function_caller()' functions names will correspond to the nodesetter.py 
#    functions and will set up new nodes and links.

# TODO 
# - color of the node header should be blue for converter.. how to do that without hacking in the memory??
# - support >= == < ect comparison operand, using right nodes for cross compatibility!!

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
    cache_booster_nodes_parent_tree,
    get_ng_socket_by_name,
    set_ng_socket_defvalue,
)
from ..nex.nodesetter import (
    get_nodesetter_functions, 
    generate_documentation,
    sepaxyz,
)


DIGITS = '0123456789'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
IRRATIONALS = {'π':'3.1415927','𝑒':'2.7182818','φ':'1.6180339',}
MACROS = {'Pi':'π','eNum':'𝑒','Gold':'φ',}
SUPERSCRIPTS = {'⁰':'0', '¹':'1', '²':'2', '³':'3', '⁴':'4', '⁵':'5', '⁶':'6', '⁷':'7', '⁸':'8', '⁹':'9',}
MATHEXFUNCDOC = generate_documentation(tag='mathex')
MATHNOTATIONDOC = {
    '+':{
        'name':"Addition",
        'desc':""},
    '-':{
        'name':"Subtraction.",
        'desc':"Can be used to negate as well ex: -x"},
    '*':{
        'name':"Multiplication.",
        'desc':""},
    '**':{
        'name':"Power.",
        'desc':""},
    '²':{ #Supported during sanatization
        'name':"Power Notation.",
        'desc':"\nPlease note that 2ab² will either be transformed into (ab)**2 or a*((b)**2) depending if you use 'Algebric Notations'."},
    '/':{
        'name':"Division.",
        'desc':""},
    '//':{
        'name':"FloorDiv.",
        'desc':""},
    '%':{
        'name':"Modulo.",
        'desc':""},
    'π':{ #Supported during sanatization
        'name':"Pi",
        'desc':"Represented as 3.1415927 float value.\nInvoked using the 'Pi' Macro."},
    '𝑒':{ #Supported during sanatization
        'name':"EulerNumber.",
        'desc':"Represented as 2.7182818 float value.\nInvoked using the 'eNum' Macro."},
    'φ':{ #Supported during sanatization
        'name':"GoldenRation.",
        'desc':"Represented as 1.6180339 float value.\nInvoked using the 'Gold' Macro."},
    }

#Store the math function used to set the nodetree
USER_FNAMES = get_nodesetter_functions(tag='mathex', get_names=True)
VECTOR_COMPONENT_FNS = {'getx', 'gety', 'getz'}
VECTOR_LITERAL_FNS = {'vec'}


def replace_superscript_exponents(expr: str, algebric_notation:bool=False,) -> str:
    """convert exponent to ** notation
    Example: "2ab²" becomes "2(ab**2) or "2ab²" becomes "2a(b**2)" if alrebric_notation
    """
    
    # Pattern for alphanumeric base followed by superscripts.
    if (algebric_notation):
          pattern_base = r'([A-Za-z0-9π𝑒φ])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
    else: pattern_base = r'([A-Za-z0-9π𝑒φ]+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
        
    def repl_base(match):
        base = match.group(1)
        superscripts = match.group(2)
        # Convert each superscript character to its digit equivalent.
        exponent = "".join(SUPERSCRIPTS.get(ch, '') for ch in superscripts)
        # Wrap the base in parentheses and apply the power operator.
        return f"({base}**{exponent})"
    
    # Pattern for a closing parenthesis immediately followed by superscripts.
    pattern_paren = r'(\))([⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
    
    def repl_parenthesis(match):
        closing = match.group(1)
        superscripts = match.group(2)
        exponent = "".join(SUPERSCRIPTS.get(ch, '') for ch in superscripts)
        # Just insert ** before the exponent after the parenthesis.
        return f"){f'**{exponent}'}"
    
    expr = re.sub(pattern_base, repl_base, expr)
    expr = re.sub(pattern_paren, repl_parenthesis, expr)
    return expr


def ast_function_caller(visited, node_tree=None, vareq:dict=None, consteq:dict=None):
    """Recursively evaluates the transformed AST tree and calls its functions with their arguments.="""
    
    user_functions_partials = get_nodesetter_functions(tag='mathex', partialdefaults=(node_tree,None),)
    user_function_namespace = {f.func.__name__:f for f in user_functions_partials}

    def getx(socket):
        return sepaxyz(node_tree, None, socket)[0]

    def gety(socket):
        return sepaxyz(node_tree, None, socket)[1]

    def getz(socket):
        return sepaxyz(node_tree, None, socket)[2]

    user_function_namespace.update({
        'getx': getx,
        'gety': gety,
        'getz': getz,
    })
    
    def caller(node):
        
        match node:
            
            # we found a function? we call it and evaluate their args.
            case ast.Call():

                # First, evaluate all arguments recursively.
                evaluated_args = [caller(arg) for arg in node.args]

                # Evaluate the function part.
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if (func_name not in user_function_namespace):
                        raise Exception(f"Function '{func_name}' not recognized.")

                    func = user_function_namespace[func_name]
                    # Call the function with the evaluated arguments.
                    return func(*evaluated_args)

                # In case the function part is a more complex expression,
                # evaluate it recursively and then call it.
                evaluated_func = caller(node.func)
                return evaluated_func(*evaluated_args)
            
            # we found a variable name? need to get it's socket value
            case ast.Name():
                if (vareq is not None and node.id in vareq):
                    return vareq[node.id]
                elif (consteq is not None and node.id in consteq):
                    return consteq[node.id]
                raise Exception(f"Element '{node.id}' not recognized.")

            # we found a constant? need to get it's socket value
            case ast.Constant():
                key = str(node.value)
                if (consteq is not None and key in consteq):
                    return consteq[key]
                else:
                    return node.value

            # User messed up and created a tuple instead of a function?
            case ast.Tuple():
                raise Exception("Wrong use of '( , )' Synthax")

            # Something else? what can it be?
            case _:
                raise Exception(f"Unknown ast type '{type(node).__name__}'.")

    final_socket = caller(visited)
    
    # We still need to connect to the nodegroup output
    try:
        last = node_tree.nodes.active
        out_node = node_tree.nodes['Group Output']
        out_node.location = (last.location.x+last.width+70, last.location.y-120,)
        link_sockets(final_socket, out_node.inputs[0])

    except Exception as e:
        print(f"{type(e).__name__} FinalLinkError: ast_function_caller():\n  {e}")
        raise Exception("Error on Final Link. See console.")

    return None


class AstTranformer(ast.NodeTransformer):
    """AST Transformer for converting math expressions into function-call expressions."""

    def __init__(self):
        super().__init__()

    def visit_BinOp(self, node):
        # First, process child nodes.
        self.generic_visit(node)

        # Map ast operators and transform to supported function names
        match node.op:
            case ast.Add():
                func_name = 'add'
            case ast.Sub():
                func_name = 'sub'
            case ast.Mult():
                func_name = 'mult'
            case ast.Div():
                func_name = 'div'
            case ast.Pow():
                func_name = 'pow'
            case ast.Mod():
                func_name = 'mod'
            case ast.FloorDiv():
                func_name = 'floordiv'
            case _:
                print(f"AstTranformer `{node.op}` NotImplementedError")
                raise Exception(f"Operator {node.op} not supported")

        # Replace binary op with a function call.
        return ast.Call(
            func=ast.Name(id=func_name, ctx=ast.Load()),
            args=[node.left, node.right],
            keywords=[],
        )

    def visit_UnaryOp(self, node):
        # Process child nodes first.
        self.generic_visit(node)
        # Replace -X with neg(X)
        if isinstance(node.op, ast.USub):
            return ast.Call(
                func=ast.Name(id='neg', ctx=ast.Load()),
                args=[node.operand],
                keywords=[]
            )
        # Otherwise, just return the node unchanged.
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node):
        self.generic_visit(node)

        match node.attr:
            case 'x':
                func_name = 'getx'
            case 'y':
                func_name = 'gety'
            case 'z':
                func_name = 'getz'
            case _:
                raise Exception(f"Attribute '.{node.attr}' not supported")

        return ast.Call(
            func=ast.Name(id=func_name, ctx=ast.Load()),
            args=[node.value],
            keywords=[],
        )

    def visit_Name(self, node):
        return node

    def visit_Num(self, node):
        return node

    def visit_Constant(self, node):
        return node

    def visit_List(self, node):
        self.generic_visit(node)

        if (len(node.elts) != 3):
            raise Exception("Vector literal must contain exactly 3 elements")

        return ast.Call(
            func=ast.Name(id='vec', ctx=ast.Load()),
            args=node.elts,
            keywords=[],
        )

    def get_function_expression(self, math_express: str) -> str:
        """Transforms a math expression into a function-call expression.
        Example: 'x*2 + (3-4/5)/3 + (x+y)**2' becomes 'add(mult(x,2),div(sub(3,div(4,5)),3),exp(add(x,y),2))'"""
        
        # Use the ast module to visit our equation
        try:
            tree = ast.parse(math_express, mode='eval')
            visited = self.visit(tree.body)
        except Exception as e:
            print(f"AstTranformer ParsingError {type(e).__name__}:\n  Expression: `{math_express}`\n{e}")
            raise Exception("Math Expression Not Recognized")
        
        return visited

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 

class Base():

    bl_idname = "NodeBoosterMathExpression"
    bl_label = "Math Expression"
    bl_description = """Evaluate a float math equation and create sockets from given variables on the fly.\n
    • The sockets are limited to Float types. Consider this node a 'Float Math Expression' node.\n
    • Please See the 'NodeBooster > Active Node > Glossary' panel to see all functions and notation available and their descriptions.\n
    • If you wish to bake this node into a nodegroup, a bake operator is available in the 'NodeBooster > Active Node' panel.\n
    • Under the hood, on each string field edit, the expression will be sanarized, then transformed into functions that will be called to create a nodetree, see the breakdown of the process in the 'NodeBooster > Active Node > Development' panel."""
    nb_menu_path = ['NodeBooster','Expressions',bl_label,] #path in add menu
    auto_upd_flags = {'NONE',}
    tree_type = "*ChildrenDefined*"
    expression_text_socket_name = "Expression"

    error_message : bpy.props.StringProperty(
        description="User interface error message"
        )
    debug_sanatized : bpy.props.StringProperty(
        description="Sanatized expression, first layer of expression interpretation"
        )
    debug_fctexp : bpy.props.StringProperty(
        description="Function expression, this function will be executed to create the nodetree."
        )
    debug_nodes_quantity : bpy.props.IntProperty(
        name="Number of nodes in the nodetree",
        default=-1,
        )

    def update_signal(self,context):
        self.apply_user_expression()
        return None 

    user_mathexp : bpy.props.StringProperty(
        default="",
        name="Expression",
        update=update_signal,
        description="type your math expression right here",
        )
    user_variables_float : bpy.props.StringProperty(
        default="",
        name="Pinned Float Variables",
        update=update_signal,
        description="Comma separated float variables that stay exposed as inputs even when not used in the expression",
        )
    user_variables_vector : bpy.props.StringProperty(
        default="",
        name="Pinned Vector Variables",
        update=update_signal,
        description="Comma separated vector variables that stay exposed as inputs even when not used in the expression",
        )
    use_algrebric_multiplication : bpy.props.BoolProperty(
        default=False,
        name="Algebric Notation",
        update=update_signal,
        description="Algebric Notation.\nAutomatically consider notation such as '2ab' as '2*a*b'",
        )
    use_macros : bpy.props.BoolProperty(
        default=False,
        name="Recognize Macros",
        update=update_signal,
        description="Recognize Macros.\nAutomatically recognize the strings 'Pi' 'eNum' 'Gold' and replace them with their unicode symbols.",
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
            out_sockets = {"Result" : "NodeSocketFloat",}
            if (self.supports_expression_text_output()):
                out_sockets[self.expression_text_socket_name] = "NodeSocketString"
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets=out_sockets,
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng
        self.ensure_expression_text_output()

        self.width = 250

        return None 

    def copy(self,node,):
        """fct run when dupplicating the node"""

        from ..utils.node_utils import schedule_customnode_tree_copy
        schedule_customnode_tree_copy(self, node)
        
        return None 
    
    def update(self):
        """generic update function"""

        from ..utils.node_utils import ensure_customnode_tree_ownership
        ensure_customnode_tree_ownership(self)

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def supports_expression_text_output(self) -> bool:
        """Only the geometry variant exposes the raw expression as a string output."""

        return (self.tree_type == "GeometryNodeTree")

    def ensure_expression_text_output(self):
        """Ensure the backing node group exposes the optional string output."""

        if (not self.supports_expression_text_output()):
            return None

        ng = self.node_tree
        if (ng is None):
            return None

        socket = get_ng_socket_by_name(ng, self.expression_text_socket_name, in_out='OUTPUT')
        if (socket is None):
            socket = create_ng_socket(ng,
                in_out='OUTPUT',
                socket_type="NodeSocketString",
                socket_name=self.expression_text_socket_name,
                )

        return socket

    def get_variable_socket_type(self, var_name: str) -> str:
        """Resolve the group input socket type for a collected variable."""

        if (var_name in getattr(self, 'elemVec', ())):
            return "NodeSocketVector"
        if (var_name in getattr(self, 'elemManualVec', ())):
            return "NodeSocketVector"
        return "NodeSocketFloat"

    def digest_manual_variable_list(self, raw_variables: str, kind: str) -> set[str]:
        """Parse user-pinned variable names from a comma separated string."""

        if (raw_variables is None or raw_variables == ""):
            return set()

        reserved = set(USER_FNAMES) | VECTOR_COMPONENT_FNS | VECTOR_LITERAL_FNS
        variables = set()

        for raw_var in raw_variables.split(','):
            raw_var = raw_var.strip()
            if (raw_var == ""):
                continue
            if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', raw_var)):
                raise Exception(f"Invalid pinned {kind} variable '{raw_var}'")
            if (raw_var in reserved):
                raise Exception(f"Pinned variable '{raw_var}' is Taken")
            variables.add(raw_var)

        return variables

    def digest_manual_variables(self) -> set[str]:
        """Parse user-pinned float and vector variables."""

        self.elemManualVec = self.digest_manual_variable_list(self.user_variables_vector, 'vector')
        elem_manual_float = self.digest_manual_variable_list(self.user_variables_float, 'float')

        overlap = self.elemManualVec & elem_manual_float
        if (overlap):
            name = sorted(overlap)[0]
            raise Exception(f"Pinned variable '{name}' is declared as both float and vector")

        return elem_manual_float | self.elemManualVec
    
    def digest_user_expression(self, expression) -> str:
        """regex transformers. We ensure the user expression is correct, if he is using correct symbols, 
        we sanatized it, transform some notations and collect a maximum of its variable to create variable sockets or constant nodes later."""

        authorized_symbols = ALPHABET + DIGITS + '/*-+%.,()[]'
        vector_component_pattern = r'(?<!\d)([A-Za-z][A-Za-z0-9]*)\.(x|y|z)\b'

        self.elemVec = set()

        for match in re.finditer(vector_component_pattern, expression):
            self.elemVec.add(match.group(1))
         
        # Remove white spaces char
        expression = expression.replace(' ','')
        expression = expression.replace('	','')
                
        # Sanatize ² Notations
        for char in expression:
            if char in SUPERSCRIPTS.keys():
                expression = replace_superscript_exponents(expression,
                    algebric_notation=self.use_algrebric_multiplication,
                    )
                break 
        
        # Support for Irrational unicode char
        mached = match_exact_tokens(expression, IRRATIONALS.keys())
        if any(mached):
            expression = replace_exact_tokens(expression, IRRATIONALS)
        
        # Gather lists of expression component outside of operand and some synthax elements.
        # Strip supported vector component suffixes here so expressions like
        # '[a,b,c].x' or 'normalize(v).y' don't leave a stray '.x' token behind.
        elemTotal = re.sub(r'\.(x|y|z)\b', '', expression)
        for char in '/*-+%,()[]':
            elemTotal = elemTotal.replace(char,'|')
        self.elemTotal = set(e for e in elemTotal.split('|') if e!='')
        
        # Implicit multiplication on parentheses? Need to add '*(' or ')*' then
        match self.use_algrebric_multiplication:
            
            # Is any vars right next to any parentheses? ex: a(ab)²c
            case True:
                for e in self.elemTotal:
                    if (e not in USER_FNAMES):
                        if match_exact_tokens(expression,f'{e}('):
                            expression = replace_exact_tokens(expression,{f'{e}(':f'{e}*('})
                        if match_exact_tokens(expression,f'){e}'):
                            expression = replace_exact_tokens(expression,{f'){e}':f')*{e}'})
            
            # At least Support for implicit math operation on parentheses (ex: '*(' '2(a+b)' or '2.59(c²)')
            case False:
                expression = re.sub(r"(\d+(?:\.\d+)?)([\(\[])", r"\1*\2", expression)
        
        # Gather and sort our expression elements
        # they can be either variables, constants, functions, or unrecognized
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
                     
                    #we have a function
                    if (e in USER_FNAMES):
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue
                    
                    #we have float or int?
                    if (e.replace('.','').isdigit()):
                        if (not is_float_compatible(e)):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue
                    
                    #we have a single char alphabetical variable a,x,E ect..
                    if (len(e)==1 and (e in ALPHABET)):
                        self.elemVar.add(e)
                        continue
                    
                    #check if user varnames is ok
                    for c in list(e):
                        if (c not in list(authorized_symbols) + list(IRRATIONALS.keys())):
                            raise Exception(f"Unauthorized Symbol '{c}'")
                            
                    # Then it means we have a composite element (ex 2ab)
                    self.elemComp.add(e)
                    
                    # Separate our composite into a list of int/float with single alphabetical char
                    # ex 24abc1.5 to [24,a,b,c,1.5]
                    esplit = [m for match in re.finditer(r'(\d+\.\d+|\d+)|([a-zA-Z])', e) for m in match.groups() if m]

                    # Store the float or int const elems of the composite
                    for esub in esplit:
                        if (esub.replace('.','').isdigit()):
                            self.elemConst.add(esub)
                        elif (esub.isalpha() and len(esub)==1):
                            self.elemVar.add(esub)
                        else:
                            msg = f"Unknown Element '{esub}' of Composite '{e}'"
                            print(f"Exception: digest_user_expression():\n{msg}")
                            raise Exception(msg)
                            
                    # Insert inplicit multiplications
                    expression = replace_exact_tokens(expression,{e:'*'.join(esplit)})
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

                    #we have a function
                    if (e in USER_FNAMES):
                        if f'{e}(' in expression:
                            self.elemFct.add(e)
                            continue

                    #we have float or int?
                    if (e.replace('.','').isdigit()):
                        if (not is_float_compatible(e)):
                            raise Exception(f"Unrecognized Float '{e}'")
                        self.elemConst.add(e)
                        continue

                    #we have a variable (ex 'ab' or 'x')
                    if all(c in ALPHABET for c in list(e)):
                        if (e in USER_FNAMES):
                            raise Exception(f"Variable '{e}' is Taken")
                        self.elemVar.add(e)
                        continue

                    #check for bad symbols
                    for c in list(e):
                        if (c not in list(authorized_symbols) + list(IRRATIONALS.keys())):
                            raise Exception(f"Unauthorized Symbol '{c}'")

                    #unauthorized variable? technically, it's unrecognized
                    raise Exception(f"Unauthorized Variable '{e}'")
        
        #Order our variable alphabetically
        self.elemVar = sorted(self.elemVar)
        self.elemVec = set(v for v in self.elemVec if v in self.elemVar)

        # Ensure user is using correct symbols #NOTE we do that 3 times already tho.. reperitive.
        for char in expression:
            if (char not in authorized_symbols):
                raise Exception(f"Unauthorized Symbol '{char}'")
        
        return expression
    
    def apply_macros(self, expression) -> str:
        """Replace macros such as 'Pi' 'eNum' or else..  by their values"""
        
        modified_expression = None
        
        for k,v in MACROS.items():
            if (k in expression):
                if (modified_expression is None):
                    modified_expression = expression
                modified_expression = modified_expression.replace(k,v)
            
        return modified_expression
    
    def store_equation(self, text):
        """we store the user text data as a frame"""

        ng = self.node_tree

        frame = ng.nodes.get("EquationStorage")
        if (frame is None):
            frame = ng.nodes.new('NodeFrame')
            frame.name = "EquationStorage"
            frame.width = 750
            frame.height = 50
            frame.location.x = -1000
            frame.label_size = 20

        if (frame.label!=text):
            frame.label = text

        return None

    def apply_user_expression(self) -> None:
        """transform the math expression into sockets and nodes arrangements"""

        # Support for automatically replacing uer symbols
        if (self.use_macros):
            new = self.apply_macros(self.user_mathexp)
            if (new is not None):
                self.user_mathexp = new
                # We just sent an update signal by modifying self.user_mathexp
                # let's stop here then, the function will restart shortly and we don't have a recu error.
                return None

        ng = self.node_tree 
        assert ng is not None, "apply_user_expression(): 'self.node_tree' must'nt be None"
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]

        expression_socket = self.ensure_expression_text_output()
        if (expression_socket is not None):
            set_ng_socket_defvalue(ng, socket=expression_socket, in_out='OUTPUT', value=self.user_mathexp)

        # Reset error message
        self.error_message = self.debug_sanatized = self.debug_fctexp = ""

        # Keepsafe the math expression within the group, might be useful later.
        self.store_equation(self.user_mathexp)

        try:
            self.elemManual = self.digest_manual_variables()
        except Exception as e:
            self.error_message = str(e)
            self.debug_sanatized = 'Failed'
            return None

        # First we make sure the user expression is correct, & collect the variables!
        try:
            r = self.digest_user_expression(self.user_mathexp)
        except Exception as e:
            self.error_message = str(e)
            self.debug_sanatized = 'Failed'
            return None

        # We store the digested expression for debug aid.
        digested_expression = self.debug_sanatized = r
        # running 'digest_user_expression()' collected all possible constants values or socket variable.
        elemVar = sorted(set(self.elemVar) | self.elemManual)
        elemConst = self.elemConst
        self.elemVar = elemVar

        # Clean up the node tree, we are about to rebuild it!
        for node in list(ng.nodes).copy():
            if (node.name not in {"Group Input", "Group Output", "EquationStorage",}):
                ng.nodes.remove(node)

        # Create new sockets depending on collected variables.
        if (elemVar):
            current_vars = [s.name for s in in_nod.outputs]
            for var in elemVar:
                if (var not in current_vars):
                    create_ng_socket(ng,
                        in_out='INPUT',
                        socket_type=self.get_variable_socket_type(var),
                        socket_name=var,
                        )

        # Remove unused sockets
        idx_to_del = []
        for idx,socket in enumerate(in_nod.outputs):
            if ((socket.type!='CUSTOM') and (socket.name not in elemVar)):
                idx_to_del.append(idx)
        for idx in reversed(idx_to_del):
            remove_ng_socket(ng, idx, in_out='INPUT')

        # Keep sockets in sync with inferred variable types.
        for socket in list(in_nod.outputs):
            if (socket.type=='CUSTOM'):
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

        # We need to collect the equivalence between the varnames and const and their constant socket representation
        vareq, consteq = dict(), dict()

        # Fill equivalence dict with it's socket eq
        # Starts with variable sockets
        if (elemVar):
            for var_sock in in_nod.outputs:
                if (var_sock.name in elemVar):
                    vareq[var_sock.name] = var_sock
                    continue
        # Then constant sockets (new input nodes)
        # Add input for constant right below the vars group input
        if (elemConst):
            xloc, yloc = in_nod.location.x, in_nod.location.y-330
            for const in elemConst:
                nodetype = 'CompositorNodeValue' if (self.tree_type=='CompositorNodeTree') else 'ShaderNodeValue'
                con_sck = create_ng_constant_node(ng, nodetype, float(const), f"C|{const}", location=(xloc,yloc),)
                yloc -= 90
                consteq[const] = con_sck
                continue

        # Give it a refresh signal, when we remove/create a lot of sockets, the customnode inputs/outputs need a kick
        self.update()

        if (digested_expression == ""):
            return None

        # if we don't have any elements to work with, quit
        if not (elemVar or elemConst):
            return None

        # Transform user expression containing '/*-+' notations into a function expression using the ast module
        try:
            transformer = AstTranformer()
            astfctexp = transformer.get_function_expression(digested_expression)
        except Exception as e:
            self.error_message = str(e)
            self.debug_fctexp = 'Failed'
            return None

        # We display the ast function expression as a debug helper
        fctexp = str(ast.unparse(astfctexp))
        self.debug_fctexp = fctexp
        
        # We always set the input node as active, the nodetree offset arrangement is based on active node.
        ng.nodes.active = in_nod

        # Call the functions in ast order, this will arrange the nodetree!
        try:
            ast_function_caller(astfctexp, node_tree=ng, vareq=vareq, consteq=consteq,)
        except Exception as e:
            self.error_message = str(e)
            return None

        #we count the number of nodes
        self.debug_nodes_quantity = len(ng.nodes)

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Math Expression'
        return self.label

    def draw_buttons(self, context, layout,):
        """node interface drawing"""

        is_error = bool(self.error_message)

        col = layout.column(align=True)
        row = col.row(align=True)

        field = row.row(align=True)
        field.alert = is_error
        field.prop(self, "user_mathexp", placeholder="(a + sin(b)/c)²", text="",)

        opt = row.row(align=True)
        opt.scale_x = 0.35
        opt.prop(self, "use_algrebric_multiplication", text="ab", toggle=True, )

        opt = row.row(align=True)
        opt.scale_x = 0.3
        opt.prop(self, "use_macros", text="π", toggle=True, )

        if (is_error):
            col = col.column(align=True)
            col.separator(factor=1)
            word_wrap(layout=col, alert=True, active=True, max_char=self.width/5.75, string=self.error_message,)

        row = col.row(align=True)
        row.prop(self, "user_variables_float", placeholder="a, b, speed", text="",)

        row = col.row(align=True)
        row.prop(self, "user_variables_vector", placeholder="v, velocity, normal", text="",)

        layout.separator(factor=0.75)

        return None
    
    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
    
        n = self

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):

            is_error = bool(n.error_message)
            col = panel.column(align=True)
            row = col.row(align=True)
            row.alert = is_error
            row.prop(n, "user_mathexp", placeholder="(a + sin(b)/c)²", text="",)

            if (is_error):
                lbl = col.row()
                lbl.alert = is_error
                lbl.label(text=n.error_message)

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
                    row.prop(s,'default_value', text=s.name,)
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

            for symbol,v in MATHNOTATIONDOC.items():

                desc = v['name']+'\n'+v['desc'] if v['desc'] else v['name']
                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=symbol,)

                col.separator(factor=0.5)

                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=desc, alignment='LEFT',
                    )
                col.separator()

            for fname,fdoc in MATHEXFUNCDOC.items():

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

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """search for all node instances of this type and refresh them. Will be called automatically if .auto_upd_flags's are defined"""

        # No need to update anything for this node. 
        # The update is done when the user enter his text.
        
        return None

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_MathExpression(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_MathExpression(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_MathExpression(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname
