"""Run the same native language workflow in a fresh Chinese process."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("smoke_i18n.py")), init_globals={"TEST_LANGUAGE": "zh-CN"})
