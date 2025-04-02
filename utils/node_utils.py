# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


# NOTE this module has a lot of functions for nodegroup manipulation. 
# It's assuming a CustomNodeGroup node, whihc has a node componemnt attached to a nodetree.

# TODO Optimization: 
# functions should always check if a value or type isn't already set before setting it.
# i don't think i was regular with this.


import bpy 

from math import hypot
from mathutils import Vector, Matrix, Quaternion

from .draw_utils import get_dpifac
from .fct_utils import ColorRGBA


SOCK_AVAILABILITY_TABLE = {
    'GEOMETRY':    ('NodeSocketFloat', 'NodeSocketInt', 'NodeSocketVector', 'NodeSocketColor', 'NodeSocketBool', 'NodeSocketRotation', 'NodeSocketMatrix', 'NodeSocketString', 'NodeSocketMenu', 'NodeSocketObject', 'NodeSocketGeometry', 'NodeSocketCollection', 'NodeSocketTexture', 'NodeSocketImage', 'NodeSocketMaterial',),
    'SHADER':      ('NodeSocketFloat', 'NodeSocketInt', 'NodeSocketVector', 'NodeSocketColor', 'NodeSocketBool', 'NodeSocketShader', ),
    'COMPOSITING': ('NodeSocketFloat', 'NodeSocketInt', 'NodeSocketVector', 'NodeSocketColor', ),
    }
TREE_TO_GROUP_EQUIV = {
    'ShaderNodeTree': 'ShaderNodeGroup',
    'CompositorNodeTree': 'CompositorNodeGroup',
    'GeometryNodeTree': 'GeometryNodeGroup',
    }


def get_all_nodes(ignore_ng_name:str="NodeBooster", approxmatch_idnames:str="", exactmatch_idnames:set=None, ngtypes:set=None,) -> set|list:
    """get nodes instances across many nodetree editor types.
    - ngtypes: the editor types to be supported in {'GEOMETRY','SHADER','COMPOSITING',}. will use all if None
    - ignore_ng_name: ignore getting nodes from a nodetree containing a specific name.
    - approxmatch_idnames: only get nodes whose include the given token.
    - exactmatch_idnames: only get nodes included in the set of given id names.
    """
 
    if (ngtypes is None):
        ngtypes = {'GEOMETRY','SHADER','COMPOSITING',}

    nodes = set()

    if ('SHADER' in ngtypes):
        #get all nodes of all materials
        for mat in bpy.data.materials:
            if mat.use_nodes and mat.node_tree:
                for n in mat.node_tree.nodes:
                    nodes.add(n)

    if ('COMPOSITING' in ngtypes):
        #get all nodes of the compositor base tree
        for scn in bpy.data.scenes:
            if scn.use_nodes and scn.node_tree:
                for n in scn.node_tree.nodes:
                    nodes.add(n)

    for ng in bpy.data.node_groups:
        
        #does the type of the nodegroup correspond to what we need?
        if (ng.type not in ngtypes):
            continue
        
        #we ignore specific ng names?
        if (ignore_ng_name and (ignore_ng_name in ng.name)):
            continue
        
        #batch add all these nodes.
        nodes.update(ng.nodes)
        continue

    #only node with matching exact id?
    if (exactmatch_idnames):
        nodes = [n for n in nodes if (n.bl_idname in exactmatch_idnames)]

    #only with node with 
    if (approxmatch_idnames):
        nodes = [n for n in nodes if (approxmatch_idnames in n.bl_idname)]

    return nodes

