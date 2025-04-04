ABOUT: Custom Nodes for Blender’s Existing NodeEditors
================================================

This plugin extends Blender’s native NodeTree system by adding custom nodes 
to the Geometry Nodes and/or Shader Node and/or Compositor Nodes editors. 
It builds on top of existing editors and enhances them 
with new node types and/or socket types.


Limitations
-----------

Please note the following restrictions, due to how Blender handles node evaluation.
- You cannot:
  - Have access the value of an existing native socket. no API currently exists for that.
    This imply that you'll never be able to, for example, recieve a float value from an input 
    and spit out a processed value out. Consider the values of any native input sockets as unknown.
    Why: The native nodetrees C++ evaluators of the various tree types do not support evaluating 
         a node.execute() function for example. Maybe it will added one day.
- You can: 
  - Arrange a hidden nodegroup nodetree nodes, links, and parameters value. 
  - Spit out a constant value. 
  - For Shader and Compositor: Add your own separate nodes evaluation process, which outputs will automatically arrange a hidden node_tree 
    and/or spit out a constant value. for geometry node this PR is required because unknown socketypes implementation in GN source is
    not as flexible as the other editors https://projects.blender.org/blender/blender/pulls/136968.


Folder Structure & Contribution
-------------------------------

You can implement two types of nodes:
- CustomNodeGroup:
    See it as a NodeGroup with python properties and  extra interface abilities.
    In the NodeBooster N Panel > Active Node > Development, you can see the hidden NodeGroup data.
- CustomNode: 
    TODO 
    write about this.. 
    How it can be used, how it requires an evaluator. 
    explain how they can implement in the current evaluator system.

To contribute a custom node, follow these steps: 

1. Create your node file:
   Create a new 'mynodename.py' file in this folder.
   Please follow the structure/examples of the existing nodes. 
     - On init(), if you are using a CustomNodeGroup, you'll need to assign 
       your hidden node.node_tree. 
     - Please follow the established naming conventions. 
       - always start your class with NODEBOOSTER_ 
       - bl_idname should contain the keyword 'NodeBooster'.
       - Use _NG_ for NodeCustomGroup and _ND_ for NodeCustom. 
     - Use the 'node.auto_update = {}' attribute to automatically run 'cls.update_all()' on depsgraph.
     - node.update() will run when the user is adding new links in the node_tree. 
       We generally dont use this for CustomNodeGroup.
  
2. Register your new node: 
     - Import your node class(es) from your new module in the main '__init__.py'.
     - In the same '__init__.py' file, add your new classes in the 'classes' object for registration
     - and define the placement in the menu tuple object for adding the node in the add menu 
       interface (The submenus are automatically registered on plugin load depending on that tuple object) .

Tips:
     - Do not directly start messing with new custom socket types & NodeCustom, it's more difficult.
       Keep it simple, implement a NodeCustomGroup that just spit out outputs at first.
       Then second, you can try implementing a NodeCustomGroup that arrange the node.node_tree nodes and links automatically (ex: math expression node). 
     - Please scoot out functions available in 'node_utils.py' module. There are useful functions in there to easily manipulate sockets and nodegroups.
       See how the existing nodes use these functions. Its best to centralized these actions, a boilerplate for the nodetree API is better for fixing API changes down the line. 
     - Try out the Python Nex Script node! Perhaps your need can be met and you wont need to implement a new node. Nex Script is pretty powerful.
