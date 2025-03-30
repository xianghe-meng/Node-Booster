# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


def map_range(value, from_min, from_max, to_min, to_max,):
    if from_max - from_min == 0:
        return to_min if value <= from_min else to_max
    result = (value - from_min) / (from_max - from_min) * (to_max - to_min) + to_min
    return result