def parcour_node_tree(nodes, socket, direction:str='LEFT',):
    """ parcour a nodetree and return all sockets connected to the passed socket.
    - important information about parcouring nodetrees: https://www.youtube.com/watch?v=FuqVCBlgJTo
    - direction: 'LEFT' or 'RIGHT'
    - the function will return a dictionary of {socket: links}.
    """

    result = {}  # Will store final sockets and their links
    visited_sockets = set()  # To avoid feedback loops
    visited_links = []  # Store all visited links
    
    # Start with the initial socket
    sockets_to_process = [socket]
    visited_sockets.add(socket)

    while sockets_to_process:
        current_socket = sockets_to_process.pop(0)

        # Get all links connected to this socket
        match direction:
            case 'LEFT': # Going left means we look at inputs, so we need links where current_socket is the to_socket
                links = [link for link in current_socket.links if link.to_socket == current_socket]
            case 'RIGHT': # Going right means we look at outputs, so we need links where current_socket is the from_socket
                links = [link for link in current_socket.links if link.from_socket == current_socket]

        for link in links:
            # Add link to visited links
            visited_links.append(link)

            # Determine the next socket to process
            next_socket = link.from_socket if (direction == 'LEFT') else link.to_socket

            # Skip if we've already visited this socket
            if (next_socket in visited_sockets):
                continue
            visited_sockets.add(next_socket)

            # Get the node of the next socket
            next_node = next_socket.node

            # If it's a reroute node, continue traversing
            if (next_node.bl_idname == 'NodeReroute'):

                # For reroute, add the socket to process
                next_socket_to_process = next_node.inputs[0] if (direction == 'LEFT') else next_node.outputs[0]

                # Check if this reroute leads nowhere (colliding reroute)
                if (not next_socket_to_process.links):
                    # This is a dead end reroute, add its socket as a result
                    if next_socket not in result:
                        result[next_socket] = []
                    result[next_socket].append(link)
                else:
                    sockets_to_process.append(next_socket_to_process)
            else:
                # For non-reroute nodes, add the socket to result
                if next_socket not in result:
                    result[next_socket] = []
                result[next_socket].append(link)

    return result


def get_node_objusers(node) -> set:
    """Return a list of objects using the given Node."""
    
    #NOTE What if the node is in a nodegroup used by many?
    users = set()
    for o in bpy.data.objects:
        for m in o.modifiers:
            if (m.type=='NODES' and m.node_group):
                for n in m.node_group.nodes:
                    if (n==node):
                        users.add(o)
    return users


def get_node_absolute_location(node) -> Vector:
    """find the location of the node in global space"""

    if (node.parent is None):
        return node.location
    
    #if there's a frame, then the location is false
    x,y = node.location

    while (node.parent is not None):
        x += node.parent.location.x
        y += node.parent.location.y
        node = node.parent
        continue

    return Vector((x,y))


def get_node_socket_by_name(node, in_out:str='OUTPUT', socket_name:str="",):
    """get a given socket by name. Required because sometimes sockets['Name'] doesn't work."""

    sockets = node.outputs if (in_out=='OUTPUT') else node.inputs

    sock = None    
    for s in sockets:
        if (s.name==socket_name):
            sock = s
            break

    if (sock is None):
        raise Exception(f"ERROR: get_node_socket_by_name(): socket '{socket_name}' not found in node '{node.name}'")

    return sock


def set_node_socketattr(node, in_out:str='OUTPUT', socket_name:str="", attribute:str="", value=None,):
    """set a given attribute of a given socket. Required because sometimes sockets['Name'] doesn't work."""

    sockets = node.outputs if (in_out=='OUTPUT') else node.inputs

    sock = None    
    for s in sockets:
        if (s.name==socket_name):
            sock = s
            break

    if (sock is None):
        raise Exception(f"ERROR: set_node_socketattr(): socket '{socket_name}' not found in node '{node.name}'")
    if not hasattr(sock, attribute):
        raise Exception(f"ERROR: set_node_socketattr(): socket '{socket_name}' does not have attribute '{attribute}'")

    setattr(sock, attribute, value)
    return None


