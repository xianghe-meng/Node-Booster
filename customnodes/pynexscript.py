# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

#TODO 
# - IMPORTANT: Support Nex for Shader/Compositor
# - Please See TODO in nextypes.py and nodesetter.py as well! ALl are related to this node!
# - BUG? If auto depsgraph enabled, and user press exec button, execution occurs twice. due to deps trigger..
# Bonus; 
# -';' python notation?

import bpy

import re, traceback

from ..__init__ import get_addon_prefs
from ..resources import cust_icon
from ..nex.nextypes import NexFactory, NexError
from ..nex.nodesetter import generate_documentation
from ..utils.str_utils import word_wrap, prettyError
from ..utils.node_utils import (
    crosseditor_socktype_adjust,
    create_new_nodegroup,
    set_ng_socket_defvalue,
    remove_ng_socket,
    set_ng_socket_label,
    get_farest_node,
    get_booster_nodes,
    cache_booster_nodes_parent_tree,
)

NEXFUNCDOC = generate_documentation(tag='nexscript')
NEXNOTATIONDOC = {
    'a + b': {
                'name':"Addition",
                'desc':"Add between SocketFloats, SocketInts, SocketBools, SocketVector or SocketColors.\nType conversion is implicit."},
    'a - b': {
                'name':"Subtraction.",
                'desc':"Subtract between SocketFloats, SocketInts, SocketBools, SocketVector or SocketColors.\nType conversion is implicit."},
    'a * b': {
                'name':"Multiplication.",
                'desc':"Multiply between SocketFloats, SocketInts, SocketBools, SocketVector or SocketColors.\nType conversion is implicit."},
    'a / b': {
                'name':"Division.",
                'desc':"Divide between SocketFloats, SocketInts, SocketBools, SocketVectors or SocketColors.\nType conversion is implicit."},
    'a ** b': {
                'name':"Power.",
                'desc':"Raise SocketFloats, SocketInts, SocketBools, SocketVector\nType conversion is implicit."},
    'a // b': {
                'name':"FloorDiv.",
                'desc':"Do a FloorDiv operation between SocketFloats, SocketInts, SocketBools, SocketVectors.\nType conversion is implicit."},
    'a % b': {
                'name':"Modulo.",
                'desc':"Do a Modulo operation between SocketFloats, SocketInts, SocketBools, and entry-wise SocketVectors.\nType conversion is implicit."},
    'a == b': {
                'name':"Equal.",
                'desc':"Compare if A and B are equals.\n\nPlease note that chaining comparison is not supported ex: 'a == b == c'.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    'a != b': {
                'name':"Not Equal.",
                'desc':"Compare if A and B are not equals.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    'a > b': {
                'name':"Greater.",
                'desc':"Compare if A is greater than B.\n\nPlease note that chaining comparison is not supported ex: 'a > b > c'.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    'a >= b': {
                'name':"Greater or Equal.",
                'desc':"Compare if A is greater or equal than B.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    'a < b': {
                'name':"Lesser.",
                'desc':"Compare if A is lesser than B.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    'a <= b': {
                'name':"Lesser or Equal.",
                'desc':"Compare if A is lesser or equal than B.\n\nSupports SocketFloats, SocketInts, SocketBools, SocketVectors, SocketColors.\nWill return a SocketBool."},
    '-a': {
                'name':"Negate.",
                'desc':"Negate using the 'a = -a' notation.\n\nSupports SocketFloats, SocketInts, SocketVectors, SocketBool."},
    'abs(a)': {
                'name':"Absolute.",
                'desc':"Get the absolute value of a SocketFloat, SocketInt, SocketVector or SocketColor."},
    'round(a)': {
                'name':"Round.",
                'desc':"Round a SocketFloat or entry-wise SocketVector and SocketColor.\n\nex: 1.49 will become 1\n1.51 will become 2."},
    'bX & bY': {
                'name':"Bitwise And.",
                'desc':"Boolean math 'and' operation between two SocketBool or python bool types.\nWill return a SocketBool."},
    'bX | bY': {
                'name':"Bitwise Or.",
                'desc':"Boolean math 'or' operation between two SocketBool or python bool types.\nWill return a SocketBool."},
    'vA.x': {
                'name':"Vector X.",
                'desc':"Get or Assign a SocketFloat value from the X axis of a SocketVector.\n\nIs equivalent to the 'vA[0]' notation."},
    'vA.y': {
                'name':"Vector Y.",
                'desc':"Get or Assign a SocketFloat value from the Y axis of a SocketVector.\n\nIs equivalent to the 'vA[1]' notation."},
    'vA.z': {
                'name':"Vector Z.",
                'desc':"Get or Assign a SocketFloat value from the Z axis of a SocketVector.\n\nIs equivalent to the 'vA[2]' notation."},
    'vA.xyz': {
                'name':"Vector XYZ tuple.",
                'desc':"Get or Assign a tuple of 3 SocketFloat values from the corresponding XYZ axes of a SocketVector.\n\nIs equivalent to the 'vA[:]' notation."},
    'vA.length': {
                'name':"Vector Length.",
                'desc':"Return a SocketFloat value corresponding to the length of SocketVector.\n\nIs a read-only property."},
    'vA.normalized()': {
                'name':"Vector Noralization.",
                'desc':"Return a normalized SocketVector."},
    'vA.to_color()': {
                'name':"Vector to Color.",
                'desc':"Return a RGBAColor from a VectorXYZ."},
    'vA.to_quaternion()': {
                'name':"Euler to Quaternion.",
                'desc':"Return a SocketRotation from an SocketVector Euler angle."},
    'qA.w': {
                'name':"Quaternion W.",
                'desc':"Get or Assign a SocketRotation W axis.\n\nIs equivalent to the 'qA[0]' notation."},
    'qA.x': {
                'name':"Quaternion X.",
                'desc':"Get or Assign a SocketRotation X axis.\n\nIs equivalent to the 'qA[1]' notation."},
    'qA.y': {
                'name':"Quaternion Y.",
                'desc':"Get or Assign a SocketRotation Y axis.\n\nIs equivalent to the 'qA[2]' notation."},
    'qA.z': {
                'name':"Quaternion Z.",
                'desc':"Get or Assign a SocketRotation Z axis.\n\nIs equivalent to the 'qA[3]' notation."},
    'qA.wxyz': {
                'name':"Quaternion WXYZ tuple.",
                'desc':"Get or Assign a tuple of 4 SocketFloat values from the corresponding WXYZ axes of a SocketRotation.\n\nIs equivalent to the 'qA[:]' notation."},
    'qA.axis': {
                'name':"Quaternion Rotation Axis.",
                'desc':"Get or Assign a SocketVector Axis componement of a Rotation Quaternion."},
    'qA.angle': {
                'name':"Quaternion Rotation Angle.",
                'desc':"Get or Assign a SocketFloat Angle componement of a Rotation Quaternion."},
    'qA.inverted()': {
                'name':"Invert Quaternion.",
                'desc':"Return the inverted quaternion."},
    'qA.to_euler()': {
                'name':"Quaternion as Euler Vector.",
                'desc':"Return the XYZ Euler Angle Vector equivalent of this quaternion."},
    'mA @ mB': {
                'name':"Matrix Multiplication.",
                'desc':"Multiply matrixes together."},
    'mA @ vB': {
                'name':"Vector Transform.",
                'desc':"Transform a vector B by a given matrix A.\nWill return a VectorSocket.\n\nAlternative notation to 'mA.transform_point(vB)'"},
    'mA.translation': {
                'name':"Matrix Translation.",
                'desc':"Get or Assign a SocketVector Translation componement of a Transform Matrix."},
    'mA.rotation': {
                'name':"Matrix Rotation.",
                'desc':"Get or Assign a SocketRotation Quaternion componement of a Transform Matrix."},
    'mA.scale': {
                'name':"Matrix Scale.",
                'desc':"Get or Assign a SocketVector Scale componement of a Transform Matrix."},
    'mA.is_invertible': {
                'name':"Matrix is Invertible.",
                'desc':"Return the SocketBool status if the matrix is indeed invertible.\n\nIs a read-only property."},
    'mA.determinant()': {
                'name':"Matrix Determinant.",
                'desc':"Return the SocketFloat determinant of the matrix."},
    'mA.transposed()': {
                'name':"Transpose Matrix.",
                'desc':"Return the transposed matrix."},
    'mA.inverted()': {
                'name':"Invert Matrix.",
                'desc':"Return the inverted matrix."},
    'mA[1][2]': {
                'name':"Matrix Itterable Notation",
                'desc':"You are able to navigate a 4x4 matrix rows of quaternions.\nmA[0] will get you the first Quaternion row member of the Matrix.\nmA[4][0] will get you the first element of the last Quaternion row.\nmA[0] = (1,2,3,4) will replace the first row by a new one.\nmA[4,4] = 0 will replace the last element of the last row Quaternion."},
    'Col.r': {
                'name':"Color Red Channel.",
                'desc':"Get or Assign a SocketColor R value.\n\nIs equivalent to the 'Col[0]' notation."},
    'Col.g': {
                'name':"Color Green Channel.",
                'desc':"Get or Assign a SocketColor G value.\n\nIs equivalent to the 'Col[1]' notation."},
    'Col.b': {
                'name':"Color Blue Channel.",
                'desc':"Get or Assign a SocketColor B value.\n\nIs equivalent to the 'Col[2]' notation."},
    'Col.rgb': {
                'name':"Color RGB tuple.",
                'desc':"Get or Assign a tuple of 3 SocketFloat values from the corresponding RGB channels of a SocketColor.\nAccepts Assigning a SocketVector or Vector as XYZ to RGB values as well.\n\nIs equivalent to the 'Col[:]' notation."},
    'Col.h': {
                'name':"Color Hue Channel.",
                'desc':"Get or Assign a SocketColor H value."},
    'Col.s': {
                'name':"Color Saturation Channel.",
                'desc':"Get or Assign a SocketColor S value."},
    'Col.v': {
                'name':"Color Value Channel.",
                'desc':"Get or Assign a SocketColor V value."},
    'Col.hsv': {
                'name':"Color HSV tuple.",
                'desc':"Get or Assign a tuple of 3 SocketFloat values from the corresponding HSV channels of a SocketColor.\nAccepts Assigning a SocketVector or Vector as XYZ to HSV values as well."},
    'Col.l': {
                'name':"Color Lightness Channel.",
                'desc':"Get or Assign a SocketColor L value."},
    'Col.hsl': {
                'name':"Color HSL tuple.",
                'desc':"Get or Assign a tuple of 3 SocketFloat values from the corresponding HSL channels of a SocketColor.\nAccepts Assigning a SocketVector or Vector as XYZ to HSL values as well."},
    'Col.a': {
                'name':"Color Alpha Channel.",
                'desc':"Get or Assign a SocketColor A value.\n\nIs equivalent to the 'Col[3]' notation."},
    'Col.to_vector()': {
                'name':"Color to Vector.",
                'desc':"Return a VectorXYZ from a RGBAColor."},
    }


