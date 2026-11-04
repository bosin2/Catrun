"""Run with UnrealEditor-Cmd -run=pythonscript -script=<this file>. Does not save assets."""
import json
from pathlib import Path

import unreal


settings_class = unreal.load_class(None, "/Script/AsyncLoadingScreen.LoadingScreenSettings")
assert settings_class, "AsyncLoadingScreen module did not load"
settings = unreal.get_default_object(settings_class)
screen = settings.get_editor_property("DefaultLoadingScreen")
widget = screen.get_editor_property("LoadingWidget")
brush = widget.get_editor_property("ThrobberSettings").get_editor_property("Image")
texture = brush.get_editor_property("ResourceObject")
report = {
    "layout": str(screen.get_editor_property("Layout")),
    "text": str(widget.get_editor_property("LoadingText")),
    "icon": texture.get_path_name() if texture else None,
    "minimum_display_time": screen.get_editor_property("MinimumLoadingScreenDisplayTime"),
    "auto_complete": screen.get_editor_property("bAutoCompleteWhenLoadingCompletes"),
    "manual_stop": screen.get_editor_property("bWaitForManualStop"),
    "overlay": screen.get_editor_property("bShowWidgetOverlay"),
}
assert ".ALSL_CENTER" in report["layout"], report
assert report["text"] == "불러오는 중…", report
assert report["icon"] == "/AsyncLoadingScreen/Default/Icon/icon-cat-print.icon-cat-print", report
assert report["minimum_display_time"] < 0, report
assert report["auto_complete"] and report["overlay"] and not report["manual_stop"], report
report["success"] = True
output = Path(unreal.Paths.project_saved_dir()) / "Loading" / "settings-verification.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("CATRUN_LOADING_SETTINGS_OK " + json.dumps(report, ensure_ascii=False))
