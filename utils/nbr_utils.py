# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from mathutils import Vector
import numpy as np


def map_range(value, from_min, from_max, to_min, to_max,):
    if (from_max - from_min == 0):
        return to_min if (value <= from_min) else to_max
    result = (value - from_min) / (from_max - from_min) * (to_max - to_min) + to_min
    return result


def map_positions(old_positions:np.array, old_bounds:tuple[Vector, Vector], new_bounds:tuple[Vector, Vector],) -> np.array:
    """map positions from old bounds to new bounds"""
    
    # Extract bounds
    old_min, old_max = old_bounds
    new_min, new_max = new_bounds
    
    # Calculate the range of the old and new bounds
    old_range = np.array([old_max.x - old_min.x, old_max.y - old_min.y])
    new_range = np.array([new_max.x - new_min.x, new_max.y - new_min.y])
    
    # Normalize positions to 0-1 range
    normalized = (old_positions - np.array([old_min.x, old_min.y])) / old_range
    
    # Scale to new range and offset to new minimum
    new_positions = normalized * new_range + np.array([new_min.x, new_min.y])
    
    return new_positions
    