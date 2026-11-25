"""Cat Audio Director: deterministic, offline audio finishing and QA (Python 3.11+)."""
from __future__ import annotations

import argparse
from array import array
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import wave

PROJECT = Path(__file__).resolve().parents[2]
RATE = 48000
ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def find_tool(name):
    override = os.environ.get('CAT_AUDIO_' + name.upper())
    if override:
        path = Path(override)
        if not path.is_file():
            raise ValueError(f'{name} override does not exist')
        return str(path.resolve())
    found = shutil.which(name)
    if found:
        return found
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/WinGet/Packages'
    matches = sorted(base.glob(f'Gyan.FFmpeg*/**/{name}.exe')) if base.is_dir() else []
    if matches:
        return str(matches[-1])
    raise RuntimeError(f'{name} missing. Run setup.ps1 or set CAT_AUDIO_{name.upper()}.')


class Runner:
    def __init__(self, log=None, attempts=2):
        self.log = Path(log) if log else None
        self.attempts = attempts
        self.lock = threading.Lock()

    def event(self, event, **data):
        if self.log:
            with self.lock, self.log.open('a', encoding='utf-8') as out:
                out.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), 'event': event, **data}, ensure_ascii=False) + '\n')

    def call(self, args, label, timeout=180):
        # Shell is never used. Only local FFmpeg/FFprobe jobs are retried, never paid requests.
        for attempt in range(1, self.attempts + 1):
            self.event('start', job=label, attempt=attempt)
            try:
                result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False)
                if result.returncode:
                    raise RuntimeError(result.stderr[-1600:])
                self.event('complete', job=label, attempt=attempt)
                return result
            except (subprocess.TimeoutExpired, OSError, RuntimeError) as error:
                self.event('failure', job=label, attempt=attempt, error=str(error)[-1600:])
                if attempt == self.attempts:
                    raise
                time.sleep(0.25 * attempt)


def validate_brief(brief, base, mode):
    assets = brief.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 64:
        raise ValueError('assets must contain 1..64 items')
    seen, validated = set(), []
    for original in assets:
        item = dict(original)
        name = item.get('id', '')
        if not isinstance(name, str) or not ID_RE.fullmatch(name) or name.casefold() in seen:
            raise ValueError('Asset IDs must be unique, safe ASCII names (case insensitive)')
        seen.add(name.casefold())
        kind = item.get('kind')
        if kind not in ('bgm', 'sfx'):
            raise ValueError(f'{name}: kind must be bgm or sfx')
        duration = item.get('duration_seconds')
        if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not math.isfinite(duration) or not 0.05 <= duration <= 600:
            raise ValueError(f'{name}: duration_seconds must be finite, 0.05..600')
        loop = item.get('loop', kind == 'bgm')
        if not isinstance(loop, bool):
            raise ValueError(f'{name}: loop must be boolean')
        item.update(loop=loop, duration_seconds=float(duration), channels=2 if kind == 'bgm' else 1,
                    target_lufs=-18.0 if kind == 'bgm' else -20.0)
        if mode == 'local':
            source = item.get('source_path')
            if not isinstance(source, str) or not source or '://' in source:
                raise ValueError(f'{name}: local source_path required; URLs are not accepted')
            source = (base / source).resolve()
            if not source.is_file() or source.stat().st_size > 1024 ** 3:
                raise ValueError(f'{name}: source missing or larger than 1 GiB')
            item['source_path'] = str(source)
        validated.append(item)
    return validated


def mock_wave(path, duration, channels, kind):
    """Synthetic fixture ONLY, never represented as generated music or production SFX."""
    count = round(duration * RATE)
    with wave.open(str(path), 'wb') as out:
        out.setparams((channels, 2, RATE, count, 'NONE', 'not compressed'))
        for start in range(0, count, RATE):
            values = array('h')
            for n in range(start, min(count, start + RATE)):
                t = n / RATE
                envelope = 0.6 + 0.4 * math.exp(-t * 3) if kind == 'sfx' else 1
                value = 0.16 * envelope * (math.sin(2 * math.pi * 220 * t) + .3 * math.sin(2 * math.pi * 431 * t))
                for _ in range(channels):
                    values.append(round(value * 32767))
            if sys.byteorder != 'little':
                values.byteswap()
            out.writeframes(values.tobytes())


