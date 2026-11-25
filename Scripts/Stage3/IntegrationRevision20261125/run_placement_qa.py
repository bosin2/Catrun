import importlib.util
import os
from pathlib import Path
import unreal as u
root=Path(u.Paths.project_dir()).resolve()
os.environ['CATRUN_STAGE3_PLACEMENT_QA_QUIT']='1'
spec=importlib.util.spec_from_file_location('stage3_placement_runtime',root/'Scripts/Stage3/PlacementRevision20261125/runtime_qa.py')
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
qa.main()
