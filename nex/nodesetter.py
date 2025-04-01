# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE ABOUT: this module gather all kind of math function between sockets and/or between sockets and python types.
#  When executing these functions, it will create and link new nodes automatically, from sockets to sockets and return another socket.

#N OTE CODE INFO: 
# Cross Compatibility:
# - be carreful with 'mathex' user domain. These functions are cross compatible for all editors.
# Move Module:
# - perhaps we should move this module, from accepting NodeSocket types, to accepting NexTypes only?
# - the problem with NodeSocket type is that there are many sub-type that are annoying to deal with.. sVecT, sVecXYZ ect..
#   All our function are strict typed. So when an user pass a SocketFloatAngle to a function designed for SocketFloat, will raise a type error..
#   And there's many useless subtype going on in the api..
# Internal Params:
# - ng, and callhistory are internal parameters, user is not exposed to them.
# - The 'callhistory' internal parameter is an important functonality! Thanks to it, we can define a stable tag id for nodes generation,
#    this functionality let us re-execute the functions to update potential .default_value without rebuilding the entire nodetree nodes and links again.
# - The problem with this technique, is that calling functions often ex Vec.x Col.r ect.. will create a new node on each getter operation. 
#   To resolved superflus creation of node, the 'callhistory' functionality could perhaps create tags not based on function call, but based on function AND their arguments.
#   The tag could look like F|funcname(ArgUniqueID1,ArgUniqueID2,ArgUniqueID3). This was implemented previously but we quickly reached limit of function name char[64]...
#   this unique_tag would also need to support python types that may change on each execution (if the user is passing #frame or a obj.location to the function, we
#   need to find a way to recognize this value cross execution which is no easy task).. so there's a lot of challenge. Perhaps not worth just fixing redudant nodes.

# TODO 
# - see todos for functions ideas and improvements below.
# Ideas:
# - sign( function )
# - genetic data.inverted() for all types.
# - More color functions
#   - gamma(col, gammavalue) Adjusts the gamma of a color. Internally, each channel is raised to the power of 1/gamma_value.
#   - Col.inverted() hueshift(col, angle)
#   - contrast(col, fac) =((c−0.5)×f+0.5)
#   - blend(mode,colA,colB) overlay/screen/ ect with optional factor??
# - More vector functions
#   - anglebetween(vA, vB) refract()
# - bitwise all(**values) any(**values)
# - improve generalbatchcompare: give system to alleq.. isbetween etc.. almosteq isbetween allbetween
# - check interesting houdnini Vex functions
# - sum(...), avg(...), min(...), max(...) over arrays sort( accumulate(
# - support min() max() on single SocketMatrix, SocketRotation, SocketVector, SocketColor? dunder class method for it __min__ __max__ ??
# - if the switch() value is not a NodeSocket but a python value, perhaps we could simply do noodle linking manipulations, 
#   and support switch between any types! (contrary to switch only for same type)
# - integer math optimization
# - noise2d(x, y) noise3d(x, y, z) randgauss(mean, stddev, seed, ID) Returns a random float from a Gaussian distribution with mean, stddev
# - fit fit01 fit10 for clampl alternative similar to Houdini Vex

import bpy 

import re
import inspect
import functools
import typing
from mathutils import Vector, Matrix, Quaternion, Color

from ..nex.pytonode import py_to_Vec3, py_to_Mtx16, py_to_RGBA
from ..utils.node_utils import link_sockets, frame_nodes, create_constant_input
from ..utils.fct_utils import is_annotation_compliant, alltypes, anytype, ColorRGBA

#shortcuts for socket types
sAny = bpy.types.NodeSocket
sBoo = bpy.types.NodeSocketBool
sInt = bpy.types.NodeSocketInt
sFlo = bpy.types.NodeSocketFloat
sCol = bpy.types.NodeSocketColor
sRot = bpy.types.NodeSocketRotation
sVec = bpy.types.NodeSocketVector

#experimental support for matrix socket
try:    sMtx = bpy.types.NodeSocketMatrix
except: sMtx = bpy.types.NodeSocketFloat ; print("WARNING: Experimental Support for 4.1")

#tell me why these type exist? what's the reason? Very annoying to support..
sVecXYZ = bpy.types.NodeSocketVectorXYZ
sVecT = bpy.types.NodeSocketVectorTranslation

NODE_YOFF, NODE_XOFF = 90, 70
TAGGED = []


def convert_pyargs(*args, toVector=False, toFloat=False, toBool=False, toRGBA=False, toMatrix=False,) -> tuple:
    """convert the passed args to python types ignoring sockets"""
    #NOTE the wrap_socketfunctions already should've convert py parameters of a functions when in use in a NexScript.
    if (toFloat):  return [float(a)       if (type(a) in {int,bool})                              else a for a in args]
    if (toBool):   return [bool(a)        if (type(a) in {int,float})                             else a for a in args]
    if (toVector): return [py_to_Vec3(a)  if (type(a) in {int,bool,float,Vector,Color,ColorRGBA}) else a for a in args]
    if (toRGBA):   return [py_to_RGBA(a)  if (type(a) in {int,bool,float,Vector,Color})           else a for a in args]
    if (toMatrix): return [py_to_Mtx16(a) if (type(a) in {int,bool,float,Matrix})                 else a for a in args]
    return None

def containsVecs(*args) -> bool:
    return anytype(*args ,types=(sVec, sVecXYZ, sVecT, Vector),)

def containsCols(*args) -> bool:
    return anytype(*args ,types=(sCol, Color, ColorRGBA),)

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
        funcs = [functools.partial(f, *partialdefaults,) for f in funcs]

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


def generalnewnode(ng, callhistory, 
    unique_tag:str,
    node_type:str,
    *inparams, #passed inputs should correspond to node.inputs in an orderly manner
    ) -> tuple:
    """generic operation for adding anew node."""

    uniquename = get_unique_name(unique_tag,callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)

        node = ng.nodes.new(node_type)

        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    for i, val in enumerate(inparams):
        match val:

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case _:
                raise Exception("Rest of Implementation Needed")
    
    return tuple(node.outputs)

def generalreroute(ng, callhistory, socket,):
    """generic operation for adding a reroute."""

    uniquename = get_unique_name('Reroute',callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)

        node = ng.nodes.new('NodeReroute')

        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    if needs_linking:
        link_sockets(socket, node.inputs[0])

    return node.outputs[0]

