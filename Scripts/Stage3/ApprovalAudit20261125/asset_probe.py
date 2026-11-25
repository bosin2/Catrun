"""Read-only Stage3 delivery/use audit. Import inert; root calls main().

Requires the existing Stage3 editor world outside PIE. No load-level, spawning,
selection, import, material assignment, package/map save or deletion. The only
write is Saved/Stage3ApprovalAudit20261125/assets02.json (override the numeric
suffix with CATRUN_STAGE3_ASSET_AUDIT_PASS). Absence from the current
map is not permission to delete an asset or to populate a gameplay passage.
"""
import hashlib
import json
import os
import traceback
from collections import Counter, defaultdict
from pathlib import Path


def source_inventory():
    root = Path('C:/Users/whghk/Desktop/CastleKit/Stage3')
    rows, manifests, errors, excluded_caches = [], [], [], []
    def manifest(relative):
        p = root / relative
        if not p.exists():
            errors.append('Missing delivery manifest: ' + str(p))
            return {}, p.parent
        raw = p.read_bytes()
        manifests.append({'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest()})
        return json.loads(raw.decode('utf8')), p.parent
    def add(folder, relative, name, source, kind='mesh_fbx'):
        if not relative:
            return
        p = (folder / relative).resolve()
        rows.append({'name': name or p.stem, 'file': str(p), 'exists': p.exists(),
                     'manifest': source, 'kind': kind})
    d, folder = manifest('Production02_20261125/asset_manifest_v3.json')
    for item in d.get('assets', []):
        add(folder, item.get('primary_fbx'), item.get('name'), 'Production02 v3')
        for relative in item.get('additional_fbx', []):
            add(folder, relative, Path(relative).stem, 'Production02 v3 additional')
    d, folder = manifest('Mechanisms03_20261125/asset_manifest.json')
    for item in d.get('items', []):
        if item.get('kind') == 'asset':
            add(folder, item.get('fbx'), item.get('name'), 'Mechanisms03')
    d, folder = manifest('Rugs04_20261125/delivery_verification.json')
    for item in d.get('deliverable_files', []):
        if item['path'].lower().endswith('.fbx'):
            add(folder, item['path'], d.get('asset'), 'Rugs04')
    project = Path(__file__).resolve().parents[3]
    for p in (project / 'SourceArt/Stage3').rglob('*.fbx'):
        add(p.parent, p.name, p.stem, 'SourceArt/Stage3', 'animation_or_mesh_fbx')
    known = {r['file'].casefold() for r in rows}
    # Surface new deliveries without equating work-in-progress or assembly FBX
    # with an approved asset package. Older Sample01/Production02 alternates are
    # intentionally represented by their authoritative v3 manifest instead.
    for folder in root.iterdir() if root.exists() else []:
        if not folder.is_dir() or folder.name.startswith(('Sample01_', 'Production02_')):
            continue
        for p in folder.rglob('*.fbx'):
            if 'import_cache' in p.parts or '.fbm' in str(p):
                excluded_caches.append(str(p))
                continue
            if str(p.resolve()).casefold() not in known and '.fbm' not in str(p):
                add(p.parent, p.name, p.stem, 'unlisted_delivery_fbx', 'unreviewed_or_assembly_fbx')
    return {'manifest_files': manifests, 'files': rows, 'errors': errors,
            'excluded_qa_import_caches': excluded_caches}


def main():
    import unreal as u
    root = Path(u.Paths.project_dir()).resolve()
    pass_id = os.environ.get('CATRUN_STAGE3_ASSET_AUDIT_PASS', '02')
    assert pass_id.isdigit(), 'Audit pass must be a numeric suffix'
    output = root / 'Saved/Stage3ApprovalAudit20261125' / ('assets' + pass_id + '.json')
    assert not output.exists(), 'Preserve previous approval audit: ' + str(output)
    report = {'success': False, 'read_only': True, 'packages_saved': False,
              'scope': 'Current Stage3 editor actors plus AssetRegistry Stage3 packages; source deliveries matched by recorded import filename first, exact asset name second.',
              'limitations': ['Registry dependency reachability is not proof of runtime use or permission to delete.',
                             'Hidden mesh components may remain critical gameplay collision proxies.',
                             'Blueprint construction/runtime spawning and unloaded sublevels may use assets absent from this actor inventory.',
                             'Source-name-only matches are candidates, not proof of identical imported bytes.',
                             'Placement suggestions are pending approval and require collision/cat-camera validation; nothing is placed.'],
              'errors': [], 'actors': [], 'assets': [], 'source_deliveries': source_inventory()}
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name() == '/Game/Maps/Stage3.Stage3', 'Stage3 must already be loaded'
    assert not editor.get_game_world(), 'Audit must run outside PIE'
    actors = list(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
    before_actor_paths = sorted(a.get_path_name() for a in actors)
    protected = [root / 'Content/Maps/Stage3.umap'] + list((root / 'Content/Environment/Stage3').rglob('*.uasset'))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    path = lambda obj: obj.get_path_name() if obj else None
    package = lambda value: value.split('.')[0] if value else None
    users = defaultdict(list)
    used_packages = set()
    def prop(obj, name):
        try:
            value = obj.get_editor_property(name)
            return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
        except Exception as exc:
            return {'unavailable': str(exc)}
    try:
        for actor in actors:
            row = {'actor': path(actor), 'label': actor.get_actor_label(), 'class': path(actor.get_class()),
                   'hidden': prop(actor, 'hidden'), 'transform': actor.get_actor_transform().export_text(),
                   'parent': path(actor.get_attach_parent_actor()), 'components': []}
            used_packages.add(package(row['class']))
            for component in actor.get_components_by_class(u.PrimitiveComponent):
                c = {'name': component.get_name(), 'class': path(component.get_class()),
                     'visible': prop(component, 'visible'), 'hidden_in_game': prop(component, 'hidden_in_game'),
                     'collision_enabled': str(component.get_collision_enabled()),
                     'collision_profile': str(component.get_collision_profile_name()),
                     'pawn_response': str(component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)),
                     'transform': component.get_world_transform().export_text()}
                mesh = None
                if isinstance(component, u.StaticMeshComponent):
                    mesh = component.static_mesh
                elif isinstance(component, u.SkeletalMeshComponent):
                    mesh = component.get_skinned_asset()
                c['mesh'] = path(mesh)
                c['materials'] = []
                if isinstance(component, u.MeshComponent):
                    c['materials'] = [path(component.get_material(i)) for i in range(component.get_num_materials())]
                for asset_path in [c['mesh']] + c['materials']:
                    if asset_path:
                        used_packages.add(package(asset_path))
                        users[asset_path].append({'actor': row['label'], 'component': c['name'],
                                                 'visible': c['visible'], 'hidden_in_game': c['hidden_in_game'],
                                                 'actor_hidden': row['hidden'], 'collision': c['collision_enabled']})
                row['components'].append(c)
            report['actors'].append(row)
        registry = u.AssetRegistryHelpers.get_asset_registry()
        # UE 5.8 IAssetRegistry.h:789-809,825-830 exposes synchronous scanning
        # and its completion barrier. Populate unloaded packages too; the first
        # audit's loaded-only registry missed 18 existing mesh packages.
        registry.search_all_assets(True)
        registry.wait_for_completion()
        registry.scan_paths_synchronous(['/Game/Environment/Stage3'], True)
        registry.wait_for_completion()
        report['registry_scan'] = {'search_all_assets_synchronous': True,
                                  'forced_stage3_path_scan': True,
                                  'wait_for_completion_returned': True,
                                  'source': 'UE_5.8 Engine/Source/Runtime/AssetRegistry/Public/AssetRegistry/IAssetRegistry.h:789-830'}
        all_assets = registry.get_assets_by_path('/Game', recursive=True)
        disk_packages = {'/Game/' + p.relative_to(root / 'Content').with_suffix('').as_posix()
                         for p in (root / 'Content/Environment/Stage3').rglob('*.uasset')}
        registry_packages = {str(a.package_name) for a in all_assets
                             if str(a.package_name).startswith('/Game/Environment/Stage3/')}
        missing = sorted(disk_packages - registry_packages)
        report['registry_disk_completeness'] = {
            'scope': '/Game/Environment/Stage3', 'disk_uasset_package_count': len(disk_packages),
            'registry_package_count': len(registry_packages), 'missing_registry_packages': missing,
            'registry_packages_without_disk_uasset': sorted(registry_packages - disk_packages),
            'complete': not missing,
            'interpretation': 'Missing registry packages make unused/unimported classification inconclusive; disk presence alone does not verify imported content.'}
        if missing:
            report['errors'].append({'registry_incomplete': missing})
        scoped = [a for a in all_assets if '/Stage3/' in str(a.package_name) or '/Stage3_' in str(a.package_name)
                  or str(a.package_name).startswith('/Game/Environment/Stage3')
                  or str(a.package_name) in used_packages]
        options = u.AssetRegistryDependencyOptions()
        options.set_editor_property('include_hard_package_references', True)
        options.set_editor_property('include_soft_package_references', True)
        def dependencies(pkg):
            try:
                # Python wraps the bool/out-array API as None when no dependency
                # result exists. That is an empty query result, not iteration failure.
                return sorted(str(x) for x in (registry.get_dependencies(pkg, options) or []))
            except Exception as exc:
                report['errors'].append({'dependency_query': pkg, 'error': str(exc)})
                return []
        # Reachability includes default mesh materials, MI parents/textures and
        # Blueprint asset references, separate from directly assigned slots.
        reachable, queue = set(), list(used_packages | {'/Game/Maps/Stage3'})
        while queue:
            pkg = queue.pop()
            if not pkg or pkg in reachable or not pkg.startswith('/Game/'):
                continue
            reachable.add(pkg)
            queue.extend(x for x in dependencies(pkg) if x not in reachable)
            assert len(reachable) < 20000, 'Unexpectedly large dependency closure'
        report['dependency_reachable_packages'] = sorted(reachable)
        import_sources, names = defaultdict(list), defaultdict(list)
        for data in scoped:
            pkg, name = str(data.package_name), str(data.asset_name)
            asset_path = pkg + '.' + name
            cls = str(data.asset_class_path.asset_name)
            assignments = users.get(asset_path, [])
            visible = [x for x in assignments if x['visible'] is True and x['hidden_in_game'] is False and x['actor_hidden'] is False]
            status = ('assigned_visible' if visible else 'assigned_hidden_or_visibility_unknown' if assignments
                      else 'dependency_only' if pkg in reachable else 'unplaced_or_unreferenced_in_current_stage3')
            r = {'path': asset_path, 'package': pkg, 'class': cls, 'status': status,
                 'direct_assignments': assignments, 'dependencies': dependencies(pkg)}
            names[name].append(asset_path)
            if cls in ('StaticMesh', 'SkeletalMesh', 'MaterialInstanceConstant', 'Material', 'Blueprint', 'AnimSequence'):
                asset = data.get_asset()
                if cls in ('StaticMesh', 'SkeletalMesh', 'AnimSequence'):
                    try:
                        info = asset.get_editor_property('asset_import_data')
                        r['import_filenames'] = list(info.extract_filenames()) if info else []
                        for filename in r['import_filenames']:
                            import_sources[str(Path(filename).resolve()).casefold()].append(asset_path)
                    except Exception as exc:
                        r['import_metadata_unavailable'] = str(exc)
                if cls == 'MaterialInstanceConstant':
                    parent = asset.get_editor_property('parent')
                    r['parent'] = path(parent)
                    r['calibration'] = {
                        'ColorTint_linear': str(u.MaterialEditingLibrary.get_material_instance_vector_parameter_value(asset, 'ColorTint')),
                        'Brightness': u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(asset, 'Brightness')}
                    r['source_metadata'] = u.EditorAssetLibrary.get_metadata_tag(asset, 'Stage3ReadabilitySource')
            report['assets'].append(r)
        for source in report['source_deliveries']['files']:
            exact = import_sources.get(source['file'].casefold(), [])
            named = names.get(source['name'], [])
            source['matching_assets'] = exact or named
            source['match_confidence'] = 'recorded_import_filename' if exact else 'exact_asset_name_only' if named else 'no_match_in_stage3_registry_scope'
            source['import_status'] = 'imported_match' if exact or named else 'not_found_in_scope_requires_review'
        report['status_counts'] = dict(Counter(r['status'] for r in report['assets']))
        report['class_counts'] = dict(Counter(r['class'] for r in report['assets']))
        # These exact mesh names were verified in Production02 v3 and on disk.
        # Suggestions are emitted only if the live registry confirms no direct
        # assignment; old replacements are explicitly on hold, never auto-added.
        proposals = [
            ('SM_S3_LightCandle', '제단실 / 전시실 벽측 낮은 받침', '소형 촛불로 의식·경비 시설의 국부 초점 보강. 통로·동상 밀기축·장치 접근면 밖에만 검토.', 'candidate'),
            ('SM_S3_LightFlame', '전시실 / 창고 정비대 위', 'LightCandle과 한 세트의 작은 불꽃 표현만 검토. 이미 쓰인 촛대 광원과 중복 조명 금지.', 'candidate'),
            ('SM_S3_Pillar_Capital', '제단실 뒤쪽 벽 / 성문 홀 측벽', '소형 벽측 마감 한 곳만 검토. 기존 대형 기둥·도면 외곽·카메라 silhouette를 늘리는 배치는 제외.', 'candidate_conditional'),
            ('SM_S3_WeaponSet', '창고 / 전시실', '분리된 Sword/Axe/Shield/Spear가 이미 쓰일 수 있는 합본. 미배치여도 기존 진열과 중복 추가하지 않고 우선 보류.', 'hold_possible_redundant_combined_mesh'),
            ('SM_S3_ChainConduit', '성문 홀 장치 벽', '신형 기계 장치 체인 커버가 같은 역할을 대체할 수 있음. 연결 근거 없이 구형 부품 재투입 금지.', 'hold_possible_superseded')]
        report['placement_proposals'] = []
        for name, region, reason, disposition in proposals:
            for r in report['assets']:
                if r['path'].rsplit('.', 1)[-1] == name and not r['direct_assignments']:
                    report['placement_proposals'].append({'asset': r['path'], 'live_status': r['status'],
                        'region': region, 'proposal': reason, 'disposition': disposition,
                        'constraints': '승인 후에도 Stage3 전용 보정 MI의 석재/흑철/황동/버건디 체계, Normal/ORM/UV 보존. 실측 통행 폭·고양이 카메라·퍼즐 접촉/이동 범위 유지. 원본/공유 재질 변경 금지.'})
        report['replacement_interpretation'] = 'Hidden assigned meshes are retained-use, not unused. Possible old/combined replacements are labeled hold and require parent/attachment and direct assignment evidence; names alone never prove obsolescence.'
        report['original_actor_set_preserved'] = before_actor_paths == sorted(a.get_path_name() for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
        report['protected_package_bytes_preserved'] = all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
        report['success'] = not report['errors'] and report['original_actor_set_preserved'] and report['protected_package_bytes_preserved']
    except Exception:
        report['errors'].append(traceback.format_exc())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    return report


if __name__ == '__main__':
    main()
