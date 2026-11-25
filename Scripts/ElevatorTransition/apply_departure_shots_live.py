"""Apply the reviewed departure camera/tags to the already-open main Stage2.

Default: read-only MCP inspection and a JSON plan. --apply is required for any
editor mutation. This never loads a map, copies a candidate map, touches native
code, closes an editor, or saves all packages. On a guard failure it stops;
it does not roll back someone else's possible concurrent edits.

The supplied MCP has no atomic transaction/revision guard. File SHA256, owning
PID, level/PIE/dirty state, and all targeted actor states are checked repeatedly.
These detect file saves and changes to the inspected actors, but cannot prove
that an unrelated actor was not edited in memory during our short apply window.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MAIN_ROOT = Path('C:/Users/whghk/Catrun').resolve()
DEFAULT_CANDIDATE = Path('C:/Users/whghk/.codex/workspaces/ElevatorRevision3_20261125_01a21074/Catrun')
MAP = '/Game/Maps/Stage2'
WORLD_PREFIX = MAP + '.Stage2:PersistentLevel.'
OWNER_TAG = 'CatrunElevatorTransition20261125'
VISIBLE_TAG = 'CatrunElevatorIsolationVisible'
TOOLSETS = {
    'actor': 'editor_toolset.toolsets.actor.ActorTools',
    'object': 'editor_toolset.toolsets.object.ObjectTools',
    'asset': 'editor_toolset.toolsets.asset.AssetTools',
    'scene': 'editor_toolset.toolsets.scene.SceneTools',
    'app': 'EditorToolset.EditorAppToolset',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unwrap(result):
    require(isinstance(result, dict) and not result.get('isError'), 'MCP tool error: ' + repr(result))
    texts = [row['text'] for row in result.get('content', []) if row.get('type') == 'text']
    require(len(texts) == 1, 'Expected one MCP JSON result block')
    payload = json.loads(texts[0])
    require(isinstance(payload, dict) and 'returnValue' in payload,
            'Unexpected MCP return envelope: ' + repr(payload))
    require(not payload.get('error'), 'Nested MCP tool error: ' + repr(payload))
    return payload['returnValue']


def reference(value):
    require(isinstance(value, dict) and isinstance(value.get('refPath'), str), 'Invalid object reference')
    path = value['refPath']
    require(path.startswith(WORLD_PREFIX), 'Refusing a reference outside loaded Stage2: ' + path)
    return {'refPath': path}


def endpoint_owners():
    """Read Windows' listening TCP table; no process/window manipulation."""
    require(os.name == 'nt', 'This live-editor helper is Windows-only')

    class Row(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulong) for name in
                    ('state', 'local_addr', 'local_port', 'remote_addr', 'remote_port', 'pid')]

    size = ctypes.c_ulong()
    api = ctypes.windll.iphlpapi.GetExtendedTcpTable
    code = api(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)
    require(code in (0, 122), 'Cannot inspect MCP listener ownership')
    buffer = ctypes.create_string_buffer(size.value)
    require(api(buffer, ctypes.byref(size), False, socket.AF_INET, 3, 0) == 0,
            'MCP listener ownership changed during inspection')
    count = ctypes.c_ulong.from_buffer(buffer).value
    rows = (Row * count).from_buffer(buffer, ctypes.sizeof(ctypes.c_ulong))
    return sorted({int(row.pid) for row in rows if socket.ntohs(row.local_port & 0xffff) == 8000})


def rotation_toward(position, target):
    x, y, z = [b - a for a, b in zip(position, target)]
    return {'pitch': math.degrees(math.atan2(z, math.hypot(x, y))),
            'yaw': math.degrees(math.atan2(y, x)), 'roll': 0.0}


def close(actual, expected, tolerance=0.001):
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and abs(actual - expected) <= tolerance
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            close(a, b, tolerance) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            close(actual[key], value, tolerance) for key, value in expected.items())
    return actual == expected


