# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this module gather all kind of math function for sockets
#  when executing these functions, it will create and link new nodes automatically, from sockets to sockets.
#  the '_reusedata' parameter will only update potential default values of existing nodes.


import bpy 

import inspect
from functools import partial
from mathutils import Vector

from ..utils.node_utils import link_sockets, frame_nodes


sBoo = bpy.types.NodeSocketBool
sInt = bpy.types.NodeSocketInt
sFlo = bpy.types.NodeSocketFloat
sCol = bpy.types.NodeSocketColor
sMtx = bpy.types.NodeSocketMatrix
sQut = bpy.types.NodeSocketRotation
sVec = bpy.types.NodeSocketVector


NODE_YOFF, NODE_XOFF = 120, 70
TAGGED = []


class InvalidTypePassedToSocket(Exception):
    def __init__(self, message):
        super().__init__(message)


def check_any_type(*args, types:tuple=None) -> bool:
    """Returns True if any argument in *args is an instance of any type in the 'types' tuple."""
    return any(isinstance(arg, types) for arg in args)

def tag_function(*tags):
    """decorator to easily retrieve functions names by tag on an orderly manner at runtime"""

    def tag_update_decorator(fct):
        """just mark function with tag"""
        
        TAGGED.append(fct)
        fct.tags = tags
        return fct

    return tag_update_decorator
    
def get_nodesetter_functions(tag='', default_ng=None,):
    """get all functions and their names, depending on function types
    optionally, pass the default ng. The '_reusedata' functionality of the functions will be disabled"""

    filtered_functions = [f for f in TAGGED if (tag in f.tags)]

    # If a default node group argument is provided, use functools.partial to bind it
    if (default_ng is not None):
        filtered_functions = [partial(f, default_ng,) for f in filtered_functions]

    return filtered_functions

def generate_documentation(tag=''):
    """generate doc about function subset for user, we are collecting function name and arguments"""

    r = {}
    for f in get_nodesetter_functions(tag=tag):
        fargs = list(f.__code__.co_varnames[:f.__code__.co_argcount])
        if ('ng' in fargs):
            fargs.remove('ng')
        fstr = f'{f.__name__}({", ".join(fargs)})'
        r[f.__name__] = {'repr':fstr, 'doc':f.__doc__,}

    return r

def assert_purple_node(node):
    """we assign the node color as purple, because it means it's being automatically processed & interacted with"""

    #TODO maybe we set purple only if the value is continuously changing
    # clould do that by storing a node['initialvalue'] = value and check if it's changing

    if not node.use_custom_color:
        node.use_custom_color = True
        node.color = [0.5, 0.2, 0.6]
    
    return None


# 88b 88  dP"Yb  8888b.  888888 .dP"Y8     .dP"Y8 888888 888888 888888 888888 88""Yb     888888  dP""b8 888888 .dP"Y8 
# 88Yb88 dP   Yb  8I  Yb 88__   `Ybo."     `Ybo." 88__     88     88   88__   88__dP     88__   dP   `"   88   `Ybo." 
# 88 Y88 Yb   dP  8I  dY 88""   o.`Y8b     o.`Y8b 88""     88     88   88""   88"Yb      88""   Yb        88   o.`Y8b 
# 88  Y8  YbodP  8888Y"  888888 8bodP'     8bodP' 888888   88     88   888888 88  Yb     88      YboodP   88   8bodP' 