def crosseditor_socktype_adjust(socket_type:str, ngtype:str) -> str:
    """ensure the socket types are correct depending on the nodes editor"""

    compat = SOCK_AVAILABILITY_TABLE[ngtype]

    match ngtype:
        
        case 'GEOMETRY':
            pass

        case 'SHADER':
            if (socket_type in {'NodeSocketRotation', 'NodeSocketMatrix'}):
                # TODO cross editor support for these types? Pff. Better: Blender code base should support it.
                pass

        case 'COMPOSITING':
            #No bool in compositor. We use int instead
            if (socket_type=='NodeSocketBool'):
                socket_type = 'NodeSocketInt'

    if (socket_type not in compat):
        return f"Unavailable{socket_type}"
    return socket_type


def get_ng_socket_by_name(ng, socket_name:str='Foo', in_out:str='OUTPUT',) -> list|None:
    """for a NodeCustomGroup: get a socket object from a nodetree input/output by name"""

    sockets = ng.nodes["Group Output"].inputs if (in_out=='OUTPUT') else ng.nodes["Group Input"].outputs
    r = [s for s in sockets if (s.name==socket_name)]
    if (len(r)==0):
        return None
    elif (len(r)==1):
        return r[0]
    return r


def get_socketui_from_ng_socket(ng, idx:int=None, in_out:str='OUTPUT', identifier:str=None,):
    """for a NodeCustomGroup: return a given socket index as an interface item, either find the socket by it's index, name or socketidentifier"""
    
    if (identifier is None):
        sockets = ng.nodes["Group Output"].inputs if (in_out=='OUTPUT') else ng.nodes["Group Input"].outputs
        for i,s in enumerate(sockets):
            if (i==idx):
                identifier = s.identifier
                break

    if (identifier is None):
        raise Exception("ERROR: get_socketui_from_ng_socket(): couldn't retrieve socket identifier..")
    
    #then we retrieve thesocket interface item from identifier
    sockui = None
    findgen = [itm for itm in ng.interface.items_tree
               if hasattr(itm,'identifier') and (itm.identifier == identifier)]
    if len(findgen):
        sockui = findgen[0]
        if len(findgen)>1:
            print(f"WARNING: get_socketui_from_ng_socket: multiple sockets with identifier '{identifier}' exists")

    if (sockui is None):
        raise Exception("ERROR: get_socketui_from_ng_socket(): couldn't retrieve socket interface item..")
    
    return sockui


def get_ng_socket_from_socketui(ng, sockui, in_out:str='OUTPUT'):
    """for a NodeCustomGroup: retrieve NodeSocket from a NodeTreeInterfaceSocket type"""
    
    sockets = ng.nodes["Group Output"].inputs if (in_out=='OUTPUT') else ng.nodes["Group Input"].outputs
    for s in sockets:
        if (s.identifier == sockui.identifier):
            return s
    raise Exception('NodeSocket from nodetree.interface.items_tree does not exist?')


def get_ng_socket_defvalue(ng, idx:int, in_out:str='OUTPUT',):
    """for a NodeCustomGroup: return the value of the given nodegroups output at given socket idx"""

    match in_out:
        case 'OUTPUT':
            return ng.nodes["Group Output"].inputs[idx].default_value
        case 'INPUT':
            raise Exception("No Support for Inputs..")
            return ng.nodes["Group Input"].outputs[idx].default_value
        case _:
            raise Exception("get_ng_socket_defvalue(): in_out arg not valid")


