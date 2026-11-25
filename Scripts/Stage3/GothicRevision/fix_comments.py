"""Remove only comment nodes from the owned dock BP. Root invokes fix().

Default does not save any package. fix(save=True) saves only this BP, never maps.
No runtime nodes, variable declarations, connections or defaults are rewritten.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = '/Game/Environment/Stage3/GothicRevision_20261125/Blueprints/BP_GothicDockPresentation'
OWNER = 'Stage3GothicDockPresentation20261125'


def fix(save=False):
    import unreal as u
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    from toolset_registry.helpers import compile_blueprint
    ea = u.EditorAssetLibrary
    bp = ea.load_asset(PATH)
    if not bp or ea.get_metadata_tag(bp, 'GothicDockOwner') != OWNER:
        raise RuntimeError('Expected the owned BP_GothicDockPresentation')

    def snapshot():
        result = {}
        for graph in BP.list_graphs(bp):
            nodes = {}
            for info in BP.get_node_infos(BP.find_nodes(graph)):
                node = info.node
                if node.get_class().get_name() == 'EdGraphNode_Comment': continue
                nodes[node.get_name()] = {'type': str(info.type_id), 'pins': [
                    [str(p.get_pin_name()), str(p.get_pin_value()), sorted(
                        (other.get_owning_node().get_name(), str(other.get_pin_name()))
                        for other in p.list_connected_pins())] for p in node.list_all_pins()]}
            result[graph.get_name()] = nodes
        return result

    before = snapshot()
    removed = []
    for graph in BP.list_graphs(bp):
        comments = [info.node for info in BP.get_node_infos(BP.find_nodes(graph))
                    if info.node.get_class().get_name() == 'EdGraphNode_Comment']
        removed.extend({'graph': graph.get_name(), 'node': n.get_name()} for n in comments)
        if comments: u.BlueprintGraphEditor.get_graph_editor(graph).remove_nodes(comments)
    if snapshot() != before: raise RuntimeError('Non-comment graph content changed')
    compile_blueprint(bp, True)
    if bp.get_editor_property('status') != u.BlueprintStatus.BS_UP_TO_DATE:
        raise RuntimeError('Blueprint compile failed')
    if snapshot() != before: raise RuntimeError('Compile changed runtime graph content')
    ea.set_metadata_tag(bp, 'GothicDockGraphVersion', '2')
    if save and not ea.save_loaded_asset(bp): raise RuntimeError('BP-only save failed')
    report = {'success': True, 'blueprint': bp.get_path_name(), 'removed': removed,
              'runtime_graph_preserved': True, 'blueprint_saved': bool(save), 'map_saved': False}
    out = ROOT / 'Saved/Stage3GothicRevision20261125/comment_fix_report.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf8')
    return report


if __name__ == '__main__':
    raise SystemExit('Root writer: call fix_comments.fix(save=True) to save only the presentation BP.')
