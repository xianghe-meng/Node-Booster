# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# TODO implement NexVec
#  - support between vec and vec
#  - vec to float = error, float to vec == possible
#  - dunder operation between NexFloat et NexVec, see how NotImplemented pass the ball to the other class..
#  - Vec itter and slicing? using separate? x,y,z = NexVex should work, x=Vex[0] should work for e in Vec should work as well.
#  - float in vec should work as well

# TODO implement functions
#  - implement a few functions as test, see how a functions that can both work with Vec and Float will work
#    because there will be name collision. perhaps could toy with namespace similar to cpp? Hmm. this would solve it

# TODO implement NexBool
#  - with Nexbool comes comparison operations. == <= ect..

# TODO later 
#  Better errors for user:
#  - need better traceback error for NexError so user can at least now the line where it got all wrong.

# TODO later
#  Optimization:
#  - Is the NexFactory bad for performance? these factory are defining classes perhaps 10-15 times per execution
#    and execution can be at very frequent. Perhaps we can initiate the factory at node.init()? If we do that, 
#    let's first check if it's safe to do so. Maybe, storing objects there is not supported. 
#    AS a Reminder: we are storing nodetree objects in there, we'll probably need to only store the nodetree name. & get rid of node_inst.
#  - If we do a constant + Nex + constant + Nex + constant, we'll create 3 constant nodes. Unsure how to mitigate this.
#    ideally we 

# TODO nodes location
# (?) Doing math operation on a value node for the first time should relocate the value node near it's math ope. Note that
# if we optimize the note above, this thought is to be dismissed


import bpy

import traceback
from collections.abc import Iterable
from mathutils import Vector
from functools import partial

from ..__init__ import dprint
from ..nex.pytonode import convert_pyvar_to_data
from ..nex import nodesetter
from ..utils.node_utils import (
    create_new_nodegroup,
    set_socket_defvalue,
    get_socket,
    get_socket_type,
    set_socket_type,
    create_socket,
    get_socket_from_socketui,
    remove_socket,
    set_socket_label,
    link_sockets,
    create_constant_input,
    frame_nodes,
)


NEXUSER_EQUIVALENCE = {
    #inputs
    'inbool':  'NodeSocketBool',
    'inint':   'NodeSocketInt',
    'infloat': 'NodeSocketFloat',
    'invec':   'NodeSocketVector',
    'incol':   'NodeSocketColor',
    'inquat':  'NodeSocketRotation',
    'inmat':   'NodeSocketMatrix',
    #outputs
    'outbool': 'NodeSocketBool',
    'outint':  'NodeSocketInt',
    'outfloat':'NodeSocketFloat',
    'outvec':  'NodeSocketVector',
    'outcol':  'NodeSocketColor',
    'outquat': 'NodeSocketRotation',
    'outmat':  'NodeSocketMatrix',
    'outauto': 'Any..',
    }


class NexError(Exception):
    def __init__(self, message):
        super().__init__(message)


def create_Nex_tag(sockfunc, *nex_or_py_variables, startchar='F',):
    """generate an unique tag for a function and their args"""

    NexType = None
    for v in nex_or_py_variables:
        if ('Nex' in type(v).__name__):
            NexType = v
            break
    assert NexType is not None, f"Error, we should've found a Nex variable in {nex_or_py_variables}]"
    
    argtags = []
    for v in nex_or_py_variables:
        if ('Nex' in type(v).__name__):
            argtags.append(f"{v.nxchar}{v.nxid}")
            continue
        argtags.append(f"PY{type(v).__name__.lower()[0]}{NexType.init_counter}")
        continue

    uniquetag = f"{startchar}|{NexType.nxchar}.{sockfunc.__name__}({','.join(argtags)})"
    return uniquetag

