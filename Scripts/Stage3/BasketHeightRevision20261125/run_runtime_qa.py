"""Disposable-editor entry point; importing this module starts nothing."""
import importlib.util
import os
from pathlib import Path


def main():
    import unreal as u
    assert '-SaveToUserDir' in u.SystemLibrary.get_command_line(), 'Disposable editor only'
    root = Path(u.Paths.project_dir()).resolve()
    os.environ['CATRUN_STAGE3_PLACEMENT_QA_QUIT'] = '1'
    spec = importlib.util.spec_from_file_location('stage3_basket_height_runtime',
                    root / 'Scripts/Stage3/BasketHeightRevision20261125/runtime_qa.py')
    global QA
    QA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(QA)
    return QA.main()


if __name__ == '__main__':
    main()
