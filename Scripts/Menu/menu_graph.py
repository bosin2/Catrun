"""Checked graph/UMG authoring primitives; imported only inside Unreal Python."""
import json
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.object import ObjectTools
from toolset_registry.helpers import compile_blueprint

UMG = unreal.get_default_object(unreal.load_class(None, '/Script/UMGToolSet.UMGToolSet'))
PROPERTY_SCHEMAS = {}

def ui(method, *args):
    return UMG.call_method(method, args=args)

def widgets(bp):
    return {i.widget.get_name(): i.widget for i in ui('GetWidgets', bp).widgets}

def properties(obj, **values):
    key = obj.get_class().get_path_name()
    if key not in PROPERTY_SCHEMAS:
        PROPERTY_SCHEMAS[key] = ObjectTools.list_properties(obj)
    for name, value in values.items():
        obj.get_editor_property(name)  # Resolve the real reflected property before writing.
        obj.set_editor_property(name, value)
    return obj

def add(bp, cls, name, parent, variable=False, index=-1):
    info = ui('AddWidget', bp, cls.static_class(), name, parent, index)
    assert info.widget and info.widget.get_name() == name, name
    if variable:
        ui('ToggleWidgetAsVariable', bp, info.widget, True)
    return info.widget

def compile_bp(bp):
    compile_blueprint(bp, True)
    assert bp.get_editor_property('status') == unreal.BlueprintStatus.BS_UP_TO_DATE

def editor(g):
    return unreal.BlueprintGraphEditor.get_graph_editor(g)

def pin(n, name, output=False):
    p = n.find_output_pin(name) if output else n.find_input_pin(name)
    assert p and p.is_valid(), (n.get_name(), name, output)
    return p

def wire(a, ap, b, bp):
    assert pin(a, ap, True).try_create_connection(pin(b, bp)), (a.get_name(), ap, b.get_name(), bp)

def literal(n, name, value):
    assert pin(n, name).set_pin_value(str(value)), (n.get_name(), name, value)

class Graph:
    """One readable lane per operation. New nodes never move existing menu nodes."""
    def __init__(self, graph, x=0, y=0):
        self.g = graph
        self.e = editor(graph)
        self.x, self.y = x, y
        self.nodes = []

    def placed(self, n):
        assert n
        n.set_node_pos(unreal.IntPoint(self.x, self.y))
        self.x += 300
        self.nodes.append(n)
        return n

    def fn(self, path, target=None, **values):
        n = self.placed(self.e.add_call_function_node(path))
        if target:
            wire(target[0], target[1], n, 'self')
        for name, value in values.items():
            if isinstance(value, tuple):
                wire(value[0], value[1], n, name)
            else:
                literal(n, name, value)
        return n

    def get(self, name, cls=''):
        return self.placed(self.e.add_get_member_variable_node(name, cls))

    def set(self, name, source=None, value=None, cls='', target=None):
        n = self.placed(self.e.add_set_member_variable_node(name, cls))
        if source:
            wire(source[0], source[1], n, name)
        elif value is not None:
            literal(n, name, value)
        if target:
            wire(target[0], target[1], n, 'self')
        return n

    def branch(self, condition):
        n = self.placed(self.e.add_branch_node())
        wire(condition[0], condition[1], n, 'Condition')
        return n

    def ref(self, name):
        return (self.get(name), name)

    def chain(self, *nodes):
        for a, b in zip(nodes, nodes[1:]):
            wire(a, 'then', b, 'execute')
        return nodes[-1]

    def comment(self, text):
        self.e.add_comment_to_nodes(text, self.nodes, 60)

def event(bp, widget, delegate):
    assert ui('BindToEventProperty', bp, delegate, widget.get_name(), widget.get_class())
    g = BP.get_graph(bp, 'EventGraph')
    suffix = '|' + delegate + '(' + widget.get_name() + ')'
    matches = [i.node for i in BP.get_node_infos(BP.find_nodes(g))
               if i.node.get_class().get_name() == 'K2Node_ComponentBoundEvent'
               and i.type_id.endswith(suffix)]
    assert len(matches) == 1, (widget.get_name(), delegate, matches)
    return matches[0]

def function(bp, name):
    return Graph(BP.add_function_graph(bp, name))

def entry(q):
    return q.e.find_graph_entry_pin().get_owning_node()

def audit(bp):
    rows = []
    for i in ui('GetWidgets', bp).widgets:
        row = {'name': i.widget.get_name(), 'type': i.widget.get_class().get_name(),
               'parent': i.parent.get_name() if i.parent else None, 'variable': i.is_variable}
        for k in ('text', 'font', 'default_options', 'visibility', 'is_enabled'):
            try:
                row[k] = str(i.widget.get_editor_property(k))
            except Exception:
                pass
        if i.slot:
            row['slot_class'] = i.slot.get_class().get_name()
            row['slot_properties'] = ObjectTools.get_properties(i.slot, [])
        rows.append(row)
    graphs = []
    for g in BP.list_graphs(bp):
        graphs.append({'name': g.get_name(), 'nodes': [
            {'name': n.node.get_name(), 'type': n.type_id,
             'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in n.input_pins],
             'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in n.output_pins]}
            for n in BP.get_node_infos(BP.find_nodes(g))]})
    return {'asset': bp.get_path_name(), 'status': str(bp.get_editor_property('status')), 'widgets': rows, 'graphs': graphs}