def set_ng_socket_defvalue(ng, idx:int=None, socket=None, socket_name:str='', in_out:str='OUTPUT', value=None, node=None,):
    """for a NodeCustomGroup: set the value of the given nodegroups inputs or output sockets"""

    assert in_out in {'INPUT','OUTPUT'}, "set_ng_socket_defvalue(): in_out arg not valid"

    in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]

    if (socket_name):
        match in_out:
            case 'OUTPUT': socket = out_nod.inputs[socket_name]
            case 'INPUT':  socket = in_nod.outputs[socket_name]

    assert not (idx is None and socket is None), "Please pass either a socket, an index to a socket, or a socket name"

    #convert color to list
    if type(value) is ColorRGBA:
        value = value[:]

    #No bool in compositor. Use int instead
    if (ng.type=='COMPOSITING' and type(value) is bool):
        value = int(value)

    # setting a default value of a input is very different from an output.
    #  - set a defaultval input can only be done by changing all node instances input of that nodegroup..
    #  - set a defaultval output can be done within the ng

    match in_out:

        case 'OUTPUT':
            sockets = out_nod.inputs

            #fine our socket
            if (socket is None):
                socket = sockets[idx]
            else:
                assert socket in sockets[:], "Socket not found from input. Did you feed the right socket?"
            if (idx is None):
                for i,s in enumerate(sockets):
                    if (s==socket):
                        idx = i
                        break

            # for some socket types, they don't have any default_values property.
            # so we need to improvise and place a new node and link it!
            match socket.type:

                case 'ROTATION':
                    #NOTE if you want to pass a vec3 to a rotation socket, don't.
                    defnodname = f"D|Quat|outputs[{idx}]"
                    defnod = ng.nodes.get(defnodname)
                    #We cleanup nodetree and set up our input special.
                    if (defnod is None):
                        defnod = ng.nodes.new('FunctionNodeQuaternionToRotation')
                        defnod.name = defnod.label = defnodname
                        defnod.location = (out_nod.location.x, out_nod.location.y + 350)
                        #link it
                        for l in socket.links:
                            ng.links.remove(l)
                        ng.links.new(defnod.outputs[0], socket)
                    #assign values
                    for sock,v in zip(defnod.inputs, value):
                        if (sock.default_value!=v):
                            sock.default_value = v

                case 'MATRIX':
                    defnodname = f"D|Matrix|outputs[{idx}]"
                    defnod = ng.nodes.get(defnodname)
                    #We cleanup nodetree and set up our input special.
                    if (defnod is None):
                        defnod = ng.nodes.new('FunctionNodeCombineMatrix')
                        defnod.name = defnod.label = defnodname
                        defnod.location = (out_nod.location.x + 150, out_nod.location.y + 350)
                        #link it
                        for l in socket.links:
                            ng.links.remove(l)
                        ng.links.new(defnod.outputs[0], socket)
                        #the node comes with tainted default values
                        for inp in defnod.inputs:
                            inp.default_value = 0
                    #assign flatten values
                    colflatten = [v for col in zip(*value) for v in col]
                    for sock,v in zip(defnod.inputs, colflatten):
                        if (sock.default_value!=v):
                            sock.default_value = v

                case _:
                    #we remove any unwanted links, if exists
                    if (socket.links):
                        for l in socket.links:
                            ng.links.remove(l)
                    #we set def value, simply..
                    #NOTE Vector/Color won't like that, will always be False.. need to use [:]!=[:] for two vec..
                    if (socket.default_value!=value):
                        socket.default_value = value

        case 'INPUT':

            assert node is not None, "for inputs please pass a node instance to tweak the input values to"

            if (idx is None):
                for i,s in enumerate(in_nod.outputs):
                    if (s==socket):
                        idx = i
                        break
                assert idx is not None, "Error, couldn't find idx.."

            instancesocket = node.inputs[idx]

            #rotation and matrixes don't have a default value
            if (instancesocket.type in {'ROTATION','MATRIX'}):
                return None
            
            #NOTE Vector/Color won't like that, will always be False.. need to use [:]!=[:] for two vec..
            if (instancesocket.default_value!=value):
                instancesocket.default_value = value

    return None

def set_ng_socket_label(ng, idx:int=None, in_out:str='OUTPUT', label:str='', identifier:str=None,) -> None:
    """for a NodeCustomGroup: return the label of the given nodegroups output at given socket idx"""
    if (not label):
        return None
    sockui = get_socketui_from_ng_socket(ng, idx=idx, in_out=in_out, identifier=identifier,)
    if (sockui.name!=label):
        sockui.name = label
    return None  