def generalfloatmath(ng, callhistory,
    operation_type:str,
    val1:sFlo|sInt|sBoo|float|int|None=None,
    val2:sFlo|sInt|sBoo|float|int|None=None,
    val3:sFlo|sInt|sBoo|float|int|None=None,
    ) -> sFlo:
    """generic operation for adding a float math node and linking. (also support clamp node)."""

    match ng.type:
        case 'GEOMETRY'|'SHADER':
            MathNodeType = 'ShaderNodeMath'
            ClampNodeType = 'ShaderNodeClamp'
        case 'COMPOSITING':
            MathNodeType = 'CompositorNodeMath'
            ClampNodeType = 'NotAvailable'

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
            node = ng.nodes.new(ClampNodeType)
            clamp_type = operation_type.replace('CLAMP.','')
            node.clamp_type = clamp_type
        else:
            node = ng.nodes.new(MathNodeType)
            node.operation = operation_type
            node.use_clamp = False

        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    for i,val in enumerate(args):
        match val:

            case _ if issubclass(type(val),sAny):
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
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector|None=None,
    val3:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector|None=None,
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

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float() | int() | bool():
                val = float(val) if (type(val) is bool) else val
                val = Vector((val,val,val))
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise Exception(f"InternalError. Function generalvecmath('{operation_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[outidx]

@user_domain('nexclassmethod')
def generalcolormath(ng, callhistory, #TODO do generalcolormix instead, later for color functions..
    blend_type:str,
    colA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|ColorRGBA|Vector,
    colB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|ColorRGBA|Vector,
    factor:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|None=1.0,
    ) -> sCol:
    """Generic operation for adding a vector math node and linking."""

    if not alltypes(colA, colB, types=(sFlo,sInt,sBoo,sVec,sVecXYZ,sVecT,sCol,float,int,bool,ColorRGBA,Vector),):
        raise Exception(f"InternalError. Function generalcolormath('{blend_type}') did not recieved color compatible type. Recieved '{type(colA).__name__}' and '{type(colB).__name__}'. This Error should've been catched previously!")

    uniquename = get_unique_name('ColorMath',callhistory)
    node = None
    needs_linking = False
    indexes = (0,6,7)
    args = (factor, *convert_pyargs(colA, colB, toRGBA=True,),)

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0, 200)
        node = ng.nodes.new('ShaderNodeMix')
        node.data_type = 'RGBA'
        node.blend_type = blend_type
        node.clamp_result = False #clamp_result
        node.clamp_factor = False #clamp_factor
        node.location = location
        ng.nodes.active = node

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename
    
    for i,val in zip(indexes, args):
        match val:

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case ColorRGBA():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val[:]
                    assert_purple_node(node)

            case float() | int() | bool():
                if type(val) is bool:
                    val = float(val)
                if node.inputs[i].default_value != val:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise Exception(f"InternalError. Function generalcolormath('{blend_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[2]

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

            case _ if issubclass(type(val),sAny):
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
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA|None=None,
    ) -> sFlo|sVec|sCol:
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

        match ng.type:
            case 'GEOMETRY'|'SHADER':
                node = ng.nodes.new('ShaderNodeMix')
                node.data_type = data_type
                node.clamp_factor = False
                #always mix non-uniform. floats will be converted to vec anyway..
                if (data_type=='VECTOR'):
                    node.factor_mode = 'NON_UNIFORM'
            case 'COMPOSITING':
                node = ng.nodes.new('CompositorNodeMixRGB')
                node.use_clamp = False
                data_type = '*COMPOSITORSPECIAL*'

        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    match data_type:
        case 'FLOAT':
            outidx = 0
            indexes = (0,2,3)
            args = convert_pyargs(*args, toFloat=True,)
        case 'VECTOR':
            outidx = 1
            indexes = (1,4,5)
            args = convert_pyargs(*args, toVector=True,)
        case 'RGBA':
            outidx = 2
            indexes = (0,6,7)
            args = (factor, *convert_pyargs(val1, val2, toRGBA=True,),)
        case '*COMPOSITORSPECIAL*':
            outidx = 0
            indexes = (0,1,2)
            args = (factor, val1, val2,)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector() | ColorRGBA():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case float():
                if type(val) is bool:
                    val = float(val)
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise Exception(f"InternalError. Function generalmix('{data_type}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[outidx]

def generalentryfloatmath(ng, callhistory,
    sepa_data_type:str,
    operation_type:str,
    A:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    fB:sFlo|sInt|sBoo|float|int|None=None,
    fC:sFlo|sInt|sBoo|float|int|None=None,
    ) -> sVec:
    """Apply regular float math to each element of a separated enement, rely on the general separate and combine functions.
    ex: newvA = func(vA.x,b,c), func(vA.y,b,c), func(vA.z,b,c)"""

    floats = generalcombsepa(ng,callhistory,'SEPARATE',sepa_data_type, A,)
    sepnode = floats[0].node

    newfloats = []
    for i,fA in enumerate(floats):
        ng.nodes.active = sepnode
        fN = generalfloatmath(ng, callhistory, operation_type, fA,fB,fC,)
        newfloats.append(fN)
        continue

    r = generalcombsepa(ng,callhistory,'COMBINE',sepa_data_type, newfloats,)
    frame_nodes(ng, floats[0].node, r.node, label='EntryWise FloatMath',)

    return r

def generalparrallelvecfloatmath(ng, callhistory,
    operation_type:str,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sVec|sVecXYZ|sVecT|Vector,
    ) -> sVec:
    """Apply regular float math to each element of the vector.  newvA = func(vA.x,vB.x), func(vA.y,vB.y), func(vA.z,vB.z)  """
    #NOTE this one is exclusive for Vectors, perhaps we can make it any sepa/comb type compatible like function above later as well.

    setA = generalcombsepa(ng,callhistory,'SEPARATE','VECTORXYZ', vA,)
    setB = generalcombsepa(ng,callhistory,'SEPARATE','VECTORXYZ', vB,)
    
    #arrange nodes
    if (not setA[0].node.parent):
        setB[0].node.location = setA[0].node.location 
        setB[0].node.location.y -= 200

    args = (setA[0],setB[0]), (setA[1],setB[1]), (setA[2],setB[2])

    results = []
    for a in args:
        op = generalfloatmath(ng, callhistory, operation_type, *a,)
        results.append(op)
    
    #arrange nodes
    if (not results[0].node.parent):
        results[2].node.location = results[1].node.location = results[0].node.location
        results[0].node.location.y += 400
        results[1].node.location.y += 200
        results[2].node.location.y += 0

    rvec = combixyz(ng, callhistory, *results)
    
    #arrange nodes
    if (not rvec.node.parent):
        rvec.node.location.y = results[1].node.location.y + 45
    
    frame_nodes(ng, setA[0].node, results[0].node, results[2].node, rvec.node, label='Vec Parrallel FloatMath',)

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

        match ng.type:
            case 'GEOMETRY'|'SHADER':
                node = ng.nodes.new('ShaderNodeMapRange')
                node.data_type = data_type
                node.interpolation_type = interpolation_type
                node.clamp = False
            case 'COMPOSITING':
                node = ng.nodes.new('CompositorNodeMapRange')
                node.use_clamp = False

        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link
        
        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    match data_type:
        case 'FLOAT':
            outidx = 0
            indexes = (0,1,2,3,4,5)
        case 'FLOAT_VECTOR':
            outidx = 1
            indexes = (6,7,8,9,10,11)
            args = convert_pyargs(*args, toVector=True,)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case _ if issubclass(type(val),sAny):
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
        new = generalfloatmath(ng,callhistory,fullopname,a,b)
        a = new
        to_frame.append(new.node)
        continue

    frame_nodes(ng, *to_frame, label='Batch MinMax',)
    return new

def generalcompare(ng, callhistory,
    data_type:str,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA|None=None,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA|None=None,
    epsilon:sFlo|sInt|sBoo|float|int|None=None,
    ) -> sBoo:
    """generic operation for comparison operation and linking."""

    uniquename = get_unique_name('Compa',callhistory)
    node = None
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
        node.inputs[12].default_value = 0 #epsilon always set on 0 by default.
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    match data_type:
        case 'FLOAT':
            indexes = (0,1,12)
            args = (*convert_pyargs(val1,val2, toFloat=True,), epsilon,)
        case 'VECTOR':
            indexes = (4,5,12)
            args = (*convert_pyargs(val1,val2, toVector=True,), epsilon,)
        case 'RGBA':
            indexes = (6,7,12)
            args = (*convert_pyargs(val1,val2, toRGBA=True,), epsilon,)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case Vector() | ColorRGBA():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val[:]
                    assert_purple_node(node)

            case float():
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case None: pass

            case _: raise Exception(f"InternalError. Function generalcompare('{data_type}','{operation}') recieved unsupported type '{type(val).__name__}'. This Error should've been catched previously!")

    return node.outputs[0]

def generalboolmath(ng, callhistory,
    operation:str,
    val1:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    val2:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool|None=None,
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

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case bool():
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
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    ) -> sBoo:
    """generic operation to batch comparison operation between a range or given float compatible itterable"""

    match operation_type:
        case 'alleq':
            opefunc = iseq
        case _: raise Exception(f"Unsupported operation_type '{operation_type}' passed to generalbatchcompare().")

        # TODO support other batch comparison method?
        # Some of them are a bit more complicated. Because on some occation we cannot simply chain comparison, 
        # ALL members will needs to be cross compared, not simply one after another.
        # case 'alluneq':
        # case 'allless':
        # case 'alllesseq':
        # case 'allgreater':
        # case 'allgreatereq':
        # case 'allbetween':
        # case 'allbetweeneq':

    to_frame = []
    compared = []

    #create comparison chain
    for i,o in enumerate(values):
        if (i==0):
            continue
        a = values[i-1]
        b = o
        compa = opefunc(ng,callhistory,a,b)
        to_frame.append(compa.node)
        compared.append(compa)
        continue

    #add all bool result together
    a = compared[0]
    for i,o in enumerate(compared):
        if (i==0):
            continue
        b = o
        andop = add(ng,callhistory,a,b)
        a = andop
        to_frame.append(andop.node)
        #adjust location on init
        if (not andop.node.parent):
            andop.node.location = b.node.location
            andop.node.location.y += 250
        continue

    #if all equals addition of all bool should be of len of all values
    final = iseq(ng,callhistory,a,len(compared))
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
        case 'matrixmult':   nodetype, args, outidx = 'FunctionNodeMatrixMultiply',     (mat1,mat2,), 0
        case 'transformloc': nodetype, args, outidx = 'FunctionNodeTransformPoint',     (vec1,mat1,), 0
        case 'projectloc':   nodetype, args, outidx = 'FunctionNodeTransformDirection', (vec1,mat1,), 0
        case 'transformdir': nodetype, args, outidx = 'FunctionNodeProjectPoint',       (vec1,mat1,), 0
        case _: raise Exception(f"Unsupported operation_type '{operation_type}' passed to generalbatchcompare().")

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

            case _ if issubclass(type(val),sAny):
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
    input_data:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|sRot|sMtx|Vector|Quaternion|ColorRGBA|tuple|list|set,
    ) -> tuple|sVec|sMtx|sRot:
    """Generic function for creating 'combine' or 'separate' nodes, over multiple types"""

    node_types = {
        'SEPARATE': {
            'VECTORXYZ': 'ShaderNodeSeparateXYZ',
            'COLORRGB': 'FunctionNodeSeparateColor',
            'COLORHSV': 'FunctionNodeSeparateColor',
            'COLORHSL': 'FunctionNodeSeparateColor',
            'QUATWXYZ': 'FunctionNodeRotationToQuaternion',
            'QUATAXEANG': 'FunctionNodeRotationToAxisAngle',
            'MATRIXFLAT': 'FunctionNodeSeparateMatrix',
            'MATRIXTRANSFORM': 'FunctionNodeSeparateTransform',
            },
        'COMBINE': {
            'VECTORXYZ': 'ShaderNodeCombineXYZ',
            'COLORRGB': 'FunctionNodeCombineColor',
            'COLORHSV': 'FunctionNodeCombineColor',
            'COLORHSL': 'FunctionNodeCombineColor',
            'QUATWXYZ': 'FunctionNodeQuaternionToRotation',
            'QUATAXEANG': 'FunctionNodeAxisAngleToRotation',
            'MATRIXFLAT': 'FunctionNodeCombineMatrix',
            'MATRIXTRANSFORM': 'FunctionNodeCombineTransform',
            },
        }
    prefix_names = {
        'SEPARATE': {
            'VECTORXYZ': "Sepa VecXYZ",
            'COLORRGB': "Sepa ColRgb",
            'COLORHSV': "Sepa ColHsv",
            'COLORHSL': "Sepa ColHsl",
            'QUATWXYZ': "Sepa Quat",
            'QUATAXEANG': "Sepa Axe&Angle",
            'MATRIXFLAT': "Sepa MtxFlat",
            'MATRIXTRANSFORM': "Sepa Transf",
            },
        'COMBINE': {
            'VECTORXYZ': "Comb VecXYZ",
            'COLORRGB': "Comb ColRgb",
            'COLORHSV': "Comb ColHsv",
            'COLORHSL': "Comb ColHsl",
            'QUATWXYZ': "Comb Quat",
            'QUATAXEANG': "Comb Axe&Angle",
            'MATRIXFLAT': "Comb MtxFlat",
            'MATRIXTRANSFORM': "Comb Transf",
            },
        }

    assert operation_type in {'SEPARATE','COMBINE'}
    if (data_type not in node_types[operation_type]):
        raise ValueError(f"Unsupported data_type '{data_type}' for operation '{operation_type}'")

    nodetype = node_types[operation_type][data_type]
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
        if (data_type in {'COLORHSV','COLORHSL'}):
            node.mode = data_type.replace('COLOR','')
        node.location = location
        ng.nodes.active = node

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename

    match operation_type:

        case 'SEPARATE':
            val = input_data
            match val:

                case _ if issubclass(type(val),sAny):
                    if needs_linking:
                        link_sockets(val, node.inputs[0])

                case Vector() | ColorRGBA():
                    if node.inputs[0].default_value[:] != val[:]:
                        node.inputs[0].default_value = val[:]
                        assert_purple_node(node)

                case Quaternion(): #this is for sepaquat()
                    #unfortunately we are forced to create a new node, there's no quaternion .default_value option for type SocketRotation..
                    if (uniquename):
                          defval = create_constant_input(ng, 'FunctionNodeQuaternionToRotation', val, f"C|{uniquename}|def0")
                    else: defval = create_constant_input(ng, 'FunctionNodeQuaternionToRotation', val, f'C|{val[:]}')
                    if needs_linking:
                        link_sockets(defval, node.inputs[0])

                case Matrix(): #this is for sepamatrix()
                    #unfortunately we are forced to create a new node, there's no .default_value option for type SocketMatrix..
                    rowflatten = [v for row in val for v in row]
                    if (uniquename):
                          defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f"C|{uniquename}|def0")
                    else: defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f'C|{rowflatten[:]}') #enough space in nodename property? hmm. this function should't be used with no uniquename anyway..
                    if needs_linking:
                        link_sockets(defval, node.inputs[0])

                case _: raise Exception(f"InternalError. Type '{type(val).__name__}' not supported in separate() operation. Previous check should've pick up on this.")

            return tuple(node.outputs)

        case 'COMBINE':
            #input_data is Expected to get a tuple here!
            for i, val in enumerate(input_data):
                match val:

                    case _ if issubclass(type(val),sAny):
                        if needs_linking:
                            link_sockets(val, node.inputs[i])

                    case float() | int() | bool():
                        val = float(val) if (type(val) is bool) else val
                        if node.inputs[i].default_value != val:
                            node.inputs[i].default_value = val
                            assert_purple_node(node)

                    case Vector():
                        if node.inputs[i].default_value[:] != val[:]:
                            node.inputs[i].default_value = val
                            assert_purple_node(node)

                    case Quaternion(): #this is for combitransforms, will have a quaternion element
                        #unfortunately we are forced to create a new node, there's no quaternion .default_value option for type SocketRotation..
                        if (uniquename):
                              defval = create_constant_input(ng, 'FunctionNodeQuaternionToRotation', val, f"C|{uniquename}|def0")
                        else: defval = create_constant_input(ng, 'FunctionNodeQuaternionToRotation', val, f'C|{val[:]}')
                        if needs_linking:
                            link_sockets(defval, node.inputs[i])

                    case None: pass

                    case _: raise Exception(f"InternalError. Type '{type(val).__name__}' not supported in combine() operation. Previous check should've pick up on this.")

            return node.outputs[0]

