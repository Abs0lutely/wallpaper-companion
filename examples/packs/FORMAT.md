# Companion pack v1 / 陪伴包 v1

`.wcpak` is a ZIP containing data only. Use the application's exporter rather than manually editing inventories. / 建议使用界面导出，避免手工清单出错。

## Members / 内容

- `pack.json`: strict metadata and inventory (itself excluded from the inventory).
- `preset.json`: existing `wallpaper-companion-preset`, version 1, exactly one profile; `name`, whitelist `settings`, `rules`, `dialogues`. All voice rule sources relative to `voice/`.
- `voice/<category>/<recording>`: companion audio. Category names retain language suffixes.
- `bgm/<recording>`: optional BGM.
- `operation-voice/<category>/<recording>` and `operation-rules.json`: optional existing `wallpaper-companion-operation-rules`, version 1.

## pack.json

```json
{
  "format": "wallpaper-companion-pack",
  "version": 1,
  "id": "publisher-defined-stable-id",
  "name": "Example",
  "character": "Voice description",
  "language": "ja-JP",
  "author": "Author",
  "description": "Pack description",
  "preview": "voice/example/hello.wav",
  "files": [
    {"path": "preset.json", "size": 123, "sha256": "<64 lowercase hex characters>"},
    {"path": "voice/example/hello.wav", "size": 456, "sha256": "<64 lowercase hex characters>"}
  ],
  "missing_sources": []
}
```

The sizes/hashes above are illustrative, not valid sample data. `preview` may be empty for text-only packs. Metadata IDs are never used as directory names. Canonicalized complete manifest SHA256 identifies duplicate content; a randomly generated install ID names the installed directory. Metadata is not an executable instruction or verified identity.

上例大小和哈希为示意。无音频时 `preview` 为空；`missing_sources` 列出规则来源、未配音台词及取消选择的包内相对路径，不包含本机绝对路径。安装目录使用程序随机 ID，而不是包作者提供的 ID。相同内容复用资源，使用操作仍新建方案。

## Validation / 校验

Archive <=512 MiB; expanded <=1 GiB; <=5,000 entries; each file <=256 MiB; each JSON <=2 MiB. Standard-library `zipfile` reads entries individually into a unique temporary tree; no `extractall`. Inventory must exactly match file members. All file sizes and SHA256 values are checked. JSON duplicate keys, encrypted members, links/reparse flags, unsupported file types, executable containers, absolute/traversal paths, case-insensitive collisions, reserved Windows names and unknown/credential-bearing profile fields are rejected.

允许音频扩展名沿用播放器：`.wav .mp3 .ogg .flac .m4a .aac .wma .opus`。WAV 核对容器和实际帧长度，其他格式做头部检查；不等于完整解码所有压缩音轨。Qt 实际试听仍可能报告编码问题。安全路径限制为 240 字符以内的包内路径，比部分文件系统上限保守。

Limits and canonical validation live in `companion/packs.py`; inventory completeness is not a signature. External resources are copied and rewritten only in the exported preset. Missing sources retain their rules. Models, credentials, references, plugins, wallpaper paths and executable content are not valid pack members.

## Transactions / 事务

Preview uses `data/pack-temp/inspect-*`; successful use installs into `data/packs/<random-ID>/`, embeds dialogues, disables other included-voice fallback and selects standalone mode. Optional global operation responses require explicit consent and use only the package's response root. On save/copy failure, prior config is restored and only the transaction-owned installation is removed. Existing matching installations remain. Preview cancel removes only preview resources. Export stages a validated archive then atomically replaces the chosen output; source files are read only.

“切回原方案”只恢复运行模式与活动方案选择，不回滚全局操作回应、不删除包、不撤销随后编辑。原来的 JSON 预设格式不受影响。

## Included catalog / 随附包

`catalog.json` describes Chinese/Japanese Gentle Days: each 38 companion recordings plus 52 optional operation recordings. `companion/pack_builtins.py` assembles them from the existing approved `examples/audio/` inventory on demand. No second copy of all audio is committed. The future Windows build validates catalog counts/hashes before freezing and copies the whole `examples/` tree. Runtime-generated `.wcpak` and installed copies are user data and must not be committed.
