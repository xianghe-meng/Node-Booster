# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

bpy_array = bpy.types.bpy_prop_array
from mathutils import Color, Euler, Matrix, Quaternion, Vector
from ..utils.fct_utils import ColorRGBA


def py_to_Vec3(value):
    match value:

        case Vector():
            if (len(value)!=3): raise TypeError(f"Vector({value[:]}) should have 3 elements for 'SocketVector' compatibility.")
            return value

        case ColorRGBA() | Color():
            return Vector((value[0],value[1],value[2]))

        case list() | set() | tuple() | bpy_array():
            if (len(value)!=3): raise TypeError(f"{type(value).__name__}({value[:]}) should have 3 float elements for 'SocketVector' compatibility.")
            return Vector(value)

        case int() | float() | bool():
            return Vector((float(value), float(value), float(value),))

        case _: raise TypeError(f"type {type(value).__name__}({value[:]}) is not compatible with 'SocketVector'.")

def py_to_Quat4(value):
    match value:

        case Quaternion():
            return value

        case ColorRGBA():
            return Quaternion(value)

        case list() | set() | tuple() | bpy_array() | Vector() | Color():
            if len(value) not in (3, 4):
                raise TypeError(f"{type(value).__name__}({list(value)}) should have 3 or 4 elements for 'ColorRGBA' compatibility.")
            if (len(value)==3):
                  return Quaternion(value+1.0)
            else: return Quaternion((value[0], value[1], value[2], value[3],))

        case int() | float() | bool():
            v = float(value)
            return Quaternion((v,v,v,v))

        case _:
            extra = value[:] if hasattr(value, '__getitem__') else value
            raise TypeError(f"type {type(value).__name__}({extra}) is not compatible with 'ColorRGBA'.")

def py_to_RGBA(value):
    match value:

        case ColorRGBA():
            return value

        case Color():
            return ColorRGBA(value[0], value[1], value[2], 1.0)

        case list() | set() | tuple() | bpy_array() | Vector():
            if len(value) not in (3, 4):
                raise TypeError(f"{type(value).__name__}({list(value)}) should have 3 or 4 elements for 'ColorRGBA' compatibility.")
            if (len(value)==3):
                  return ColorRGBA(value[0], value[1], value[2], 1.0)
            else: return ColorRGBA(value[0], value[1], value[2], value[3])

        case int() | float() | bool():
            v = float(value)
            return ColorRGBA(v, v, v, 1.0)

        case _:
            extra = value[:] if hasattr(value, '__getitem__') else value
            raise TypeError(f"type {type(value).__name__}({extra}) is not compatible with 'ColorRGBA'.")

def py_to_Mtx16(value):
    match value:

        case Matrix():
            rowflatten = [v for row in value for v in row]
            if (len(value)!=4): raise TypeError(f"type Matrix({rowflatten[:]}) type should have 4 rows or 4 elements of float values for 'SocketMatrix' compatibility.")
            if (len(rowflatten)!=16): raise TypeError(f"type Matrix({rowflatten[:]}) should contain a total of 16 elements for 'SocketMatrix' compatibility. {len(rowflatten)} found.")
            return value

        case list() | set() | tuple():
            if (len(value)!=16): raise TypeError(f"{type(value).__name__}({value[:]}) should contain 16 float elements for 'SocketMatrix' compatibility. {len(value)} elements found.")
            rows = [value[i*4:(i+1)*4] for i in range(4)]
            return Matrix(rows)
        
        case _: raise TypeError(f"Cannot convert type {type(value).__name__}({value[:]}) to Matrix().")

def py_to_Sockdata(value, return_value_only=False):
    """Convert a given python variable into data we can use to create and assign sockets default value, type and label."""

    matrix_label = ''

    #we sanatize out possible types depending on their length
    if (type(value) in {tuple, list, set, Vector, Euler, bpy_array}):

        if type(value) in {tuple, list, set}:
            if any('Nex' in type(e).__name__ for e in value) or any('Node' in type(e).__name__ for e in value):
                raise TypeError(f"Cannot assign a '{type(value).__name__}' containing a SocketTypes to a Socket default value.")

        value = list(value)
        n = len(value)

        match n:
            case 0: value = Vector((0,0,0))
            case 1: value = Vector((value[0],0,0))
            case 2: value = Vector((value[0],value[1],0))
            case 3: value = Vector(value)
            case 4: value = ColorRGBA(*value)

            case _ if n <= 16:
                if (n != 16):
                    matrix_label = f'List[{len(value)}]'
                    nulmatrix = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                    value.extend(nulmatrix[len(value):])
                flatTorows = [value[i*4:(i+1)*4] for i in range(4)]
                value = Matrix(flatTorows)

            case _:
                raise TypeError(f"Cannot assign a '{type(value).__name__}' of lenght {n} to a Socket default value.")

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
            value = ColorRGBA(*value,1) #add alpha channel
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketColor'

        case ColorRGBA():
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketColor'

        case Quaternion():
            repr_label = str(tuple(round(n,4) for n in value))
            socket_type = 'NodeSocketRotation'

        case Matrix():
            repr_label = "4x4Matrix" if (not matrix_label) else matrix_label
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
            raise TypeError(f"Assigning a '{type(value).__name__}' to a Socket default value is not possible.")

    if (return_value_only):
        return value
    return value, repr_label, socket_type