def generalswitch(ng, callhistory,
    Type:str,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|sMtx|float|int|bool|Vector|Matrix,
    ) -> sFlo|sInt|sBoo|sVec|sCol|sMtx:

    #TODO support quaternion and color type here
    data_type_eq = {'float':'FLOAT', 'int':'INT', 'bool':'BOOLEAN', 'vec':'VECTOR', 'mat':'MATRIX','col':'RGBA'} #'quat':'ROTATION'
    if (Type not in data_type_eq.keys()):
        raise Exception(f"Function generalswitch recieved wrong type arg.")

    uniquename = get_unique_name('Switch', callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('GeometryNodeIndexSwitch')
        node.data_type = data_type_eq[Type]
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    #link index
    match idx:

        case _ if issubclass(type(idx),sAny):
            if needs_linking:
                link_sockets(idx, node.inputs[0])

        case float() | int() | bool():
            idx = int(idx)
            if (node.inputs[0].default_value!=idx):
                node.inputs[0].default_value = idx
                assert_purple_node(node)

    #create new slots if neccessary
    if len(values)>(len(node.inputs)-2):
        for _ in range(len(values)-2):
            node.index_switch_items.new()

    #convert passed params to correct python types
    converted = []
    for p in values:
        #if it's a socket, we don't need to convert values.
        if issubclass(type(p),sAny):
            converted.append(p)
            continue
        #duck type conversion
        try:
            match Type:
                case 'int':   converted.append(int(p))
                case 'float': converted.append(float(p))
                case 'bool':  converted.append(bool(p))
                case 'vec':   converted.append(py_to_Vec3(p))
                case 'col':   converted.append(py_to_RGBA(p))
                case 'mat':   converted.append(py_to_Mtx16(p))
        except:
            raise UserParamError(f"Function switch{Type}() Recieved an unexpected type '{type(p).__name__}'.")

    #link the rest
    for i,val in enumerate(converted):
        i += 1
        match val:

            case _ if issubclass(type(val),sAny):
                if needs_linking:
                    link_sockets(val, node.inputs[i])

            case int() | float() | bool():
                if (node.inputs[i].default_value!=val):
                    node.inputs[i].default_value = val
                    assert_purple_node(node)

            case Vector() | ColorRGBA():
                if node.inputs[i].default_value[:] != val[:]:
                    node.inputs[i].default_value = val[:]
                    assert_purple_node(node)

            case Matrix():
                #unfortunately we are forced to create a new node, there's no .default_value option for type SocketMatrix..
                rowflatten = [v for row in val for v in row]
                if (uniquename):
                      defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f"C|{uniquename}|def{i}")
                else: defval = create_constant_input(ng, 'FunctionNodeCombineMatrix', val, f'C|{rowflatten[:]}') #enough space in nodename property? hmm. this function should't be used with no uniquename anyway..
                if needs_linking:
                    link_sockets(defval, node.inputs[i])

            case None: pass

            case _: raise Exception(f"InternalError. Function switch{Type}() recieved unsupported type '{type(val).__name__}'.")

    return node.outputs[0]

def generalrandom(ng, callhistory,
    data_type:str,
    valmin:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    valmax:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    probability:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    seed:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ID:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ) -> sFlo|sVec:
    """generic operation for adding a mix node and linking."""

    assert data_type in {'FLOAT','INT','BOOLEAN','FLOAT_VECTOR',}

    uniquename = get_unique_name('Rnd',callhistory)
    node = None
    needs_linking = False

    if (uniquename):
        node = ng.nodes.get(uniquename)

    if (node is None):
        last = ng.nodes.active
        if (last):
              location = (last.location.x + last.width + NODE_XOFF, last.location.y - NODE_YOFF,)
        else: location = (0,200,)
        node = ng.nodes.new('FunctionNodeRandomValue')
        node.data_type = data_type
        node.location = location
        ng.nodes.active = node #Always set the last node active for the final link

        needs_linking = True
        if (uniquename):
            node.name = node.label = uniquename #Tag the node, in order to avoid unessessary build

    # Need to choose socket depending on node data_type (hidden sockets)
    match data_type:
        case 'FLOAT_VECTOR':
            outidx = 0
            indexes = (0,1,7,8)
            args = (*convert_pyargs(valmin,valmax, toVector=True,), ID, seed)
        case 'FLOAT':
            outidx = 1
            indexes = (2,3,7,8)
            args = (valmin, valmax, ID, seed)
        case 'INT':
            outidx = 2
            indexes = (4,5,7,8)
            args = (valmin, valmax, ID, seed)
        case 'BOOLEAN':
            outidx = 3
            indexes = (6,7,8)
            args = (probability, ID, seed)
        case _:
            raise Exception("Integration Needed")

    for i,val in zip(indexes,args):
        match val:

            case _ if issubclass(type(val),sAny):
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

# ooooo     ooo                                  oooooooooooo             .            
# `888'     `8'                                  `888'     `8           .o8            
#  888       8   .oooo.o  .ooooo.  oooo d8b       888        .ooooo.  .o888oo  .oooo.o 
#  888       8  d88(  "8 d88' `88b `888""8P       888oooo8  d88' `"Y8   888   d88(  "8 
#  888       8  `"Y88b.  888ooo888  888           888    "  888         888   `"Y88b.  
#  `88.    .8'  o.  )88b 888    .o  888           888       888   .o8   888 . o.  )88b 
#    `YbodP'    8""888P' `Y8bod8P' d888b         o888o      `Y8bod8P'   "888" 8""888P' 


class UserParamError(Exception):
    """Raise this error if the user didn't used the function parameter types properly"""
    def __init__(self, message):
        super().__init__(message)

class UserEditorContextError(Exception):
    """Raise this error if the user is using functions not available for his context"""
    def __init__(self, message):
        super().__init__(message)

