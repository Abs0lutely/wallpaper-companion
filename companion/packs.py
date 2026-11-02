"""Versioned, offline data-only companion packs. No network, GUI or model loading."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from .core import AUDIO_EXTENSIONS, candidates, new_profile, writable_path, audio_files
from .presets import export_payload, validate_payload, FORMAT as PRESET_FORMAT, RULE_FIELDS, NUMERIC, BOOLEAN
from .operation_rules import normalize_payload as normalize_operation
from .pack_text import p

FORMAT = 'wallpaper-companion-pack'
VERSION = 1
MIB = 1024 * 1024
MAX_ARCHIVE, MAX_TOTAL, MAX_FILES, MAX_FILE, MAX_JSON = 512*MIB, 1024*MIB, 5000, 256*MIB, 2*MIB
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}
META = {'id', 'name', 'character', 'language', 'author', 'description'}


def safe_name(name):
    if not isinstance(name,str) or not name or len(name)>240 or '\\' in name or name.startswith('/'):
        raise ValueError(p('unsafe'))
    parts=name.split('/')
    if any(not s or s in {'.','..'} or s.rstrip(' .')!=s or any(ord(c)<32 or c in '<>:"|?*' for c in s)
           or s.split('.')[0].upper() in RESERVED for s in parts):
        raise ValueError(p('unsafe'))
    return name


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(MIB),b''):h.update(block)
    return h.hexdigest()


def json_bytes(value):return json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')


def read_json(path):
    if Path(path).stat().st_size>MAX_JSON:raise ValueError(p('limit'))
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError(p('invalid'))
            result[k]=v
        return result
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
    except (UnicodeError,json.JSONDecodeError) as e:raise ValueError(p('invalid')) from e


def check_audio(path):
    """Conservative container checks; Qt decoding is additionally verified in UI tests."""
    path=Path(path)
    with path.open('rb') as f:head=f.read(64)
    ext=path.suffix.lower()
    valid=False
    if ext=='.wav':
        try:
            with wave.open(str(path),'rb') as f:
                expected=f.getnframes()*f.getnchannels()*f.getsampwidth()
                if not expected or f.getframerate()<=0:raise ValueError(p('bad_audio'))
                read=0
                while data:=f.readframes(65536):read+=len(data)
                valid=read==expected
        except (wave.Error,EOFError):valid=False
    elif ext=='.flac':valid=head.startswith(b'fLaC')
    elif ext in {'.ogg','.opus'}:valid=head.startswith(b'OggS')
    elif ext in {'.m4a','.aac'}:valid=(len(head)>12 and head[4:8]==b'ftyp') or (ext=='.aac' and len(head)>2 and head[0]==255 and head[1]&246==240)
    elif ext=='.mp3':valid=head.startswith(b'ID3') or (len(head)>2 and head[0]==255 and head[1]&224==224)
    elif ext=='.wma':valid=head.startswith(bytes.fromhex('3026b2758e66cf11a6d900aa0062ce6c'))
    if not valid:raise ValueError(p('bad_audio')+' '+path.name)


def validate_preset(payload):
    """Reject rather than silently discard secret/unsupported sender fields."""
    if not isinstance(payload,dict) or set(payload)!={'format','version','profiles'}:raise ValueError(p('path_leak'))
    profiles=payload.get('profiles')
    if not isinstance(profiles,list) or len(profiles)!=1:raise ValueError(p('invalid'))
    item=profiles[0]
    if not isinstance(item,dict) or set(item)!={'name','settings','rules','dialogues'}:raise ValueError(p('path_leak'))
    if not isinstance(item['settings'],dict) or set(item['settings'])-(NUMERIC.keys()|BOOLEAN):raise ValueError(p('path_leak'))
    if any(not isinstance(r,dict) or set(r)-RULE_FIELDS for r in item['rules']):raise ValueError(p('path_leak'))
    if any(not isinstance(d,dict) or set(d)-{'id','text','category','enabled'} for d in item['dialogues']):raise ValueError(p('path_leak'))
    cleaned,_=validate_payload(payload)
    for r in cleaned[0]['rules']:
        if r['source']:safe_name(r['source'])
    return cleaned[0]


def audio_for_line(root,entry):
    from .audio_names import matching_files
    return matching_files(Path(root)/entry['category'],entry['text'])


@dataclass
class CheckedPack:
    root: Path
    manifest: dict
    profile: dict
    content_id: str
    operation: dict | None
    @property
    def recordings(self):return len([f for f in self.manifest['files'] if f['path'].startswith('voice/')])
    @property
    def missing(self):return [d for d in self.profile['dialogues'] if d['enabled'] and not audio_for_line(self.root/'voice',d)]
    @property
    def complete(self):return not self.missing and self.recordings>0 and all(not r['enabled'] or candidates(dict(voice_dir=str(self.root/'voice'),use_bundled_demo=False),r) for r in self.profile['rules'])


def validate_directory(root):
    root=Path(root).resolve()
    manifest=read_json(root/'pack.json')
    if not isinstance(manifest,dict) or set(manifest)!={'format','version',*META,'preview','files','missing_sources'} or manifest['format']!=FORMAT or type(manifest['version']) is not int or manifest['version']!=VERSION:raise ValueError(p('invalid'))
    for key in META:
        value=manifest[key]
        if not isinstance(value,str) or len(value)>(2000 if key=='description' else 200) or (key in {'id','name','language'} and not value.strip()):raise ValueError(p('invalid'))
    if not isinstance(manifest['missing_sources'],list) or len(manifest['missing_sources'])>5000 or any(not isinstance(x,str) or len(x)>1000 for x in manifest['missing_sources']):raise ValueError(p('invalid'))
    files=manifest['files']
    if not isinstance(files,list) or not 1<=len(files)<MAX_FILES:raise ValueError(p('limit'))
    names={'pack.json'}; folded={'pack.json'};total=(root/'pack.json').stat().st_size
    for entry in files:
        if not isinstance(entry,dict) or set(entry)!={'path','size','sha256'}:raise ValueError(p('invalid'))
        name=safe_name(entry['path'])
        if name.casefold() in folded:raise ValueError(p('unsafe'))
        if name not in {'preset.json','operation-rules.json'} and (PurePosixPath(name).parts[0] not in {'voice','bgm','operation-voice'} or PurePosixPath(name).suffix.lower() not in AUDIO_EXTENSIONS):raise ValueError(p('unsafe'))
        if type(entry['size']) is not int or not 0<entry['size']<=MAX_FILE or not re.fullmatch('[0-9a-f]{64}',str(entry['sha256'])):raise ValueError(p('invalid'))
        file=root/name
        if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file() or file.stat().st_size!=entry['size'] or digest(file)!=entry['sha256']:raise ValueError(p('invalid'))
        total+=entry['size']
        if total>MAX_TOTAL:raise ValueError(p('limit'))
        if file.suffix.lower() in AUDIO_EXTENSIONS:check_audio(file)
        names.add(name);folded.add(name.casefold())
    actual={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file()}
    if names!=actual or 'preset.json' not in names:raise ValueError(p('invalid'))
    for f in root.rglob('*'):
        if f.is_symlink() or getattr(f.stat(),'st_file_attributes',0)&0x400:raise ValueError(p('unsafe'))
    profile=validate_preset(read_json(root/'preset.json'))
    if any(parent.as_posix().casefold() in folded for name in names for parent in PurePosixPath(name).parents if parent.as_posix()!='.'):
        raise ValueError(p('unsafe'))
    preview=manifest['preview']
    if not isinstance(preview,str) or preview and (preview not in names or not preview.startswith('voice/')):raise ValueError(p('invalid'))
    operation=normalize_operation(read_json(root/'operation-rules.json')) if 'operation-rules.json' in names else None
    if operation:
        raw=read_json(root/'operation-rules.json')
        if set(raw)-{'format','version','enabled','min_interval','rules'} or any(set(r)-{'event','enabled','category','cooldown'} for r in raw['rules']):raise ValueError(p('path_leak'))
    elif any(n.startswith('operation-voice/') for n in names):raise ValueError(p('invalid'))
    content_id=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return CheckedPack(root,manifest,profile,content_id,operation)


class PackPreview:
    """Owns only a newly created extraction tree; close never deletes installed data."""
    def __init__(self,archive,temporary):
        temporary=Path(temporary);temporary.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='inspect-',dir=temporary)
        try:
            archive=Path(archive)
            if archive.stat().st_size>MAX_ARCHIVE:raise ValueError(p('limit'))
            root=Path(self.temp.name)
            with zipfile.ZipFile(archive) as zip:
                entries=zip.infolist()
                if len(entries)>MAX_FILES:raise ValueError(p('limit'))
                seen=set();total=0
                for info in entries:
                    safe_name(info.filename.rstrip('/') if info.is_dir() else info.filename)
                    if info.filename.casefold() in seen:raise ValueError(p('unsafe'))
                    seen.add(info.filename.casefold())
                    mode=info.external_attr>>16
                    if stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR) or info.flag_bits&1:raise ValueError(p('unsafe'))
                    if info.file_size>MAX_FILE or info.filename.lower().endswith('.json') and info.file_size>MAX_JSON:raise ValueError(p('limit'))
                    total+=info.file_size
                    if total>MAX_TOTAL:raise ValueError(p('limit'))
                # Read the inventory before extracting any non-manifest file.
                info=zip.getinfo('pack.json')
                if info.file_size>MAX_JSON:raise ValueError(p('limit'))
                (root/'pack.json').write_bytes(zip.read(info))
                manifest=read_json(root/'pack.json')
                if not isinstance(manifest,dict) or not isinstance(manifest.get('files'),list):raise ValueError(p('invalid'))
                listed=set();inventory={}
                for entry in manifest['files']:
                    if not isinstance(entry,dict) or set(entry)!={'path','size','sha256'}:raise ValueError(p('invalid'))
                    name=safe_name(entry['path'])
                    if name in listed or name.casefold() in {n.casefold() for n in listed}:raise ValueError(p('unsafe'))
                    if name not in {'preset.json','operation-rules.json'} and (PurePosixPath(name).parts[0] not in {'voice','bgm','operation-voice'} or PurePosixPath(name).suffix.lower() not in AUDIO_EXTENSIONS):raise ValueError(p('unsafe'))
                    if type(entry['size']) is not int or not 0<entry['size']<=MAX_FILE or not re.fullmatch('[0-9a-f]{64}',str(entry['sha256'])):raise ValueError(p('invalid'))
                    listed.add(name);inventory[name]=entry
                if {i.filename for i in entries if not i.is_dir()}!=listed|{'pack.json'}:raise ValueError(p('invalid'))
                for info in entries:
                    if info.is_dir() or info.filename=='pack.json':continue
                    safe_name(info.filename)
                    if inventory[info.filename]['size']!=info.file_size:raise ValueError(p('invalid'))
                    target=root/info.filename
                    if not target.resolve().is_relative_to(root):raise ValueError(p('unsafe'))
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with zip.open(info) as source,target.open('xb') as dest:
                        length=0
                        while block:=source.read(MIB):
                            length+=len(block)
                            if length>info.file_size or length>MAX_FILE:raise ValueError(p('limit'))
                            dest.write(block)
                self.pack=validate_directory(root)
        except Exception:
            self.close();raise
    def close(self):self.temp.cleanup()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def install_and_use(store,pack,include_operation=False):
    """Save profile + optional global response settings in one transaction."""
    pack=validate_directory(pack.root)
    base=writable_path(store.path.parent/'packs',store.protected());base.mkdir(parents=True,exist_ok=True)
    created=None;destination=None
    for item in base.iterdir():
        if item.is_dir() and not item.is_symlink():
            try:
                existing=validate_directory(item)
                if existing.content_id==pack.content_id:destination=item;break
            except (ValueError,OSError,KeyError,TypeError):pass
    try:
        if destination is None:
            destination=base/uuid.uuid4().hex
            # A unique, transaction-owned path; never delete another install.
            destination.mkdir();created=destination
            shutil.copytree(pack.root,destination,dirs_exist_ok=True)
            validate_directory(destination)
        previous=copy.deepcopy(store.config)
        profile=new_profile(pack.manifest['name'])
        profile.update(pack.profile['settings'],dialogues=copy.deepcopy(pack.profile['dialogues']),rules=copy.deepcopy(pack.profile['rules']))
        profile.update(wallpaper='',voice_dir=str(destination/'voice'),bgm_dir=str(destination/'bgm'),
            asset_dir='',private_asset_dir='',dialogue_file='',use_bundled_demo=False,pack_install=destination.name)
        # IDs must be fresh even when the same pack is used twice.
        for rule in profile['rules']:rule['id']=uuid.uuid4().hex
        updated=copy.deepcopy(previous);updated['profiles'].append(profile)
        updated.update(run_mode='standalone',standalone_profile=profile['id'])
        if include_operation and pack.operation:
            updated.update(operation_voice_enabled=pack.operation['enabled'],operation_voice_rules=pack.operation['rules'],
                operation_voice_min_interval=pack.operation['min_interval'],operation_voice_dir=str(destination/'operation-voice'),operation_voice_pack_only=True)
        store.config=updated
        try:store.save()
        except Exception:store.config=previous;raise
        return profile['id'],previous
    except Exception:
        if created:shutil.rmtree(created)
        raise


def restore_selection(store,previous):
    """Restore active selection only, never roll back unrelated settings or new profiles."""
    updated=copy.deepcopy(store.config)
    target=previous.get('standalone_profile') if previous.get('run_mode')=='standalone' else previous.get('manual_profile')
    if target and not store.profile(target):raise ValueError(p('no_previous'))
    for key in ('run_mode','standalone_profile','manual_profile'):updated[key]=previous.get(key, 'wallpaper_engine' if key=='run_mode' else '')
    old=store.config;store.config=updated
    try:store.save()
    except Exception:store.config=old;raise


@dataclass
class ExportPlan:
    metadata: dict
    preset: dict
    sources: dict
    stamps: dict
    missing: list
    operation: dict | None


def plan_export(profile,metadata,*,include_bgm=False,operation=None,operation_roots=()):
    """Collect real engine candidates; snapshot hashes, preserve unresolved rules."""
    from .assets import load_dialogues
    from .operation_audio import scan_clips
    source_profile=copy.deepcopy(profile);source_profile['dialogues']=load_dialogues(profile)
    source_profile['use_bundled_demo']=False
    preset,_=export_payload([source_profile])
    sources={};missing=[]
    def add(path,name):
        safe_name(name);path=Path(path)
        if not path.is_file() or path.is_symlink():raise ValueError(p('unsafe'))
        if any(n.casefold()==name.casefold() and str(p)!=str(path) for n,p in sources.items()):raise ValueError(p('unsafe'))
        sources[name]=path.resolve()
    for original,rule in zip(profile.get('rules',[]),preset['profiles'][0]['rules']):
        raw=original.get('source','').strip()
        base=Path(profile.get('voice_dir') or '.')
        root=Path(raw) if Path(raw).is_absolute() else base/raw
        files=candidates(profile,original)
        # External references get unique, predictable relative destinations.
        try:relative=root.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:relative='external/'+hashlib.sha256(str(root).encode()).hexdigest()[:12]+('/'+root.name if root.is_file() else '')
        rule['source']='' if relative=='.' else relative
        safe_name(rule['source'] or 'voice')
        if not files:missing.append(rule['name']+' → '+(rule['source'] or 'voice/'))
        for path in files:
            path=Path(path)
            try:name=path.resolve().relative_to(base.resolve()).as_posix()
            except ValueError:
                name=relative if root.is_file() else relative+'/'+path.relative_to(root).as_posix()
            # Factory fallback files keep the requested category instead of their installation path.
            if profile.get('use_bundled_demo') and not audio_files(profile.get('voice_dir','')):
                name=(rule['source']+'/' if rule['source'] and not Path(rule['source']).suffix else '')+path.name
                if not raw:
                    name=path.parent.name+'/'+path.name
            add(path,'voice/'+name)
    # Unused lines are still included as text; report missing recordings explicitly.
    from .audio_names import matches_any_model
    for line in source_profile['dialogues']:
        if line['enabled'] and not any(n.startswith('voice/'+line['category']+'/') and matches_any_model(Path(n).stem,line['text']) for n in sources):
            missing.append(line['category']+'/'+line['text'])
    if include_bgm:
        files=audio_files(profile.get('bgm_dir',''))
        if not files:missing.append('bgm/')
        for file in files:add(file,'bgm/'+file.relative_to(Path(profile['bgm_dir'])).as_posix())
    preset['profiles'][0]['settings']['bgm_enabled']=bool(include_bgm and profile.get('bgm_enabled',True))
    preset['profiles'][0]['settings']['use_bundled_demo']=False
    if operation:
        operation=normalize_operation(operation)
        clips=scan_clips(operation_roots,operation['rules'])
        for rule in operation['rules']:
            paths=clips.get(rule['event'],[])
            if rule['enabled'] and not paths:missing.append('operation-voice/'+rule['category'])
            for path in paths:add(path,'operation-voice/'+rule['category']+'/'+Path(path).name)
    meta={k:str(metadata.get(k,'')) for k in META};meta['id']=meta['id'] or uuid.uuid4().hex
    stamps={name:(file.stat().st_size,digest(file)) for name,file in sources.items()}
    validate_preset(preset)
    return ExportPlan(meta,preset,sources,stamps,list(dict.fromkeys(missing)),operation)


def write_export(plan,target,selected=None,protected=()):
    target=writable_path(target,protected)
    if target.suffix.lower()!='.wcpak':raise ValueError(p('invalid'))
    names=set(plan.sources) if selected is None else set(selected)
    if names-set(plan.sources):raise ValueError(p('invalid'))
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='export-',dir=target.parent) as tmp:
        root=Path(tmp)/'payload';root.mkdir()
        if len(names)+3>MAX_FILES or sum(plan.stamps[n][0] for n in names)>MAX_TOTAL or any(plan.stamps[n][0]>MAX_FILE for n in names):raise ValueError(p('limit'))
        (root/'preset.json').write_bytes(json_bytes(plan.preset))
        if plan.operation:(root/'operation-rules.json').write_bytes(json_bytes(plan.operation))
        for name in sorted(names):
            source=plan.sources[name]
            if (source.stat().st_size,digest(source))!=plan.stamps[name]:raise ValueError(p('changed'))
            dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        files=[dict(path=f.relative_to(root).as_posix(),size=f.stat().st_size,sha256=digest(f)) for f in sorted(root.rglob('*')) if f.is_file()]
        manifest=dict(format=FORMAT,version=VERSION,**plan.metadata,preview=next((n for n in sorted(names) if n.startswith('voice/')),''),files=files,
                      missing_sources=plan.missing+[n for n in sorted(plan.sources) if n not in names])
        (root/'pack.json').write_bytes(json_bytes(manifest))
        validate_directory(root)
        archive=Path(tmp)/'result.wcpak'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zip:
            for file in sorted(root.rglob('*')):
                if file.is_file():zip.write(file,file.relative_to(root).as_posix())
        if archive.stat().st_size>MAX_ARCHIVE:raise ValueError(p('limit'))
        os.replace(archive,target)
    return target
