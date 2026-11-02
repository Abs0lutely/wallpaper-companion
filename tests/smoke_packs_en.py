import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('smoke_packs.py')),init_globals={'TEST_LANGUAGE':'en-US'})
