"""Import the native Stage3 hall capture for the existing chapter menu."""
from pathlib import Path
import unreal as u
root=Path(u.Paths.project_dir()).resolve()
source=root/'Saved/Stage3Integration20261125/Visual/GateHall.png'
assert source.is_file()
task=u.AssetImportTask();task.filename=str(source)
task.destination_path='/Game/UI/Continue/Thumbnails';task.destination_name='T_Chapter_Stage3'
task.automated=True;task.replace_existing=True;task.save=True
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
tex=u.EditorAssetLibrary.load_asset('/Game/UI/Continue/Thumbnails/T_Chapter_Stage3')
assert tex
tex.set_editor_property('compression_settings',u.TextureCompressionSettings.TC_EDITOR_ICON)
tex.set_editor_property('mip_gen_settings',u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
assert u.EditorAssetLibrary.save_loaded_asset(tex)
print('STAGE3_THUMBNAIL_OK')
