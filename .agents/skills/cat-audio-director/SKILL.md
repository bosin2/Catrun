---
name: cat-audio-director
description: Coordinate Catrun game audio from one request through parallel BGM and SFX planning, authorized Suno generation, FFmpeg processing, safe Unreal import, and QA.
---

# Cat Audio Director

Work from the Catrun project root. Read `Scripts/CatAudioDirector/README.md` for
installed commands, verified capabilities, and authentication status. The main
agent is the director; do not spawn another director recursively.

## One request, several roles

1. Inspect the current project, dirty files, source GDD, existing sound assets,
   and `python Scripts/CatAudioDirector/cat_audio.py doctor`. Infer a small,
   concrete asset list from the request. Distinguish audible presentation from
   gameplay sound events; do not change AI hearing or sound propagation.
2. Delegate independent planning to `cat_audio_bgm` and `cat_audio_sfx` in parallel.
   Give each its own asset IDs and the user's constraints. They return proposals
   with `id`, `kind`, `prompt`, `duration_seconds`, and `loop`, plus uncertainty and
   existing source candidates. They do not spend credits or edit game assets.
3. Merge both results into a `brief.json` in a new work directory under
   `Saved/CatAudioDirector`. The top-level contract is `{"assets": [...]}`.
   `kind` is `bgm` or `sfx`; IDs are unique safe ASCII identifiers. Use absolute
   `source_path` values for local inputs. Read the installed script's validation
   rules before constructing optional fields. Keep the user's natural-language
   brief and the subagent results with the run evidence.
4. Resolve inputs using the provider procedure below. If credentials or approval
   are missing, complete planning and mock testing while clearly marking generated
   tones as test signals. A mock run is not finished music or finished SFX.
5. Delegate `cat_audio_edit` to run the deterministic pipeline with `--mode mock`
   or `--mode local`. Wait for its manifest and QA before integration. One editor
   owns a run directory; never let multiple agents modify the same manifest.
6. Delegate `cat_audio_unreal` as the sole Unreal writer. Run bridge inspection
   first. A user request to apply audio authorizes new isolated imports; it does
   not authorize replacing assets or rewiring existing Blueprints. Use the bridge
   apply command only after its entire import plan passes validation. Mock import
   additionally requires the explicit `--allow-mock` flag and test intent. Do not
   silently treat import as runtime playback or gameplay integration.
7. Delegate `cat_audio_qa` to rerun QA, inspect the reports, and compare the
   requested IDs with completed files and imported assets. The director collects
   all results and reports completed work, tests, and exact remaining blockers.

Limit simultaneous workers to the configured slots; use sequential waves.
Custom agents inherit the parent permissions and MCP connections. Their role
instructions are not a security boundary. If the current desktop session does
not expose the custom role selector, read the matching `.codex/agents/*.toml`
and pass its instructions to a supported general-purpose subagent. Record that
fallback; do not claim the native custom-role loader was tested. A new chat opened
on the Catrun project may be needed to discover newly installed project skills.

## Suno: discover, authorize, generate, retrieve

The configured official endpoint is `https://api.suno.com/mcp`. Use Codex's
OAuth login flow when the user is ready; do not ask for passwords or copy tokens
into project files. Authentication and provider access must be demonstrated by
an authenticated read, not just by the presence of a configuration entry.
The user deferred connection during setup: the Suno server is initially disabled.
Keep mock/local workflows working; do not resume login unless the user requests it.
After requested login, use `inspect_suno.py` to verify tools before enabling the
project MCP server. See README for the CLI-specific login command.

Discover the current tools and their input schemas. Verify account/credit reads,
music generation, sound-effect generation, status polling, and download support
individually. Never invent a `sounds-create` tool, undocumented API route, or
response field. A web product feature does not prove MCP support. If SFX generation
or downloads are unavailable, state that limitation and accept user-provided local
files. Do not substitute a paid provider without authorization.

Before a paid call, prepare the exact asset batch, tool arguments, expected cost
or stated uncertainty, maximum credits, and maximum calls. Request user approval
only for that concrete batch. Do not infer approval from a previous login or a
general instruction to build the system. The director alone submits paid calls
after approval; BGM/SFX workers prepare requests. Record approval scope, provider
job IDs, call count, and returned status in a generation ledger without secrets.
Do not retry a generation submission after an ambiguous timeout: reconcile its
job status first to avoid duplicate charges. Poll existing jobs with bounded
retries. Stop at the approved limit or an unrecoverable error.

Download only URLs returned by verified provider results using the installed
download helper when available, preserving provenance and hashes. Do not log
signed query strings or credentials. Retain original downloads unchanged and
pass absolute paths into local mode. Failed or unavailable downloads remain
explicitly incomplete in the manifest.

## Commands and evidence

```powershell
python Scripts/CatAudioDirector/cat_audio.py doctor
python Scripts/CatAudioDirector/cat_audio.py run --brief <brief.json> --mode mock
python Scripts/CatAudioDirector/cat_audio.py run --brief <brief.json> --mode local
python Scripts/CatAudioDirector/cat_audio.py qa --run <run-directory>
python Scripts/CatAudioDirector/unreal_bridge.py inspect --output <report.json>
python Scripts/CatAudioDirector/unreal_bridge.py import --plan <import_plan.json> --apply
```

Use each script's `--help` as the installed command authority. The pipeline writes
`manifest.json`, `import_plan.json`, `final/*.wav`, and `logs.jsonl` under
`Saved/CatAudioDirector/<run_id>`. Default targets are 48 kHz PCM16 WAV, stereo BGM
at -18 LUFS, mono SFX at -20 LUFS. Numeric QA does not certify artistic quality or
musical seamlessness: report loop boundary measurements and listening-review
limitations honestly. A failed run must not be imported as complete.

New imports belong only under `/Game/Audio/CatAudioDirector/<run_id>`. Preserve
source assets, maps, dirty packages, and existing bindings. Sound Cue or MetaSound
authoring is permitted only if the installed tools and actual engine schema have
been verified for that operation; otherwise list it as unsupported. Blender MCP
is optional and unchanged by this workflow.
