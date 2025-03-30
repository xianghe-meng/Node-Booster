# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import (
        NODEBOOSTER_NG_GN_CameraInfo,
        NODEBOOSTER_NG_SH_CameraInfo,
        NODEBOOSTER_NG_CP_CameraInfo,
        )
from . lightinfo import (
        NODEBOOSTER_NG_GN_LightInfo,
        NODEBOOSTER_NG_SH_LightInfo,
        NODEBOOSTER_NG_CP_LightInfo,
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
        NODEBOOSTER_NG_GN_SequencerSound,
        NODEBOOSTER_NG_SH_SequencerSound,
        NODEBOOSTER_NG_CP_SequencerSound,
        )
from . mathexpression import (
        NODEBOOSTER_NG_GN_MathExpression,
        NODEBOOSTER_NG_SH_MathExpression,
        NODEBOOSTER_NG_CP_MathExpression,
        )
from . pyexpression import (
        NODEBOOSTER_NG_GN_PyExpression,
        NODEBOOSTER_NG_SH_PyExpression,
        NODEBOOSTER_NG_CP_PyExpression,
        )
from . pynexscript import (
        NODEBOOSTER_NG_GN_pynexscript,
        )

#For menus, in order of appearance

GN_CustomNodes = (
    NODEBOOSTER_NG_GN_LightInfo,
    NODEBOOSTER_NG_GN_SceneInfo,
    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_GN_CameraInfo,
    NODEBOOSTER_NG_GN_IsRenderedView, #this one doesn't make sense in other editors.
    NODEBOOSTER_NG_GN_SequencerSound,
    NODEBOOSTER_NG_GN_MathExpression,
    NODEBOOSTER_NG_GN_PyExpression,
    NODEBOOSTER_NG_GN_pynexscript,
    )

SH_CustomNodes = (
    NODEBOOSTER_NG_SH_LightInfo,
    NODEBOOSTER_NG_SH_SceneInfo,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_SH_CameraInfo,
    NODEBOOSTER_NG_SH_SequencerSound,
    NODEBOOSTER_NG_SH_MathExpression,
    NODEBOOSTER_NG_SH_PyExpression,
    )

CP_CustomNodes = (
    NODEBOOSTER_NG_CP_LightInfo,
    NODEBOOSTER_NG_CP_SceneInfo,
    NODEBOOSTER_NG_CP_RenderInfo,
    NODEBOOSTER_NG_CP_CameraInfo,
    NODEBOOSTER_NG_CP_SequencerSound,
    NODEBOOSTER_NG_CP_MathExpression,
    NODEBOOSTER_NG_CP_PyExpression,
    )

#for register, handlers will also use this list for automatic updates.

classes = (
    NODEBOOSTER_NG_GN_CameraInfo,
    NODEBOOSTER_NG_SH_CameraInfo,
    NODEBOOSTER_NG_CP_CameraInfo,

    NODEBOOSTER_NG_GN_LightInfo,
    NODEBOOSTER_NG_SH_LightInfo,
    NODEBOOSTER_NG_CP_LightInfo,

    NODEBOOSTER_NG_GN_SceneInfo,
    NODEBOOSTER_NG_SH_SceneInfo,
    NODEBOOSTER_NG_CP_SceneInfo,

    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_CP_RenderInfo,

    NODEBOOSTER_NG_GN_IsRenderedView,

    NODEBOOSTER_NG_GN_SequencerSound,
    NODEBOOSTER_NG_SH_SequencerSound,
    NODEBOOSTER_NG_CP_SequencerSound,

    NODEBOOSTER_NG_GN_MathExpression,
    NODEBOOSTER_NG_SH_MathExpression,
    NODEBOOSTER_NG_CP_MathExpression,

    NODEBOOSTER_NG_GN_PyExpression,
    NODEBOOSTER_NG_SH_PyExpression,
    NODEBOOSTER_NG_CP_PyExpression,

    NODEBOOSTER_NG_GN_pynexscript,
    )
