bl_info = {
    "name": "Shape Key Transfer",
    "author": "r2detta",
    "version": (1, 2),
    "blender": (4, 3, 0),
    "location": "Object Properties > Shape Key Transfer",
    "description": "Transfer shape keys between objects with flexible options",
    "warning": "",
    "wiki_url": "",
    "category": "Mesh",
}

import bpy
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import PointerProperty, StringProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty

# ------------------------------
# Property Group
# ------------------------------
class ShapeKeyTransferProperties(PropertyGroup):
    def update_enabled(self, context):
        """Called when enabled property is changed"""
        if not self.enabled:
            # Clear all properties when disabled
            self.source_object = None
            self.transfer_mode = 'FULL'
            self.auto_transfer = False
            self.only_selected_vertices = False
    
    # Enable/Disable the addon for this object
    enabled: BoolProperty(
        name="Enable Shape Key Transfer",
        description="Enable Shape Key Transfer for this object",
        default=False,
        update=update_enabled
    )
    
    # Source object to get shape keys from
    source_object: PointerProperty(
        name="Source Object",
        description="Object to get shape keys from",
        type=bpy.types.Object,
    )
    
    # Transfer mode
    transfer_mode: EnumProperty(
        name="Transfer Mode",
        description="Choose what to transfer",
        items=[
            ('FULL', "Full Transfer", "Transfer complete shape key data (requires same vertex count)"),
            ('NAMES_ONLY', "Names Only", "Transfer only shape key names and values (creates empty shape keys)")
        ],
        default='FULL'
    )
    
    # Automatically transfer all shape keys
    auto_transfer: BoolProperty(
        name="Auto Transfer All",
        description="Automatically transfer all shape keys from source to target",
        default=False
    )
    
    # Only transfer selected vertices
    only_selected_vertices: BoolProperty(
        name="Only Selected Vertices",
        description="Transfer shape key data only for selected vertices in source object",
        default=False
    )

# ------------------------------
# Shape Key Item
# ------------------------------
class ShapeKeyItem(PropertyGroup):
    name: StringProperty(
        name="Name", 
        description="Shape key name", 
        default=""
    )
    
    is_selected: BoolProperty(
        name="Transfer",
        description="Select to transfer this shape key",
        default=True
    )

# ------------------------------
# Operators
# ------------------------------
class OBJECT_OT_TransferShapeKey(Operator):
    bl_idname = "object.transfer_shape_key"
    bl_label = "Transfer Shape Key"
    bl_description = "Transfer the selected shape key from source to target"
    bl_options = {'REGISTER', 'UNDO'}
    
    shape_key_name: StringProperty(
        name="Shape Key",
        description="Shape key to transfer",
        default=""
    )
    
    @classmethod
    def poll(cls, context):
        # Check if the active object is a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if shape key transfer is enabled for this object
        props = context.active_object.shape_key_transfer_props
        if not props.enabled:
            return False
        
        # Check if source object is set and has shape keys
        if not props.source_object or props.source_object.type != 'MESH':
            return False
        
        if not props.source_object.data.shape_keys:
            return False
            
        return True
    
    def execute(self, context):
        props = context.active_object.shape_key_transfer_props
        source_obj = props.source_object
        target_obj = context.active_object
        
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Source or target object not set")
            return {'CANCELLED'}
        
        # Check if source has shape keys
        if not source_obj.data.shape_keys:
            self.report({'ERROR'}, "Source object has no shape keys")
            return {'CANCELLED'}
        
        # Get the shape key from source
        if self.shape_key_name not in source_obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"Shape key '{self.shape_key_name}' not found in source object")
            return {'CANCELLED'}
        
        source_key = source_obj.data.shape_keys.key_blocks[self.shape_key_name]
        
        # Ensure target has basis shape key
        if not target_obj.data.shape_keys:
            target_obj.shape_key_add(name="Basis", from_mix=False)
        
        # Check if target already has this shape key
        if self.shape_key_name in target_obj.data.shape_keys.key_blocks:
            target_key = target_obj.data.shape_keys.key_blocks[self.shape_key_name]
        else:
            # Create new shape key
            target_key = target_obj.shape_key_add(name=self.shape_key_name, from_mix=False)
        
        # Handle different transfer modes
        if props.transfer_mode == 'FULL':
            # Check vertex count for full transfer
            if len(target_obj.data.vertices) != len(source_obj.data.vertices):
                self.report({'ERROR'}, f"Vertex count mismatch: Source has {len(source_obj.data.vertices)}, Target has {len(target_obj.data.vertices)}")
                return {'CANCELLED'}
            
            # Get selected vertices if only_selected_vertices is enabled
            selected_vertices = set()
            if props.only_selected_vertices:
                # Get selected vertices from source object
                for i, vertex in enumerate(source_obj.data.vertices):
                    if vertex.select:
                        selected_vertices.add(i)
            
            # Transfer vertex data from source to target
            for i in range(len(target_obj.data.vertices)):
                # Skip if only selected vertices mode is enabled and this vertex is not selected
                if props.only_selected_vertices and i not in selected_vertices:
                    continue
                
                target_co = target_key.data[i].co
                basis_co = target_obj.data.shape_keys.key_blocks["Basis"].data[i].co
                source_co = source_key.data[i].co
                source_basis_co = source_obj.data.shape_keys.key_blocks["Basis"].data[i].co
                
                # Calculate delta from source
                delta = source_co - source_basis_co
                
                # Apply delta to target
                target_key.data[i].co = basis_co + delta
        
        elif props.transfer_mode == 'NAMES_ONLY':
            # For names only mode, we just create the shape key with the same name
            # The shape key data remains as it was created (empty/basis)
            pass
        
        # Transfer shape key value
        target_key.value = source_key.value
        
        # Update mesh
        target_obj.data.update()
        
        mode_text = "with full data" if props.transfer_mode == 'FULL' else "with name only"
        if props.transfer_mode == 'FULL' and props.only_selected_vertices:
            selected_count = len(selected_vertices)
            self.report({'INFO'}, f"Shape key '{self.shape_key_name}' transferred {mode_text} for {selected_count} selected vertices")
        else:
            self.report({'INFO'}, f"Shape key '{self.shape_key_name}' transferred {mode_text}")
        return {'FINISHED'}

