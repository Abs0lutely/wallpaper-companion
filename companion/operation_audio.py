"""Pure operation recording lookup shared by runtime and offline export."""
from pathlib import Path
from .action_lines import EVENT_LINES
from .core import AUDIO_EXTENSIONS

def scan_clips(roots, rules=None):
    from .operation_rules import default_rules
    result = {event: [] for event in EVENT_LINES}
    category_lines = {category: lines for category, lines in EVENT_LINES.values()}
    from .audio_names import matches_any_model
    for rule in rules if rules is not None else default_rules():
        event, category = rule["event"], rule["category"]
        lines = category_lines.get(category)
        for root in roots:
            folder = Path(root) / category
            if not folder.is_dir():
                continue
            try:
                paths = [str(p) for p in folder.iterdir() if p.is_file() and p.suffix.casefold() in AUDIO_EXTENSIONS and (lines is None or any(matches_any_model(p.stem,line) for line in lines))]
            except OSError:
                paths = []
            if paths:
                result[event] = paths
                break
    return result

