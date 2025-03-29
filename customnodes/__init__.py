# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import (
        NODEBOOSTER_NG_GN_CameraInfo,
        NODEBOOSTER_NG_SH_CameraInfo,
        NODEBOOSTER_NG_CP_CameraInfo,
        )
from . lightinfo import (
        NODEBOOSTER_NG_lightinfo,
        )
from . sceneinfo import (
        NODEBOOSTER_NG_GN_SceneInfo,
        NODEBOOSTER_NG_SH_SceneInfo,
        NODEBOOSTER_NG_CP_SceneInfo,
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
        NODEBOOSTER_NG_GN_SequencerVolume,
        NODEBOOSTER_NG_SH_SequencerVolume,
        NODEBOOSTER_NG_CP_SequencerVolume,
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
    NODEBOOSTER_NG_GN_SceneInfo,
    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_GN_CameraInfo,
    NODEBOOSTER_NG_GN_IsRenderedView,
    NODEBOOSTER_NG_GN_SequencerVolume,
    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,
    )

SH_CustomNodes = (
    NODEBOOSTER_NG_SH_SceneInfo,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_SH_CameraInfo,
    NODEBOOSTER_NG_SH_SequencerVolume,
    )

CP_CustomNodes = (
    NODEBOOSTER_NG_CP_SceneInfo,
    NODEBOOSTER_NG_CP_RenderInfo,
    NODEBOOSTER_NG_CP_CameraInfo,
    NODEBOOSTER_NG_CP_SequencerVolume,
    )

#for register, handlers will also use this list for automatic updates.

classes = (
    NODEBOOSTER_NG_GN_CameraInfo,
    NODEBOOSTER_NG_SH_CameraInfo,
    NODEBOOSTER_NG_CP_CameraInfo,

    NODEBOOSTER_NG_lightinfo,

    NODEBOOSTER_NG_GN_SceneInfo,
    NODEBOOSTER_NG_SH_SceneInfo,
    NODEBOOSTER_NG_CP_SceneInfo,

    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_CP_RenderInfo,

    NODEBOOSTER_NG_GN_IsRenderedView,

    NODEBOOSTER_NG_GN_SequencerVolume,
    NODEBOOSTER_NG_SH_SequencerVolume,
    NODEBOOSTER_NG_CP_SequencerVolume,

    NODEBOOSTER_NG_mathexpression,
    NODEBOOSTER_NG_pyexpression,
    NODEBOOSTER_NG_pynexscript,
    )
