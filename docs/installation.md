# Installation

`boris-clip` requires [ffmpeg](https://ffmpeg.org/) to be installed and available on your `PATH`.

## Global installation (recommended)

Install `boris-clip` as a standalone tool, available system-wide without activating any environment.

=== "uv"

    ```sh
    uv tool install boris-clip
    ```

    ffmpeg must be installed separately, e.g. via `brew install ffmpeg`, `conda install -c conda-forge ffmpeg`, or your system package manager.

=== "pixi"

    ```sh
    pixi global install boris-clip
    ```

    ffmpeg is pulled in automatically from conda-forge.

## Into an existing environment

=== "uv"

    ```sh
    uv add boris-clip
    ```

=== "pixi"

    ```sh
    pixi add boris-clip
    ```

=== "pip"

    ```sh
    pip install boris-clip
    ```