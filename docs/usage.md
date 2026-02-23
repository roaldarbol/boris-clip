# Usage

## Quick start

Point `boris-clip` at your `.boris` project file. If the file contains the video path (which it does by default when you annotate in BORIS), that is all you need:

```sh
boris-clip annotations.boris
```

If the video has moved since you created the project, or you are working with a CSV export, pass the video path explicitly:

```sh
boris-clip annotations.boris recording.mp4
```

Clips are saved to a `clips/` directory in the current folder.

## Common usage

**Change the output directory:**

```sh
boris-clip annotations.boris -o /path/to/output/
```

**Filter by behaviour:**

```sh
boris-clip annotations.boris -b REM
boris-clip annotations.boris -b REM -b walking
```

**Add padding around each clip:**

```sh
boris-clip annotations.boris --padding 2.0
```

**Asymmetric padding — 1 second before, 3 seconds after:**

```sh
boris-clip annotations.boris --padding-pre 1.0 --padding-post 3.0
```

**Limit clip duration and count:**

```sh
# Truncate clips to at most 10 seconds
boris-clip annotations.boris --max-duration 10.0

# At most 3 clips per behaviour/subject combination
boris-clip annotations.boris --max-clips 3
```

**Multiple videos** (matched to observations by filename):

```sh
boris-clip annotations.boris rec1.mp4 rec2.mp4 rec3.mp4
```

**Fast mode** — stream-copy instead of re-encoding, much faster but cuts are keyframe-approximate:

```sh
boris-clip annotations.boris --fast
```

## BORIS file formats

`boris-clip` auto-detects whichever format you provide:

| Format | Notes |
|---|---|
| `.boris` project file | Best option — contains video paths, FPS, and duration for validation |
| Tabular events CSV | Exported from BORIS via *Observations → Export events* |
| Aggregated events CSV | Exported from BORIS via *Observations → Export aggregated events* |

Multiple observations in a `.boris` project file are each processed independently and matched to their respective video by filename. Observations with no annotations are skipped automatically.

## Output file naming

Clips are named using the pattern:

```
{video_stem}_{behaviour}_{subject}_{start}-{stop}.mp4
```

- Times reflect the original annotation timestamps, not the padded clip boundaries, so names are stable regardless of padding settings.
- Subjects labelled *No focal subject* in BORIS become `no-focal-subject` in the filename.
- Special characters in behaviour or subject names are replaced with underscores.

## Validation

When a `.boris` project file is provided, `boris-clip` cross-checks the embedded metadata against the actual video via `ffprobe`:

- **Hard error** (use `--force` to override): media filename mismatch, annotation timestamps beyond video duration
- **Warning**: FPS mismatch between BORIS file and video, duration mismatch