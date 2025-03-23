# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import NODEBOOSTER_NG_camerainfo
from . point_lightinfo import NODEBOOSTER_NG_point_lightinfo
from . sun_lightinfo import NODEBOOSTER_NG_sun_lightinfo
from . spot_lightinfo import NODEBOOSTER_NG_spot_lightinfo
from . area_lightinfo import NODEBOOSTER_NG_area_lightinfo
from . isrenderedview import NODEBOOSTER_NG_isrenderedview
from . sequencervolume import NODEBOOSTER_NG_sequencervolume
from . mathexpression import NODEBOOSTER_NG_mathexpression
from . pyexpression import NODEBOOSTER_NG_pyexpression
from . pynexscript import NODEBOOSTER_NG_pynexscript
# from . pythonscript import NODEBOOSTER_NG_pythonscript


#NOTE order will be order of appearance in addmenu
classes = (

    NODEBOOSTER_NG_camerainfo,
    NODEBOOSTER_NG_point_lightinfo,
    NODEBOOSTER_NG_sun_lightinfo,
    NODEBOOSTER_NG_spot_lightinfo,
    NODEBOOSTER_NG_area_lightinfo,
    NODEBOOSTER_NG_isrenderedview,
    NODEBOOSTER_NG_sequencervolume,
    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,
    # NODEBOOSTER_NG_pythonscript,

    )
