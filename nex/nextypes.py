# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

# NOTE all these types are meant for the pynexscripy.py node.
#  The node is a python script evaluator that is meant to toy with these sockets.

# TODO later
#  Optimization:
#  - NexFactory exec is bad for performance? This factory are initialized in the main node class once per execution. Can be frequent.
#    Perhaps we can initiate the factory at node.init()? If we do that, let's first check if it's safe. Maybe, storing pyobjects in there is not supported. 
#    AS a Reminder: we are storing nodetree objects in there, we'll probably need to only store the nodetree name? what about node_inst?
#  Code Redundency:
#  - A lot of operation overloads are very simimar. Some math and comparison operation are repeated across many NexTypes.
#    perhaps could centralize some operations via class inheritence 'NexMath' 'NexCompare' to not repeat function def?
#  - Complex task: Maybe find a smart way to centralized ALL AND ANY type conversion and type error handling? 
#    We do type conversion and checks in dunder overloads, we do conversions in nodesetter function wrapper, and in the nodesetter module as well.
#    Blender type conversion is complex and sometimes do not make sense. It depends on the nodes we are using and the default arguments types as well.
#    Implicit Conversion is wild. Sometimes a color can be evaluated as a float and a float as Color, and sometimes we might want to apply stricter rules in NexScript.


import bpy

bpy_array = bpy.types.bpy_prop_array
import traceback
import math, random
from mathutils import Vector, Matrix, Color, Euler, Quaternion
from functools import partial

