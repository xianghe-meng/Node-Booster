# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this module gather all kind of math function for sockets
#  when executing these functions, it will create and link new nodes automatically, from sockets to sockets.
#  the 'reusenode' parameter will only update potential default values of existing nodes.


import bpy 

import math
from functools import partial
from mathutils import Vector

from ..utils.node_utils import link_sockets, frame_nodes
from ..utils.fct_utils import alltypes, anytype

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


def convert_args(*args, toVector=False,) -> tuple:
    if (toVector):
        return [Vector((a,a,a)) if type(a) in (int,bool,float) else a for a in args]
    return None
    
def user_domain(*tags):
    """decorator to easily retrieve functions names by tag on an orderly manner at runtime"""

    def decorator(fct):
        """just mark function with tag"""
        
        TAGGED.append(fct)
        fct.tags = tags
        return fct

    return decorator

def user_doc(**kwarks):
    """decorator to easily define user description depending on domain tag"""

    def decorator(fct):
        """just mark function with tag"""
        d = getattr(fct,'_userdoc',None)
        if (d is None):
            d = fct._userdoc = {}
        for k,v in kwarks.items():
            d[k] = v
        return fct

    return decorator

def get_nodesetter_functions(tag='', get_names=False, partialdefaults:tuple=None,):
    """get all functions and their names, depending on function types
    optionally, pass the default ng. The 'reusenode' functionality of the functions will be disabled"""

    if (tag==''):
          filtered_functions = TAGGED[:]
    else: filtered_functions = [f for f in TAGGED if (tag in f.tags)]
    
    if (get_names):
        return [f.__name__ for f in filtered_functions]

    # If a default node group argument is provided, use functools.partial to bind it
    if (partialdefaults is not None):
        filtered_functions = [partial(f, *partialdefaults,) for f in filtered_functions]

    return filtered_functions

def generate_documentation(tag=''):
    """generate doc about function subset for user, we are collecting function name and arguments"""

    r = {}
    for f in get_nodesetter_functions(tag=tag):

        fargs = list(f.__code__.co_varnames[:f.__code__.co_argcount])
        if ('ng' in fargs):
            fargs.remove('ng')
        if ('reusenode' in fargs):
            fargs.remove('reusenode')
        fstr = f'{f.__name__}({", ".join(fargs)})'

        doc = 'Doc here...'
        if hasattr(f,'_userdoc'):
            if (tag in f._userdoc):
                doc = f._userdoc[tag]

        r[f.__name__] = {'repr':fstr, 'doc':doc,}
        continue

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
                                                                                            

def _floatmath(ng, reusenode:str,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    ) -> sFlo:
    """generic operation for adding a float math node and linking.
    if 'reusenode' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

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
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build
    
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

def _vecmath(ng, reusenode:str,
    operation_type:str,
    val1:sFlo|sInt|sBoo|sVec|Vector|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|Vector|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|sVec|Vector|float|int|Vector=None,
    ) -> sVec:
    """Generic operation for adding a vector math node and linking.
    If 'reusenode' is provided, update the existing node; otherwise, create a new one."""

    node = None
    args = (val1, val2, val3)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

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
        if (reusenode):
            node.name = node.label = reusenode

    #need to define different input/output depending on operation..
    outidx = 0
    indexes = (0,1,2)
    match operation_type:
        case 'DOT_PRODUCT'|'LENGTH'|'DISTANCE':
            outidx = 1
            
    for i,val in zip(indexes,args):
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

    return node.outputs[outidx]

def _mix(ng, reusenode:str,
    data_type:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sFlo|sVec:
    """generic operation for adding a mix node and linking.
    if 'reusenode' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

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
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build

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

def _floatclamp(ng, reusenode:str,
    clamp_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    ) -> sFlo:
    """generic operation for adding a mix node and linking"""

    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

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
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build

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

