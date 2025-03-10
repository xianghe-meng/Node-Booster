# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import types

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