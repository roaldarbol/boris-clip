# boris-clip

Extract video clips from [BORIS](https://www.boris.unito.it/) behavioural annotation files.

For each annotated bout in a BORIS file, `boris-clip` cuts the corresponding segment from your video and saves it as an individual clip. Clips are named after the source video, behaviour, subject, and time interval — making them easy to sort and identify without opening them.

```
recording_REM_ind1_10.033-15.766.mp4
recording_grooming_ind2_42.100-48.500.mp4
```

---

## Installation

`boris-clip` requires [ffmpeg](https://ffmpeg.org/) to be installed and available on your `PATH`.

### Global installation (recommended)

Install `boris-clip` as a standalone tool, available system-wide without activating any environment.

**With uv:**

```sh
uv tool install boris-clip
```

**With pixi:**

```sh
pixi global install boris-clip
```

Both approaches isolate `boris-clip` in their own environment under the hood, so there are no dependency conflicts with your other projects. Note that with `uv tool install`, ffmpeg must be installed separately (e.g. via `brew install ffmpeg`, `conda install -c conda-forge ffmpeg`, or your system package manager). With `pixi global install`, ffmpeg is pulled in automatically from conda-forge.

### Into an existing environment

**With uv:**

```sh
uv add boris-clip
```

**With pixi:**

```sh
pixi add boris-clip
```

**With pip:**

```sh
pip install boris-clip
```

---

## Quick start

Point `boris-clip` at your `.boris` project file. If the file contains the video path (which it does by default when you annotate in BORIS), that's all you need:

```sh
boris-clip annotations.boris
```

If the video has moved since you created the project, or you are working with a CSV export, pass the video path explicitly:

```sh
boris-clip annotations.boris recording.mp4
```

Clips are saved to a `clips/` directory in the current folder.

---

## Common usage

**Change the output directory:**

```sh
boris-clip annotations.boris -o /path/to/output/
```

**Add padding around each clip:**

```sh
boris-clip annotations.boris --padding 2.0
```

**Asymmetric padding — 1 second before, 3 seconds after:**

```sh
boris-clip annotations.boris --padding-pre 1.0 --padding-post 3.0
```

**Multiple videos** (matched to observations by filename):

```sh
boris-clip annotations.boris rec1.mp4 rec2.mp4 rec3.mp4
```

**Fast mode** — stream-copy instead of re-encoding, much faster but cuts are keyframe-approximate:

```sh
boris-clip annotations.boris --fast
```

---

## BORIS file formats

`boris-clip` auto-detects whichever format you provide:

| Format | Notes |
|---|---|
| `.boris` project file | Best option — contains video paths, FPS, and duration for validation |
| Tabular events CSV | Exported from BORIS via *Observations → Export events* |
| Aggregated events CSV | Exported from BORIS via *Observations → Export aggregated events* |

**Multiple observations** in a `.boris` project file are each processed independently and matched to their respective video by filename. Observations with no annotations are skipped automatically.

---

## Output file naming

Clips are named using the pattern:

```
{video_stem}_{behaviour}_{subject}_{start}-{stop}.mp4
```

- Times reflect the **original annotation timestamps**, not the padded clip boundaries, so names are stable regardless of padding settings.
- Subjects labelled *No focal subject* in BORIS become `no-focal-subject` in the filename.
- Special characters in behaviour or subject names are replaced with underscores.

---

## Reference

### Arguments

| Argument | Description |
|---|---|
| `BORIS_FILE` | Path to a `.boris` project file or BORIS CSV export |
| `[VIDEO ...]` | Optional. One or more video files. If omitted, paths embedded in the `.boris` file are used. Multiple videos are matched to observations by filename. |

### Options

| Option | Default | Description |
|---|---|---|
| `-o`, `--output-dir` | `clips/` | Directory to write output clips into |
| `--padding SECONDS` | `0` | Add this many seconds before **and** after each state event bout |
| `--padding-pre SECONDS` | `0` | Seconds to add before each bout (overrides `--padding` for the pre side) |
| `--padding-post SECONDS` | `0` | Seconds to add after each bout (overrides `--padding` for the post side) |
| `--point-padding SECONDS` | `5` | Padding for point events, both sides (defaults to 5s if no general padding is set) |
| `--point-padding-pre SECONDS` | — | Pre-padding for point events (overrides `--point-padding`) |
| `--point-padding-post SECONDS` | — | Post-padding for point events (overrides `--point-padding`) |
| `--fast` | off | Use stream-copy instead of re-encoding. Much faster, but cut points snap to the nearest keyframe and may be slightly imprecise |
| `--force` | off | Downgrade hard errors (mismatched media file, out-of-bounds annotations) to warnings |
| `--version` | — | Show version and exit |
| `--help` | — | Show help and exit |

### Padding precedence

Padding follows a CSS-like precedence: `--padding` sets both sides, while `--padding-pre` and `--padding-post` override their respective side independently.

```sh
# 2s before and after
--padding 2.0

# 2s after only
--padding-post 2.0

# 1s before, 3s after (--padding-pre and --padding-post override --padding)
--padding 3.0 --padding-pre 1.0
```

Point events have no inherent duration, so padding is always applied. If no point-specific padding is set, the general `--padding` value is used; if no padding is set at all, a default of 5 seconds each side is applied.

### Re-encoding vs. stream-copy

By default, `boris-clip` re-encodes clips using ffmpeg. This is slower but **frame-accurate** — cuts land exactly at the annotated timestamp.

With `--fast`, ffmpeg uses stream-copy, which skips re-encoding and is significantly faster. The trade-off is that cuts snap to the nearest keyframe, which can be a second or two away from the annotation. This is fine for a quick preview but may not be suitable for precise analysis.

---

## Validation

When a `.boris` project file is provided, `boris-clip` cross-checks the embedded metadata against the actual video via `ffprobe`:

- **Hard error** (use `--force` to override): media filename mismatch, annotation timestamps beyond video duration
- **Warning**: FPS mismatch between BORIS file and video, duration mismatch

---

## Contributing

Bug reports and pull requests are welcome on [GitHub](https://github.com/roaldarbol/boris-clip).

## License

MIT