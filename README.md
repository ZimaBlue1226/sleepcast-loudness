# sleepcast-loudness

[English](./README.md) | [中文版](./README.zh.md)

A self-contained Codex / agent skill for measuring, judging, and non-destructively adjusting **VelaSleep SleepCast** loudness with FFmpeg.

It treats SleepCast as sleep-podcast narration rather than normal podcast mastering or sleep music. The voice section is the primary loudness reference; the full 45-minute file and BGM-only tail are supporting context.

## Who reads what

| File | Audience | Purpose |
|---|---|---|
| `README.md` / `README.zh.md` | Humans | Installation, usage, and package notes. |
| `SKILL.md` | Agent | Trigger metadata, two-stage workflow, judgment rules, and reporting contract. |
| `scripts/sleepcast_loudness.py` | Agent-executable helper | Measures sections, probes media metadata, and renders linear-gain audition files. |
| `agents/openai.yaml` | Codex UI | Display name, short description, and default prompt. |

The repository root is the skill package itself. The skill name, repository name, and clone directory are all `sleepcast-loudness`.

## Workflow

1. Measure the source file and report voice-main, whole-file, tail-BGM, true-peak, LRA, threshold, and media metadata.
2. Stop for user confirmation, including the proposed gain, target, actual voice-end assumption, and risks.
3. After confirmation, render a new linear-gain audition file without overwriting the source.
4. Re-measure the output and report the fixed completion fields.

The initial voice-main audition target is approximately `-26.5 LUFS`. Dynamic `loudnorm` and compression are not used by default because they can change the intended voice/BGM relationship.

Exports whose narration continues beyond the normal 30–33 minute range can be measured and rendered with `--voice-end-min` and `--tail-start-min`.

## Requirements

- Python 3.10+
- FFmpeg and FFprobe in `PATH`, or in a helper-supported local install path

## Install

This is a private repository. Configure GitHub authentication and repository access first.

```bash
npx skills add https://github.com/ZimaBlue1226/sleepcast-loudness
```

For manual installation, clone the repository and place the complete `sleepcast-loudness/` directory under the target agent's skills directory. Keep `SKILL.md`, `agents/`, and `scripts/` together.

## Usage

Measure the default SleepCast sections:

```powershell
python scripts/sleepcast_loudness.py measure "E:\path\to\sleepcast.wav"
```

Measure an export whose confirmed narration ends around 39 minutes:

```powershell
python scripts/sleepcast_loudness.py measure "E:\path\to\sleepcast.wav" --voice-end-min 39 --tail-start-min 39
```

After user confirmation, render to the default voice-main target:

```powershell
python scripts/sleepcast_loudness.py render "E:\path\to\sleepcast.wav" --target-voice-lufs -26.5
```

The render is written next to the source with a gain suffix such as `-plus5p0db.wav`; the source is preserved.

## Customizing

Edit `SKILL.md` for workflow policy, loudness guidance, and reporting requirements. Edit `scripts/sleepcast_loudness.py` only when measurement segments, FFmpeg behavior, output naming, or metadata reporting must change.
