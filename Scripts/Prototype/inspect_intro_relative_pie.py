"""Run the temporary binding probe with sequence-relative binding IDs."""
import unreal
from pathlib import Path
source = (Path(unreal.Paths.project_dir())/'Scripts/Prototype/inspect_intro_rebound_pie.py').read_text()
source = source.replace("bid=unreal.MovieSceneObjectBindingID();bid.set_editor_property('guid',b.get_id())", 'bid=player.get_sequence().get_binding_id(b)')
source = source.replace("binding=unreal.MovieSceneObjectBindingID()\n                    binding.set_editor_property('guid',b.get_id())", 'binding=player.get_sequence().get_binding_id(b)')
source = source.replace("row['bindings']={}", "row['camera_actors']=[a.get_path_name() for a in actors if isinstance(a,unreal.CameraActor)]\n                row['bindings']={}")
source = source.replace('for b in player.get_sequence().get_bindings():\n                        target=', 'for b in player.get_sequence().get_possessables():\n                        target=')
source = source.replace('intro-pie-rebound','intro-pie-relative').replace('intro-rebound-','intro-relative-')
exec(compile(source, 'inspect_intro_relative_pie', 'exec'))
