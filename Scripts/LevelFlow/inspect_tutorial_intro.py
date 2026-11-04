import json
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
result = {}
for path in ['/Game/Blueprints/BP_TutorialIntro', '/Game/UI/WBP_MainMenu']:
    bp = unreal.EditorAssetLibrary.load_asset(path)
    graphs = BP.list_graphs(bp)
    rows = []
    for graph in graphs:
        for node in BP.get_node_infos(BP.find_nodes(graph)):
            rows.append({'graph': graph.get_name(), 'node': node.node.get_name(), 'type': node.type_id,
                'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in node.input_pins],
                'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in node.output_pins]})
    result[path] = rows
out=Path(unreal.Paths.project_saved_dir())/'Flow/Playability/intro-graphs.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
