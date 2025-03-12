# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE this module gather all kind of math function between sockets and/or between sockets and python types.
#  When executing these functions, it will create and link new nodes automatically, from sockets to sockets and return another socket.

# NOTE The 'callhistory' internal parameter is an important functonality! Thanks to it, we can define a stable tag id for nodes generation,
#  this functionality let us re-execute the functions to update potential .default_value without rebuilding the entire nodetree nodes and links again.

import bpy 

from functools import partial
from mathutils import Vector, Matrix, Quaternion

from ..utils.node_utils import link_sockets, frame_nodes, create_constant_input
from ..utils.fct_utils import alltypes, anytype

sBoo = bpy.types.NodeSocketBool
sInt = bpy.types.NodeSocketInt
sFlo = bpy.types.NodeSocketFloat
sCol = bpy.types.NodeSocketColor
sMtx = bpy.types.NodeSocketMatrix
sQut = bpy.types.NodeSocketRotation
sVec = bpy.types.NodeSocketVector

#tell me why these type exist? what's the reason? Very annoying to support..
sVecXYZ = bpy.types.NodeSocketVectorXYZ
sVecT = bpy.types.NodeSocketVectorTranslation

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
    optionally, pass the default internal args."""

    assert tag!='', "Tag must be valid"

    if (tag=='all'):
          funcs = [f for f in TAGGED ]
    else: funcs = [f for f in TAGGED if (tag in f.tags)]

    #return names only?
    if (get_names):
        return [f.__name__ for f in funcs]

    # If a default node group argument is provided, use functools.partial to bind it
    if (partialdefaults is not None):
        funcs = [partial(f, *partialdefaults,) for f in funcs]

    return funcs

def generate_documentation(tag=''):
    """generate doc about function subset for user, we are collecting function name and arguments"""

    r = {}
    for f in get_nodesetter_functions(tag=tag):
        
        #collect args of this function
        fargs = list(f.__code__.co_varnames[:f.__code__.co_argcount])
        
        #remove strictly internal args from documentation
        if ('ng' in fargs):
            fargs.remove('ng')
        if ('callhistory' in fargs):
            fargs.remove('callhistory')
        
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

def get_unique_name(funcnameid, callhistory):
    """generate a unique name for a given function, depending on the call order.
    If a callhistory is not passed, the node unique name is set to None and the nodetree will not be stable,
    each execution will trigger a rebuilding of the entire tree"""

    if (callhistory is None):
        return None

    uniquetag = f"F{len(callhistory)}|{funcnameid}"
    callhistory.append(uniquetag)

    return uniquetag

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
                                                                                            

def generalfloatmath(ng, callhistory:list,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int=None,
    val2:sFlo|sInt|sBoo|float|int=None,
    val3:sFlo|sInt|sBoo|float|int=None,
    ) -> sFlo:
    """generic operation for adding a float math node and linking. (also support clamp node)."""

    uniquename = get_unique_name('FloatMath',callhistory)
    node = None
    args = (val1, val2, val3,)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    for i,val in enumerate(args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case float() | int():
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalfloatmath({operation_type}) recieved unsupported type '{type(val).__name__}'")

    return node.outputs[0]

def generalvecmath(ng, callhistory:list,
    operation_type:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val3:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    """Generic operation for adding a vector math node and linking."""

    uniquename = get_unique_name('VecMath',callhistory)
    node = None
    args = (val1, val2, val3)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename

    #need to define different input/output depending on operation..
    outidx = 0
    indexes = (0,1,2)
    match operation_type:
        case 'DOT_PRODUCT'|'LENGTH'|'DISTANCE':
            outidx = 1
            
    for i,val in zip(indexes,args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalverotate(ng, callhistory:list,
    rotation_type:str,
    invert:bool,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    vX:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    fA:sFlo|sInt|sBoo|sVec|float|int=None,
    vE:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    """Generic operation for adding a vector rotation node and linking."""

    uniquename = get_unique_name('VecRot',callhistory)
    node = None
    args = (vA,vC,vX,fA,vE)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename

    #need to define different input/output depending on operation..
    for i,val in enumerate(args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalmix(ng, callhistory:list,
    data_type:str,
    factor:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sFlo|sVec:
    """generic operation for adding a mix node and linking."""

    uniquename = get_unique_name('Mix',callhistory)
    node = None
    args = (factor, val1, val2,)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

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

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalvecfloatmath(ng, callhistory:list,
    operation_type:str,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    fB:sFlo|sInt|sBoo|float|int=None,
    fC:sFlo|sInt|sBoo|float|int=None,
    ) -> sVec:
    """Apply regular float math to each element of the vector."""

    floats = separate_xyz(ng, callhistory, vA)
    sepnode = floats[0].node
    
    newfloats = set()
    for i,fE in enumerate(floats):
        ng.nodes.active = sepnode
        fN = generalfloatmath(ng, callhistory, operation_type, fE,fB,fC,)
        newfloats.add(fN)
        continue

    rvec = combine_xyz(ng, callhistory, *newfloats)
    frame_nodes(ng, floats[0].node, rvec.node, label='Vec EntryWise FloatMath',)

    return rvec

def generalmaprange(ng, callhistory:list,
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

    uniquename = get_unique_name('MapRange',callhistory)

    node = None
    args = (value, from_min, from_max, to_min, to_max, steps,)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

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

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalminmax(ng, callhistory:list,
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
        new = generalfloatmath(ng,callhistory, fullopname, a,b)
        a = new
        to_frame.append(new.node)
        continue

    frame_nodes(ng, *to_frame, label='Batch MinMax',)
    return new

def generalcompare(ng, callhistory:list,
    data_type:str,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    val2:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    epsilon:sFlo|sInt|sBoo|float|int=None,
    ) -> sBoo:
    """generic operation for comparison operation and linking."""

    uniquename = get_unique_name('Compa',callhistory)
    node = None
    args = (val1, val2, epsilon,)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

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

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalboolmath(ng, callhistory:list,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    val2:sFlo|sInt|sBoo|sVec|float|int|bool|Vector=None,
    ) -> sBoo:
    """generic operation for BooleanMath."""

    uniquename = get_unique_name('BoolMath',callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

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
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    for i,val in enumerate((val1,val2)):
        match val:

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT():
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

def generalbatchcompare(ng, callhistory:list,
    operation_type:str,
    epsilon:sFlo|sInt|sBoo|float|int,
    valueA:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    valueB:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    *values:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    ) -> sBoo:
    """generic operation to batch comparison operation between a range or given float compatible itterable"""

    match operation_type:
        case 'alleq':
            opefunc = iseq
        # TODO support other batch comparison method?
        # Some of them are a bit more complicated. Because on some occation we cannot simply chain comparison, ALL members will needs to be cross compared, not simply one after another.
        # case 'alluneq':
        #     opefunc = isuneq
        # case 'allless':
        #     opefunc = isless
        # case 'alllesseq':
        #     opefunc = islesseq
        # case 'allgreater':
        #     opefunc = isgreater
        # case 'allgreatereq':
        #     opefunc = isgreatereq
        # case 'allbetween':
        #     pass
        # case 'allbetweeneq':
        #     pass
        case _:
            raise Exception(f"Unsupported operation_type '{operation_type}' passed to generalbatchcompare().")

    if len(values) in {0,1}:
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() needs two Params or more.") 
    for o in values:
        if type(o) not in {sFlo, sInt, sBoo, sVec, sVecXYZ, sVecT, float, int, bool, Vector}:
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() recieved unsupported type '{type(o).__name__}'.") 

    to_frame = []
    compared = []

    #create comparison chain
    for i,o in enumerate(values):
        if (i==0):
            continue
        a = values[i-1]
        b = o
        compa = opefunc(ng,callhistory, a,b)
        to_frame.append(compa.node)
        compared.append(compa)
        continue

    #add all bool result together
    a = compared[0]
    for i,o in enumerate(compared):
        if (i==0):
            continue
        b = o
        andop = add(ng,callhistory, a,b)
        andop.node.location = b.node.location
        andop.node.location.y += 250
        a = andop
        to_frame.append(andop.node)
        continue

    #if all equals addition of all bool should be of len of all values
    final = iseq(ng,callhistory, a,len(compared))
    to_frame.append(final.node)

    frame_nodes(ng, *to_frame, label="Batch Compare",)
    return final

def generalmatrixmath(ng, callhistory:list,
    operation_type:str,
    vec1:sFlo|sInt|sBoo|sVec|float|int|bool|Vector=None,
    mat1:sMtx=None,
    mat2:sMtx=None,
    ) -> sMtx|sVec|sBoo|sFlo:
    """generic operation for operation on Matrix."""

    if (vec1 is not None):
        if (type(vec1) not in {sFlo, sInt, sBoo, sVec, sVecXYZ, sVecT, float, int, bool, Vector}):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() recieved unsupported type '{type(vec1).__name__}' for parameter 'vec1'.")
    for mat in (mat1,mat2):
        if (mat is not None):
            if (type(mat) not in {sMtx, Matrix}):
                raise InvalidTypePassedToSocket(f"ParamTypeError. Function {operation_type}() recieved unsupported type '{type(mat).__name__}' for parameter 'mat1' or 'mat2'.")

    match operation_type:
        case 'matrixdeterminant':
            nodetype, args, outidx = 'FunctionNodeMatrixDeterminant', (mat1,), 0
        case 'matrixinvert':
            nodetype, args, outidx = 'FunctionNodeInvertMatrix', (mat1,), 0
        case 'matrixisinvertible':
            nodetype, args, outidx = 'FunctionNodeInvertMatrix', (mat1,), 1
        case 'matrixtranspose':
            nodetype, args, outidx = 'FunctionNodeTransposeMatrix', (mat1,), 0
        case 'matrixmult':
            nodetype, args, outidx = 'FunctionNodeMatrixMultiply', (mat1, mat2,), 0
        case 'transformloc':
            nodetype, args, outidx = 'FunctionNodeTransformPoint', (vec1, mat1,), 0
        case 'projectloc':
            nodetype, args, outidx = 'FunctionNodeTransformDirection', (vec1, mat1,), 0
        case 'transformdir':
            nodetype, args, outidx = 'FunctionNodeProjectPoint', (vec1, mat1,), 0
        case _:
            raise Exception(f"Unsupported operation_type '{operation_type}' passed to generalbatchcompare().")

    uniquename = get_unique_name('MtxMath',callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new(nodetype)
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    for i,val in enumerate(args):
        match val:

            case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT() | sMtx():
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Matrix():
                #unfortunately we are forced to create a new node, there's no .default_value option for type SocketMatrix..
                rowflatten = [v for row in val for v in row]
                if (uniquename):
                      defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f"C|{uniquename}|def{i}")
                else: defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f'C|{rowflatten[:]}') #enough space in nodename property? hmm. this function should't be used with no uniquename anyway..
                if needs_linking:
                    link_sockets(defval, node.inputs[i])

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

            case _: raise InvalidTypePassedToSocket(f"ParamTypeError. Function generalmatrixmath('{operation_type}') recieved unsupported type '{type(val).__name__}'. Should not happen. Previous check should've pick up on this.")

    return node.outputs[outidx]

def generalcombsepa(ng, callhistory:list,
    operation_type:str,
    data_type:str, 
    input_data:sFlo|sInt|sBoo|sVec|sMtx|tuple|list|set,
    ) -> tuple|sVec|sMtx:
    """Generic function for creating 'combine' or 'separate' nodes, over multiple types"""

    node_types = {
        'SEPARATE': {
            'VECTORXYZ': 'ShaderNodeSeparateXYZ',
            'MATRIXFLAT': 'FunctionNodeSeparateMatrix',
            'MATRIXTRANSFORM': 'FunctionNodeSeparateTransform',
            },
        'COMBINE': {
            'VECTORXYZ': 'ShaderNodeCombineXYZ',
            'MATRIXFLAT': 'FunctionNodeCombineMatrix',
            'MATRIXTRANSFORM': 'FunctionNodeCombineTransform',
            },
        }

    assert operation_type in {'SEPARATE','COMBINE'}
    if data_type not in node_types[operation_type]:
        raise ValueError(f"Unsupported data_type '{data_type}' for operation '{operation_type}'")
    nodetype = node_types[operation_type][data_type]

    prefix_names = {
        'SEPARATE': {
            'VECTORXYZ': "Sepa VecXYZ",
            'MATRIXFLAT': "Sepa MtxFlat",
            'MATRIXTRANSFORM': "Sepa Transf",
            },
        'COMBINE': {
            'VECTORXYZ': "Comb VecXYZ",
            'MATRIXFLAT': "Comb MtxFlat",
            'MATRIXTRANSFORM': "Comb Transf",
            },
        }

    nameid = prefix_names[operation_type][data_type]
    uniquename = get_unique_name(nameid, callhistory)
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new(nodetype)
        node.location = location
        ng.nodes.active = node

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename

    match operation_type:

        case 'SEPARATE':
            assert type(input_data) in {sVec, sVecXYZ, sVecT, sMtx}, "This function is expecting to recieve a SocketVector or SocketMatrix"
            if needs_linking:
                link_sockets(input_data, node.inputs[0])
            return tuple(node.outputs)

        case 'COMBINE':
            for i, val in enumerate(input_data):
                match val:

                    case sFlo() | sInt() | sBoo() | sVec() | sVecXYZ() | sVecT() | sQut():
                        if needs_linking:
                            link_sockets(val, node.inputs[i])

                    case float() | int() | bool():
                        val = float(val) if isinstance(val, bool) else val
                        if node.inputs[i].default_value != val:
                            node.inputs[i].default_value = val
                            assert_purple_node(node)

                    case Vector():
                        if node.inputs[i].default_value[:] != val[:]:
                            node.inputs[i].default_value = val
                            assert_purple_node(node)

                    case None: pass

                    case _:
                        raise InvalidTypePassedToSocket(f"Unsupported type '{type(val).__name__}' in combine operation.")
            return node.outputs[0]

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Addition.\nEquivalent to the '+' symbol.")
def add(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'ADD',a,b)
    return generalfloatmath(ng,callhistory, 'ADD',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Subtraction.\nEquivalent to the '-' symbol.")
def sub(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'SUBTRACT',a,b)
    return generalfloatmath(ng,callhistory, 'SUBTRACT',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Multiplications.\nEquivalent to the '*' symbol.")
def mult(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'MULTIPLY',a,b)
    return generalfloatmath(ng,callhistory, 'MULTIPLY',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Division.\nEquivalent to the '/' symbol.")
def div(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'DIVIDE',a,b)
    return generalfloatmath(ng,callhistory, 'DIVIDE',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="A Power N.\nEquivalent to the 'A**N' or '²' symbol.")
def pow(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(n,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function pow(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")
        return generalvecfloatmath(ng,callhistory, 'POWER',a,n)
    return generalfloatmath(ng,callhistory, 'POWER',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Logarithm A base N.")
@user_doc(nexscript="Logarithm A base N.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
def log(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,n,types=(float,int,)):
    #     return math.log(a,n)
    if anytype(a,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(n,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function log(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")
        return generalvecfloatmath(ng,callhistory, 'LOGARITHM',a,n)
    return generalfloatmath(ng,callhistory, 'LOGARITHM',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Square Root of A.")
@user_doc(nexscript="Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sqrt(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sqrt(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalvecfloatmath(ng,callhistory, 'SQRT',a)
    return generalfloatmath(ng,callhistory, 'SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Inverse Square Root of A.")
@user_doc(nexscript="Inverse Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
def invsqrt(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalvecfloatmath(ng,callhistory, 'INVERSE_SQRT',a)
    return generalfloatmath(ng,callhistory, 'INVERSE_SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="A Root N.\nEquivalent to doing 'A**(1/N)'.")
@user_doc(nexscript="A Root N.\nEquivalent to doing 'A**(1/N)'.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
def nroot(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:

    if anytype(a,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(n,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function nroot(). Second argument must be a float compatible type. Recieved '{type(n).__name__}'.")

    _x = div(ng,callhistory, 1,n,)
    _r = pow(ng,callhistory, a,_x)

    frame_nodes(ng, _x.node, _r.node.parent if _r.node.parent else _r.node, label='nRoot',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Absolute of A.")
def abs(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'ABSOLUTE',a)
    return generalfloatmath(ng,callhistory, 'ABSOLUTE',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Negate the value of A.\nEquivalent to the symbol '-x.'")
def neg(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    _r = sub(ng,callhistory, 0,a)
    frame_nodes(ng, _r.node,label='Negate',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Round a Float value.\nex: 1.49 will become 1\n1.51 will become 2.")
def round(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'ROUND',a)
    return generalfloatmath(ng,callhistory, 'ROUND',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Floor a Float value.\nex: 1.51 will become 1\n-1.51 will become -2.")
@user_doc(nexscript="Floor a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.51 will become 1\n-1.51 will become 2.")
def floor(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.floor(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'FLOOR',a)
    return generalfloatmath(ng,callhistory, 'FLOOR',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Ceil a Float value.\nex: 1.01 will become 2\n-1.99 will become -1.")
@user_doc(nexscript="Ceil a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.01 will become 2\n-1.99 will become 1.")
def ceil(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.ceil(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'CEIL',a)
    return generalfloatmath(ng,callhistory, 'CEIL',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Trunc a Float value.\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_doc(nexscript="Trunc a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.99 will become 1\n-1.99 will become -1.")
def trunc(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.trunc(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'TRUNC',a)
    return generalfloatmath(ng,callhistory, 'TRUNC',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Fraction.\nThe fraction part of A.")
@user_doc(nexscript="Fraction.\nThe fraction part of A.\nSupports SocketFloat and entry-wise SocketVector.")
def frac(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'FRACTION',a)
    return generalfloatmath(ng,callhistory, 'FRACT',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Modulo.\nEquivalent to the '%' symbol.")
def mod(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'MODULO',a,b)
    return generalfloatmath(ng,callhistory, 'MODULO',a,b)

#not covered in Nex.. user can do floor(A%B)
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Floored Modulo.")
def floormod(ng, callhistory:list,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'FLOORED_MODULO',a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Wrapping.\nWrap a value V to Range A B.")
@user_doc(nexscript="Wrapping.\nWrap a value V to Range A B.\nSupports SocketFloat and entry-wise SocketVector.")
def wrap(ng, callhistory:list,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalvecmath(ng,callhistory, 'WRAP',v,a,b)
    return generalfloatmath(ng,callhistory, 'WRAP',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Snapping.\nSnap a value V to the nearest increament I.")
@user_doc(nexscript="Snapping.\nSnap a value V to the nearest increament I.\nSupports SocketFloat and SocketVector.")
def snap(ng, callhistory:list,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    i:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,i,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalvecmath(ng,callhistory, 'SNAP',v,i)
    return generalfloatmath(ng,callhistory, 'SNAP',v,i)

@user_domain('mathex','nexscript')
@user_doc(mathex="PingPong.\nWrap a value and every other cycles at cycle Scale.")
@user_doc(nexscript="PingPong.\nWrap a value and every other cycles at cycle Scale.\nSupports SocketFloat and entry-wise SocketVector if scale is float compatible.")
def pingpong(ng, callhistory:list,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    scale:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(scale,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function pingpong(). Second argument must be a float compatible type. Recieved '{type(scale).__name__}'.")
        return generalvecfloatmath(ng,callhistory, 'PINGPONG',v,scale)
    return generalfloatmath(ng,callhistory, 'PINGPONG',v,scale)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Floor Division.\nEquivalent to the '//' symbol.")
def floordiv(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:

    _x = div(ng,callhistory, a,b)
    _r = floor(ng,callhistory, _x)
    frame_nodes(ng, _x.node, _r.node,label='FloorDiv',)

    return _r

@user_domain('mathex','nexscript')
@user_doc(mathex="The Sine of A.")
@user_doc(nexscript="The Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sin(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sin(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'SINE',a)
    return generalfloatmath(ng,callhistory, 'SINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Cosine of A.")
@user_doc(nexscript="The Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def cos(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.cos(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'COSINE',a)
    return generalfloatmath(ng,callhistory, 'COSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Tangent of A.")
@user_doc(nexscript="The Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def tan(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec|float:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.tan(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecmath(ng,callhistory, 'TANGENT',a)
    return generalfloatmath(ng,callhistory, 'TANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arcsine of A.")
@user_doc(nexscript="The Arcsine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def asin(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.asin(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'ARCSINE',a)
    return generalfloatmath(ng,callhistory, 'ARCSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arccosine of A.")
@user_doc(nexscript="The Arccosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def acos(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.acos(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'ARCCOSINE',a)
    return generalfloatmath(ng,callhistory, 'ARCCOSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arctangent of A.")
@user_doc(nexscript="The Arctangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def atan(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.atan(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'ARCTANGENT',a)
    return generalfloatmath(ng,callhistory, 'ARCTANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Sine of A.")
@user_doc(nexscript="The Hyperbolic Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def sinh(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.sinh(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'SINH',a)
    return generalfloatmath(ng,callhistory, 'SINH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Cosine of A.")
@user_doc(nexscript="The Hyperbolic Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
def cosh(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.cosh(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'COSH',a)
    return generalfloatmath(ng,callhistory, 'COSH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Tangent of A.")
@user_doc(nexscript="The Hyperbolic Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
def tanh(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.tanh(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'TANH',a)
    return generalfloatmath(ng,callhistory, 'TANH',a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Degrees to Radians.")
def rad(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.radians(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'RADIANS',a)
    return generalfloatmath(ng,callhistory, 'RADIANS',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="Convert a value from Degrees to Radians.\nSupports SocketFloat and entry-wise SocketVector.")
def radians(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return rad(ng,callhistory,a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Radians to Degrees.")
def deg(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    # #If user is only using python type, we use the math function instead of creating new nodes
    # if alltypes(a,types=(float,int,)):
    #     return math.degrees(a)
    if anytype(a,types=(sVec, sVecXYZ, sVecT,),):
        return generalvecfloatmath(ng,callhistory, 'DEGREES',a)
    return generalfloatmath(ng,callhistory, 'DEGREES',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="Convert a value from Radians to Degrees.\nSupports SocketFloat and entry-wise SocketVector.")
def degrees(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return deg(ng,callhistory,a)

@user_domain('nexscript')
@user_doc(nexscript="Vector Cross Product.\nThe cross product between vector A an B.")
def cross(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'CROSS_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Dot Product.\nA dot B.")
def dot(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'DOT_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject A onto B.")
def project(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Faceforward.\nFaceforward operation between a given vector, an incident and a reference.")
def faceforward(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vI:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vR:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'FACEFORWARD',vA,vI,vR)

@user_domain('nexscript')
@user_doc(nexscript="Vector Reflection.\nReflect A onto B.")
def reflect(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Distance.\nThe distance between location A & B.")
def distance(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory, 'DISTANCE',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Normalization.\nNormalize the values of a vector A to fit a 0-1 range.")
def normalize(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'NORMALIZE',vA)

#covered internally in nexscript with NexVec.length
@user_domain('nexclassmethod')
def length(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory, 'LENGTH',vA)

@user_domain('nexscript')
@user_doc(nexscript="Separate Vector.\nSeparate a SocketVector into a tuple of 3 SocketFloat.\n\nTip: you can use python slicing notations 'myX, myY, myZ = vA' instead.")
def separate_xyz(ng, callhistory:list,
    vA:sVec,
    ) -> tuple:
    if (type(vA) not in {sVec, sVecXYZ, sVecT}):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_xyz() recieved unsupported type '{type(vA).__name__}'")
    return generalcombsepa(ng,callhistory, 'SEPARATE','VECTORXYZ', vA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Vector.\nCombine 3 SocketFloat, SocketInt or SocketBool into a SocketVector.")
def combine_xyz(ng, callhistory:list,
    fX:sFlo|sInt|sBoo|float|int,
    fY:sFlo|sInt|sBoo|float|int,
    fZ:sFlo|sInt|sBoo|float|int,
    ) -> sVec:
    if not alltypes(fX,fY,fZ,types=(sFlo, sInt, sBoo, float, int),):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function combine_xyz(). Expected x,y,z arguments in SocketFloat,SocketInt,SocketBool,float or int. Recieved '{type(fX).__name__}','{type(fY).__name__}','{type(fZ).__name__}'.")
    return generalcombsepa(ng,callhistory, 'COMBINE','VECTORXYZ', (fX,fY,fZ),)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Euler).\nRotate a given Vector A with euler angle radians E, at optional center C.")
def roteuler(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vE:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    return generalverotate(ng, callhistory, 'EULER_XYZ',False, vA,vC,None,None,vE,)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Euler).\nRotate a given Vector A from defined axis X & angle radians F, at optional center C.")
def rotaxis(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vX:sFlo|sInt|sBoo|sVec|float|int|Vector,
    fA:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|float|int|Vector=None,
    ) -> sVec:
    return generalverotate(ng, callhistory, 'AXIS_ANGLE',False, vA,vC,vX,fA,None,)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
def matrixdeterminant(ng, callhistory:list,
    mA:sMtx,
    ) -> sFlo:
    return generalmatrixmath(ng,callhistory, 'matrixdeterminant', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
def matrixinvert(ng, callhistory:list,
    mA:sMtx,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixinvert', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
def matrixisinvertible(ng, callhistory:list,
    mA:sMtx,
    ) -> sBoo:
    return generalmatrixmath(ng,callhistory, 'matrixisinvertible', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
def matrixtranspose(ng, callhistory:list,
    mA:sMtx,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixtranspose', None,mA,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def matrixmult(ng, callhistory:list,
    mA:sMtx|Matrix,
    mB:sMtx|Matrix,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixmult', None,mA,mB)
        
@user_domain('nexscript')
@user_doc(nexscript="Vector Transform.\nTransform a location vector A by a given matrix B.\nWill return a VectorSocket.\n\nCould use notation 'mB @ vA' instead.")
def transformloc(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'transformloc', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject a location vector A by a given matrix B.\nWill return a VectorSocket.")
def projectloc(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'projectloc', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Direction Transform.\nTransform direction vector A by a given matrix B.\nWill return a VectorSocket.")
def transformdir(ng, callhistory:list,
    vA:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'transformdir', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Flatten).\nSeparate a SocketMatrix into a tuple of 16 SocketFloat arranged by columns.")
def separate_matrix(ng, callhistory:list,
    mA:sMtx,
    ) -> tuple:
    if (type(mA) is not sMtx):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_matrix() recieved unsupported type '{type(mA).__name__}'")
    return generalcombsepa(ng,callhistory, 'SEPARATE','MATRIXFLAT', mA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Flatten).\nCombine an itterable containing  16 SocketFloat, SocketInt or SocketBool arranged by columns to a SocketMatrix.")
def combine_matrix(ng, callhistory:list,
    *itterables:sFlo|sInt|sBoo|float|int|tuple|set|list,
    ) -> tuple:

    #unpack itterable?
    if ((len(itterables)==1) and (type(itterables[0]) in {tuple, set, list})):
        itterables = itterables[0]

    if (type(itterables) not in {tuple, set, list}):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function combine_matrix() recieved unsupported type '{type(itterables).__name__}'")
    if (len(itterables) !=16):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function combine_matrix() recieved itterable must be of len 16 to fit a 4x4 SocketMatrix")

    for it in itterables:
        if type(it) not in {sFlo, sInt, sBoo, float, int}:
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function combine_matrix(). Expected arguments in SocketFloat,SocketInt,SocketBool,float or int. Recieved a '{type(it).__name__}'.")

    return generalcombsepa(ng,callhistory, 'COMBINE','MATRIXFLAT', itterables,)

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Transform).\nSeparate a SocketMatrix into a tuple of 3 SocketVector.")
def separate_transform(ng, callhistory:list,
    mA:sMtx,
    ) -> tuple:
    if (type(mA) is not sMtx):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_transform() recieved unsupported type '{type(mA).__name__}'")
    return generalcombsepa(ng,callhistory, 'SEPARATE','MATRIXTRANSFORM', mA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Transform).\nCombine 3 SocketVector into a SocketMatrix.")
def combine_transform(ng, callhistory:list,
    vLoc:sFlo|sInt|sBoo|sVec|float|int|Vector,
    vRot:sFlo|sInt|sBoo|sVec|sQut|float|int|Vector|Quaternion,
    vSca:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> tuple:
    
    if type(vLoc) in {int, float}:
        vLoc = Vector((vLoc,vLoc,vLoc))
    if type(vRot) in {int, float}:
        vRot = Vector((vRot,vRot,vRot)) #support quaternion in here?
    if type(vSca) in {int, float}:
        vSca = Vector((vSca,vSca,vSca))

    if (type(vLoc) not in {sFlo, sInt, sBoo, sVec, sVecXYZ, sVecT, Vector}):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_transform() recieved unsupported type '{type(vLoc).__name__}' for Location parameter")
    if (type(vRot) not in {sFlo, sInt, sBoo, sVec, sVecXYZ, sVecT, sQut, Vector}):#, Quaternion}):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_transform() recieved unsupported type '{type(vRot).__name__}' for Rotation parameter")
    if (type(vSca) not in {sFlo, sInt, sBoo, sVec, sVecXYZ, sVecT, Vector}):
        raise InvalidTypePassedToSocket(f"ParamTypeError. Function separate_transform() recieved unsupported type '{type(vSca).__name__}' for Scale parameter")

    return generalcombsepa(ng,callhistory, 'COMBINE','MATRIXTRANSFORM', (vLoc,vRot,vSca),)

@user_domain('mathex','nexscript')
@user_doc(mathex="Minimum.\nGet the absolute minimal value across all passed arguments.")
@user_doc(nexscript="Minimum.\nGet the absolute minimal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
def min(ng, callhistory:list,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalminmax(ng,callhistory, 'min',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
def smin(ng, callhistory:list,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'SMOOTH_MIN',a,b,dist)

@user_domain('mathex','nexscript')
@user_doc(mathex="Maximum.\nGet the absolute maximal value across all passed arguments.")
@user_doc(nexscript="Maximum.\nGet the absolute maximal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
def max(ng, callhistory:list,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalminmax(ng,callhistory, 'max',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
def smax(ng, callhistory:list,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'SMOOTH_MAX',a,b,dist)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def iseq(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory, 'XNOR', a,b)
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def isuneq(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory, 'XOR', a,b)
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','NOT_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','NOT_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def isless(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','LESS_THAN', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','LESS_THAN', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def islesseq(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','LESS_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','LESS_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def isgreater(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','GREATER_THAN', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','GREATER_THAN', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def isgreatereq(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    )->sBoo:
    if anytype(a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalcompare(ng,callhistory, 'VECTOR','GREATER_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','GREATER_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def booland(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'AND', a,b)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
def boolor(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'OR', a,b)

@user_domain('nexclassmethod')
def boolnot(ng, callhistory:list,
    a:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'NOT', a)

@user_domain('nexscript')
@user_doc(nexscript="All Equals.\nCheck if all passed arguments have equal values.\n\nCompatible with SocketFloats, SocketVectors and SocketBool. Will return a SocketBool.")
def alleq(ng, callhistory:list,
    *values:sFlo|sInt|sBoo|sVec|float|int|bool|Vector,
    )->sBoo:
    return generalbatchcompare(ng,callhistory, 'alleq',None,None,None, *values)

#TODO what about epsilon??? problem is that epsilon is not supported for all operaiton type
#def almosteq(a,b,epsilon)
#TODO 
#def isbetween(value, min, max)
#def allbetween(min, max, *betweens)

@user_domain('mathex','nexscript')
@user_doc(mathex="Mix.\nLinear Interpolation between value A and B from given factor F.")
@user_doc(nexscript="Mix.\nLinear Interpolation between value A and B from given factor F.\nSupports SocketFloat and SocketVector.")
def lerp(ng, callhistory:list,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(f,a,b,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalmix(ng,callhistory, 'VECTOR',f,a,b)
    return generalmix(ng,callhistory, 'FLOAT',f,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Alternative notation to lerp() function.")
@user_doc(nexscript="Alternative notation to lerp() function.")
def mix(ng, callhistory:list,
    f:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|float|int|Vector,
    ) -> sFlo|sVec:
    return lerp(ng,callhistory, f,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Clamping.\nClamp a value a between min A an max B.")
@user_doc(nexscript="Clamping.\nClamp a value a between min A an max B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
def clamp(ng, callhistory:list,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(a,b,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function clamp(). Second or Third argument must be float compatible types. Recieved '{type(a).__name__}' & '{type(b).__name__}'.")
        return generalvecfloatmath(ng,callhistory, 'CLAMP.MINMAX',v,a,b)
    return generalfloatmath(ng,callhistory, 'CLAMP.MINMAX',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="AutoClamping.\nClamp a value a between auto-defined min/max A & B.")
@user_doc(nexscript="AutoClamping.\nClamp a value a between auto-defined min/max A & B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
def clampauto(ng, callhistory:list,
    v:sFlo|sInt|sBoo|sVec|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if anytype(v,types=(sVec, sVecXYZ, sVecT, Vector,),):
        if not alltypes(a,b,types=(sFlo, sInt, sBoo, float, int),):
            raise InvalidTypePassedToSocket(f"ParamTypeError. Function clamp(). Second or Third argument must be float compatible types. Recieved '{type(a).__name__}' & '{type(b).__name__}'.")
        return generalvecfloatmath(ng,callhistory, 'CLAMP.RANGE',v,a,b)
    return generalfloatmath(ng,callhistory, 'CLAMP.RANGE',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range.\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range.\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapl(ng, callhistory:list,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','LINEAR',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','LINEAR',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.")
@user_doc(nexscript="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\nSupports SocketFloat and SocketVector.")
def mapst(ng, callhistory:list,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    step:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,step,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','STEPPED',v,a,b,x,y,step)
    return generalmaprange(ng,callhistory, 'FLOAT','STEPPED',v,a,b,x,y,step)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapsmo(ng, callhistory:list,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','SMOOTHSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','SMOOTHSTEP',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
def mapsmoo(ng, callhistory:list,
    v:sFlo|sInt|sBoo|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int|Vector,
    b:sFlo|sInt|sBoo|float|int|Vector,
    x:sFlo|sInt|sBoo|float|int|Vector,
    y:sFlo|sInt|sBoo|float|int|Vector,
    ) -> sFlo|sVec:
    if anytype(v,a,b,x,y,types=(sVec, sVecXYZ, sVecT, Vector,),):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','SMOOTHERSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','SMOOTHERSTEP',v,a,b,x,y)

@user_domain('nexscript')
@user_doc(nexscript="Position Attribute.\nGet the GeometryNode 'Position' SocketVector input attribute.")
def getp(ng, callhistory:list,
    ) -> sVec:

    uniquename = 'F|GetPosition' if (callhistory is not None) else None #This one is a singleton
    node = ng.nodes.get(uniquename)

    if (node is None):
        node = ng.nodes.new('GeometryNodeInputPosition')
        node.name = node.label = uniquename
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*1

    return node.outputs[0]

@user_domain('nexscript')
@user_doc(nexscript="Normal Attribute.\nGet the GeometryNode 'Normal' SocketVector input attribute.")
def getn(ng, callhistory:list,
    ) -> sVec:

    uniquename = 'F|GetNormal' if (callhistory is not None) else None #This one is a singleton
    node = ng.nodes.get(uniquename)

    if (node is None):
        node = ng.nodes.new('GeometryNodeInputNormal')
        node.name = node.label = uniquename
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*2

    return node.outputs[0]

# TODO more attr input
# def getid() -> Int
# def getindex() -> Int
# def getnamedattr(name) -> Dynamic