def transform_nex_script(original_text:str, nextypes:list) -> str:
    """
    Transforms a Nex script:
    - Remove comments
    - Replace with custom Nex type declarations 
        "VAR : TYPE = RESTOFTHELINE" → "VAR = TYPE('VAR', RESTOFTHELINE)"
        "VAR : TYPE"                 → "VAR = TYPE('VAR', None)"
    """

    #TODO support ';' python notation?

    def replacer(match):
        varname = match.group(1)
        typename = match.group(2)
        rest = match.group(3)
        if (rest is None or rest.strip() == ''):
              return f"{varname} = {typename}('{varname}', None)"
        else: return f"{varname} = {typename}('{varname}', {rest.strip()})"

    pattern = re.compile(rf"\b(\w+)\s*:\s*({'|'.join(nextypes)})\s*(?:=\s*(.+))?")

    lines = []
    for line in original_text.splitlines():

        # Remove comments: delete anything from a '#' to the end of the line.
        line = re.sub(r'#.*', '', line)

        #transform type hinting notation
        line = pattern.sub(replacer, line)

        lines.append(line)
        continue

    return '\n'.join(lines)

# ooooo      ooo                 .o8            
# `888b.     `8'                "888            
#  8 `88b.    8   .ooooo.   .oooo888   .ooooo.  
#  8   `88b.  8  d88' `88b d88' `888  d88' `88b 
#  8     `88b.8  888   888 888   888  888ooo888 
#  8       `888  888   888 888   888  888    .o 
# o8o        `8  `Y8bod8P' `Y8bod88P" `Y8bod8P' 
                                              
