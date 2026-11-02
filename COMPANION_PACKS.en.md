# Using and sharing companion packs

[简体中文](COMPANION_PACKS.md)

## First experience

1. Click **Choose a companion pack** in the home banner. No Wallpaper Engine, model or API is required.
2. Select Chinese or Japanese **Gentle Days**, then **Preview**. A separate player previews the recording without changing the active profile or starting AI. Cards show companion recordings, optional app responses and availability.
3. Use **View interactions** to review F8, middle-click responses, time-window greetings, quiet company and a daily 22:30 good-night rule. Input defaults to the desktop foreground; keys pressed inside other applications may not trigger. Advanced settings can change that scope.
4. Select **Use this pack** and confirm. A new standalone sound profile is created, preserving existing profiles, shared resources and WE links. Partial/text-only packs say **Needs recordings**; missing rules remain, without silently starting AI or falling back to another character.
5. Global pause remains paused. Use **Start companionship** explicitly. **Return to previous setup** restores only the preceding mode and active selection, retaining the new profile/files and subsequent unrelated changes. The shortcut is available within the current app session.

Each included language has 38 companion recordings and 52 optional operation responses: 180 previously approved recordings in total. Neither contains BGM or models. Original recordings have mixed or missing character labels; cards therefore do not claim a verified single character. Voice language is independent of interface language.

**Also use the pack’s operation responses (affects the entire app)** is off by default. Only explicit confirmation changes global operation response settings; interaction rules always belong to the new profile. Pack responses use their own source without fallback to another character. Restoring defaults restores the normal default rules and included-source lookup.

After using a pack, **Link to current wallpaper** performs a read-only WE query and asks for confirmation. It refuses to overwrite another profile’s existing link. Without a detected wallpaper the standalone profile remains available. Existing wallpaper management remains available in WE mode.

## Offline import

Select **Import file…** and choose `.wcpak`. Current drafts are saved first. A dedicated `pack-temp/` directory under the user data directory holds temporary validation of paths, inventory, hashes and recordings. Installation into `packs/<random-install-ID>/` happens only after confirming use. Closing an unused preview removes its own temporary files.

Identical content reuses installed resources while creating a fresh profile. Same-name packs with different content get separate directories. Failed saves, invalid packages and failed installs retain existing profiles. The old JSON preset import remains unchanged.

## Share a profile

Choose **Profile management → Export companion pack…** to export the currently edited profile, one at a time.

- Enter name, voice character, voice language code, author and description. These are the sharer’s descriptions, not verified model or voice identities.
- BGM and operation responses are off by default; opt in separately.
- Click **Preview resources**. Columns show internal filename, local source and size; hover for full paths. Local source paths are for review only, never written into the package.
- Existing rule matching determines default recordings. Whole-folder random rules may collect every matching recording. Deselect anything you do not want to distribute, or use select all/none.
- The report lists missing/excluded sources and dialogue lines without recordings. Rules are never silently removed; recipients see partial availability accurately.
- Confirm distribution rights and **Export** a `.wcpak`. Then **Open containing folder**. Editing metadata/options requires a fresh preview.

Export copies selected material and rewrites paths only in the exported copy. Original profiles, recordings and shared dialogue files are untouched. APIs, credentials, models, reference recordings, plugins, startup entries and wallpapers are excluded. SHA256 checks integrity; it is not an author signature or rights certificate.

## Initial limits

No online store, accounts, auto-updates, model distribution or free-form chat. Closing to the tray does not exit. Preparing an included pack involves validation/copying with busy indication; allow space for temporary and installed resources.

WAV receives container/frame-length checks. Other supported compressed formats receive header checks, with actual decoding delegated to Qt; this is not an exhaustive decode audit. Playback errors appear during preview. Device-specific codecs, actual WE identification and frozen distributions need environment-specific testing.

See the [format specification](examples/packs/FORMAT.md). This work is local source development; installed binaries require a later explicitly authorized release.
