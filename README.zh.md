# sleepcast-loudness

[中文版](./README.zh.md) | [English](./README.md)

一个自包含的 Codex / agent Skill，用 FFmpeg 测量、判断并以非破坏方式调整 **VelaSleep SleepCast** 响度。

它把 SleepCast 当作睡眠播客人声内容处理，不按普通播客母带或 Sleep Music 的标准判断。人声段是主要响度依据；整条 45 分钟响度和 BGM-only 尾段只用于辅助判断。

## 文件分工

| 文件 | 读者 | 作用 |
|---|---|---|
| `README.md` / `README.zh.md` | 人 | 安装、用法和仓库说明。 |
| `SKILL.md` | Agent | 触发元数据、两阶段工作流、判断规则和汇报契约。 |
| `scripts/sleepcast_loudness.py` | Agent 可执行辅助脚本 | 分段测量、媒体规格探测和线性增益试听版生成。 |
| `agents/openai.yaml` | Codex UI | 展示名称、简短说明和默认提示。 |

仓库根目录就是 Skill 包本身。Skill 名、仓库名和 clone 文件夹名统一为 `sleepcast-loudness`。

## 工作流

1. 先测量源文件，汇报人声主段、整条、尾段 BGM、True Peak、LRA、响度门限和媒体规格。
2. 停下等待用户确认，并说明拟采用的增益、目标、实际人声结束点假设和风险。
3. 用户确认后，再生成新的整条线性增益试听版，不覆盖源文件。
4. 对输出文件复测，并按固定字段汇报。

首次试听默认以人声主段约 `-26.5 LUFS` 为目标。不默认使用动态 `loudnorm` 或压缩，以免改变原有的人声 / BGM 关系。

如果导出文件的人声超过常规 30–33 分钟，可用 `--voice-end-min` 和 `--tail-start-min` 按确认后的真实结构测量和生成。

## 依赖

- Python 3.10+
- FFmpeg 和 FFprobe 位于 `PATH`，或位于辅助脚本支持的本地安装路径

## 安装

这是私有仓库。安装前需先配置 GitHub 认证并拥有仓库访问权限。

```bash
npx skills add https://github.com/ZimaBlue1226/sleepcast-loudness
```

人工安装时，clone 仓库后把完整的 `sleepcast-loudness/` 目录放到目标 agent 的 skills 目录中；`SKILL.md`、`agents/` 和 `scripts/` 必须保持在一起。

## 用法

测量默认 SleepCast 分段：

```powershell
python scripts/sleepcast_loudness.py measure "E:\path\to\sleepcast.wav"
```

测量已确认人声约在 39 分钟结束的导出：

```powershell
python scripts/sleepcast_loudness.py measure "E:\path\to\sleepcast.wav" --voice-end-min 39 --tail-start-min 39
```

用户确认后，按默认人声主段目标生成试听版：

```powershell
python scripts/sleepcast_loudness.py render "E:\path\to\sleepcast.wav" --target-voice-lufs -26.5
```

输出文件与源文件位于同一目录，使用 `-plus5p0db.wav` 一类增益后缀；源文件不覆盖。

## 自定义

工作流口径、响度目标和汇报字段修改在 `SKILL.md`；只有当分段、FFmpeg 行为、输出命名或媒体规格汇报发生变化时，才修改 `scripts/sleepcast_loudness.py`。