class OBJECT_OT_TransferAllShapeKeys(Operator):
    bl_idname = "object.transfer_all_shape_keys"
    bl_label = "Transfer All Shape Keys"
    bl_description = "Transfer all shape keys from source to target"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Check if the active object is a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if shape key transfer is enabled for this object
        props = context.active_object.shape_key_transfer_props
        if not props.enabled:
            return False
        
        # Check if source object is set and has shape keys
        if not props.source_object or props.source_object.type != 'MESH':
            return False
        
        if not props.source_object.data.shape_keys:
            return False
            
        return True
    
    def execute(self, context):
        props = context.active_object.shape_key_transfer_props
        source_obj = props.source_object
        target_obj = context.active_object
        
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Source or target object not set")
            return {'CANCELLED'}
        
        # Check if source has shape keys
        if not source_obj.data.shape_keys:
            self.report({'ERROR'}, "Source object has no shape keys")
            return {'CANCELLED'}
        
        # Check vertex count for full transfer mode
        if props.transfer_mode == 'FULL':
            if len(target_obj.data.vertices) != len(source_obj.data.vertices):
                self.report({'ERROR'}, f"Vertex count mismatch: Source has {len(source_obj.data.vertices)}, Target has {len(target_obj.data.vertices)}")
                return {'CANCELLED'}
        
        # Ensure target has basis shape key
        if not target_obj.data.shape_keys:
            target_obj.shape_key_add(name="Basis", from_mix=False)
        
        # Transfer all shape keys except basis
        transferred = 0
        for source_key in source_obj.data.shape_keys.key_blocks:
            if source_key.name == "Basis":
                continue  # Skip Basis shape key
                
            # Check if target already has this shape key
            if source_key.name in target_obj.data.shape_keys.key_blocks:
                target_key = target_obj.data.shape_keys.key_blocks[source_key.name]
            else:
                # Create new shape key
                target_key = target_obj.shape_key_add(name=source_key.name, from_mix=False)
            
            # Handle different transfer modes
            if props.transfer_mode == 'FULL':
                # Get selected vertices if only_selected_vertices is enabled
                selected_vertices = set()
                if props.only_selected_vertices:
                    # Get selected vertices from source object
                    for i, vertex in enumerate(source_obj.data.vertices):
                        if vertex.select:
                            selected_vertices.add(i)
                
                # Transfer vertex data from source to target
                for i in range(len(target_obj.data.vertices)):
                    # Skip if only selected vertices mode is enabled and this vertex is not selected
                    if props.only_selected_vertices and i not in selected_vertices:
                        continue
                    
                    basis_co = target_obj.data.shape_keys.key_blocks["Basis"].data[i].co
                    source_co = source_key.data[i].co
                    source_basis_co = source_obj.data.shape_keys.key_blocks["Basis"].data[i].co
                    
                    # Calculate delta from source
                    delta = source_co - source_basis_co
                    
                    # Apply delta to target
                    target_key.data[i].co = basis_co + delta
            
            elif props.transfer_mode == 'NAMES_ONLY':
                # For names only mode, we just create the shape key with the same name
                # The shape key data remains as it was created (empty/basis)
                pass
            
            # Transfer shape key value
            target_key.value = source_key.value
            transferred += 1
        
        # Update mesh
        target_obj.data.update()
        
        mode_text = "with full data" if props.transfer_mode == 'FULL' else "with names only"
        if props.transfer_mode == 'FULL' and props.only_selected_vertices:
            selected_count = len(selected_vertices)
            self.report({'INFO'}, f"Transferred {transferred} shape keys {mode_text} for {selected_count} selected vertices")
        else:
            self.report({'INFO'}, f"Transferred {transferred} shape keys {mode_text}")
        return {'FINISHED'}

