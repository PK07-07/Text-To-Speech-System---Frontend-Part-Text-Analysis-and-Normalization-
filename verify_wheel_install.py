"""Build wheel, install in isolated temporary virtual environment outside repo, and verify normalization."""
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parent
wheel_files = list((repo_root / "dist").glob("text_frontend-*.whl"))
if not wheel_files:
    print("No wheel file found in dist/")
    sys.exit(1)

wheel_path = sorted(wheel_files)[-1]
print(f"Testing wheel: {wheel_path.name}")

# Create temp dir for venv
temp_dir = Path(tempfile.gettempdir()) / "text_frontend_clean_venv"
if temp_dir.exists():
    shutil.rmtree(temp_dir)

print(f"Creating isolated virtualenv in: {temp_dir}")
subprocess.run([sys.executable, "-m", "venv", str(temp_dir)], check=True)

if sys.platform == "win32":
    venv_python = temp_dir / "Scripts" / "python.exe"
else:
    venv_python = temp_dir / "bin" / "python"

print("Installing wheel into clean virtualenv...")
subprocess.run([str(venv_python), "-m", "pip", "install", str(wheel_path)], check=True)

test_code = """
import text_frontend
from text_frontend import normalize, NormalizerConfig

print("Installed package location:", text_frontend.__file__)
print("Installed package version:", text_frontend.__version__)

# Required test cases:
# 1. normalize("Dr. Smith at 12:00")
res1 = normalize("Dr. Smith at 12:00")
print("Case 1: normalize('Dr. Smith at 12:00') ->", repr(res1.normalized_text))
assert res1.normalized_text == "Doctor Smith at noon"

# 2. All-caps case ("PLEASE CALL ME, THE US ECONOMY")
res2 = normalize("PLEASE CALL ME, THE US ECONOMY")
print("Case 2: normalize('PLEASE CALL ME, THE US ECONOMY') ->", repr(res2.normalized_text))
assert res2.normalized_text == "please call me, the U S economy"

# 3. Emoji verbalize case
cfg_verb = NormalizerConfig.for_locale("en-US", emoji_policy="verbalize")
res3 = normalize("Hello 👋 world!", config=cfg_verb)
print("Case 3: Emoji verbalize ->", repr(res3.normalized_text))
assert res3.normalized_text == "Hello waving hand world!"

print("SUCCESS: Wheel installation and normalization verified in clean environment outside repo!")
"""

print("\n--- Running verification inside clean virtual environment ---")
res = subprocess.run([str(venv_python), "-c", test_code], cwd=str(temp_dir), capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)
if res.returncode != 0:
    sys.exit(res.returncode)

# Cleanup
shutil.rmtree(temp_dir, ignore_errors=True)
print("Clean virtualenv removed.")
