# Local Voice Studio for Eufy L60

Import a voice pack you acquired yourself, map its sounds to Eufy events, build the voice ZIP and explicitly install it over your local network. **No voices or stock packages are bundled.** This is an experimental desktop tool, not an official Eufy product or a universal installer.

## Download and start on Windows

Download `LocalVoiceStudio-Windows-x64.zip` from Releases, extract it, and open `LocalVoiceStudio.exe`. Python is included in the executable; you do not need to install Python.

Audio conversion, preview and pre-install validation require FFmpeg. If it is not installed, run the included `Setup-Audio.cmd` and review the Windows Package Manager prompts, then reopen the app. Alternatively install FFmpeg yourself and put `ffmpeg`, `ffprobe` and `ffplay` on PATH or in a `tools` folder beside the executable. These audio tools are not bundled or downloaded automatically. The executable is unsigned.

## What you need first

- Your vacuum must be an L60 on the same LAN, idle and powered. Its identity is owner-confirmed: the app does not independently verify model or firmware compatibility.
- Your own legitimate original English stock voice ZIP, kept unchanged as a private backup. Only the reviewed male/female layouts with 86 numbered clips are supported. No stock-download catalogue is included.
- Your vacuum's device ID, 16-byte Tuya local key and LAN address. These are advanced setup prerequisites. An existing local integration may have them; this app does not retrieve keys from a Eufy login. An address alone is not sufficient. If you do not already have the stock package and connection details, this preview does not complete that acquisition step.
- Access to official voice selection in the Eufy app for stock restoration after a successful update. Recovery after a failed or interrupted update remains unproven.

The initial method worked in a limited research setup. The new desktop application has been tested with synthetic archives, protocol messages, simulated device behavior and a local test server. **It has not itself been validated on physical hardware. Other model or firmware combinations are unverified.** Do not treat a matching archive layout or read-only connection check as proof of compatibility.

## Use your pack

1. Open your original stock ZIP in **Import and map**.
2. Import your acquired ZIP/TAR.GZ pack, or add individual recordings, including OGG. Archive scripts are ignored and never executed.
3. Listen to the stock event and available recordings. Select one on each side and choose **Use for event**. Unmapped events keep their original stock audio. Numeric filenames from another vacuum brand do not establish a mapping.
4. Optionally supply your own phrase CSV with exactly the headers `filename,phrase`. This adds searchable text; no pack-specific mapping is bundled. Verify safety and error announcements carefully.
5. Choose **Build ZIP** and a new output filename. Replacements become mono 16 kHz, 16 kbps MP3 with loudness normalization. The original folder, clip names, package ID and version are preserved. No version increase is performed.
6. Under **Review and install**, enter your own private connection details. Optionally import your private JSON with string fields `address`, `device_id`, `local_key`. The app never saves these details. Do not post that file publicly.
7. Use **Check connection** for a bounded read-only voice status query. Review the selected candidate, confirm the idle-device checklist, then approve the separate installation dialog.

An already-built compatible Eufy ZIP can be selected instead of building one, but still requires the original stock ZIP for comparison and full audio validation.

## Installation behavior and recovery

Before writing, the app snapshots both archives, checks their layout/configuration and decodes every candidate MP3. It performs a read-only voice-status query, serves only the selected archive to the specified target, sends one local voice-update request and observes for up to three minutes. It does not change firewall/router settings or attempt firmware modification. Incoming file transfer may be blocked by your existing network/firewall configuration; no automatic rule is added.

There is no automatic write retry. A complete download plus a matching success response is reported as an observation; listen for the changed voice and check normal operation yourself. Success without a full observed transfer is inconclusive. Failure, missing responses or a timeout must not be followed by blind retries.

After a successful settled update, select an official stock voice in the Eufy app to restore it. The app also accepts your saved original ZIP as a candidate, but that is not a proven emergency recovery procedure. After a failed or unresolved update, keep power stable, resolve status through the official app and consult device support before further changes. No universal rollback guarantee is made.

## Source and checks

For source users: install Python with Tk, run `python -m pip install -r requirements.txt`, then `python app.py`. Install FFmpeg separately as above. The older `builder.py` entry point remains available as a minimal offline builder.

Run `python -m unittest -v`. Tests use synthetic inputs and loopback networking only; no device credentials or physical vacuum are required. `python app.py --self-test` checks hidden GUI startup. A Windows build uses `build_windows.cmd` from this directory after installing `build-requirements.txt` in a fresh virtual environment. Packaging approach: [PyInstaller documentation](https://pyinstaller.org/en/stable/usage.html).

## Privacy and attribution

No telemetry, account authentication or diagnostic upload. Credentials remain in process memory and are never included in releases. The local key is removed from the form when an install attempt starts. Operating-system memory, crash dumps and external audio-tool process arguments are outside a secure-erasure guarantee. Keep your inputs and outputs private. Report a stage and generic error category, without account data, connection files, packages or raw logs.

See PRIVACY.md, METHOD.md and THIRD_PARTY.md. No personal research workspace, voice audio, owner-specific device identifiers or owner software-build details are included. The GitHub publishing account remains publicly visible.