def probe(path, runner):
    result = runner.call([find_tool('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], 'probe')
    parsed = json.loads(result.stdout)
    streams = [s for s in parsed['streams'] if s['codec_type'] == 'audio']
    if len(streams) != 1:
        raise ValueError('Exactly one audio stream is required')
    return streams[0], float(parsed['format']['duration'])


def loudness(path, target, runner):
    result = runner.call([find_tool('ffmpeg'), '-hide_banner', '-nostdin', '-i', str(path), '-af',
                          f'apad=whole_dur=0.5,loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], 'loudness')
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not matches:
        raise ValueError('FFmpeg loudness measurement missing')
    measurement = json.loads(matches[-1])
    for key in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'):
        if not math.isfinite(float(measurement[key])):
            raise ValueError('Silent/non-finite audio cannot be normalized')
    return measurement


def pcm_stats(path):
    with wave.open(str(path), 'rb') as source:
        if source.getsampwidth() != 2:
            raise ValueError('QA requires PCM16 WAV')
        channels = source.getnchannels()
        total, squared, signed, peak = 0, 0, 0, 0
        first, last = None, None
        while data := source.readframes(RATE):
            values = array('h', data)
            if sys.byteorder != 'little':
                values.byteswap()
            first = first if first is not None else values[:channels]
            last = values[-channels:]
            peak = max(peak, max(abs(v) for v in values))
            signed += sum(values)
            squared += sum(v * v for v in values)
            total += len(values)
        if not total:
            raise ValueError('Empty WAV')
        return {'peak_dbfs': 20 * math.log10(max(peak, 1) / 32768),
                'rms_dbfs': 20 * math.log10(max(math.sqrt(squared / total), 1e-9) / 32768),
                'dc_offset': signed / total / 32768,
                'boundary_delta': max(abs(a - b) for a, b in zip(first, last)) / 32768}


def qa_audio(path, item, runner):
    stream, duration = probe(path, runner)
    stats = pcm_stats(path)
    measured = loudness(path, item['target_lufs'], runner)
    checks = {
        'pcm16': stream['codec_name'] == 'pcm_s16le',
        'sample_rate': int(stream['sample_rate']) == RATE,
        'channels': stream['channels'] == item['channels'],
        'duration': abs(duration - item['duration_seconds']) <= .025,
        'not_silent': stats['rms_dbfs'] > -60,
        'sample_peak': stats['peak_dbfs'] <= -1.0,
        'true_peak': float(measured['input_tp']) <= -1.0,
        'loudness': abs(float(measured['input_i']) - item['target_lufs']) <= 1.5,
        'dc_offset': abs(stats['dc_offset']) < .01,
        'loop_boundary': not item['loop'] or stats['boundary_delta'] < .06,
    }
    return {'passed': all(checks.values()), 'checks': checks, 'duration_seconds': duration,
            'integrated_lufs': float(measured['input_i']), 'true_peak_dbtp': float(measured['input_tp']), **stats,
            'listening_review': 'required; numerical QA does not prove musical continuity or artistic quality'}


def finish_asset(item, mode, run, runner):
    name = item['id']
    work = run / 'work' / name
    work.mkdir(parents=True)
    duration = item['duration_seconds']
    cross = min(.1, duration / 8) if item['loop'] else 0
    needed = duration + cross
    source = work / 'source.wav'
    if mode == 'mock':
        mock_wave(source, needed + .05, item['channels'], item['kind'])
        provenance = {'provider': 'mock', 'production_ready': False}
    else:
        original = Path(item['source_path'])
        source = work / ('source' + original.suffix)
        shutil.copyfile(original, source)
        provenance = {'provider': 'local', 'original_path': str(original), 'source_sha256': sha256(source),
                      'generation': item.get('generation', {}), 'production_ready': False}
    _, available = probe(source, runner)
    if available + .001 < needed:
        raise ValueError(f'{name}: source requires {needed:.3f}s (including loop overlap); has {available:.3f}s')
    ffmpeg = find_tool('ffmpeg')
    decoded = work / 'decoded.wav'
    common = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y']
    runner.call(common + ['-i', str(source), '-map', '0:a:0', '-vn', '-t', str(needed), '-ar', str(RATE), '-ac', str(item['channels']), '-c:a', 'pcm_s16le', str(decoded)], name + ':decode')
    shaped = work / 'shaped.wav'
    if item['loop']:
        # Tail -> head crossfade, placed after the middle. Output is exactly duration.
        graph = (f'[0:a]asplit=3[h][m][t];[h]atrim=0:{cross},asetpts=PTS-STARTPTS[head];'
                 f'[m]atrim={cross}:{duration},asetpts=PTS-STARTPTS[mid];'
                 f'[t]atrim={duration}:{needed},asetpts=PTS-STARTPTS[tail];'
                 f'[tail][head]acrossfade=d={cross}:c1=tri:c2=tri[seam];'
                 '[mid][seam]concat=n=2:v=0:a=1[out]')
        runner.call(common + ['-i', str(decoded), '-filter_complex', graph, '-map', '[out]', '-c:a', 'pcm_s16le', str(shaped)], name + ':loop')
    else:
        fade = min(.008, duration / 8)
        runner.call(common + ['-i', str(decoded), '-af', f'afade=t=in:d={fade},afade=t=out:st={duration-fade}:d={fade}', '-c:a', 'pcm_s16le', str(shaped)], name + ':fades')
    measured = loudness(shaped, item['target_lufs'], runner)
    # Very short SFX need an EBU measurement window. Pad only while processing,
    # then trim back; QA uses the identical 0.5s silence-padded convention.
    normalize = (f"apad=whole_dur=0.5,loudnorm=I={item['target_lufs']}:TP=-1.5:LRA=11:"
                 f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
                 f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
                 f"offset={measured['target_offset']}:linear=true,atrim=duration={duration}")
    final = run / 'final' / (name + '.wav')
    runner.call(common + ['-i', str(shaped), '-af', normalize, '-ar', str(RATE), '-ac', str(item['channels']), '-c:a', 'pcm_s16le', str(final)], name + ':normalize')
    quality = qa_audio(final, item, runner)
    return {**item, 'path': str(final.resolve()), 'sha256': sha256(final), 'provenance': provenance,
            'qa': quality, 'status': 'ready_for_import' if quality['passed'] else 'qa_failed'}


def run_pipeline(brief_path, mode='mock', output_root=None, workers=2):
    brief_path = Path(brief_path).resolve()
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    items = validate_brief(brief, brief_path.parent, mode)
    # Preflight dependencies before creating a run.
    find_tool('ffmpeg')
    find_tool('ffprobe')
    run_id = 'CAD_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8]
    run = Path(output_root or PROJECT / 'Saved/CatAudioDirector').resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    (run / 'final').mkdir()
    runner = Runner(run / 'logs.jsonl')
    manifest = {'schema_version': 1, 'run_id': run_id, 'mode': mode, 'mock': mode == 'mock',
                'status': 'processing', 'assets': [], 'errors': [], 'paid_requests': 0,
                'unreal_status': 'not_imported', 'artistic_review': 'pending',
                'brief_sha256': sha256(brief_path)}
    save_json(run / 'brief.json', brief)
    manifest['saved_brief_sha256'] = sha256(run / 'brief.json')
    save_json(run / 'manifest.json', manifest)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
        jobs = {pool.submit(finish_asset, item, mode, run, runner): item for item in items}
        for job in as_completed(jobs):
            item = jobs[job]
            try:
                manifest['assets'].append(job.result())
            except Exception as error:
                manifest['errors'].append({'id': item['id'], 'error': str(error)[-1600:]})
                runner.event('asset_failed', id=item['id'], error=str(error)[-1600:])
            save_json(run / 'manifest.json', manifest)
    manifest['assets'].sort(key=lambda item: item['id'])
    passed = not manifest['errors'] and all(a['qa']['passed'] for a in manifest['assets'])
    manifest['status'] = 'ready_for_import' if passed else 'failed'
    if passed:
        plan = {'schema_version': 1, 'run_id': run_id, 'mock': mode == 'mock',
                'assets': [{k: a[k] for k in ('id', 'path', 'sha256', 'loop', 'kind')} for a in manifest['assets']]}
        save_json(run / 'import_plan.json', plan)
    save_json(run / 'manifest.json', manifest)
    return run, manifest


def qa_run(run):
    run = Path(run).resolve()
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    brief = json.loads((run / 'brief.json').read_text(encoding='utf-8'))
    expected = [a['id'] for a in brief['assets']]
    actual = [a['id'] for a in manifest['assets']]
    completeness = sorted(expected) == sorted(actual) and len(set(actual)) == len(actual)
    brief_intact = sha256(run / 'brief.json') == manifest['saved_brief_sha256']
    runner, results = Runner(run / 'logs.jsonl'), []
    for item in manifest['assets']:
        try:
            path = Path(item['path']).resolve()
            if not path.is_relative_to(run / 'final'):
                raise ValueError('Asset outside run final directory')
            quality = qa_audio(path, item, runner)
            quality['checks']['sha256'] = sha256(path) == item['sha256']
            quality['passed'] = all(quality['checks'].values())
            results.append({'id': item['id'], **quality})
        except Exception as error:
            results.append({'id': item['id'], 'passed': False, 'error': str(error)})
    report = {'run_id': manifest['run_id'], 'passed': bool(results) and completeness and brief_intact and not manifest['errors'] and all(r['passed'] for r in results),
              'complete_asset_set': completeness, 'brief_intact': brief_intact, 'assets': results}
    save_json(run / 'qa_report.json', report)
    return report


def integrate_run(run, allow_mock=False):
    """Single writer integration; never retries a possibly successful UE mutation."""
    run = Path(run).resolve()
    manifest_path = run / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['status'] != 'ready_for_import' or not qa_run(run)['passed']:
        raise ValueError('Import blocked: pipeline and independent QA must pass')
    if manifest['mock'] and not allow_mock:
        raise ValueError('Mock import needs --allow-mock')
    if manifest['unreal_status'] != 'not_imported':
        raise ValueError('Import already attempted. Inspect unreal_report.json before another run')
    plan = json.loads((run / 'import_plan.json').read_text(encoding='utf-8'))
    expected = [{k: a[k] for k in ('id', 'path', 'sha256', 'loop', 'kind')} for a in manifest['assets']]
    if plan['assets'] != expected or plan['run_id'] != manifest['run_id'] or plan['mock'] != manifest['mock']:
        raise ValueError('Import plan differs from verified manifest')
    manifest['unreal_status'] = 'attempting'
    save_json(manifest_path, manifest)
    command = [sys.executable, str(Path(__file__).with_name('unreal_bridge.py')), 'import', '--plan', str(run / 'import_plan.json'), '--apply']
    if allow_mock:
        command.append('--allow-mock')
    runner = Runner(run / 'logs.jsonl', attempts=1)
    try:
        runner.call(command, 'unreal_import', timeout=180)
        report = json.loads((run / 'unreal_report.json').read_text(encoding='utf-8'))
        if report.get('status') != 'passed' or sorted(a['id'] for a in report.get('assets', [])) != sorted(a['id'] for a in manifest['assets']):
            raise ValueError('Unreal report is unsuccessful or incomplete')
        manifest['unreal_status'] = 'imported'
    except Exception:
        manifest['unreal_status'] = 'failed_or_unknown'
        save_json(manifest_path, manifest)
        raise
    save_json(manifest_path, manifest)
    return report


def doctor():
    report = {'python': sys.version.split()[0], 'project': str(PROJECT), 'tools': {}}
    for name in ('ffmpeg', 'ffprobe'):
        try:
            executable = find_tool(name)
            result = subprocess.run([executable, '-version'], capture_output=True, text=True, timeout=10, check=True)
            report['tools'][name] = {'path': executable, 'version': result.stdout.splitlines()[0], 'ok': True}
        except Exception as error:
            report['tools'][name] = {'ok': False, 'error': str(error)}
    report['ok'] = all(value['ok'] for value in report['tools'].values())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    run = commands.add_parser('run')
    run.add_argument('--brief', required=True)
    run.add_argument('--mode', choices=('mock', 'local'), default='mock')
    run.add_argument('--workers', type=int, default=2)
    run.add_argument('--output-root')
    run.add_argument('--apply-unreal', action='store_true', help='After successful QA, add new Unreal assets through the verified bridge')
    run.add_argument('--allow-mock', action='store_true')
    qa = commands.add_parser('qa')
    qa.add_argument('--run', required=True)
    integrate = commands.add_parser('integrate')
    integrate.add_argument('--run', required=True)
    integrate.add_argument('--apply', action='store_true', required=True)
    integrate.add_argument('--allow-mock', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor()
            okay = result['ok']
        elif args.command == 'run':
            directory, manifest = run_pipeline(args.brief, args.mode, args.output_root, args.workers)
            result = {'run': str(directory), 'status': manifest['status'], 'errors': manifest['errors']}
            okay = manifest['status'] == 'ready_for_import'
            if okay and args.apply_unreal:
                result['unreal'] = integrate_run(directory, args.allow_mock)
        elif args.command == 'integrate':
            result = integrate_run(args.run, args.allow_mock)
            okay = result.get('status') == 'passed'
        else:
            result = qa_run(args.run)
            okay = result['passed']
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if okay else 1
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
