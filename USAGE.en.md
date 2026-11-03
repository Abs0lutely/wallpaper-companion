# Wallpaper Companion: Getting started

## Automatic updates (v0.12.0+)

In Runtime settings, **Enable automatic updates** is on by default. The app checks stable releases shortly after startup, then daily, and downloads the package matching your installed or portable edition. Turning it off cancels background checks and downloads. **Check for updates** remains available manually. The preference supports autosave and undo.

The update window shows the version, release notes and download progress. After size and SHA256 verification, select **Update now** and confirm: the app saves your edits, exits normally, updates and restarts. **Later** lets you keep working. Finish speech generation or local API operations first. A failed save prevents exit; other instances are never force-closed.

Installed editions retain their installation directory. Portable editions replace program files only, keep a program backup and roll back failed replacements. Settings, bindings, dialogues, audio, shared folders, companion packs and personal plugins are preserved. Installer failures retain the package and logs for retry. Source checkouts show the release page without replacing source files. GitHub connectivity is required; no GitHub token is needed. Automatic updates do not bypass Windows security prompts.

**v0.11.0 and earlier do not have an updater: install v0.12.0 manually first**, using setup.exe or the documented portable program-only update process. Later releases can be installed from within the app.


## Multilingual voices and standalone use

Choose **Mode → Standalone sound companion** on home or in Settings. No WE is needed for sound profiles, input / timed voice and BGM. Existing WE bindings and its profile choice are kept.

There are 180 bundled clips: 90 Chinese and 90 Japanese. Select bundled sample language in Sound settings; operation language is selected through **Operation voice rules → Switch categories**, then Save. Use **Send checked lines to generation** to preserve categories. See the [full guide](USER_GUIDE.en.md) for legacy migration, language warnings and safely switching shared JSON.


## Hear your first response

1. Play a wallpaper in Wallpaper Engine, then open Wallpaper Companion.
2. Click **Bind current wallpaper**. If detection is unavailable, create a **New profile** and enable **Use selected profile manually** instead.
3. New profiles can use the bundled demo when their voice directory has no audio. Click **Preview random voice**. The app includes **180 Chinese/Japanese recordings**: 90 per language, each with 38 companion lines and 52 operation responses. No AI server is needed to try them.
4. In **Dialogue library**, click **Apply category trigger rules**. Confirming replaces the rules being edited. Leave the page to autosave, or click **Save profile**.
5. Return to the desktop and try **F8** or the **middle mouse button**. Desktop-only input, cooldowns and existing playback can prevent a response.

Existing profiles are not forced to enable demo voices. If silent, check **Use bundled demo when voice directory is empty**, profile enablement, volume and pause status.

## Find your way around

- **Companion home:** voice and music settings, interaction rules, resource directories and wallpaper binding.
- **Wallpaper library:** read-only discovery and batch bindings. Deleting a binding keeps wallpapers, audio and dialogues.
- **Audio library:** find, preview, import, copy and delete shared or per-wallpaper audio. Confirmed deletions go to the system Recycle Bin.
- **Dialogue library:** edit, import and select text. Text needs recordings or synthesis before it can play.
- **Generate voice:** configure local GPT-SoVITS or another provider, then create WAV files.
- **Settings:** language, background, operation voices, startup, paths and extensions.
- **Activity log:** scan, trigger, playback and generation results.

## Music and resource directories

New shared resources default to **shared** in the application directory, containing **voice**, **bgm** and **dialogues.json**. Existing paths are never automatically moved. Each wallpaper can mix shared voice with dedicated BGM or other directory choices.

Choose a BGM folder in **Resources and bindings** and enable background music. Use the bottom player to pause, skip or adjust volume. Disabling BGM for that profile hides the player. Music can lower automatically during speech.

Original-wallpaper audio detection only finds tracks or asset evidence. It cannot guarantee that music is actually audible. If companion BGM is blocked for a silent wallpaper, check it yourself and choose **I confirm the wallpaper is silent / muted** when appropriate.

## Saving, undo and language

Leaving a page automatically saves profile, dialogue, rule and API-setting edits. A successful save notification offers **Undo** for a short time. Manual Save buttons remain available. File deletion, system startup, manual saves and immediate volume changes are outside automatic-save undo.

Select **Settings → Runtime settings → Interface language → English**, then save. The change applies at the next start. Use **Exit** in the tray and reopen; closing the window only hides it. Chinese UI opens Chinese documents; English UI opens separate English documents.

## Generate more voices

Local GPT-SoVITS requires your own project, models and reference recording. Scanning or selecting a character does not start the API. Generating starts an owned API as needed and waits for models; you may also start or stop it manually. Exiting releases services owned by Companion, never services started by other software.

The reference transcript must match the recording word for word. Output uses **dialogue-model.wav** names. Existing matches are checked first; choose to skip, generate new copies or cancel. Originals are not overwritten.

The English / Japanese dialogue packs and the 72-line **Gentle Replies** pack are extra text, not additional recordings. Generate or record them yourself. Interface language does not change speech language.

Cloud providers receive synthesis text and may charge your account. Keys are stored in the system credential manager and should not be shared.

## Installation, exit and data

Neither installer nor portable ZIP needs Python. Extract the entire ZIP and keep **_internal** and **portable.flag**; do not move only the EXE.

Installed configuration uses your local user-data directory; portable configuration uses the adjacent **data** directory. Shared audio defaults to **shared** in the application directory. Uninstalling the installed edition preserves user data; backing up before updating is still recommended.

This free, open-source app runs independently and plays prepared audio by rules. It does not provide free-form conversation, modify Wallpaper Engine or alter downloaded wallpapers. No wallpaper patches are needed.

[Full user guide](USER_GUIDE.en.md)

[GitHub project](https://github.com/Abs0lutely/wallpaper-companion)

[Download releases](https://github.com/Abs0lutely/wallpaper-companion/releases/latest)


## Companion packs

Use **Choose a companion pack** in the home banner to preview and apply included Chinese/Japanese recordings without WE or AI. Export a profile from Profile management. Global operation responses remain opt-in. See [Using and sharing companion packs](COMPANION_PACKS.en.md).