def get_ng_socket_type(ng, idx:int=None, in_out:str='OUTPUT', identifier:str=None,) -> str:
    """for a NodeCustomGroup: return the type of the given nodegroups output at given socket idx"""
    
    sockui = get_socketui_from_ng_socket(ng, idx=idx, in_out=in_out, identifier=identifier,)
    return sockui.socket_type


def set_ng_socket_type(ng, idx:int=None, in_out:str='OUTPUT', socket_type:str="NodeSocketFloat", identifier:str=None,):
    """for a NodeCustomGroup: set socket type via bpy.ops.node.tree_socket_change_type() with manual override, context MUST be the geometry node editor"""
    #NOTE blender bug: you might need to use the return value because the original socket after change will be dirty.

    socket_type = crosseditor_socktype_adjust(socket_type, ng.type)
    sockui = get_socketui_from_ng_socket(ng, idx=idx, in_out=in_out, identifier=identifier,)
    if (sockui.socket_type!=socket_type):
        sockui.socket_type = socket_type
    return get_ng_socket_from_socketui(ng, sockui, in_out=in_out)


def set_ng_socket_description(ng, idx:int=None, in_out:str='OUTPUT', description:str='', identifier:str=None,) -> None:
    """for a NodeCustomGroup: set the description of the given nodegroups socket"""

    sockui = get_socketui_from_ng_socket(ng, idx=idx, in_out=in_out, identifier=identifier,)
    if (sockui.description!=description):
        sockui.description = description
    return None


def get_ng_socket_description(ng, idx:int=None, in_out:str='OUTPUT', identifier:str=None,) -> str:
    """for a NodeCustomGroup: return the description of the given nodegroups socket"""
    
    sockui = get_socketui_from_ng_socket(ng, idx=idx, in_out=in_out, identifier=identifier,)
    return sockui.description


def create_ng_socket(ng, in_out:str='OUTPUT', socket_type:str="NodeSocketFloat",
    socket_name:str="Value", socket_description:str="",): #socket_custom_info:dict=None,):
    """for a NodeCustomGroup: create a new socket output of given type for given nodegroup."""

    # NOTE this is a test on how to create a custom socket type in a nodegroup. It failed. 
    # because ng.links.new() to a CUSTOM grey socketype of a ng input/output do not 
    # automatically create the socket we need. We counter this problem by using existing ng stored in .blend files.
    # NOTE would be nice that the C ng.interface.new_socket() supports custom socket types...
    # Attempt: 
    # # NOTE about custom socket types:
    # # it's not possible to use the ng.interface.new_socket() but we can link to an undefined socket and it shall work
    # # node.inputs.new('customtype') works on other editors, but not for geometry node.. because could benefit from a C source code modif..
    # # NOTE C++ ng.interface isn't happy with custom types. Color is pink and if user go in interface it will scream.
    # # perhaps would require a bug report? THis tool need to gain popularity first tho, to convice C dev it's very useful to userbase and plugin dev base..
    # if (socket_type.startswith('NodeBoosterCustomSocket')):
    #
    #     #create an utility reroute
    #     customreroute = ng.nodes.new('CustomSocketUtility')
    #
    #     #specify custom socket information
    #     subtype, color = socket_custom_info['type'], socket_custom_info['color']
    #     rr_in, rr_out = customreroute.inputs[0], customreroute.outputs[0]
    #     rr_in.socket_type, rr_in.socket_color = subtype, color
    #     rr_out.socket_type, rr_out.socket_color = subtype, color
    #
    #     #link the reroute to the nodegroup socket
    #     undefsocket = ng.nodes["Group Output"].inputs[-1] if (in_out=='OUTPUT') else ng.nodes["Group Input"].outputs[-1]
    #     tolink = rr_out if (in_out=='OUTPUT') else rr_in
    #     link_sockets(tolink, undefsocket)
    #
    #     # remove the utility node after linking. We got our new sockets.
    #     # ng.nodes.remove(customreroute)
    #
    #     # TODO socket name and description..
    #     # is it safe to assume last item of ng.interface is our new socket?
    #
    #     return None

    #naive support for strandard socket.type notation
    if (socket_type.isupper()):
        socket_type = f'NodeSocket{socket_type.title()}'
    
    socket_type = crosseditor_socktype_adjust(socket_type, ng.type)

    sockui = ng.interface.new_socket(socket_name, in_out=in_out, socket_type=socket_type,)
    if (socket_description):
        sockui.description = socket_description
    return get_ng_socket_from_socketui(ng, sockui, in_out=in_out)


