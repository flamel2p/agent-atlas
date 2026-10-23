"""Public workflow for validated, deterministic physical-world simulation.

``parse_scenario`` owns the input trust boundary. ``run_replay`` consumes that
immutable scenario and returns a JSON-ready report without external effects.
"""

from .schema import ScenarioError, parse_scenario
from .replay import run_replay

__all__ = ["ScenarioError", "parse_scenario", "run_replay"]
