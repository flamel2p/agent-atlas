"""Public surface for one validated, immutable learning experiment.

Only `load_scenario` reads fixture data. `run_experiment` is pure. Python permits
internal imports, so this documented boundary is not a security sandbox.
"""

from .experiment import ExperimentReport, run_experiment
from .scenarios import ScenarioError, ScenarioName, load_scenario

__all__ = ["ExperimentReport", "ScenarioError", "ScenarioName", "load_scenario", "run_experiment"]
