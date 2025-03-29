# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import (
       NODEBOOSTER_NG_camerainfo,
       )
from . lightinfo import (
       NODEBOOSTER_NG_lightinfo,
       )
from . sceneinfo import (
       NODEBOOSTER_NG_sceneinfo,
       )
from . renderinfo import (
       NODEBOOSTER_NG_GN_RenderInfo,
       NODEBOOSTER_NG_SH_RenderInfo,
       NODEBOOSTER_NG_CP_RenderInfo,
       )
from . isrenderedview import (
       NODEBOOSTER_NG_GN_IsRenderedView,
       )
from . sequencervolume import (
       NODEBOOSTER_NG_sequencervolume,
       )
from . mathexpression import (
       NODEBOOSTER_NG_mathexpression,
       )
from . pyexpression import (
       NODEBOOSTER_NG_pyexpression,
       )
from . pynexscript import (
       NODEBOOSTER_NG_pynexscript,
       )

#For menus, in order of appearance

GN_CustomNodes = (
    NODEBOOSTER_NG_lightinfo,
    NODEBOOSTER_NG_sceneinfo,
    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_camerainfo,
    NODEBOOSTER_NG_GN_IsRenderedView,
    NODEBOOSTER_NG_sequencervolume,
    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,
    )

SH_CustomNodes = (
    NODEBOOSTER_NG_SH_RenderInfo,
    )

CP_CustomNodes = (
    NODEBOOSTER_NG_CP_RenderInfo,
    )

#for register, handlers will also use this list for automatic updates.

classes = (
    NODEBOOSTER_NG_camerainfo,
    NODEBOOSTER_NG_lightinfo,
    NODEBOOSTER_NG_sceneinfo,
    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_CP_RenderInfo,
    NODEBOOSTER_NG_GN_IsRenderedView,
    NODEBOOSTER_NG_sequencervolume,
    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,
    )
