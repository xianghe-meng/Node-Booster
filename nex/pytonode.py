# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from mathutils import Color, Euler, Matrix, Quaternion, Vector
from collections import namedtuple
RGBAColor = namedtuple('RGBAColor', ['r','g','b','a'])


def py_to_Vec3(value):
    match value:
        case Vector():
            if (len(value)!=3): raise TypeError(f"Vector({value[:]}) should have 3 elements for 'SocketVector' compatibility.")
            return value
        case list() | set() | tuple():
            if (len(value)!=3): raise TypeError(f"{type(value).__name__}({value[:]}) should have 3 float elements for 'SocketVector' compatibility.")
            return Vector(value)
        case int() | float() | bool():
            return Vector((float(value), float(value), float(value),))
        case _:
            raise TypeError(f"type {type(value).__name__}({value[:]}) is not compatible with 'SocketVector'.")

def py_to_Mtx16(value):
    match value:
        case Matrix():
            flatten = [val for row in value for val in row]
            if (len(value)!=4):
                raise TypeError(f"type Matrix({flatten[:]}) type should have 4 rows or 4 elements of float values for 'SocketMatrix' compatibility.")
            if (len(flatten)!=16):
                raise TypeError(f"type Matrix({flatten[:]}) should contain a total of 16 elements for 'SocketMatrix' compatibility. {len(flatten)} found.")
            return value
        case list() | set() | tuple():
            if (len(value)!=16): raise TypeError(f"{type(value).__name__}({value[:]}) should contain 16 float elements for 'SocketMatrix' compatibility. {len(value)} elements found.")
            rows = [value[i*4:(i+1)*4] for i in range(4)]
            return Matrix(rows)
        case _:
            raise TypeError(f"Cannot convert type {type(value).__name__}({value[:]}) to Matrix().")

def py_to_Sockdata(value):
    """Convert a given python variable into data we can use to create and assign sockets"""
    #TODO do we want to support numpy as well? or else?

    matrix_special_label = ''

    #we sanatize out possible types depending on their length
    if (type(value) in {tuple, list, set, Vector, Euler, bpy.types.bpy_prop_array}):

        if type(value) in {tuple, list, set}:
            if any('Nex' in type(e).__name__ for e in value):
                raise TypeError(f"Cannot convert '{type(value).__name__.title()}' containing SocketTypes to a SocketData.")

        value = list(value)
        n = len(value)

        if (n == 1):
            value = float(value[0])

        elif (n <= 3):
            value = Vector(value + [0.0]*(3 - n))

        elif (n == 4):
            value = RGBAColor(*value)

        elif (4 < n <= 16):
            if (n < 16):
                matrix_special_label = f'List[{len(value)}]'
                nulmatrix = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                value.extend(nulmatrix[len(value):])
            value =  Matrix([value[i*4:(i+1)*4] for i in range(4)])

        else:
            raise TypeError(f"Converting a type '{type(value).__name__.title()}' of lenght {n} to a SocketData is not supported.")

    # then we define the socket type string & the potential socket label
    match value:

        case bool():
            repr_label = str(value)
            socket_type = 'NodeSocketBool'

        case int():
            repr_label = str(value)
            socket_type = 'NodeSocketInt'

        case float():
            repr_label = str(round(value,4))
            socket_type = 'NodeSocketFloat'

        case str():
            repr_label = '"'+value+'"'
            socket_type = 'NodeSocketString'

        case Vector():
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketVector'

        case Color():
            value = RGBAColor(*value,1) #add alpha channel
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketColor'

        case RGBAColor():
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketColor'

        case Quaternion():
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketRotation'

        case Matrix():
            repr_label = "MatrixValue" if (not matrix_special_label) else matrix_special_label
            socket_type = 'NodeSocketMatrix'

        case bpy.types.Object():
            repr_label = f'D.objects["{value.name}"]'
            socket_type = 'NodeSocketObject'

        case bpy.types.Collection():
            repr_label = f'D.collections["{value.name}"]'
            socket_type = 'NodeSocketCollection'

        case bpy.types.Material():
            repr_label = f'D.materials["{value.name}"]'
            socket_type = 'NodeSocketMaterial'

        case bpy.types.Image():
            repr_label = f'D.images["{value.name}"]'
            socket_type = 'NodeSocketImage'

        case _:
            raise TypeError(f"Converting a '{type(value).__name__.title()}' to a SocketData is not possible.")

    return value, repr_label, socket_type
