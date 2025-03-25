# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import NODEBOOSTER_NG_camerainfo
from . lightinfo import NODEBOOSTER_NG_lightinfo
from . isrenderedview import NODEBOOSTER_NG_isrenderedview
from . sequencervolume import NODEBOOSTER_NG_sequencervolume
from . mathexpression import NODEBOOSTER_NG_mathexpression
from . pyexpression import NODEBOOSTER_NG_pyexpression
from . pynexscript import NODEBOOSTER_NG_pynexscript


#NOTE order here will be order of appearance in the shift+a add menu
classes = (

    NODEBOOSTER_NG_camerainfo,
    NODEBOOSTER_NG_lightinfo,
    NODEBOOSTER_NG_isrenderedview,
    NODEBOOSTER_NG_sequencervolume,
    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,

    )
