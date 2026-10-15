"""Local Voice Studio: user-owned audio import, mapping and explicit installation."""
import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from audio_tools import tool
from builder import build, read_template
from packs import import_pack, phrases, validate_install
from transport import check_connection, install

logging.disable(logging.CRITICAL)


class Studio:
    def __init__(self, window):
        self.window = window
        window.title('Local Voice Studio — experimental L60 installer')
        window.geometry('1120x780')
        window.minsize(940, 670)
        self.temp = tempfile.TemporaryDirectory(prefix='local-voice-')
        self.folder = Path(self.temp.name)
        self.events = json.loads((Path(__file__).parent / 'events.json').read_text(encoding='utf-8'))
        self.sources = {}
        self.labels = {}
        self.mapping = {}
        self.template = None
        self.template_files = {}
        self.candidate = None
        self.busy = False
        self.player = None
        self.messages = queue.Queue()
        self.buttons = []
        self.status = tk.StringVar(value='Start with your original stock voice ZIP. No voices are included.')
        ttk.Label(window, text='Your voices. Your vacuum. Local processing.', font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=18, pady=(16, 4))
        ttk.Label(window, text='Experimental L60 support • No cloud login • No credential saving • No automatic device changes').pack(anchor='w', padx=18)
        tabs = ttk.Notebook(window)
        tabs.pack(fill='both', expand=True, padx=16, pady=12)
        mapping = ttk.Frame(tabs, padding=12)
        device = ttk.Frame(tabs, padding=16)
        help_tab = ttk.Frame(tabs, padding=16)
        tabs.add(mapping, text='1  Import and map')
        tabs.add(device, text='2  Review and install')
        tabs.add(help_tab, text='Setup and recovery')
        controls = ttk.Frame(mapping)
        controls.pack(fill='x')
        self.button(controls, 'Open stock ZIP', self.open_template).pack(side='left', padx=(0, 6))
        self.button(controls, 'Import voice pack', self.open_pack).pack(side='left', padx=6)
        self.button(controls, 'Add recordings', self.add_recordings).pack(side='left', padx=6)
        self.button(controls, 'Load phrase CSV', self.load_phrases).pack(side='left', padx=6)
        ttk.Label(mapping, text='Event labels are community interpretations, not proof of every trigger. Preview stock audio before mapping.').pack(anchor='w', pady=10)
        panes = ttk.Panedwindow(mapping, orient='horizontal')
        panes.pack(fill='both', expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        self.tree = ttk.Treeview(left, columns=('event', 'choice'), show='tree headings', selectmode='browse')
        self.tree.heading('#0', text='Clip')
        self.tree.heading('event', text='Eufy event')
        self.tree.heading('choice', text='Replacement')
        self.tree.column('#0', width=90, stretch=False)
        self.tree.column('event', width=250)
        self.tree.column('choice', width=160)
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.search = tk.StringVar()
        ttk.Label(right, text='Your imported recordings — search names or supplied phrases').pack(anchor='w')
        ttk.Entry(right, textvariable=self.search).pack(fill='x', pady=5)
        self.search.trace_add('write', lambda *_: self.refresh_sources())
        self.source_list = tk.Listbox(right, exportselection=False)
        self.source_list.pack(fill='both', expand=True)
        self.source_list.bind('<Double-Button-1>', lambda _: self.preview_source())
        row = ttk.Frame(mapping)
        row.pack(fill='x', pady=(10, 0))
        for text, command in [('Listen to stock', self.preview_stock), ('Listen to source', self.preview_source),
                              ('Use for event', self.assign), ('Keep stock', self.unassign), ('Build ZIP', self.build_pack)]:
            self.button(row, text, command).pack(side='left', padx=(0, 8))
        ttk.Label(device, text='Connect using your own local credentials', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        self.fields = {}
        for index, (name, title, secret) in enumerate((('address', 'Vacuum LAN address', False),
                ('device_id', 'Device ID', True), ('local_key', 'Local key (16 bytes)', True)), 1):
            ttk.Label(device, text=title).grid(row=index, column=0, sticky='w', pady=6)
            value = tk.StringVar()
            self.fields[name] = value
            ttk.Entry(device, textvariable=value, show='•' if secret else '', width=52).grid(row=index, column=1, sticky='ew', padx=12, pady=6)
        device.columnconfigure(1, weight=1)
        row = ttk.Frame(device)
        row.grid(row=4, column=0, columnspan=2, sticky='w', pady=12)
        self.button(row, 'Import private connection JSON', self.import_connection).pack(side='left', padx=(0, 8))
        self.button(row, 'Check connection (read only)', self.check).pack(side='left', padx=8)
        self.button(row, 'Clear credentials', self.clear_credentials).pack(side='left', padx=8)
        self.review = tk.StringVar(value='No built or imported candidate selected.')
        ttk.Label(device, textvariable=self.review, wraplength=850).grid(row=5, column=0, columnspan=2, sticky='w', pady=12)
        self.button(device, 'Select an already-built Eufy ZIP', self.open_candidate).grid(row=6, column=0, columnspan=2, sticky='w', pady=8)
        self.approval = tk.BooleanVar(value=False)
        ttk.Checkbutton(device, variable=self.approval, text='This is my L60, it is idle and powered, and I have an original stock ZIP and official-app recovery access.').grid(row=7, column=0, columnspan=2, sticky='w', pady=12)
        ttk.Label(device, text='A failed or interrupted update may not be recoverable. Compatibility outside the research setup is unverified.\n'
                  'The next button asks for final confirmation. It then sends one voice request and observes for up to three minutes.',
                  wraplength=850).grid(row=8, column=0, columnspan=2, sticky='w', pady=10)
        self.button(device, 'Review and install selected ZIP…', self.install_pack).grid(row=9, column=0, columnspan=2, sticky='w', pady=10)
        guide = (
            'Before you start\n\n'
            '• Use the same LAN as your vacuum. Keep your firewall settings unchanged unless you understand and approve a required rule.\n'
            '• You need your own original English voice ZIP plus the vacuum device ID and Tuya local key. This app does not obtain these from your Eufy account.\n'
            '• Existing local integrations may already have these details. The LAN address alone is not sufficient. Never post keys or connection files publicly.\n'
            '• For source recordings, install FFmpeg (ffmpeg, ffprobe and ffplay) on PATH, or place the executables in a tools folder beside this app. No automatic download occurs.\n\n'
            'Map your pack\n\n'
            'Import a ZIP or TAR.GZ, or add individual OGG/MP3/WAV files. Pack scripts are never run. Select an Eufy event on the left and a recording on the right, then Use for event. '
            'Unmapped clips remain stock. A numeric filename in another brand’s pack does not imply the same Eufy event. '
            'Optional phrase CSV headers: filename,phrase. Preserve accurate safety and error announcements.\n\n'
            'Installation and recovery\n\n'
            'Read-only connection checking does not establish the model or firmware. L60 identity is owner-confirmed. Only reviewed English archive layouts are accepted. '
            'The app validates all audio, preserves ID/version, serves one file to the target for a bounded time and sends one request. No automatic retries or firmware changes. '
            'A full transfer and success status still need a listening check and normal-operation check.\n\n'
            'After a completed successful update, restore an official stock language through the Eufy app if desired. A saved original ZIP can also be selected here, '
            'but this is not a proven recovery route after an interrupted or failed update. If the outcome is unknown, do not immediately retry, reboot or cut power; '
            'first resolve status in the official app and consult device support.\n\n'
            'Privacy\n\n'
            'No telemetry, account login or saved credentials. The local key is cleared from the form after an install attempt. '
            'Inputs, previews and generated archives remain local. Do not share connection JSON, stock backups or raw logs. '
            'See README and PRIVACY for limitations. No voices are bundled.'
        )
        text = tk.Text(help_tab, wrap='word', relief='flat', padx=8, pady=8)
        text.insert('1.0', guide)
        text.configure(state='disabled')
        text.pack(fill='both', expand=True)
        ttk.Label(window, textvariable=self.status, wraplength=1050).pack(anchor='w', padx=18, pady=(0, 14))
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.report_callback_exception = lambda *_: messagebox.showerror('Stopped', 'The action could not complete. No raw device or account details were logged.')
        window.after(100, self.poll)

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.buttons.append(button)
        return button

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                elif kind == 'done':
                    self.busy = False
                    for button in self.buttons:
                        button.configure(state='normal')
                    callback, result, error = value
                    if error:
                        self.status.set(error)
                        messagebox.showerror('Action stopped', error)
                    else:
                        callback(result)
        except queue.Empty:
            pass
        self.window.after(100, self.poll)

    def background(self, action, complete, secret=False):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state='disabled')
        def run():
            result = error = None
            try:
                result = action()
            except ValueError as failure:
                # Our ValueErrors are safe categories; third-party errors are not.
                if failure.__traceback__:
                    origin = failure.__traceback__
                    while origin.tb_next:
                        origin = origin.tb_next
                    safe = Path(origin.tb_frame.f_code.co_filename).name in ('app.py', 'builder.py', 'packs.py', 'transport.py')
                else:
                    safe = False
                error = str(failure) if safe else 'Unsupported input or response. Raw details omitted.'
            except Exception:
                error = 'Action could not complete. Check setup and the recovery guide; raw details omitted.'
            self.messages.put(('done', (lambda value: complete(value), result, error)))
            if secret:
                self.messages.put(('status', 'Installation attempt finished. Resolve any unknown outcome before trying again.'))
        threading.Thread(target=run, daemon=True).start()

    def refresh_sources(self):
        query = self.search.get().casefold()
        self.visible = [name for name in sorted(self.sources) if query in (name + ' ' + self.labels.get(name, '')).casefold()]
        self.source_list.delete(0, tk.END)
        for name in self.visible:
            label = self.labels.get(name, '')
            self.source_list.insert(tk.END, name + (' — ' + label if label else ''))

    def refresh_events(self):
        selected = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)
        if self.template:
            for name in sorted(self.template_files):
                if name.endswith('.mp3'):
                    short = Path(name).name
                    self.tree.insert('', 'end', iid=name, text=short,
                        values=(self.events.get(short, 'Verify by listening'), self.mapping.get(name, 'Keep stock')))
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        self.status.set(str(len(self.mapping)) + ' replacements selected. Unmapped events stay stock.')

    def open_template(self):
        path = filedialog.askopenfilename(filetypes=[('Original stock voice ZIP', '*.zip')])
        if not path:
            return
        try:
            files, _ = read_template(path)
        except Exception:
            messagebox.showerror('Template rejected', 'Unsupported, unsafe or unreadable stock ZIP.')
            return
        self.template = Path(path)
        self.template_files = files
        self.mapping.clear()
        self.candidate = None
        self.review.set('Template selected. Build a candidate or select an existing compatible ZIP.')
        self.refresh_events()

    def open_pack(self):
        path = filedialog.askopenfilename(filetypes=[('Voice packs', '*.zip *.tar.gz *.tgz *.tar'), ('All files', '*')])
        if not path:
            return
        directory = self.folder / ('pack-' + str(len(list(self.folder.iterdir()))))
        directory.mkdir()
        def complete(audio):
            for name, path in audio.items():
                while name in self.sources:
                    name = 'imported-' + name
                self.sources[name] = path
            self.refresh_sources()
            self.status.set(str(len(audio)) + ' recordings imported. Nothing was installed.')
        self.background(lambda: import_pack(path, directory), complete)

    def add_recordings(self):
        paths = filedialog.askopenfilenames(filetypes=[('Audio', '*.ogg *.mp3 *.wav *.flac *.m4a *.aac')])
        for value in paths:
            path = Path(value)
            name = path.name
            if name in self.sources:
                name = str(len(self.sources)) + '-' + name
            self.sources[name] = path
        self.refresh_sources()

    def load_phrases(self):
        path = filedialog.askopenfilename(filetypes=[('Phrase CSV', '*.csv')])
        if not path:
            return
        try:
            self.labels.update(phrases(path))
            self.refresh_sources()
        except Exception:
            messagebox.showerror('Phrase list rejected', 'Use a bounded CSV with headers filename,phrase.')

    def selected_source(self):
        selection = self.source_list.curselection()
        return self.visible[selection[0]] if selection else None

    def assign(self):
        event = self.tree.selection()
        source = self.selected_source()
        if event and source:
            self.mapping[event[0]] = source
            self.candidate = None
            self.review.set('Mapping changed. Build a new candidate before installation.')
            self.refresh_events()

    def unassign(self):
        event = self.tree.selection()
        if event:
            self.mapping.pop(event[0], None)
            self.candidate = None
            self.review.set('Mapping changed. Build a new candidate before installation.')
            self.refresh_events()

    def stop_player(self):
        if self.player and self.player.poll() is None:
            self.player.terminate()
            try:
                self.player.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.player.kill()
        self.player = None

    def play(self, path):
        player = tool('ffplay')
        if not player:
            messagebox.showinfo('Preview setup', 'FFplay is required for listening previews. See Setup and recovery.')
            return
        self.stop_player()
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        self.player = subprocess.Popen([player, '-nostats', '-loglevel', 'quiet', '-protocol_whitelist', 'file,pipe', '-nodisp', '-autoexit', '-t', '120', '-i', str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)

    def preview_source(self):
        name = self.selected_source()
        if name:
            self.play(self.sources[name])

    def preview_stock(self):
        selected = self.tree.selection()
        if selected:
            self.stop_player()
            path = self.folder / 'stock-preview.mp3'
            path.write_bytes(self.template_files[selected[0]])
            self.play(path)

    def build_pack(self):
        if not self.template or not self.mapping:
            messagebox.showinfo('Select audio', 'Open a stock ZIP and map at least one recording first.')
            return
        value = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('Built voice ZIP', '*.zip')])
        if not value:
            return
        template = self.template
        replacements = {name: self.sources[source] for name, source in self.mapping.items()}
        def complete(_):
            self.candidate = Path(value)
            self.review.set('Built candidate selected. ' + str(len(replacements)) + ' replacements. ID and version preserved.')
            self.status.set('Build complete. Review and install is a separate explicit action.')
        self.status.set('Converting recordings and building your ZIP…')
        self.background(lambda: build(template, replacements, value), complete)

    def open_candidate(self):
        if not self.template:
            messagebox.showinfo('Original required', 'Open your original stock ZIP first, to validate this candidate.')
            return
        value = filedialog.askopenfilename(filetypes=[('Already-built Eufy voice ZIP', '*.zip')])
        if value:
            self.candidate = Path(value)
            self.review.set('Existing candidate selected. Structure and audio will be validated before any write.')

    def details(self):
        return tuple(self.fields[name].get().strip() if name != 'local_key' else self.fields[name].get()
                     for name in ('device_id', 'address', 'local_key'))

    def clear_credentials(self):
        for value in self.fields.values():
            value.set('')
        self.approval.set(False)

    def import_connection(self):
        value = filedialog.askopenfilename(filetypes=[('Private connection JSON', '*.json')])
        if not value:
            return
        try:
            path = Path(value)
            if path.stat().st_size > 16384:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            fields = {'address': data.get('address', data.get('candidate_local_ip')), 'device_id': data.get('device_id'), 'local_key': data.get('local_key')}
            if not all(isinstance(v, str) for v in fields.values()):
                raise ValueError()
            for name, text in fields.items():
                self.fields[name].set(text)
            self.status.set('Private details loaded into memory only. Never share this JSON.')
        except Exception:
            messagebox.showerror('Connection file rejected', 'Expected a small private JSON with address, device_id and local_key fields.')

    def check(self):
        details = self.details()
        self.background(lambda: check_connection(*details), lambda _: self.status.set('Local voice status received. This does not independently verify the model or compatibility.'))

    def install_pack(self):
        if not self.template or not self.candidate or not self.approval.get():
            messagebox.showinfo('Review required', 'Select a stock template and candidate, then confirm the idle-device and recovery checklist.')
            return
        if not messagebox.askyesno('Approve one voice installation?',
            'Install the selected archive on your L60?\n\nOne local voice request; no version increase or automatic retry. '
            'Keep the vacuum powered and this app open for up to three minutes. '
            'Failure/interruption recovery is unproven. Your local key will be cleared after the attempt.\n\nProceed?'):
            return
        template, candidate, details = self.template, self.candidate, self.details()
        self.approval.set(False)
        # Clear form immediately; only the worker retains the key for this operation.
        self.fields['local_key'].set('')
        def action():
            with tempfile.TemporaryDirectory() as directory:
                snapshots = []
                for index, source in enumerate((template, candidate)):
                    with source.open('rb') as stream:
                        blob = stream.read(64 * 1024 * 1024 + 1)
                    if len(blob) > 64 * 1024 * 1024:
                        raise ValueError('Archive exceeds supported limits.')
                    snapshot = Path(directory) / (str(index) + '.zip')
                    snapshot.write_bytes(blob)
                    snapshots.append(snapshot)
                package_id, version = validate_install(*snapshots, self.events)
                self.messages.put(('status', 'Validating all candidate audio before connecting…'))
                self.validate_audio(snapshots[1])
                return install(*details, blob, package_id, version, lambda text: self.messages.put(('status', text)))
        def complete(result):
            self.status.set(result)
            messagebox.showinfo('Installation observation', result)
        self.background(action, complete)

    def validate_audio(self, path):
        probe, ffmpeg = tool('ffprobe'), tool('ffmpeg')
        if not probe or not ffmpeg:
            raise ValueError('FFmpeg and FFprobe are required for pre-install audio validation.')
        files, clips = read_template(path)
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        with tempfile.TemporaryDirectory() as temp:
            for index, name in enumerate(clips):
                audio = Path(temp) / (str(index) + '.mp3')
                audio.write_bytes(files[name])
                try:
                    result = subprocess.run([probe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_entries',
                        'stream=codec_name,sample_rate,channels,bit_rate:format=duration', '-of', 'json', str(audio)],
                        check=True, capture_output=True, timeout=20, **flags)
                    meta = json.loads(result.stdout)
                    if meta['streams'] != [{'codec_name': 'mp3', 'sample_rate': '16000', 'channels': 1, 'bit_rate': '16000'}] or not 0 < float(meta['format']['duration']) <= 120:
                        raise ValueError('Audio must be mono 16 kbps MP3 at 16 kHz, with duration at most two minutes.')
                    decoded = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-i', str(audio), '-f', 'null', '-'],
                        check=True, capture_output=True, timeout=30, **flags)
                    if decoded.stderr.strip():
                        raise ValueError('Candidate audio contains decoding errors.')
                except (subprocess.SubprocessError, KeyError, TypeError):
                    raise ValueError('Candidate audio could not be validated. No update sent.') from None

    def close(self):
        if self.busy:
            messagebox.showinfo('Action in progress', 'Keep the app open until the bounded operation finishes.')
            return
        self.stop_player()
        self.clear_credentials()
        self.temp.cleanup()
        self.window.destroy()


def main():
    window = tk.Tk()
    if sys.argv[1:] == ['--self-test']:
        window.withdraw()
        studio = Studio(window)
        assert len(studio.events) == 86 and not studio.sources and studio.candidate is None
        studio.close()
        return
    Studio(window)
    window.mainloop()


if __name__ == '__main__':
    main()
