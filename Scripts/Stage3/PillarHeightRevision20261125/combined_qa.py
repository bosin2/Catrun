"""Root-only one-process GPU + three possessed-camera views; import is inert.

Call main() in a NEW disposable unattended full editor with -SaveToUserDir.
No package save. Never run this in the user's editor. Readiness is deferred;
GPU completes and restores MPC before the existing asynchronous PIE capture.
"""
import hashlib
import importlib.util
import json
import os
import time
import traceback
from pathlib import Path

EXPECTED_SHA = '1ebff0f5ef36a6031d0a782fe6817b323d7981f1018a95a2dd86efcc0c50b65c'
VIEWS = [('GateMiddle',(-250,-3400,26.2)),
         ('GateExtreme',(-945,-4545,26.2)),
         ('AnnexBasket',(-200,-2045,26.2))]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    import unreal as u
    root=Path(u.Paths.project_dir()).resolve()
    run=os.environ.get('CATRUN_COMFORT_QA_PASS','01')
    assert run.replace('_','').isalnum()
    out=root/'Saved/Stage3PillarHeightRevision20261125'/('CombinedQA'+run)
    capture_pass='ComfortVisual'+run
    capture_out=root/'Saved/Stage3IntegrationRevision20261125'/capture_pass
    gpu_out=root/'Saved/Stage3PillarHeightRevision20261125'/('RuntimeQAGPU'+run)
    assert not out.exists() and not gpu_out.exists() and not (capture_out/'report.json').exists(),'Use fresh pass identifier'
    ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    le=u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert u.SystemLibrary.is_unattended()
    assert '-savetouserdir' in u.SystemLibrary.get_command_line().lower()
    assert not ed.get_game_world(),'Never attach to a user PIE session'
    out.mkdir(parents=True)
    map_path=root/'Content/Maps/Stage3.umap'
    digest=lambda:hashlib.sha256(map_path.read_bytes()).hexdigest()
    expected=os.environ.get('CATRUN_COMFORT_EXPECTED_SHA',EXPECTED_SHA)
    assert digest()==expected,'Saved Stage3 changed; review before choosing a new expected SHA'
    state={'success':False,'execution_complete':False,'save_count':0,'phase':'startup',
           'map_sha_before':digest(),'expected_sha':expected,'requested_views':VIEWS,
           'gpu_report':str(gpu_out/'report.json'),'visual_report':str(capture_out/'report.json'),
           'fixture':'GPU uses transient SceneCapture/MPC; then real possessed player-camera PIE with fixed cat poses and NPC ticks stopped. Not manual play or basket interaction QA.',
           'started':time.monotonic(),'ticks':0}
    def persist():
        (out/'report.json').write_text(json.dumps({k:v for k,v in state.items() if k!='handle'},indent=2),encoding='utf8')
    def quit_on_error():
        state['error']=traceback.format_exc();state['success']=False
        state['map_sha_after']=digest();persist()
        u.SystemLibrary.execute_console_command(ed.get_editor_world(),'QUIT_EDITOR')
    def start_tick(_dt):
        state['ticks']+=1
        if state['ticks']<30 or time.monotonic()-state['started']<3:return
        u.unregister_slate_post_tick_callback(state['handle'])
        try:
            assert le.load_level('/Game/Maps/Stage3')
            u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
            state['phase']='gpu';persist()
            os.environ['CATRUN_PILLAR_HEIGHT_GPU_PASS']=run
            os.environ['CATRUN_PILLAR_HEIGHT_GPU_QUIT']='0'
            gpu=load(root/'Scripts/Stage3/PillarHeightRevision20261125/gpu_occlusion.py','comfort_gpu')
            report=gpu.main()
            assert report['success'] and report['execution_complete']
            state['gpu_passed']=True
            assert digest()==expected
            state['phase']='possessed_camera';persist()
            os.environ['CATRUN_STAGE3_AFTER_CAPTURE_PASS']=capture_pass
            # capture_followup imports the proven PIE state machine and installs
            # its final readback hook. Override its three positions synchronously
            # before another Slate callback can capture an old view.
            capture=load(root/'Scripts/Stage3/IntegrationRevision20261125/capture_followup.py','comfort_followup')
            capture.capture.c.VIEWS=list(VIEWS)
            c=capture.capture.c
            old_tick=capture.tick
            u.unregister_slate_post_tick_callback(c.S['handle'])
            def capture_tick(dt):
                try:
                    old_tick(dt)
                    if c.S['phase']=='shutdown' and not ed.get_game_world():
                        state['map_sha_after']=digest()
                        state['visual_passed']=bool(c.S.get('success'))
                        state['final_readback']=c.S.get('final_readback')
                        state['captured_views']=c.S.get('views',[])
                        actual=[row['name'] for row in state['captured_views']]
                        state['image_files_present']=all((capture_out/(name+'_Lit.png')).exists() for name,_ in VIEWS)
                        state['execution_complete']=True
                        state['success']=bool(state['gpu_passed'] and state['visual_passed'] and
                            state['map_sha_after']==expected and state['final_readback'] and
                            state['final_readback']['map_sha256']==expected and
                            actual==[name for name,_ in VIEWS] and state['image_files_present'])
                        state['phase']='complete_pending_human_image_review' if state['success'] else 'failed'
                        persist()
                except Exception:
                    u.unregister_slate_post_tick_callback(c.S['handle'])
                    quit_on_error()
            c.S['handle']=u.register_slate_post_tick_callback(capture_tick)
        except Exception:quit_on_error()
    persist()
    state['handle']=u.register_slate_post_tick_callback(start_tick)
    return state


if __name__=='__main__':
    main()