class OBJECT_OT_TransferDrivers(Operator):
    bl_idname = "object.transfer_drivers"
    bl_label = "Transfer Drivers"
    bl_description = "Transfer shape key drivers from source to target (only for matching shape keys)"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Check if the active object is a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if shape key transfer is enabled for this object
        props = context.active_object.shape_key_transfer_props
        if not props.enabled:
            return False
        
        # Check if source object is set and has shape keys
        if not props.source_object or props.source_object.type != 'MESH':
            return False
        
        if not props.source_object.data.shape_keys:
            return False
            
        return True
    
    def execute(self, context):
        props = context.active_object.shape_key_transfer_props
        source_obj = props.source_object
        target_obj = context.active_object
        
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Source or target object not set")
            return {'CANCELLED'}
        
        # Check if source has shape keys
        if not source_obj.data.shape_keys:
            self.report({'ERROR'}, "Source object has no shape keys")
            return {'CANCELLED'}
        
        # Check if target has shape keys
        if not target_obj.data.shape_keys:
            self.report({'ERROR'}, "Target object has no shape keys")
            return {'CANCELLED'}
        
        # Get source and target shape key names
        source_shape_keys = set()
        for key in source_obj.data.shape_keys.key_blocks:
            if key.name != "Basis":
                source_shape_keys.add(key.name)
        
        target_shape_keys = set()
        for key in target_obj.data.shape_keys.key_blocks:
            if key.name != "Basis":
                target_shape_keys.add(key.name)
        
        # Find matching shape keys
        matching_shape_keys = source_shape_keys.intersection(target_shape_keys)
        
        if not matching_shape_keys:
            self.report({'ERROR'}, "No matching shape keys found between source and target objects")
            return {'CANCELLED'}
        
        # Transfer drivers for matching shape keys
        transferred_drivers = 0
        
        for shape_key_name in matching_shape_keys:
            source_key = source_obj.data.shape_keys.key_blocks[shape_key_name]
            target_key = target_obj.data.shape_keys.key_blocks[shape_key_name]
            
            # Check if source shape key has drivers
            # In Blender, shape key drivers are accessed through the shape keys data
            source_drivers = []
            if source_obj.data.shape_keys.animation_data and source_obj.data.shape_keys.animation_data.drivers:
                for driver in source_obj.data.shape_keys.animation_data.drivers:
                    if driver.data_path == f'key_blocks["{shape_key_name}"].value':
                        source_drivers.append(driver)
            
            if source_drivers:
                # Remove existing drivers from target shape key
                if target_obj.data.shape_keys.animation_data:
                    for driver in target_obj.data.shape_keys.animation_data.drivers[:]:
                        if driver.data_path == f'key_blocks["{shape_key_name}"].value':
                            target_obj.data.shape_keys.animation_data.drivers.remove(driver)
                
                # Copy drivers from source to target
                for source_driver in source_drivers:
                    # Create new driver for the target shape key
                    target_driver = target_obj.data.shape_keys.driver_add(f'key_blocks["{shape_key_name}"].value').driver
                    
                    # Copy driver settings
                    target_driver.type = source_driver.driver.type
                    target_driver.expression = source_driver.driver.expression
                    
                    # Copy variables
                    for source_var in source_driver.driver.variables:
                        target_var = target_driver.variables.new()
                        target_var.name = source_var.name
                        target_var.type = source_var.type
                        
                        # Copy variable targets
                        for i, source_target in enumerate(source_var.targets):
                            if i < len(target_var.targets):
                                target_target = target_var.targets[i]
                                # Only copy writable properties
                                try:
                                    target_target.id = source_target.id
                                except:
                                    pass
                                try:
                                    target_target.bone_target = source_target.bone_target
                                except:
                                    pass
                                try:
                                    target_target.data_path = source_target.data_path
                                except:
                                    pass
                                try:
                                    target_target.transform_type = source_target.transform_type
                                except:
                                    pass
                                try:
                                    target_target.transform_space = source_target.transform_space
                                except:
                                    pass
                    
                    transferred_drivers += 1
        
        if transferred_drivers > 0:
            self.report({'INFO'}, f"Transferred {transferred_drivers} drivers for {len(matching_shape_keys)} matching shape keys")
        else:
            self.report({'INFO'}, "No drivers found to transfer")
        
        return {'FINISHED'}

