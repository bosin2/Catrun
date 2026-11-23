"""Remove placed Stage2 recovery buttons and update the practice hint in the loaded map."""
import gc
import unreal as u


PRACTICE_MESSAGE = '동상 뒤에 서서 발판 쪽으로 이동키를 누르세요. 동상이 발판에 놓이면 철문이 열려요.'
LEGACY_PRACTICE_MESSAGE = '동상 뒤에서 이동키를 누르면 밀 수 있어요. 잘못 밀었다면 푸른 복구 장치 가까이에서 F를 누르세요. 이 방의 동상만 돌아갑니다.'


def remove_reset_buttons(actors, subsystem):
    removed = []
    for actor in list(actors):
        if isinstance(actor, u.CatrunPuzzleReset):
            removed.append(actor.get_actor_label())
            assert subsystem.destroy_actor(actor), removed[-1]
    return removed


def update_practice_hint(actors):
    changed = False
    for actor in actors:
        if (isinstance(actor, u.CatrunGuidanceZone)
                and actor.get_actor_label() == 'Guide_StatuePractice'
                and str(actor.get_editor_property('Message')) == LEGACY_PRACTICE_MESSAGE):
            actor.set_editor_property('Message', PRACTICE_MESSAGE)
            changed = True
    return changed


def main():
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    for name in ('Stage2', 'SoundTest_Stage2'):
        assert levels.load_level('/Game/Maps/' + name)
        actors = list(subsystem.get_all_level_actors())
        changed = update_practice_hint(actors)
        removed = remove_reset_buttons(actors, subsystem)
        if changed or removed:
            assert levels.save_current_level()
        del actors
        gc.collect()


if __name__ == '__main__':
    main()