def remove_ng_socket(ng, idx:int, in_out:str='OUTPUT',) -> None:
    """for a NodeCustomGroup: remove a nodegroup socket output at given index"""
        
    itm = get_socketui_from_ng_socket(ng, idx, in_out=in_out,)
    ng.interface.remove(itm)
    
    return None 


def create_ng_constant_node(ng, nodetype:str, value, uniquetag:str, location:str='auto', width:int=200,):
    """for a NodeCustomGroup: add a new constant input node in nodetree if not existing, ensure it's value"""

    if (not uniquetag.startswith('C|')) and (location=='auto'):
        print("WARNING: Internal message: create_ng_constant_node() please make the uniquetag startswith 'C|' to support automatic location")

    if (location=='auto'):
        constcount = len([C for C in ng.nodes if C.name.startswith('C|')])
        in_nod = ng.nodes["Group Input"]
        locx = in_nod.location.x
        locy = in_nod.location.y
        locy -= 330
        locy -= (90*constcount)
        location = locx, locy

    #initialize the creation of the input node?
    node = ng.nodes.get(uniquetag)
    if (node is None):
        node = ng.nodes.new(nodetype)
        node.label = node.name = uniquetag
        node.width = width
        if (location):
            node.location.x = location[0]
            node.location.y = location[1]

    match nodetype:

        case 'ShaderNodeValue'|'CompositorNodeValue':
            if (node.outputs[0].default_value!=value):
                node.outputs[0].default_value = value
            return node.outputs[0]

        case 'FunctionNodeQuaternionToRotation':
            assert type(value) is Quaternion, f"Please make sure passed value is of Quaternion type. Currently is of {type(value).__name__}"
            assert len(value)==4, f"Please make sure the passed Quaternion has 4 WXYZ elements. Currently contains {len(value)}"
            #assign values
            node.inputs[0].default_value = value.w
            node.inputs[1].default_value = value.x
            node.inputs[2].default_value = value.y
            node.inputs[3].default_value = value.z
            return node.outputs[0]

        case 'FunctionNodeCombineMatrix':
            assert type(value) is Matrix, f"Please make sure passed value is of Matrix type. Currently is of {type(value).__name__}"
            rowflatten = [v for row in value for v in row]
            assert len(rowflatten)==16, f"Please make sure the passed Matrix has 16 elements in total. Currently contains {len(rowflatten)}"
            #assign flatten values
            colflatten = [v for col in zip(*value) for v in col]
            for sock,v in zip(node.inputs, colflatten):
                if (sock.default_value!=v):
                    sock.default_value = v
            return node.outputs[0]

        case _:
            raise Exception(f"{nodetype} Not Implemented Yet")

    return None


