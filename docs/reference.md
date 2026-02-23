# CLI Reference

## Arguments

| Argument | Description |
|---|---|
| `BORIS_FILE` | Path to a `.boris` project file or BORIS CSV export |
| `[VIDEO ...]` | Optional. One or more video files. If omitted, paths embedded in the `.boris` file are used. Multiple videos are matched to observations by filename. |

## Options

| Option | Default | Description |
|---|---|---|
| `-o`, `--output-dir` | `clips/` | Directory to write output clips into |
| `-b`, `--behaviour`, `--behavior` | — | Only extract clips for this behaviour. Can be repeated: `-b REM -b walking` |
| `--padding SECONDS` | `0` | Add this many seconds before and after each state event bout |
| `--padding-pre SECONDS` | `0` | Seconds to add before each bout (overrides `--padding` for the pre side) |
| `--padding-post SECONDS` | `0` | Seconds to add after each bout (overrides `--padding` for the post side) |
| `--point-padding SECONDS` | `5` | Padding for point events, both sides (defaults to 5s if no general padding is set) |
| `--point-padding-pre SECONDS` | — | Pre-padding for point events (overrides `--point-padding`) |
| `--point-padding-post SECONDS` | — | Post-padding for point events (overrides `--point-padding`) |
| `--max-duration SECONDS` | — | Truncate clips longer than this many seconds (from the end, after padding) |
| `--max-clips N` | — | Maximum clips per (behaviour, subject) group; earlier bouts take priority |
| `--fast` | off | Use stream-copy instead of re-encoding. Much faster, but cut points snap to the nearest keyframe |
| `--force` | off | Downgrade hard errors (mismatched media file, out-of-bounds annotations) to warnings |
| `--version` | — | Show version and exit |
| `--help` | — | Show help and exit |

## Padding precedence

Padding follows a CSS-like precedence: `--padding` sets both sides, while `--padding-pre` and `--padding-post` override their respective side independently.

```sh
# 2s before and after
--padding 2.0

# 2s after only
--padding-post 2.0

# 1s before, 3s after (--padding-pre overrides --padding on the pre side)
--padding 3.0 --padding-pre 1.0
```

Point events have no inherent duration, so padding is always applied. If no point-specific padding is set, the general `--padding` value is used; if no padding is set at all, a default of 5 seconds each side is applied.

## Re-encoding vs. stream-copy

By default, `boris-clip` re-encodes clips using ffmpeg. This is slower but frame-accurate — cuts land exactly at the annotated timestamp.

With `--fast`, ffmpeg uses stream-copy, which skips re-encoding and is significantly faster. The trade-off is that cuts snap to the nearest keyframe, which can be a second or two away from the annotation. This is fine for a quick preview but may not be suitable for precise analysis.