# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE all these types are meant for the pynexscripy.py node.
#  The node is a python script evaluator that is meant to toy with these sockets.

# NOTE implicit type conversion
#  is it really a good idea to implicitly make functions and operand work cross types? ex: NexVec + NexFloat..
#  Perhaps the typing should be a little stronger and user should convert their Nex type manually.

# TODO later
#  Better errors for user:
#  - need better traceback error for NexError so user can at least now the line where it got all wrong.
#    see 'raise from e' notation perhaps?
#  Optimization:
#  - Is the NexFactory bad for performance? these factory are defining classes perhaps 10-15 times per execution
#    and execution can be at very frequent. Perhaps we can initiate the factory at node.init()? If we do that, 
#    let's first check if it's safe to do so. Maybe, storing objects there is not supported. 
#    AS a Reminder: we are storing nodetree objects in there, we'll probably need to only store the nodetree name. & get rid of node_inst.
#  - If we do a constant + Nex + constant + Nex + constant, we'll create 3 constant nodes. Unsure how to mitigate this.
#    ideally we 
#  Code Redundency:
#  - A lot of operation overloads are very simimar. Some math and comparison operation are repeated across many NexTypes.
#    perhaps could centralize some operations via class inheritence 'NexMath' 'NexCompare' to not repeat function def?


import bpy

import traceback
from mathutils import Vector, Matrix
from functools import partial

from ..__init__ import dprint
from ..nex.pytonode import py_to_Sockdata, py_to_Mtx16, py_to_Vec3
from ..nex import nodesetter
from ..utils.fct_utils import alltypes, anytype
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

def NexErrorWrapper(convert_func):
    """NexError wrapper for function that try to convert pydata to sockets compatible data.
    should raise NexError not TypeError if conversion failed"""
    def wrap(*args,**kwargs):
        try:
            return convert_func(*args,**kwargs)
        except TypeError as e:
            raise NexError('TypeError. '+str(e))
        except Exception as e:
            print(f"ERROR: NexErrorWrapper.{convert_func.__name__}() caught error {type(e).__name__}")
            raise
    return wrap

trypy_to_Sockdata = NexErrorWrapper(py_to_Sockdata)
trypy_to_Mtx16 = NexErrorWrapper(py_to_Mtx16)
trypy_to_Vec3 = NexErrorWrapper(py_to_Vec3)


def create_Nex_tag(sockfunc, *nex_or_py_variables, startchar='F',):
    """generate an unique tag for a function and their args"""

    NexType = None
    for v in nex_or_py_variables:
        if ('Nex' in type(v).__name__):
            NexType = v
            break
    assert NexType is not None, f"We should've found a Nex variable in  {sockfunc.__name__}{nex_or_py_variables}"

    argtags = []
    for v in nex_or_py_variables:
        if ('Nex' in type(v).__name__):
            argtags.append(f"{v.nxchar}{v.nxid}")
            continue
        argtags.append(f"p{type(v).__name__.lower()[0]}{NexType.init_counter}") #better support for python args? how to identify them properly given that their values can change?
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
            msg = f"TypeError. Function {sockfunc.__name__}() Expected parameters in " + str(e).split('Expected parameters in ')[1]
        raise NexError(msg) #Note that a previous NexError Should've been raised prior to that.. If the user see that error, the nextype didn't handle typing properly..

    except Exception as e:
        print(f"ERROR: call_Nex_operand.sockfunc() caught error {type(e).__name__}")
        raise
    
    # Then return a Nextype..
    # (Support for multi outputs & if output type is not the same as input with NexReturnType)
    # NOTE perhaps is better to use autosetNexType() for the wrapping the return Nex than manually defining a NexReturnType? Will need to move this fct in factory then..
    if (NexReturnType is not None):
        NexType = NexReturnType
    if (type(r) is tuple):
        return tuple(NexType(fromsocket=s) for s in r)        
    return NexType(fromsocket=r)

