# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import types
import typing
from collections import namedtuple


ColorRGBA = namedtuple('ColorRGBA', ['r','g','b','a'])

def anytype(*args, types:tuple=None) -> bool:
    """Returns True if any argument in *args is an instance of any type in the 'types' tuple."""
    return any(isinstance(arg, types) for arg in args)


def alltypes(*args, types: tuple = None) -> bool:
    """Returns True if all arguments in *args are instances of any type in the 'types' tuple."""
    return all(isinstance(arg, types) for arg in args)


def functioncopy(fct, new_name=''):
    """Creates a new function with exactly the same behavior, arguments, defaults, closure, and attributes but with a new __name__."""
    assert new_name!='', "Please define a 'new_name' parameter for functioncopy()"
    new = types.FunctionType(fct.__code__, fct.__globals__, name=new_name, argdefs=fct.__defaults__, closure=fct.__closure__,)
    new.__dict__.update(fct.__dict__)
    new.__annotations__ = fct.__annotations__
    return new


def is_annotation_compliant(value, annotated_type) -> bool:
    """Recursively check if 'value' is an instance of 'annotated_type', 
    which may be a simple type, a PEP 604 union (X|Y|Z), or a typing.Union."""

    # If there's no 'origin', it's a normal type (e.g. int, float, etc.)
    origin = typing.get_origin(annotated_type)
    if (origin is None):
        # A direct type, so just do an isinstance check
        return isinstance(value, annotated_type)

    # If it's a union (PEP 604 or typing.Union), check each sub‐type
    if (origin is typing.Union):
        sub_types = typing.get_args(annotated_type)
        # Return True if *any* of the sub_types matches
        return any(is_annotation_compliant(value, st) for st in sub_types)

    # Otherwise (e.g. a generic like List[str]), fallback to a direct check
    # or you could expand this if you need deeper generics logic
    return isinstance(value, annotated_type)