class Base():

    bl_idname = "NodeBoosterPyNexScript"
    bl_label = "Python Nex Script"
    bl_description = """Executes a Python script containing 'Nex' language. 'Nex' stands for nodal expression.\
    With Nex, you can efficiently and easily interpret python code into Geometry-Node nodal programming.
    • Create a new text-data and initiate Nex input and output using `a:infloat` or `z:outfloat = a` for example.
    • These created input variables are SocketTypes, do math, write code with them, then assign their values to an output.
    • An example of NexCode is available in your text editor template panel."""
    auto_upd_flags = {'FRAME_PRE','DEPS_POST','AUTORIZATION_REQUIRED',}
    tree_type = "*ChildrenDefined*"
    # bl_icon = 'SCRIPT'

    error_message : bpy.props.StringProperty(
        description="User interface error message",
        )
    debug_evaluation_counter : bpy.props.IntProperty(
        name="Execution Counter",
        default=0,
        )
    debug_nodes_quantity : bpy.props.IntProperty(
        name="Number of nodes in the nodetree",
        default=-1,
        )
    user_textdata : bpy.props.PointerProperty(
        type=bpy.types.Text,
        name="TextData",
        description="Blender Text datablock to execute",
        poll=lambda self, data: not data.name.startswith('.'),
        update=lambda self, context: self.interpret_nex_script(rebuild=True) if (self.user_textdata is None) else None,
        )
    execute_script : bpy.props.BoolProperty(
        name="Execute",
        description="Click here to execute the Nex script & re-building the generated node-tree",
        update=lambda self, context: self.interpret_nex_script(rebuild=True),
        )
    execute_at_depsgraph : bpy.props.BoolProperty(
        name="Automatically Refresh",
        description="Synchronize the interpreted python constants (if any) with the outputs values on each depsgraph frame and interaction. By toggling this option, your Nex script will be executed constantly on each interaction you have with blender (note that the internal nodetree will not be constantly rebuilt, press the Play button to do so.).",
        default=False,
        )

    def init(self, context):
        """Called when the node is first added."""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                tree_type=self.tree_type,
                out_sockets={"Error" : "NodeSocketBool",},
                )

        ng = ng.copy() #always using a copy of the original ng
        self.node_tree = ng

        self.width = 185

        return None

    def copy(self,node,):
        """fct run when dupplicating the node"""

        #NOTE: copy/paste can cause crashes, we use a timer to delay the action
        def delayed_copy():
            self.node_tree = node.node_tree.copy()
        bpy.app.timers.register(delayed_copy, first_interval=0.01)

        return None 

    def update(self):
        """generic update function"""

        cache_booster_nodes_parent_tree(self.id_data)

        return None

    def cleanse_sockets(self, in_protectednames=None, out_protectednames=None,):
        """remove all our sockets except error socket
        optional: except give list of names"""

        ng = self.node_tree
        assert ng is not None, "cleanse_sockets(): 'self.node_tree' must'nt be None"
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]

        for mode in ('INPUT','OUTPUT'):
            sockets = in_nod.outputs if (mode=='INPUT') else out_nod.inputs
            protected = in_protectednames if (mode=='INPUT') else out_protectednames

            idx_to_del = []
            for idx,socket in enumerate(sockets):

                #skip custom sockets
                if (socket.type=='CUSTOM'):
                    continue

                #skip error socket, is the first output..
                if (mode=='OUTPUT' and idx==0):
                    continue

                #deletion by name? if passed
                if (protected):
                    if (socket.name not in protected):
                        idx_to_del.append(idx)
                    continue

                idx_to_del.append(idx)

                #protection is only valid once, we do remove doubles
                if (protected):
                    protected.remove(socket.name)

                continue

            for idx in reversed(idx_to_del):
                remove_ng_socket(ng, idx, in_out=mode,)

        return None

    def cleanse_nodes(self):
        """remove any added nodes in the nodetree"""

        ng = self.node_tree
        assert ng is not None, "cleanse_nodes(): 'self.node_tree' must'nt be None"

        for node in list(ng.nodes).copy():
            if (node.name not in {"Group Input", "Group Output", "ScriptStorage",}):
                ng.nodes.remove(node)

        #move output near to input again..
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]
        out_nod.location = in_nod.location
        out_nod.location.x += 200

        self.debug_nodes_quantity = -1
        return None

    def store_text_data_as_frame(self, text):
        """we store the user text data as a frame"""

        ng = self.node_tree

        frame = ng.nodes.get("ScriptStorage")
        if (frame is None):
            frame = ng.nodes.new('NodeFrame')
            frame.name = frame.label = "ScriptStorage"
            frame.width = 500
            frame.height = 1500
            frame.location.x = -750
            frame.label_size = 8

        if (frame.text!=text):
            frame.text = text

        return None

    def cross_compatibility_checks(self, user_script):
        """check for types"""

        ng = self.node_tree

        KEYWORD_UNAVAILABILITY_MAP = {
            'GEOMETRY':    (),
            'SHADER':      ('inquat', 'inmat',),
            'COMPOSITING': ('inquat', 'inmat',),
            }

        for kw in KEYWORD_UNAVAILABILITY_MAP[ng.type]:
            if (kw in user_script):
                return f"Keyword '{kw}' not available for the {ng.type.title()} editor."

        return None

    def interpret_nex_script(self, rebuild=False):
        """Execute the Python script from a Blender Text datablock, capture local variables whose names start with "out_",
        and update the node group's output sockets accordingly."""

        ng = self.node_tree
        assert ng is not None, "interpret_nex_script(): 'self.node_tree' must'nt be None"
        in_nod, out_nod = ng.nodes["Group Input"], ng.nodes["Group Output"]
        self.debug_evaluation_counter += 1 # potential issue with int limit here? idk how blender handle this
        self.error_message = ''

        #we reset the Error status back to false
        set_ng_socket_label(ng,0, label="NoErrors",)
        set_ng_socket_defvalue(ng,0, value=False,)
        self.error_message = ''

        #Keepsafe the text data as extra user
        self.store_text_data_as_frame(self.user_textdata)

        # Check if a Blender Text datablock has been specified
        if (self.user_textdata is None):
            #cleanse all sockets and nodes then
            self.cleanse_sockets()
            self.cleanse_nodes()
            # set error to True
            set_ng_socket_label(ng,0, label="EmptyTextError",)
            set_ng_socket_defvalue(ng,0, value=True,)
            return None

        user_script = self.user_textdata.as_string()

        #check if the user script is correct for his editor type. perhaps his using some unavailable keywords..
        err = self.cross_compatibility_checks(user_script)
        if (err):
            #cleanse all sockets and nodes then
            self.cleanse_sockets()
            self.cleanse_nodes()
            # Display error
            self.error_message = err
            # set error to True
            set_ng_socket_label(ng,0, label="AvailabilityError",)
            set_ng_socket_defvalue(ng,0, value=True,)
            return None

        #capture the inputs/outputs later on execution.

        #define all possible Nex types & functions the user can toy with
        all_inputs_names = [] #capture on Nextype initalization.
        all_outputs_names = []
        function_call_history = [] #we need a function call history defined here for a stable nodetree on multiple execution.
        nextoys = NexFactory(self, all_inputs_names, all_outputs_names, function_call_history,)

        # Synthax:
        # replace varname:infloat=REST with varname=infloat('varname',REST) & remove comments
        # much better workflow for artists to use python type indications IMO
        final_script = transform_nex_script(user_script, nextoys['nexusertypes'].keys(),)

        #did the user changes stuff in the script?
        cached_script = ''
        cache_name = f".boostercache.{self.user_textdata.name}"
        cache_text = bpy.data.texts.get(cache_name)
        if (cache_text is not None):
              cached_script = cache_text.as_string()
        is_dirty = (final_script!=cached_script)

        # If user modified the script, the script will need a rebuild.
        if (is_dirty or rebuild):
            #Clean up nodes.. we'll rebuild the nodetree
            self.cleanse_nodes()
            # We set the first node active (node arrangement in nodesetter.py module is based on active)
            ng.nodes.active = in_nod
            #when initalizing the NexTypes, the inputs/outputs sockets will be created.

        # Namespace, we inject Nex types in user namespace
        exec_namespace = {}
        exec_namespace.update(nextoys['nexusertypes'])
        exec_namespace.update(nextoys['nexuserfunctions'])
        script_vars = {} #catch variables from exec?

        #Don't want all the pretty user error wrapping for user? set it to True
        if False:
            compiled_script = compile(
                source=final_script,
                filename=self.user_textdata.name,
                mode="exec",
                )
            exec(compiled_script, exec_namespace, script_vars)
        else:
            try:
                compiled_script = compile(
                    source=final_script,
                    filename=self.user_textdata.name,
                    mode="exec",
                    )
                exec(compiled_script, exec_namespace, script_vars)

            except SyntaxError as e:
                #print more information in console
                full, short = prettyError(e)
                print(full)
                # set error to True
                set_ng_socket_label(ng,0, label="SynthaxError",)
                set_ng_socket_defvalue(ng,0, value=True,)
                # Display error
                self.error_message =  short
                # Cleanse nodes, there was an error anyway, the current nodetree is tainted..
                self.cleanse_nodes()
                return None

            except NexError as e:
                #print more information in console
                full, short = prettyError(e, userfilename=self.user_textdata.name,)
                print(full)
                # set error to True
                set_ng_socket_label(ng,0, label="NexError",)
                set_ng_socket_defvalue(ng,0, value=True,)
                # Display error
                self.error_message = short
                # Cleanse nodes, there was an error anyway, the current nodetree is tainted..
                self.cleanse_nodes()
                return None

            except Exception as e:
                #print more information in console
                full, short = prettyError(e, userfilename=self.user_textdata.name,)
                print(full)
                #print more information
                print("Full Traceback Error:")
                traceback.print_exc()
                # set error to True
                set_ng_socket_label(ng,0, label="PythonError",)
                set_ng_socket_defvalue(ng,0, value=True,)
                # Display error
                self.error_message = short
                return None

        #check on vars..
        #make sure there are Nex types in the user expression
        if len(all_inputs_names + all_outputs_names)==0:
            #cleanse all sockets and nodes then
            self.cleanse_sockets()
            self.cleanse_nodes()
            # set error to True
            set_ng_socket_label(ng,0, label="VoidNexError",)
            set_ng_socket_defvalue(ng,0, value=True,)
            # Display error
            self.error_message = f"No Nex Found in Script. An example of NexScript can be found in 'Text Editor > Template > Booster Scripts'"
            return None
        #also make sure there are Nex outputs types in there..
        if len(all_outputs_names)==0:
            # set error to True
            set_ng_socket_label(ng,0, label="NoOutputError",)
            set_ng_socket_defvalue(ng,0, value=True,)
            # Display error
            self.error_message = f"Mandatory Outputs not Found. An example of NexScript can be found in 'Text Editor > Template > Booster Scripts'"
            return None
                
        # Clean up leftover sockets from previous run which created sockets no longer in use
        self.cleanse_sockets(
            in_protectednames=all_inputs_names,
            out_protectednames=all_outputs_names,
            )

        #we cache the script it correspond to current nodetree arrangements, keep track of modifications
        if (cache_text is None):
            cache_text = bpy.data.texts.new(cache_name)
        if (is_dirty):
            cache_text.clear()
            cache_text.write(final_script)

        #we count the number of nodes
        self.debug_nodes_quantity = len(ng.nodes)

        #Clean up the nodetree spacing a little, for the output node
        if (is_dirty or rebuild):
            farest = get_farest_node(ng)
            if (farest!=out_nod):
                out_nod.location.x = farest.location.x + 250

        return None
    
    def free(self):
        """when user delete the node we need to clean up"""

        self.user_textdata = None

        return None

    def draw_label(self,):
        """node label"""
        if (self.label==''):
            return 'Nex Script'
        return self.label

    def draw_buttons(self, context, layout,):
        """node interface drawing"""

        sett_win = context.window_manager.nodebooster
        is_error = bool(self.error_message)
        animated_icon = f"W_TIME_{self.debug_evaluation_counter%8}"

        layout.separator(factor=0.25)
            
        col = layout.column(align=True)
        row = col.row(align=True)
        
        field = row.row(align=True)
        field.alert = is_error
        field.prop(self, "user_textdata", text="", icon="TEXT", placeholder="NexScript.py",)

        prop = row.row(align=True)
        prop.enabled = sett_win.authorize_automatic_execution
        prop.prop(self, "execute_at_depsgraph", text="", icon_value=cust_icon(animated_icon),)

        row.prop(self, "execute_script", text="", icon="PLAY", invert_checkbox=self.execute_script,)

        if (not sett_win.authorize_automatic_execution):
            col.separator(factor=0.75)
            col.prop(sett_win,"authorize_automatic_execution")

        if (is_error):
            col = col.column(align=True)
            col.separator(factor=2)
            word_wrap(layout=col, alert=True, active=True, max_char=self.width/5.75, string=self.error_message,)

            #TODO remove when all nex domain functions are verified and covered
            if (self.tree_type in {'ShaderNodeTree','CompositorNodeTree'}):
                col = layout.column(align=True).box()
                word_wrap(layout=col, alert=False, active=True, max_char=self.width/6.5,
                    string=f"Warning NexScript does not fully support the {self.tree_type.replace('NodeTree','')} editor yet.",)

        layout.separator(factor=0.5)

        return None

    def draw_panel(self, layout, context):
        """draw in the nodebooster N panel 'Active Node'"""
    
        n = self
        sett_win = context.window_manager.nodebooster

        header, panel = layout.panel("params_panelid", default_closed=False,)
        header.label(text="Parameters",)
        if (panel):

            is_error = bool(n.error_message)
            col = panel.column(align=True)
            row = col.row(align=True)
            field = row.row(align=True)
            field.alert = is_error
            field.prop(n, "user_textdata", text="", icon="TEXT", placeholder="NexScript.py",)
            row.prop(n, "execute_script", text="", icon="PLAY", invert_checkbox=n.execute_script,)

            if (is_error):
                lbl = col.row()
                lbl.alert = is_error
                lbl.label(text=n.error_message)

            panel.prop(sett_win,"authorize_automatic_execution")
            
            prop = panel.column()
            prop.enabled = sett_win.authorize_automatic_execution
            prop.prop(n,"execute_at_depsgraph")

        header, panel = layout.panel("inputs_panelid", default_closed=True,)
        header.label(text="Inputs",)
        if (panel):
            
            col = panel.column()
            col.use_property_split = True
            col.use_property_decorate = True
            
            if n.inputs:
                for s in n.inputs:
                    row = col.row()
                    row.active = not any(s.links)
                    if hasattr(s,'default_value'):
                        row.prop(s,'default_value', text=s.name,)
                    else:
                        row.prop(s,'type', text=s.name,)
            else:
                col.label(text="No Input Created")

        header, panel = layout.panel("doc_panelid", default_closed=True,)
        header.label(text="Documentation",)
        if (panel):
            word_wrap(layout=panel, alert=False, active=True, max_char='auto',
                char_auto_sidepadding=0.9, context=context, string=n.bl_description,
                )
            panel.operator("wm.url_open", text="Documentation",).url = "https://blenderartists.org/t/node-booster-extending-blender-node-editors"

        header, panel = layout.panel("doc_glossid", default_closed=True,)
        header.label(text="Glossary",)
        if (panel):

            col = panel.column()

            for symbol,v in NEXNOTATIONDOC.items():

                desc = v['name']+'\n'+v['desc'] if v['desc'] else v['name']
                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=symbol,)

                col.separator(factor=0.5)

                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=desc, alignment='LEFT',
                    )
                col.separator()

            for fname,fdoc in NEXFUNCDOC.items():

                row = col.row()
                row.scale_y = 0.65
                row.box().label(text=fdoc['repr'],)

                col.separator(factor=0.5)

                word_wrap(layout=col, alert=False, active=True, max_char='auto',
                    char_auto_sidepadding=0.95, context=context, string=fdoc['doc'], alignment='LEFT',
                    )
                col.separator()
                
        header, panel = layout.panel("dev_panelid", default_closed=True,)
        header.label(text="Development",)
        if (panel):
            panel.active = False
                            
            col = panel.column(align=True)
            col.label(text="NodeTree:")
            col.template_ID(n, "node_tree")

            col = panel.column(align=True)
            col.label(text="NodesCreated:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_nodes_quantity", text="",)

            col = panel.column(align=True)
            col.label(text="Execution Count:")
            row = col.row()
            row.enabled = False
            row.prop(n, "debug_evaluation_counter", text="",)

        col = layout.column(align=True)
        op = col.operator("extranode.bake_customnode", text="Convert to Group",)
        op.nodegroup_name = n.node_tree.name
        op.node_name = n.name

        return None

    @classmethod
    def update_all(cls, using_nodes=None, signal_from_handlers=False,):
        """search for all node instances of this type and refresh them. Will be called automatically if .auto_upd_flags's are defined"""

        if (using_nodes is None):
              nodes = get_booster_nodes(by_idnames={cls.bl_idname},)
        else: nodes = [n for n in using_nodes if (n.bl_idname==cls.bl_idname)]

        for n in nodes:
            if (signal_from_handlers and not n.execute_at_depsgraph):
                continue
            if (n.mute):
                continue
            n.interpret_nex_script()
            continue

        return None

#Per Node-Editor Children:
#Respect _NG_ + _GN_/_SH_/_CP_ nomenclature

class NODEBOOSTER_NG_GN_PyNexScript(Base, bpy.types.GeometryNodeCustomGroup):
    tree_type = "GeometryNodeTree"
    bl_idname = "GeometryNode" + Base.bl_idname

class NODEBOOSTER_NG_SH_PyNexScript(Base, bpy.types.ShaderNodeCustomGroup):
    tree_type = "ShaderNodeTree"
    bl_idname = "ShaderNode" + Base.bl_idname

class NODEBOOSTER_NG_CP_PyNexScript(Base, bpy.types.CompositorNodeCustomGroup):
    tree_type = "CompositorNodeTree"
    bl_idname = "CompositorNode" + Base.bl_idname

