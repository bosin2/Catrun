import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
b=unreal.load_asset('/Game/Characters/BlackCat/Final/Animations/ABP_Cat_Final');g=BP.get_graph(b,'AnimGraph');a=unreal.BlueprintGraphEditor.get_graph_editor(g).list_available_nodes([])
print('SLOT_CHOICES',[str(x) for x in a if ('슬롯' in str(x) or 'Slot' in str(x) or 'slot' in str(x)) and ('애니' in str(x) or 'Default' in str(x))])
print('UNREAL_NODE_DOC',unreal.BlueprintEditorLibrary.__doc__)
