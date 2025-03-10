# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this module gather all kind of math function for sockets.
#  when executing these functions, it will create and link new nodes automatically, from sockets to sockets.
#  - Reusenode parameter:
#    The 'reusenode' positional parameter is to be assigned a unique tag corresponding to the node used 
#    and their recognizable socket id, if you wish the nodetree to stay stable on multiple execution while updating constant values.


import bpy 

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

    assert tag!='', "Tag must be valid"
    userfuncs = [f for f in TAGGED if (tag in f.tags)]

    #return names only?
    if (get_names):
        return [f.__name__ for f in userfuncs]

    # If a default node group argument is provided, use functools.partial to bind it
    if (partialdefaults is not None):
        userfuncs = [partial(f, *partialdefaults,) for f in userfuncs]

    return userfuncs

def generate_documentation(tag=''):
    """generate doc about function subset for user, we are collecting function name and arguments"""

    r = {}
    for f in get_nodesetter_functions(tag=tag):
        
        #collect args of this function
        fargs = list(f.__code__.co_varnames[:f.__code__.co_argcount])
        
        #remove strictly internal args from documentation
        if ('ng' in fargs):
            fargs.remove('ng')
        if ('reusenode' in fargs):
            fargs.remove('reusenode')
        
        # support for *args parameters?
        if (f.__code__.co_flags & 0x04):  # Function has *args
            fargs.append(f'a, b, c,.. ')
        
        #generate documentation function strings
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
                                                                                            