def create_Nex_constant(node_tree, NexType, value,):
    """Create a new input node (if not already exist) ensure it's default value, then assign to a NexType & return it."""

    new = NexType(manualdef=True)
    tag = f"C|{new.nxchar}{new.nxid}.constant(p{type(value).__name__.lower()[0]})"
    
    type_name = NexType.__name__
    match type_name:
        case 'NexMtx':
            nodetype = 'FunctionNodeCombineMatrix'
        case _:
            raise Exception(f"create_Nex_constant() Unsupported constant for Nextype '{type_name}'.")

    # create_constant_input() is smart it will create the node only if it doesn't exist, & ensure (new?) values
    newsock = create_constant_input(node_tree, nodetype, value, tag)

    new.nxsock = newsock
    return new

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

        nxstype = ''      # - The exact type of socket the Nex type is using.
        nxtydsp = ''      # - The user display type of socket.
        nxchar = ''       # - The character assigned to this Nextype.

        def __init__(*args, **kwargs):
            nxsock = None # - The most important part of a NexType, it's association with an output socket!
            nxsnam = ''   # - The name of the socket (if the Nex instance is related to an input or output socket, if else will be blank)
            nxid = None   # - In order to not constantly rebuild the nodetree, but still update 
                          #    some python evaluated values to the nodetree constants (nodes starting with "C|" in the tree)
                          #    we need to have some sort of stable id for our nex Instances.
                          #    the problem is that these instances can be anonymous. So here i've decided to identify by instance generation count.

        # Nex Math Operand
        def __add__(self, other): # self + other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '+'.")
        def __radd__(self, other): # other + self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '+'.")
        def __sub__(self, other): # self - other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '-'.")
        def __rsub__(self, other): # other - self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '-'.")
        def __mul__(self, other): # self * other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '*'.")
        def __rmul__(self, other): # other * self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '*'.")
        def __truediv__(self, other): # self / other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '/'.")
        def __rtruediv__(self, other): # other / self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '/'.")
        def __pow__(self, other): #self ** other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '**'.")
        def __rpow__(self, other): #other ** self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '**'.")
        def __mod__(self, other): # self % other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '%'.")
        def __rmod__(self, other): # other % self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '%'.")
        def __floordiv__(self, other): # self // other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '//'.")
        def __rfloordiv__(self, other): # other // self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '//'.")
        def __neg__(self): # -self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support negation.")
        def __abs__(self): # abs(self)
            raise NexError(f"TypeError.  '{self.nxtydsp}' has no abs() method.")
        def __round__(self): # round(self)
            raise NexError(f"TypeError.  '{self.nxtydsp}' has no round() method.")
        def __matmul__(self, other): # self @ other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '@'.")
        def __rmatmul__(self, other): # other @ self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '@'.")
        
        # Nex Itter
        def __len__(self): #len(itter)
            raise NexError(f"TypeError. '{self.nxtydsp}' has no len() method.")
        def __iter__(self): #for f in itter
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")
        def __getitem__(self, key): #suport x = vec[0], x,y,z = vec ect..
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")
        def __setitem__(self, key, value): #x[0] += a+b
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")

        # Nex Comparisons
        def __eq__(self, other): # self == other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '=='.")
        def __ne__(self, other): # self != other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '!='.")
        def __lt__(self, other): # self < other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '<'.")
        def __le__(self, other): # self <= other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '<='.")
        def __gt__(self, other): # self > other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '>'.")
        def __ge__(self, other): # self >= other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '>='.")

        # Nex Bitwise
        def __and__(self, other): # self & other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '&'.")
        def __rand__(self, other): # other & self
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '&'.")
        def __or__(self, other): # self | other
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '|'.")
        def __ror__(self, other): # other | self
            raise NexError(f"TypeError. '{self.nxtydsp}' do not support operand '|'.")

        # Nex python bool evaluation? Impossible.
        def __bool__(self):
            raise NexError(f"EvaluationError. Cannot evaluate '{self.nxtydsp}' as a python boolean.")

        # print the Nex
        def __repr__(self):
            return f"<{type(self.nxsock).__name__ if self.nxsock else 'NoneSocket'} {type(self).__name__}{self.nxid}>"
            return f"<{type(self)}{self.nxid} nxsock=`{self.nxsock}` isoutput={self.nxsock.is_output}' socketnode='{self.nxsock.node.name}''{self.nxsock.node.label}'>"

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
        nxtydsp = 'SocketFloat'
        nxchar = 'f'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            # Important, we create a stable identifier for our Nex object
            # used for building a tree we can recognize on second run
            self.nxid = NexFloat.init_counter
            NexFloat.init_counter += 1

            #We have 3 Initialization method..

            #1: Manual initialization
            #on some occation we might want to first initialize this new python object, and define it later (ot get the id)
            if (manualdef):
                return None

            #2: From socket initialization used 
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None

            #3: User initialization that will create new a socket 'myvalue:infloat = 3' or 'myvalue = infloat('myvalue',3). 
            # Define different initialization depending on given value type
            type_name = type(value).__name__
            match type_name: 

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                #Initialize a new nextype with a default value socket
                case 'NoneType' | 'int' | 'float' | 'bool':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type=self.nxstype, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!=self.nxstype):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type=self.nxstype, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    #ensure default value of socket in node instance
                    if (value is not None):
                        fval = float(value)
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)

                # wrong initialization?
                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketFloat'. Was expecting 'None' | 'int' | 'float' | 'bool'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None
        
        # ---------------------
        # NexFloat Additions

        def __add__(self, other): # self + other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool': 
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot add type 'SocketFloat' to '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.add, *args,)

        def __radd__(self, other): # other + self
            # commutative operation.
            return self.__add__(other)

        # ---------------------
        # NexFloat Subtraction

        def __sub__(self, other): # self - other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot subtract type 'SocketFloat' with '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.sub, *args,)

        def __rsub__(self, other): # other - self
            type_name = type(other).__name__
            match type_name:
                case 'NexInt' | 'NexBool':
                    args = other, self
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"TypeError. Cannot subtract '{type(other).__name__}' with 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.sub, *args,)

        # ---------------------
        # NexFloat Multiplication

        def __mul__(self, other): # self * other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot multiply type 'SocketFloat' with '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.mult, *args,)

        def __rmul__(self, other): # other * self
            # commutative operation.
            return self.__mul__(other)

        # ---------------------
        # NexFloat True Division

        def __truediv__(self, other): # self / other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot divide type 'SocketFloat' by '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.div, *args,)

        def __rtruediv__(self, other): # other / self
            type_name = type(other).__name__
            match type_name:
                case 'NexInt' | 'NexBool':
                    args = other, self
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"TypeError. Cannot divide '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.div, *args,)

        # ---------------------
        # NexFloat Power

        def __pow__(self, other): #self ** other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot raise type 'SocketFloat' to the power of '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.pow, *args,)

        def __rpow__(self, other): #other ** self
            type_name = type(other).__name__
            match type_name:
                case 'NexInt' | 'NexBool':
                    args = other, self
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"TypeError. Cannot raise '{type(other).__name__}' to the power of 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.pow, *args,)

        # ---------------------
        # NexFloat Modulo

        def __mod__(self, other): # self % other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot compute type 'SocketFloat' modulo '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.mod, *args,)

        def __rmod__(self, other): # other % self
            type_name = type(other).__name__
            match type_name:
                case 'NexInt' | 'NexBool':
                    args = other, self
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"TypeError. Cannot compute modulo of '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.mod, *args,)

        # ---------------------
        # NexFloat Floor Division

        def __floordiv__(self, other): # self // other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform floordiv on type 'SocketFloat' with '{type(other).__name__}'.")
            return call_Nex_operand(NexFloat, nodesetter.floordiv, *args,)

        def __rfloordiv__(self, other): # other // self
            type_name = type(other).__name__
            match type_name:
                case 'NexInt' | 'NexBool':
                    args = other, self
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = float(other), self
                case _:
                    raise NexError(f"TypeError. Cannot perform floor division of '{type(other).__name__}' by 'SocketFloat'.")
            return call_Nex_operand(NexFloat, nodesetter.floordiv, *args,)

        # ---------------------
        # NexFloat Negate

        def __neg__(self): # -self
            return call_Nex_operand(NexFloat, nodesetter.neg, self,)

        # ---------------------
        # NexFloat Absolute

        def __abs__(self): # abs(self)
            return call_Nex_operand(NexFloat, nodesetter.abs, self,)

        # ---------------------
        # NexFloat Round
        
        def __round__(self): # round(self)
            return call_Nex_operand(NexFloat, nodesetter.round, self,)
    
        # ---------------------
        # NexFloat Comparisons
        #NOTE a==b==c will not work because and is involved and we cannot override it.. and/or/not keywords rely on python booleans type...

        def __eq__(self, other): # self == other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '==' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.iseq, *args,  NexReturnType=NexBool,)

        def __ne__(self, other): # self != other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '!=' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.isuneq, *args,  NexReturnType=NexBool,)

        def __lt__(self, other): # self < other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '<' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.isless, *args,  NexReturnType=NexBool,)

        def __le__(self, other): # self <= other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '<=' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.islesseq, *args,  NexReturnType=NexBool,)

        def __gt__(self, other): # self > other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '>' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.isgreater, *args,  NexReturnType=NexBool,)

        def __ge__(self, other): # self >= other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '>=' comparison between types 'SocketFloat' and '{type(other).__name__}'")
            return call_Nex_operand(NexFloat, nodesetter.isgreatereq, *args,  NexReturnType=NexBool,)


        # ---------------------
        # NexFloat Custom Functions & Properties
        # ...

    # ooooo      ooo                       oooooooooo.                      oooo  
    # `888b.     `8'                       `888'   `Y8b                     `888  
    #  8 `88b.    8   .ooooo.  oooo    ooo  888     888  .ooooo.   .ooooo.   888  
    #  8   `88b.  8  d88' `88b  `88b..8P'   888oooo888' d88' `88b d88' `88b  888  
    #  8     `88b.8  888ooo888    Y888'     888    `88b 888   888 888   888  888  
    #  8       `888  888    .o  .o8"'88b    888    .88P 888   888 888   888  888  
    # o8o        `8  `Y8bod8P' o88'   888o o888bood8P'  `Y8bod8P' `Y8bod8P' o888o 

    class NexBool(Nex):

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree

        nxstype = 'NodeSocketBool'
        nxtydsp = 'SocketBool'
        nxchar = 'b'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexBool.init_counter
            NexBool.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None

            type_name = type(value).__name__
            match type_name: 

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                #Initialize a new nextype with a default value socket
                case 'NoneType' | 'bool':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type=self.nxstype, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!=self.nxstype):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type=self.nxstype, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    #ensure default value of socket in node instance
                    if (value is not None):
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=value, in_out='INPUT',)

                # wrong initialization?
                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketBool'. Was expecting 'None' | 'bool'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexBool Comparisons
        #NOTE a==b==c will not work because and is involved and we cannot override it.. and/or/not keywords rely on python booleans type...

        def __eq__(self, other): # self == other
            type_name = type(other).__name__
            match type_name:
                case 'NexBool' | 'bool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case _:
                    raise NexError(f"TypeError. Cannot perform '==' comparison between types 'SocketBool' and '{type(other).__name__}'")
            return call_Nex_operand(NexBool, nodesetter.iseq, *args,)

        def __ne__(self, other): # self != other
            type_name = type(other).__name__
            match type_name:
                case 'NexBool' | 'bool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    return NotImplemented
                case _:
                    raise NexError(f"TypeError. Cannot perform '!=' comparison between types 'SocketBool' and '{type(other).__name__}'")
            return call_Nex_operand(NexBool, nodesetter.isuneq, *args,)

        # ---------------------
        # NexBool Bitwise Operations

        def __and__(self, other): # self & other
            type_name = type(other).__name__
            match type_name:
                case 'NexBool' | 'bool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Bitwise operation '&' is exclusive between 'SocketBool'.")
                case _:
                    raise NexError(f"TypeError. Cannot perform '&' bitwise operation between 'SocketBool' and '{type(other).__name__}'.")
            return call_Nex_operand(NexBool, nodesetter.booland, *args,)

        def __rand__(self, other): # other & self
            # commutative operation.
            return self.__and__(other)

        def __or__(self, other): # self | other
            type_name = type(other).__name__
            match type_name:
                case 'NexBool' | 'bool':
                    args = self, other
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Bitwise operation '|' is exclusive between 'SocketBool'.")
                case _:
                    raise NexError(f"TypeError. Cannot perform '|' bitwise operation between 'SocketBool' and '{type(other).__name__}'.")
            return call_Nex_operand(NexBool, nodesetter.boolor, *args,)

        def __ror__(self, other): # other | self
            # commutative operation.
            return self.__or__(other)

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
        nxtydsp = 'SocketVector'
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

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")
                
                #Initialize a new nextype with a default value socket
                case 'NoneType' | 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    
                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type=self.nxstype, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!=self.nxstype):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type=self.nxstype, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    #ensure default value of socket in node instance
                    if (value is not None):
                        fval = trypy_to_Vec3(value)
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)

                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketVector'. Was expecting 'None' | 'Vector[3]' | 'list[3]' | 'set[3]' | 'tuple[3]' | 'int' | 'float' | 'bool'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexVec Additions

        def __add__(self, other): # self + other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot add type 'SocketVector' to '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.add, *args,)

        def __radd__(self, other): # other + self
            # commutative operation.
            return self.__add__(other)

        # ---------------------
        # NexVec Subtraction

        def __sub__(self, other): # self - other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot subtract type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.sub, *args,)

        def __rsub__(self, other): # other - self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = trypy_to_Vec3(other), self
                case _:
                    raise NexError(f"TypeError. Cannot subtract '{type(other).__name__}' with 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.sub, *args,)

        # ---------------------
        # NexVec Multiplication

        def __mul__(self, other): # self * other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot multiply type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.mult, *args,)

        def __rmul__(self, other): # other * self
            # commutative operation.
            return self.__mul__(other)

        # ---------------------
        # NexVec True Division

        def __truediv__(self, other): # self / other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot divide type 'SocketVector' by '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.div, *args,)

        def __rtruediv__(self, other): # other / self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = trypy_to_Vec3(other), self
                case _:
                    raise NexError(f"TypeError. Cannot divide '{type(other).__name__}' by 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.div, *args,)

        # ---------------------
        # NexVec Power

        def __pow__(self, other):  # self ** other
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                case 'NexVec' | 'Vector':
                    raise NexError(f"TypeError. Cannot raise a Vector to another Vector. Exponent must be float compatible.")
                case _:
                    raise NexError(f"TypeError. Cannot raise 'SocketVector' to the power of '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.pow, *args,)

        def __rpow__(self, other):  # other ** self
            raise NexError(f"TypeError. Cannot raise '{type(other).__name__}' to the power of 'SocketVector'.")

        # ---------------------
        # NexVec Modulo

        def __mod__(self, other): # self % other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot compute type 'SocketVector' modulo '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.mod, *args,)

        def __rmod__(self, other): # other % self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = trypy_to_Vec3(other), self
                case _:
                    raise NexError(f"TypeError. Cannot compute modulo of '{type(other).__name__}' by 'SocketVector'.")
            return call_Nex_operand(NexVec, nodesetter.mod, *args,)

        # ---------------------
        # NexVec Floor Division

        def __floordiv__(self, other): # self // other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform floordiv on type 'SocketVector' with '{type(other).__name__}'.")
            return call_Nex_operand(NexVec, nodesetter.floordiv, *args,)

        def __rfloordiv__(self, other): # other // self
            type_name = type(other).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = trypy_to_Vec3(other), self
                case _:
                    raise NexError(f"TypeError. Cannot perform floor division of '{type(other).__name__}' by 'SocketVector'.")
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
        # NexVec Round

        def __round__(self): # round(self)
            return call_Nex_operand(NexVec, nodesetter.round, self,)

        # ---------------------
        # NexVec Itter

        def __len__(self): #len(itter)
            return 3

        def __iter__(self): #for f in itter
            for i in range(3):
                yield self[i]

        def __getitem__(self, key): #suport x = vec[0], x,y,z = vec ect..

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

        def __setitem__(self, key, value): #x[0] += a+b

            to_frame = []

            match key:

                case int(): #vec[i]
                    separated = call_Nex_operand(NexVec, nodesetter.separate_xyz, self, NexReturnType=NexFloat)
                    to_frame.append(separated[0].nxsock.node)
                    if (key==0):
                        new_components = value, separated[1], separated[2]
                    elif (key==1):
                        new_components = separated[0], value, separated[2]
                    elif (key==2):
                        new_components = separated[0], separated[1], value
                    else:
                        raise NexError("IndexError. indice in VectorSocket[i] exceeded maximal range of 2.")

                case slice():
                    if (key!=slice(None,None,None)):
                        raise NexError("Only [:] slicing is supported for SocketVector.")
                    new_components = tuple(value)
                    if (len(new_components)!=3):
                        raise NexError("Slice assignment requires exactly 3 values.")

                case _:
                    raise NexError("TypeError. indices in VectorSocket[i] must be integers or slices.")

            new = call_Nex_operand(NexFloat, nodesetter.combine_xyz, 
                new_components[0], new_components[1], new_components[2],
                NexReturnType=NexVec,)

            self.nxsock = new.nxsock
            self.nxid = new.nxid
            to_frame.append(new.nxsock.node)
    
            frame_nodes(self.node_tree, *to_frame, 
                label=f"v.setitem[{key if (type(key) is int) else ':'}]",
                )
            return None

        # ---------------------
        # NexVec Comparisons
        #NOTE a==b==c will not work because and is involved and we cannot override it.. and/or/not keywords rely on python booleans type...

        def __eq__(self, other): # self == other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '==' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.iseq, *args, NexReturnType=NexBool,)

        def __ne__(self, other): # self != other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '!=' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.isuneq, *args, NexReturnType=NexBool,)

        def __lt__(self, other): # self < other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '<' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.isless, *args, NexReturnType=NexBool,)

        def __le__(self, other): # self <= other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '<=' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.islesseq, *args, NexReturnType=NexBool,)

        def __gt__(self, other): # self > other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '>' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.isgreater, *args, NexReturnType=NexBool,)

        def __ge__(self, other): # self >= other
            type_name = type(other).__name__
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other
                case 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    args = self, trypy_to_Vec3(other)
                case _:
                    raise NexError(f"TypeError. Cannot perform '>=' comparison between types 'SocketVector' and '{type(other).__name__}'")
            return call_Nex_operand(NexVec, nodesetter.isgreatereq, *args, NexReturnType=NexBool,)

        # ---------------------
        # NexVec Custom Functions & Properties

        @property
        def x(self):
            return self[0]
        @x.setter
        def x(self, value):
            self[0] = value

        @property
        def y(self):
            return self[1]
        @y.setter
        def y(self, value):
            self[1] = value

        @property
        def z(self):
            return self[2]
        @z.setter
        def z(self, value):
            self[2] = value

        @property
        def xyz(self):
            return self[:]
        @xyz.setter
        def xyz(self, value):
            if (type(value) is tuple and len(value)==3):
                  self[:] = value
            else: raise NexError("TypeError. Assignment to SocketVector.xyz is expected to be a tuple of length 3 containing sockets or Python values.")

        @property
        def length(self):
            return call_Nex_operand(NexVec, nodesetter.length, self, NexReturnType=NexFloat,)
        @length.setter
        def length(self, value):
            raise NexError("AssignationError. 'SocketVector.length' is read-only.")

        @property
        def normalized(self):
            return call_Nex_operand(NexVec, nodesetter.normalize, self,)
        @normalized.setter
        def normalized(self, value):
            raise NexError("AssignationError. 'SocketVector.normalized' is read-only.")

    # ooooo      ooo                       ooo        ooooo     .               
    # `888b.     `8'                       `88.       .888'   .o8               
    #  8 `88b.    8   .ooooo.  oooo    ooo  888b     d'888  .o888oo oooo    ooo 
    #  8   `88b.  8  d88' `88b  `88b..8P'   8 Y88. .P  888    888    `88b..8P'  
    #  8     `88b.8  888ooo888    Y888'     8  `888'   888    888      Y888'    
    #  8       `888  888    .o  .o8"'88b    8    Y     888    888 .  .o8"'88b   
    # o8o        `8  `Y8bod8P' o88'   888o o8o        o888o   "888" o88'   888o 

    class NexMtx(Nex):

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree

        nxstype = 'NodeSocketMatrix'
        nxtydsp = 'SocketMatrix'
        nxchar = 'm'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexMtx.init_counter
            NexMtx.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None

            type_name = type(value).__name__
            match type_name:

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                #Initialize a new nextype with a default value socket
                case 'NoneType': # | 'Matrix' | 'list' | 'set' | 'tuple':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket(self.node_tree, in_out='INPUT', socket_name=socket_name,)
                    if (outsock is None):
                        outsock = create_socket(self.node_tree, in_out='INPUT', socket_type=self.nxstype, socket_name=socket_name,)
                    elif (type(outsock) is list):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    #ensure type is correct, change type if necessary
                    current_type = get_socket_type(self.node_tree, in_out='INPUT', identifier=outsock.identifier,)
                    if (current_type!=self.nxstype):
                        outsock = set_socket_type(self.node_tree, in_out='INPUT', socket_type=self.nxstype, identifier=outsock.identifier,)

                    self.nxsock = outsock
                    self.nxsnam = socket_name

                    # #ensure default value of socket in node instance
                    # if (value is not None):
                    #     fval = trypy_to_Mtx16(value)
                    #     set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)
                    #     NOTE: SocketMatrix type do not support assigning a default socket values.

                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketMatrix'. Was expecting 'None'")# | 'Matrix[16]' | 'list[16]' | 'set[16]' | 'tuple[16]'")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexMtx Matrix Mult

        def __matmul__(self, other): # self @ other
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx':
                    args = self, other
                    sockfunc, rType = nodesetter.matrixmult, NexMtx
                case 'NexVec':
                    args = self, other
                    sockfunc, rType = nodesetter.matrixtransformloc, NexVec
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot do a matrix multiplication operation with 'SocketMatrix' and '{other.nxtydsp}'.")
                case 'Vector':
                    args = self, trypy_to_Vec3(other)
                    sockfunc, rType = nodesetter.matrixtransformloc, NexVec
                case 'Matrix':
                    convother = trypy_to_Mtx16(other)
                    othernex = create_Nex_constant(self.node_tree, NexMtx, convother,)
                    args = self, othernex
                    sockfunc, rType = nodesetter.matrixmult, NexMtx
                case 'list' | 'set' | 'tuple':
                    if len(other)<=3:
                        args = self, trypy_to_Vec3(other)
                        sockfunc, rType = nodesetter.matrixtransformloc, NexVec
                    else:
                        convother = trypy_to_Mtx16(other)
                        othernex = create_Nex_constant(self.node_tree, NexMtx, convother,)
                        args = self, othernex
                        sockfunc, rType = nodesetter.matrixmult, NexMtx
                case _:
                    raise NexError(f"TypeError. Cannot do a matrix multiplication operation with 'SocketMatrix' and '{type(other).__name__}'.")
            return call_Nex_operand(NexMtx,  sockfunc, *args, NexReturnType=rType,)

        def __rmatmul__(self, other): # other @ self
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx':
                    return NotImplemented
                case 'NexVec' | 'Vector':
                    raise NexError(f"TypeError. Cannot matrix-multiply TypeVector by a TypeMatrix. Please do 'Matrix @ Vector' instead.")
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot do a matrix multiplication operation with '{other.nxtydsp}' and 'SocketMatrix'.")
                case 'Matrix' | 'list' | 'set' | 'tuple':
                    convother = trypy_to_Mtx16(other)
                    othernex = create_Nex_constant(self.node_tree, NexMtx, convother,)
                    args = othernex, self
                    sockfunc, rType = nodesetter.matrixmult, NexMtx
                case _:
                    raise NexError(f"TypeError. Cannot do a matrix multiplication operation with '{type(other).__name__}' and 'SocketMatrix'.")
            return call_Nex_operand(NexMtx, sockfunc, *args, NexReturnType=rType,)

        # ---------------------
        # NexMtx Custom Functions & Properties

        @property
        def determinant(self):
            return call_Nex_operand(NexMtx, nodesetter.matrixdeterminant, self, NexReturnType=NexFloat,)
        @determinant.setter
        def determinant(self, value):
            raise NexError("AssignationError. 'SocketMatrix.determinant' is read-only.")

        @property
        def is_invertible(self):
            return call_Nex_operand(NexMtx, nodesetter.matrixisinvertible, self, NexReturnType=NexBool,)
        @is_invertible.setter
        def is_invertible(self, value):
            raise NexError("AssignationError. 'SocketMatrix.is_invertible' is read-only.")

        @property
        def inverted(self):
            return call_Nex_operand(NexMtx, nodesetter.matrixinvert, self,)
        @inverted.setter
        def inverted(self, value):
            raise NexError("AssignationError. 'SocketMatrix.inverted' is read-only.")

        @property
        def transposed(self):
            return call_Nex_operand(NexMtx, nodesetter.matrixtranspose, self,)
        @transposed.setter
        def transposed(self, value):
            raise NexError("AssignationError. 'SocketMatrix.transposed' is read-only.")

        def transform_point(self, vec):
            return call_Nex_operand(NexMtx, nodesetter.matrixtransformloc, self,vec, NexReturnType=NexVec,)

        def project_point(self, vec):
            return call_Nex_operand(NexMtx, nodesetter.matrixprojectloc, self,vec, NexReturnType=NexVec,)

        def transform_direction(self, vec):
            return call_Nex_operand(NexMtx, nodesetter.matrixtransformdir, self,vec, NexReturnType=NexVec,)

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

        nxstype = None #Children definition..
        nxtydsp = None #Children definition..
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
                    if (out_type=='NodeSocketNexAutomatic'):
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
                        raise NexError(f"TypeError. Cannot assign '{value.nxtydsp}' to var '{socket_name}' of output '{self.nxtydsp}'.")

                # or we simply output a default python constant value
                case _:

                    # try to convert our pyvalue to a socket compatible datatype.
                    newval, _, socktype = trypy_to_Sockdata(value)
                    
                    #support for automatic types
                    out_type = self.nxstype
                    if (out_type=='NodeSocketNexAutomatic'):
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
                        raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of output '{self.nxtydsp}'.")

    class NexOutputBool(NexOutput):
        nxstype = 'NodeSocketBool'
        nxtydsp = 'SocketBool'

    class NexOutputInt(NexOutput):
        nxstype = 'NodeSocketInt'
        nxtydsp = 'SocketInt'

    class NexOutputFloat(NexOutput):
        nxstype = 'NodeSocketFloat'
        nxtydsp = 'SocketFloat'

    class NexOutputVec(NexOutput):
        nxstype = 'NodeSocketVector'
        nxtydsp = 'SocketVector'

    class NexOutputCol(NexOutput):
        nxstype = 'NodeSocketColor'
        nxtydsp = 'SocketColor'

    class NexOutputQuat(NexOutput):
        nxstype = 'NodeSocketRotation'
        nxtydsp = 'SocketRotation'

    class NexOutputMtx(NexOutput):
        nxstype = 'NodeSocketMatrix'
        nxtydsp = 'SocketMatrix'

    class NexOutputAuto(NexOutput):
        nxstype = 'NodeSocketNexAutomatic'
        nxtydsp = 'SocketAuto'

    # 88""Yb 888888 888888 88   88 88""Yb 88b 88     
    # 88__dP 88__     88   88   88 88__dP 88Yb88     
    # 88"Yb  88""     88   Y8   8P 88"Yb  88 Y88     
    # 88  Yb 888888   88   `YbodP' 88  Yb 88  Y8     
    
    # Return our premade types and function that the factory made for the specific NexInterpreter node context.                                                                     

    nextoys = {}
    nextoys['nexusertypes'] = {
        'inbool':NexBool,
        # 'inint':NexInt,
        'infloat':NexFloat,
        'invec':NexVec,
        # 'incol':NexCol,
        # 'inquat':NexQuat,
        'inmat':NexMtx,
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
            case bpy.types.NodeSocketBool(): return NexBool(fromsocket=socket)
            # case bpy.types.NodeSocketInt(): return NexInt(fromsocket=socket)
            case bpy.types.NodeSocketFloat(): return NexFloat(fromsocket=socket)
            case bpy.types.NodeSocketVector(): return NexVec(fromsocket=socket)
            case bpy.types.NodeSocketVectorXYZ(): return NexVec(fromsocket=socket)
            # case bpy.types.NodeSocketColor(): return NexCol(fromsocket=socket)
            # case bpy.types.NodeSocketRotation(): return NexQuat(fromsocket=socket)
            case bpy.types.NodeSocketMatrix(): return NexMtx(fromsocket=socket)
            case _: raise Exception(f"ERROR: autosetNexType(): Unrecognized '{socket}' of type '{type(socket).__name__}'")
        return None

    def sockfunction_Nex_wrapper(sockfunc, default_ng=None,):
        """wrap a nodesetter function to transform it into a Nex functions, nodesetter fct always expecting socket or py variables
        & return sockets or tuple of sockets. Function similar to 'call_Nex_operand' but more general"""

        #TODO What if user is using some Nexfunc on only python values?
        # when we wrap a function we need a unique id tag so the nodetree construction stays stable cross execution. 
        # The problem is that for now we can't generate a unique tag if the user is using a Nexfunction with only python values.
        # Some of these functions supports only python args as they will execute math funcs instead. We need a better solution for handling pyvalue in the nodetree.

        def wrapped_func(*args, **kwargs):

            uniquetag = None

            # The user is using a NexFunction but he passed no NexType arguments?
            if not any(('Nex' in type(v).__name__) for v in args):
                funcname = sockfunc.__name__
                match funcname:

                    # Name conflict with python bultin functions? 
                    # If no NexType are involved, we simply call builtin function, no Nexwrapper!
                    case 'min': return min(*args, **kwargs)
                    case 'max': return max(*args, **kwargs)

                    # Name conflict with math module functions?
                    # If no NexType are involved, we simply call builtin math function, no Nexwrapper!
                    case 'cos'|'sin'|'tan'|'acos'|'asin'|'atan'|'cosh'|'sinh'|'tanh'|'sqrt'|'log'|'degrees'|'radians'|'floor'|'ceil'|'trunc':
                        import math
                        mathfunction = getattr(math,funcname)
                        return mathfunction(*args, **kwargs)
                    
                    # Some functions do not require to generate a unique tag.
                    case 'getp'|'getn':
                        uniquetag = f'F|{funcname}()'

                    case _:
                        raise NexError(f"ParamTypeError. Function {sockfunc.__name__}() didn't recieved any SocketType.")

            #define reuse taga unique tag to ensure the function is not generated on each nex script run
            if (uniquetag is None):
                uniquetag = create_Nex_tag(sockfunc, *args,)

            #define a function with the first two args already defined
            partialsockfunc = partial(sockfunc, default_ng, uniquetag)

            #sockfunc expect nodesockets, not nextype, we need to convert their args to sockets.. (we did that previously with 'sock_or_py_variables')
            args = [v.nxsock if ('Nex' in type(v).__name__) else v for v in args]
            #support for tuple as vectors
            args = [trypy_to_Vec3(v) if (isinstance(v,(tuple,list)) and len(v)==3 and all(isinstance(i,(float,int)) for i in v)) else v for v in args]

            #Call the Nex function
            try:
                r = partialsockfunc(*args, **kwargs)

            except TypeError as e:
                #Cook better error message to end user
                e = str(e)
                if ('()' in e):
                    fname = e.split('()')[0]
                    if ('() missing' in e) and ('required positional argument' in e):
                        nbr = e.split('() missing ')[1][0]
                        raise NexError(f"Function {fname}() needs {nbr} more Param(s)")
                    elif ('() takes' in e) and ('positional argument' in e):
                        raise NexError(f"Function {fname}() recieved Extra Param(s)")
                raise

            except nodesetter.InvalidTypePassedToSocket as e:
                msg = str(e)
                if ('Expected parameters in' in msg):
                    msg = f"TypeError. Function {sockfunc.__name__}() Expected parameters in " + str(e).split('Expected parameters in ')[1]
                raise NexError(msg) #Note that a previous NexError Should've been raised prior to that.

            except Exception as e:
                print(f"ERROR: sockfunction_Nex_wrapper.sockfunc() caught error {type(e).__name__}")
                raise

            # Wrap return value as Nex as well

            if ((type(r) is not tuple) and (not issubclass(type(r), bpy.types.NodeSocket))):
                raise Exception(f"Function '{sockfunc}' did not return a NodeSocket. This should never happen.")
            if (type(r) is tuple):
                return tuple(autosetNexType(s) for s in r)
            return autosetNexType(r)

        return wrapped_func

    nexfunctions = {f.__name__ : sockfunction_Nex_wrapper(f, default_ng=NODEINSTANCE.node_tree) for f in nodesetter.get_nodesetter_functions(tag='nexscript')}

    nextoys['nexuserfunctions'] = {}
    nextoys['nexuserfunctions'].update(nexfunctions)
    
    return nextoys