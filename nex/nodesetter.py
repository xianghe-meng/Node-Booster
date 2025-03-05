# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this module gather all kind of math function for sockets
#  when executing these functions, it will create and link new nodes automatically, from sockets to sockets.
#  the '_reusedata' parameter will only update potential default values of existing nodes.


import bpy 

import math
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


def anytype(*args, types:tuple=None) -> bool:
    """Returns True if any argument in *args is an instance of any type in the 'types' tuple."""
    return any(isinstance(arg, types) for arg in args)

def convert_args(*args, toVector=False,) -> tuple:
    if (toVector):
        return [Vector((a,a,a)) if type(a) in (int,bool,float) else a for a in args]
    return None
    
def user_domain(*tags):
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
        if ('_reusedata' in fargs):
            fargs.remove('_reusedata')
        fstr = f'{f.__name__}({", ".join(fargs)})'
        r[f.__name__] = {'repr':fstr, 'doc':f.__doc__,}

    return r

def assert_purple_node(node):
    """we assign the node color as purple, because it means it's being automatically processed & interacted with"""

    #TODO maybe we set purple only if the value is continuously changing
    # clould do that by storing a node['initialvalue'] = value and check if it's changing

    if (not node.use_custom_color):
        node.use_custom_color = True
        node.color = [0.5, 0.2, 0.6]
    
    return None


# oooooooooooo                                       .    o8o                                 
# `888'     `8                                     .o8    `"'                                 
#  888         oooo  oooo  ooo. .oo.    .ooooo.  .o888oo oooo   .ooooo.  ooo. .oo.    .oooo.o 
#  888oooo8    `888  `888  `888P"Y88b  d88' `"Y8   888   `888  d88' `88b `888P"Y88b  d88(  "8 
#  888    "     888   888   888   888  888         888    888  888   888  888   888  `"Y88b.  
#  888          888   888   888   888  888   .o8   888 .  888  888   888  888   888  o.  )88b 
# o888o         `V88V"V8P' o888o o888o `Y8bod8P'   "888" o888o `Y8bod8P' o888o o888o 8""888P' 
                                                                                            

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

            case sFlo() | sInt() | sBoo():
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

            case sVec() | sFlo() | sInt() | sBoo():
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

