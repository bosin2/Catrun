"""/Game 에셋 전체의 로드·의존성·재질·Nanite 상태를 읽기 전용으로 점검한다(-run=pythonscript)."""
import json
import os
import traceback
from pathlib import Path

import unreal as u

OUT = Path(os.environ['CATRUN_REGRESSION_OUT'])
R = {'scope': __doc__, 'counts': {}, 'load_failed': [], 'missing_dependencies': {}, 'blueprint_errors': [],
     'null_mesh_material': [], 'nanite_unsupported_material': [], 'material_issues': [], 'null_skeleton': [],
     'redirectors': [], 'skipped_classes': {}, 'success': False}
SKIP = {'Texture2D', 'TextureCube', 'SoundWave', 'World', 'MapBuildDataRegistry', 'VolumeTexture'}


def persist():
    (OUT / 'report.json').write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def blend(mat):
    try:
        return mat.get_blend_mode().name if isinstance(mat, u.MaterialInterface) else None
    except Exception:
        return None


def inspect(path, asset):
    if isinstance(asset, u.StaticMesh):
        nanite = False
        try:
            nanite = asset.get_editor_property('nanite_settings').get_editor_property('enabled')
        except Exception:
            pass
        for i, slot in enumerate(asset.get_editor_property('static_materials')):
            m = slot.get_editor_property('material_interface')
            if not m:
                R['null_mesh_material'].append('%s[%d]' % (path, i))
            elif nanite and blend(m) not in (None, 'BLEND_OPAQUE', 'BLEND_MASKED'):
                R['nanite_unsupported_material'].append('%s[%d] %s %s' % (path, i, m.get_path_name(), blend(m)))
    elif isinstance(asset, u.SkeletalMesh):
        if not asset.get_editor_property('skeleton'):
            R['null_skeleton'].append(path)
        for i, slot in enumerate(asset.get_editor_property('materials')):
            if not slot.get_editor_property('material_interface'):
                R['null_mesh_material'].append('%s[%d]' % (path, i))
    elif isinstance(asset, u.AnimSequenceBase):
        try:
            if not asset.get_editor_property('skeleton'):
                R['null_skeleton'].append(path)
        except Exception:
            pass
    elif isinstance(asset, u.MaterialInstanceConstant):
        if not asset.get_editor_property('parent'):
            R['material_issues'].append(path + ' : no parent')


def main():
    reg = u.AssetRegistryHelpers.get_asset_registry()
    reg.scan_paths_synchronous(['/Game'], True)
    reg.wait_for_completion()
    data = [d for d in reg.get_assets_by_path('/Game', True) or []]
    R['total'] = len(data)
    opts = u.AssetRegistryDependencyOptions(include_soft_package_references=False,
                                            include_hard_package_references=True,
                                            include_searchable_names=False, include_soft_management_references=False,
                                            include_hard_management_references=False)
    known = {str(d.package_name) for d in data}
    seen = set()
    for n, d in enumerate(data):
        cls = str(d.asset_class_path.asset_name)
        R['counts'][cls] = R['counts'].get(cls, 0) + 1
        pkg = str(d.package_name)
        if cls == 'ObjectRedirector':
            R['redirectors'].append(pkg)
        if pkg not in seen:
            seen.add(pkg)
            missing = []
            for dep in reg.get_dependencies(pkg, opts) or []:
                dep = str(dep)
                if dep.startswith('/Script/') or dep in known:
                    continue
                if dep.startswith('/Game') or not reg.get_assets_by_package_name(dep, True):
                    if not u.EditorAssetLibrary.does_asset_exist(dep):
                        missing.append(dep)
            if missing:
                R['missing_dependencies'][pkg] = missing
        if cls in SKIP:
            R['skipped_classes'][cls] = R['skipped_classes'].get(cls, 0) + 1
            continue
        try:
            asset = d.get_asset()
            if not asset:
                R['load_failed'].append(pkg)
            else:
                inspect(pkg, asset)
            del asset
        except Exception:
            R['load_failed'].append(pkg + ' : ' + traceback.format_exc(limit=1))
        if n % 120 == 119:
            u.SystemLibrary.collect_garbage()
            persist()
    R['success'] = not (R['load_failed'] or R['missing_dependencies'])
    persist()
    u.log('REGRESSION_ASSET_SWEEP_DONE %d' % len(data))


try:
    main()
except Exception:
    R['error'] = traceback.format_exc()
    persist()
    raise
