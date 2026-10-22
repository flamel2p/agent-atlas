"""Case-local disposable workspaces with the same ownership markers as a copy."""

from importlib.resources import files
from pathlib import Path
import tempfile
import unittest


def fixture(name="repaired.txt"):
    return files("code_generation_agent").joinpath("fixtures", name).read_text(encoding="utf-8")


def function(body):
    return "def shipping_fee(weight_kg, subtotal_rm):\n" + "\n".join(
        "    " + line for line in body.splitlines()
    ) + "\n"


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        artifact_root = Path(__file__).resolve().parents[1] / "artifacts"
        artifact_root.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="test-", dir=artifact_root)
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        (self.workspace / "SPEC.md").write_text("Slug: 13-code-generation\n", encoding="utf-8")
        (self.workspace / "pyproject.toml").write_text(
            '[project]\nname = "agent-atlas-13-code-generation"\n', encoding="utf-8"
        )