def user_overseer(assert_editortype:set=None):
    """A decorator factory that takes a given error class and enforces type hints on the decorated function’s parameters.
    Handle error if user passed wrong parameter types. Or too much or too little params.
    - use 'assert_editortype' arg to ensure that the user is using a function in the correct editor type (ng.type). 
      If None, function is considered to be available for all editors"""

    def decorator(func):

        sig = inspect.signature(func)
        hints = typing.get_type_hints(func)

        #all functions below are designed with these two arguments as default. User shouldn't interact with these.
        internalparams = {'ng','callhistory'}

        def pretty(annot,istype=False):
            """better annotation for user error message"""
            if (istype):
                annot = type(annot).__name__
                annot = annot.replace('NodeSocket','Socket')
                return annot
            annot = str(annot)
            annot = annot.replace('bpy.types.','').replace('NodeSocket','Socket')
            annot = re.sub(r'\| bl_ext.*?\.nodebooster\.utils\.fct_utils\.ColorRGBA', '| ColorRGBA', annot) #internal type. User don't have access to ColorRGBA
            annot = annot.replace('SocketVectorXYZ | ','').replace('SocketVectorTranslation | ','') #internal dumb distinctions..
            annot = annot.replace(' |',',')
            annot = annot.replace("<class '",'').replace("'>",'')
            return annot

        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            #collect args of this function & remove strictly internal args from documentation
            allparamnames = list(func.__code__.co_varnames[:func.__code__.co_argcount])
            allparamnames = [n for n in allparamnames if (n not in internalparams)]
            parameternames = ', '.join(allparamnames)
            funcparamcount = len(allparamnames)

            #default arguments, always present. Hidden from user.
            if (assert_editortype):
                ngtype = args[0].type
                if (ngtype not in assert_editortype):
                    raise UserEditorContextError(f"Function {func.__name__}() is not available in the {ngtype.title()} editor.")

            #calling the bind function will raise an error if the user inputed wrong params. We are taking advantage of this to wrap the error to the user
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
            except TypeError as e:
                if ('too many positional arguments' in str(e)):
                    raise UserParamError(f"Function {func.__name__}({parameternames}) recieved extra Param(s). Expected {funcparamcount}. Recieved {len(args)-2}.")
                elif ('missing a required argument') in str(e):
                    raise UserParamError(f"Function {func.__name__}({parameternames}) needs more Param(s). Expected {funcparamcount}. Recieved {len(args)-2}.")
                raise

            # For each parameter, check annotation
            for param_name, param_value in bound.arguments.items():

                # Check if user gave a hint
                annotated_type = hints.get(param_name)
                if (annotated_type is None):
                    continue  # No hint == no checking

                # See if this param was defined as *args
                param = sig.parameters[param_name]
                if (param.kind == inspect.Parameter.VAR_POSITIONAL):

                    # param_value is a tuple of items
                    for item in param_value:
                        if (not is_annotation_compliant(item, annotated_type)):
                            raise UserParamError(f"Function {func.__name__}({parameternames}{', ' if parameternames else ''}{param_name}..) accepts Params of type {pretty(annotated_type)}. Recieved {pretty(item,istype=True)}.")
                else:
                    # Normal parameter check a single value
                    if (not is_annotation_compliant(param_value, annotated_type)):
                        if (funcparamcount>1):
                            raise UserParamError(f"Function {func.__name__}({parameternames}) accepts Param '{param_name}' of type {pretty(annotated_type)}. Recieved {pretty(param_value,istype=True)}.")
                        raise UserParamError(f"Function {func.__name__}({parameternames}) accepts Param of type {pretty(annotated_type)}. Recieved {pretty(param_value,istype=True)}.")

            return func(*bound.args, **bound.kwargs)

        wrapper.originalfunc = func
        return wrapper

    return decorator