def generalfloatmath(ng, reusenode:str,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    ) -> sFlo:
    """generic operation for adding a float math node and linking. (also support clamp node).
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

        #floatmath also support clamp method. These two nodes are highly similar.
        if operation_type.startswith('CLAMP.'):
            node = ng.nodes.new('ShaderNodeClamp')
            clamp_type = operation_type.replace('CLAMP.','')
            node.clamp_type = clamp_type
        else:
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalfloatmath({operation_type}) recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

def generalvecmath(ng, reusenode:str,
    operation_type:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalvecmath('{operation_type}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[outidx]

def generalverotate(ng, reusenode:str,
    rotation_type:str,
    invert:bool,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    vX:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    fA:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    vE:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    """Generic operation for adding a vector rotation node and linking.
    If 'reusenode' is provided, update the existing node; otherwise, create a new one."""

    node = None
    args = (vA,vC,vX,fA,vE)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0, 200)
        node = ng.nodes.new('ShaderNodeVectorRotate')
        node.rotation_type = rotation_type
        node.invert = invert
        node.location = location
        ng.nodes.active = node
    
        needs_linking = True
        if (reusenode):
            node.name = node.label = reusenode

    #need to define different input/output depending on operation..
    for i,val in enumerate(args):
        match val:

            case sVec() | sFlo() | sInt() | sBoo():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector():
                if (i==3):
                    raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalverotate('{rotation_type}') recieved unsupported type 'Vector' for angle parameter. Expected a Float compatible type.")
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float() | int():
                if (i==3):
                    if node.inputs[i].default_value != val:
                        node.inputs[i].default_value = val
                    continue
                val = Vector((val,val,val))
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalverotate('{rotation_type}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

def generalmix(ng, reusenode:str,
    data_type:str,
    factor:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sFlo|sVec:
    """generic operation for adding a mix node and linking.
    if 'reusenode' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (factor, val1, val2,)
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalmix('{data_type}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[outidx]

def generalvecfloatmath(ng, reusenode:str,
    operation_type:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    fB:sFlo|sInt|sBoo|float|int=None,
    fC:sFlo|sInt|sBoo|float|int=None,
    ) -> sVec:
    """Apply regular float math to each element of the vector."""

    floats = separate_xyz(ng, f'{reusenode}|in.sep', vA)
    sepnode = floats[0].node
    
    newfloats = set()
    for i,fE in enumerate(floats):
        ng.nodes.active = sepnode
        fN = generalfloatmath(ng,  f'{reusenode}|in{i}', operation_type, fE,fB,fC,)
        newfloats.add(fN)
        continue

    rvec = combine_xyz(ng, f'{reusenode}|in.comb', *newfloats)
    frame_nodes(ng, floats[0].node, rvec.node,
        label=f'{reusenode}|ewise',
        )
    return rvec

def generalmaprange(ng, reusenode:str,
    data_type:str,
    interpolation_type:str,
    value:sFlo|sInt|sBoo|float|int|Vector=None,
    from_min:sFlo|sInt|sBoo|float|int|Vector=None,
    from_max:sFlo|sInt|sBoo|float|int|Vector=None,
    to_min:sFlo|sInt|sBoo|float|int|Vector=None,
    to_max:sFlo|sInt|sBoo|float|int|Vector=None,
    steps:sFlo|sInt|sBoo|float|int|Vector=None,
    ) -> sFlo|sVec:
    """generic operation for adding a remap node and linking"""

    node = None
    args = (value, from_min, from_max, to_min, to_max, steps,)
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalmaprange('{data_type}','{interpolation_type}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[outidx]

def generalminmax(ng, reusenode:str,
    operation_type:str,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    """generic operation to cover the max/min operation between a range or given float compatible itterable"""

    assert operation_type in {'min','max'}
    fullopname = 'MINIMUM' if operation_type=='min' else 'MAXIMUM'
    
    if len(floats) in {0,1}:
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() needs two Params or more.") 
    for o in floats:
        if type(o) not in {sFlo, sInt, sBoo, float, int}:
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() recieved unsupported type '{type(o).__name__}'.") 

    to_frame = []

    a = floats[0]
    for i,o in enumerate(floats):
        if (i==0):
            continue
        b = o
        if (reusenode):
              new = generalfloatmath(ng,f"{reusenode}|{i}", fullopname, a,b)
        else: new = generalfloatmath(ng,'', fullopname, a,b)
        a = new
        to_frame.append(new.node)
        continue

    frame_nodes(ng, *to_frame,
        label=reusenode if (reusenode) else f"{operation_type}(*floats)",
        )
    return new

def generalcompare(ng, reusenode:str,
    data_type:str,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    epsilon:sFlo|sInt|sBoo|float|int=None,
    ) -> sBoo:
    """generic operation for comparison operation and linking.
    if 'reusenode' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    args = (val1, val2, epsilon,)
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('FunctionNodeCompare')
        node.data_type = data_type
        node.operation = operation
        node.mode = 'ELEMENT' #for vector data_type
        node.inputs[12].default_value = 0 #epsilon always set on 0
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    indexes = None
    match data_type:
        case 'FLOAT':
            indexes = (0,1,12)
        case 'VECTOR':
            indexes = (4,5,12)
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalcompare('{data_type}','{operation}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

def generalboolmath(ng, reusenode:str,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sBoo:
    """generic operation for BooleanMath.
    if 'reusenode' is passed the function shall only but update values of existing node, not adding new nodes"""

    node = None
    needs_linking = False

    if (reusenode):
        node = ng.nodes.get(reusenode)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('FunctionNodeBooleanMath')
        node.operation = operation
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (reusenode):
            node.name = node.label = reusenode #Tag the node, in order to avoid unessessary build

    for i,val in enumerate((val1,val2)):
        match val:

            case sFlo() | sInt() | sBoo() | sVec():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int() | bool() | Vector():
                if type(val) is not bool:
                    val = bool(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalboolmath('{operation}') recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Addition.\nEquivalent to the '+' symbol.")
def add(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'ADD',a,b)
    return generalfloatmath(ng,reusenode, 'ADD',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Subtraction.\nEquivalent to the '-' symbol.")
def sub(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'SUBTRACT',a,b)
    return generalfloatmath(ng,reusenode, 'SUBTRACT',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Multiplications.\nEquivalent to the '*' symbol.")
def mult(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'MULTIPLY',a,b)
    return generalfloatmath(ng,reusenode, 'MULTIPLY',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Division.\nEquivalent to the '/' symbol.")
def div(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'DIVIDE',a,b)
    return generalfloatmath(ng,reusenode, 'DIVIDE',a,b)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="A Power N.\nEquivalent to the 'A**N' or '²' symbol.")
def pow(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,Vector),):
        if not alltypes(n,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function pow(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")
        return generalvecfloatmath(ng,reusenode, 'POWER',a,n)
    return generalfloatmath(ng,reusenode, 'POWER',a,n)

@user_domain('mathex','nexcode')
@user_doc(mathex="Logarithm A base N.")
@user_doc(nexcode="Logarithm A base N.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
def log(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,n,types=(float,int,)):
    #     return math.log(a,n)
    if anytype(a,types=(sVec,Vector),):
        if not alltypes(n,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function log(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")
        return generalvecfloatmath(ng,reusenode, 'LOGARITHM',a,n)
    return generalfloatmath(ng,reusenode, 'LOGARITHM',a,n)

@user_domain('mathex','nexcode')
@user_doc(mathex="Square Root of A.")
@user_doc(nexcode="Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sqrt(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sqrt(a)
    if anytype(a,types=(sVec,Vector),):
        return generalvecfloatmath(ng,reusenode, 'SQRT',a)
    return generalfloatmath(ng,reusenode, 'SQRT',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="Inverse Square Root of A.")
@user_doc(nexcode="Inverse Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
def invsqrt(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,Vector),):
        return generalvecfloatmath(ng,reusenode, 'INVERSE_SQRT',a)
    return generalfloatmath(ng,reusenode, 'INVERSE_SQRT',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="A Root N.\nEquivalent to doing 'A**(1/N)'.")
@user_doc(nexcode="A Root N.\nEquivalent to doing 'A**(1/N)'.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
def nroot(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:

    if anytype(a,types=(sVec,Vector),):
        if not alltypes(n,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function nroot(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")

    if (reusenode): #this function is created multiple nodes so we need multiple tag
          _x = div(ng,f"{reusenode}|inner", 1,n)
    else: _x = div(ng,'', 1,n,)

    _r = pow(ng,reusenode, a,_x)
    frame_nodes(ng, _x.node, _r.node.parent if _r.node.parent else _r.node,
        label=reusenode if (reusenode) else 'nRoot',
        )
    return _r

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Absolute of A.")
def abs(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'ABSOLUTE',a)
    return generalfloatmath(ng,reusenode, 'ABSOLUTE',a)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Negate the value of A.\nEquivalent to the symbol '-x.'")
def neg(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    _r = sub(ng,reusenode, 0,a)
    frame_nodes(ng, _r.node,
        label=reusenode if (reusenode) else 'Negate',
        )
    return _r

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Round a Float value.\nex: 1.49 will become 1\n1.51 will become 2.")
def round(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'ROUND',a)
    return generalfloatmath(ng,reusenode, 'ROUND',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="Floor a Float value.\nex: 1.51 will become 1\n-1.51 will become -2.")
@user_doc(nexcode="Floor a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.51 will become 1\n-1.51 will become 2.")
def floor(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.floor(a)
    if anytype(a,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'FLOOR',a)
    return generalfloatmath(ng,reusenode, 'FLOOR',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="Ceil a Float value.\nex: 1.01 will become 2\n-1.99 will become -1.")
@user_doc(nexcode="Ceil a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.01 will become 2\n-1.99 will become 1.")
def ceil(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.ceil(a)
    if anytype(a,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'CEIL',a)
    return generalfloatmath(ng,reusenode, 'CEIL',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="Trunc a Float value.\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_doc(nexcode="Trunc a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.99 will become 1\n-1.99 will become -1.")
def trunc(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.trunc(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'TRUNC',a)
    return generalfloatmath(ng,reusenode, 'TRUNC',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="Fraction.\nThe fraction part of A.")
@user_doc(nexcode="Fraction.\nThe fraction part of A.\nSupports SocketFloat and entry-wise SocketVector.")
def frac(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'FRACTION',a)
    return generalfloatmath(ng,reusenode, 'FRACT',a)

#covered in nexcode via python dunder overload
@user_domain('mathex')
@user_doc(mathex="Modulo.\nEquivalent to the '%' symbol.")
def mod(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec,),):
        return generalvecmath(ng,reusenode, 'MODULO',a,b)
    return generalfloatmath(ng,reusenode, 'MODULO',a,b)

#not covered in Nex.. user can do floor(A%B)
@user_domain('mathex')
@user_doc(mathex="Floored Modulo.")
def floormod(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,reusenode, 'FLOORED_MODULO',a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Wrapping.\nWrap a value V to Range A B.")
@user_doc(nexcode="Wrapping.\nWrap a value V to Range A B.\nSupports SocketFloat and entry-wise SocketVector.")
def wrap(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,types=(sVec,Vector,),):
        return generalvecmath(ng,reusenode, 'WRAP',v,a,b)
    return generalfloatmath(ng,reusenode, 'WRAP',v,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Snapping.\nSnap a value V to the nearest increament I.")
@user_doc(nexcode="Snapping.\nSnap a value V to the nearest increament I.\nSupports SocketFloat and SocketVector.")
def snap(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    i:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,i,types=(sVec,Vector,),):
        return generalvecmath(ng,reusenode, 'SNAP',v,i)
    return generalfloatmath(ng,reusenode, 'SNAP',v,i)

@user_domain('mathex','nexcode')
@user_doc(mathex="PingPong.\nWrap a value and every other cycles at cycle Scale.")
@user_doc(nexcode="PingPong.\nWrap a value and every other cycles at cycle Scale.\nSupports SocketFloat and entry-wise SocketVector if scale is float compatible.")
def pingpong(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    scale:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec,Vector),):
        if not alltypes(scale,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function pingpong(). Second argument must be a float compatible type. Recieved '{type(scale).__name__}'.")
        return generalvecfloatmath(ng,reusenode, 'PINGPONG',v,scale)
    return generalfloatmath(ng,reusenode, 'PINGPONG',v,scale)

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
    frame_nodes(ng, _x.node, _r.node,
        label=reusenode if (reusenode) else 'FloorDiv',
        )
    return _r

@user_domain('mathex','nexcode')
@user_doc(mathex="The Sine of A.")
@user_doc(nexcode="The Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sin(a)
    if anytype(a,types=(sVec,Vector,),):
        return generalvecmath(ng,reusenode, 'SINE',a)
    return generalfloatmath(ng,reusenode, 'SINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Cosine of A.")
@user_doc(nexcode="The Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def cos(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.cos(a)
    if anytype(a,types=(sVec,Vector,),):
        return generalvecmath(ng,reusenode, 'COSINE',a)
    return generalfloatmath(ng,reusenode, 'COSINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Tangent of A.")
@user_doc(nexcode="The Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def tan(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.tan(a)
    if anytype(a,types=(sVec,Vector,),):
        return generalvecmath(ng,reusenode, 'TANGENT',a)
    return generalfloatmath(ng,reusenode, 'TANGENT',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Arcsine of A.")
@user_doc(nexcode="The Arcsine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def asin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.asin(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'ARCSINE',a)
    return generalfloatmath(ng,reusenode, 'ARCSINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Arccosine of A.")
@user_doc(nexcode="The Arccosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def acos(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.acos(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'ARCCOSINE',a)
    return generalfloatmath(ng,reusenode, 'ARCCOSINE',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Arctangent of A.")
@user_doc(nexcode="The Arctangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def atan(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.atan(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'ARCTANGENT',a)
    return generalfloatmath(ng,reusenode, 'ARCTANGENT',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Hyperbolic Sine of A.")
@user_doc(nexcode="The Hyperbolic Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sinh(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sinh(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'SINH',a)
    return generalfloatmath(ng,reusenode, 'SINH',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Hyperbolic Cosine of A.")
@user_doc(nexcode="The Hyperbolic Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def cosh(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.cosh(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'COSH',a)
    return generalfloatmath(ng,reusenode, 'COSH',a)

@user_domain('mathex','nexcode')
@user_doc(mathex="The Hyperbolic Tangent of A.")
@user_doc(nexcode="The Hyperbolic Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def tanh(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.tanh(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'TANH',a)
    return generalfloatmath(ng,reusenode, 'TANH',a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Degrees to Radians.")
def rad(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.radians(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'RADIANS',a)
    return generalfloatmath(ng,reusenode, 'RADIANS',a)

#same as above, just different user fct name.
@user_domain('nexcode')
@user_doc(nexcode="Convert a value from Degrees to Radians.\nSupports SocketFloat and entry-wise SocketVector.")
def radians(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return rad(ng,reusenode,a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Radians to Degrees.")
def deg(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.degrees(a)
    if anytype(a,types=(sVec,),):
        return generalvecfloatmath(ng,reusenode, 'DEGREES',a)
    return generalfloatmath(ng,reusenode, 'DEGREES',a)

#same as above, just different user fct name.
@user_domain('nexcode')
@user_doc(nexcode="Convert a value from Radians to Degrees.\nSupports SocketFloat and entry-wise SocketVector.")
def degrees(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return deg(ng,reusenode,a)

@user_domain('nexcode')
@user_doc(nexcode="Vector Cross Product.\nThe cross product between vector A an B.")
def cross(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'CROSS_PRODUCT',vA,vB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Dot Product.\nA dot B.")
def dot(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'DOT_PRODUCT',vA,vB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Projection.\nProject A onto B.")
def project(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'PROJECT',vA,vB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Faceforward.\nFaceforward operation between a given vector, an incident and a reference.")
def faceforward(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vI:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vR:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'FACEFORWARD',vA,vI,vR)

@user_domain('nexcode')
@user_doc(nexcode="Vector Reflection.\nReflect A onto B.")
def reflect(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'PROJECT',vA,vB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Distance.\nThe distance between location A & B.")
def distance(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,reusenode, 'DISTANCE',vA,vB)

@user_domain('nexcode')
@user_doc(nexcode="Vector Normalization.\nNormalize the values of a vector A to fit a 0-1 range.")
def normalize(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,reusenode, 'NORMALIZE',vA)

#covered in nexcode with NexVec.length
def length(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,reusenode, 'LENGTH',vA)

@user_domain('nexcode')
@user_doc(nexcode="Separate a SocketVector into 3 SocketFloat.\n\nTip: you can use python slicing notations 'myX, myY, myZ = vA' to do that instead.")
def separate_xyz(ng, reusenode:str,
    vA:sVec,
    ) -> tuple:

    if (type(vA) is not sVec):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_xyz() recieved unsupported type '{type(vA).__name__}'")

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
        link_sockets(vA, node.inputs[0])

    return tuple(node.outputs)

@user_domain('nexcode')
@user_doc(nexcode="Combine 3 SocketFloat (or python values) into a SocketVector.")
def combine_xyz(ng, reusenode:str,
    fX:sFlo|sInt|sBoo|float|int,
    fY:sFlo|sInt|sBoo|float|int,
    fZ:sFlo|sInt|sBoo|float|int,
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

    for i, val in enumerate((fX, fY, fZ)):
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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function combine_xyz() recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

@user_domain('nexcode')
@user_doc(nexcode="Vector Rotate (Euler).\nRotate a given Vector A with euler angle radians E, at optional center C.")
def roteuler(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vE:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    return generalverotate(ng, reusenode, 'EULER_XYZ',False, vA,vC,None,None,vE,)

@user_domain('nexcode')
@user_doc(nexcode="Vector Rotate (Euler).\nRotate a given Vector A from defined axis X & angle radians F, at optional center C.")
def rotaxis(ng, reusenode:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vX:sFlo|sInt|sBoo|sVec|float|int|Vector,
    fA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    return generalverotate(ng, reusenode, 'AXIS_ANGLE',False, vA,vC,vX,fA,None,)

@user_domain('mathex','nexcode')
@user_doc(mathex="Minimum.\nGet the absolute minimal value across all passed arguments.")
@user_doc(nexcode="Minimum.\nGet the absolute minimal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
def min(ng, reusenode:str,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalminmax(ng,reusenode, 'min',*floats)

@user_domain('mathex','nexcode')
@user_doc(mathex="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexcode="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
def smin(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,reusenode, 'SMOOTH_MIN',a,b,dist)

@user_domain('mathex','nexcode')
@user_doc(mathex="Maximum.\nGet the absolute maximal value across all passed arguments.")
@user_doc(nexcode="Maximum.\nGet the absolute maximal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
def max(ng, reusenode:str,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalminmax(ng,reusenode, 'max',*floats)

@user_domain('mathex','nexcode')
@user_doc(mathex="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexcode="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
def smax(ng, reusenode:str,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,reusenode, 'SMOOTH_MAX',a,b,dist)

@user_domain('mathex','nexcode')
@user_doc(mathex="Mix.\nLinear Interpolation between value A and B from given factor F.")
@user_doc(nexcode="Mix.\nLinear Interpolation between value A and B from given factor F.\nSupports SocketFloat and SocketVector.")
def lerp(ng, reusenode:str,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(f,a,b,types=(sVec,Vector,),):
        return generalmix(ng,reusenode, 'VECTOR',f,a,b)
    return generalmix(ng,reusenode, 'FLOAT',f,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Alternative notation to lerp() function.")
@user_doc(nexcode="Alternative notation to lerp() function.")
def mix(ng, reusenode:str,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return lerp(ng,reusenode, f,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Clamping.\nClamp a value a between min A an max B.")
@user_doc(nexcode="Clamping.\nClamp a value a between min A an max B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
def clamp(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec,Vector),):
        if not alltypes(a,b,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function clamp(). Second or Third argument must be float compatible types. Recieved '{type(a).__name__}' & '{type(b).__name__}'.")
        return generalvecfloatmath(ng,reusenode, 'CLAMP.MINMAX',v,a,b)
    return generalfloatmath(ng,reusenode, 'CLAMP.MINMAX',v,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="AutoClamping.\nClamp a value a between auto-defined min/max A & B.")
@user_doc(nexcode="AutoClamping.\nClamp a value a between auto-defined min/max A & B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
def clampauto(ng, reusenode:str,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec,Vector),):
        if not alltypes(a,b,types=(sFlo,sInt,sBoo,float,int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function clamp(). Second or Third argument must be float compatible types. Recieved '{type(a).__name__}' & '{type(b).__name__}'.")
        return generalvecfloatmath(ng,reusenode, 'CLAMP.RANGE',v,a,b)
    return generalfloatmath(ng,reusenode, 'CLAMP.RANGE',v,a,b)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range.\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range.\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapl(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return generalmaprange(ng,reusenode, 'FLOAT_VECTOR','LINEAR',v,a,b,x,y)
    return generalmaprange(ng,reusenode, 'FLOAT','LINEAR',v,a,b,x,y)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.")
@user_doc(nexcode="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\nSupports SocketFloat and SocketVector.")
def mapst(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    step:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,step,types=(sVec,Vector,),):
        return generalmaprange(ng,reusenode, 'FLOAT_VECTOR','STEPPED',v,a,b,x,y,step)
    return generalmaprange(ng,reusenode, 'FLOAT','STEPPED',v,a,b,x,y,step)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapsmo(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return generalmaprange(ng,reusenode, 'FLOAT_VECTOR','SMOOTHSTEP',v,a,b,x,y)
    return generalmaprange(ng,reusenode, 'FLOAT','SMOOTHSTEP',v,a,b,x,y)

@user_domain('mathex','nexcode')
@user_doc(mathex="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexcode="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapsmoo(ng, reusenode:str,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec,Vector,),):
        return generalmaprange(ng,reusenode, 'FLOAT_VECTOR','SMOOTHERSTEP',v,a,b,x,y)
    return generalmaprange(ng,reusenode, 'FLOAT','SMOOTHERSTEP',v,a,b,x,y)

@user_domain('nexcode')
@user_doc(nexcode="Position Attribute.\nGet the GeometryNode 'Position' SocketVector input attribute.")
def getp(ng, reusenode:str,
    ) -> sVec:
    node = ng.nodes.get(reusenode)
    if (node is None):
        node = ng.nodes.new('GeometryNodeInputPosition')
        node.name = node.label = reusenode
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*1
    return node.outputs[0]

@user_domain('nexcode')
@user_doc(nexcode="Normal Attribute.\nGet the GeometryNode 'Normal' SocketVector input attribute.")
def getn(ng, reusenode:str,
    ) -> sVec:
    node = ng.nodes.get(reusenode)
    if (node is None):
        node = ng.nodes.new('GeometryNodeInputNormal')
        node.name = node.label = reusenode
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*2
    return node.outputs[0]

# TODO more attr input
# def getid() -> Int
# def getindex() -> Int
# def getnamedattr(name) -> Dynamic

#covered in nexcode via python dunder overload
def iseq(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo,bool),):
        return generalboolmath(ng,reusenode, 'XNOR', a,b)
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','EQUAL', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','EQUAL', a,b,None)

#covered in nexcode via python dunder overload
def isnoteq(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo,bool),):
        return generalboolmath(ng,reusenode, 'XOR', a,b)
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','NOT_EQUAL', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','NOT_EQUAL', a,b,None)

#covered in nexcode via python dunder overload
def isless(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','LESS_THAN', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','LESS_THAN', a,b,None)

#covered in nexcode via python dunder overload
def islesseq(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','LESS_EQUAL', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','LESS_EQUAL', a,b,None)

#covered in nexcode via python dunder overload
def isgreater(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','GREATER_THAN', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','GREATER_THAN', a,b,None)

#covered in nexcode via python dunder overload
def isgreatereq(ng, reusenode:str,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec,Vector,),):
        return generalcompare(ng,reusenode, 'VECTOR','GREATER_EQUAL', a,b,None)
    return generalcompare(ng,reusenode, 'FLOAT','GREATER_EQUAL', a,b,None)

#TODO 
#def allequal(*values)
#def allbetween(min, max, *betweens)
#TODO what about epsilon? problem is that epsilon is not supported for all operaiton type
#def almosteq(a,b,epsilon)