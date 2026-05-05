# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN (Dorian B.)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy


def _copy_socket_default(from_socket, to_socket):
    if (not hasattr(from_socket, "default_value")) or (not hasattr(to_socket, "default_value")):
        return None

    value = from_socket.default_value
    try:
        if hasattr(value, "__len__") and (type(value) is not str):
            to_socket.default_value = value[:]
        else:
            to_socket.default_value = value
    except Exception:
        pass

    return None


def _move_input_links(tree, from_socket, to_socket):
    for link in list(from_socket.links):
        tree.links.new(link.from_socket, to_socket)
        tree.links.remove(link)
    return None


def _move_output_links(tree, from_socket, to_socket):
    targets = [link.to_socket for link in from_socket.links]
    for link in list(from_socket.links):
        tree.links.remove(link)
    for target_socket in targets:
        tree.links.new(to_socket, target_socket)
    return None


def _new_socket(node_tree, name, in_out, socket_type):
    return node_tree.interface.new_socket(name,
        in_out=in_out,
        socket_type=socket_type,
        )


def _make_exact_match(node_tree, string_socket, item_name, location):
    """Return a bool socket for string_socket == item_name."""

    match = node_tree.nodes.new("FunctionNodeMatchString")
    match.location = location
    match.inputs["Operation"].default_value = "Starts With"
    match.inputs["Key"].default_value = item_name
    node_tree.links.new(string_socket, match.inputs["String"])

    length = node_tree.nodes.new("FunctionNodeStringLength")
    length.location = (location[0], location[1] - 110)
    node_tree.links.new(string_socket, length.inputs["String"])

    compare = node_tree.nodes.new("FunctionNodeCompare")
    compare.location = (location[0] + 210, location[1] - 60)
    compare.data_type = "INT"
    compare.operation = "EQUAL"
    compare.inputs[3].default_value = len(item_name)
    node_tree.links.new(length.outputs["Length"], compare.inputs[2])

    both = node_tree.nodes.new("FunctionNodeBooleanMath")
    both.location = (location[0] + 420, location[1])
    both.operation = "AND"
    node_tree.links.new(match.outputs["Result"], both.inputs[0])
    node_tree.links.new(compare.outputs["Result"], both.inputs[1])

    return both.outputs["Boolean"]


def _build_string_switch_group(source_node):
    tree_type = source_node.id_data.bl_idname
    data_type = source_node.data_type
    items = [item.name for item in source_node.enum_definition.enum_items]

    if (len(items) < 1):
        raise ValueError("Menu Switch has no menu items.")

    value_input_type = source_node.inputs[1].bl_idname
    value_output_type = source_node.outputs[0].bl_idname

    group_name = f".String Switch - {source_node.name}"
    node_tree = bpy.data.node_groups.new(group_name, tree_type)

    _new_socket(node_tree, "String", "INPUT", "NodeSocketString")
    for item_name in items:
        _new_socket(node_tree, item_name, "INPUT", value_input_type)

    _new_socket(node_tree, source_node.outputs[0].name, "OUTPUT", value_output_type)
    for item_name in items:
        _new_socket(node_tree, item_name, "OUTPUT", "NodeSocketBool")

    group_input = node_tree.nodes.new("NodeGroupInput")
    group_input.location = (-900, 0)
    group_output = node_tree.nodes.new("NodeGroupOutput")
    group_output.location = (700, 0)

    index_switch = node_tree.nodes.new("GeometryNodeIndexSwitch")
    index_switch.location = (380, 120)
    index_switch.data_type = data_type

    for _ in range(max(0, len(items) - 2)):
        index_switch.index_switch_items.new()

    for idx, _item_name in enumerate(items):
        node_tree.links.new(group_input.outputs[idx + 1], index_switch.inputs[idx + 1])

    node_tree.links.new(index_switch.outputs["Output"], group_output.inputs[0])

    index_socket = None
    for idx, item_name in enumerate(items):
        match_socket = _make_exact_match(node_tree,
            group_input.outputs["String"],
            item_name,
            (-650, -idx * 260),
            )
        node_tree.links.new(match_socket, group_output.inputs[idx + 1])

        if (idx == 0):
            continue

        switch = node_tree.nodes.new("GeometryNodeSwitch")
        switch.location = (90, -idx * 260)
        switch.input_type = "INT"
        node_tree.links.new(match_socket, switch.inputs["Switch"])
        if (index_socket is not None):
            node_tree.links.new(index_socket, switch.inputs["False"])
        switch.inputs["True"].default_value = idx
        index_socket = switch.outputs["Output"]

    if (index_socket is not None):
        node_tree.links.new(index_socket, index_switch.inputs["Index"])

    return node_tree


def _convert_menu_switch_node(tree, source_node):
    if source_node.inputs[0].links:
        raise ValueError("Linked Menu input cannot be converted to a String input automatically.")

    node_tree = _build_string_switch_group(source_node)

    group_node = tree.nodes.new("GeometryNodeGroup")
    group_node.node_tree = node_tree
    group_node.name = f"{source_node.name} String"
    group_node.label = source_node.label or "String Switch"
    group_node.location = source_node.location.copy()
    group_node.width = source_node.width

    if hasattr(group_node.inputs[0], "default_value"):
        group_node.inputs[0].default_value = source_node.inputs[0].default_value

    for idx in range(1, min(len(group_node.inputs), len(source_node.inputs))):
        _copy_socket_default(source_node.inputs[idx], group_node.inputs[idx])
        _move_input_links(tree, source_node.inputs[idx], group_node.inputs[idx])

    for idx in range(min(len(source_node.outputs), len(group_node.outputs))):
        _move_output_links(tree, source_node.outputs[idx], group_node.outputs[idx])

    group_node.select = source_node.select
    tree.nodes.active = group_node
    tree.nodes.remove(source_node)

    return group_node


class NODEBOOSTER_OT_convert_menu_switch_to_string_switch(bpy.types.Operator):
    bl_idname = "nodebooster.convert_menu_switch_to_string_switch"
    bl_label = "Convert to String Switch"
    bl_description = "Convert a Menu Switch node into a string-driven switch node group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        node = getattr(context, "active_node", None)
        tree = getattr(context.space_data, "edit_tree", None) if context.space_data else None
        return bool(tree and node and node.bl_idname == "GeometryNodeMenuSwitch")

    def execute(self, context):
        tree = context.space_data.edit_tree
        source_node = context.active_node

        try:
            _convert_menu_switch_node(tree, source_node)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        return {'FINISHED'}


def draw_string_switch_context_menu(self, context):
    node = getattr(context, "active_node", None)
    if (node is None) or (node.bl_idname != "GeometryNodeMenuSwitch"):
        return None

    self.layout.separator()
    self.layout.operator(NODEBOOSTER_OT_convert_menu_switch_to_string_switch.bl_idname,
        icon='NODETREE',
        )
    return None
