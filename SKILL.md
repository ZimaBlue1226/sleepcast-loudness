---
name: sleepcast-loudness
description: "Two-stage loudness workflow for VelaSleep SleepCast sleep-podcast audio files: first measure and analyze SleepCast sections, then after user confirmation create non-destructive linear-gain loudness-optimized audition renders. Use when Codex needs to inspect SleepCast WAV/MP3/AAC loudness, separate voice-bed sections from BGM-only tails, compare male/female versions, decide whether LUFS/LRA/true peak are acceptable for sleep narration, or optimize confirmed SleepCast files without using dynamic loudnorm compression."
---

# SleepCast Loudness

## Core Context

Treat SleepCast as sleep-podcast narration, not normal podcast mastering and not sleepmusic. Do not default to `-16 LUFS`, and do not use full-file 45-minute integrated LUFS as the voice loudness target.

VelaSleep SleepCast structure:

```text
0s: BGM starts.
8-16s: voice starts, usually around 8s.
30-33min: voice ends; exact end varies with script length.
After voice end: the same BGM loops until 45min.
Tail: BGM may fade out; fade length varies, often around 20s.
```

The 33-45min BGM-only tail can make whole-file LUFS much lower than the effective narration loudness. Judge voice loudness from the voice section, not from the full file.

Some exports may violate the expected 30-33min voice ending. For example, a script/TTS assembly mistake can leave narration active until around 39min. If 33-40min loudness stays close to the voice section, do not treat it as BGM-only tail. Ask the user to confirm the actual voice end, then rerun measurement and rendering with `--voice-end-min` and `--tail-start-min`.

## Required Two-Stage Workflow

1. Read `project_context.md` first when working inside `E:\VelaSleep`.
2. Identify SleepCast files. Filenames with `male` or `female` are podcast versions.
3. Stage 1 is mandatory: measure first and explain the conclusion. Use the bundled script:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py measure "E:\path\to\sleepcast.wav"
```

4. Interpret sections separately:
   - `full_00_45`: informational only; do not use as the main target.
   - `intro_bgm_00_08`: BGM-only intro check.
   - `voice_entry_00_08_00_16`: voice entrance check.
   - `voice_main_00_16_30_00`: main loudness reference.
   - `end_window_30_00_33_00`: voice ending / transition check.
   - `tail_bgm_33_00_40_00` and `tail_bgm_40_00_44_30`: stable BGM tail check.
   - `fade_check_44_30_45_00`: fade and noise check only.
5. If `tail_bgm_33_00_40_00` is close to the voice-main loudness, perform a finer check around 30-41min, report that the voice may extend past 33min, and wait for the user to confirm the actual voice end.
6. After Stage 1, stop and ask for confirmation before writing optimized audio. Include the proposed processing mode, gain, target voice-main LUFS, expected true peak, actual voice-end assumption, and risks such as louder BGM tails or exposed noise.
7. Stage 2 starts only after the user confirms. Create the optimized audition render, then measure the output and report the same sections.
8. For a first sleep-podcast audition, target the voice-main section around `-26.5 LUFS` unless the user gives a different listening target.
9. Prefer linear gain for stable SleepCast voice sections. Do not use dynamic `loudnorm` or compression by default; it can overreact to the quiet BGM tail and change the intended voice/BGM relationship.
10. Preserve source files. Write audition files with a suffix like `-plus5p0db.wav`.

## Risk Judgement

Low risk: voice-main loudness is stable across 5-minute windows, true peak has at least several dB of headroom after planned gain, and the user has confirmed optimization after seeing the Stage 1 analysis.

Medium risk: voice-main LRA is high, true peak after gain would exceed about `-3 dBTP`, BGM tail may become too present, or male/female versions differ strongly. Stop after measurement and explain the tradeoff before rendering.

High risk: the file is a stem, BGM-only asset, corrupted export, has obvious clipping, or the user goal is unclear. Do not render until clarified.

## Recommended Commands

Measure default SleepCast sections:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py measure "E:\VelaSleep\待处理音频\Rainy Night Restoration Shop-202606181415-female.wav"
```

Measure a confirmed extended narration export, such as voice ending around 39min:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py measure "E:\path\to\sleepcast.wav" --voice-end-min 39 --tail-start-min 39
```

After user confirmation, render to a target voice-main loudness:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py render "E:\VelaSleep\待处理音频\Rainy Night Restoration Shop-202606181415-female.wav" --target-voice-lufs -26.5
```

After user confirmation, render a confirmed extended narration export:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py render "E:\path\to\sleepcast.wav" --voice-end-min 39 --tail-start-min 39 --target-voice-lufs -26.5
```

After user confirmation, render with an explicit linear gain:

```powershell
python C:\Users\周润泽\.codex\skills\sleepcast-loudness\scripts\sleepcast_loudness.py render "E:\path\to\file.wav" --gain-db 5.0
```

Useful manual FFmpeg pattern:

```powershell
ffmpeg -hide_banner -y -i "input.wav" -af "volume=5dB" -ar 44100 -c:a pcm_s16le "input-plus5p0db.wav"
```

## Completion Output

Summarize in Chinese unless the user asks otherwise. Include:

For Stage 1:

```text
实测文件：
人声主段：
整条：
尾段 BGM：
True Peak 余量：
建议处理：
实际人声结束假设：
需用户确认：
```

For Stage 2, end the response with a copyable plain-text parameter list. Do not use a Markdown table. Treat the optimized output as the measured file, keep whole-file loudness informational, and make the actual voice-main range explicit. For linear-gain processing, state the voice-main LUFS goal and true-peak safety limit; do not present LRA as a normalization target because LRA is measured, not actively changed.

```text
源文件：
实测文件：
处理目标：人声主段约 -26.5 LUFS，True Peak 不高于约 -3 dBTP
处理方式：整条线性增益 +X.XX dB
实际人声主段：00:16-30:00
人声主段综合响度：-XX.XX LUFS
人声主段 True Peak：-XX.XX dBTP
人声主段 LRA：XX.XX LU
人声主段响度门限：-XX.XX LUFS
整条综合响度：-XX.XX LUFS（仅供参考）
尾段 BGM：时间范围及 -XX.XX LUFS
采样率：XXXXX Hz
声道：
位深：
时长：MM:SS
源文件状态：未覆盖
判断：
```

Replace the example target, gain, time range, and measurements with the values actually used. If narration ends outside the normal 30-33min window, report the confirmed range, such as `00:16-39:00`. Use the bundled script's `ffprobe` metadata output for sample rate, channel layout, bit depth, and actual duration. Do not silently omit unavailable fields; mark them unavailable and explain why. Always state when the source file was not overwritten.
