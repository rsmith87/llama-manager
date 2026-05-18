import shutil
import subprocess
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_TESTS_DIR = ROOT_DIR / "frontend-tests"


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is required for frontend tests")
def test_frontend_unit_tests_pass():
    subprocess.run(["npm", "ci"], cwd=FRONTEND_TESTS_DIR, check=True)
    subprocess.run(["npm", "test"], cwd=FRONTEND_TESTS_DIR, check=True)
