"""Observe OS Start/SpaceBar inputs; never start PIE, ring, move, or rebind actors."""
import json
import time
import traceback
from pathlib import Path
import unreal

manual_out = Path(unreal.Paths.project_saved_dir()) / 'Prototype20261104/CanonicalManualStart1'
manual_out.mkdir(parents=True, exist_ok=True)
assert not (manual_out / 'observations.json').exists(), 'Preserve prior evidence; choose a new run folder'
manual_editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
manual_probe = {'armed': time.monotonic(), 'samples': [], 'menu_seen': False, 'shots': []}

def save_manual(final=False, error=None):
    data = {k: v for k, v in manual_probe.items() if k != 'handle'}
    data.update(final=final, error=error)
    (manual_out / ('observations.json' if final else 'progress.json')).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def finish_manual(error=None):
    unreal.unregister_slate_post_tick_callback(manual_probe['handle'])
    save_manual(True, error)
    print('CANONICAL_MANUAL_OBSERVER_FINISHED', error)

def observe_manual(delta):
    try:
        now = time.monotonic()
        if (manual_out / 'finish.txt').exists():
            finish_manual(); return
        if now - manual_probe['armed'] > 200:
            finish_manual('Observer timeout'); return
        if now - manual_probe.get('last', 0) < .12: return
        manual_probe['last'] = now
        world = manual_editor.get_game_world()
        if not world: return
        pc = unreal.GameplayStatics.get_player_controller(world, 0)
        cat = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not pc: return
        row = {'epoch': time.time(), 'world': world.get_name(), 'move_ignored': pc.is_move_input_ignored()}
        view = pc.get_view_target()
        row['view'] = view.get_name() if view else None
        if world.get_name() == 'MainMenu': manual_probe['menu_seen'] = True
        if cat:
            p = cat.get_actor_location(); row['location'] = [p.x, p.y, p.z]
            mesh = cat.get_component_by_class(unreal.SkeletalMeshComponent)
            if mesh:
                row['anim_mode'] = str(mesh.get_animation_mode())
                instance = mesh.get_anim_instance()
                row['anim_class'] = instance.get_class().get_name() if instance else None
            actions = cat.get_component_by_class(unreal.CatrunBasketInteractionComponent)
            if actions: row['busy'] = actions.get_editor_property('Busy')
        notices = [w for w in unreal.WidgetLibrary.get_all_widgets_of_class(world, unreal.CatrunNoticeWidget, False)
                   if w.is_in_viewport() and w.get_visibility() != unreal.SlateVisibility.COLLAPSED]
        row['notices'] = [str(t.get_text()) for t in unreal.ObjectIterator(unreal.TextBlock)
                          if any(t.get_typed_outer(unreal.CatrunNoticeWidget) == w for w in notices)]
        if world.get_name() == 'Tutorial':
            manual_probe.setdefault('tutorial_entered', now)
            elapsed = now - manual_probe['tutorial_entered']; row['tutorial_elapsed'] = elapsed
            intro = next((a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                          if a.get_class().get_name() == 'BP_TutorialIntro_C'), None)
            player = intro.get_editor_property('IntroPlayer') if intro else None
            row['intro_playing'] = bool(player and player.is_playing())
            if elapsed > 25 and not row['intro_playing'] and not row['move_ignored']:
                manual_probe['intro_completed'] = True
            for mark in [4, 16, 24]:
                if elapsed >= mark and mark not in manual_probe['shots']:
                    manual_probe['shots'].append(mark)
                    unreal.SystemLibrary.execute_console_command(world, 'Shot showui filename="' +
                        str(manual_out / ('intro-' + str(mark) + '.png')).replace('\\', '/') + '"')
                    break
            if row['notices'] and 'notice' not in manual_probe['shots']:
                manual_probe['shots'].append('notice')
                unreal.SystemLibrary.execute_console_command(world, 'Shot showui filename="' +
                    str(manual_out / 'physical-bell-denied.png').replace('\\', '/') + '"')
        manual_probe['samples'].append(row)
        if now - manual_probe.get('last_saved', 0) > 2:
            manual_probe['last_saved'] = now; save_manual()
    except Exception:
        finish_manual(traceback.format_exc())

manual_probe['handle'] = unreal.register_slate_post_tick_callback(observe_manual)
print('CANONICAL_MANUAL_OBSERVER_ARMED')
