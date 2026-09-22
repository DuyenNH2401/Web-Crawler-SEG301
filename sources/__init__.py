"""Source-specific adapters for the shared crawler."""

from .bbc import BBCSource
from .cnn import CNNSource
from .globaltimes import GlobalTimesSource
from .guardian import GuardianSource
from .vnexpress import VnExpressSource


ALL_SOURCES = [
    VnExpressSource(),
    CNNSource(),
    BBCSource(),
    GuardianSource(),
    GlobalTimesSource(),
]

__all__ = ["ALL_SOURCES", "BBCSource", "CNNSource", "GlobalTimesSource", "GuardianSource", "VnExpressSource"]
