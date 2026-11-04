"""Replace only the active verification observer after fixing its completion guard."""
import unreal,gc
from pathlib import Path
script=(Path(unreal.Paths.project_dir())/'Scripts/Prototype/task4c_tutorial_retry.py').read_text(encoding='utf8')
definition=script[script.index('def tick(dt):'):script.index("s['handle']=unreal.register_slate_post_tick_callback(tick)")]
for candidate in gc.get_objects():
 if callable(candidate) and getattr(candidate,'__name__','')=='tick':
  scope=getattr(candidate,'__globals__',{})
  if str(scope.get('OUT','')).replace('\\','/').endswith('/Task4c/TutorialRetry'):
   unreal.unregister_slate_post_tick_callback(scope['s']['handle']);exec(compile(definition,'task4c_tutorial_retry.py','exec'),scope);scope['s']['handle']=unreal.register_slate_post_tick_callback(scope['tick']);print('RETRY_OBSERVER_GUARD_FIXED');break
