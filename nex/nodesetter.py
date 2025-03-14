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
from ..utils.fct_utils import strongtyping as user_paramError

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


def convert_args(*args, toVector=False,) -> tuple:
    if (toVector):
        return [Vector((a,a,a)) if type(a) in (int,bool,float) else a for a in args]
    return None

def containsVecs(*args) -> bool:
    return anytype(*args ,types=(sVec, sVecXYZ, sVecT, Vector),)

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
        
        #we wrapped our function, we need to access the real function to check the doc, not the wrapped one.
        rf = f
        if hasattr(f,'originalfunc'):
            rf = f.originalfunc

        #collect args of this function
        fargs = list(rf.__code__.co_varnames[:rf.__code__.co_argcount])

        #remove strictly internal args from documentation
        if ('ng' in fargs):
            fargs.remove('ng')
        if ('callhistory' in fargs):
            fargs.remove('callhistory')

        # support for *args parameters?
        if (rf.__code__.co_flags & 0x04):  # Function has *args
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

#   .oooooo.                                                       oooo       oooooooooooo               .            
#  d8P'  `Y8b                                                      `888       `888'     `8             .o8            
# 888            .ooooo.  ooo. .oo.    .ooooo.  oooo d8b  .oooo.    888        888          .ooooo.  .o888oo  .oooo.o 
# 888           d88' `88b `888P"Y88b  d88' `88b `888""8P `P  )88b   888        888oooo8    d88' `"Y8   888   d88(  "8 
# 888     ooooo 888ooo888  888   888  888ooo888  888      .oP"888   888        888    "    888         888   `"Y88b.  
# `88.    .88'  888    .o  888   888  888    .o  888     d8(  888   888        888         888   .o8   888 . o.  )88b 
#  `Y8bood8P'   `Y8bod8P' o888o o888o `Y8bod8P' d888b    `Y888""8o o888o      o888o        `Y8bod8P'   "888" 8""888P' 