@user_domain('mathex')
def add(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Addition.\nEquivalent to the '+' symbol."""
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,'ADD',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'ADD',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def sub(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Subtraction.\nEquivalent to the '-' symbol."""
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,'SUBTRACT',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'SUBTRACT',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def mult(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Multiplications.\nEquivalent to the '*' symbol."""
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,'MULTIPLY',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'MULTIPLY',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def div(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Division.\nEquivalent to the '/' symbol."""
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,'DIVIDE',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'DIVIDE',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def pow(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """A Power n.\nEquivalent to the 'a**n' and '²' symbol."""
    if anytype(a,n,types=(sVec,),):
        return _vecmath(ng,'POWER',a,n, _reusedata=_reusedata,)
    return _floatmath(ng,'POWER',a,n, _reusedata=_reusedata,)

@user_domain('mathex')
def log(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Logarithm A base B."""
    return _floatmath(ng,'LOGARITHM',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def sqrt(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Square Root of A."""
    return _floatmath(ng,'SQRT',a, _reusedata=_reusedata,)

@user_domain('mathex')
def invsqrt(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """1/ Square Root of A."""
    return _floatmath(ng,'INVERSE_SQRT',a, _reusedata=_reusedata,)

@user_domain('mathex')
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

@user_domain('mathex')
def abs(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Absolute of A."""
    if anytype(a,types=(sVec,),):
        return _vecmath(ng,'ABSOLUTE',a, _reusedata=_reusedata,)
    return _floatmath(ng,'ABSOLUTE',a, _reusedata=_reusedata,)

@user_domain('mathex')
def neg(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Negate the value of A.\nEquivalent to the symbol '-x.'"""
    _r = sub(ng,0,a, _reusedata=_reusedata,)
    frame_nodes(ng, _r.node, label='Negate',)
    return _r

@user_domain('mathex')
def min(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Minimum between A & B."""
    return _floatmath(ng,'MINIMUM',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def smin(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Minimum between A & B considering a smoothing distance."""
    return _floatmath(ng,'SMOOTH_MIN',a,b,dist, _reusedata=_reusedata,)

@user_domain('mathex')
def max(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Maximum between A & B."""
    return _floatmath(ng,'MAXIMUM',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def smax(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Maximum between A & B considering a smoothing distance."""
    return _floatmath(ng,'SMOOTH_MAX',a,b,dist, _reusedata=_reusedata,)

@user_domain('mathex')
def round(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Round a Float to an Integer."""
    return _floatmath(ng,'ROUND',a, _reusedata=_reusedata,)

@user_domain('mathex')
def floor(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Floor a Float to an Integer."""
    if anytype(a,types=(sVec,),):
        return _vecmath(ng,'FLOOR',a, _reusedata=_reusedata,)
    return _floatmath(ng,'FLOOR',a, _reusedata=_reusedata,)

@user_domain('mathex')
def ceil(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Ceil a Float to an Integer."""
    return _floatmath(ng,'CEIL',a, _reusedata=_reusedata,)

@user_domain('mathex')
def trunc(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Trunc a Float to an Integer."""
    return _floatmath(ng,'TRUNC',a, _reusedata=_reusedata,)

@user_domain('mathex')
def frac(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Fraction.\nThe fraction part of A."""
    return _floatmath(ng,'FRACT',a, _reusedata=_reusedata,)

@user_domain('mathex')
def mod(ng,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Modulo.\nEquivalent to the '%' symbol."""
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,'MODULO',a,b, _reusedata=_reusedata,)
    return _floatmath(ng,'MODULO',a,b, _reusedata=_reusedata,)
    
@user_domain('mathex')
def flooredmod(ng,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Floored Modulo."""
    return _floatmath(ng,'FLOORED_MODULO',a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def wrap(ng,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Wrap value to Range A B."""
    return _floatmath(ng,'WRAP',v,a,b, _reusedata=_reusedata,)

@user_domain('mathex')
def snap(ng,
    v:sFlo|sInt|sBoo|float|int,
    i:sFlo|sInt|sBoo|float|int, 
    _reusedata:str='',
    ) -> sFlo:
    """Snap to Increment."""
    return _floatmath(ng,'SNAP',v,i, _reusedata=_reusedata,)

@user_domain('mathex')
def pingpong(ng,
    v:sFlo|sInt|sBoo|float|int,
    scale:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """PingPong. Wrap a value and every other cycles at cycle Scale."""
    return _floatmath(ng,'PINGPONG',v,scale, _reusedata=_reusedata,)

@user_domain('mathex')
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

@user_domain('mathex')
def sin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Sine of A."""
    return _floatmath(ng,'SINE',a, _reusedata=_reusedata,)

@user_domain('mathex')
def cos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Cosine of A."""
    return _floatmath(ng,'COSINE',a, _reusedata=_reusedata,)

@user_domain('mathex')
def tan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Tangent of A."""
    return _floatmath(ng,'TANGENT',a, _reusedata=_reusedata,)

@user_domain('mathex')
def asin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arcsine of A."""
    return _floatmath(ng,'ARCSINE',a, _reusedata=_reusedata,)

@user_domain('mathex')
def acos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arccosine of A."""
    return _floatmath(ng,'ARCCOSINE',a, _reusedata=_reusedata,)

@user_domain('mathex')
def atan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Arctangent of A."""
    return _floatmath(ng,'ARCTANGENT',a, _reusedata=_reusedata,)

@user_domain('mathex')
def hsin(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Sine of A."""
    return _floatmath(ng,'SINH',a, _reusedata=_reusedata,)

@user_domain('mathex')
def hcos(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Cosine of A."""
    return _floatmath(ng,'COSH',a, _reusedata=_reusedata,)

@user_domain('mathex')
def htan(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """The Hyperbolic Tangent of A."""
    return _floatmath(ng,'TANH',a, _reusedata=_reusedata,)

@user_domain('mathex')
def rad(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Convert from Degrees to Radians."""
    return _floatmath(ng,'RADIANS',a, _reusedata=_reusedata,)

@user_domain('mathex')
def deg(ng,
    a:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Convert from Radians to Degrees."""
    return _floatmath(ng,'DEGREES',a, _reusedata=_reusedata,)

def _mix(ng,
    data_type:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    _reusedata:str='',
    ) -> sFlo|sVec:
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
        node.factor_mode = 'NON_UNIFORM'
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (_reusedata):
            node.name = node.label = _reusedata #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    outidx = None
    indexes = None
    match data_type:
        case 'FLOAT':
            outidx = 0
            indexes = (0,2,3)
        case 'VECTOR':
            outidx = 1
            indexes = (1,4,5)
            args = convert_args(*args, toVector=True,)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _mix(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[outidx]

@user_domain('mathex','nexgeneral')
def lerp(ng,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Mix.\nLinear Interpolation of value A and B from given factor."""
    if anytype(f,a,b,types=(sVec,Vector,),):
        return _mix(ng,'VECTOR',f,a,b, _reusedata=_reusedata,)
    return _mix(ng,'FLOAT',f,a,b, _reusedata=_reusedata,)

@user_domain('mathex','nexgeneral')
def mix(ng,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
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

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _floatclamp(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@user_domain('mathex')
def clamp(ng,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    _reusedata:str='',
    ) -> sFlo:
    """Clamp value between min an max."""
    return _floatclamp(ng,'MINMAX',v,a,b, _reusedata=_reusedata,)

@user_domain('mathex')
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
    val1:sFlo|sInt|sBoo|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|float|int|Vector=None,
    val4:sFlo|sInt|sBoo|float|int|Vector=None,
    val5:sFlo|sInt|sBoo|float|int|Vector=None,
    val6:sFlo|sInt|sBoo|float|int|Vector=None,
    _reusedata:str='',
    ) -> sFlo|sVec:
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

    # Need to choose socket depending on node data_type (hidden sockets)
    outidx = None
    indexes = None
    match data_type:
        case 'FLOAT':
            outidx = 0
            indexes = (0,1,2,3,4,5)
        case 'FLOAT_VECTOR':
            outidx = 1
            indexes = (6,7,8,9,10,11)
            args = convert_args(*args, toVector=True,)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ArgsTypeError for _maprange(). Recieved unsupported type '{type(val).__name__}'")

    return node.outputs[outidx]

@user_domain('mathex','nexgeneral')
def maplin(ng,
    val:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Map Range.\nRemap a value from a fiven A,B range to a X,Y range."""
    if anytype(val,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,'FLOAT_VECTOR','LINEAR',val,a,b,x,y, _reusedata=_reusedata,)
    return _maprange(ng,'FLOAT','LINEAR',val,a,b,x,y, _reusedata=_reusedata,)

@user_domain('mathex','nexgeneral')
def mapstep(ng,
    val:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    step:sFlo|sInt|sBoo|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Map Range (Stepped).\nRemap a value from a fiven A,B range to a X,Y range with step."""
    if anytype(val,a,b,x,y,step,types=(sVec,Vector,),):
        return _maprange(ng,'FLOAT_VECTOR','STEPPED',val,a,b,x,y,step, _reusedata=_reusedata,)
    return _maprange(ng,'FLOAT','STEPPED',val,a,b,x,y,step, _reusedata=_reusedata,)

@user_domain('mathex','nexgeneral')
def mapsmooth(ng,
    val:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Map Range (Smooth).\nRemap a value from a fiven A,B range to a X,Y range."""
    if anytype(val,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,'FLOAT_VECTOR','SMOOTHSTEP',val,a,b,x,y, _reusedata=_reusedata,)
    return _maprange(ng,'FLOAT','SMOOTHSTEP',val,a,b,x,y, _reusedata=_reusedata,)

@user_domain('mathex','nexgeneral')
def mapsmoother(ng,
    val:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    _reusedata:str='',
    ) -> sFlo|sVec:
    """Map Range (Smoother).\nRemap a value from a fiven A,B range to a X,Y range."""
    if anytype(val,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,'FLOAT_VECTOR','SMOOTHERSTEP',val,a,b,x,y, _reusedata=_reusedata,)
    return _maprange(ng,'FLOAT','SMOOTHERSTEP',val,a,b,x,y, _reusedata=_reusedata,)

@user_domain('nexgeneral')
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

@user_domain('nexgeneral')
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