def call_Nex_operand(NexType, sockfunc, *nex_or_py_variables, NexReturnType=None,):
    """call the sockfunc related to the operand with sockets of our NexTypes, and return a 
    new NexType from the newly formed socket.
    
    Each new node the sockfuncs will create will be tagged, it is essential that we don't create & 
    link the nodes if there's no need to do so, as a Nex script can be executed very frequently. 
    
    We tag them using the Nex id and types to ensure uniqueness of our values. If a tag already exists, 
    the 'reusenode' parameter of the nodesetter functions will make sure to only update the values
    of an existing node that already exists"""
    
    # Below, We generate an unique tag from the function and args & transoform nex args to sockets
    # ex: 'F|f.pow(f4,f5)'
    #     'F|f.mult(f2,Py6Int)'

    uniquetag = create_Nex_tag(sockfunc, *nex_or_py_variables)
    sock_or_py_variables = [v.nxsock if ('Nex' in type(v).__name__) else v for v in nex_or_py_variables]

    try:
        #call the socket functions with partials posargs
        r = sockfunc(NexType.node_tree, uniquetag, *sock_or_py_variables,)
    except nodesetter.InvalidTypePassedToSocket as e:
        msg = str(e)
        if ('Expected parameters in' in msg):
            msg = f"SocketTypeError. Function '{sockfunc.__name__}' Expected parameters in " + str(e).split('Expected parameters in ')[1]
        raise NexError(msg) #Note that a previous NexError Should've been raised prior to that.

    except Exception as e:
        print(f"ERROR: call_Nex_operand.sockfunc() caught error {type(e).__name__}")
        raise

    # Then return a Nextype..
    # (Support for multi outputs & if output type is not the same as input with NexReturnType)
    if (type(r) is tuple):
        if (NexReturnType is not None):
            return tuple(NexReturnType(fromsocket=s) for s in r)
        return tuple(NexType(fromsocket=s) for s in r)
    return NexType(fromsocket=r)


# unused for now
# def create_Nex_constant(node_tree, NexType, nodetype:str, value,):
#     """Create a new input node (if not already exist) ensure it's default value, then assign to a NexType & return it."""
#
#     new = NexType(manualdef=True)
#     tag = f"{new.nxchar}{new.nxid}"
#
#     # create_constant_input() is smart it will create the node only if it doesn't exist, & ensure (new?) values
#     newsock = create_constant_input(node_tree, nodetype, value, tag)
#
#     new.nxsock = newsock
#     return new


def py_to_Vec3(value):
    match value:
        case Vector():
            if (len(value)!=3): raise NexError(f"ValueError. Vector({value[:]}) should have 3 elements for fitting in a 'SocketVector'.")
            return value
        case list() | set() | tuple():
            if (len(value)!=3): raise NexError(f"ValueError. Itterable '{value}' should have 3 elements for fitting in a 'SocketVector'.")
            return Vector(value)
        case int() | float() | bool():
            return Vector((float(value), float(value), float(value),))
        case _:
            raise Exception(f"Unsuported type for {value}")

# oooooooooooo                         .                                  
# `888'     `8                       .o8                                  
#  888          .oooo.    .ooooo.  .o888oo  .ooooo.  oooo d8b oooo    ooo 
#  888oooo8    `P  )88b  d88' `"Y8   888   d88' `88b `888""8P  `88.  .8'  
#  888    "     .oP"888  888         888   888   888  888       `88..8'   
#  888         d8(  888  888   .o8   888 . 888   888  888        `888'    
# o888o        `Y888""8o `Y8bod8P'   "888" `Y8bod8P' d888b        .8'     
#                                                             .o..P'      
#                                                             `Y8P'       

