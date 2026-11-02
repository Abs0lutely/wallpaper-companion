"""Included packs are assembled from approved read-only defaults, without duplicate audio."""
import tempfile
from pathlib import Path
from .core import ROOT,new_profile,new_rule
from .packs import read_json,plan_export,write_export,PackPreview


def builtin_catalog():
    path=ROOT/'examples/packs/catalog.json'
    return read_json(path)['packs'] if path.is_file() else []


def prepare_builtin(identifier,temporary):
    from .bundled_audio import bundled_root,validate_bundled_manifest
    from .dialogues import starter_dialogues,dialogue_rules
    from .voice_locales import translated_lines,category_for,switch_operation_categories
    from .operation_rules import default_rules,normalize_payload,FORMAT
    from .pack_text import p
    entry=next((item for item in builtin_catalog() if item['id']==identifier),None)
    if entry is None:raise ValueError(p('invalid'))
    root=bundled_root();validate_bundled_manifest(root)
    ja=entry['language']=='ja-JP';locale=entry['language']
    profile=new_profile(entry['name']);profile.update(voice_dir=str(root/('starter-voice-ja-JP' if ja else 'starter-voice')),
        use_bundled_demo=False,dialogues=translated_lines('starter',locale) if ja else starter_dialogues(),rules=dialogue_rules())
    for rule in profile['rules']:rule['source']=category_for(rule['source'],locale)
    idle=new_rule('random','闲置陪伴 / Quiet company');idle.update(source=category_for('闲置陪伴',locale),interval_min=600,interval_max=1200)
    evening=new_rule('scheduled','晚安 / Good night');evening.update(source=category_for('夜间',locale),at='22:30')
    profile['rules'].extend([idle,evening])
    rules,_=switch_operation_categories(default_rules(),locale)
    operation=normalize_payload(dict(format=FORMAT,version=1,enabled=True,min_interval=1.2,rules=rules))
    plan=plan_export(profile,entry,operation=operation,operation_roots=[root/('operation-voice-ja-JP' if ja else 'operation-voice')])
    temporary=Path(temporary);temporary.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='builtin-',dir=temporary) as tmp:
        archive=write_export(plan,Path(tmp)/'included.wcpak')
        preview=PackPreview(archive,temporary)
    return preview


def validate_builtin_catalog():
    """Future build prerequisite, not an installer or binary build."""
    from .bundled_audio import bundled_root,validate_bundled_manifest
    manifest=validate_bundled_manifest(bundled_root())
    entries=builtin_catalog()
    if len(entries)!=2 or {e['language'] for e in entries}!={'zh-CN','ja-JP'}:raise ValueError('Included pack catalog is incomplete')
    for entry in entries:
        suffix='-ja-JP' if entry['language']=='ja-JP' else ''
        files=[f for f in manifest['files'] if f['pack'] in {'starter-voice'+suffix,'operation-voice'+suffix}]
        if len(files)!=90 or sum(f['bytes'] for f in files)!=entry['bytes'] or entry['recordings']!=38 or entry['operation_recordings']!=52:raise ValueError('Included pack inventory mismatch')
    return entries