from ..__init__ import dprint
from ..utils.fct_utils import alltypes, anytype, ColorRGBA
from ..utils.node_utils import (
    create_new_nodegroup,
    set_socket_defvalue,
    get_socket_by_name,
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
from ..nex.pytonode import py_to_Sockdata, py_to_Mtx16, py_to_Vec3, py_to_RGBA, py_to_Quat4
from ..nex import nodesetter

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
trypy_to_Quat4 = NexErrorWrapper(py_to_Quat4)
trypy_to_RGBA = NexErrorWrapper(py_to_RGBA)

# oooooooooooo                         .                                  
# `888'     `8                       .o8                                  
#  888          .oooo.    .ooooo.  .o888oo  .ooooo.  oooo d8b oooo    ooo 
#  888oooo8    `P  )88b  d88' `"Y8   888   d88' `88b `888""8P  `88.  .8'
#  888    "     .oP"888  888         888   888   888  888       `88..8'
#  888         d8(  888  888   .o8   888 . 888   888  888        `888'
# o888o        `Y888""8o `Y8bod8P'   "888" `Y8bod8P' d888b        .8'
#                                                             .o..P'
#                                                             `Y8P'

def NexFactory(NODEINSTANCE, ALLINPUTS=[], ALLOUTPUTS=[], CALLHISTORY=[],):
    """return a nex type, which is simply an overloaded custom type that automatically arrange links and nodes and
    set default values. The nextypes will/should only build the nodetree and links when neccessary.
    in ALLINPUTS/ALLOUTPUTS we collect all Nex init created when initializing any instances of a Nex type."""

    def AutoNexType(socket):
        """automatically convert a node socket to Nex"""
        match socket:
            case bpy.types.NodeSocketBool():
                return NexBool(fromsocket=socket)

            case bpy.types.NodeSocketInt():
                return NexInt(fromsocket=socket)

            case bpy.types.NodeSocketFloat() | bpy.types.NodeSocketFloatAngle():
                return NexFloat(fromsocket=socket)

            case bpy.types.NodeSocketVector() | bpy.types.NodeSocketVectorXYZ() | bpy.types.NodeSocketVectorTranslation() | bpy.types.NodeSocketVectorEuler():
                return NexVec(fromsocket=socket)

            case bpy.types.NodeSocketMatrix():
                return NexMtx(fromsocket=socket)

            case bpy.types.NodeSocketColor():
                return NexCol(fromsocket=socket)

            case bpy.types.NodeSocketRotation():
                return NexQuat(fromsocket=socket)

            case _: raise TypeError(f"AutoNexType() got Unrecognized '{socket}' of type '{type(socket).__name__}'")

    def create_Nex_constant(NexType, value,):
        """Create a new input node (if not already exist) ensure it's default value, then assign to a NexType & return it."""

        new = NexType(manualdef=True)
        uniquetag = f"C|{new.nxchar}{new.nxid}.const(p{type(value).__name__.lower()[0]})"

        type_name = NexType.__name__
        match type_name:
            case 'NexMtx':
                nodetype = 'FunctionNodeCombineMatrix'
            case _:
                raise Exception(f"create_Nex_constant() Unsupported constant for Nextype '{type_name}'.")

        # create_constant_input fct is smart it will create the node only if it doesn't exist, & ensure (new?) values
        node_tree = NODEINSTANCE.node_tree
        newsock = create_constant_input(node_tree, nodetype, value, uniquetag)

        new.nxsock = newsock
        return new

    def wrap_socketfunctions(sockfunc, typeconvert_args=False):
        """Wrap nodesetter function with interal nodetree & history args, & wrap with NexTypes, so can recieve and output NexTypes automatically.
        This wrapper also: Handle namecollision functions, can auto convert args to Vector or Matrix, handle user errors."""

        def wrappedfunc(*args, **kwargs):
            fname = sockfunc.__name__
            values = tuple(args) + tuple(kwargs.values())

            if (len(args)>=1):

                # some special functions accept that user pass a tuple instead. We need to unpack in order to read what's in the itterable.
                if fname in {'combimatrix','alleq','min','max'}:
                    if (len(args)==1 and (type(args) in {tuple,set,list})):
                        if (type(args[0]) in {tuple,set,list}):
                            args = args[0]
                            values = tuple(args) + tuple(kwargs.values())

                # Name conflict with some native functions? If no NexType foud, we simply call builtin function
                match fname:

                    case 'cos'|'sin'|'tan'|'acos'|'asin'|'atan'|'cosh'|'sinh'|'tanh'|'sqrt'|'log'|'degrees'|'radians'|'floor'|'ceil'|'trunc':
                        if not any(('Nex' in type(v).__name__) for v in values):
                            mathfunction = getattr(math,fname)
                            return mathfunction(*args, **kwargs)

                    case 'min'|'max':
                        if not any(('Nex' in type(v).__name__) for v in values):
                            return min(*args, **kwargs) if (fname=='min') else max(*args, **kwargs)

                    # case 'randint':
                    #     if not any(('Nex' in type(v).__name__) for v in values):
                    #         return random.randint(*args, **kwargs)

            #Process the passed args:

            # -1 sockfunc expect nodesockets, not nextype, we need to convert their args to sockets.. (we did that previously with 'sock_or_py_variables')
            args = [v.nxsock if ('Nex' in type(v).__name__) else v for v in args]

            # -2 automatically convert the passed argument of a function
            if (typeconvert_args):
                args = [trypy_to_Sockdata(v, return_value_only=True) 
                        if type(v) in {tuple, list, set, Vector, Euler, Color, Matrix, bpy_array,}
                        and all((type(i) in {float,int,bool}) for i in v)
                        else v
                        for v in args]

            #define a function with the first two args already defined
            node_tree = NODEINSTANCE.node_tree
            partialsockfunc = partial(sockfunc, node_tree, CALLHISTORY,)

            #Call the socket function with wrapped error handling.
            try:
                r = partialsockfunc(*args, **kwargs)
            except TypeError as e:
                raise

            except nodesetter.UserParamError as e:
                msg = str(e)
                if ('Expected parameters in' in msg):
                    msg = f"TypeError. Function {fname}() Expected parameters in " + str(e).split('Expected parameters in ')[1]
                raise NexError(msg) #Note that Ideally, a previous NexError Should've been raised prior to that.

            except Exception as e:
                print(f"ERROR: wrap_socketfunctions.{fname}() caught error {type(e).__name__}")
                raise

            # Wrap return value as Nex as well
            if ((type(r) is not tuple) and (not issubclass(type(r), bpy.types.NodeSocket))):
                raise Exception(f"Function '{sockfunc}' did not return a NodeSocket. This should never happen.")

            if (type(r) is tuple):
                  rNex = tuple(AutoNexType(s) for s in r)
            else: rNex = AutoNexType(r)

            return rNex

        return wrappedfunc

    # Let's generate the user and internal NexWrapped functions
    NexWrappedFcts = {f.__name__ : wrap_socketfunctions(f, typeconvert_args=False)
                        for f in nodesetter.get_nodesetter_functions(tag='all')}

    NexWrappedUserFcts = {f.__name__ : wrap_socketfunctions(f, typeconvert_args=True)
                        for f in nodesetter.get_nodesetter_functions(tag='nexscript')}

    # ooooo      ooo                            oooooooooo.                               
    # `888b.     `8'                            `888'   `Y8b                              
    #  8 `88b.    8   .ooooo.  oooo    ooo       888     888  .oooo.    .oooo.o  .ooooo.  
    #  8   `88b.  8  d88' `88b  `88b..8P'        888oooo888' `P  )88b  d88(  "8 d88' `88b 
    #  8     `88b.8  888ooo888    Y888'          888    `88b  .oP"888  `"Y88b.  888ooo888 
    #  8       `888  888    .o  .o8"'88b         888    .88P d8(  888  o.  )88b 888    .o 
    # o8o        `8  `Y8bod8P' o88'   888o      o888bood8P'  `Y888""8o 8""888P' `Y8bod8P' 

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

        #Do not allow user to create any custom attribute on a NexType
        _attributes = ('init_counter','node_inst','node_tree','nxstype','nxtydsp','nxchar','nxsock','nxsnam','nxid',)

        #Strict attribute setter & Error wrapping
        def __setattr__(self, name, value):
            if (name not in self._attributes):
                raise NexError(f"AttributeError. '{self.nxtydsp}' do not have any '{name}' attribute.")
            return super().__setattr__(name, value)

        def __getattribute__(self, name):
            try:
                return super().__getattribute__(name)
            except AttributeError:
                raise NexError(f"AttributeError.'{self.nxtydsp}' do not have any '{name}' attribute.")
            except Exception:
                raise

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
        
        # MatMult
        def __matmul__(self, other): # self @ other
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '@'.")
        def __rmatmul__(self, other): # other @ self
            raise NexError(f"TypeError.  '{self.nxtydsp}' do not support operand '@'.")
        
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

        # Nex Itter
        def __len__(self): #len(itter)
            raise NexError(f"TypeError. '{self.nxtydsp}' has no len() method.")
        def __getitem__(self, key): #suport x = vec[0], x,y,z = vec ect..
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")
        def __iter__(self): #for f in itter
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")
        def __setitem__(self, key, value): #x[0] += a+b
            raise NexError(f"TypeError. '{self.nxtydsp}' is not an itterable.")

        # Nex python bool evaluation? Impossible.
        def __bool__(self):
            raise NexError(f"EvaluationError. Cannot evaluate '{self.nxtydsp}' as a python boolean.")

        # print the Nex
        def __repr__(self):
            return f"<{type(self).__name__}{self.nxid} for {type(self.nxsock).__name__ if self.nxsock else 'NoneSocket'}>"
            return f"<{type(self)}{self.nxid} nxsock=`{self.nxsock}` isoutput={self.nxsock.is_output}' socketnode='{self.nxsock.node.name}''{self.nxsock.node.label}'>"

    # ooooo      ooo                              .oooooo.                                                             .o8  
    # `888b.     `8'                             d8P'  `Y8b                                                           "888  
    #  8 `88b.    8   .ooooo.  oooo    ooo      888      888 oo.ooooo.   .ooooo.  oooo d8b  .oooo.   ooo. .oo.    .oooo888  
    #  8   `88b.  8  d88' `88b  `88b..8P'       888      888  888' `88b d88' `88b `888""8P `P  )88b  `888P"Y88b  d88' `888  
    #  8     `88b.8  888ooo888    Y888'         888      888  888   888 888ooo888  888      .oP"888   888   888  888   888  
    #  8       `888  888    .o  .o8"'88b        `88b    d88'  888   888 888    .o  888     d8(  888   888   888  888   888  
    # o8o        `8  `Y8bod8P' o88'   888o       `Y8bood8P'   888bod8P' `Y8bod8P' d888b    `Y888""8o o888o o888o `Y8bod88P" 
    #                                                         888                                                           
    #                                                        o888o

    class NexMath:
        """Basic math operand for math between NexFloat NexBool NexInt NexVector NexColor & python float int bool Vector list set tuple Vector Color of correct Length.
        Nodesetter functions will be in charge of deciding which nodes to use"""

        def __add__(self, other): # self + other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case 'NexCol': args = self, trypy_to_RGBA(other)
                        case _:        args = self, float(other)

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = self, trypy_to_Vec3(other)
                        case 4: args = self, trypy_to_RGBA(other)
                        case _: raise NexError(f"TypeError. Cannot add type '{self.nxtydsp}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color': 
                    args = self, trypy_to_RGBA(other)

                case _: raise NexError(f"TypeError. Cannot add type '{self.nxtydsp}' to '{type(other).__name__}'.")

            return NexWrappedFcts['add'](*args,)

        def __radd__(self, other): # other + self
            # commutative operation.
            return self.__add__(other)

        def __sub__(self, other): # self - other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case 'NexCol': args = self, trypy_to_RGBA(other)
                        case _:        args = self, float(other)

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = self, trypy_to_Vec3(other)
                        case 4: args = self, trypy_to_RGBA(other)
                        case _: raise NexError(f"TypeError. Cannot subtract type '{self.nxtydsp}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color': 
                    args = self, trypy_to_RGBA(other)

                case _: raise NexError(f"TypeError. Cannot subtract type '{self.nxtydsp}' with '{type(other).__name__}'.")

            return NexWrappedFcts['sub'](*args,)

        def __rsub__(self, other): # other - self
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = other, self

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = trypy_to_Vec3(other), self
                        case 'NexCol': args = trypy_to_RGBA(other), self
                        case _:        args = float(other), self

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = trypy_to_Vec3(other), self
                        case 4: args = trypy_to_RGBA(other), self
                        case _: raise NexError(f"TypeError. Cannot subtract type '{type(other).__name__}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color': 
                    args = trypy_to_RGBA(other), self

                case _: raise NexError(f"TypeError. Cannot subtract '{type(other).__name__}' with '{self.nxtydsp}'.")

            return NexWrappedFcts['sub'](*args,)

        def __mul__(self, other): # self * other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case 'NexCol': args = self, trypy_to_RGBA(other)
                        case _:        args = self, float(other)

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = self, trypy_to_Vec3(other)
                        case 4: args = self, trypy_to_RGBA(other)
                        case _: raise NexError(f"TypeError. Cannot multiply type '{self.nxtydsp}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color': 
                    args = self, trypy_to_RGBA(other)

                case _: raise NexError(f"TypeError. Cannot multiply type '{self.nxtydsp}' with '{type(other).__name__}'.")

            return NexWrappedFcts['mult'](*args,)

        def __rmul__(self, other): # other * self
            # commutative operation.
            return self.__mul__(other)

        def __truediv__(self, other): # self / other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case 'NexCol': args = self, trypy_to_RGBA(other)
                        case _:        args = self, float(other)

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = self, trypy_to_Vec3(other)
                        case 4: args = self, trypy_to_RGBA(other)
                        case _: raise NexError(f"TypeError. Cannot divide type '{self.nxtydsp}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color':
                    args = self, trypy_to_RGBA(other)

                case _: raise NexError(f"TypeError. Cannot divide type '{self.nxtydsp}' by '{type(other).__name__}'.")

            return NexWrappedFcts['div'](*args,)

        def __rtruediv__(self, other): # other / self
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = other, self

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = trypy_to_Vec3(other), self
                        case 'NexCol': args = trypy_to_RGBA(other), self
                        case _:        args = float(other), self

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = trypy_to_Vec3(other), self
                        case 4: args = trypy_to_RGBA(other), self
                        case _: raise NexError(f"TypeError. Cannot divide type '{type(other).__name__}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'Color': 
                    args = trypy_to_RGBA(other), self

                case _: raise NexError(f"TypeError. Cannot divide '{type(other).__name__}' by '{self.nxtydsp}'.")

            return NexWrappedFcts['div'](*args,)

        def __pow__(self, other): #self ** other
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot raise a Color.")

            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = self, trypy_to_Vec3(other)

                case 'int' | 'float' | 'bool':
                    args = self, float(other)
                
                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot raise a Color.")

                case _: raise NexError(f"TypeError. Cannot raise type '{self.nxtydsp}' to the power of '{type(other).__name__}'.")

            return NexWrappedFcts['pow'](*args,)

        def __rpow__(self, other): #other ** self
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot raise a Color.")

            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = trypy_to_Vec3(other), self

                case 'int' | 'float' | 'bool':
                    args = float(other), self

                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot raise a Color.")

                case _: raise NexError(f"TypeError. Cannot raise '{type(other).__name__}' to the power of '{self.nxtydsp}'.")

            return NexWrappedFcts['pow'](*args,)

        def __mod__(self, other): # self % other
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot compute modulo of a Color.")

            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = self, trypy_to_Vec3(other)

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case _:        args = self, float(other)

                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot compute modulo of a Color.")

                case _: raise NexError(f"TypeError. Cannot compute type '{self.nxtydsp}' modulo '{type(other).__name__}'.")

            return NexWrappedFcts['mod'](*args,)

        def __rmod__(self, other): # other % self
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot compute modulo of a Color.")
                
            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = trypy_to_Vec3(other), self

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = trypy_to_Vec3(other), self
                        case _:        args = float(other), self

                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot compute modulo of a Color.")

                case _: raise NexError(f"TypeError. Cannot compute modulo of '{type(other).__name__}' by '{self.nxtydsp}'.")

            return NexWrappedFcts['mod'](*args,)

        def __floordiv__(self, other): # self // other
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot compute floordiv of a Color.")

            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = self, other

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = self, trypy_to_Vec3(other)

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = self, trypy_to_Vec3(other)
                        case _:        args = self, float(other)

                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot compute floordiv of a Color.")

                case _: raise NexError(f"TypeError. Cannot perform floordiv on type '{self.nxtydsp}' with '{type(other).__name__}'.")

            return NexWrappedFcts['floordiv'](*args,)
    
        def __rfloordiv__(self, other): # other // self
            self_type = type(self).__name__
            type_name = type(other).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot compute floordiv of a Color.")

            match type_name:
                case 'NexVec' | 'NexFloat' | 'NexInt' | 'NexBool':
                    args = other, self

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    args = trypy_to_Vec3(other), self

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexVec': args = trypy_to_Vec3(other), self
                        case _:        args = float(other), self

                case 'NexCol' | 'Color':
                    raise NexError(f"TypeError. Cannot compute floordiv of a Color.")

                case _: raise NexError(f"TypeError. Cannot perform floor division of '{type(other).__name__}' by '{self.nxtydsp}'.")

            return NexWrappedFcts['floordiv'](*args,)

        def __neg__(self): # -self
            self_type = type(self).__name__

            if (self_type=='NexCol'):
                raise NexError(f"TypeError. Cannot negate a Color.")

            return NexWrappedFcts['neg'](self,)

        def __abs__(self): # abs(self)
            return NexWrappedFcts['abs'](self,)
        
        def __round__(self): # round(self)
            return NexWrappedFcts['round'](self,)

    class NexCompare:
        """Basic comparison operand between all possible types.
        Nodesetter functions will be in charge of deciding which nodes to use"""

        def _generalcompare(self, other, op):
            """internal compare function"""
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'Vector' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    match len(other):
                        case 3: args = self, trypy_to_Vec3(other)
                        case 4: args = self, trypy_to_RGBA(other)
                        case _: raise NexError(f"TypeError. Cannot compare type '{self.nxtydsp}' with '{type(other).__name__}' of length {len(other)}. Use length 3 or 4 for SocketVector or SocketColor conversion.")

                case 'int' | 'float' | 'bool':
                    match self_type:
                        case 'NexBool': args = self, bool(other)
                        case 'NexVec':  args = self, trypy_to_Vec3(other)
                        case 'NexCol':  args = self, trypy_to_RGBA(other)
                        case _:         args = self, float(other)

                case 'Color': 
                    args = self, trypy_to_RGBA(other)

                case _: raise NexError(f"TypeError. Cannot compare '{self.nxtydsp}' with '{type(other).__name__}'.")

            return NexWrappedFcts[op](*args,)

        def __eq__(self, other): # self == other
            return  self._generalcompare(other, 'iseq')

        def __ne__(self, other): # self != other
            return  self._generalcompare(other, 'isuneq')

        def __lt__(self, other): # self < other
            return  self._generalcompare(other, 'isless')

        def __le__(self, other): # self <= other
            return  self._generalcompare(other, 'islesseq')

        def __gt__(self, other): # self > other
            return  self._generalcompare(other, 'isgreater')

        def __ge__(self, other): # self >= other
            return  self._generalcompare(other, 'isgreatereq')

    class NexBitwise:

        def __and__(self, other): # self & other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'bool':
                    args = self, other
                case 'float' | 'int':
                    args = self, bool(other)

                case 'Vector' | 'Color' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    if not alltypes(*other, types=(float,int,bool)):
                        raise NexError(f"TypeError. Cannot perform '&' bitwise operation on a '{type(other).__name__}' that do not contain types bool, int, float. {other}.")
                    args = self, any(bool(v) for v in other)

                case _: raise NexError(f"TypeError. Cannot perform '&' bitwise operation between '{self.nxtydsp}' and '{type(other).__name__}'.")

            return NexWrappedFcts['booland'](*args,)

        def __rand__(self, other): # other & self
            # commutative operation.
            return self.__and__(other)

        def __or__(self, other): # self | other
            self_type = type(self).__name__
            type_name = type(other).__name__

            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    args = self, other

                case 'bool':
                    args = self, other
                case 'float' | 'int':
                    args = self, bool(other)

                case 'Vector' | 'Color' | 'list' | 'set' | 'tuple' | 'bpy_prop_array':
                    if not alltypes(*other, types=(float,int,bool)):
                        raise NexError(f"TypeError. Cannot perform '|' bitwise operation on a '{type(other).__name__}' that do not contain types bool, int, float. {other}.")
                    args = self, any(bool(v) for v in other)

                case _: raise NexError(f"TypeError. Cannot perform '|' bitwise operation between '{self.nxtydsp}' and '{type(other).__name__}'.")

            return NexWrappedFcts['boolor'](*args,)

        def __ror__(self, other): # other | self
            # commutative operation.
            return self.__or__(other)

    # ooooo      ooo                       oooooooooooo oooo                          .   
    # `888b.     `8'                       `888'     `8 `888                        .o8   
    #  8 `88b.    8   .ooooo.  oooo    ooo  888          888   .ooooo.   .oooo.   .o888oo 
    #  8   `88b.  8  d88' `88b  `88b..8P'   888oooo8     888  d88' `88b `P  )88b    888   
    #  8     `88b.8  888ooo888    Y888'     888    "     888  888   888  .oP"888    888   
    #  8       `888  888    .o  .o8"'88b    888          888  888   888 d8(  888    888 . 
    # o8o        `8  `Y8bod8P' o88'   888o o888o        o888o `Y8bod8P' `Y888""8o   "888" 
                                                                                        
    class NexFloat(NexMath, NexCompare, NexBitwise, Nex):

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
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to SocketFloat '{socket_name}'. Was expecting 'None' | 'int' | 'float' | 'bool'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexFloat Functions & Properties
        # ...

    # ooooo      ooo                       oooooooooo.                      oooo  
    # `888b.     `8'                       `888'   `Y8b                     `888  
    #  8 `88b.    8   .ooooo.  oooo    ooo  888     888  .ooooo.   .ooooo.   888  
    #  8   `88b.  8  d88' `88b  `88b..8P'   888oooo888' d88' `88b d88' `88b  888  
    #  8     `88b.8  888ooo888    Y888'     888    `88b 888   888 888   888  888  
    #  8       `888  888    .o  .o8"'88b    888    .88P 888   888 888   888  888  
    # o8o        `8  `Y8bod8P' o88'   888o o888bood8P'  `Y8bod8P' `Y8bod8P' o888o 

    class NexBool(NexMath, NexCompare, NexBitwise, Nex):

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

                case 'NoneType' | 'bool':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to SocketBool '{socket_name}'. Was expecting 'None' | 'bool'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

    # ooooo      ooo                       ooooo                 .   
    # `888b.     `8'                       `888'               .o8   
    #  8 `88b.    8   .ooooo.  oooo    ooo  888  ooo. .oo.   .o888oo 
    #  8   `88b.  8  d88' `88b  `88b..8P'   888  `888P"Y88b    888   
    #  8     `88b.8  888ooo888    Y888'     888   888   888    888   
    #  8       `888  888    .o  .o8"'88b    888   888   888    888 . 
    # o8o        `8  `Y8bod8P' o88'   888o o888o o888o o888o   "888" 
                                            
    #TODO this one could have optimized node. Nodesetter functions could check like we are already doing with NexVec & containsVecs()

    class NexInt(NexMath, NexCompare, NexBitwise, Nex):

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree

        nxstype = 'NodeSocketInt'
        nxtydsp = 'SocketInt'
        nxchar = 'i'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexInt.init_counter
            NexInt.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None

            type_name = type(value).__name__
            match type_name: 

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                case 'NoneType' | 'int' | 'float':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=int(value), in_out='INPUT',)

                # wrong initialization?
                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to SocketInt '{socket_name}'. Was expecting 'int' | 'Float'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

    # ooooo      ooo                       oooooo     oooo                     
    # `888b.     `8'                        `888.     .8'                      
    #  8 `88b.    8   .ooooo.  oooo    ooo   `888.   .8'    .ooooo.   .ooooo.  
    #  8   `88b.  8  d88' `88b  `88b..8P'     `888. .8'    d88' `88b d88' `"Y8 
    #  8     `88b.8  888ooo888    Y888'        `888.8'     888ooo888 888       
    #  8       `888  888    .o  .o8"'88b        `888'      888    .o 888   .o8 
    # o8o        `8  `Y8bod8P' o88'   888o       `8'       `Y8bod8P' `Y8bod8P' 

    class NexVec(NexMath, NexCompare, NexBitwise, Nex):

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
                
                case 'NoneType' | 'bpy_prop_array' | 'Vector' | 'list' | 'set' | 'tuple' | 'int' | 'float' | 'bool':
                    
                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
        # NexVec MatMult Operations

        def __matmul__(self, other): # self @ other
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx' | 'Matrix' | 'list' | 'tuple' | 'set':
                    raise NexError(f"TypeError. Cannot matrix-multiply 'Vector' with 'Matrix'. Only 'Matrix @ Vector' is allowed.")
                case 'NexVec' | 'Vector':
                    raise NexError(f"TypeError. Cannot matrix-multiply two TypeVector together. Only 'Matrix @ Vector' is allowed.")
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot matrix-multiply 'SocketVector' with '{other.nxtydsp}'. Only 'Matrix @ Vector' is allowed.")
                case _:
                    raise NexError(f"TypeError. Cannot matrix-multiply 'SocketVector' with '{type(other).__name__}'. Only 'Matrix @ Vector' is allowed.")

        def __rmatmul__(self, other): # other @ self
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx':
                    return NotImplemented
                case 'NexVec' | 'Vector':
                    raise NexError(f"TypeError. Cannot matrix-multiply 'Vector' with 'Vector'. Only 'Matrix @ Vector' is allowed.")
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot matrix-multiply '{other.nxtydsp}' with 'SocketVector'.")
                case 'Matrix' | 'list' | 'set' | 'tuple':
                    convother = trypy_to_Mtx16(other)
                    othernex = create_Nex_constant(NexMtx, convother,)
                    args = othernex, self
                case _:
                    raise NexError(f"TypeError. Cannot matrix-multiply '{type(other).__name__}' with 'SocketVector'.")
            return NexWrappedFcts['transformloc'](*args,)

        # ---------------------
        # NexVec Itter

        def __len__(self): #len(itter)
            return 3

        def __getitem__(self, key): #suport x = vec[0], x,y,z = vec ect..
            match key:
                case int(): #vec[i]
                    sep_xyz = NexWrappedFcts['sepaxyz'](self,)
                    if key not in (0,1,2):
                        raise NexError("IndexError. indice in SocketVector[i] exceeded maximal range of 2.")
                    return sep_xyz[key]
                
                case slice(): #vec[:i]
                    sep_xyz = NexWrappedFcts['sepaxyz'](self,)
                    indices = range(*key.indices(3))
                    return tuple(sep_xyz[i] for i in indices)
                
                case _: raise NexError("TypeError. indices in SocketVector[i] must be integers or slices.")

        def __iter__(self): #for f in itter
            for i in range(len(self)):
                yield self[i]

        def __setitem__(self, key, value): #x[0] += a+b
            to_frame = []
            type_name = type(value).__name__

            match key:
                case int(): #vec[i] =
                    if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                        raise NexError(f"TypeError. Value assigned to SocketVector[i] must float compatible. Recieved '{type_name}'.")
                    x, y, z = NexWrappedFcts['sepaxyz'](self,)
                    to_frame.append(x.nxsock.node)
                    match key:
                        case 0: new_xyz = value, y, z
                        case 1: new_xyz = x, value, z
                        case 2: new_xyz = x, y, value
                        case _: raise NexError("IndexError. indice in SocketVector[i] exceeded maximal range of 2.")

                case slice(): #vec[:] =
                    if (key!=slice(None,None,None)):
                        raise NexError("Only [:] slicing is supported for SocketVector.")
                    new_xyz = value
                    if (len(new_xyz)!=3):
                        raise NexError("Slice assignment requires exactly 3 values in XYZ for SocketVector.")

                case _: raise NexError("TypeError. indices in SocketVector[i] must be integers or slices.")

            new = NexWrappedFcts['combixyz'](*new_xyz,)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            to_frame.append(new.nxsock.node)

            frame_nodes(self.node_tree, *to_frame, label=f"Vec.setitem[{key if (type(key) is int) else ':'}]",)

            return None

        # ---------------------
        # NexVec Functions & Properties
        # We try to immitate mathutils https://docs.blender.org/api/current/mathutils.html

        _attributes = Nex._attributes + ('x','y','z','xyz','length',)

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
            if not (type(value) in {tuple,Vector} and len(value)==3):
                raise NexError("TypeError. Assignment to SocketVector.xyz is expected to be a tuple of length 3 containing sockets or Python values.")
            self[:] = value

        @property
        def length(self):
            return NexWrappedFcts['length'](self,)
        @length.setter
        def length(self, value):
            #TODO looks like mathutils.length support setter. need to find formula and apply it
            raise NexError("AssignationError. 'SocketVector.length' is read-only.")

        def normalized(self):
            return NexWrappedFcts['normalize'](self,)

        def to_color(self):
            return NexWrappedFcts['vectocolor'](self,)

        def to_quaternion(self):
            return NexWrappedFcts['vectorot'](self,)


    # ooooo      ooo                         .oooooo.             oooo                     
    # `888b.     `8'                        d8P'  `Y8b            `888                     
    #  8 `88b.    8   .ooooo.  oooo    ooo 888           .ooooo.   888   .ooooo.  oooo d8b 
    #  8   `88b.  8  d88' `88b  `88b..8P'  888          d88' `88b  888  d88' `88b `888""8P 
    #  8     `88b.8  888ooo888    Y888'    888          888   888  888  888   888  888     
    #  8       `888  888    .o  .o8"'88b   `88b    ooo  888   888  888  888   888  888     
    # o8o        `8  `Y8bod8P' o88'   888o  `Y8bood8P'  `Y8bod8P' o888o `Y8bod8P' d888b    
                                                                     
    class NexCol(NexMath, NexCompare, NexBitwise, Nex):

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree

        nxstype = 'NodeSocketColor'
        nxtydsp = 'SocketColor'
        nxchar = 'c'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexCol.init_counter
            NexCol.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None
                        
            type_name = type(value).__name__
            match type_name:

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                case 'NoneType' | 'bpy_prop_array' | 'Color' | 'list' | 'set' | 'tuple':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
                        fval = trypy_to_RGBA(value)
                        set_socket_defvalue(self.node_tree, socket=outsock, node=self.node_inst, value=fval, in_out='INPUT',)

                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketColor'. Was expecting 'None' | 'Color[3]' | 'list[4]' | 'set[4]' | 'tuple[4]'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexCol Itter

        def __len__(self): #len(itter)
            return 4

        def __getitem__(self, key): #suport c = col[0], r,g,b,a = col ect..
            match key:
                case int(): #col[i]
                    sep_col = NexWrappedFcts['sepacolor'](self, mode='RGB')
                    if (key not in {0,1,2,3}):
                        raise NexError("IndexError. indice in SocketColor[i] exceeded maximal range of 3.")
                    return sep_col[key]

                case slice(): #col[:i]
                    sep_col = NexWrappedFcts['sepacolor'](self, mode='RGB')
                    indices = range(*key.indices(4))
                    return tuple(sep_col[i] for i in indices)

                case _: raise NexError("TypeError. indices in SocketColor[i] must be integers or slices.")

        def __iter__(self): #for f in itter
            for i in range(len(self)):
                yield self[i]

        def __setitem__(self, key, value): #x[0] += a+b
            to_frame = []
            type_name = type(value).__name__

            match key:
                case int(): #col[i] =
                    if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                        raise NexError(f"TypeError. Value assigned to SocketColor[i] must float compatible. Recieved '{type_name}'.")
                    r, g, b, a = NexWrappedFcts['sepacolor'](self, mode='RGB')
                    to_frame.append(a.nxsock.node)
                    match key:
                        case 0: new_col = value, g, b, a
                        case 1: new_col = r, value, b, a
                        case 2: new_col = r, g, value, a
                        case 3: new_col = r, g, b, value
                        case _: raise NexError("IndexError. indice in SocketColor[i] exceeded maximal range of 3.")

                case slice(): #col[:] =
                    if (key!=slice(None,None,None)):
                        raise NexError("Only [:] slicing is supported for SocketColor.")
                    new_col = value
                    if (len(new_col)!=4):
                        raise NexError("Slice assignment requires exactly 4 values in RGBA for SocketColor.")

                case _: raise NexError("TypeError. indices in SocketColor[i] must be integers or slices.")

            new = NexWrappedFcts['combicolor'](*new_col, mode='RGB')
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            to_frame.append(new.nxsock.node)

            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem[{key if (type(key) is int) else ':'}]",)

            return None

        # ---------------------
        # NexCol Functions & Properties
        # We try to immitate mathutils https://docs.blender.org/api/current/mathutils.html

        _attributes = Nex._attributes + ('r','g','b','rgb','h','s','v','hsv','l','hsl','a','lightness','blackbody')

        @property
        def r(self):
            return self[0]
        @r.setter
        def r(self, value):
            self[0] = value

        @property
        def g(self):
            return self[1]
        @g.setter
        def g(self, value):
            self[1] = value

        @property
        def b(self):
            return self[2]
        @b.setter
        def b(self, value):
            self[2] = value

        @property
        def rgb(self):
            return self[:][:3]
        @rgb.setter
        def rgb(self, value):
            if not (type(value) in {tuple,Color,Vector,NexVec} and len(value)==3):
                raise NexError("TypeError. Assignment to SocketColor.rgb is expected to be a tuple of length 3 containing sockets or Python values.")
            to_frame = []

            _, _, _, a = NexWrappedFcts['sepacolor'](self, mode='RGB')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](value[0], value[1], value[2], a, mode='RGB')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.rgb",)

        @property
        def h(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSV')[0]
        @h.setter
        def h(self, value):
            to_frame = []
            type_name = type(value).__name__
            if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                raise NexError(f"TypeError. Value assigned to SocketColor.h must float compatible. Recieved '{type_name}'.")

            _, s, v, a = NexWrappedFcts['sepacolor'](self, mode='HSV')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](value, s, v, a, mode='HSV')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.h",)

        @property
        def s(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSV')[1]
        @s.setter
        def s(self, value):
            to_frame = []
            type_name = type(value).__name__
            if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                raise NexError(f"TypeError. Value assigned to SocketColor.s must float compatible. Recieved '{type_name}'.")

            h, _, v, a = NexWrappedFcts['sepacolor'](self, mode='HSV')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](h, value, v, a, mode='HSV')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.s",)

        @property
        def v(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSV')[2]
        @v.setter
        def v(self, value):
            to_frame = []
            type_name = type(value).__name__
            if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                raise NexError(f"TypeError. Value assigned to SocketColor.v must float compatible. Recieved '{type_name}'.")

            h, s, _, a = NexWrappedFcts['sepacolor'](self, mode='HSV')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](h, s, value, a, mode='HSV')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.v",)

        @property
        def hsv(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSV')[:3]
        @hsv.setter
        def hsv(self, value):
            if not (type(value) in {tuple,Color,Vector,NexVec} and len(value)==3):
                raise NexError("TypeError. Assignment to SocketColor.hsv is expected to be a tuple of length 3 containing sockets or Python values.")
            to_frame = []

            _, _, _, a = NexWrappedFcts['sepacolor'](self, mode='HSV')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](value[0], value[1], value[2], a, mode='HSV')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.hsv",)

        @property
        def a(self):
            return self[3]
        @a.setter
        def a(self, value):
            self[3] = value

        @property
        def l(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSL')[2]
        @l.setter
        def l(self, value):
            to_frame = []
            type_name = type(value).__name__
            if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                raise NexError(f"TypeError. Value assigned to SocketColor.l must float compatible. Recieved '{type_name}'.")

            h, s, _, a = NexWrappedFcts['sepacolor'](self, mode='HSL')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](h, s, value, a, mode='HSL')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.l",)

        @property
        def hsl(self):
            return NexWrappedFcts['sepacolor'](self, mode='HSL')[:3]
        @hsl.setter
        def hsl(self, value):
            if not (type(value) in {tuple,Color,Vector,NexVec} and len(value)==3):
                raise NexError("TypeError. Assignment to SocketColor.hsl is expected to be a tuple of length 3 containing sockets or Python values.")
            to_frame = []

            _, _, _, a = NexWrappedFcts['sepacolor'](self, mode='HSL')
            to_frame.append(a.nxsock.node)

            new = NexWrappedFcts['combicolor'](value[0], value[1], value[2], a, mode='HSL')
            self.nxsock = new.nxsock
            self.nxid = new.nxid

            to_frame.append(new.nxsock.node)
            frame_nodes(self.node_tree, *to_frame, label=f"Col.setitem.hsl",)

        # TODO .c .m .y .k .cmyk would be really nice!
        
        # TODO need to get and set blackbody! find formula!
        # complete nodesetter.get_blackbody
        # @property
        # def blackbody(self):
        #     pass
        # @blackbody.setter
        # def blackbody(self, value):
        #     pass

        def to_vector(self):
            return NexWrappedFcts['colortovec'](self,)

        # def to_quaternion(self):
        #     return NexWrappedFcts['colortorotation'](self,)


    # ooooo      ooo                       ooooooooo.                 .   
    # `888b.     `8'                       `888   `Y88.             .o8   
    #  8 `88b.    8   .ooooo.  oooo    ooo  888   .d88'  .ooooo.  .o888oo 
    #  8   `88b.  8  d88' `88b  `88b..8P'   888ooo88P'  d88' `88b   888   
    #  8     `88b.8  888ooo888    Y888'     888`88b.    888   888   888   
    #  8       `888  888    .o  .o8"'88b    888  `88b.  888   888   888 . 
    # o8o        `8  `Y8bod8P' o88'   888o o888o  o888o `Y8bod8P'   "888" 

    class NexQuat(Nex):

        init_counter = 0
        node_inst = NODEINSTANCE
        node_tree = node_inst.node_tree

        nxstype = 'NodeSocketRotation'
        nxtydsp = 'SocketRotation'
        nxchar = 'r'

        def __init__(self, socket_name='', value=None, fromsocket=None, manualdef=False,):

            self.nxid = NexQuat.init_counter
            NexQuat.init_counter += 1

            if (manualdef):
                return None
            if (fromsocket is not None):
                self.nxsock = fromsocket
                return None

            type_name = type(value).__name__
            match type_name:

                case _ if ('Nex' in type_name):
                    raise NexError(f"Invalid Input Initialization. Cannot initialize a 'SocketInput' with another Socket.")

                case 'NoneType': #| 'Quaternion' | 'Vector' | 'Euler' | 'list' | 'set' | 'tuple':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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

                case _:
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketRotation'. Was expecting 'None'.")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexQuat Itter

        def __len__(self): #len(itter)
            return 4

        def __getitem__(self, key):
            match key:
                case int(): #q[i]
                    sep_quat = NexWrappedFcts['sepaquat'](self)
                    if (key not in {0,1,2,3}):
                        raise NexError("IndexError. indice in SocketRotation[i] exceeded maximal range of 3.")
                    return sep_quat[key]

                case slice(): #q[:i]
                    sep_quat = NexWrappedFcts['sepaquat'](self)
                    indices = range(*key.indices(4))
                    return tuple(sep_quat[i] for i in indices)

                case _: raise NexError("TypeError. indices in SocketRotation[i] must be integers or slices.")

        def __iter__(self): #for f in itter
            for i in range(len(self)):
                yield self[i]

        def __setitem__(self, key, value): #x[0] += a+b
            to_frame = []
            type_name = type(value).__name__

            match key:
                case int(): #q[i] =
                    if (type_name not in {'NexFloat', 'NexInt', 'NexBool', 'int', 'float'}):
                        raise NexError(f"TypeError. Value assigned to SocketRotation[i] must float compatible. Recieved '{type_name}'.")
                    w, x, y, z = NexWrappedFcts['sepaquat'](self)
                    to_frame.append(x.nxsock.node)
                    match key:
                        case 0: new_quat = value, x, y, z
                        case 1: new_quat = w, value, y, z
                        case 2: new_quat = w, x, value, z
                        case 3: new_quat = w, x, y, value
                        case _: raise NexError("IndexError. indice in SocketRotation[i] exceeded maximal range of 3.")

                case slice(): #q[:] =
                    if (key!=slice(None,None,None)):
                        raise NexError("Only [:] slicing is supported for SocketRotation.")
                    new_quat = value
                    if (len(new_quat)!=4):
                        raise NexError("Slice assignment requires exactly 4 values in WXYZ for SocketRotation.")

                case _: raise NexError("TypeError. indices in SocketRotation[i] must be integers or slices.")

            new = NexWrappedFcts['combiquat'](*new_quat)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            to_frame.append(new.nxsock.node)

            frame_nodes(self.node_tree, *to_frame, label=f"Quat.setitem[{key if (type(key) is int) else ':'}]",)

            return None

        # ---------------------
        # NexQuat Functions & Properties
        # We try to immitate mathutils https://docs.blender.org/api/current/mathutils.html

        _attributes = Nex._attributes + ('x','y','z','w','wxyz','axis','angle')

        @property
        def w(self):
            return self[0]
        @w.setter
        def w(self, value):
            self[0] = value

        @property
        def x(self):
            return self[1]
        @x.setter
        def x(self, value):
            self[1] = value

        @property
        def y(self):
            return self[2]
        @y.setter
        def y(self, value):
            self[2] = value

        @property
        def z(self):
            return self[3]
        @z.setter
        def z(self, value):
            self[3] = value

        @property
        def wxyz(self):
            return self[:]
        @wxyz.setter
        def wxyz(self, value):
            if not (type(value) in {tuple,Quaternion} and len(value)==4):
                raise NexError("TypeError. Assignment to SockerRotation.wxyz is expected to be a tuple of length 4 containing sockets or Python values.")
            self[:] = value[:]

        @property
        def axis(self):
            return NexWrappedFcts['separot'](self,)[0]
        @axis.setter
        def axis(self, value):
            axis, angle = NexWrappedFcts['separot'](self,)
            type_name = type(value).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexCol':
                    pass
                case 'Vector' | 'int' | 'float' | 'bool':
                    value = trypy_to_Vec3(value)
                case 'list' | 'set' | 'tuple':
                    #correct lenght?
                    if len(value)!=3:
                        raise NexError(f"AssignationError. 'SocketRotation.axis' Expected an itterable of len3. Recieved len{len(value)}.")
                    #user is giving us a mix of Sockets and python types?..
                    iscombi = any(('Nex' in type(v).__name__) for v in value)
                    #not valid itterable
                    if (not iscombi) and not alltypes(*value, types=(float,int,bool),):
                        raise NexError(f"AssignationError. 'SocketRotation.axis' Expected an itterable containing types 'Socket','int','float','bool'.")
                    value = NexWrappedFcts['combixyz'](*value,) if (iscombi) else trypy_to_Vec3(value)
                case _:
                    raise NexError(f"AssignationError. 'SocketRotation.axis' Expected Vector-compatible values. Recieved '{type_name}'.")

            new = NexWrappedFcts['combirot'](value,angle)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            frame_nodes(self.node_tree, axis.nxsock.node, new.nxsock.node, label="Rotation.axis =..",)
            return None

        @property
        def angle(self):
            return NexWrappedFcts['separot'](self,)[1]
        @angle.setter
        def angle(self, value):
            axis, angle = NexWrappedFcts['separot'](self,)
            type_name = type(value).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool':
                    pass
                case 'int' | 'float' | 'bool':
                    value = float(value)
                case _:
                    raise NexError(f"AssignationError. 'SocketRotation.angle' Expected Float-compatible values. Recieved '{type_name}'.")

            new = NexWrappedFcts['combirot'](axis,value)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            frame_nodes(self.node_tree, axis.nxsock.node, new.nxsock.node, label="Rotation.angle =..",)
            return None

        def inverted(self):
            return NexWrappedFcts['rotinvert'](self,)

        def to_euler(self):
            return NexWrappedFcts['rottoeuler'](self,)

        # def to_color(self):
        #     return NexWrappedFcts['rotationtocolor'](self,)

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

                case 'NoneType': # | 'Matrix' | 'list' | 'set' | 'tuple':

                    #ensure name chosen is correct
                    assert socket_name!='', "Nex Initialization should always define a socket_name."
                    if (socket_name in ALLINPUTS):
                        raise NexError(f"SocketNameError. Multiple sockets with the name '{socket_name}' found. Ensure names are unique.")
                    ALLINPUTS.append(socket_name)

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='INPUT', socket_name=socket_name,)
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
                    raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to var '{socket_name}' of type 'SocketMatrix'. Was expecting 'None'.")# | 'Matrix[16]' | 'list[16]' | 'set[16]' | 'tuple[16]'")

            dprint(f'DEBUG: {type(self).__name__}.__init__({value}). Instance:{self}')
            return None

        # ---------------------
        # NexMtx MatMult Operations

        def __matmul__(self, other): # self @ other
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx':
                    fname = 'matrixmult'
                    args = self, other
                case 'NexVec':
                    fname = 'transformloc'
                    args = other, self
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot matrix-multiply 'SocketMatrix' with '{other.nxtydsp}'.")
                case 'Vector':
                    fname = 'transformloc'
                    args = trypy_to_Vec3(other), self
                case 'Matrix':
                    fname = 'matrixmult'
                    convother = trypy_to_Mtx16(other)
                    othernex = create_Nex_constant(NexMtx, convother,)
                    args = self, othernex
                case 'list' | 'set' | 'tuple':
                    if (len(other)<=3):
                        fname = 'transformloc'
                        args = trypy_to_Vec3(other), self
                    else:
                        fname = 'matrixmult'
                        convother = trypy_to_Mtx16(other)
                        othernex = create_Nex_constant(NexMtx, convother,)
                        args = self, othernex
                case _:
                    raise NexError(f"TypeError. Cannot matrix-multiply 'SocketMatrix' with '{type(other).__name__}'.")
            return NexWrappedFcts[fname](*args,)

        def __rmatmul__(self, other): # other @ self
            type_name = type(other).__name__
            match type_name:
                case 'NexMtx':
                    return NotImplemented
                case 'NexVec' | 'Vector':
                    raise NexError(f"TypeError. Cannot matrix-multiply 'Vector' with 'Matrix'. Only 'Matrix @ Vector' is allowed.")
                case _ if ('Nex' in type_name):
                    raise NexError(f"TypeError. Cannot matrix-multiply '{other.nxtydsp}' with 'SocketMatrix'.")
                case 'Matrix' | 'list' | 'set' | 'tuple':
                    convother = trypy_to_Mtx16(other)
                    othernex = create_Nex_constant(NexMtx, convother,)
                    args = othernex, self
                case _:
                    raise NexError(f"TypeError. Cannot matrix-multiply '{type(other).__name__}' with 'SocketMatrix'.")
            return NexWrappedFcts['matrixmult'](*args,)

        # ---------------------
        # NexMtx Itter

        def __len__(self): #len(itter)
            return 4

        def __getitem__(self, key):
            match key:
                case int(): #m[i]
                    sep_rows = NexWrappedFcts['separows'](self)
                    if (key not in {0,1,2,3}):
                        raise NexError("IndexError. indice in SocketMatrix[i] exceeded maximal range of 3.")
                    return sep_rows[key]

                case slice(): #m[:i]
                    sep_rows = NexWrappedFcts['separows'](self)
                    indices = range(*key.indices(4))
                    return tuple(sep_rows[i] for i in indices)

                case tuple(): #m[i,j]
                    i, j = key
                    sep_rows = NexWrappedFcts['separows'](self)
                    return sep_rows[i][j]

                case _: raise NexError("TypeError. indices in SocketMatrix[i] must be integers or slices or tuple.")

        def __iter__(self): #for f in itter
            for i in range(len(self)):
                yield self[i]

        def __setitem__(self, key, value): #m[0] = Quaternion((1,2,3,4))
            to_frame = []

            match key:
                case int(): #m[i] =
                    q1, q2, q3, q4 = NexWrappedFcts['separows'](self)
                    to_frame.append(q4.nxsock.node.parent)
                    match key:
                        case 0: new_rows = value, q2, q3, q4
                        case 1: new_rows = q1, value, q3, q4
                        case 2: new_rows = q1, q2, value, q4
                        case 3: new_rows = q1, q2, q3, value
                        case _: raise NexError("IndexError. indice in SocketMatrix[i] exceeded maximal range of 3.")

                case slice(): #m[:] =
                    if (key!=slice(None,None,None)):
                        raise NexError("Only [:] slicing is supported for SocketMatrix.")
                    new_rows = value
                    if (len(new_rows)!=4):
                        raise NexError("Slice assignment requires exactly 4 Quaternion compatible value.")

                case tuple(): #m[i,j] =
                    i, j = key
                    if (i not in {0,1,2,3}) or (j not in {0,1,2,3}):
                        raise NexError("IndexError. indices in SocketMatrix[i,j] exceeded maximal range of 3.")
                    quats = NexWrappedFcts['separows'](self)
                    q1, q2, q3, q4 = quats
                    to_frame.append(q4.nxsock.node.parent)
                    newq = quats[i]
                    newq[j] = value
                    match i:
                        case 0: new_rows = newq, q2, q3, q4
                        case 1: new_rows = q1, newq, q3, q4
                        case 2: new_rows = q1, q2, newq, q4
                        case 3: new_rows = q1, q2, q3, newq

                case _: raise NexError("TypeError. indices in SocketMatrix[i] must be integers or slices or tuple.")

            #need to convert items in rows to quaternion compatible, in case user passed a set
            conv_rows = []
            for q in new_rows:
                row_typename = type(q).__name__
                match row_typename:
                    case 'NexQuat' | 'NexVec':
                        newq = q
                    case 'NexCol':
                        r, g, b, a = NexWrappedFcts['sepacolor'](q)
                        newq =  NexWrappedFcts['combiquat'](r,g,b,a)
                        to_frame.append(r.nxsock.node.parent)
                    case 'Quaternion' | 'Vector' | 'Color' | 'bpy_prop_array' | 'int' | 'float' | 'bool':
                        newq = trypy_to_Quat4(q)
                    case 'list' | 'set' | 'tuple':
                        #correct lenght?
                        if len(q)!=4:
                            raise NexError(f"AssignationError. Assigning to 'SocketMatrix' row Expected an itterable of len4. Recieved len{len(value)}.")
                        #user is giving us a mix of Sockets and python types?..
                        iscombi = any(('Nex' in type(v).__name__) for v in q)
                        #not valid itterable
                        if (not iscombi) and not alltypes(*q, types=(float,int,bool),):
                            raise NexError(f"AssignationError.  Assigning to 'SocketMatrix' row Expected an itterable containing types 'Socket','int','float','bool'.")
                        newq = NexWrappedFcts['combiquat'](*q,) if (iscombi) else trypy_to_Quat4(q)
                    case _:
                        raise NexError(f"AssignationError.  Assigning to 'SocketMatrix' row Expected Quaternion-compatible values. Recieved '{row_typename}'.")
                conv_rows.append(newq)
                continue

            new = NexWrappedFcts['combirows'](*conv_rows)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            to_frame.append(new.nxsock.node.parent)

            frame_nodes(self.node_tree, *to_frame, label=f"Mtx.setitem[{key if (type(key) is int) else ',' if (type(key) is tuple) else ':' }]",)

            return None

        # ---------------------
        # NexMtx Functions & Properties
        # We try to immitate mathutils https://docs.blender.org/api/current/mathutils.html

        _attributes = Nex._attributes + ('translation','rotation','scale','is_invertible')

        def determinant(self):
            return NexWrappedFcts['matrixdeterminant'](self,)

        def inverted(self):
            return NexWrappedFcts['matrixinvert'](self,)

        def transposed(self):
            return NexWrappedFcts['matrixtranspose'](self,)

        #TODO .decompose() #Same as sepatransforms
        #TODO .normalized() #Return a column normalized matrix
        #TODO .row & .col return tuple of 4Quat setter & getter.

        @property
        def translation(self):
            return NexWrappedFcts['sepatransforms'](self,)[0]
        @translation.setter
        def translation(self, value):
            loc, rot, sca = NexWrappedFcts['sepatransforms'](self,)
            type_name = type(value).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec':
                    pass
                case 'Vector' | 'int' | 'float' | 'bool':
                    value = trypy_to_Vec3(value)
                case 'list' | 'set' | 'tuple':
                    #correct lenght?
                    if len(value)!=3:
                        raise NexError(f"AssignationError. 'SocketMatrix.translation' Expected an itterable of len3. Recieved len{len(value)}.")
                    #user is giving us a mix of Sockets and python types?..
                    iscombi = any(('Nex' in type(v).__name__) for v in value)
                    #not valid itterable
                    if (not iscombi) and not alltypes(*value, types=(float,int,bool),):
                        raise NexError(f"AssignationError. 'SocketMatrix.translation' Expected an itterable containing types 'Socket','int','float','bool'.")
                    value = NexWrappedFcts['combixyz'](*value,) if (iscombi) else trypy_to_Vec3(value)
                case _:
                    raise NexError(f"AssignationError. 'SocketMatrix.translation' Expected Vector-compatible values. Recieved '{type_name}'.")

            new = NexWrappedFcts['combitransforms'](value,rot,sca)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            frame_nodes(self.node_tree, loc.nxsock.node, new.nxsock.node, label="Matrix.translation =..",)
            return None

        #NOTE somehow mathutils.Matrix.rotation do not exist? why?
        @property
        def rotation(self):
            return NexWrappedFcts['sepatransforms'](self,)[1]
        @rotation.setter
        def rotation(self, value):
            loc, rot, sca = NexWrappedFcts['sepatransforms'](self,)
            type_name = type(value).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec' | 'NexQuat':
                    pass
                case 'Quaternion' | 'Vector' | 'int' | 'float' | 'bool':
                    value = trypy_to_Quat4(value)
                case 'list' | 'set' | 'tuple':
                    #correct lenght?
                    if len(value)!=4:
                        raise NexError(f"AssignationError. 'SocketMatrix.rotation' Expected an itterable of len4. Recieved len{len(value)}.")
                    #user is giving us a mix of Sockets and python types?..
                    iscombi = any(('Nex' in type(v).__name__) for v in value)
                    #not valid itterable
                    if (not iscombi) and not alltypes(*value, types=(float,int,bool),):
                        raise NexError(f"AssignationError. 'SocketMatrix.rotation' Expected an itterable containing types 'Socket','int','float','bool'.")
                    value = NexWrappedFcts['combiquat'](*value,) if (iscombi) else trypy_to_Quat4(value)
                case _:
                    raise NexError(f"AssignationError. 'SocketMatrix.rotation' Expected Vector-compatible values. Recieved '{type_name}'.")

            new = NexWrappedFcts['combitransforms'](loc,value,sca)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            frame_nodes(self.node_tree, loc.nxsock.node, new.nxsock.node, label="Matrix.rotation =..",)
            return None

        #NOTE somehow mathutils.Matrix.scale do not exist? why?
        @property
        def scale(self):
            return NexWrappedFcts['sepatransforms'](self,)[2]
        @scale.setter
        def scale(self, value):
            loc, rot, sca = NexWrappedFcts['sepatransforms'](self,)
            type_name = type(value).__name__
            match type_name:
                case 'NexFloat' | 'NexInt' | 'NexBool' | 'NexVec':
                    pass
                case 'Vector' | 'int' | 'float' | 'bool':
                    value = trypy_to_Vec3(value)
                case 'list' | 'set' | 'tuple':
                    #correct lenght?
                    if len(value)!=3:
                        raise NexError(f"AssignationError. 'SocketMatrix.scale' Expected an itterable of len3. Recieved len{len(value)}.")
                    #user is giving us a mix of Sockets and python types?..
                    iscombi = any(('Nex' in type(v).__name__) for v in value)
                    #not valid itterable
                    if (not iscombi) and not alltypes(*value,types=(float,int,bool),):
                        raise NexError(f"AssignationError. 'SocketMatrix.scale' Expected an itterable containing types 'Socket','int','float','bool'.")
                    value = NexWrappedFcts['combixyz'](value[0], value[1], value[2],) if (iscombi) else trypy_to_Vec3(value)
                case _:
                    raise NexError(f"AssignationError. 'SocketMatrix.scale' Expected Vector-compatible values. Recieved '{type_name}'.")

            new = NexWrappedFcts['combitransforms'](loc,rot,value)
            self.nxsock = new.nxsock
            self.nxid = new.nxid
            frame_nodes(self.node_tree, loc.nxsock.node, new.nxsock.node, label="Matrix.scale =..",)
            return None

        @property
        def is_invertible(self):
            return NexWrappedFcts['matrixisinvertible'](self,)
        @is_invertible.setter
        def is_invertible(self, value):
            raise NexError("AssignationError. 'SocketMatrix.is_invertible' is read-only.")

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
                    outsock = get_socket_by_name(self.node_tree, in_out='OUTPUT', socket_name=socket_name,)
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
                        raise NexError(f"TypeError. Cannot assign '{value.nxtydsp}' to output {self.nxtydsp} '{socket_name}'.")

                # or we simply output a default python constant value
                case _:

                    # try to convert our pyvalue to a socket compatible datatype.
                    newval, _, socktype = trypy_to_Sockdata(value)
                    
                    #support for automatic types
                    out_type = self.nxstype
                    if (out_type=='NodeSocketNexAutomatic'):
                        out_type = socktype

                    #get socket, create if non existent
                    outsock = get_socket_by_name(self.node_tree, in_out='OUTPUT', socket_name=socket_name,)
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
                        raise NexError(f"TypeError. Cannot assign type '{type(value).__name__}' to output {self.nxtydsp} '{socket_name}'.")

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
    
    # Return our premade types and function that the factory made for the context custom node.

    nextoys = {}
    nextoys['nexusertypes'] = {
        'inbool':NexBool,
        'inint':NexInt,
        'infloat':NexFloat,
        'invec':NexVec,
        'incol':NexCol,
        'inquat':NexQuat,
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

    nextoys['nexuserfunctions'] = {}
    nextoys['nexuserfunctions'].update(NexWrappedUserFcts)

    return nextoys