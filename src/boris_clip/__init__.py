"""boris-clip: extract video clips from BORIS behavioural annotations."""

from .models import Bout, ParsedAnnotations, VideoInfo

__version__ = "0.2.0"
__all__ = ["Bout", "ParsedAnnotations", "VideoInfo"]