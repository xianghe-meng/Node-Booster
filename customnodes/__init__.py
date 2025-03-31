# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later


#TODO nodes ideas:
# InputListener node: 
#   - listen to user keyboard or mouse inputs. launch a modal operator that listen and pass the infor to the node.
#   - the listener might work on global space
# Material Info node? 
#   - gather informations about the material? what?
# Color Palette Node? easily swap between color palettes?
# File IO:
#   - For geometry node, could create a mesh on the fly from a file and set up as field attributes.
# View3D Info node:
#   - Like camera info, but for the 3d view (location/rotation/fov/clip/)
#   - Problem: what if there are many? Perhaps should use context.

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
from .rnainfo import (
        NODEBOOSTER_NG_GN_RNAInfo,
        NODEBOOSTER_NG_SH_RNAInfo,
        NODEBOOSTER_NG_CP_RNAInfo,
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
        NODEBOOSTER_NG_GN_PyNexScript,
        NODEBOOSTER_NG_SH_PyNexScript,
        NODEBOOSTER_NG_CP_PyNexScript,
        )
from . deviceinput import (
        NODEBOOSTER_NG_GN_DeviceInput,
        NODEBOOSTER_NG_SH_DeviceInput,
        NODEBOOSTER_NG_CP_DeviceInput,
        )

#For menus, in order of appearance

GN_CustomNodes = (
    NODEBOOSTER_NG_GN_RNAInfo,
    NODEBOOSTER_NG_GN_LightInfo,
    NODEBOOSTER_NG_GN_SceneInfo,
    NODEBOOSTER_NG_GN_DeviceInput,
    NODEBOOSTER_NG_GN_RenderInfo,
    NODEBOOSTER_NG_GN_CameraInfo,
    NODEBOOSTER_NG_GN_IsRenderedView, #this one doesn't make sense in other editors.
    NODEBOOSTER_NG_GN_SequencerSound,
    NODEBOOSTER_NG_GN_MathExpression,
    NODEBOOSTER_NG_GN_PyExpression,
    NODEBOOSTER_NG_GN_PyNexScript,
    )

SH_CustomNodes = (
    NODEBOOSTER_NG_SH_RNAInfo,
    NODEBOOSTER_NG_SH_LightInfo,
    NODEBOOSTER_NG_SH_SceneInfo,
    NODEBOOSTER_NG_SH_DeviceInput,
    NODEBOOSTER_NG_SH_RenderInfo,
    NODEBOOSTER_NG_SH_CameraInfo,
    NODEBOOSTER_NG_SH_SequencerSound,
    NODEBOOSTER_NG_SH_MathExpression,
    NODEBOOSTER_NG_SH_PyExpression,
    NODEBOOSTER_NG_SH_PyNexScript,
    )

CP_CustomNodes = (
    NODEBOOSTER_NG_CP_RNAInfo,
    NODEBOOSTER_NG_CP_LightInfo,
    NODEBOOSTER_NG_CP_SceneInfo,
    NODEBOOSTER_NG_CP_DeviceInput,
    NODEBOOSTER_NG_CP_RenderInfo,
    NODEBOOSTER_NG_CP_CameraInfo,
    NODEBOOSTER_NG_CP_SequencerSound,
    NODEBOOSTER_NG_CP_MathExpression,
    NODEBOOSTER_NG_CP_PyExpression,
    NODEBOOSTER_NG_CP_PyNexScript,
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

    NODEBOOSTER_NG_GN_RNAInfo,
    NODEBOOSTER_NG_SH_RNAInfo,
    NODEBOOSTER_NG_CP_RNAInfo,

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

    NODEBOOSTER_NG_GN_PyNexScript,
    NODEBOOSTER_NG_SH_PyNexScript,
    NODEBOOSTER_NG_CP_PyNexScript,

    NODEBOOSTER_NG_GN_DeviceInput,
    NODEBOOSTER_NG_SH_DeviceInput,
    NODEBOOSTER_NG_CP_DeviceInput,
    )
