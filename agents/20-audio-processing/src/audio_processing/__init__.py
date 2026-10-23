"""Public operations use the installed package's fixed replay resources.

Neither operation accepts annotations, a provider, or a manifest path. Asset
errors become typed rejections before any input analysis. Each call owns all
state and validates resources again so a broken installation fails closed.
"""

from .assets import AssetError, FIXTURE_IDS, load_assets
from .core import Analysis, Mode, Outcome, Rejected, analyze_validated_assets

__all__ = ["Analysis", "FIXTURE_IDS", "Mode", "Rejected", "analyze", "analyze_fixture"]


def _arguments(wav_bytes: bytes, mode: Mode) -> None:
    if type(wav_bytes) is not bytes or not isinstance(mode, Mode):
        raise TypeError("Expected immutable WAV bytes and a Mode value.")


def analyze(wav_bytes: bytes, mode: Mode = Mode.CLEAN) -> Outcome:
    """Measure local bytes with only fixed package annotations as replay authority."""
    _arguments(wav_bytes, mode)
    try:
        assets = load_assets()
    except AssetError as error:
        return Rejected("invalid_assets", str(error))
    return analyze_validated_assets(wav_bytes, mode, assets.fixtures)


def analyze_fixture(fixture_id: str, mode: Mode = Mode.CLEAN) -> Outcome:
    """Analyze one allowlisted packaged WAV without a path or annotation override."""
    if fixture_id not in FIXTURE_IDS:
        raise ValueError("Unknown packaged fixture.")
    _arguments(b"", mode)
    try:
        assets = load_assets()
    except AssetError as error:
        return Rejected("invalid_assets", str(error))
    return analyze_validated_assets(assets.waveform(fixture_id), mode, assets.fixtures)
