# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


import types
import inspect
import typing
import functools


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


def check_annotation(value, annotated_type) -> bool:
    """Recursively check if 'value' is an instance of 'annotated_type', which may be a simple type, a PEP 604 union (X|Y|Z), or a typing.Union."""

    # If there's no 'origin', it's a normal type (e.g. int, float, etc.)
    origin = typing.get_origin(annotated_type)
    if (origin is None):
        # A direct type, so just do an isinstance check
        return isinstance(value, annotated_type)

    # If it's a union (PEP 604 or typing.Union), check each sub‐type
    if (origin is typing.Union):
        sub_types = typing.get_args(annotated_type)
        # Return True if *any* of the sub_types matches
        return any(check_annotation(value, st) for st in sub_types)

    # Otherwise (e.g. a generic like List[str]), fallback to a direct check
    # or you could expand this if you need deeper generics logic
    return isinstance(value, annotated_type)


def strongtyping(PassedError):
    """A decorator factory that takes a given error class and enforces type hints on the decorated function’s parameters.
    Handle error if user passed wrong parameter types. Or too much or too little params."""

    #NOTE this function is biased toward functions of nodesetter that work with internal types. might need a rework later if you
    # intend to use it with other functions. Pass internalparams and adjusts -2

    def pretty(annot,istype=False):
        """better annotation for user error message"""
        if (istype):
            annot = type(annot).__name__
            annot = annot.replace('NodeSocket','Socket')
            return annot
        annot = str(annot)
        annot = annot.replace('bpy.types.','').replace('NodeSocket','Socket')
        annot = annot.replace('SocketVectorXYZ | ','').replace('SocketVectorTranslation | ','') #internal dumb distinctions..
        annot = annot.replace(' |',',')
        annot = annot.replace("<class '",'').replace("'>",'')
        return annot

    def decorator(func):
        sig = inspect.signature(func)
        hints = typing.get_type_hints(func)
        internalparams = {'ng','callhistory'}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            
            #collect args of this function & remove strictly internal args from documentation
            allparamnames = list(func.__code__.co_varnames[:func.__code__.co_argcount])
            allparamnames = [n for n in allparamnames if (n not in internalparams)]
            parameternames = ', '.join(allparamnames)
            funcparamcount = len(allparamnames)

            #calling the bind function will raise an error if the user inputed wrong params. We are taking advantage of this to wrap the error to the user
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
            except TypeError as e:
                if ('too many positional arguments' in str(e)):
                    raise PassedError(f"Function {func.__name__}({parameternames}) recieved extra Param(s). Expected {funcparamcount}. Recieved {len(args)-2}.")
                elif ('missing a required argument') in str(e):
                    raise PassedError(f"Function {func.__name__}({parameternames}) needs more Param(s). Expected {funcparamcount}. Recieved {len(args)-2}.")
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
                        if not check_annotation(item, annotated_type):
                            raise PassedError(f"Function {func.__name__}({parameternames}..) accepts Params of type {pretty(annotated_type)}. Recieved {pretty(item,istype=True)}.")
                else:
                    # Normal parameter check a single value
                    if not check_annotation(param_value, annotated_type):
                        if (funcparamcount>1):
                            raise PassedError(f"Function {func.__name__}({parameternames}) accepts Param '{param_name}' of type {pretty(annotated_type)}. Recieved {pretty(param_value,istype=True)}.")
                        raise PassedError(f"Function {func.__name__}({parameternames}) accepts Param of type {pretty(annotated_type)}. Recieved {pretty(param_value,istype=True)}.")

            return func(*bound.args, **bound.kwargs)

        return wrapper
    return decorator