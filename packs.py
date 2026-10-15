"""Read user-owned packs without extracting paths or executing pack scripts."""
import csv
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from builder import MAX_BYTES, read_template

AUDIO = {'.ogg', '.mp3', '.wav', '.flac', '.m4a', '.aac'}


def safe_name(name):
    parts = PurePosixPath(name).parts
    if not parts or name.startswith('/') or '\\' in name or ':' in name or any(p in ('.', '..') for p in parts):
        raise ValueError('Unsafe source archive path.')
    return PurePosixPath(name)


def import_pack(path, directory):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Source pack exceeds the supported size limit.')
    audio = {}
    seen = set()
    total = 0

    def add(name, size, read):
        nonlocal total
        clean = safe_name(name)
        if name in seen:
            raise ValueError('Duplicate source archive entry.')
        seen.add(name)
        total += size
        if len(seen) > 2048 or total > MAX_BYTES * 2:
            raise ValueError('Expanded source pack exceeds supported limits.')
        suffix = clean.suffix.lower()
        if suffix in AUDIO:
            if len(audio) >= 1024:
                raise ValueError('Too many recordings in source pack.')
            # Use generated output names, never paths supplied by an archive.
            target = Path(directory) / (str(len(audio)) + suffix)
            data = read()
            if len(data) != size:
                raise ValueError('Source entry length mismatch.')
            target.write_bytes(data)
            audio[name] = target

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > 2048:
                raise ValueError('Too many source entries.')
            for entry in archive.infolist():
                safe_name(entry.filename)
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Source links are not supported.')
                if not entry.is_dir():
                    add(entry.filename, entry.file_size, lambda e=entry: archive.read(e))
    else:
        with tarfile.open(path, 'r:*') as archive:
            count = 0
            for entry in archive:
                count += 1
                if count > 2048:
                    raise ValueError('Too many source entries.')
                safe_name(entry.name)
                if entry.isdir():
                    continue
                if not entry.isfile():
                    raise ValueError('Source links and special files are not supported.')
                def read(e=entry):
                    with archive.extractfile(e) as stream:
                        return stream.read(MAX_BYTES * 2 + 1)
                add(entry.name, entry.size, read)
    if not audio:
        raise ValueError('No supported audio files in this pack.')
    return audio


def phrases(path):
    """Optional user-supplied CSV: filename,phrase. Never a Python pack script."""
    if Path(path).stat().st_size > 1024 * 1024:
        raise ValueError('Phrase list exceeds supported limits.')
    rows = csv.DictReader(io.StringIO(Path(path).read_text(encoding='utf-8-sig')))
    if rows.fieldnames != ['filename', 'phrase']:
        raise ValueError('CSV must have exactly these headers: filename,phrase')
    result = {}
    for row in rows:
        if len(result) >= 1024 or not row.get('filename') or not isinstance(row.get('phrase'), str):
            raise ValueError('Invalid phrase list.')
        result[row['filename']] = row['phrase'][:400]
    return result


def metadata(files):
    config = next(v for k, v in files.items() if k.endswith('/config.yaml'))
    values = [int(x) for x in re.findall(rb': ([0-9]+)', config)]
    if len(values) != 2:
        raise ValueError('Invalid package configuration.')
    return tuple(values)


def validate_install(template, candidate, event_names):
    original, clips = read_template(template)
    files, output_clips = read_template(candidate)
    package_id, version = metadata(original)
    folder = {501: 'en_us_female', 502: 'en_us_male'}.get(package_id)
    if not folder or not 0 < version < 65536:
        raise ValueError('Only the reviewed English voice layouts are supported.')
    if len(clips) != 86 or {Path(n).name for n in clips} != set(event_names):
        raise ValueError('Stock template does not match the reviewed 86-clip layout.')
    if any(not n.startswith(folder + '/') for n in original):
        raise ValueError('Stock folder does not match the voice ID.')
    if set(files) != set(original) or output_clips != clips or files[folder + '/config.yaml'] != original[folder + '/config.yaml']:
        raise ValueError('Candidate structure, ID or version differs from the original stock template.')
    with zipfile.ZipFile(candidate) as archive:
        if any(e.compress_type != zipfile.ZIP_STORED for e in archive.infolist()):
            raise ValueError('Candidate must use uncompressed ZIP storage.')
    return package_id, version
