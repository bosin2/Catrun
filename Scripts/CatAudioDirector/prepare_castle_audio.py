"""Prepare the licensed Catrun castle audio batch for cat_audio.py local mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cat_audio import RATE, Runner, find_tool, probe, save_json, sha256, validate_brief


# Ceilings measured against the edited input levels. Leave room for the
# finish pipeline's integrated-loudness gain on these transient-heavy clips.
PEAK_CEILING_DBFS = {
    'BGM_Stage1': -2.4,
    'ArmorStep_A': -31.5,
    'ArmorStep_B': -27.5,
    'ArmorClank': -14,
    'DoorClose': -16,
    'GateStop': -22.8,
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def trim(start, duration):
    start_sample = round(start * RATE)
    end_sample = start_sample + round(duration * RATE)
    return f'atrim=start_sample={start_sample}:end_sample={end_sample},asetpts=PTS-STARTPTS'


def pitch(ratio):
    return f'asetrate={round(RATE * ratio)},aresample={RATE}'


def edit_recipe(item):
    name = item['id']
    duration = item['duration_seconds']
    recommendation = item.get('recommended_preparation', {})
    start = item.get('trim_start_seconds', 0)
    duration = recommendation.get('duration_seconds_after_trim', duration)
    start = recommendation.get('trim_start_seconds', start)
    if name == 'BGM_Stage2':
        duration = recommendation['duration_seconds_preserving_full_period']

    overlap = min(.1, duration / 8) if item['loop'] else 0
    prepared_duration = duration + overlap
    primary = trim(start, prepared_duration)
    secondary = None
    if name in ('Bell_A', 'Bell_B'):
        primary += f',afade=t=out:st={duration - .08:.6f}:d=0.08'
    elif name == 'ArmorClank':
        primary = f'{pitch(.96)},lowpass=f=5400,{primary}'
    elif name == 'GateStop':
        primary = f'{pitch(.8)},lowpass=f=2200,{primary}'
    elif name == 'GateMove':
        primary = trim(.1, prepared_duration)
        secondary = f'{trim(.01, prepared_duration)},volume=-8dB'
    elif name == 'PortalHum':
        primary += ',highpass=f=32'
        secondary = f'{trim(.25, prepared_duration)},highpass=f=55,volume=-12dB'
    elif name == 'StatueSeat':
        primary = trim(.32, duration)
        secondary = (
            f'{pitch(.7)},lowpass=f=450,{trim(0, .16)},afade=t=out:st=0.11:d=0.05,'
            f'volume=-12dB,adelay=600:all=1,apad=whole_dur={duration}'
        )

    layout = 'stereo' if item['kind'] == 'bgm' else 'mono'
    resample = f'aresample={RATE},aformat=sample_fmts=fltp:channel_layouts={layout}'
    ceiling = PEAK_CEILING_DBFS.get(name)
    output = 'trimmed' if ceiling is not None else 'out'
    if name == 'BGM_Stage2':
        graph = (
            f'[0:a]{resample},asplit=2[main][head];'
            f'[main]{trim(0, duration)}[body];[head]{trim(0, overlap)}[extra];'
            f'[body][extra]concat=n=2:v=0:a=1[{output}]'
        )
    elif secondary:
        graph = (
            f'[0:a]{resample},{primary}[main];[1:a]{resample},{secondary}[layer];'
            f'[main][layer]amix=inputs=2:duration=first:normalize=0,volume=0.5[{output}]'
        )
    else:
        graph = f'[0:a]{resample},{primary}[{output}]'
    if ceiling is not None:
        # Gain-stage in floating point because alimiter's minimum limit is -24 dBFS.
        gain = -6 - ceiling
        graph += (
            f';[{output}]aresample={RATE * 4},volume={gain}dB,alimiter=limit=0.50118723:'
            f'attack=2:release=35:level=false:latency=true,volume={-gain}dB,aresample={RATE}[out]'
        )
    return duration, prepared_duration, graph


def licensed_input(path, record, expected_hash):
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(f'Licensed source hash changed: {path}')
    return {
        'path': str(path),
        'sha256': actual_hash,
        'license': record['license'],
        'license_url': record['license_url'],
        'creator': record.get('artist', record.get('author')),
        'landing_url': record['landing_url'],
    }


def source_records(item, base, sfx_sources):
    source = Path(item['source_path'])
    if item['kind'] == 'bgm':
        record = item['source_candidate']
        return [licensed_input(source, record, record['source_sha256'])]

    def sfx_input(path, record, entry):
        source_details = record['extracted'][entry] if entry else record
        return licensed_input((base / path).resolve(), record, source_details['sha256'])

    records = [sfx_input(source, sfx_sources[item['source']], item.get('entry'))]
    if item.get('secondary_source_path'):
        record = sfx_sources[item['secondary_source']]
        records.append(sfx_input(item['secondary_source_path'], record, item.get('secondary_entry')))
    return records


def prepare(brief_path, output):
    brief_hash = sha256(brief_path)
    brief = read_json(brief_path)
    items = validate_brief(brief, brief_path.parent, 'local')
    sfx_sources = read_json(brief_path.with_name('sfx_proposals.json'))['sources']
    original_inputs = [source_records(item, brief_path.parent, sfx_sources) for item in items]
    ffmpeg = find_tool('ffmpeg')
    find_tool('ffprobe')
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output / 'logs.jsonl')
    version = runner.call([ffmpeg, '-version'], 'ffmpeg:version').stdout.splitlines()[0]
    base_command = [
        ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y',
        '-filter_complex_threads', '1',
    ]
    derived_items = []
    edit_rows = []
    for item, inputs in zip(items, original_inputs, strict=True):
        name = item['id']
        path = output / f'{name}.wav'
        duration, needed, graph = edit_recipe(item)
        arguments = base_command.copy()
        for source in inputs:
            arguments += ['-i', source['path']]
        arguments += [
            '-filter_complex', graph, '-map', '[out]', '-map_metadata', '-1',
            '-bitexact', '-c:a', 'pcm_f32le', str(path),
        ]
        runner.call(arguments, f'{name}:prepare')
        stream, available = probe(path, runner)
        if abs(available - needed) > 1 / RATE or int(stream['sample_rate']) != RATE:
            raise ValueError(f'{name}: prepared {available:.6f}s, expected {needed:.6f}s at {RATE} Hz')
        if stream['channels'] != item['channels']:
            raise ValueError(f'{name}: prepared channel count differs from the brief')

        edit_rows.append({
            'id': name,
            'inputs': inputs,
            'filter_graph': graph,
            'prepared_path': str(path),
            'prepared_sha256': sha256(path),
            'prepared_duration_seconds': available,
            'output_duration_seconds': duration,
        })
        derived_items.append({
            **item, 'original_source_path': item['source_path'], 'source_path': str(path),
            'duration_seconds': duration,
        })

    if sha256(brief_path) != brief_hash:
        raise ValueError(f'Original brief changed during preparation: {brief_path}')
    for row in edit_rows:
        for source in row['inputs']:
            if sha256(source['path']) != source['sha256']:
                raise ValueError(f'Original source changed during preparation: {source["path"]}')

    derived_brief = output / 'brief.json'
    edit_report = output / 'edit_report.json'
    save_json(derived_brief, {**brief, 'assets': derived_items, 'edit_report': str(edit_report)})
    save_json(edit_report, {
        'source_brief_path': str(brief_path),
        'source_brief_sha256': brief_hash,
        'prepared_brief_path': str(derived_brief),
        'prepared_brief_sha256': sha256(derived_brief),
        'ffmpeg': version,
        'assets': edit_rows,
    })
    return derived_brief


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='New directory, defaulting to Prepared beside the brief')
    args = parser.parse_args()
    brief = args.brief.resolve()
    output = args.output.resolve() if args.output else brief.with_name('Prepared')
    print(prepare(brief, output))


if __name__ == '__main__':
    main()
