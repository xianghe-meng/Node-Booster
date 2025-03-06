# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


def anytype(*args, types:tuple=None) -> bool:
    """Returns True if any argument in *args is an instance of any type in the 'types' tuple."""
    return any(isinstance(arg, types) for arg in args)

def alltypes(*args, types: tuple = None) -> bool:
    """Returns True if all arguments in *args are instances of any type in the 'types' tuple."""
    return all(isinstance(arg, types) for arg in args)