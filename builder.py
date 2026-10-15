"""Offline voice archive builder. Python standard library plus FFmpeg tools."""
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 64 * 1024 * 1024


def read_template(path):
    """Accept a bounded voice ZIP with one config and numbered MP3 clips."""
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 512 or sum(x.file_size for x in entries) > MAX_BYTES:
            raise ValueError('Template exceeds supported limits.')
        files = {}
        roots = set()
        for entry in entries:
            name = entry.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith('/') or '\\' in name or
                    any(p in ('.', '..') for p in parts) or ':' in name or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe archive entry.')
            if entry.is_dir():
                continue
            if name in files or not re.fullmatch(
                    r'[a-zA-Z0-9_]+/(?:config\.yaml|main/A[0-9]{4}\.mp3)', name):
                raise ValueError('Unexpected or duplicate archive entry.')
            roots.add(parts[0])
            files[name] = archive.read(entry)
        if len(roots) != 1:
            raise ValueError('Expected one voice folder.')
        root = roots.pop()
        config = files.get(root + '/config.yaml', b'')
        if not re.fullmatch(rb'id: [0-9]+\r?\nversion: [0-9]+\r?\n?', config):
            raise ValueError('Unsupported template configuration.')
        clips = sorted(n for n in files if n.endswith('.mp3'))
        if not clips:
            raise ValueError('Template contains no voice clips.')
        return files, clips


def build(template, replacements, destination):
    files, clips = read_template(template)
    if not replacements or set(replacements) - set(clips):
        raise ValueError('Choose at least one valid replacement.')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a new output filename; existing files are preserved.')
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise ValueError('Install FFmpeg and make ffmpeg and ffprobe available on PATH.')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with tempfile.TemporaryDirectory() as temp:
        for index, (name, source) in enumerate(replacements.items()):
            output = Path(temp) / (str(index) + '.mp3')
            command = [ffmpeg, '-nostdin', '-v', 'error', '-i', str(Path(source).resolve()),
                       '-map_metadata', '-1', '-vn', '-af', 'loudnorm=I=-20:TP=-3:LRA=7',
                       '-ar', '16000', '-ac', '1', '-codec:a', 'libmp3lame', '-b:a', '16k',
                       '-write_xing', '1', '-id3v2_version', '3', str(output)]
            try:
                subprocess.run(command, check=True, capture_output=True, timeout=120, **flags)
                result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'a:0',
                    '-show_entries', 'stream=codec_name,sample_rate,channels', '-of', 'csv=p=0',
                    str(output)], check=True, capture_output=True, timeout=30, **flags)
            except (subprocess.SubprocessError, OSError):
                raise ValueError('Audio conversion failed. Check the selected recording.') from None
            if result.stdout.decode().strip() != 'mp3,16000,1':
                raise ValueError('Converted audio failed format verification.')
            files[name] = output.read_bytes()
        if sum(map(len, files.values())) > MAX_BYTES:
            raise ValueError('Result exceeds supported limits.')
        # Build privately first; exclusive creation prevents accidental overwrite.
        staged = Path(temp) / 'pack.zip'
        with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                info.create_system = 0
                archive.writestr(info, data)
        with destination.open('xb') as target:
            target.write(staged.read_bytes())


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    window = tk.Tk()
    window.title('Local Voice Builder — offline preview')
    window.geometry('650x460')
    state = {'template': None, 'clips': [], 'replacements': {}}
    tk.Label(window, text='Open your own stock ZIP, select a clip, then choose replacement audio.\n'
             'Unselected clips and package ID/version are preserved. Nothing is installed.',
             justify='left', pady=12).pack()
    listing = tk.Listbox(window, width=75)
    listing.pack(fill='both', expand=True, padx=12)
    status = tk.StringVar(value='No template loaded. Clip meanings must be verified by you.')
    tk.Label(window, textvariable=status, wraplength=620).pack(pady=8)

    def open_template():
        path = filedialog.askopenfilename(filetypes=[('Stock voice archive', '*.zip')])
        if not path:
            return
        try:
            _, clips = read_template(path)
        except Exception:
            messagebox.showerror('Template rejected', 'Unsupported, unsafe or unreadable template.')
            return
        state.update(template=path, clips=clips, replacements={})
        listing.delete(0, tk.END)
        for name in clips:
            listing.insert(tk.END, name)
        status.set('Template loaded. Select a clip to replace.')

    def replace():
        selection = listing.curselection()
        if not selection:
            return
        path = filedialog.askopenfilename(filetypes=[('Audio recordings', '*.ogg *.wav *.mp3 *.flac *.m4a')])
        if path:
            name = state['clips'][selection[0]]
            state['replacements'][name] = path
            listing.delete(selection[0])
            listing.insert(selection[0], name + ' [replacement selected]')
            status.set(str(len(state['replacements'])) + ' replacements selected.')

    def save():
        if not state['template'] or not state['replacements']:
            messagebox.showinfo('Choose audio', 'Load a template and select replacement audio first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('Voice archive', '*.zip')])
        if not path:
            return
        try:
            build(state['template'], state['replacements'], path)
        except ValueError as error:
            messagebox.showerror('Build stopped', str(error))
        except Exception:
            messagebox.showerror('Build stopped', 'Unable to build or save the archive.')
        else:
            messagebox.showinfo('Built locally', 'Archive saved. Device compatibility and installation are separate steps.')

    controls = tk.Frame(window)
    controls.pack(pady=12)
    for text, command in [('Open stock ZIP', open_template), ('Replace selected clip', replace), ('Build ZIP', save)]:
        tk.Button(controls, text=text, command=command).pack(side='left', padx=6)
    window.mainloop()


if __name__ == '__main__':
    main()
