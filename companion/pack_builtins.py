"""Included packs are materialized from approved read-only resources, never personal audio."""
from pathlib import Path
from .core import ROOT

def builtin_catalog():
    path=ROOT/'examples/packs/catalog.json'
    if not path.is_file():return []
    from .packs import read_json
    return read_json(path)['packs']

def prepare_builtin(identifier,temporary):
    from .pack_text import p
    raise ValueError(p('invalid'))
