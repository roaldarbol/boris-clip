---
hide:
  - navigation
  - toc
---

<h1 align="center">boris-clip</h1>

<p align="center">
  <a href="https://pypi.org/project/boris-clip"><img src="https://img.shields.io/pypi/v/boris-clip?color=teal&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/boris-clip"><img src="https://img.shields.io/pypi/pyversions/boris-clip?color=teal" alt="Python versions"></a>
  <a href="https://github.com/roaldarbol/boris-clip/blob/main/LICENSE"><img src="https://img.shields.io/github/license/roaldarbol/boris-clip?color=teal" alt="License"></a>
  <a href="https://github.com/roaldarbol/boris-clip/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/roaldarbol/boris-clip/ci.yml?label=CI&color=teal" alt="CI status"></a>
</p>

<p align="center"><em>Extract video clips from <a href="https://www.boris.unito.it/">BORIS</a> behavioural annotation files.</em></p>

---

For each annotated bout in a BORIS file, `boris-clip` cuts the corresponding segment from your video and saves it as an individual clip. Clips are named after the source video, behaviour, subject, and time interval — making them easy to sort and identify without opening them.

```
recording_REM_ind1_10.033-15.766.mp4
recording_grooming_ind2_42.100-48.500.mp4
```

## Quickstart

```sh
# Install globally
uv tool install boris-clip

# Run on your .boris project file
boris-clip annotations.boris
```

Clips are saved to a `clips/` directory in the current folder. See the [Installation](installation.md) page for all install options, or the [Usage](usage.md) guide for more examples.

## Contributing

Bug reports and pull requests are welcome on [GitHub](https://github.com/roaldarbol/boris-clip).

## License

MIT