# Wallpaper Companion: Features and fields user guide

## Multilingual voices and standalone use

Choose **Mode → Standalone sound companion** from home or Settings. With no profiles, a **My sound space** profile is created. No Wallpaper Engine is required for mouse, hotkey, timed voice or BGM. Desktop-only input remains the default and can be changed. This mode stops WE polling and wallpaper-audio detection, keeps bindings and remembers its own profile choice. Returning to WE preserves its previous manual choice; mode switching supports undo. It does not set the Windows desktop wallpaper.

The dialogue library now has one generation route: **Send checked lines to generation**. It retains categories, output and duplicate settings. Generate there to save into category subfolders. Editing transferred text visibly switches to ordinary lines without the original categories.

All default English/Japanese categories use **·en-US / ·ja-JP** suffixes. **Update legacy translation categories…** previews known legacy entries before confirmation and saving, preferring stable IDs plus exact text and allowing old imported IDs. Custom categories/text remain unchanged. Existing recordings are not moved or renamed; known legacy translations have restricted old-folder lookup.

Choose a language beside **Apply category trigger rules** to create matching categories; confirmation still replaces the draft rules. Examples: examples/presets/interaction-ja-JP.json and interaction-en-US.json.

In **Settings → Operation voice rules…**, choose Chinese, Japanese or English and click **Switch categories**. It changes known default actions together, preserving custom categories, toggles and cooldowns. Save to apply. English actions without recordings stay silent until you generate them.

There are **180 bundled recordings: 90 Chinese and 90 Japanese**, each with 38 companion and 52 operation clips. **Bundled demo voice language** selects samples when the personal voice folder is empty. Personal audio takes priority; operation language is controlled separately by its rules. UI language never changes speech automatically. English dialogue and the 72-line Gentle Replies pack remain text.

**Shared dialogue file** is editable with Browse and Detach. Existing JSON is previewed and loaded without overwriting it; a new path creates a file only after confirmation. Old drafts save before switching. Cancel, invalid JSON or failed saves retain the previous binding. Detach keeps embedded text. Later edits to a shared file still affect its other users.

Pickers start from the current value or nearest existing parent. Relative model/reference paths use the GPT-SoVITS project; empty values use related resource/data directories.

Target/reference languages are editable dropdowns: Chinese, English, Japanese, Korean, Cantonese, and common automatic/all-language codes. Custom codes are saved unchanged; actual support depends on the API/model. Offline script checks separately inspect generated text and reference transcript before generation. Possible mismatches and uncertain short/mixed text allow returning or proceeding. This does not identify model training language or guarantee compatibility; cross-language synthesis is allowed. No API starts before confirmation.

For a shorter first-use walkthrough, see [Getting started](USAGE.en.md).

## Interface language

Open **Settings → Runtime settings → Interface language**, choose **English** or **简体中文**, then click **Save runtime settings** or leave the page to autosave. The change applies at the next start. Use **Exit** in the tray and reopen; closing the window only hides it.

The save notification offers **Undo**. Restoring defaults selects Chinese for next start. Old configurations and invalid language values default to Chinese without losing other settings. Language changes do not interrupt playback or generation.

Language does not translate your profile / rule names, dialogues, categories, paths, filenames or models. It does not change speech language or import translated dialogue. Existing Chinese recordings remain usable. Plugin text, raw external service errors and historical logs retain their original language.

Both help buttons select documents matching the active UI language. This reader uses an opaque, text-only page without promotional images or remote badges. Development links are marked when their documents remain Chinese.

## Navigation and appearance

The sidebar opens **Companion home**, **Wallpaper library**, **Audio library**, **Dialogue library**, **Generate voice**, **Settings** and **Activity log**. Home has **Sound settings**, **Interaction rules** and **Resources and bindings**. Editing selectors stay synchronized, but editing a profile does not necessarily activate it; check the editing / playing status.

