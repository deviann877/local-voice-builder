# Local Voice Builder

Experimental offline source release for building replacement Eufy-style voice archives.
No voice packs, recordings, stock archives or device credentials are included.

## Run

Install Python with Tk support and FFmpeg separately. Both `ffmpeg` and `ffprobe` must be on PATH.
Run `python builder.py`, or double-click `Start-Builder.cmd` on Windows with the Python launcher installed.
No Python packages are required. Run checks with `python -m unittest -v`.

1. Obtain your own compatible stock voice ZIP legitimately and keep an untouched private backup.
2. Open the ZIP. This preview supports one voice folder containing `config.yaml` and `main/A####.mp3` files.
3. Select a clip and choose your replacement recording. OGG, WAV and other FFmpeg-supported audio can be converted.
4. Build to a new ZIP filename. Unselected clips and the original configuration remain byte-for-byte unchanged.

The builder converts replacements to mono MP3 at 16 kHz and 16 kbps, normalizes loudness, removes source metadata and creates an uncompressed ZIP. These settings describe this builder's output, not universal device compatibility. Filenames alone do not establish event meanings; listen to your own template and verify each mapping. Keep safety/error prompts accurate.

## Installation status

This release builds archives only. It has no login, discovery, network server or device installation feature. Building successfully does not establish that a particular vacuum will accept the package. There is no bundled event catalogue, compatibility list or universal installer. See METHOD.md for the experimental installation approach and remaining gates.

This is a source preview, not a signed Windows executable. No claim of first discovery or support for every model is made. Only use audio and original archives you have permission to use; do not upload them with bug reports.

## Privacy and reporting

All processing is local. No telemetry or upload feature is implemented. Temporary converted clips are cleaned up after normal completion; interrupted runs and operating-system storage may retain local remnants. Source recordings and output archives remain private files on your computer. Report only the stage that failed and a generic error category. Do not attach packages, account information, device identifiers, screenshots of device details or raw logs.

See PRIVACY.md and RELEASE_REQUIREMENTS.md. This source archive has no Git history.