def NexFactory(NODEINSTANCE, ALLINPUTS=[], ALLOUTPUTS=[],):
    """return a nex type, which is simply an overloaded custom type that automatically arrange links and nodes and
    set default values. The nextypes will/should only build the nodetree and links when neccessary.
    in ALLINPUTS/ALLOUTPUTS we collect all Nex init created when initializing any instances of a Nex type."""

    # ooooo      ooo                       
    # `888b.     `8'                       
    #  8 `88b.    8   .ooooo.  oooo    ooo 
    #  8   `88b.  8  d88' `88b  `88b..8P'  
    #  8     `88b.8  888ooo888    Y888'    
    #  8       `888  888    .o  .o8"'88b   
    # o8o        `8  `Y8bod8P' o88'   888o 

    class Nex:
        """parent class of all Nex subclasses"""

        init_counter = 0  # - Needed to define nxid, see nxid note.
        node_inst = None  # - The node affiliated with this Nex type.
        node_tree = None  # - The node.nodetree affiliated with this Nex type.
        nxstype = ''      # - The type of socket the Nex type is using.
        nxchar = ''       # - The short name of the nex type (for display reasons)

        def __init__(*args, **kwargs):
            nxsock = None # - The most important part of a NexType, it's association with an output socket!
            nxsnam = ''   # - The name of the socket (if the Nex instance is related to an input or output socket, if else will be blank)
            nxid = None   # - In order to not constantly rebuild the nodetree, but still update 
                          #    some python evaluated values to the nodetree constants (nodes starting with "C|" in the tree)
                          #    we need to have some sort of stable id for our nex Instances.
                          #    the problem is that these instances can be anonymous. So here i've decided to identify by instance generation count.

        def __repr__(self):
            return f"<{self.nxstype}{self.nxid}>"
            #return f"<{type(self)}{self.nxid} nxsock=`{self.nxsock}` isoutput={self.nxsock.is_output}' socketnode='{self.nxsock.node.name}''{self.nxsock.node.label}'>"

    # ooooo      ooo                       oooooooooooo oooo                          .   
    # `888b.     `8'                       `888'     `8 `888                        .o8   
    #  8 `88b.    8   .ooooo.  oooo    ooo  888          888   .ooooo.   .oooo.   .o888oo 
    #  8   `88b.  8  d88' `88b  `88b..8P'   888oooo8     888  d88' `88b `P  )88b    888   
    #  8     `88b.8  888ooo888    Y888'     888    "     888  888   888  .oP"888    888   
    #  8       `888  888    .o  .o8"'88b    888          888  888   888 d8(  888    888 . 
    # o8o        `8  `Y8bod8P' o88'   888o o888o        o888o `Y8bod8P' `Y888""8o   "888" 
                                                                                        
    class NexFloat(Nex):
        
        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree
        nxstype = 'NodeSocketFloat'
        nxchar = 'f'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            #create a stable identifier for our NexObject
            self.nxid = NexFloat.init_counter
            NexFloat.init_counter += 1

            #on some occation we might want to first initialize this new python object, and define it later (ot get the id)
            if (manualdef):
                return None

            #initialize from a socket?
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None
            
            # Now, define different initialization depending on given value type
            # NOTE to avoid the pitfalls of name resolution within class definitions..

            type_name = type(value).__name__
            match type_name: 

                # is user toying with  output? output cannot be reused in any way..
                case _ if ('NexOutput' in type_name):
                    raise NexError(f"Invalid use of Outputs. Cannot assign 'SocketOutput' to 'SocketInput'.")

                # a:infloat = anotherinfloat
                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid use of Inputs. Cannot assign 'SocketInput' to 'SocketInput'.")

                # initial creation by assignation, we need to create a socket type
                case 'NoneType' | 'int' | 'float' | 'bool':
                    
                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type='NodeSocketFloat', socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!='NodeSocketFloat'):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type='NodeSocketFloat', identifier=outsock.identifier,)
                    
                    self.nxsock = outsock
                    self.nxsnam = socket_name
                    
                    #ensure default value of socket in node instance
                    if (value is not None):
                        fval = float(value)
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)

                # wrong initialization?
                case _:
                    raise NexError(f"SocketTypeError. Cannot assign var '{socket_name}' of type '{type(value).__name__}' to 'SocketFloat'.")

            print(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:',self)
            return None

        # ---------------------
        # NexFloat Additions

        def __add__(self, other): # self + other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool': 
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot add type 'SocketFloat' to '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.add, *args,)

        def __radd__(self, other): # other + self
            # Multiplication is commutative.
            return self.__add__(other)

        # ---------------------
        # NexFloat Subtraction

        def __sub__(self, other): # self - other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot subtract type 'SocketFloat' with '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.sub, *args,)

        def __rsub__(self, other): # other - self
            type_name = type(other).__name__
            match type_name:
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot subtract '{type(other).__name__}' with 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.sub, *args,)

        # ---------------------
        # NexFloat Multiplication

        def __mul__(self, other): # self * other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot multiply type 'SocketFloat' with '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.mult, *args,)

        def __rmul__(self, other): # other * self
            # Multiplication is commutative.
            return self.__mul__(other)

        # ---------------------
        # NexFloat True Division

        def __truediv__(self, other): # self / other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot divide type 'SocketFloat' by '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.div, *args,)

        def __rtruediv__(self, other): # other / self
            type_name = type(other).__name__
            match type_name:
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot divide '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.div, *args,)

        # ---------------------
        # NexFloat Power

        def __pow__(self, other): #self ** other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot raise type 'SocketFloat' to the power of '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.pow, *args,)

        def __rpow__(self, other): #other ** self
            type_name = type(other).__name__
            match type_name:
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot raise '{type(other).__name__}' to the power of 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.pow, *args,)

        # ---------------------
        # NexFloat Modulo

        def __mod__(self, other): # self % other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot compute type 'SocketFloat' modulo '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.mod, *args,)

        def __rmod__(self, other): # other % self
            type_name = type(other).__name__
            match type_name:
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot compute modulo of '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.mod, *args,)

        # ---------------------
        # NexFloat Floor Division

        def __floordiv__(self, other): # self // other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = self, other
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot perform floordiv on type 'SocketFloat' with '{type(other).__name__}'.")
            sockfunc = nodesetter.floordiv
            return call_Nex_operand(NexFloat, sockfunc, *args,)

        def __rfloordiv__(self, other): # other // self
            type_name = type(other).__name__
            match type_name:
                case 'NexVec':
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot perform floor division of '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.floordiv, *args,)

        # ---------------------
        # NexFloat Negate

        def __neg__(self): # -self
            return call_Nex_operand(NexFloat, nodesetter.neg, self,)

        # ---------------------
        # NexFloat Absolute

        def __abs__(self): # abs(self)
            return call_Nex_operand(NexFloat, nodesetter.abs, self,)

    # ooooo      ooo                       oooooo     oooo                     
    # `888b.     `8'                        `888.     .8'                      
    #  8 `88b.    8   .ooooo.  oooo    ooo   `888.   .8'    .ooooo.   .ooooo.  
    #  8   `88b.  8  d88' `88b  `88b..8P'     `888. .8'    d88' `88b d88' `"Y8 
    #  8     `88b.8  888ooo888    Y888'        `888.8'     888ooo888 888       
    #  8       `888  888    .o  .o8"'88b        `888'      888    .o 888   .o8 
    # o8o        `8  `Y8bod8P' o88'   888o       `8'       `Y8bod8P' `Y8bod8P' 
                                                                            
    class NexVec(Nex):
        
        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree
        nxstype = 'NodeSocketVector'
        nxchar = 'v'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexVec.init_counter
            NexVec.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None
                        
            type_name = type(value).__name__
            match type_name:

                case _ if ('NexOutput' in type_name):
                    raise NexError(f"Invalid use of Outputs. Cannot assign 'SocketOutput' to 'SocketInput'.")

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid use of Inputs. Cannot assign 'SocketInput' to 'SocketInput'.")                

                case 'NoneType' | 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    
                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type='NodeSocketVector', socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!='NodeSocketVector'):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type='NodeSocketVector', identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name
                    
                    #ensure default value of socket in node instance
                    if (value is not None):
                        fval = py_to_Vec3(value)
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)

                case _:
                    raise NexError(f"SocketTypeError. Cannot assign var '{socket_name}' of type '{type(value).__name__}' to 'SocketVector'.")

            print(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:',self)
            return None

        # ---------------------
        # NexVec Additions

        def __add__(self, other): # self + other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot add type 'SocketVector' to '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.add, *args,)

        def __radd__(self, other): # other + self
            # Multiplication is commutative.
            return self.__add__(other)

        # ---------------------
        # NexVec Subtraction

        def __sub__(self, other): # self - other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot subtract type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.sub, *args,)

        def __rsub__(self, other): # other - self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = py_to_Vec3(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot subtract '{type(other).__name__}' with 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.sub, *args,)

        # ---------------------
        # NexVec Multiplication

        def __mul__(self, other): # self * other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot multiply type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.mult, *args,)

        def __rmul__(self, other): # other * self
            # Multiplication is commutative.
            return self.__mul__(other)

        # ---------------------
        # NexVec True Division

        def __truediv__(self, other): # self / other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot divide type 'SocketVector' by '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.div, *args,)

        def __rtruediv__(self, other): # other / self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = py_to_Vec3(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot divide '{type(other).__name__}' by 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.div, *args,)

        # ---------------------
        # NexVec Power

        def __pow__(self, other): #self ** other
            raise NexError(f"SocketTypeError. Cannot raise a 'SocketVector'.") #TODO add a function for that in nodesetter. not comprised in vector math node of blender..

        def __rpow__(self, other): #other ** self
            raise NexError(f"SocketTypeError. Cannot raise a 'SocketVector'.") #TODO add a function for that in nodesetter. not comprised in vector math node of blender..

        # ---------------------
        # NexVec Modulo

        def __mod__(self, other): # self % other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot compute type 'SocketVector' modulo '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.mod, *args,)

        def __rmod__(self, other): # other % self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = py_to_Vec3(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot compute modulo of '{type(other).__name__}' by 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.mod, *args,)

        # ---------------------
        # NexVec Floor Division

        def __floordiv__(self, other): # self // other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, py_to_Vec3(other)
                case _:
                    raise NexError(f"SocketTypeError. Cannot perform floordiv on type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.floordiv, *args,)

        def __rfloordiv__(self, other): # other // self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = py_to_Vec3(other), self
                case _:
                    raise NexError(f"SocketTypeError. Cannot perform floor division of '{type(other).__name__}' by 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.floordiv, *args,)

        # ---------------------
        # NexVec Negate

        def __neg__(self): # -self
            return call_Nex_operand(NexVec, nodesetter.neg, self,)

        # ---------------------
        # NexVec Absolute

        def __abs__(self): # abs(self)
            return call_Nex_operand(NexVec, nodesetter.abs, self,)

        # ---------------------
        # NexVec Itter

        #NOTE would be also nice to have NexVec.x .y .z maybe? hmm..

        def __len__(self):
            return 3

        def __iter__(self):
            for i in range(3):
                yield self[i]

        def __getitem__(self, key):
            """suport x = vec[0], x,y,z = vec ect.."""

            components = call_Nex_operand(NexVec, nodesetter.separate_xyz, self, NexReturnType=NexFloat,)

            match key:

                case int(): #vec[i]
                    if key not in (0,1,2):
                        raise NexError("IndexError. indice in VectorSocket[i] exceeded maximal range of 2.")
                    return components[key]

                case slice(): #vec[:i]
                    indices = range(*key.indices(3))
                    return tuple(components[i] for i in indices)

                case _:
                    raise NexError("TypeError. indices in VectorSocket[i] must be integers or slices.")
    
        def __setitem__(self, key, value):
            """support x[0] += a+b"""

            components = call_Nex_operand(NexVec, nodesetter.separate_xyz, self, NexReturnType=NexFloat)

            match key:
                case 0: components = value, components[1], components[2]
                case 1: components = components[0], value, components[2]
                case 2: components = components[0], components[1], value
                case slice():
                    raise NexError("IndexError. Slice in VectorSocket[:] not supported.")
                    #NOTE for now support for 'x[:] = x[0]*1,x[1]+2,3 ' will not work
                case _:
                    raise NexError("IndexError. indice in VectorSocket[i] exceeded maximal range of 2.")

            new = call_Nex_operand(NexFloat, nodesetter.combine_xyz, 
                components[0], components[1], components[2],
                NexReturnType=NexVec,)

            self.nxsock = new.nxsock
            self.nxid = new.nxid

            frame_nodes(self.node_tree, components[0].nxsock.node, new.nxsock.node, label=f'v.setitem[{key}]',)
            return None

    # ooooo      ooo                         .oooooo.                   .   
    # `888b.     `8'                        d8P'  `Y8b                .o8   
    #  8 `88b.    8   .ooooo.  oooo    ooo 888      888 oooo  oooo  .o888oo 
    #  8   `88b.  8  d88' `88b  `88b..8P'  888      888 `888  `888    888   
    #  8     `88b.8  888ooo888    Y888'    888      888  888   888    888   
    #  8       `888  888    .o  .o8"'88b   `88b    d88'  888   888    888 . 
    # o8o        `8  `Y8bod8P' o88'   888o  `Y8bood8P'   `V88V"V8P'   "888" 
                                                                        
    class NexOutput(Nex):
        """A nex output is just a simple linking operation. We only assign to an output.
        After assinging the final output not a lot of other operations are possible"""

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree
        nxstype = None #Children will define this.
        nxchar = 'o'

        def __init__(self, socket_name='', value=0.0):
            
            #ensure name chosen is correct. Outputs should always have a name, always!
            assert socket_name!='', "NexOutput Initialization should always define a socket_name"
            if (socket_name in ALLOUTPUTS):
                raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
            ALLOUTPUTS.append(socket_name)
            if ('Error' in socket_name):
                raise NexError("SocketNameError. Cannot use 'Error' as an output socket.")

            self.nxid = NexOutput.init_counter
            NexOutput.init_counter += 1

            type_name = type(value).__name__
            match type_name:

                # is user toying with  output? output cannot be reused in any way..
                case 'NexOutput':
                    raise NexError(f"Invalid use of Outputs. Cannot assign 'SocketOutput' to 'SocketOutput'.")

                # we link another nextype
                case _ if ('Nex' in type_name):

                    #support for automatic types
                    out_type = self.nxstype
                    if (out_type=='AutoDefine'):
                        out_type = value.nxstype
                    
                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='OUTPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='OUTPUT', socket_type=out_type, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='OUTPUT', identifier=outsock.identifier,)
                    if (current_type!=out_type):
                        outsock = set_socket_type(self.node_tree, in_out='OUTPUT', socket_type=out_type, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    # simply link the sockets and see if it's valid
                    l = link_sockets(value.nxsock, outsock)
                    if (not l.is_valid):
                        raise NexError(f"SocketTypeError. Cannot assign output '{socket_name}' of type '{self.nxstype}' to '{type(value).__name__}'.")


                # or we simply output a default python constant value
                case _:

                    newval, _, socktype = convert_pyvar_to_data(value)

                    #support for automatic types
                    out_type = self.nxstype
                    if (out_type=='AutoDefine'):
                        out_type = socktype
                        
                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='OUTPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='OUTPUT', socket_type=out_type, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='OUTPUT', identifier=outsock.identifier,)
                    if (current_type!=out_type):
                        outsock = set_socket_type(self.node_tree, in_out='OUTPUT', socket_type=out_type, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    # just do a try except to see if the var assignment to python is working.. easier.
                    try:
                        set_socket_defvalue(self.node_tree, value=newval, socket=outsock, in_out='OUTPUT',)
                    except Exception as e:
                        print(e)
                        raise NexError(f"SocketTypeError. Cannot assign output '{socket_name}' of type '{self.nxstype}' to python '{type(value).__name__}'.")

    class NexOutputBool(NexOutput):
        nxstype = 'NodeSocketBool'

    class NexOutputInt(NexOutput):
        nxstype = 'NodeSocketInt'

    class NexOutputFloat(NexOutput):
        nxstype = 'NodeSocketFloat'

    class NexOutputVec(NexOutput):
        nxstype = 'NodeSocketVector'

    class NexOutputCol(NexOutput):
        nxstype = 'NodeSocketColor'

    class NexOutputQuat(NexOutput):
        nxstype = 'NodeSocketRotation'

    class NexOutputMtx(NexOutput):
        nxstype = 'NodeSocketMatrix'

    class NexOutputAuto(NexOutput):
        nxstype = 'AutoDefine'

    # 88""Yb 888888 888888 88   88 88""Yb 88b 88     
    # 88__dP 88__     88   88   88 88__dP 88Yb88     
    # 88"Yb  88""     88   Y8   8P 88"Yb  88 Y88     
    # 88  Yb 888888   88   `YbodP' 88  Yb 88  Y8     
    
    # Return our premade types and function that the factory made for the specific NexInterpreter node context.                                                                     

    nextoys = {}
    nextoys['nexusertypes'] = {
        # 'inbool':NexBool,
        # 'inint':NexInt,
        'infloat':NexFloat,
        'invec':NexVec,
        # 'incol':NexCol,
        # 'inquat':NexQuat,
        # 'inmat':NexMtx,
        'outbool':NexOutputBool,
        'outint':NexOutputInt,
        'outfloat':NexOutputFloat,
        'outvec':NexOutputVec,
        'outcol':NexOutputCol,
        'outquat':NexOutputQuat,
        'outmat':NexOutputMtx,
        'outauto':NexOutputAuto,
        }

    def autosetNexType(socket):
        """automatically convert a node socket to Nex"""
        match socket:
            # case bpy.types.NodeSocketBool(): return NexBool(fromsocket=socket)
            # case bpy.types.NodeSocketInt(): return NexInt(fromsocket=socket)
            case bpy.types.NodeSocketFloat(): return NexFloat(fromsocket=socket)
            case bpy.types.NodeSocketVector(): return NexVec(fromsocket=socket)
            # case bpy.types.NodeSocketColor(): return NexCol(fromsocket=socket)
            # case bpy.types.NodeSocketRotation(): return NexQuat(fromsocket=socket)
            # case bpy.types.NodeSocketMatrix(): return NexMtx(fromsocket=socket)
            case _: raise Exception(f"ERROR: autosetNexType(): Unrecognized '{socket}' of type '{type(socket).__name__}'")
        return None

    def sockfunction_Nex_wrapper(sockfunc, default_ng=None,):
        """wrap a nodesetter function to transform it into a Nex functions, nodesetter fct always expecting socket or py variables
        & return sockets or tuple of sockets. Function similar to 'call_Nex_operand' but more general"""
        def wrapped_func(*args, **kwargs):
            #define reuse taga unique tag to ensure the function is not generated on each nex script run
            uniquetag = create_Nex_tag(sockfunc, *args, startchar='nF',)
            partialsockfunc = partial(sockfunc, default_ng, uniquetag)
            #sockfunc expect nodesockets, not nex..
            args = [v.nxsock if ('Nex' in type(v).__name__) else v for v in args] #we did that previously with 'sock_or_py_variables'
            #execute the function
            try:
                r = partialsockfunc(*args, **kwargs)
            except TypeError as e:
                #Cook better error message to end user
                e = str(e)
                if ('()' in e):
                    fname = e.split('()')[0]
                    if ('() missing' in e) and ('required positional argument' in e):
                        nbr = e.split('() missing ')[1][0]
                        raise NexError(f"Function '{fname}' needs {nbr} more Param(s)")
                    elif ('() takes' in e) and ('positional argument' in e):
                        raise NexError(f"Function '{fname}' recieved Extra Param(s)")
                raise
            except nodesetter.InvalidTypePassedToSocket as e:
                msg = str(e)
                if ('Expected parameters in' in msg):
                    msg = f"SocketTypeError. Function '{sockfunc.__name__}' Expected parameters in " + str(e).split('Expected parameters in ')[1]
                raise NexError(msg) #Note that a previous NexError Should've been raised prior to that.
            except Exception as e:
                print(f"ERROR: sockfunction_Nex_wrapper.sockfunc() caught error {type(e).__name__}")
                raise
            #automatically convert socket returns to nex
            if (type(r) is tuple):
                return tuple(autosetNexType(s) for s in r)
            return autosetNexType(r)
        return wrapped_func

    generalfuncs = {f.__name__ : sockfunction_Nex_wrapper(f, default_ng=NODEINSTANCE.node_tree) for f in nodesetter.get_nodesetter_functions(tag='nexgeneral')}

    nextoys['nexuserfunctions'] = {}
    nextoys['nexuserfunctions'].update(generalfuncs)
    
    return nextoys