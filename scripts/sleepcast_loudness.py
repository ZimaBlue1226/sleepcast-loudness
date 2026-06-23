#!/usr/bin/env python3
"""Measure and render VelaSleep SleepCast loudness audition files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TARGET_VOICE_LUFS = -26.5


@dataclass(frozen=True)
class Segment:
    label: str
    start: float
    duration: float


def time_label(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}_{secs:02d}"


def build_segments(voice_end_min: float = 30.0, tail_start_min: float = 33.0) -> list[Segment]:
    voice_start = 16.0
    voice_end = voice_end_min * 60.0
    tail_start = tail_start_min * 60.0
    fade_start = 44.5 * 60.0

    if voice_end <= voice_start:
        raise ValueError("--voice-end-min must be after 00:16")
    if tail_start < voice_end:
        raise ValueError("--tail-start-min must be equal to or after --voice-end-min")
    if tail_start >= fade_start:
        raise ValueError("--tail-start-min must be before 44:30")

    segments = [
        Segment("full_00_45", 0, 2700),
        Segment("intro_bgm_00_08", 0, 8),
        Segment("voice_entry_00_08_00_16", 8, 8),
        Segment(
            f"voice_main_00_16_{time_label(voice_end)}",
            voice_start,
            voice_end - voice_start,
        ),
    ]

    if tail_start > voice_end:
        segments.append(
            Segment(
                f"end_window_{time_label(voice_end)}_{time_label(tail_start)}",
                voice_end,
                tail_start - voice_end,
            )
        )

    first_tail_end = min(tail_start + 7 * 60, fade_start)
    segments.append(
        Segment(
            f"tail_bgm_{time_label(tail_start)}_{time_label(first_tail_end)}",
            tail_start,
            first_tail_end - tail_start,
        )
    )
    if first_tail_end < fade_start:
        segments.append(
            Segment(
                f"tail_bgm_{time_label(first_tail_end)}_44_30",
                first_tail_end,
                fade_start - first_tail_end,
            )
        )
    segments.append(Segment("fade_check_44_30_45_00", fade_start, 30))
    return segments


def find_ffmpeg() -> str:
    candidates = [
        shutil.which("ffmpeg"),
        r"D:\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("ffmpeg not found in PATH or known local install paths")


def find_ffprobe() -> str:
    candidates = [
        shutil.which("ffprobe"),
        r"D:\ffmpeg-8.1.1-essentials_build\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("ffprobe not found in PATH or known local install paths")


def parse_loudnorm(stderr: str) -> dict[str, str]:
    match = re.search(r'(?s)\{\s*"input_i".*?\}', stderr)
    if not match:
        raise RuntimeError("Could not parse loudnorm JSON from ffmpeg output")
    return json.loads(match.group(0))


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def describe_bit_depth(stream: dict[str, object]) -> str:
    codec = str(stream.get("codec_name") or "")
    bits = 0
    for key in ("bits_per_raw_sample", "bits_per_sample"):
        try:
            bits = int(stream.get(key) or 0)
        except (TypeError, ValueError):
            bits = 0
        if bits > 0:
            break

    sample_fmt = str(stream.get("sample_fmt") or "")
    if bits == 0:
        match = re.match(r"[su](\d+)", sample_fmt)
        if match:
            bits = int(match.group(1))
        elif sample_fmt.startswith("flt"):
            bits = 32
        elif sample_fmt.startswith("dbl"):
            bits = 64

    if bits == 0:
        return "unavailable"
    if codec.startswith("pcm_"):
        return f"{bits}-bit PCM"
    return f"{bits}-bit ({codec or sample_fmt})"


def probe_media(input_path: Path) -> dict[str, object]:
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        (
            "stream=codec_name,sample_fmt,sample_rate,channels,channel_layout,"
            "bits_per_sample,bits_per_raw_sample,duration:format=duration"
        ),
        "-of",
        "json",
        str(input_path),
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")

    data = json.loads(proc.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError("ffprobe found no audio stream")
    stream = streams[0]
    format_data = data.get("format") or {}
    duration_raw = format_data.get("duration") or stream.get("duration")
    if duration_raw is None:
        raise RuntimeError("ffprobe did not report audio duration")

    duration_seconds = float(duration_raw)
    channels = int(stream.get("channels") or 0)
    channel_layout = str(stream.get("channel_layout") or "")
    if not channel_layout:
        channel_layout = {1: "mono", 2: "stereo"}.get(channels, f"{channels} channels")
    sample_rate = int(stream.get("sample_rate") or 0)
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "channel_layout": channel_layout,
        "bit_depth": describe_bit_depth(stream),
        "codec": str(stream.get("codec_name") or "unknown"),
        "duration_seconds": round(duration_seconds, 3),
        "duration": format_duration(duration_seconds),
    }


def measure_segment(ffmpeg: str, input_path: Path, segment: Segment) -> dict[str, object]:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-ss",
        str(segment.start),
        "-t",
        str(segment.duration),
        "-i",
        str(input_path),
        "-af",
        "loudnorm=I=-20:TP=-2:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ffmpeg failed for {segment.label}")
    data = parse_loudnorm(proc.stderr)
    return {
        "segment": segment.label,
        "LUFS": float(data["input_i"]),
        "TP": float(data["input_tp"]),
        "LRA": float(data["input_lra"]),
        "thresh": float(data["input_thresh"]),
    }


def measure_file(input_path: Path, voice_end_min: float = 30.0, tail_start_min: float = 33.0) -> list[dict[str, object]]:
    ffmpeg = find_ffmpeg()
    return [measure_segment(ffmpeg, input_path, segment) for segment in build_segments(voice_end_min, tail_start_min)]


def gain_suffix(gain_db: float) -> str:
    sign = "plus" if gain_db >= 0 else "minus"
    value = f"{abs(gain_db):.1f}".replace(".", "p")
    return f"{sign}{value}db"


def default_output_path(input_path: Path, gain_db: float) -> Path:
    return input_path.with_name(f"{input_path.stem}-{gain_suffix(gain_db)}.wav")


def render_linear_gain(input_path: Path, output_path: Path, gain_db: float) -> None:
    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        f"volume={gain_db}dB",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg render failed")


def find_voice_lufs(results: list[dict[str, object]]) -> float:
    for item in results:
        if str(item["segment"]).startswith("voice_main_"):
            return float(item["LUFS"])
    raise RuntimeError("voice_main segment missing")


def print_results(path: Path, results: list[dict[str, object]]) -> None:
    print(f"file: {path}")
    for item in results:
        print(
            "{segment}: {LUFS:.2f} LUFS / {TP:.2f} dBTP / "
            "LRA {LRA:.2f} LU / thresh {thresh:.2f} LUFS".format(**item)
        )


def print_media_info(media: dict[str, object]) -> None:
    print("media:")
    print(f"  sample_rate: {media['sample_rate_hz']} Hz")
    print(f"  channels: {media['channel_layout']} ({media['channels']})")
    print(f"  bit_depth: {media['bit_depth']}")
    print(f"  codec: {media['codec']}")
    print(f"  duration: {media['duration']} ({media['duration_seconds']:.3f} s)")


def command_measure(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    results = measure_file(input_path, args.voice_end_min, args.tail_start_min)
    media = probe_media(input_path)
    if args.json:
        print(
            json.dumps(
                {"file": str(input_path), "media": media, "segments": results},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_results(input_path, results)
        print_media_info(media)


def command_render(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    source_media = probe_media(input_path)
    source_results = measure_file(input_path, args.voice_end_min, args.tail_start_min)
    if args.gain_db is None:
        voice_lufs = find_voice_lufs(source_results)
        gain_db = args.target_voice_lufs - voice_lufs
    else:
        gain_db = args.gain_db
    output_path = Path(args.output).resolve() if args.output else default_output_path(input_path, gain_db)
    render_linear_gain(input_path, output_path, gain_db)
    output_results = measure_file(output_path, args.voice_end_min, args.tail_start_min)
    output_media = probe_media(output_path)
    print(f"source: {input_path}")
    print(f"linear_gain_db: {gain_db:.2f}")
    print(f"output: {output_path}")
    print_results(output_path, output_results)
    print_media_info(output_media)
    duration_delta = float(output_media["duration_seconds"]) - float(source_media["duration_seconds"])
    print(f"duration_delta_seconds: {duration_delta:.3f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    measure = subparsers.add_parser("measure", help="measure SleepCast sections")
    measure.add_argument("input")
    measure.add_argument("--voice-end-min", type=float, default=30.0)
    measure.add_argument("--tail-start-min", type=float, default=33.0)
    measure.add_argument("--json", action="store_true")
    measure.set_defaults(func=command_measure)

    render = subparsers.add_parser("render", help="render a non-destructive linear-gain audition file")
    render.add_argument("input")
    render.add_argument("--target-voice-lufs", type=float, default=DEFAULT_TARGET_VOICE_LUFS)
    render.add_argument("--voice-end-min", type=float, default=30.0)
    render.add_argument("--tail-start-min", type=float, default=33.0)
    render.add_argument("--gain-db", type=float)
    render.add_argument("--output")
    render.set_defaults(func=command_render)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI should present concise errors.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
