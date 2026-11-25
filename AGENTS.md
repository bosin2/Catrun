# Catrun project instructions

## Cat Audio Director

These instructions apply to audio production and Cat Audio Director requests only.
For those requests, read `.agents/skills/cat-audio-director/SKILL.md` and act as the
single director. Delegate independent BGM and SFX work to parallel subagents, collect
their results, and then run editing, Unreal integration, and QA in dependency order.
The user should not need to assign each role separately.

Preserve existing source, assets, Blueprints, cinematics, settings, and uncommitted
work. Read `Docs/Design/GameDesign_Source.md` for gameplay intent before selecting
audio events. Audible assets must not change gameplay sound propagation or enemy
perception rules. Keep new tool code in `Scripts/CatAudioDirector`, run artifacts in
`Saved/CatAudioDirector`, and imported assets in a new per-run folder under
`/Game/Audio/CatAudioDirector`. Never replace an existing asset implicitly.

Suno login and paid generation are separate steps. Before spending credits, obtain
explicit approval for a concrete batch and credit limit; authentication alone is
not spending approval. Discover the live provider tools and schemas before use.
If a provider or feature cannot be verified, use mock/local mode and report the gap.
Blender is optional and must not block an audio-only task.