class LiveUpdate:
    def __init__(self, client, candidate_root, editor_pid, apply):
        self.client = client
        self.candidate_root = candidate_root.resolve()
        self.editor_pid = editor_pid
        self.apply = apply
        self.map_file = ROOT / 'Content/Maps/Stage2.umap'
        self.source_report = self.candidate_root / 'Saved/ElevatorTransition/departure_shots_refine_report.json'
        self.candidate_map = self.candidate_root / 'Content/Maps/Stage2.umap'
        self.map_hash = sha256(self.map_file)
        self.report_hash = sha256(self.source_report)
        self.candidate_hash = sha256(self.candidate_map)
        self.plan = json.loads(self.source_report.read_text(encoding='utf-8-sig'))
        self.expected = {}
        self.camera_ref = None
        self.component_ref = None
        self.director_ref = None
        self.director_properties = None
        self.expected_camera_properties = None
        self.expected_dirty = False
        self.mutation_started = False
        self.receipt = {'mode': 'apply' if apply else 'dry-run', 'success': False,
                        'map': MAP, 'main_root': str(ROOT), 'editor_pid': editor_pid,
                        'candidate_report': str(self.source_report), 'candidate_report_sha256': self.report_hash,
                        'main_stage2_sha256_before': self.map_hash, 'operations': []}
        self.validate_plan()

    def validate_plan(self):
        p = self.plan
        require(ROOT == EXPECTED_MAIN_ROOT, 'Run the helper from the main Catrun Scripts folder')
        require(self.candidate_root != ROOT, 'Candidate and live main must be different folders')
        require(p.get('success') is True and p.get('map') == MAP + '.Stage2', 'Candidate authoring failed/wrong map')
        require(p.get('changed_actor') == 'E23_Shot_Below', 'Unexpected candidate camera')
        require(p.get('stage2_sha256_after') == self.candidate_hash, 'Candidate map/report hash mismatch')
        after = p['after']
        require(after['position'] == [729.0, -1310.0, 14.0], 'Candidate lens differs from reviewed plan')
        require(after['preview_target'] == [715.0, -1493.34, 200.0], 'Candidate target differs from reviewed plan')
        require(after['horizontal_fov'] == 36.0, 'Candidate FOV differs from reviewed plan')
        labels = p['isolation_allowlisted_actors']
        require(labels and len(labels) == len(set(labels)), 'Missing/duplicate allowlist')
        require(all(name.startswith(('E23_Lift_', 'E23_Guide_')) for name in labels), 'Allowlist scope changed')
        self.wanted_labels = sorted(labels)
        self.desired_transform = {
            'location': dict(zip(('x', 'y', 'z'), after['position'])),
            'rotation': rotation_toward(after['position'], after['preview_target']),
            'scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
        }
        self.desired_camera_properties = {'FieldOfView': 36.0, 'bConstrainAspectRatio': False}

    def file_guard(self, include_main=True):
        require(endpoint_owners() == [self.editor_pid], 'Port 8000 is no longer owned by the expected editor PID')
        require(sha256(self.source_report) == self.report_hash, 'Candidate plan changed during the operation')
        require(sha256(self.candidate_map) == self.candidate_hash, 'Candidate map changed during the operation')
        if include_main:
            require(sha256(self.map_file) == self.map_hash, 'Main Stage2 was saved by another writer; stopping')

    def call(self, group, name, arguments):
        self.file_guard()
        return unwrap(self.client.call('call_tool', {
            'toolset_name': TOOLSETS[group], 'tool_name': name, 'arguments': arguments}))

    def editor_guard(self, dirty=None):
        require(self.call('scene', 'get_current_level', {}) == MAP, 'Current level changed; stopping')
        require(self.call('app', 'IsPIERunning', {}) is False, 'PIE started; stopping')
        value = self.call('asset', 'is_dirty', {'asset_path': MAP})
        require(value is (self.expected_dirty if dirty is None else dirty), 'Unexpected Stage2 dirty-state change')
        self.file_guard()

    def find(self, name):
        rows = self.call('scene', 'find_actors',
                         {'name': name, 'tag': OWNER_TAG, 'collision_channels': []})
        require(isinstance(rows, list), 'Expected actor reference array')
        return [reference(row) for row in rows]

    def properties(self, instance, names):
        value = self.call('object', 'get_properties', {'instance': instance, 'properties': names})
        require(isinstance(value, str), 'Expected object properties JSON string')
        result = json.loads(value)
        require(isinstance(result, dict) and set(result) == set(names), 'Requested properties could not all be read')
        return result

    def actor_state(self, actor):
        state = {'ref': actor, 'label': self.call('actor', 'get_label', {'actor': actor}),
                 'tags': sorted(self.call('actor', 'get_tags', {'actor': actor})),
                 'transform': self.call('actor', 'get_actor_transform', {'actor': actor})}
        require(OWNER_TAG in state['tags'], 'E23 ownership tag missing: ' + state['label'])
        return state

    def actor_guard(self, path):
        expected = self.expected[path]
        actual = self.actor_state(expected['ref'])
        require(close(actual, expected), 'Target actor changed concurrently: ' + expected['label'])

    def camera_guard(self):
        actual = self.properties(self.component_ref, list(self.expected_camera_properties))
        require(close(actual, self.expected_camera_properties), 'Camera properties changed concurrently')
        require(self.properties(self.director_ref, list(self.director_properties)) == self.director_properties,
                'Director camera/pivot ownership changed concurrently')

    def inspect(self):
        self.editor_guard(dirty=False)
        references = self.find('E23_Lift_') + self.find('E23_Guide_')
        references += self.find('E23_Shot_Below') + self.find('E23_Director')
        require(len({ref['refPath'] for ref in references}) == len(references), 'Duplicate target references')
        for ref in references:
            state = self.actor_state(ref)
            self.expected[ref['refPath']] = state
        labels = [row['label'] for row in self.expected.values()]
        require(len(set(labels)) == len(labels), 'Duplicate E23 actor labels')
        require(sorted(labels) == sorted(self.wanted_labels + ['E23_Shot_Below', 'E23_Director']),
                'Live E23 actors do not exactly match the candidate allowlist')
        by_label = {row['label']: row for row in self.expected.values()}
        self.camera_ref = by_label['E23_Shot_Below']['ref']
        self.director_ref = by_label['E23_Director']['ref']
        for ref, expected_class in [(self.camera_ref, '/Script/Engine.CameraActor'),
                                    (self.director_ref, '/Script/Catrun.CatrunElevatorTransition')]:
            require(self.call('object', 'get_class', {'instance': ref}) == {'refPath': expected_class},
                    'Unexpected actor class: ' + ref['refPath'])
        components = self.call('actor', 'get_components',
                               {'actor': self.camera_ref, 'component_type': {'refPath': '/Script/Engine.CameraComponent'}})
        require(isinstance(components, list) and len(components) == 1, 'Camera must own exactly one camera component')
        self.component_ref = reference(components[0])
        require(self.component_ref['refPath'].startswith(self.camera_ref['refPath'] + '.'), 'Foreign camera component')
        root = reference(self.call('actor', 'get_root_component', {'actor': self.camera_ref}))
        require(self.call('actor', 'get_parent_component', {'component': root}) is None,
                'The fixed low camera is attached to another component')
        self.director_properties = self.properties(self.director_ref, ['PeekCamera', 'CabinPivot', 'bArrivalSide'])
        require(self.director_properties['PeekCamera'] == self.camera_ref, 'Director points to another peek camera')
        require(self.director_properties['bArrivalSide'] is False, 'Refusing arrival-side director')
        pivot = self.actor_state(reference(self.director_properties['CabinPivot']))
        require(pivot['label'] == 'E23_Mark_CabinPivot', 'Unexpected cabin pivot actor')
        require(close(pivot['transform']['location'], {'x': 715.0, 'y': -1590.0, 'z': 0.0}), 'Cabin pivot moved')
        self.expected[pivot['ref']['refPath']] = pivot
        self.expected_camera_properties = self.properties(self.component_ref, ['FieldOfView', 'bConstrainAspectRatio'])
        original = self.plan['before']
        before_rotation = original['rotation']  # Unreal Rotator.to_tuple is roll, pitch, yaw.
        original_transform = {
            'location': dict(zip(('x', 'y', 'z'), original['position'])),
            'rotation': dict(zip(('roll', 'pitch', 'yaw'), before_rotation)),
            'scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
        }
        camera = self.expected[self.camera_ref['refPath']]
        require(close(camera['transform'], original_transform) or close(camera['transform'], self.desired_transform),
                'Live camera differs from both candidate baseline and reviewed target')
        require(close(self.expected_camera_properties, {'FieldOfView': original['horizontal_fov'], 'bConstrainAspectRatio': False})
                or close(self.expected_camera_properties, self.desired_camera_properties),
                'Live camera properties differ from the reviewed baseline/target')
        self.receipt['actors_before'] = copy.deepcopy(self.expected)
        self.receipt['camera_properties_before'] = copy.deepcopy(self.expected_camera_properties)
        self.receipt['plan'] = {'camera_ref': self.camera_ref, 'camera_component_ref': self.component_ref,
                                'desired_transform': self.desired_transform,
                                'desired_camera_properties': self.desired_camera_properties,
                                'tag': VISIBLE_TAG, 'tag_actor_labels': self.wanted_labels,
                                'save_assets': [MAP]}
        self.editor_guard(dirty=False)

    def mutation(self, group, name, arguments):
        require(self.apply, 'Mutating tool reached in dry-run')
        self.mutation_started = True
        value = self.call(group, name, arguments)
        if name != 'add_tag':
            require(value is True, 'Mutation failed: ' + name)
        self.expected_dirty = True
        self.receipt['operations'].append({'toolset': TOOLSETS[group], 'tool': name, 'arguments': arguments})

    def execute(self):
        self.inspect()
        if not self.apply:
            self.receipt['success'] = True
            self.receipt['editor_mutations'] = 0
            return self.receipt
        backup = ROOT / ('Saved/ElevatorTransition/Backups/Stage2_BeforeLiveDeparture_'
                         + time.strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()) + '.umap')
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.map_file, backup)
        require(sha256(backup) == self.map_hash, 'Backup hash mismatch')
        self.receipt['backup'] = str(backup)
        # Repeat preconditions immediately before the first edit, after inspection/backup.
        self.editor_guard(dirty=False)
        for path in self.expected:
            self.actor_guard(path)
        self.camera_guard()
        self.editor_guard(dirty=False)
        path = self.camera_ref['refPath']
        if not close(self.expected[path]['transform'], self.desired_transform):
            self.actor_guard(path)
            self.mutation('actor', 'set_actor_transform',
                          {'actor': self.camera_ref, 'xform': self.desired_transform, 'worldspace': True})
            self.expected[path]['transform'] = copy.deepcopy(self.desired_transform)
            self.actor_guard(path)
        self.editor_guard()
        if not close(self.expected_camera_properties, self.desired_camera_properties):
            self.camera_guard()
            self.mutation('object', 'set_properties',
                          {'instance': self.component_ref, 'values': json.dumps(self.desired_camera_properties)})
            self.expected_camera_properties = copy.deepcopy(self.desired_camera_properties)
            self.camera_guard()
        for label in self.wanted_labels:
            path = next(path for path, row in self.expected.items() if row['label'] == label)
            self.editor_guard()
            self.actor_guard(path)
            state = self.expected[path]
            if VISIBLE_TAG not in state['tags']:
                self.mutation('actor', 'add_tag', {'actor': state['ref'], 'tag': VISIBLE_TAG})
                state['tags'] = sorted(state['tags'] + [VISIBLE_TAG])
                self.actor_guard(path)
        for path in self.expected:
            self.actor_guard(path)
        self.camera_guard()
        self.editor_guard()
        if self.mutation_started:
            # This is deliberately the only save call. Never pass an empty list.
            require(self.call('asset', 'save_assets', {'asset_paths': [MAP]}) is True, 'Targeted Stage2 save failed')
            self.map_hash = sha256(self.map_file)
            self.expected_dirty = False
        self.editor_guard(dirty=False)
        for path in self.expected:
            self.actor_guard(path)
        self.camera_guard()
        self.receipt['success'] = True
        self.receipt['actors_after'] = copy.deepcopy(self.expected)
        self.receipt['camera_properties_after'] = self.expected_camera_properties
        self.receipt['main_stage2_sha256_after'] = self.map_hash
        self.receipt['editor_mutations'] = len(self.receipt['operations'])
        self.receipt['saved_packages'] = [MAP] if self.mutation_started else []
        return self.receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Explicitly apply camera/tags and save only loaded Stage2')
    parser.add_argument('--candidate-root', type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument('--expected-editor-pid', type=int, default=40748)
    parser.add_argument('--report', type=Path, help='Optional JSON receipt file; otherwise print it only')
    args = parser.parse_args(argv)
    require(ROOT == EXPECTED_MAIN_ROOT, 'Run the main-project copy of this helper')
    require(endpoint_owners() == [args.expected_editor_pid], 'Unexpected process owns MCP port 8000')
    spec = importlib.util.spec_from_file_location('e23_editor_mcp', ROOT / 'Scripts/Prototype/ue_mcp.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    update = LiveUpdate(module.EditorMCP(), args.candidate_root, args.expected_editor_pid, args.apply)
    try:
        result = update.execute()
    except Exception as exc:
        result = update.receipt
        result.update(error=str(exc), editor_mutations_may_have_started=update.mutation_started,
                      recovery='Stopped without further writes. Inspect any remaining dirty Stage2 state; no automatic rollback.')
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
