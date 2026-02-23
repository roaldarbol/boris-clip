"""Core data models for boris-clip."""

from dataclasses import dataclass, field


@dataclass
class VideoInfo:
    """Metadata extracted from a video file via ffprobe."""

    path: str
    filename: str
    duration: float  # seconds
    fps: float


@dataclass
class Bout:
    """A single annotated behavioural bout."""

    subject: str
    behaviour: str
    start: float  # seconds
    stop: float  # seconds
    is_point: bool = False

    @property
    def duration(self) -> float:
        return self.stop - self.start

    def with_padding(
        self,
        pre: float = 0.0,
        post: float = 0.0,
        video_duration: float | None = None,
    ) -> "Bout":
        """Return a new Bout with padding applied, clamped to video bounds."""
        new_start = max(0.0, self.start - pre)
        new_stop = self.stop + post
        if video_duration is not None:
            new_stop = min(video_duration, new_stop)
        return Bout(
            subject=self.subject,
            behaviour=self.behaviour,
            start=new_start,
            stop=new_stop,
            is_point=self.is_point,
        )


@dataclass
class ParsedAnnotations:
    """Result of parsing a BORIS file."""

    bouts: list[Bout]
    obs_id: str | None = None          # observation ID, populated for .boris project files
    media_filename: str | None = None  # best-effort from the file
    media_path: str | None = None      # full path, only available from .boris project files
    fps: float | None = None
    duration: float | None = None
    source_format: str = "unknown"