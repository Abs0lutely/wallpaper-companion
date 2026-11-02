# Japanese bundled default recordings

90 user-provided recordings, explicitly authorized for distribution: 38 companion and 52 operation responses. Companion files are under starter-voice-ja-JP, operation files under operation-voice-ja-JP. Every category ends in ·ja-JP. Chinese packs stay unchanged.

The combined manifest ../manifest.json records text, category, original model-tagged filename, bytes and SHA256 for all 180 Chinese/Japanese assets. The local starter manifest describes the 38 Japanese companion clips. All bundled recordings are read-only at runtime. Personal originals were copied, never moved or renamed.

Prepare only known Japanese default dialogue recordings with:

```powershell
.\.conda\python.exe scripts/prepare_translated_audio.py --source <generated-audio-root> --apply
```

The script matches the approved text lists, supports legacy unsuffixed companion directories, rejects ambiguous matches and different existing assets, validates WAV contents, and keeps Chinese resources. It does not copy other personal recordings or call a speech API.

Use Bundled demo voice language for empty personal voice folders; use Operation voice rules → Switch categories → Japanese for operation responses. UI language never changes the selected speech language.