# 88""Yb 888888  dP""b8 88   88 88        db    88""Yb     8b    d8    db    888888 88  88 
# 88__dP 88__   dP   `" 88   88 88       dPYb   88__dP     88b  d88   dPYb     88   88  88 
# 88"Yb  88""   Yb  "88 Y8   8P 88  .o  dP__Yb  88"Yb      88YbdP88  dP__Yb    88   888888 
# 88  Yb 888888  YboodP `YbodP' 88ood8 dP""""Yb 88  Yb     88 YY 88 dP""""Yb   88   88  88 

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Addition.\nEquivalent to the '+' symbol.")
@user_overseer()
def add(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec|sCol:
    if containsCols(a,b):
        return generalcolormath(ng,callhistory,'ADD',a,b)
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory,'ADD',a,b)
    return generalfloatmath(ng,callhistory,'ADD',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Subtraction.\nEquivalent to the '-' symbol.")
@user_overseer()
def sub(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec|sCol:
    if containsCols(a,b):
        return generalcolormath(ng,callhistory,'SUBTRACT',a,b)
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory,'SUBTRACT',a,b)
    return generalfloatmath(ng,callhistory,'SUBTRACT',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Multiplications.\nEquivalent to the '*' symbol.")
@user_overseer()
def mult(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec|sCol:
    if containsCols(a,b):
        return generalcolormath(ng,callhistory,'MULTIPLY',a,b)
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory,'MULTIPLY',a,b)
    return generalfloatmath(ng,callhistory,'MULTIPLY',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Division.\nEquivalent to the '/' symbol.")
@user_overseer()
def div(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec|sCol:
    if containsCols(a,b):
        return generalcolormath(ng,callhistory,'DIVIDE',a,b)
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory,'DIVIDE',a,b)
    return generalfloatmath(ng,callhistory,'DIVIDE',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="A Power N.\nEquivalent to the 'A**N' or '²' symbol.")
@user_overseer()
def pow(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    n:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(n):
        return generalparrallelvecfloatmath(ng,callhistory,'POWER',a,n)
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','POWER',a,n)
    return generalfloatmath(ng,callhistory,'POWER',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Logarithm A base N.")
@user_doc(nexscript="Logarithm A base N.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
@user_overseer()
def log(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    # for nexcript, math.log will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','LOGARITHM',a,n)
    return generalfloatmath(ng,callhistory,'LOGARITHM',a,n)

@user_domain('mathex','nexscript')
@user_doc(mathex="Square Root of A.")
@user_doc(nexscript="Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def sqrt(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.sqrt will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','SQRT',a)
    return generalfloatmath(ng,callhistory,'SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Inverse Square Root of A.")
@user_doc(nexscript="Inverse Square Root of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def invsqrt(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','INVERSE_SQRT',a)
    return generalfloatmath(ng,callhistory,'INVERSE_SQRT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="A Root N.\nEquivalent to doing 'A**(1/N)'.")
@user_doc(nexscript="A Root N.\nEquivalent to doing 'A**(1/N)'.\nSupports SocketFloat and entry-wise SocketVector if N is float compatible.")
@user_overseer()
def nroot(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    n:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    _x = div(ng,callhistory,1,n,)
    _r = pow(ng,callhistory,a,_x)
    frame_nodes(ng, _x.node, _r.node.parent if _r.node.parent else _r.node, label='nRoot',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Absolute of A.")
@user_overseer()
def abs(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|Vector|ColorRGBA,
    ) -> sFlo|sVec:
    if containsCols(a):
        return generalentryfloatmath(ng,callhistory,'COLORRGB','ABSOLUTE',a)
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'ABSOLUTE',a)
    return generalfloatmath(ng,callhistory,'ABSOLUTE',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Negate the value of A.\nEquivalent to the symbol '-x.'")
@user_overseer()
def neg(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    _r = sub(ng,callhistory,0,a)
    frame_nodes(ng, _r.node, label='Negate',)
    return _r

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Round a Float value.\nex: 1.49 will become 1\n1.51 will become 2.")
@user_overseer()
def round(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|Vector|ColorRGBA,
    ) -> sFlo|sVec:
    if containsCols(a):
        return generalentryfloatmath(ng,callhistory,'COLORRGB','ROUND',a)
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','ROUND',a)
    return generalfloatmath(ng,callhistory,'ROUND',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Floor a Float value.\nex: 1.51 will become 1\n-1.51 will become -2.")
@user_doc(nexscript="Floor a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.51 will become 1\n-1.51 will become 2.")
@user_overseer()
def floor(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.floor will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'FLOOR',a)
    return generalfloatmath(ng,callhistory,'FLOOR',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Ceil a Float value.\nex: 1.01 will become 2\n-1.99 will become -1.")
@user_doc(nexscript="Ceil a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.01 will become 2\n-1.99 will become 1.")
@user_overseer()
def ceil(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.ceil will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'CEIL',a)
    return generalfloatmath(ng,callhistory,'CEIL',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Trunc a Float value.\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_doc(nexscript="Trunc a Float value.\nSupports SocketFloat and entry-wise SocketVector.\n\nex: 1.99 will become 1\n-1.99 will become -1.")
@user_overseer()
def trunc(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.trunc will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','TRUNC',a)
    return generalfloatmath(ng,callhistory,'TRUNC',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="Fraction.\nThe fraction part of A.")
@user_doc(nexscript="Fraction.\nThe fraction part of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def frac(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'FRACTION',a)
    return generalfloatmath(ng,callhistory,'FRACT',a)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Modulo.\nEquivalent to the '%' symbol.")
@user_overseer()
def mod(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(a,b):
        return generalvecmath(ng,callhistory,'MODULO',a,b)
    return generalfloatmath(ng,callhistory,'MODULO',a,b)

#not covered in Nex.. user can do floor(A%B)
@user_domain('mathex')
@user_doc(mathex="Floored Modulo.")
@user_overseer()
def floormod(ng, callhistory,
    a:sFlo|sInt|sBoo,
    b:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory,'FLOORED_MODULO',a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Wrapping.\nWrap a value V to Range A B.")
@user_doc(nexscript="Wrapping.\nWrap a value V to Range A B.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def wrap(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b):
        return generalvecmath(ng,callhistory,'WRAP',v,a,b)
    return generalfloatmath(ng,callhistory,'WRAP',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Snapping.\nSnap a value V to the nearest increament I.")
@user_doc(nexscript="Snapping.\nSnap a value V to the nearest increament I.\nSupports SocketFloat and SocketVector.")
@user_overseer()
def snap(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    i:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,i):
        return generalvecmath(ng,callhistory,'SNAP',v,i)
    return generalfloatmath(ng,callhistory,'SNAP',v,i)

@user_domain('mathex','nexscript')
@user_doc(mathex="PingPong.\nWrap a value and every other cycles at cycle Scale.")
@user_doc(nexscript="PingPong.\nWrap a value and every other cycles at cycle Scale.\nSupports SocketFloat and entry-wise SocketVector if scale is float compatible.")
@user_overseer()
def pingpong(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    scale:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec:
    if containsVecs(v):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','PINGPONG',v,scale)
    return generalfloatmath(ng,callhistory,'PINGPONG',v,scale)

#covered internally in nexscript via python dunder overload
@user_domain('mathex','nexclassmethod')
@user_doc(mathex="Floor Division.\nEquivalent to the '//' symbol.")
@user_overseer()
def floordiv(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    _x = div(ng,callhistory,a,b)
    _r = floor(ng,callhistory,_x)
    frame_nodes(ng, _x.node, _r.node, label='FloorDiv',)
    return _r

# 888888 88""Yb 88  dP""b8  dP"Yb  
#   88   88__dP 88 dP   `" dP   Yb 
#   88   88"Yb  88 Yb  "88 Yb   dP 
#   88   88  Yb 88  YboodP  YbodP  

@user_domain('mathex','nexscript')
@user_doc(mathex="The Sine of A.")
@user_doc(nexscript="The Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def sin(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.sin will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'SINE',a)
    return generalfloatmath(ng,callhistory,'SINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Cosine of A.")
@user_doc(nexscript="The Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def cos(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.cos will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'COSINE',a)
    return generalfloatmath(ng,callhistory,'COSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Tangent of A.")
@user_doc(nexscript="The Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def tan(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec|float:
    # for nexcript, math.tan will be called if given param is python float or int
    if containsVecs(a):
        return generalvecmath(ng,callhistory,'TANGENT',a)
    return generalfloatmath(ng,callhistory,'TANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arcsine of A.")
@user_doc(nexscript="The Arcsine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def asin(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.asin will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','ARCSINE',a)
    return generalfloatmath(ng,callhistory,'ARCSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arccosine of A.")
@user_doc(nexscript="The Arccosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def acos(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.acos will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','ARCCOSINE',a)
    return generalfloatmath(ng,callhistory,'ARCCOSINE',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Arctangent of A.")
@user_doc(nexscript="The Arctangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def atan(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.atan will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','ARCTANGENT',a)
    return generalfloatmath(ng,callhistory,'ARCTANGENT',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Sine of A.")
@user_doc(nexscript="The Hyperbolic Sine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def sinh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.sinh will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','SINH',a)
    return generalfloatmath(ng,callhistory,'SINH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Cosine of A.")
@user_doc(nexscript="The Hyperbolic Cosine of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def cosh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.cosh will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','COSH',a)
    return generalfloatmath(ng,callhistory,'COSH',a)

@user_domain('mathex','nexscript')
@user_doc(mathex="The Hyperbolic Tangent of A.")
@user_doc(nexscript="The Hyperbolic Tangent of A.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def tanh(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.tanh will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','TANH',a)
    return generalfloatmath(ng,callhistory,'TANH',a)

#    db    88b 88  dP""b8 88     888888 .dP"Y8 
#   dPYb   88Yb88 dP   `" 88     88__   `Ybo." 
#  dP__Yb  88 Y88 Yb  "88 88  .o 88""   o.`Y8b 
# dP""""Yb 88  Y8  YboodP 88ood8 888888 8bodP' 

@user_domain('mathex')
@user_doc(mathex="To Radians.\nConvert a value from Degrees to Radians.")
@user_overseer()
def rad(ng, callhistory,
    a:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory,'RADIANS',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="To Radians.\nConvert a value from Degrees to Radians.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def radians(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.radians will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','RADIANS',a)
    return generalfloatmath(ng,callhistory,'RADIANS',a)

@user_domain('mathex')
@user_doc(mathex="To Degrees.\nConvert a value from Radians to Degrees.")
@user_overseer()
def deg(ng, callhistory,
    a:sFlo|sInt|sBoo,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory,'DEGREES',a)

#same as above, just different user fct name.
@user_domain('nexscript')
@user_doc(nexscript="To Degrees.\nConvert a value from Radians to Degrees.\nSupports SocketFloat and entry-wise SocketVector.")
@user_overseer()
def degrees(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|Vector,
    ) -> sFlo|sVec:
    # for nexcript, math.degrees will be called if given param is python float or int
    if containsVecs(a):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','DEGREES',a)
    return generalfloatmath(ng,callhistory,'DEGREES',a)

# Yb    dP 888888  dP""b8 888888  dP"Yb  88""Yb 
#  Yb  dP  88__   dP   `"   88   dP   Yb 88__dP 
#   YbdP   88""   Yb        88   Yb   dP 88"Yb  
#    YP    888888  YboodP   88    YbodP  88  Yb 

@user_domain('nexscript')
@user_doc(nexscript="Vector Cross Product.\nThe cross product between vector A an B.")
@user_overseer()
def cross(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'CROSS_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Dot Product.\nA dot B.")
@user_overseer()
def dot(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'DOT_PRODUCT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject A onto B.")
@user_overseer()
def project(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Faceforward.\nFaceforward operation between a given vector, an incident and a reference.")
@user_overseer()
def faceforward(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vI:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vR:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'FACEFORWARD',vA,vI,vR)

@user_domain('nexscript')
@user_doc(nexscript="Vector Reflection.\nReflect A onto B.")
@user_overseer()
def reflect(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'PROJECT',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Distance.\nThe distance between location A & B.")
@user_overseer()
def distance(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vB:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory,'DISTANCE',vA,vB)

@user_domain('nexscript')
@user_doc(nexscript="Vector Normalization.\nNormalize the values of a vector A to fit a 0-1 range.")
@user_overseer()
def normalize(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector,
    ) -> sVec:
    return generalvecmath(ng,callhistory,'NORMALIZE',vA)

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def vectocolor(ng, callhistory,
    vA:sVec|sVecXYZ|sVecT,
    ) -> sCol:
    x,y,z = sepaxyz(ng,callhistory,vA)
    _r = combicolor(ng,callhistory,x,y,z,1.0)
    frame_nodes(ng, x.node, _r.node, label="VecToCol",)
    return _r

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def vectorot(ng, callhistory,
    vA:sVec|sVecXYZ|sVecT,
    ) -> sRot:
    return generalnewnode(ng,callhistory,'VecToRot','FunctionNodeEulerToRotation',vA)[0]

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def length(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo:
    return generalvecmath(ng,callhistory,'LENGTH',vA)

@user_domain('nexscript')
@user_doc(nexscript="Separate Vector.\nSeparate a SocketVector into a tuple of 3 XYZ SocketFloat.\n\nTip: you can use python slicing notations 'myX, myY, myZ = vA' instead.")
@user_overseer()
def sepaxyz(ng, callhistory,
    vA:sVec|sVecXYZ|sVecT|sCol|float|int|Vector,
    ) -> tuple:
    if (type(vA) in {float, int}): 
        vA = Vector((vA,vA,vA))
    return generalcombsepa(ng,callhistory,'SEPARATE','VECTORXYZ',vA)

@user_domain('nexscript')
@user_doc(nexscript="Combine Vector.\nCombine 3 XYZ SocketFloat, SocketInt or SocketBool into a SocketVector.")
@user_overseer()
def combixyz(ng, callhistory,
    fX:sFlo|sInt|sBoo|float|int,
    fY:sFlo|sInt|sBoo|float|int,
    fZ:sFlo|sInt|sBoo|float|int,
    ) -> sVec:
    return generalcombsepa(ng,callhistory,'COMBINE','VECTORXYZ',(fX,fY,fZ),)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Euler).\nRotate a given Vector A with euler angle radians E, at optional center C.")
@user_overseer()
def roteuler(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vE:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vC:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    ) -> sVec:
    return generalverotate(ng, callhistory,'EULER_XYZ',False,vA,vC,None,None,vE)

@user_domain('nexscript')
@user_doc(nexscript="Vector Rotate (Axis).\nRotate a given Vector A from defined axis X & angle radians F, at optional center C.")
@user_overseer()
def rotaxis(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    vX:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    fA:sFlo|sInt|sBoo|float|int,
    vC:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector|None=None,
    ) -> sVec:
    return generalverotate(ng, callhistory,'AXIS_ANGLE',False,vA,vC,vX,fA,None)

#  dP""b8  dP"Yb  88      dP"Yb  88""Yb 
# dP   `" dP   Yb 88     dP   Yb 88__dP 
# Yb      Yb   dP 88  .o Yb   dP 88"Yb  
#  YboodP  YbodP  88ood8  YbodP  88  Yb 

@user_domain('nexscript')
@user_doc(nexscript="Separate Color.\nSeparate a SocketColor into a tuple of 4 SocketFloat depending on the optionally passed mode in 'RGB','HSV','HSL'.\nThe fourth element of the tuple must be the alpha.\n\nTip: you can use python slicing notations instead.")
@user_overseer()
def sepacolor(ng, callhistory,
    colA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    mode:str='RGB',
    ) -> tuple:
    assert mode in {'RGB','HSV','HSL'}, f"{mode} not in 'RGB','HSV','HSL'"

    if (type(colA) in {float, int}):
        colA = ColorRGBA(colA, colA, colA, 1.0)
    elif (type(colA) in {Vector,}):
        colA = ColorRGBA(colA[0], colA[1], colA[2], 1.0)

    return generalcombsepa(ng,callhistory,'SEPARATE',f'COLOR{mode}',colA)

@user_domain('nexscript')
@user_doc(nexscript="Combine Color.\nCombine 4 SocketFloat, SocketInt or SocketBool into a SocketColor depending on the optionally passed mode in 'RGB','HSV','HSL'.\nThe fourth element of the tuple must be the alpha.")
@user_overseer()
def combicolor(ng, callhistory,
    f1:sFlo|sInt|sBoo|float|int,
    f2:sFlo|sInt|sBoo|float|int,
    f3:sFlo|sInt|sBoo|float|int,
    fA:sFlo|sInt|sBoo|float|int,
    mode:str='RGB',
    ) -> sCol:
    assert mode in {'RGB','HSV','HSL'}, f"{mode} not in 'RGB','HSV','HSL'"
    return generalcombsepa(ng,callhistory,'COMBINE',f'COLOR{mode}',(f1,f2,f3,fA),)

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def colortovec(ng, callhistory,
    colA:sCol,
    ) -> sVec:
    r,g,b,_ = sepacolor(ng,callhistory,colA)
    _r = combixyz(ng,callhistory,r,g,b)
    frame_nodes(ng, r.node, _r.node, label="ColToVec",)
    return _r

# @user_domain('nexclassmethod')
# def get_blackbody(ng, callhistory,
#     generalnode(ng, callhistory, 
#         unique_name:str,
#         node_type:str,
#         *inputs, #passed inputs should correspond to node.inputs in an orderly manner
#         )

# 8b    d8    db    888888 88""Yb 88 Yb  dP 
# 88b  d88   dPYb     88   88__dP 88  YbdP  
# 88YbdP88  dP__Yb    88   88"Yb  88  dPYb  
# 88 YY 88 dP""""Yb   88   88  Yb 88 dP  Yb 

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_overseer()
def matrixdeterminant(ng, callhistory,
    mA:sMtx,
    ) -> sFlo:
    return generalnewnode(ng,callhistory,'MtxDeter','FunctionNodeMatrixDeterminant',mA)[0]
    
#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_overseer()
def matrixinvert(ng, callhistory,
    mA:sMtx,
    ) -> sMtx:
    return generalnewnode(ng,callhistory,'MtxInvert','FunctionNodeInvertMatrix',mA)[0]

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_overseer()
def matrixisinvertible(ng, callhistory,
    mA:sMtx,
    ) -> sBoo:
    return generalnewnode(ng,callhistory,'MtxIsInv','FunctionNodeInvertMatrix',mA)[1]

#covered internally in nexscript via python prop or function
@user_domain('nexclassmethod')
@user_overseer()
def matrixtranspose(ng, callhistory,
    mA:sMtx,
    ) -> sMtx:
    return generalnewnode(ng,callhistory,'MtxTrans','FunctionNodeTransposeMatrix',mA)[0]

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def matrixmult(ng, callhistory,
    mA:sMtx|Matrix,
    mB:sMtx|Matrix,
    ) -> sMtx:
    return generalmatrixmath(ng,callhistory,'matrixmult',None,mA,mB)
        
@user_domain('nexscript')
@user_doc(nexscript="Vector Transform.\nTransform a location vector A by a given matrix B.\nWill return a VectorSocket.\n\nCould use notation 'mB @ vA' instead.")
@user_overseer()
def transformloc(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory,'transformloc',vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Projection.\nProject a location vector A by a given matrix B.\nWill return a VectorSocket.")
@user_overseer()
def projectloc(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory,'projectloc',vA,mB,None)

@user_domain('nexscript')
@user_doc(nexscript="Vector Direction Transform.\nTransform direction vector A by a given matrix B.\nWill return a VectorSocket.")
@user_overseer()
def transformdir(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector,
    mB:sMtx|Matrix,
    ) -> sVec:
    return generalmatrixmath(ng,callhistory,'transformdir',vA,mB,None)

# 88""Yb  dP"Yb  888888    db    888888 88  dP"Yb  88b 88 
# 88__dP dP   Yb   88     dPYb     88   88 dP   Yb 88Yb88 
# 88"Yb  Yb   dP   88    dP__Yb    88   88 Yb   dP 88 Y88 
# 88  Yb  YbodP    88   dP""""Yb   88   88  YbodP  88  Y8 

@user_domain('nexscript')
@user_doc(nexscript="Separate Quaternion.\nSeparate a SocketRotation into a tuple of 4 WXYZ SocketFloat.\n\nTip: you can use python slicing notations 'myX, myY, myZ, myW = qA' instead.")
@user_overseer()
def sepaquat(ng, callhistory,
    qA:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    ) -> tuple:
    #NOTE Special Case: an itter or len4 passed to a Nex function may automatically be interpreted as a RGBA color. But, it's a quaternion..
    if (type(qA)==ColorRGBA): qA = Quaternion(qA[:])
    return generalcombsepa(ng,callhistory,'SEPARATE','QUATWXYZ',qA)

@user_domain('nexscript')
@user_doc(nexscript="Combine Quaternion.\nCombine 4 WXYZ SocketFloat, SocketInt or SocketBool into a SocketRotation.")
@user_overseer()
def combiquat(ng, callhistory,
    fW:sFlo|sInt|sBoo|float|int,
    fX:sFlo|sInt|sBoo|float|int,
    fY:sFlo|sInt|sBoo|float|int,
    fZ:sFlo|sInt|sBoo|float|int,
    ) -> sRot:
    return generalcombsepa(ng,callhistory,'COMBINE','QUATWXYZ',(fW,fX,fY,fZ),)

@user_domain('nexscript')
@user_doc(nexscript="Separate Quaternion Rotation.\nSeparate a SocketRotation into a SocketVector Axis and a SocketFloat angle.")
@user_overseer()
def separot(ng, callhistory,
    qA:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    ) -> tuple:
    
    #NOTE Special Case: an itter or len4 passed to a Nex function may automatically be interpreted as a RGBA color. But, it's a quaternion..
    if (type(qA)==ColorRGBA): qA = Quaternion(qA[:])
    axis, angle = generalcombsepa(ng,callhistory,'SEPARATE','QUATAXEANG',qA)
    
    #NOTE Annoying Socket Type.. : 'angle' will be of type NodeSocketFloatAngle. our functions were not designed for that type. We already support VecXYZ & VecT..
    # So instead of adding a new SocketFloatAngle support for every single function, we add a dummy +0 operation to convert it into a socket we like instead..
    angle = generalfloatmath(ng,callhistory,'ADD',angle,0)
    
    return axis, angle

@user_domain('nexscript')
@user_doc(nexscript="Combine Quaternion Rotation.\nCombine a Vector axis and a Float Angle into a SocketRotation.")
@user_overseer()
def combirot(ng, callhistory,
    vA:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector,
    fA:sFlo|sInt|sBoo|float|int,
    ) -> sRot:
    if type(vA) in {float,int,bool}: vA = Vector((vA,vA,vA))
    return generalcombsepa(ng,callhistory,'COMBINE','QUATAXEANG',(vA,fA),)

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def rotinvert(ng, callhistory,
    qA:sRot,
    ) -> sRot:
    return generalnewnode(ng,callhistory,'InvertRot','FunctionNodeInvertRotation',qA)[0]

#covered internally in nexscript via property or function
@user_domain('nexclassmethod')
@user_overseer()
def rottoeuler(ng, callhistory,
    qA:sRot,
    ) -> sVec:
    euler = generalnewnode(ng,callhistory,'RotToEuler','FunctionNoderottoeuler',qA)[0]
    
    #NOTE Annoying Socket Type.. : 'euler' will be of type NodeSocketVectorEuler. our functions were not designed for that type. We already support VecXYZ & VecT..
    # So instead of adding a SocketType support for every single function, we add a dummy +0 operation to convert it into a socket we like instead..
    euler = generalvecmath(ng,callhistory,'ADD',euler,0)

    return euler

#  dP""b8  dP"Yb  8b    d8 88""Yb 88 .dP"Y8 
# dP   `" dP   Yb 88b  d88 88__dP 88 `Ybo." 
# Yb      Yb   dP 88YbdP88 88""Yb 88 o.`Y8b 
#  YboodP  YbodP  88 YY 88 88oodP 88 8bodP' 

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Flatten).\nSeparate a SocketMatrix into a tuple of 16 SocketFloat arranged by columns.")
@user_overseer()
def sepamatrix(ng, callhistory,
    mA:sMtx|Matrix,
    ) -> tuple:
    return generalcombsepa(ng,callhistory,'SEPARATE','MATRIXFLAT',mA)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Flatten).\nCombine an itterable containing  16 SocketFloat, SocketInt or SocketBool arranged by columns to a SocketMatrix.")
@user_overseer()
def combimatrix(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sMtx:
    if (type(floats) not in {tuple, set, list}):
        raise UserParamError(f"Function combimatrix() recieved unsupported type '{type(floats).__name__}' was expecting a tuple of 16 float compatible values.")
    if (len(floats)!=16):
        raise UserParamError(f"Function combimatrix() recieved itterable must be of len 16 to fit a 4x4 SocketMatrix")
    return generalcombsepa(ng,callhistory,'COMBINE','MATRIXFLAT',floats)

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Rows).\nSeparate a SocketMatrix into a tuple of 4 Quaternion SocketRotation, by rows.")
@user_overseer()
def separows(ng, callhistory,
    mA:sMtx|Matrix,
    ) -> tuple:
    floats = generalcombsepa(ng,callhistory,'SEPARATE','MATRIXFLAT',mA)
    q1 = combiquat(ng,callhistory, floats[0], floats[4], floats[8],  floats[12],)
    q2 = combiquat(ng,callhistory, floats[1], floats[5], floats[9],  floats[13],)
    q3 = combiquat(ng,callhistory, floats[2], floats[6], floats[10], floats[14],)
    q4 = combiquat(ng,callhistory, floats[3], floats[7], floats[11], floats[15],)

    #arrange nodes
    if (not q4.node.parent):
        q2.node.location = q1.node.location.x, q1.node.location.y - 150
        q3.node.location = q1.node.location.x, q1.node.location.y - 300
        q4.node.location = q1.node.location.x, q1.node.location.y - 450

    frame_nodes(ng, floats[0].node, q4.node, label='Sep Mtx Rows',)
    return q1, q2, q3, q4

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Rows).\nCombine an itterable containing  4 Quaternion SocketRotation to a SocketMatrix, by rows.")
@user_overseer()
def combirows(ng, callhistory,
    q1:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q2:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q3:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q4:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    ) -> sMtx:
    w1, x1, y1, z1 = sepaquat(ng,callhistory,q1)
    w2, x2, y2, z2 = sepaquat(ng,callhistory,q2)
    w3, x3, y3, z3 = sepaquat(ng,callhistory,q3)
    w4, x4, y4, z4 = sepaquat(ng,callhistory,q4)

    #arrange nodes
    if (not w1.node.parent):
        w2.node.location = w1.node.location.x, w1.node.location.y - 150
        w3.node.location = w1.node.location.x, w1.node.location.y - 300
        w4.node.location = w1.node.location.x, w1.node.location.y - 450

    floats = [w1, w2, w3, w4,
              x1, x2, x3, x4,
              y1, y2, y3, y4,
              z1, z2, z3, z4,]
    _r = generalcombsepa(ng,callhistory,'COMBINE','MATRIXFLAT',floats)
    frame_nodes(ng, w1.node, _r.node, label='Sep Mtx Rows',)
    return _r

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Columns).\nSeparate a SocketMatrix into a tuple of 4 Quaternion SocketRotation, by columns.")
@user_overseer()
def separacols(ng, callhistory,
    mA:sMtx|Matrix,
    ) -> tuple:
    floats = generalcombsepa(ng,callhistory,'SEPARATE','MATRIXFLAT',mA)
    q1 = combiquat(ng,callhistory, floats[0],  floats[1],  floats[2],  floats[3],)
    q2 = combiquat(ng,callhistory, floats[4],  floats[5],  floats[6],  floats[7],)
    q3 = combiquat(ng,callhistory, floats[8],  floats[9],  floats[10], floats[11],)
    q4 = combiquat(ng,callhistory, floats[12], floats[13], floats[14], floats[15],)

    #arrange nodes
    if (not q4.node.parent):
        q2.node.location = q1.node.location.x, q1.node.location.y - 150
        q3.node.location = q1.node.location.x, q1.node.location.y - 300
        q4.node.location = q1.node.location.x, q1.node.location.y - 450

    frame_nodes(ng, floats[0].node, q4.node, label='Sep Mtx Cols',)
    return q1, q2, q3, q4

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Columns).\nCombine an itterable containing  4 Quaternion SocketRotation to a SocketMatrix, by columns.")
@user_overseer()
def combicols(ng, callhistory,
    q1:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q2:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q3:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    q4:sVec|sVecXYZ|sVecT|sRot|Quaternion|ColorRGBA,
    ) -> sMtx:
    w1, x1, y1, z1 = sepaquat(ng,callhistory,q1)
    w2, x2, y2, z2 = sepaquat(ng,callhistory,q2)
    w3, x3, y3, z3 = sepaquat(ng,callhistory,q3)
    w4, x4, y4, z4 = sepaquat(ng,callhistory,q4)

    #arrange nodes
    if (not w1.node.parent):
        w2.node.location = w1.node.location.x, w1.node.location.y - 150
        w3.node.location = w1.node.location.x, w1.node.location.y - 300
        w4.node.location = w1.node.location.x, w1.node.location.y - 450

    floats = [w1, x1, y1, z1,
              w2, x2, y2, z2,
              w3, x3, y3, z3,
              w4, x4, y4, z4,]
    _r = generalcombsepa(ng,callhistory,'COMBINE','MATRIXFLAT',floats)
    frame_nodes(ng, w1.node, _r.node, label='Sep Mtx Cols',)
    return _r

@user_domain('nexscript')
@user_doc(nexscript="Separate Matrix (Transform).\nSeparate a SocketMatrix into a tuple SocketVector, SocketRotation, SocketVector.")
@user_overseer()
def sepatransforms(ng, callhistory,
    mA:sMtx|Matrix,
    ) -> tuple:
    return generalcombsepa(ng,callhistory,'SEPARATE','MATRIXTRANSFORM',mA)

@user_domain('nexscript')
@user_doc(nexscript="Combine Matrix (Transform).\nCombine 3 SocketVector into a SocketMatrix.")
@user_overseer()
def combitransforms(ng, callhistory,
    vL:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    qR:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sRot|float|int|Vector|Quaternion|ColorRGBA,
    vS:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sMtx:
    #NOTE Special Case: an itter or len4 passed to a Nex function may automatically be interpreted as a RGBA color. But, it's a quaternion..
    if (type(qR)==ColorRGBA):
        qR = Quaternion(qR[:])
    if (type(vL) in {float, int}):
        vL = Vector((vL,vL,vL))
    if (type(qR) in {float, int}):
        qR = Quaternion((qR,qR,qR,qR))
    if (type(vS) in {float, int}):
        vS = Vector((vS,vS,vS))
    return generalcombsepa(ng,callhistory,'COMBINE','MATRIXTRANSFORM',(vL,qR,vS),)

# 8b    d8 88 88b 88 8b    d8    db    Yb  dP 
# 88b  d88 88 88Yb88 88b  d88   dPYb    YbdP  
# 88YbdP88 88 88 Y88 88YbdP88  dP__Yb   dPYb  
# 88 YY 88 88 88  Y8 88 YY 88 dP""""Yb dP  Yb 

@user_domain('mathex','nexscript')
@user_doc(mathex="Minimum.\nGet the absolute minimal value across all passed arguments.")
@user_doc(nexscript="Minimum.\nGet the absolute minimal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
@user_overseer()
def min(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    # for nexcript, min will be called if given params are all python float or int
    if (len(floats) in {0,1}):
        raise UserParamError(f"Function min() needs two Params or more.") 
    return generalminmax(ng,callhistory,'min',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Minimum\nGet the minimal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
@user_overseer()
def smin(ng, callhistory,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory,'SMOOTH_MIN',a,b,dist)

@user_domain('mathex','nexscript')
@user_doc(mathex="Maximum.\nGet the absolute maximal value across all passed arguments.")
@user_doc(nexscript="Maximum.\nGet the absolute maximal value across all passed arguments.\nArguments must be compatible with SocketFloat.")
@user_overseer()
def max(ng, callhistory,
    *floats:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    # for nexcript, max will be called if given params are all python float or int
    if (len(floats) in {0,1}):
        raise UserParamError(f"Function max() needs two Params or more.") 
    return generalminmax(ng,callhistory,'max',*floats)

@user_domain('mathex','nexscript')
@user_doc(mathex="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.")
@user_doc(nexscript="Smooth Maximum\nGet the maximal value between A & B considering a smoothing distance to avoid abrupt transition.\nSupports SocketFloats only.")
@user_overseer()
def smax(ng, callhistory,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    dist:sFlo|sInt|sBoo|float|int,
    ) -> sFlo:
    return generalfloatmath(ng,callhistory,'SMOOTH_MAX',a,b,dist)

#  dP""b8  dP"Yb  8b    d8 88""Yb    db    88""Yb 88 .dP"Y8  dP"Yb  88b 88 
# dP   `" dP   Yb 88b  d88 88__dP   dPYb   88__dP 88 `Ybo." dP   Yb 88Yb88 
# Yb      Yb   dP 88YbdP88 88"""   dP__Yb  88"Yb  88 o.`Y8b Yb   dP 88 Y88 
#  YboodP  YbodP  88 YY 88 88     dP""""Yb 88  Yb 88 8bodP'  YbodP  88  Y8 

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def iseq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    # NOTE it is a little strange to assume 1 == Vector(1,1,1)  == Color(1,1,1,1)? 
    # but oh well, that's how blender comparison system works with it's implicit types.
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory,'XNOR',a,b)
    if containsCols(a,b):
        return generalcompare(ng,callhistory,'RGBA','EQUAL',a,b,None)
    if containsVecs(a,b):
        return generalcompare(ng,callhistory,'VECTOR','EQUAL',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','EQUAL',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def isuneq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if alltypes(a,b,types=(sBoo, bool),):
        return generalboolmath(ng,callhistory,'XOR',a,b)
    if containsCols(a,b):
        return generalcompare(ng,callhistory,'RGBA','NOT_EQUAL',a,b,None)
    if containsVecs(a,b):
        return generalcompare(ng,callhistory,'VECTOR','NOT_EQUAL',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','NOT_EQUAL',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def isless(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if containsVecs(a,b) or containsCols(a,b):
        return generalcompare(ng,callhistory,'VECTOR','LESS_THAN',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','LESS_THAN',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def islesseq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if containsVecs(a,b) or containsCols(a,b):
        return generalcompare(ng,callhistory,'VECTOR','LESS_EQUAL',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','LESS_EQUAL',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def isgreater(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if containsVecs(a,b) or containsCols(a,b):
        return generalcompare(ng,callhistory,'VECTOR','GREATER_THAN',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','GREATER_THAN',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def isgreatereq(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if containsVecs(a,b) or containsCols(a,b):
        return generalcompare(ng,callhistory,'VECTOR','GREATER_EQUAL',a,b,None)
    return generalcompare(ng,callhistory,'FLOAT','GREATER_EQUAL',a,b,None)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def booland(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    )->sBoo:
    return generalboolmath(ng,callhistory,'AND',a,b)

#covered internally in nexscript via python dunder overload
@user_domain('nexclassmethod')
@user_overseer()
def boolor(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    )->sBoo:
    return generalboolmath(ng,callhistory,'OR',a,b)

@user_domain('nexclassmethod')
@user_overseer()
def boolnot(ng, callhistory,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|bool,
    )->sBoo:
    return generalboolmath(ng,callhistory,'NOT',a)

@user_domain('nexscript')
@user_doc(nexscript="All Equals.\nCheck if all passed arguments have equal values.\n\nCompatible with SocketFloats, SocketBools, SocketInts, SocketVectors, SocketColors. Will return a SocketBool.")
@user_overseer()
def alleq(ng, callhistory,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    )->sBoo:
    if (len(values) in {0,1}):
        raise UserParamError(f"Function alleq() needs two Params or more.") 
    return generalbatchcompare(ng,callhistory,'alleq',None,None,None,*values)

#TODO what about epsilon??? problem is that epsilon is not supported for all operaiton type
# would require a fix in blender source code.

#def almosteq(a,b,epsilon)
#TODO 
#def isbetween(value, min, max)
#def allbetween(min, max, *betweens)

# 8b    d8 88 Yb  dP 
# 88b  d88 88  YbdP  
# 88YbdP88 88  dPYb  
# 88 YY 88 88 dP  Yb 

@user_domain('mathex','nexscript')
@user_doc(mathex="Mix.\nLinear Interpolation between value A and B from given factor F.")
@user_doc(nexscript="Mix.\nLinear Interpolation between value A and B from given factor F.\nSupports SocketFloat, SocketVector and SocketColor.")
@user_overseer()
def lerp(ng, callhistory,
    f:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec:
    if containsVecs(f):
        return generalmix(ng,callhistory,'VECTOR',f,a,b)
    if containsCols(a,b):
        return generalmix(ng,callhistory,'RGBA',f,a,b)
    if containsVecs(a,b):
        return generalmix(ng,callhistory,'VECTOR',f,a,b)
    return generalmix(ng,callhistory,'FLOAT',f,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="Alternative notation to lerp() function.")
@user_doc(nexscript="Alternative notation to lerp() function.")
@user_overseer()
def mix(ng, callhistory,
    f:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    ) -> sFlo|sVec:
    return lerp(ng,callhistory,f,a,b)

#  dP""b8 88        db    8b    d8 88""Yb 
# dP   `" 88       dPYb   88b  d88 88__dP 
# Yb      88  .o  dP__Yb  88YbdP88 88"""  
#  YboodP 88ood8 dP""""Yb 88 YY 88 88     

@user_domain('mathex','nexscript')
@user_doc(mathex="Clamping.\nClamp a value between min A & max B default set on 0,1.")
@user_doc(nexscript="Clamping.\nClamp a value between min A & max B default set on 0,1.\nSupports SocketFloat and entry-wise SocketVector, SocketColor.")
@user_overseer()
def clamp(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    a:sFlo|sInt|sBoo|float|int=0,
    b:sFlo|sInt|sBoo|float|int=1,
    ) -> sFlo|sVec|sCol:

    if (ng.type=='COMPOSITING'):
        _m = generalfloatmath(ng,callhistory,'MINIMUM',v,b)
        _r = generalfloatmath(ng,callhistory,'MAXIMUM',a,_m)
        frame_nodes(ng, _m.node, _r.node, label='Clamp|CompositorSpecial',)
        return _r

    if containsCols(v):
        return generalentryfloatmath(ng,callhistory,'COLORRGB','CLAMP.MINMAX',v,a,b)
    if containsVecs(v):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','CLAMP.MINMAX',v,a,b)

    return generalfloatmath(ng,callhistory,'CLAMP.MINMAX',v,a,b)

@user_domain('mathex','nexscript')
@user_doc(mathex="AutoClamping.\nClamp a value between auto-defined min/max A and B.")
@user_doc(nexscript="AutoClamping.\nClamp a value between auto-defined min/max A and B.\nSupports SocketFloat and entry-wise SocketVector, SocketColor.")
@user_overseer()
def clampauto(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|Vector|ColorRGBA,
    a:sFlo|sInt|sBoo|float|int,
    b:sFlo|sInt|sBoo|float|int,
    ) -> sFlo|sVec|sCol:

    if (ng.type=='COMPOSITING'):
        _mi = generalfloatmath(ng,callhistory,'MINIMUM',v,b)
        _ma = generalfloatmath(ng,callhistory,'MAXIMUM',v,b)
        _m = generalfloatmath(ng,callhistory,'MINIMUM',v,_ma)
        _r = generalfloatmath(ng,callhistory,'MAXIMUM',_mi,_m)
        frame_nodes(ng, _mi.node, _r.node, label='ClampAuto|CompositorSpecial',)
        return _r

    if containsCols(v):
        return generalentryfloatmath(ng,callhistory,'COLORRGB','CLAMP.RANGE',v,a,b)
    if containsVecs(v):
        return generalentryfloatmath(ng,callhistory,'VECTORXYZ','CLAMP.RANGE',v,a,b)

    return generalfloatmath(ng,callhistory,'CLAMP.RANGE',v,a,b)

# 8b    d8    db    88""Yb 
# 88b  d88   dPYb   88__dP 
# 88YbdP88  dP__Yb  88"""  
# 88 YY 88 dP""""Yb 88     

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range.\nRemap a value V from a given range A,B to another range X,Y.")
@user_doc(nexscript="Map Range.\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_overseer()
def mapl(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory,'FLOAT_VECTOR','LINEAR',v,a,b,x,y)
    return generalmaprange(ng,callhistory,'FLOAT','LINEAR',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\n\nNot Available for the Compositor.")
@user_doc(nexscript="Map Range (Stepped).\nRemap a value V from a given range A,B to another range X,Y with a given step.\nSupports SocketFloat and SocketVector.")
@user_overseer(assert_editortype={'GEOMETRY','SHADER'},)
def mapst(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    step:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y,step):
        return generalmaprange(ng,callhistory,'FLOAT_VECTOR','STEPPED',v,a,b,x,y,step)
    return generalmaprange(ng,callhistory,'FLOAT','STEPPED',v,a,b,x,y,step)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\n\nNot Available for the Compositor.")
@user_doc(nexscript="Map Range (Smooth).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_overseer(assert_editortype={'GEOMETRY','SHADER'},)
def mapsmo(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory,'FLOAT_VECTOR','SMOOTHSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory,'FLOAT','SMOOTHSTEP',v,a,b,x,y)

@user_domain('mathex','nexscript')
@user_doc(mathex="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\n\nNot Available for the Compositor.")
@user_doc(nexscript="Map Range (Smoother).\nRemap a value V from a given range A,B to another range X,Y.\nSupports SocketFloat and SocketVector.")
@user_overseer(assert_editortype={'GEOMETRY','SHADER'},)
def mapsmoo(ng, callhistory,
    v:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    a:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    b:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    x:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    y:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|Vector,
    ) -> sFlo|sVec:
    if containsVecs(v,a,b,x,y):
        return generalmaprange(ng,callhistory,'FLOAT_VECTOR','SMOOTHERSTEP',v,a,b,x,y)
    return generalmaprange(ng,callhistory,'FLOAT','SMOOTHERSTEP',v,a,b,x,y)

# .dP"Y8 Yb        dP 88 888888  dP""b8 88  88 
# `Ybo."  Yb  db  dP  88   88   dP   `" 88  88 
# o.`Y8b   YbdPYbdP   88   88   Yb      888888 
# 8bodP'    YP  YP    88   88    YboodP 88  88 

@user_domain('nexscript')
@user_doc(nexscript="Switch (Boolean).\nSwap between the different bool parameters depending on the index.")
@user_overseer()
def switchbool(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool,
    ) -> sBoo:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchbool() needs at least three Params.")
    return generalswitch(ng,callhistory,'bool',idx,*values)

@user_domain('nexscript')
@user_doc(nexscript="Switch (Int).\nSwap between the different integer parameters depending on the index.")
@user_overseer()
def switchint(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool,
    ) -> sInt:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchint() needs at least three Params.")
    return generalswitch(ng,callhistory,'int',idx,*values)

@user_domain('nexscript')
@user_doc(nexscript="Switch (Float).\nSwap between the different float parameters depending on the index.")
@user_overseer()
def switchfloat(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool,
    ) -> sFlo:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchfloat() needs at least three Params.")
    return generalswitch(ng,callhistory,'float',idx,*values)

@user_domain('nexscript')
@user_doc(nexscript="Switch (Vector).\nSwap between the different Vector parameters depending on the index.")
@user_overseer()
def switchvec(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    ) -> sVec:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchvec() needs at least three Params.")
    return generalswitch(ng,callhistory,'vec',idx,*values)

@user_domain('nexscript')
@user_doc(nexscript="Switch (Color).\nSwap between the different Color parameters depending on the index.")
@user_overseer()
def switchcol(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|sCol|float|int|bool|Vector|ColorRGBA,
    ) -> sCol:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchcol() needs at least three Params.")
    return generalswitch(ng,callhistory,'col',idx,*values)

@user_domain('nexscript')
@user_doc(nexscript="Switch (Matrix).\nSwap between the different Matrix parameters depending on the index.")
@user_overseer()
def switchmat(ng, callhistory,
    idx:sFlo|sInt|sBoo|float|int|bool,
    *values:sMtx|Matrix,
    ) -> sMtx:
    if (len(values) in {0,1}): raise UserParamError(f"Function switchmat() needs at least three Params.")
    return generalswitch(ng,callhistory,'mat',idx,*values)

# 88""Yb    db    88b 88 8888b.   dP"Yb  8b    d8 
# 88__dP   dPYb   88Yb88  8I  Yb dP   Yb 88b  d88 
# 88"Yb   dP__Yb  88 Y88  8I  dY Yb   dP 88YbdP88 
# 88  Yb dP""""Yb 88  Y8 8888Y"   YbodP  88 YY 88 

@user_domain('nexscript')
@user_doc(nexscript="Random (Boolean).\nGet a random boolean.\nOptionally: pass a probability default set on 0.5, a seed number, and an ID SocketInt.")
@user_overseer()
def randbool(ng, callhistory,
    prob:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool=0.5,
    seed:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ID:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ) -> sBoo:
    return generalrandom(ng,callhistory,'BOOLEAN', None,None,prob,seed,ID)

@user_domain('nexscript')
@user_doc(nexscript="Random (Int).\nGet a random integer number.\nOptionally: define a min/max range by default set on -10k & 10k, a seed number, and an ID SocketInt.")
@user_overseer()
def randint(ng, callhistory, 
    min:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool=-10_000,
    max:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool=10_000,
    seed:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ID:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ) -> sInt:
    # for nexcript, shall we call  random.randint if all args are py? Hmm. users might not want that.
    return generalrandom(ng,callhistory,'INT',min,max,None,seed,ID)

@user_domain('nexscript')
@user_doc(nexscript="Random (Float).\nGet a random float number.\nOptionally: define a min/max range by default set on -10k & 10k, a seed number, and an ID SocketInt.")
@user_overseer()
def randfloat(ng, callhistory,
    min:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool=-10_000,
    max:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool=10_000,
    seed:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ID:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ) -> sFlo:
    return generalrandom(ng,callhistory,'FLOAT',min,max,None,seed,ID)

@user_domain('nexscript')
@user_doc(nexscript="Random (Vector).\nGet a random Vector.\nOptionally: define a min/max range by default set on (0,0,0) & (1,1,1), a seed number, and an ID SocketInt.")
@user_overseer()
def randvec(ng, callhistory,
    min:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector=Vector((0,0,0)),
    max:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|bool|Vector=Vector((1,1,1)),
    seed:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ID:sFlo|sInt|sBoo|sVec|sVecXYZ|sVecT|float|int|None=None,
    ) -> sVec:
    return generalrandom(ng,callhistory,'FLOAT_VECTOR',min,max,None,seed,ID)

#    db    888888 888888 88""Yb 
#   dPYb     88     88   88__dP 
#  dP__Yb    88     88   88"Yb  
# dP""""Yb   88     88   88  Yb 

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

# TODO 
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

# TODO 
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

# TODO 
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