**Import background…** processes an image locally and saves a copy in app data. Originals are never moved. Under **Appearance and background**, automatic color extraction or fixed cherry pink is available. Restoring default appearance keeps imported copies.

The bottom player controls the active profile. Turning off **Enable background music** hides it. Cover artwork uses track metadata or nearby cover.jpg/png / folder.jpg/png; otherwise a default icon appears. BGM pause leaves interactive voice available. **Pause companion** pauses companion sound and triggers together.

## Installation and first setup

The app runs independently without changing WE or downloaded wallpapers. Neither the installer nor ZIP requires Python. Extract the entire ZIP; keep **_internal** and **portable.flag**. Portable data uses the adjacent **data** folder. Installed configuration uses `%LOCALAPPDATA%\WallpaperCompanion`; uninstalling preserves it. New shared resources default to application/**shared**; old paths are kept. Exit from the tray and back up personal data before updating.

1. Play a wallpaper in WE and check **Current wallpaper**. Correct the installation path / monitor in settings if needed.
2. Click **Bind current wallpaper**, or scan and batch bind. For testing without detection, create **New profile** and enable manual use.
3. Choose voice / BGM folders in **Resources and bindings**. New profiles can use bundled voices while their own voice directory has no audio.
4. Click **Preview random voice**. There are 180 bundled Chinese/Japanese clips: 90 per language, each with 38 companion and 52 operation responses.
5. Add rules or apply category rules from the dialogue library, then return to the desktop to try F8 / middle-click.

Text and audio are separate. Downloaded recordings play directly from folders; text needs synthesis or recording first.

## Top bar, profiles and tray

| Control | Purpose |
|---|---|
| Current wallpaper | Followed monitor and detection source. Saved selection can lag behind WE. |
| Detect now | Tries the official query once, then saved selection. Automatic polling only reads saved settings without launching a query GUI. |
| Hover help | Saves immediately; hover about one second. Leaving, clicking or typing hides the tooltip. |
| Open user guide | This detailed guide inside the app, without Markdown file associations. |
| Pause / Resume companion | This app's voice and BGM only. Independently paused BGM stays paused. |
| Profile list | Choose a profile to edit; Ctrl / Shift supports multiple profiles for deletion. |
| Bind current wallpaper | Creates a binding or opens its existing profile. |
| Profile management | New, delete, scan / batch bind, import and export. |
| New profile | Unbound profile for manual testing or later binding. |
| Delete selected profiles | Confirmation required; wallpapers, audio and dialogue files stay. |
| Use selected profile manually | Plays the selected profile instead of following WE. |
| Tray double-click / Exit | Show the window or end the app. Closing the window normally stays in the tray. Exiting during generation asks to cancel; saved audio stays and owned APIs are released. |

### Automatic saving and undo

Profile, rule, dialogue, API and runtime edits save when changing pages / profiles, hiding to the tray or exiting normally. A notification lasts about 6.5 seconds with **Undo**; settings also has **Undo last automatic save**. Manual Save remains available. Temporary ordinary generation text is not persistent configuration.

Undo covers only the latest automatic save / default reset. It refuses to overwrite new edits, later saves or externally changed files. Shared dialogues and referencing profiles restore together. API keys in the system credential manager are excluded. Failure keeps edits and blocks navigation until corrected. Ordinary autosave does not restart the song or reset unchanged rule timers.

Immediate volume, startup toggles, manual saves and file deletion are outside this undo. Recover deleted audio from the system Recycle Bin.

## Operation voice responses

On by default, these play prepared responses to saves, edits, navigation and other actions. They never start a speech API. Rapid actions are throttled; typing changes are grouped. They do not interrupt character / reference speech or queue during pause / fullscreen muting. Missing categories stay silent.

| Control | Purpose |
|---|---|
| Play operation voice responses | Saves immediately; disabling stops current operation speech, not unrelated previews. |
| Operation voice directory | Optional root with operation-category subdirectories. Empty searches edited-profile voice, shared voice roots, then bundled operation voices. |
| Refresh operation voices | Background rediscovery; also refreshes after generation, profile changes and later actions. |
| Import default operation dialogues | Adds missing text: 52 original lines. Does not select all or call an API. |
| Operation voice rules… | Separate action enablement, category, cooldown and global interval. JSON import / export never changes wallpaper rules. |
| Restore default rules | Restores operation defaults inside that dialog. |
| Restore default settings… | Confirms resetting runtime preferences, language, appearance, operation settings and active editing profile playback / rules. Keeps bindings, paths, dialogues, audio, characters and API settings. Does not change startup. Can be undone. |

Chinese default categories are resource folder names, so remain Chinese in English UI. All 180 Chinese/Japanese default recordings are bundled. New profiles enable demo fallback; legacy profiles missing that field default to off. Personal audio takes priority. Ordinary root-random rules exclude operation categories unless explicitly targeted.

## Sound and resource fields

Edits save on leaving the page or using **Save profile**, unless noted.

| Field | Meaning |
|---|---|
| Profile name | Your label; does not rename wallpaper files. |
| Bound wallpaper | Read-only entry path; use rebind to change. |
| Voice / BGM folders | Audio roots including subdirectories. Empty BGM means no companion music. |
| Enable this profile | Automatic voice and BGM master switch for the profile. |
| Enable background music | Music only; disables and hides its player. |
| Desktop-only response | Default on, avoids responses while typing / gaming. Editing the app is not a wallpaper input trigger. |
| Fullscreen pause | Pauses this app, never WE. |
| Shuffle | Off uses filename order. |
| Voice volume | 0–100%, companion voice only. |
| BGM volume | 0–100%, companion music only. Active-profile edits save immediately; other profiles save normally. |
| BGM during speech | Percentage of normal volume retained. BGM 40% with 25% retained becomes about 10% while speaking. |
| Global voice cooldown | Minimum seconds between successful automatic responses, alongside rule cooldowns. |
| Resource root | Defaults to application/shared for new shared resources; uses voice, bgm and dialogues.json. Existing paths stay. |
| Shared / dedicated resources | Choose shared, dedicated or keep-current independently per channel. Dedicated defaults to data/audio/profile-ID. |
| Shared dialogue file | Linked JSON; saves affect every profile using it. Empty means embedded profile text. |
| Conflict policy / override | Decide BGM blocking from original-sound evidence, or manually confirm silent / audible. |
| Wallpaper sound status | Evidence for the playing profile, which may differ from the edited one. |

### Resource and playback buttons

- **Bind this profile to current wallpaper:** associates the edited profile; warns about an existing binding.
- **Bind voice, BGM and dialogues to this root:** creates directories and links JSON, reading existing JSON rather than overwriting it with defaults.
- **Recheck wallpaper sound:** background track / asset inspection without playback.
- **Create dedicated audio directories:** starts with dedicated modes. Saving shows actual profile / paths for a second confirmation. Cancelling creates nothing. Old audio is not moved, copied or deleted.
- **Shared / dedicated directories…:** independent channel choices; **Open voice / BGM folder** opens Explorer.
- **Preview random voice:** ignores trigger time / cooldown for testing the edited voice root.
- **Pause / Resume current BGM:** active-profile music only, saved per profile.
- **Next BGM:** uses shuffle / ordering without forcing playback through pause or conflict protection.
- **Stop preview:** stops current voice; BGM state is unchanged.

Audio rescans on later selections. WAV / MP3 / OGG / FLAC / M4A support depends on the player backend. Damaged music is logged and skipped.

## Audio library

Shared and wallpaper directories are deduplicated by actual path. Browsing / searching / previewing never starts GPT-SoVITS.

| Control | Purpose |
|---|---|
| Search scope | All, shared voice / BGM, a wallpaper, or read-only bundled voices. Opening / refreshing scans in the background. |
| Search | Filename, path or owning profile. Filtering clears selection to avoid hidden-file operations. |
| File list | Ctrl / Shift and row selection; double-click preview. Profile count means directory references, not exact rule analysis. |
| Cell hover | Full filename, usage / directory, exact bytes or full path. Column headers explain column functions. |
| Preview selected / Stop preview | First selected file, without synthesis. |
| Open file location | Selected file's directory; without selection, the first visible file's directory. Empty lists show a message. |
| Select all listed / Deselect all | All visible files or clear selection. |
| Import / copy destination | Shared or configured wallpaper directory. Establish dedicated resources first if a separate copy is needed. |
| Category subdirectory | Optional relative name, never absolute or parent paths. |
| Import audio files… | Copy originals, automatically number duplicate names. |
| Copy selected | Copies every selected file, never moves originals. Direct sharing needs no copy. |
| Use destination for wallpaper voice / BGM | Binds destination/category and saves the profile draft; no copying or dialogue-file change. |
| Delete | Confirm, then move selected audio to the system Recycle Bin. Shared users may be affected. Bindings stay; failures never become permanent deletion. |
| Shared root | application/shared by default. Empty restores default. Affects new / later explicitly shared choices, never existing paths. |
| Shared voice / BGM scopes | Include current roots and legacy data/audio/shared when present; tooltip lists actual paths. Nothing is moved. |
| Bundled default voices | Preview / copy 180 clips; cannot delete, overwrite or import into their directory. |

Wait for generation / scanning / copying before file management. Renaming may affect dialogue matching, filters and duplicate skipping; review rules afterward.

## Wallpaper sound and conflict protection

| Policy / result | Meaning |
|---|---|
| Pause if sound detected or unknown | Default, pauses companion BGM only; interactive voice remains available. |
| Pause only with sound evidence | Detected / possible sound blocks; unknown allows BGM. |
| Allow companion BGM | Detection never blocks music. |
| Video has audio | ffprobe found a stream: music, dialogue or even silence. |
| Video has no audio | ffprobe successfully confirmed no stream. |
| Scene / web assets found | Possible sound; actual enablement / audibility unknown. |
| Unknown | Missing ffprobe, unrecognized packages, shared assets or scripts can prevent confirmation. |
| Override | After checking / muting WE yourself, confirm silent or audible. |

This is not live listening or complete inspection of WE volume / mute settings. A track or unused asset may be silent. Scene packages are indexed read-only. Recheck repeats evidence detection; it cannot guarantee music recognition.

## Interaction rules

Choose **Time-based** or **Event-based**, the relevant trigger, then audio. Irrelevant fields hide; cooldown / filters are under **More settings**.

| Field | Meaning |
|---|---|
| Rule name / enable | Recognizable name and participation; no file rename. |
| Time mode | Daily scheduled time or random playback in a window. |
| Daily time | Local HH:mm. Once per day when the app reaches that minute and conditions permit. Missed times are not replayed; restarting within that minute may trigger again. |
| Event type / mouse action | Mouse, keyboard or wallpaper / extension; mouse buttons / wheel need no keyboard shortcut. |
| Keyboard mode | Recorded key / combination or any key. |
| Key binding | Read-only. Record then press e.g. Ctrl + Alt + H. Esc / Cancel keeps the previous binding. Duplicate enabled shortcuts are rejected. |
| Audio to play | Root random, category / subdirectory, or custom file / folder. |
| Category | Dialogue categories and immediate voice subdirectories populate choices. Legacy missing categories remain. Real audio is required. |
| Audio source | Browse a folder or choose one file. |
| Filename contains | Name filter only; empty means no filtering, never speech synthesis. |
| Playback / active window | Local time. Equal start/end means all day; 22:00–06:00 crosses midnight. End is excluded. Event limits are optional in More settings. |
| Cooldown | Minimum seconds after this rule plays, also limited by global cooldown. |
| Random interval | Minimum / maximum delay, at least 5 seconds. Enabling does not play immediately. |

Busy voice does not overlap or build a queue. Simultaneous rules use list order. Preview tests candidates without trigger time / cooldown, not trigger correctness. **Bound wallpaper starts playing** means entering its profile, not every desktop return or internal WE pause.

### Import and share presets

Import previews pure JSON names / counts. Export selected profiles includes rules, dialogues and playback settings, not audio, keys, plugins or absolute machine paths.

Create unbound new profiles, or apply a single-profile file to the current profile. Applying replaces rules / dialogues / playback but keeps local wallpaper and audio paths, removing the shared dialogue link to protect other profiles. New profiles need local binding and audio.

Relative categories / filenames travel with presets. External sources need review on the receiving machine. Missing event extensions disable those rules. Import never changes startup, switches APIs or loads plugins. Example: examples/interaction-preset.json.

## Wallpaper library and batch binding

| Control | Purpose |
|---|---|
| Search | Title, workshop ID or path; hidden checkmarks remain. |
| Scan | Read-only workshop, local creations and extra paths; no bindings created. |
| Checkboxes | Batch scope, separate from sidebar profile selection. |
| Select / Deselect visible | Visible rows only; clear search to inspect hidden selections. |
| Open selected profile | Existing binding; bind unbound entries first. |
| Delete checked bindings | Confirm, then profiles only; all resources stay. |
| Additional paths | One real directory per line. Add then save; saving rescans and protects those roots against app output. |

Batch modes share voice/BGM only, share full resources (voice, bgm, dialogues.json), or create dedicated structures under Companion data. Shared voice must exist; BGM is optional. A template copies volume / dialogues / rules to new independent IDs. Updating existing directories is off by default; enabling updates paths, keeping names, rules and files.

Only valid project.json entries are found; packed scenes need no unpacking. Invalid projects are reported / skipped. Repeated scans do not duplicate bindings for the same entry.

## Dialogue library

Without a selected profile, this edits shared text; fresh installs show 38 companion lines without requiring a binding. Saving writes shared-root/dialogues.json. Selecting a profile edits its library instead.

**Add missing default dialogues** adds missing originals, preserving custom text. Shared mode also supports add / import / export / category generation. Unsaved shared drafts save before first binding or changing roots; failure blocks switching. Broken JSON is reported and kept, never silently overwritten.

| Control | Purpose |
|---|---|
| Generate checkboxes | Temporary selection, initially empty; does not edit or delete dialogue data. |
| Drag / Ctrl / Shift selection | Two-way synchronization with generation checkmarks, including scrolling while dragging. Checkbox clicks toggle that row only. |
| Select / Deselect all | All lines or clear generation selection. |
| Category selector | Select only that category, with individual adjustments afterward. |
| New / Edit / double-click | Category and text. Categories must be safe subdirectory names. |
| Delete | Text rows only after save; recordings stay. |
| Save dialogue library | Shared JSON edits affect all profiles referencing it. |
| Skip existing matching audio | Avoid repeated category synthesis. Both generation paths review duplicates first. |
| Send checked lines to generation | Preserves categories / skip setting; editing transferred text switches to ordinary line mode rather than guessing categories. |
| Apply category trigger rules | Confirms replacing draft rules with F8 / middle-click, wallpaper greeting and morning / daytime / night rules. Save to apply. |
| Import JSON / TXT | JSON retains categories; UTF-8 TXT is one line per row in the default click category. Deduplicates; save afterward. |
| Export JSON | Complete library for backup / reimport. |

English and Japanese packs each have 38 companion and 52 operation lines. Some categories stay Chinese for compatibility; language-specific operation rules are included. The JSON packs are text; Japanese default recordings are also bundled with the app. English recordings are not bundled. See examples/dialogues/TRANSLATIONS.md. The separate heartfelt-zh-CN.json contains 72 Chinese Gentle Replies, also requiring synthesis / recording.

Editing text does not rename or regenerate old audio. Duplicate outputs receive numbers rather than replacing originals.

## Generate voice: shared controls

Brief button feedback only acknowledges the click. Read final status / errors for success. Button animation does not change hit regions; file pickers use the app dialog so the current directory and interface language are consistent.

Progress counts clips actually saved or skipped. Stages show API checks, owned-service setup, model loading, synthesis, WAV validation and writing. Internal model percentages are not invented. Failure preserves partial audio and completed counts.

Both generation paths check existing audio / batch duplicates before calling a provider. Choose skip, generate new copies, or cancel. Filenames include a model tag: dialogue-character.wav. Checks include legacy untagged clips; other models are stored separately.

| Control | Purpose |
|---|---|
| Provider | Settings saved separately per service. |
| Output directory | Ordinary WAV destination, not automatic binding. |
| Filename model tag | Filename only; does not change models. Empty infers character / weights / service model or voice. Unknown keeps the existing unspecified-model tag. |
| Dialogue input | One line per row; text alone makes no API request. |
| Save API settings | Parameters save; passwords go to system credentials. Starts nothing. |
| Check connection | Local readiness only, never starts the API. Cloud format checking does not prove authentication / quota. |
| Start local API / Stop owned API | Processes started by this app only; stopping is unavailable during loading / generation. External services stay untouched. |
| Use current profile's voice directory | Output becomes the edited profile's voice root. |
| Play reference / Stop reference preview | Plays the selected reference, resolving project-relative paths. Starts no API. |
| Generate and save audio | Current settings snapshot; starts a local API as needed. |
| Open output directory | Opens Explorer. |

### Local GPT-SoVITS fields

| Field | What to enter |
|---|---|
| API URL | Local HTTP address, usually http://127.0.0.1:9880; the number is the port. |
| Project directory | Root containing api_v2.py, not the output folder. |
| Python executable | Optional project interpreter; empty tries runtime/python.exe. |
| GPT model (.ckpt) | Matching weights; scan, browse or use project-relative paths. Both model fields empty keep current API models. |
| SoVITS model (.pth) | Matching acoustic weights. Scanning does not load contents. |
| Reference audio | Recording appropriate for the character / model. |
| Reference transcript | Exact words in that recording, not the dialogue to generate. |
| Target language | Text language code supported by your model, e.g. zh, en, ja. |
| Reference language | Recording / transcript language code. |
| Speed | 0.5–2.0; 1.0 normal. |
| Allow external model switching | Default off. Changes global external model state and affects other clients. Otherwise choose a free port for an owned API. |

### Characters and model scanning

1. Set the project path or click **Scan local models**. Read-only scan excludes runtime, base pretrained models and tools, without importing PyTorch or loading weights.
2. Choose a suggested pair or individual GPT / SoVITS files. Suggestions use name / directory / version hints, not verified compatibility. Ambiguous pairs are not guessed.
3. Select reference audio, click **Use reference audio**, then fill its exact transcript / languages. **Read matching transcript** reads same-name .lab / .txt only; still check every word.
4. **Save character** stores name, models, reference, transcript, languages, speed, project and optional Python; **Save as…** creates another preset. URL / external-switch permission remain general API settings.
5. Selecting restores fields without loading. Saving API settings does not overwrite a preset; use Save character. Unsaved character edits prompt before switching.
6. Generation starts / loads as needed; manual Start also loads models. Repeated work reuses owned API. Changed weights restart the owned service for the new model. Scanning, selecting and saving never start it.

Owned services use a private config under data/tts-runtime, never edit the original tts_infer.yaml, and clean the copy on stop. Exit releases the owned process tree. Allowed external switching is global; avoid other clients switching models concurrently.

Deleting a character removes only its preset, keeping models / reference / transcript files. Presets live under config.json's tts_characters, contain no API keys and are excluded from shared interaction exports. Offline files do not block app startup but fail generation validation.

The app still uses api_v2. You need not run api_v2.bat for owned startup: generation checks readiness, launches configured Python / api_v2.py if necessary, waits for models, sends text / reference parameters to /tts, receives WAV and saves it. See sovits-api.log. If every line is skipped, no API starts. Exiting cancels remaining work and keeps completed clips. Externally started services are not stopped.

### Azure Speech

| Field | Meaning |
|---|---|
| Full synthesis endpoint | Your resource URL, e.g. https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1. |
| API key | Resource key stored in Windows Credential Manager. |
| Key environment variable | Variable name, e.g. AZURE_SPEECH_KEY, not its value. Direct key takes priority. |
| Voice ID | Supported voice, e.g. zh-CN-XiaoxiaoNeural; not a file. |
| Locale | Matches the voice, e.g. zh-CN. |
| Speed | 0.5–2.0; 1.0 normal. |

### OpenAI-compatible TTS

Use the complete provider /audio/speech endpoint, not its homepage. Fill the required key / environment-variable name, supported model ID and voice ID. Local unauthenticated compatible services may leave keys empty. Speed is 0.5–2.0, subject to provider limits.

Services must return WAV. Other JSON / MP3 protocols need an extension. Remote URLs require HTTPS. Cloud synthesis sends text to your selected provider and may cost money. Extensions can define additional fields.

## Runtime settings

| Control | Purpose |
|---|---|
| Interface language | Chinese or English for next start. |
| Backend selectors | Loaded detection / playback / input / library / audio-detection backends. Save and restart. |
| WE installation path | Contains wallpaper32.exe / wallpaper64.exe; read-only queries. |
| Workshop directory | Usually Steam library/workshop/content/431960; read-only scanning / write protection. |
| Monitor | Numbered from 0, one at a time. |
| Polling interval | 2–60 seconds, saved selection only; WE save delays affect following. |
| Start at sign-in | Current Windows user, off by default; fix application location before enabling. Starts in tray without a speech API. |
| ffprobe | Optional executable; empty searches PATH. Missing tool means unknown tracks, not total app failure. Save after changing. |
| Local plugins | Place trusted .py in plugins, restart to list, enable / save / restart to load. Plugins have app file / network permissions. |
| Open plugins / data directory | Opens plugin files or app data / logs; shared audio may be elsewhere. |
| Open documentation | Getting started in the active UI language. Top Open user guide is this detailed manual. |

## Activity log and troubleshooting

Logs show activation, triggers, tracks, generation, scans and errors, never typed input. Recent UI records are limited; startup / API logs are separate files.

| Symptom | Check first |
|---|---|
| Mouse / hotkey silent | Saved active profile, desktop foreground, pause, time, cooldown and actual matching audio. |
| BGM silent | Enable toggle, manual / conflict pause, folder and volume. |
| Generated clip does not trigger | Output versus bound root, categories / keywords and saved WAV. |
| Unwanted shared dialogue | Choose a different root or dedicated resources. Old shared files stay. |
| Following delayed | Saved-selection lag; try Detect now or manual mode. |
| Cloud check passes but synthesis fails | Format validation is not authentication. Check endpoint, key, model, voice, quota and WAV response. |
| Audio remains after deleting a profile | Intentional resource protection for shared / future bindings. |
| Hover text missing | Enable hover help, hold about one second, avoid typing / dragging. |
| API connection refused | Start local API and wait, or generate for automatic startup. Verify address, port, project and Python. |

[Getting started](USAGE.en.md)

[GitHub project](https://github.com/Abs0lutely/wallpaper-companion)

[Build instructions (Chinese)](BUILDING.md)

[Extension API (Chinese)](EXTENSIONS.md)