def create_new_nodegroup(name:str, tree_type:str='GeometryNodeTree', in_sockets:dict={},
    out_sockets:dict={}, sockets_description:dict={},): #socket_custom_info:dict=None,):
    """create new nodegroup with outputs from given dict {"name":"type",},
    optionally pass a sockets_description dict to set the description of the sockets, format: {socket_name:description}"""

    ng = bpy.data.node_groups.new(name=name, type=tree_type,)

    #create main input/output
    in_nod, out_nod = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    in_nod.location.x -= 200 ; out_nod.location.x += 200

    #create the sockets
    #inputs
    for sname, stype in in_sockets.items():
        create_ng_socket(ng, in_out='INPUT', socket_type=stype,
            socket_name=sname, socket_description=sockets_description.get(sname,''))
            #socket_custom_info=socket_custom_info.get(sname,{}),) #LATER? when we make this work..
    #outputs
    for sname, stype in out_sockets.items():
        create_ng_socket(ng, in_out='OUTPUT', socket_type=stype,
            socket_name=sname, socket_description=sockets_description.get(sname,''))
            #socket_custom_info=socket_custom_info.get(sname,{}),) #LATER? when we make this work..

    return ng


def import_new_nodegroup(blendpath, ngname, tree_type='GeometryNodeTree'):
    """Import a nodegroup from an external blend file."""

    # Check if the nodegroup already exists
    if ngname in bpy.data.node_groups:
        return bpy.data.node_groups[ngname]
    
    # Import the nodegroup from the blend file
    with bpy.data.libraries.load(blendpath, link=False) as (data_from, data_to):
        if ngname in data_from.node_groups:
            data_to.node_groups = [ngname]
        else:
            return None
    
    # Return the imported nodegroup
    if (data_to.node_groups):
        return data_to.node_groups[0]

    return None


def link_sockets(socket1, socket2):
    """link two nodes together in a nodetree"""
    # if not issubclass(type(socket1), bpy.types.NodeSocket):
    #     return None
    # if not issubclass(type(socket2), bpy.types.NodeSocket):
    #     return None
    ng = socket1.id_data
    return ng.links.new(socket1, socket2)


def replace_node_by_ng(node_tree, old_node, node_group):
    """Replace an existing node with a new Node Group node (assuming same socket structure)"""

    # Save old node properties.
    old_node_width = float(old_node.width)
    old_node_location = old_node.location.copy()

    # For inputs, store default values and the linked from_socket (if exists)
    old_inputs_defaults = [getattr(sock, 'default_value', None) for sock in old_node.inputs]
    old_inputs_links = [sock.links[0].from_socket if sock.links else None for sock in old_node.inputs]

    # For outputs, store the linked to_socket (if exists)
    old_outputs_links = [sock.links[0].to_socket if sock.links else None for sock in old_node.outputs]

    # Determine the appropriate node type for a node group.
    ng_type = TREE_TO_GROUP_EQUIV.get(node_tree.bl_idname)
    if (ng_type is None):
        print(f"replace_node_by_ng() does not support '{node_tree.bl_idname}'.")
        return None

    # Delete the old node.
    node_tree.nodes.remove(old_node)

    # Create the new node group node.
    new_node = node_tree.nodes.new(ng_type)
    new_node.location = old_node_location
    new_node.width = old_node_width

    # Assign the provided node group.
    new_node.node_tree = node_group

    # Re-apply default values to new node inputs (if available).
    for i, sock in enumerate(new_node.inputs):
        if (i < len(old_inputs_defaults) and old_inputs_defaults[i] is not None):
            try: sock.default_value = old_inputs_defaults[i]
            except Exception as e: print(f"Warning: Could not copy default for input '{sock.name}': {e}")

    # Re-create input links.
    for i, sock in enumerate(new_node.inputs):
        if (i < len(old_inputs_links) and old_inputs_links[i] is not None):
            try: node_tree.links.new(old_inputs_links[i], sock)
            except Exception as e: print(f"Warning: Could not re-link input '{sock.name}': {e}")

    # Re-create output links.
    for i, sock in enumerate(new_node.outputs):
        if (i < len(old_outputs_links) and old_outputs_links[i] is not None):
            try: node_tree.links.new(sock, old_outputs_links[i])
            except Exception as e: print(f"Warning: Could not re-link output '{sock.name}': {e}")
    
    return new_node


