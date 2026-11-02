"""Run the new multilingual/standalone workflows with an English interface."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("smoke_multilingual.py")),init_globals={"TEST_LANGUAGE":"en-US"})
