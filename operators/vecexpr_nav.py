import bpy

class NODEBOOSTER_OT_vec_expr_nav(bpy.types.Operator):
    """Cycle through Vector Expression fields"""
    bl_idname = "nodebooster.vec_expr_nav"
    bl_label = "Cycle Vector Expression"
    bl_options = {'INTERNAL'}

    direction: bpy.props.EnumProperty(
        items=[('NEXT', 'Next', ''), ('PREV', 'Previous', ''), ('CONFIRM', 'Confirm', '')],
        default='NEXT'
    )

    def execute(self, context):
        node = context.active_node
        if not node or node.bl_idname != 'NodeBoosterVecExpression':
            return {'CANCELLED'}

        idx = getattr(node, 'active_field', 0)
        if self.direction == 'NEXT':
            idx = (idx + 1) % 3
        elif self.direction == 'PREV':
            idx = (idx - 1) % 3
        else:
            context.area.header_text_set(None)
            return {'FINISHED'}

        node.active_field = idx
        try:
            bpy.ops.ui.focus_set(index=idx)
        except Exception:
            pass
        return {'FINISHED'}

def register():
    bpy.utils.register_class(NODEBOOSTER_OT_vec_expr_nav)

def unregister():
    bpy.utils.unregister_class(NODEBOOSTER_OT_vec_expr_nav)