def frame_nodes(node_tree, *nodes, label:str="Frame",) -> None:
    """Create a Frame node in the given node_tree and parent the specified nodes to it."""

    # we check if there's not a frame already existing. Important for nodesetter.py
    nodes = [n for n in nodes if (n is not None)]
    existing = set(n.parent.label for n in nodes if n.parent)
    frame_exist_already = len(existing) == 1 and next(iter(existing)) == label

    if (not frame_exist_already):
        frame = node_tree.nodes.new('NodeFrame')
        frame.label = label

        for node in nodes:
            node.parent = frame

    return None


def get_nearest_node_at_position(nodes:list|set, context, event, position=None, allow_reroute:bool=True, forbidden:list|set=None,):
    """get nearest node at cursor location"""
    # Function from from 'node_wrangler.py'

    nodes_near_mouse = []
    nodes_under_mouse = []
    target_node = None

    x, y = position

    # Make a list of each corner (and middle of border) for each node.
    # Will be sorted to find nearest point and thus nearest node
    node_points_with_dist = []

    for n in nodes:
        if (n.type == 'FRAME'):
            continue
        if (not allow_reroute and (n.type == 'REROUTE')):
            continue
        if (forbidden is not None) and (n in forbidden):
            continue

        locx, locy = get_node_absolute_location(n)
        dimx, dimy = n.dimensions.x/get_dpifac(), n.dimensions.y/get_dpifac()

        node_points_with_dist.append([n, hypot(x - locx, y - locy)])  # Top Left
        node_points_with_dist.append([n, hypot(x - (locx + dimx), y - locy)])  # Top Right
        node_points_with_dist.append([n, hypot(x - locx, y - (locy - dimy))])  # Bottom Left
        node_points_with_dist.append([n, hypot(x - (locx + dimx), y - (locy - dimy))])  # Bottom Right

        node_points_with_dist.append([n, hypot(x - (locx + (dimx / 2)), y - locy)])  # Mid Top
        node_points_with_dist.append([n, hypot(x - (locx + (dimx / 2)), y - (locy - dimy))])  # Mid Bottom
        node_points_with_dist.append([n, hypot(x - locx, y - (locy - (dimy / 2)))])  # Mid Left
        node_points_with_dist.append([n, hypot(x - (locx + dimx), y - (locy - (dimy / 2)))])  # Mid Right

        continue

    nearest_node = sorted(node_points_with_dist, key=lambda k: k[1])[0][0]

    for n in nodes:
        if (n.type == 'FRAME'):
            continue
        if (not allow_reroute and (n.type == 'REROUTE')):
            continue
        if (forbidden is not None) and (n in forbidden):
            continue

        locx, locy = get_node_absolute_location(n)
        dimx, dimy = n.dimensions.x/get_dpifac(), n.dimensions.y/get_dpifac()

        if (locx <= x <= locx+dimx) and \
           (locy-dimy <= y <= locy):
               nodes_under_mouse.append(n)
        continue

    if (len(nodes_under_mouse)==1):

        if nodes_under_mouse[0] != nearest_node:
              target_node = nodes_under_mouse[0]
        else: target_node = nearest_node
    else:
        target_node = nearest_node

    return target_node


def get_farest_node(node_tree):
    """find the lowest/rightest node in nodetree"""
    
    assert node_tree and node_tree.nodes, "Nodetree given is empty?"

    # Initialize to extreme values; adjust if you expect nodes to have negative positions.
    max_x, min_y = -1e6, 1e6
    farest = None

    for node in node_tree.nodes:
        x, y = node.location
        if ((x > max_x) or \
           ((x == max_x) and (y < min_y))):
            farest = node
            max_x, min_y = x, y

    return farest