def _maprange(ng, reusenode:str,
    data_type:str,
    interpolation_type:str,
    val1:sFlo|sInt|sBoo|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|float|int|Vector=None,
    val4:sFlo|sInt|sBoo|float|int|Vector=None,
    val5:sFlo|sInt|sBoo|float|int|Vector=None,
    val6:sFlo|sInt|sBoo|float|int|Vector=None,
    ) -> sFlo|sVec:
    """generic operation for adding a remap node and linking"""

    node = None
    args = (val1, val2, val3, val4, val5, val6,)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

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
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build

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

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Addition.\nEquivalent to the '+' symbol.")
def add(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,reusenode, 'ADD',a,b)
    return _floatmath(ng,reusenode, 'ADD',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Subtraction.\nEquivalent to the '-' symbol.")
def sub(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,reusenode, 'SUBTRACT',a,b)
    return _floatmath(ng,reusenode, 'SUBTRACT',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Multiplications.\nEquivalent to the '*' symbol.")
def mult(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,reusenode, 'MULTIPLY',a,b)
    return _floatmath(ng,reusenode, 'MULTIPLY',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Division.\nEquivalent to the '/' symbol.")
def div(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,reusenode, 'DIVIDE',a,b)
    return _floatmath(ng,reusenode, 'DIVIDE',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="A Power n.\nEquivalent to the 'a**n' and '²' symbol.")
def pow(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,n,types=(sVec,),):
        return _vecmath(ng,reusenode, 'POWER',a,n)
    return _floatmath(ng,reusenode, 'POWER',a,n)

@user_domain('mathex')
@user_doc(mathex="Logarithm A base B.")
def log(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'LOGARITHM',a,b)

@user_domain('mathex')
@user_doc(mathex="Square Root of A.")
def sqrt(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'SQRT',a)

@user_domain('mathex')
@user_doc(mathex="1/ Square Root of A.")
def invsqrt(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'INVERSE_SQRT',a)

@user_domain('mathex')
@user_doc(mathex="A Root N. Equivalent to doing 'a**(1/n).'")
def nroot(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    
    if (reusenode): #this function is created multiple nodes so we need multiple tag
          _x = div(ng,f"{reusenode}|inner", 1,n)
    else: _x = div(ng,'', 1,n,)

    _r = pow(ng,reusenode, a,_x)
    frame_nodes(ng, _x.node, _r.node, label='nRoot',)
    return _r

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Absolute of A.")
def abs(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,),):
        return _vecmath(ng,reusenode, 'ABSOLUTE',a)
    return _floatmath(ng,reusenode, 'ABSOLUTE',a)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Negate the value of A.\nEquivalent to the symbol '-x.'")
def neg(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    _r = sub(ng,reusenode, 0,a)
    frame_nodes(ng, _r.node, label='Negate',)
    return _r

@user_domain('mathex')
@user_doc(mathex="Minimum between A & B.")
def min(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'MINIMUM',a,b)

@user_domain('mathex')
@user_doc(mathex="Minimum between A & B considering a smoothing distance.")
def smin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'SMOOTH_MIN',a,b,dist)

@user_domain('mathex')
@user_doc(mathex="Maximum between A & B.")
def max(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'MAXIMUM',a,b)

@user_domain('mathex')
@user_doc(mathex="Maximum between A & B considering a smoothing distance.")
def smax(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'SMOOTH_MAX',a,b,dist)

#covered in nexcode with NexFloat.round()
@user_domain('mathex')
@user_doc(mathex="Round a Float value.")
def round(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'ROUND',a)

#covered in nexcode with NexFloat.floor()
@user_domain('mathex')
@user_doc(mathex="Floor a Float value.")
def floor(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,),):
        return _vecmath(ng,reusenode, 'FLOOR',a)
    return _floatmath(ng,reusenode, 'FLOOR',a)

#covered in nexcode with NexFloat.ceil()
@user_domain('mathex')
@user_doc(mathex="Ceil a Float value.")
def ceil(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'CEIL',a)

#covered in nexcode with NexFloat.trunc()
@user_domain('mathex')
@user_doc(mathex="Trunc a Float value.")
def trunc(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'TRUNC',a)

@user_domain('mathex')
@user_doc(mathex="Fraction.\nThe fraction part of A.")
def frac(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'FRACT',a)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Modulo.\nEquivalent to the '%' symbol.")
def mod(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return _vecmath(ng,reusenode, 'MODULO',a,b)
    return _floatmath(ng,reusenode, 'MODULO',a,b)

@user_domain('mathex')
@user_doc(mathex="Floored Modulo.")
def flooredmod(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'FLOORED_MODULO',a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Wrapping.\nWrap a value V to Range A B.")
@user_doc(nexcode="Wrapping.\nWrap a value V to Range A B.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def wrap(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    if anytype(v,a,b,types=(sVec,Vector,),):
        return _vecmath(ng,reusenode, 'WRAP',v,a,b)
    return _floatmath(ng,reusenode, 'WRAP',v,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Snapping.\nSnap a value V to the nearest increament I.")
@user_doc(nexcode="Snapping.\nSnap a value V to the nearest increament I.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def snap(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    i:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    if anytype(v,i,types=(sVec,Vector,),):
        return _vecmath(ng,reusenode, 'SNAP',v,i)
    return _floatmath(ng,reusenode, 'SNAP',v,i)

@user_domain('mathex')
@user_doc(mathex="PingPong. Wrap a value and every other cycles at cycle Scale.")
def pingpong(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int,
    scale:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'PINGPONG',v,scale)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Floor Division.\nEquivalent to the '//' symbol.")
def floordiv(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:

    if (reusenode): #this function is created multiple nodes so we need multiple tag
          _x = div(ng,f"{reusenode}|inner", a,b)
    else: _x = div(ng,'', a,b)

    _r = floor(ng,reusenode, _x)
    frame_nodes(ng, _x.node, _r.node, label='FloorDiv',)
    return _r

@user_domain('mathex','nexcode')
@user_doc(mathex="The Sine of A.")
@user_doc(nexcode="The Sine of A.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector.\nIf python types int, float are found 'math.sin' function will be used.")
def sin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    if alltypes(a,types=(float,int,)):
        return math.sin(a)
    elif anytype(a,types=(sVec,Vector,),):
        return _vecmath(ng,reusenode, 'SINE',a)
    return _floatmath(ng,reusenode, 'SINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Cosine of A.")
@user_doc(nexcode="The Cosine of A.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector.\nIf python types int, float are found 'math.cos' function will be used.")
def cos(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    if alltypes(a,types=(float,int,)):
        return math.cos(a)
    elif anytype(a,types=(sVec,Vector,),):
        return _vecmath(ng,reusenode, 'COSINE',a)
    return _floatmath(ng,reusenode, 'COSINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Tangent of A.")
@user_doc(nexcode="The Tangent of A.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector.\nIf python types int, float are found 'math.tan' function will be used.")
def tan(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    if alltypes(a,types=(float,int,)):
        return math.tan(a)
    elif anytype(a,types=(sVec,Vector,),):
        return _vecmath(ng,reusenode, 'TANGENT',a)
    return _floatmath(ng,reusenode, 'TANGENT',a)

@user_domain('mathex')
@user_doc(mathex="The Arcsine of A.")
def asin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'ARCSINE',a)

@user_domain('mathex')
@user_doc(mathex="The Arccosine of A.")
def acos(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'ARCCOSINE',a)

@user_domain('mathex')
@user_doc(mathex="The Arctangent of A.")
def atan(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'ARCTANGENT',a)

@user_domain('mathex')
@user_doc(mathex="The Hyperbolic Sine of A.")
def hsin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'SINH',a)

@user_domain('mathex')
@user_doc(mathex="The Hyperbolic Cosine of A.")
def hcos(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'COSH',a)

@user_domain('mathex')
@user_doc(mathex="The Hyperbolic Tangent of A.")
def htan(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'TANH',a)

#covered in nexcode with NexFloat.as_radians()
@user_domain('mathex')
@user_doc(mathex="Convert from Degrees to Radians.")
def rad(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'RADIANS',a)

#covered in nexcode with NexFloat.as_degrees()
@user_domain('mathex')
@user_doc(mathex="Convert from Radians to Degrees.")
def deg(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatmath(ng,reusenode, 'DEGREES',a)

@user_domain('nexcode')
@user_doc(nexcode="Vector Cross Product.\nThe cross product between vector A an B.")
def cross(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'CROSS_PRODUCT',vecA,vecB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Dot Product.\nA dot B.")
def dot(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'DOT_PRODUCT',vecA,vecB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Projection.\nProject A onto B.")
def project(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'PROJECT',vecA,vecB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Faceforward.\nFaceforward operation between a given vector, an incident and a reference.")
def faceforward(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecI:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecR:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'FACEFORWARD',vecA,vecI,vecR)

@user_domain('nexcode')
@user_doc(nexcode="Vector Reflection.\nReflect A onto B.")
def reflect(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'PROJECT',vecA,vecB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Distance.\nThe distance between location A & B.")
def distance(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vecB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return _vecmath(ng,reusenode, 'DISTANCE',vecA,vecB)

#covered in nexcode with NexVec.normalize()
def normalize(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return _vecmath(ng,reusenode, 'NORMALIZE',vecA)

#covered in nexcode with NexVec.length()
def length(ng, reusenode:str,
    vecA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return _vecmath(ng,reusenode, 'LENGTH',vecA)

@user_domain('nexcode')
@user_doc(nexcode="Separate a SocketVector into 3 SocketFloat.\nTip: you can use python slicing notations 'myX, myY, myZ = VecA' to do that instead.")
def separate_xyz(ng, reusenode:str,
    vecA:sVec,
    ) -> tuple:

    if (type(vecA) is not sVec):
        raise InvalidTypePassedToSocket(f"ArgsTypeError for separate_xyz(). Recieved unsupported type '{type(vecA).__name__}'")

    node = None
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('ShaderNodeSeparateXYZ')
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (reusenode):
            node.name = node.label = reusenode

    if (needs_linking):
        link_sockets(vecA, node.inputs[0])

    return tuple(node.outputs)

@user_domain('nexcode')
@user_doc(nexcode="Combine 3 SocketFloat (or python values) into a SocketVector.")
def combine_xyz(ng, reusenode:str,
    x:sFlo|sInt|sBoo|float|int,
    y:sFlo|sInt|sBoo|float|int,
    z:sFlo|sInt|sBoo|float|int,
    ) -> sVec:

    node = None
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

    if (node is None):
        last = ng.nodes.active
        if last:
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0, 200,)
        node = ng.nodes.new('ShaderNodeCombineXYZ')
        node.location = location
        ng.nodes.active = node
        needs_linking = True
        if (reusenode):
            node.name = node.label = reusenode

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

@user_domain('mathex','nexcode')
@user_doc(mathex="Mix.\nLinear Interpolation between value A and B from given factor F.")
@user_doc(nexcode="Mix.\nLinear Interpolation between value A and B from given factor F.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def lerp(ng, reusenode:str,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(f,a,b,types=(sVec,Vector,),):
        return _mix(ng,reusenode, 'VECTOR',f,a,b)
    return _mix(ng,reusenode, 'FLOAT',f,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Alternative notation to lerp() function.")
@user_doc(nexcode="Alternative notation to lerp() function.")
def mix(ng, reusenode:str,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return lerp(ng,reusenode, f,a,b)

@user_domain('mathex')
@user_doc(mathex="Clamping.\nClamp a value a between min a an max b.")
def clamp(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatclamp(ng,reusenode, 'MINMAX',v,a,b)

@user_domain('mathex')
@user_doc(mathex="AutoClamping.\nClamp a value a between auto-defined min/max a&b.")
def clampr(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return _floatclamp(ng,reusenode, 'RANGE',v,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range.\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range.\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def maplin(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,reusenode, 'FLOAT_VECTOR','LINEAR',v,a,b,x,y)
    return _maprange(ng,reusenode, 'FLOAT','LINEAR',v,a,b,x,y)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.")
@user_doc(nexcode="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def mapstep(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    step:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,step,types=(sVec,Vector,),):
        return _maprange(ng,reusenode, 'FLOAT_VECTOR','STEPPED',v,a,b,x,y,step)
    return _maprange(ng,reusenode, 'FLOAT','STEPPED',v,a,b,x,y,step)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def mapsmooth(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,reusenode, 'FLOAT_VECTOR','SMOOTHSTEP',v,a,b,x,y)
    return _maprange(ng,reusenode, 'FLOAT','SMOOTHSTEP',v,a,b,x,y)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat, SocketBool, SocketInt, SocketVector implicitly. Can also work with python int, float, and Vector types.")
def mapsmoother(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return _maprange(ng,reusenode, 'FLOAT_VECTOR','SMOOTHERSTEP',v,a,b,x,y)
    return _maprange(ng,reusenode, 'FLOAT','SMOOTHERSTEP',v,a,b,x,y)



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