def _floatmath(ng,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    _reusedata:str='',
    ) -> sFlo:
    """generic operation for adding a float math node and linking.
    if '_reusedata' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeMath')
        node.operation = operation_type
        node.use_clamp = False
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata #Tag the node, in order to avoid unessessary build
    
    for i,val in enumerate(args):
        match val:

            case sFlo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int():
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _floatmath(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

def _vecmath(ng,
    operation_type:str,
    val1:sFlo|sInt|sBoo|sVec|Vector|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|Vector|float|int|Vector=None,
    _reusedata:str='',
    ) -> sVec:
    """Generic operation for adding a vector math node and linking.
    If '_reusedata' is provided, update the existing node; otherwise, create a new one."""

    node = None
    args = (val1, val2)
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0, 200)
        node = ng.nodes.new('ShaderNodeVectorMath')
        node.operation = operation_type
        node.location = location
        ng.nodes.active = node
    
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata

    for i, val in enumerate(args):
        match val:

            case sVec() | sFlo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float() | int():
                val = Vector((val,val,val))
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _vecmath(). Received unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@tag_function('mathex')
def add(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Addition.\nEquivalent to the '+' symbol."""
    if check_any_type(a,b,types=(Vector,sVec),):
        return _vecmath(ng,'ADD',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'ADD',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def sub(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Subtraction.\nEquivalent to the '-' symbol."""
    if check_any_type(a,b,types=(Vector,sVec),):
        return _vecmath(ng,'SUBTRACT',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'SUBTRACT',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def mult(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Multiplications.\nEquivalent to the '*' symbol."""
    if check_any_type(a,b,types=(Vector,sVec),):
        return _vecmath(ng,'MULTIPLY',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'MULTIPLY',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def div(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Division.\nEquivalent to the '/' symbol."""
    if check_any_type(a,b,types=(Vector,sVec),):
        return _vecmath(ng,'DIVIDE',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'DIVIDE',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def pow(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """A Power n.\nEquivalent to the 'a**n' and '²' symbol."""
    if check_any_type(a,n,types=(Vector,sVec),):
        return _vecmath(ng,'POWER',a,n, _reusedata=_reusedata,)
    return _floatmath(ng,'POWER',a,n, _reusedata=_reusedata,)

@tag_function('mathex')
def log(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Logarithm A base B."""
    return _floatmath(ng,'LOGARITHM',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def sqrt(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Square Root of A."""
    return _floatmath(ng,'SQRT',a, _reusedata=_reusedata,)

@tag_function('mathex')
def invsqrt(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """1/ Square Root of A."""
    return _floatmath(ng,'INVERSE_SQRT',a, _reusedata=_reusedata,)

@tag_function('mathex')
def nroot(ng,
    a:sFlo|sInt|sBoo|float|int,
    n:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """A Root N. a**(1/n.)"""
    
    if (_reusedata): #this function is created multiple nodes so we need multiple tag
          _x = div(ng,1,n, _reusedata=f"{_reusedata}|inner",)
    else: _x = div(ng,1,n,)

    _r = pow(ng,a,_x, _reusedata=_reusedata,)
    frame_nodes(ng, _x.node, _r.node, label='nRoot',)
    return _r

@tag_function('mathex')
def abs(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Absolute of A."""
    if check_any_type(a,types=(Vector,sVec),):
        return _vecmath(ng,'ABSOLUTE',a, _reusedata=_reusedata,)
    return _floatmath(ng,'ABSOLUTE',a, _reusedata=_reusedata,)

@tag_function('mathex')
def neg(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Negate the value of A.\nEquivalent to the symbol '-x.'"""
    _r = sub(ng,0,a, _reusedata=_reusedata,)
    frame_nodes(ng, _r.node, label='Negate',)
    return _r

@tag_function('mathex')
def min(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Minimum between A & B."""
    return _floatmath(ng,'MINIMUM',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def smin(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Minimum between A & B considering a smoothing distance."""
    return _floatmath(ng,'SMOOTH_MIN',a,b,dist, _reusedata=_reusedata,)

@tag_function('mathex')
def max(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Maximum between A & B."""
    return _floatmath(ng,'MAXIMUM',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def smax(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Maximum between A & B considering a smoothing distance."""
    return _floatmath(ng,'SMOOTH_MAX',a,b,dist, _reusedata=_reusedata,)

@tag_function('mathex')
def round(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Round a Float to an Integer."""
    return _floatmath(ng,'ROUND',a, _reusedata=_reusedata,)

@tag_function('mathex')
def floor(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Floor a Float to an Integer."""
    if check_any_type(a,types=(Vector,sVec),):
        return _vecmath(ng,'FLOOR',a, _reusedata=_reusedata,)
    return _floatmath(ng,'FLOOR',a, _reusedata=_reusedata,)

@tag_function('mathex')
def ceil(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Ceil a Float to an Integer."""
    return _floatmath(ng,'CEIL',a, _reusedata=_reusedata,)

@tag_function('mathex')
def trunc(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Trunc a Float to an Integer."""
    return _floatmath(ng,'TRUNC',a, _reusedata=_reusedata,)

@tag_function('mathex')
def frac(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Fraction.\nThe fraction part of A."""
    return _floatmath(ng,'FRACT',a, _reusedata=_reusedata,)

@tag_function('mathex')
def mod(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Modulo.\nEquivalent to the '%' symbol."""
    if check_any_type(a,b,types=(Vector,sVec),):
        return _vecmath(ng,'MODULO',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'MODULO',a,b, _reusedata=_reusedata,)
    
@tag_function('mathex')
def fmod(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Floored Modulo."""
    return _floatmath(ng,'FLOORED_MODULO',a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def wrap(ng,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Wrap value to Range A B."""
    return _floatmath(ng,'WRAP',v,a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def snap(ng,
    v:sFlo|sInt|sBoo|float|int,
    i:sFlo|sInt|sBoo|float|int, 
    _reusedata:str='',
    ) -> sFlo:
    """Snap to Increment."""
    return _floatmath(ng,'SNAP',v,i, _reusedata=_reusedata,)

@tag_function('mathex')
def pingpong(ng,
    v:sFlo|sInt|sBoo|float|int,
    scale:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """PingPong. Wrap a value and every other cycles at cycle Scale."""
    return _floatmath(ng,'PINGPONG',v,scale, _reusedata=_reusedata,)

@tag_function('mathex')
def floordiv(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Floor Division.\nEquivalent to the '//' symbol."""

    if (_reusedata): #this function is created multiple nodes so we need multiple tag
          _x = div(ng,a,b,_reusedata=f"{_reusedata}|inner",)
    else: _x = div(ng,a,b)

    _r = floor(ng,_x,_reusedata=_reusedata)
    frame_nodes(ng, _x.node, _r.node, label='FloorDiv',)
    return _r

@tag_function('mathex')
def sin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Sine of A."""
    return _floatmath(ng,'SINE',a, _reusedata=_reusedata,)

@tag_function('mathex')
def cos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Cosine of A."""
    return _floatmath(ng,'COSINE',a, _reusedata=_reusedata,)

@tag_function('mathex')
def tan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Tangent of A."""
    return _floatmath(ng,'TANGENT',a, _reusedata=_reusedata,)

@tag_function('mathex')
def asin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arcsine of A."""
    return _floatmath(ng,'ARCSINE',a, _reusedata=_reusedata,)

@tag_function('mathex')
def acos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arccosine of A."""
    return _floatmath(ng,'ARCCOSINE',a, _reusedata=_reusedata,)

@tag_function('mathex')
def atan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arctangent of A."""
    return _floatmath(ng,'ARCTANGENT',a, _reusedata=_reusedata,)

@tag_function('mathex')
def hsin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Sine of A."""
    return _floatmath(ng,'SINH',a, _reusedata=_reusedata,)

@tag_function('mathex')
def hcos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Cosine of A."""
    return _floatmath(ng,'COSH',a, _reusedata=_reusedata,)

@tag_function('mathex')
def htan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Tangent of A."""
    return _floatmath(ng,'TANH',a, _reusedata=_reusedata,)

@tag_function('mathex')
def rad(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Convert from Degrees to Radians."""
    return _floatmath(ng,'RADIANS',a, _reusedata=_reusedata,)

@tag_function('mathex')
def deg(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Convert from Radians to Degrees."""
    return _floatmath(ng,'DEGREES',a, _reusedata=_reusedata,)

def _mix(ng,
    data_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    _reusedata:str='',
    ) -> sFlo:
    """generic operation for adding a mix node and linking.
    if '_reusedata' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeMix')
        node.data_type = data_type
        node.clamp_factor = False
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    indexes = None
    match data_type:
        case 'FLOAT':
            indexes = (0,2,3)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):    
        match val:

            case sFlo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _mix(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@tag_function('mathex')
def lerp(ng,
    f:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Mix.\nLinear Interpolation of value A and B from given factor."""
    return _mix(ng,'FLOAT',f,a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def mix(ng,
    f:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo: 
    """Alternative notation to lerp() function."""
    return lerp(ng,f,a,b, _reusedata=_reusedata,)

def _floatclamp(ng,
    clamp_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    _reusedata:str='',
    ) -> sFlo:
    """generic operation for adding a mix node and linking"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeClamp')
        node.clamp_type = clamp_type
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata #Tag the node, in order to avoid unessessary build

    for i,val in enumerate(args):
        match val:

            case sFlo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _floatclamp(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@tag_function('mathex')
def clamp(ng,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Clamp value between min an max."""
    return _floatclamp(ng,'MINMAX',v,a,b, _reusedata=_reusedata,)

@tag_function('mathex')
def clampr(ng,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Clamp value between auto-defined min/max."""
    return _floatclamp(ng,'RANGE',v,a,b, _reusedata=_reusedata,)

def _maprange(ng,
    data_type:str,
    interpolation_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    val4:sFlo|sInt|sBoo|float|int=None,
    val5:sFlo|sInt|sBoo|float|int=None,
    val6:sFlo|sInt|sBoo|float|int=None,
    _reusedata:str='',
    ) -> sFlo:
    """generic operation for adding a remap node and linking"""

    node = None
    args = (val1, val2, val3, val4, val5, val6,)
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeMapRange')
        node.data_type = data_type
        node.interpolation_type = interpolation_type
        node.clamp = False
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata #Tag the node, in order to avoid unessessary build

    for i,val in enumerate(args):
        match val:

            case sFlo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _maprange(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@tag_function('mathex')
def map(ng,
    val:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Map Range.\nRemap a value from a fiven A,B range to a X,Y range."""
    return _maprange(ng,'FLOAT','LINEAR',val,a,b,x,y, _reusedata=_reusedata,)

@tag_function('mathex')
def mapst(ng,
    val:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    step:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Map Range (Stepped).\nRemap a value from a fiven A,B range to a X,Y range with step."""
    return _maprange(ng,'FLOAT','STEPPED',val,a,b,x,y,step, _reusedata=_reusedata,)

@tag_function('mathex')
def mapsmo(ng,
    val:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Map Range (Smooth).\nRemap a value from a fiven A,B range to a X,Y range."""
    return _maprange(ng,'FLOAT','SMOOTHSTEP',val,a,b,x,y, _reusedata=_reusedata,)

@tag_function('mathex')
def mapsmoo(ng,
    val:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Map Range (Smoother).\nRemap a value from a fiven A,B range to a X,Y range."""
    return _maprange(ng,'FLOAT','SMOOTHERSTEP',val,a,b,x,y, _reusedata=_reusedata,)

@tag_function('nexfct')
def separate_xyz(ng,
    v:sVec,
    _reusedata:str='',
    ) -> tuple:
    """Separate a SocketVector into 3 SocketFloat.\nTip: you can use python slicing notations to do that instead."""

    if (type(v) is not sVec):
        raise InvalidTypePassedToSocket(f"ArgsTypeError for separate_xyz(). Recieved unsupported type '{type(v).__name__}'")

    node = None
    needs_linking = False
    
    if (_reusedata):
        node = ng.nodes.get(_reusedata)
    
    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeSeparateXYZ')
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata

    if (needs_linking):
        link_sockets(v, node.inputs[0])

    return tuple(node.outputs)

@tag_function('nexfct')
def combine_xyz(ng,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    z:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sVec:
    """Combine 3 SocketFloat (or python values) into a SocketVector"""

    node = None
    needs_linking = False

    if (_reusedata):
        node = ng.nodes.get(_reusedata)

    if (node is None):
        last = ng.nodes.active
        if last:
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0, 200,)
        node = ng.nodes.new('ShaderNodeCombineXYZ')
        node.location = location
        ng.nodes.active = node
        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata

    for i, val in enumerate((x, y, z)):
        match val:

            case sFlo() | sInt() | sBoo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for combine_xyz(). Received unsupported type '{type(val).__name__}'")

    return node.outputs[0]



#TODO support comparison functions
# def equal(a, b,)
# def notequal(a, b,)
# def aequal(a, b, threshold,)
# def anotequal(a, b, threshold,)
# def issmaller(a, b,)
# def isasmaller(a, b, threshold,)
# def isbigger(a, b,)
# def isabigger(a, b, threshold,)
# def isbetween(a, x, y,)
# def isabetween(a, x, y, threshold,)
# def isbetweeneq(a, x, y,)
