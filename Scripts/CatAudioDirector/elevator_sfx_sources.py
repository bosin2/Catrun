"""Render deterministic provisional Catrun elevator Foley and its local brief."""

import argparse
import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path


RATE = 48_000


def impact(track, rng, start, gain, modes, decay, grit):
    """Layer damped resonances with the short scrape of the contact."""
    first = round(start * RATE)
    length = min(len(track) - first, round(7 * decay * RATE))
    phases = [rng.uniform(0, math.tau) for _ in modes]
    previous_noise = 0.0
    for offset in range(length):
        t = offset / RATE
        modal = sum(weight * math.sin(math.tau * frequency * t + phase)
                    * math.exp(-t * damping / decay)
                    for (frequency, weight, damping), phase in zip(modes, phases))
        noise = rng.uniform(-1, 1)
        transient = (noise - 0.67 * previous_noise) * grit * math.exp(-t / 0.009)
        previous_noise = noise
        attack = min(t / 0.0015, 1.0)
        track[first + offset] += gain * attack * (modal + transient)


def creak(track, rng, start, length, gain):
    """Vary the speed and pressure of a loaded timber joint."""
    phase = 0.0
    filtered_noise = 0.0
    first = round(start * RATE)
    for offset in range(round(length * RATE)):
        t = offset / RATE
        progress = t / length
        frequency = 76 + 62 * progress + 15 * math.sin(math.tau * 3.5 * t)
        phase += math.tau * frequency / RATE
        stick_slip = (0.55 + 0.45 * math.sin(math.tau * 18 * t)) ** 2
        filtered_noise = 0.84 * filtered_noise + 0.16 * rng.uniform(-1, 1)
        envelope = math.sin(math.pi * progress) ** 1.4 * stick_slip
        timber = (0.50 * math.sin(phase) + 0.22 * math.sin(2.03 * phase)
                  + 0.13 * math.sin(3.11 * phase) + 0.75 * filtered_noise)
        track[first + offset] += gain * envelope * timber


LINKS = ((727, 0.50, 0.8), (1289, 0.37, 1.1), (2063, 0.24, 1.5), (3217, 0.12, 2.0))
IRON = ((86, 0.61, 0.58), (159, 0.41, 0.85), (387, 0.28, 1.1),
        (961, 0.21, 1.25), (1687, 0.12, 1.85))
LATCH = ((222, 0.43, 0.82), (693, 0.48, 0.97), (1167, 0.31, 1.22), (2521, 0.19, 1.8))


def chain_ring_pull(track, rng):
    for start, gain in ((0.02, 0.9), (0.078, 0.57), (0.137, 0.75), (0.232, 1.0),
                        (0.31, 0.52), (0.398, 0.49), (0.49, 0.27), (0.55, 0.19)):
        modes = [(frequency * rng.uniform(0.88, 1.12), weight, damping)
                 for frequency, weight, damping in LINKS]
        impact(track, rng, start, gain, modes, 0.073, 0.43)


def lift_departure(track, rng):
    creak(track, rng, 0.019, 0.58, 0.91)
    impact(track, rng, 0.23, 0.38, LATCH, 0.061, 0.38)
    impact(track, rng, 0.52, 1.25, IRON, 0.12, 0.40)
    creak(track, rng, 0.61, 0.71, 0.59)
    for start, gain in ((0.7, 0.26), (0.81, 0.32), (0.95, 0.17), (1.12, 0.11)):
        impact(track, rng, start, gain, IRON, 0.078, 0.30)


def dock_latch(track, rng):
    for start, gain in ((0.115, 0.30), (0.163, 0.52), (0.205, 0.31), (0.278, 0.44)):
        impact(track, rng, start, gain, LINKS, 0.053, 0.56)
    impact(track, rng, 0.347, 0.35, IRON, 0.056, 0.25)
    impact(track, rng, 0.435, 1.29, LATCH, 0.070, 0.60)


EFFECTS = (
    (chain_ring_pull, 0.8, 171, "Staggered iron chain links, a firm tug, lighter settling links."),
    (lift_departure, 1.4, 241, "Loaded wooden joint creaks, heavy iron release jolt, low travel rattle."),
    (dock_latch, 0.7, 331, "Delayed small metal clatter and a firm latch clack."),
)


def render(effect, duration, seed, target):
    track = [0.0] * round(RATE * duration)
    effect(track, random.Random(seed))
    end_fade = round(0.03 * RATE)
    for offset in range(end_fade):
        track[-1 - offset] *= offset / end_fade
    peak = max(map(abs, track))
    # Round off transient peaks so normalization preserves the quieter details.
    drive = 1.0 if effect is chain_ring_pull else 3.0
    scale = 0.73 * 32767 / math.tanh(drive)
    samples = [round(math.tanh(drive * value / peak) * scale) for value in track]
    with wave.open(str(target), "wb") as wav:
        wav.setparams((1, 2, RATE, len(samples), "NONE", "not compressed"))
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    with wave.open(str(target), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (
            1, 2, RATE, len(samples))
        verified = struct.unpack(f"<{len(samples)}h", wav.readframes(len(samples)))
    peak = max(map(abs, verified)) / 32768
    rms = math.sqrt(sum(sample * sample for sample in verified) / len(verified)) / 32768
    dc = sum(verified) / (len(verified) * 32768)
    assert 0.6 < peak < 0.8 and rms > 0.015 and abs(dc) < 0.01
    assert not verified[0] and not verified[-1]
    return {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "peak_dbfs": 20 * math.log10(peak), "rms_dbfs": 20 * math.log10(rms),
            "dc_ratio": dc, "frames": len(verified)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    source = output / "source"
    source.mkdir(parents=True, exist_ok=True)
    assets = []
    provenance = {"purpose": "Provisional sound design timing sources; art review pending",
                  "method": "Local procedural Foley using seeded noise and damped modal resonances",
                  "script": "Scripts/CatAudioDirector/elevator_sfx_sources.py", "files": {}}
    for effect, duration, seed, prompt in EFFECTS:
        asset_id = effect.__name__
        target = source / f"{asset_id}.wav"
        provenance["files"][target.name] = {"seed": seed, **render(effect, duration, seed, target)}
        assets.append({"id": asset_id, "kind": "sfx", "prompt": f"Provisional timing Foley. {prompt}",
                       "duration_seconds": duration, "loop": False, "source_path": target.as_posix()})
    for filename, data in (("brief_source.json", {"assets": assets}), ("provenance.json", provenance)):
        (output / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