# ------------------------------
# UI Panel (Modifier-like)
# ------------------------------
class OBJECT_PT_ShapeKeyTransfer(Panel):
    bl_label = "Shape Key Transfer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon='SHAPEKEY_DATA')
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        obj = context.active_object
        props = obj.shape_key_transfer_props
        
        # Enable/Disable toggle at the top
        layout.prop(props, "enabled")
        
        # Only show the rest of the interface if enabled
        if not props.enabled:
            return
        
        # Source object selector
        layout.prop(props, "source_object")
        
        # Check if source is valid and has shape keys
        source_obj = props.source_object
        if not source_obj or source_obj.type != 'MESH' or not source_obj.data.shape_keys:
            layout.label(text="Source object has no shape keys", icon='ERROR')
            return
        
        # Transfer mode selector
        layout.prop(props, "transfer_mode")
        
        # Check vertex count only for full transfer mode
        vertex_count_mismatch = len(obj.data.vertices) != len(source_obj.data.vertices)
        if props.transfer_mode == 'FULL' and vertex_count_mismatch:
            layout.label(text="Objects have different vertex counts", icon='ERROR')
            layout.label(text=f"Source: {len(source_obj.data.vertices)}, Target: {len(obj.data.vertices)}")
            layout.label(text="Switch to 'Names Only' mode or use objects with same vertex count")
            return
        elif props.transfer_mode == 'NAMES_ONLY' and vertex_count_mismatch:
            # Show info but don't block operation
            box = layout.box()
            box.label(text="Different vertex counts detected", icon='INFO')
            box.label(text=f"Source: {len(source_obj.data.vertices)}, Target: {len(obj.data.vertices)}")
            box.label(text="Only shape key names and values will be transferred")
        
        # Auto transfer option
        layout.prop(props, "auto_transfer")
        
        # Only selected vertices option - only show if source object is selected
        if source_obj:
            layout.prop(props, "only_selected_vertices")
        
        # Transfer all button
        row = layout.row()
        row.scale_y = 1.5
        transfer_text = "Transfer All (Full Data)" if props.transfer_mode == 'FULL' else "Transfer All (Names Only)"
        row.operator("object.transfer_all_shape_keys", text=transfer_text, icon='IMPORT')
        
        # Transfer Drivers button
        row = layout.row()
        row.scale_y = 1.5
        row.operator("object.transfer_drivers", text="Transfer Drivers", icon='DRIVER')
        
        # Shape keys selection and transfer buttons
        box = layout.box()
        box.label(text="Available Shape Keys:")
        
        # List shape keys and add transfer buttons
        for key in source_obj.data.shape_keys.key_blocks:
            if key.name == "Basis":
                continue  # Skip Basis shape key
                
            row = box.row(align=True)
            row.label(text=key.name)
            
            # Show if target has this shape key already
            if obj.data.shape_keys and key.name in obj.data.shape_keys.key_blocks:
                icon = 'CHECKMARK'
            else:
                icon = 'NONE'
                
            transfer_button_text = "Transfer" if props.transfer_mode == 'FULL' else "Transfer Name"
            op = row.operator("object.transfer_shape_key", text=transfer_button_text, icon=icon)
            op.shape_key_name = key.name

# ------------------------------
# Registration
# ------------------------------
classes = (
    ShapeKeyTransferProperties,
    ShapeKeyItem,
    OBJECT_OT_TransferShapeKey,
    OBJECT_OT_TransferAllShapeKeys,
    OBJECT_OT_TransferDrivers,
    OBJECT_PT_ShapeKeyTransfer
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties on the object instead of scene (more modifier-like)
    bpy.types.Object.shape_key_transfer_props = PointerProperty(type=ShapeKeyTransferProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Remove properties
    del bpy.types.Object.shape_key_transfer_props

if __name__ == "__main__":
    register()