def generalfloatmath(ng, callhistory,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int|None=None,
    val2:sFlo|sInt|sBoo|float|int|None=None,
    val3:sFlo|sInt|sBoo|float|int|None=None,
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

            case _: raise Exception(f"InternalError. Function generalfloatmath({operation_type}) recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[0]

def generalvecmath(ng, callhistory,
    operation_type:str,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    val3:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
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

            case _: raise Exception(f"InternalError. Function generalvecmath('{operation_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[outidx]

def generalverotate(ng, callhistory,
    rotation_type:str,
    invert:bool,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    vC:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    vX:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    fA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    vE:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
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

            case _: raise Exception(f"InternalError. Function generalverotate('{rotation_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[0]

def generalmix(ng, callhistory,
    data_type:str,
    factor:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
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

            case _: raise Exception(f"InternalError. Function generalmix('{data_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[outidx]

def generalvecfloatmath(ng, callhistory,
    operation_type:str,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    fB:sFlo|sInt|sBoo|float|int|None=None,
    fC:sFlo|sInt|sBoo|float|int|None=None,
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

def generalmaprange(ng, callhistory,
    data_type:str,
    interpolation_type:str,
    value:sFlo|sInt|sBoo|float|int|Vector|None=None,
    from_min:sFlo|sInt|sBoo|float|int|Vector|None=None,
    from_max:sFlo|sInt|sBoo|float|int|Vector|None=None,
    to_min:sFlo|sInt|sBoo|float|int|Vector|None=None,
    to_max:sFlo|sInt|sBoo|float|int|Vector|None=None,
    steps:sFlo|sInt|sBoo|float|int|Vector|None=None,
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

            case _: raise Exception(f"InternalError. Function generalmaprange('{data_type}','{interpolation_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[outidx]

def generalminmax(ng, callhistory,
    operation_type:str,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    """generic operation to cover the max/min operation between a range or given float compatible itterable"""

    assert operation_type in {'min','max'}
    fullopname = 'MINIMUM' if (operation_type=='min') else 'MAXIMUM'
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

def generalcompare(ng, callhistory,
    data_type:str,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    epsilon:sFlo|sInt|sBoo|float|int|None=None,
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

            case _: raise Exception(f"InternalError. Function generalcompare('{data_type}','{operation}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[0]

def generalboolmath(ng, callhistory,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector|None=None,
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

            case _: raise Exception(f"InternalError. Function generalboolmath('{operation}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[0]

def generalbatchcompare(ng, callhistory,
    operation_type:str,
    epsilon:sFlo|sInt|sBoo|float|int,
    valueA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    valueB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
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

def generalmatrixmath(ng, callhistory,
    operation_type:str,
    vec1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector|None=None,
    mat1:sMtx|Matrix|None=None,
    mat2:sMtx|Matrix|None=None,
    ) -> sMtx|sVec|sBoo|sFlo:
    """generic operation for operation on Matrix."""

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

            case _: raise Exception(f"InternalError. Function generalmatrixmath('{operation_type}') recieved unsupported type '{type(val).__name__}'. Previous check should've pick up on this.")

    return node.outputs[outidx]

def generalcombsepa(ng, callhistory,
    operation_type:str,
    data_type:str, 
    input_data:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sMtx|Vector|tuple|list|set,
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
            val = input_data
            match val:
                case sVec() | sVecXYZ() | sVecT() | sMtx():
                    if needs_linking:
                        link_sockets(val, node.inputs[0])

                case Vector():
                    if node.inputs[0].default_value[:] != val[:]:
                        node.inputs[0].default_value = val
                        assert_purple_node(node)

                case _: raise Exception(f"InternalError. Type '{type(val).__name__}' not supported in separate() operation. Previous check should've pick up on this.")

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

                    case _: raise Exception(f"InternalError. Type '{type(val).__name__}' not supported in combine() operation. Previous check should've pick up on this.")

    return node.outputs[0]

# ooooo     ooo                                  oooooooooooo                                       .            
# `888'     `8'                                  `888'     `8                                     .o8            
#  888       8   .oooo.o  .ooooo.  oooo d8b       888         oooo  oooo  ooo. .oo.    .ooooo.  .o888oo  .oooo.o 
#  888       8  d88(  "8 d88' `88b `888""8P       888oooo8    `888  `888  `888P"Y88b  d88' `"Y8   888   d88(  "8 
#  888       8  `"Y88b.  888ooo888  888           888    "     888   888   888   888  888         888   `"Y88b.  
#  `88.    .8'  o.  )88b 888    .o  888           888          888   888   888   888  888   .o8   888 . o.  )88b 
#    `YbodP'    8""888P' `Y8bod8P' d888b         o888o         `V88V"V8P' o888o o888o `Y8bod8P'   "888" 8""888P' 


class UserParamError(Exception):
    """Raise this error if the user didn't used the function parameter types properly"""
    def __init__(self, message):
        super().__init__(message)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Addition.\nEquivalent to the '+' symbol.")
@user_paramError(UserParamError)
def add(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory, 'ADD',a,b)
    return generalfloatmath(ng,callhistory, 'ADD',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Subtraction.\nEquivalent to the '-' symbol.")
@user_paramError(UserParamError)
def sub(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory, 'SUBTRACT',a,b)
    return generalfloatmath(ng,callhistory, 'SUBTRACT',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Multiplications.\nEquivalent to the '*' symbol.")
@user_paramError(UserParamError)
def mult(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory, 'MULTIPLY',a,b)
    return generalfloatmath(ng,callhistory, 'MULTIPLY',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Division.\nEquivalent to the '/' symbol.")
@user_paramError(UserParamError)
def div(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory, 'DIVIDE',a,b)
    return generalfloatmath(ng,callhistory, 'DIVIDE',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="A Power N.\nEquivalent to the 'A**N' or '²' symbol.")
@user_paramError(UserParamError)
def pow(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'POWER',a,n)
    return generalfloatmath(ng,callhistory, 'POWER',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Logarithm A base N.")
@user_doc(nexscript="Logarithm A base N.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
@user_paramError(UserParamError)
def log(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    # for nexcript, math.log will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'LOGARITHM',a,n)
    return generalfloatmath(ng,callhistory, 'LOGARITHM',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Square Root of A.")
@user_doc(nexscript="Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def sqrt(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.sqrt will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'SQRT',a)
    return generalfloatmath(ng,callhistory, 'SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Inverse Square Root of A.")
@user_doc(nexscript="Inverse Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def invsqrt(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'INVERSE_SQRT',a)
    return generalfloatmath(ng,callhistory, 'INVERSE_SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="A Root N.\nEquivalent to doing 'A**(1/N)'.")
@user_doc(nexscript="A Root N.\nEquivalent to doing 'A**(1/N)'.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
@user_paramError(UserParamError)
def nroot(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    _x = div(ng,callhistory, 1,n,)
    _r = pow(ng,callhistory, a,_x)
    frame_nodes(ng, _x.node, _r.node.parent if _r.node.parent else _r.node, label='nRoot',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Absolute of A.")
@user_paramError(UserParamError)
def abs(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'ABSOLUTE',a)
    return generalfloatmath(ng,callhistory, 'ABSOLUTE',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Negate the value of A.\nEquivalent to the symbol '-x.'")
@user_paramError(UserParamError)
def neg(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    _r = sub(ng,callhistory, 0,a)
    frame_nodes(ng, _r.node,label='Negate',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Round a Float value.\nex: 1.49 will become 1\n1.51 will become 2.")
@user_paramError(UserParamError)
def round(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'ROUND',a)
    return generalfloatmath(ng,callhistory, 'ROUND',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Floor a Float value.\nex: 1.51 will become 1\n-1.51 will become -2.")
@user_doc(nexscript="Floor a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.51 will become 1\n-1.51 will become 2.")
@user_paramError(UserParamError)
def floor(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.floor will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'FLOOR',a)
    return generalfloatmath(ng,callhistory, 'FLOOR',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Ceil a Float value.\nex: 1.01 will become 2\n-1.99 will become -1.")
@user_doc(nexscript="Ceil a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.01 will become 2\n-1.99 will become 1.")
@user_paramError(UserParamError)
def ceil(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.ceil will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'CEIL',a)
    return generalfloatmath(ng,callhistory, 'CEIL',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Trunc a Float value.\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_doc(nexscript="Trunc a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_paramError(UserParamError)
def trunc(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.trunc will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'TRUNC',a)
    return generalfloatmath(ng,callhistory, 'TRUNC',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Fraction.\nThe fraction part of A.")
@user_doc(nexscript="Fraction.\nThe fraction part of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def frac(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'FRACTION',a)
    return generalfloatmath(ng,callhistory, 'FRACT',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Modulo.\nEquivalent to the '%' symbol.")
@user_paramError(UserParamError)
def mod(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory, 'MODULO',a,b)
    return generalfloatmath(ng,callhistory, 'MODULO',a,b)

#not covered in Nex.. user can do floor(A%B)
@user_domain('mathex')
@user_doc(mathex="Floored Modulo.")
@user_paramError(UserParamError)
def floormod(ng, callhistory,
    a:sFlo|sInt|sBoo,
    b:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'FLOORED_MODULO',a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Wrapping.\nWrap a value V to Range A B.")
@user_doc(nexscript="Wrapping.\nWrap a value V to Range A B.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def wrap(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b):
        return generalvecmath(ng,callhistory, 'WRAP',v,a,b)
    return generalfloatmath(ng,callhistory, 'WRAP',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Snapping.\nSnap a value V to the nearest increament I.")
@user_doc(nexscript="Snapping.\nSnap a value V to the nearest increament I.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def snap(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    i:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,i):
        return generalvecmath(ng,callhistory, 'SNAP',v,i)
    return generalfloatmath(ng,callhistory, 'SNAP',v,i)

@user_domain('mathex','nexscript')
@user_doc(mathex="PingPong.\nWrap a value and every other cycles at cycle Scale.")
@user_doc(nexscript="PingPong.\nWrap a value and every other cycles at cycle Scale.\nSupports SocketFloat and entry-wise SocketVector if scale is float compatible.")
@user_paramError(UserParamError)
def pingpong(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    scale:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if containsVecs(v):
        return generalvecfloatmath(ng,callhistory, 'PINGPONG',v,scale)
    return generalfloatmath(ng,callhistory, 'PINGPONG',v,scale)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Floor Division.\nEquivalent to the '//' symbol.")
@user_paramError(UserParamError)
def floordiv(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    _x = div(ng,callhistory, a,b)
    _r = floor(ng,callhistory, _x)
    frame_nodes(ng, _x.node, _r.node, label='FloorDiv',)
    return _r

@user_domain('mathex','nexscript')
@user_doc(mathex="The Sine of A.")
@user_doc(nexscript="The Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def sin(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.sin will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'SINE',a)
    return generalfloatmath(ng,callhistory, 'SINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Cosine of A.")
@user_doc(nexscript="The Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def cos(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.cos will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'COSINE',a)
    return generalfloatmath(ng,callhistory, 'COSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Tangent of A.")
@user_doc(nexscript="The Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def tan(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.tan will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory, 'TANGENT',a)
    return generalfloatmath(ng,callhistory, 'TANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arcsine of A.")
@user_doc(nexscript="The Arcsine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def asin(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.asin will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'ARCSINE',a)
    return generalfloatmath(ng,callhistory, 'ARCSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arccosine of A.")
@user_doc(nexscript="The Arccosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def acos(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.acos will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'ARCCOSINE',a)
    return generalfloatmath(ng,callhistory, 'ARCCOSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arctangent of A.")
@user_doc(nexscript="The Arctangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def atan(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.atan will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'ARCTANGENT',a)
    return generalfloatmath(ng,callhistory, 'ARCTANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Sine of A.")
@user_doc(nexscript="The Hyperbolic Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def sinh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.sinh will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'SINH',a)
    return generalfloatmath(ng,callhistory, 'SINH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Cosine of A.")
@user_doc(nexscript="The Hyperbolic Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def cosh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.cosh will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'COSH',a)
    return generalfloatmath(ng,callhistory, 'COSH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Tangent of A.")
@user_doc(nexscript="The Hyperbolic Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def tanh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.tanh will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'TANH',a)
    return generalfloatmath(ng,callhistory, 'TANH',a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Degrees to Radians.")
@user_paramError(UserParamError)
def rad(ng, callhistory,
    a:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'RADIANS',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="Convert a value from Degrees to Radians.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def radians(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.radians will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'RADIANS',a)
    return generalfloatmath(ng,callhistory, 'RADIANS',a)

@user_domain('mathex')
@user_doc(mathex="Convert a value from Radians to Degrees.")
@user_paramError(UserParamError)
def deg(ng, callhistory,
    a:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'DEGREES',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="Convert a value from Radians to Degrees.\nSupports SocketFloat and entry-wise SocketVector.")
@user_paramError(UserParamError)
def degrees(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.degrees will be called if given param is python float or int
    if containsVecs(a):
        return generalvecfloatmath(ng,callhistory, 'DEGREES',a)
    return generalfloatmath(ng,callhistory, 'DEGREES',a)

@user_domain('nexscript')
@user_doc(nexscript="Vector Cross Product.\nThe cross product between vector A an B.")
@user_paramError(UserParamError)
def cross(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'CROSS_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Dot Product.\nA dot B.")
@user_paramError(UserParamError)
def dot(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'DOT_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject A onto B.")
@user_paramError(UserParamError)
def project(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Faceforward.\nFaceforward operation between a given vector, an incident and a reference.")
@user_paramError(UserParamError)
def faceforward(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vI:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vR:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'FACEFORWARD',vA,vI,vR)

@user_domain('nexscript')
@user_doc(nexscript="Vector Reflection.\nReflect A onto B.")
@user_paramError(UserParamError)
def reflect(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Distance.\nThe distance between location A & B.")
@user_paramError(UserParamError)
def distance(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory, 'DISTANCE',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Normalization.\nNormalize the values of a vector A to fit a 0-1 range.")
@user_paramError(UserParamError)
def normalize(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory, 'NORMALIZE',vA)

#covered internally in nexscript with NexVec.length
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def length(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory, 'LENGTH',vA)

@user_domain('nexscript')
@user_doc(nexscript="Separate Vector.\nSeparate a SocketVector into a tuple of 3 SocketFloat.\n\nTip: you can use python slicing notations 'myX, myY, myZ = vA' instead.")
@user_paramError(UserParamError)
def separate_xyz(ng, callhistory,
    vA:sVec|sVecXYZ|sVecT|Vector,
    ) -> tuple:
    return generalcombsepa(ng,callhistory, 'SEPARATE','VECTORXYZ', vA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Vector.\nCombine 3 SocketFloat, SocketInt or SocketBool into a SocketVector.")
@user_paramError(UserParamError)
def combine_xyz(ng, callhistory,
    fX:sFlo|sInt|sBoo|float|int,
    fY:sFlo|sInt|sBoo|float|int,
    fZ:sFlo|sInt|sBoo|float|int,
    ) -> sVec:
    return generalcombsepa(ng,callhistory, 'COMBINE','VECTORXYZ', (fX,fY,fZ),)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Euler).\nRotate a given Vector A with euler angle radians E, at optional center C.")
@user_paramError(UserParamError)
def roteuler(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vE:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    ) -> sVec:
    return generalverotate(ng, callhistory, 'EULER_XYZ',False, vA,vC,None,None,vE,)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Euler).\nRotate a given Vector A from defined axis X & angle radians F, at optional center C.")
@user_paramError(UserParamError)
def rotaxis(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vX:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    fA:sFlo|sInt|sBoo|float|int,
    vC:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    ) -> sVec:
    return generalverotate(ng, callhistory, 'AXIS_ANGLE',False, vA,vC,vX,fA,None,)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def matrixdeterminant(ng, callhistory,
    mA:sMtx,
    ) -> sFlo:
    return generalmatrixmath(ng,callhistory, 'matrixdeterminant', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def matrixinvert(ng, callhistory,
    mA:sMtx,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixinvert', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def matrixisinvertible(ng, callhistory,
    mA:sMtx,
    ) -> sBoo:
    return generalmatrixmath(ng,callhistory, 'matrixisinvertible', None,mA,None)

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def matrixtranspose(ng, callhistory,
    mA:sMtx,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixtranspose', None,mA,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def matrixmult(ng, callhistory,
    mA:sMtx|Matrix,
    mB:sMtx|Matrix,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory, 'matrixmult', None,mA,mB)
        
@user_domain('nexscript')
@user_doc(nexscript="Vector Transform.\nTransform a location vector A by a given matrix B.\nWill return a VectorSocket.\n\nCould use notation 'mB @ vA' instead.")
@user_paramError(UserParamError)
def transformloc(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'transformloc', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject a location vector A by a given matrix B.\nWill return a VectorSocket.")
@user_paramError(UserParamError)
def projectloc(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'projectloc', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Direction Transform.\nTransform direction vector A by a given matrix B.\nWill return a VectorSocket.")
@user_paramError(UserParamError)
def transformdir(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory, 'transformdir', vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Flatten).\nSeparate a SocketMatrix into a tuple of 16 SocketFloat arranged by columns.")
@user_paramError(UserParamError)
def separate_matrix(ng, callhistory,
    mA:sMtx,
    ) -> tuple:
    return generalcombsepa(ng,callhistory, 'SEPARATE','MATRIXFLAT', mA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Flatten).\nCombine an itterable containing  16 SocketFloat, SocketInt or SocketBool arranged by columns to a SocketMatrix.")
@user_paramError(UserParamError)
def combine_matrix(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sMtx:
    if (type(floats) not in {tuple, set, list}):
        raise UserParamError(f"Function combine_matrix() recieved unsupported type '{type(floats).__name__}' was expecting a tuple of 16 float compatible values.")
    if (len(floats)!=16):
        raise UserParamError(f"Function combine_matrix() recieved itterable must be of len 16 to fit a 4x4 SocketMatrix")
    return generalcombsepa(ng,callhistory, 'COMBINE','MATRIXFLAT', floats,)

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Transform).\nSeparate a SocketMatrix into a tuple of 3 SocketVector.")
@user_paramError(UserParamError)
def separate_transform(ng, callhistory,
    mA:sMtx,
    ) -> tuple:
    return generalcombsepa(ng,callhistory, 'SEPARATE','MATRIXTRANSFORM', mA,)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Transform).\nCombine 3 SocketVector into a SocketMatrix.")
@user_paramError(UserParamError)
def combine_transform(ng, callhistory,
    vL:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vR:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sQut|float|int|Vector|Quaternion,
    vS:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sMtx:
    if type(vL) in {int, float}: vL = Vector((vL,vL,vL))
    if type(vR) in {int, float}: vR = Vector((vR,vR,vR)) #support quaternion in here?
    if type(vS) in {int, float}: vS = Vector((vS,vS,vS))
    return generalcombsepa(ng,callhistory, 'COMBINE','MATRIXTRANSFORM', (vL,vR,vS),)

@user_domain('mathex','nexscript')
@user_doc(mathex="Minimum.\nGet the absolute minimal value across all passed arguments.")
@user_doc(nexscript="Minimum.\nGet the absolute minimal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
@user_paramError(UserParamError)
def min(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    # for nexcript, min will be called if given params are all python float or int
    if (len(floats) in {0,1}):
        raise UserParamError(f"Function min() needs two Params or more.") 
    return generalminmax(ng,callhistory, 'min',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
@user_paramError(UserParamError)
def smin(ng, callhistory,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'SMOOTH_MIN',a,b,dist)

@user_domain('mathex','nexscript')
@user_doc(mathex="Maximum.\nGet the absolute maximal value across all passed arguments.")
@user_doc(nexscript="Maximum.\nGet the absolute maximal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
@user_paramError(UserParamError)
def max(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    # for nexcript, max will be called if given params are all python float or int
    if (len(floats) in {0,1}):
        raise UserParamError(f"Function max() needs two Params or more.") 
    return generalminmax(ng,callhistory, 'max',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
@user_paramError(UserParamError)
def smax(ng, callhistory,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory, 'SMOOTH_MAX',a,b,dist)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def iseq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory, 'XNOR', a,b)
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def isuneq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory, 'XOR', a,b)
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','NOT_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','NOT_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def isless(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    )->sBoo:
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','LESS_THAN', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','LESS_THAN', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def islesseq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    )->sBoo:
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','LESS_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','LESS_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def isgreater(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    )->sBoo:
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','GREATER_THAN', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','GREATER_THAN', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def isgreatereq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    )->sBoo:
    if containsVecs(a,b):
        return generalcompare(ng,callhistory, 'VECTOR','GREATER_EQUAL', a,b,None)
    return generalcompare(ng,callhistory, 'FLOAT','GREATER_EQUAL', a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def booland(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'AND', a,b)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def boolor(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'OR', a,b)

@user_domain('nexclassmethod')
@user_paramError(UserParamError)
def boolnot(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    return generalboolmath(ng,callhistory, 'NOT', a)

@user_domain('nexscript')
@user_doc(nexscript="All Equals.\nCheck if all passed arguments have equal values.\n\nCompatible with SocketFloats, SocketVectors and SocketBool. Will return a SocketBool.")
@user_paramError(UserParamError)
def alleq(ng, callhistory,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    )->sBoo:
    if (len(values) in {0,1}):
        raise UserParamError(f"Function alleq() needs two Params or more.") 
    return generalbatchcompare(ng,callhistory, 'alleq',None,None,None, *values)

#TODO what about epsilon??? problem is that epsilon is not supported for all operaiton type
#def almosteq(a,b,epsilon)
#TODO 
#def isbetween(value, min, max)
#def allbetween(min, max, *betweens)

@user_domain('mathex','nexscript')
@user_doc(mathex="Mix.\nLinear Interpolation between value A and B from given factor F.")
@user_doc(nexscript="Mix.\nLinear Interpolation between value A and B from given factor F.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def lerp(ng, callhistory,
    f:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(f,a,b):
        return generalmix(ng,callhistory, 'VECTOR',f,a,b)
    return generalmix(ng,callhistory, 'FLOAT',f,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Alternative notation to lerp() function.")
@user_doc(nexscript="Alternative notation to lerp() function.")
@user_paramError(UserParamError)
def mix(ng, callhistory,
    f:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    return lerp(ng,callhistory, f,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Clamping.\nClamp a value a between min A an max B.")
@user_doc(nexscript="Clamping.\nClamp a value a between min A an max B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
@user_paramError(UserParamError)
def clamp(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if containsVecs(v):
        return generalvecfloatmath(ng,callhistory, 'CLAMP.MINMAX',v,a,b)
    return generalfloatmath(ng,callhistory, 'CLAMP.MINMAX',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="AutoClamping.\nClamp a value a between auto-defined min/max A & B.")
@user_doc(nexscript="AutoClamping.\nClamp a value a between auto-defined min/max A & B.\nSupports SocketFloat and entry-wise SocketVector if A & B are float compatible.")
@user_paramError(UserParamError)
def clampauto(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if containsVecs(v):
        return generalvecfloatmath(ng,callhistory, 'CLAMP.RANGE',v,a,b)
    return generalfloatmath(ng,callhistory, 'CLAMP.RANGE',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range.\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range.\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def mapl(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','LINEAR',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','LINEAR',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.")
@user_doc(nexscript="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def mapst(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    step:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y,step):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','STEPPED',v,a,b,x,y,step)
    return generalmaprange(ng,callhistory, 'FLOAT','STEPPED',v,a,b,x,y,step)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def mapsmo(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','SMOOTHSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','SMOOTHSTEP',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_paramError(UserParamError)
def mapsmoo(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory, 'FLOAT_VECTOR','SMOOTHERSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory, 'FLOAT','SMOOTHERSTEP',v,a,b,x,y)

@user_domain('nexscript')
@user_doc(nexscript="Position Attribute.\nGet the GeometryNode 'Position' SocketVector input attribute.")
def getp(ng, callhistory,
    ) -> sVec:
    uniquename = 'I|GetPosition' #This one is a singleton, no need for callhistory..
    node = ng.nodes.get(uniquename)
    if (node is None):
        node = ng.nodes.new('GeometryNodeInputPosition')
        node.name = node.label = uniquename
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*1
    return node.outputs[0]

@user_domain('nexscript')
@user_doc(nexscript="Normal Attribute.\nGet the GeometryNode 'Normal' SocketVector input attribute.")
def getn(ng, callhistory,
    ) -> sVec:
    uniquename = 'I|GetNormal' #This one is a singleton, no need for callhistory..
    node = ng.nodes.get(uniquename)
    if (node is None):
        node = ng.nodes.new('GeometryNodeInputNormal')
        node.name = node.label = uniquename
        node.location = ng.nodes["Group Input"].location
        node.location.y += 65*2
    return node.outputs[0]

#TODO later, need NexInt
# @user_domain('nexscript')
# @user_doc(nexscript="ID Attribute.\nGet the GeometryNode 'ID' SocketInt input attribute.")
# def getid(ng, callhistory,
#     ) -> sInt:
#     """
#     Retrieve the 'ID' attribute in Geometry Nodes as a SocketInt.
#     This node will give each point/instance an integer ID if available.
#     """
#     # Use a unique name to avoid creating duplicates on re-runs
#     uniquename = 'F|GetID' if (callhistory is not None) else None
#     node = None

#     if uniquename:
#         node = ng.nodes.get(uniquename)

#     if node is None:
#         node = ng.nodes.new('GeometryNodeInputID')  
#         if uniquename:
#             node.name = node.label = uniquename
#         # Place it near the Group Input for convenience
#         if "Group Input" in ng.nodes:
#             node.location = ng.nodes["Group Input"].location
#             node.location.y += 65 * 3
#         ng.nodes.active = node

#     return node.outputs[0]  # 'ID' output (Int)


# @user_domain('nexscript')
# @user_doc(nexscript="Index Attribute.\nGet the GeometryNode 'Index' SocketInt input attribute.")
# def getindex(ng, callhistory,
#     ) -> sInt:
#     """
#     Retrieve the 'Index' attribute in Geometry Nodes as a SocketInt.
#     This node will output the index of each element (e.g., each point).
#     """
#     uniquename = 'F|GetIndex' if (callhistory is not None) else None
#     node = None

#     if uniquename:
#         node = ng.nodes.get(uniquename)

#     if node is None:
#         node = ng.nodes.new('GeometryNodeInputIndex')
#         if uniquename:
#             node.name = node.label = uniquename
#         # Place it near the Group Input for convenience
#         if "Group Input" in ng.nodes:
#             node.location = ng.nodes["Group Input"].location
#             node.location.y += 65 * 4
#         ng.nodes.active = node

#     return node.outputs[0]  # 'Index' output (Int)


# @user_domain('nexscript')
# @user_doc(nexscript="Named Attribute.\nGet the GeometryNode 'Named Attribute' with a chosen type.\nNote: This node was removed in newer Blender versions (3.5+).")
# def getnamedattr(ng, callhistory,
#     name:str = "my_attribute",
#     data_type:str = "FLOAT",
#     ) -> bpy.types.NodeSocket:
#     """
#     Retrieve a named attribute (e.g., a custom attribute on points, edges, etc.).
#     - name:      The string name of the attribute.
#     - data_type: One of 'FLOAT', 'INT', 'BOOLEAN', 'VECTOR', 'COLOR', etc. (depending on your Blender version).
    
#     Returns the primary output (the actual attribute).
#     For older Blender versions: 'GeometryNodeInputNamedAttribute' was used.
#     For Blender 3.5+: This node was removed in favor of the new fields system or the 'Capture Attribute' node.
#     """
#     # Use a unique name so it can be reused if we run multiple times
#     uniquename = f'F|GetNamedAttr({name})' if (callhistory is not None) else None
#     node = None

#     if uniquename:
#         node = ng.nodes.get(uniquename)

#     if node is None:
#         # If your version of Blender still has this node:
#         node = ng.nodes.new('GeometryNodeInputNamedAttribute')
#         if uniquename:
#             node.name = node.label = uniquename
#         node.data_type = data_type  # e.g. 'FLOAT', 'VECTOR', 'INT', 'BOOLEAN', ...
#         if "Group Input" in ng.nodes:
#             node.location = ng.nodes["Group Input"].location
#             node.location.y += 65 * 5
#         ng.nodes.active = node

#     # Always ensure the attribute name is set
#     if node.inputs.get("Name"):
#         if node.inputs["Name"].default_value != name:
#             node.inputs["Name"].default_value = name

#     # The node has multiple outputs:
#     #  - "Attribute"  (the actual data, index 0)
#     #  - "Exists"     (bool, index 1)
#     return node.outputs[0]
