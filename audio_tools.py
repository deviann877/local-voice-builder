"""Locate user-installed FFmpeg, including an optional adjacent tools folder."""
import shutil
import sys
from pathlib import Path


def tool(name):
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    for directory in (base / 'tools', base):
        path = directory / (name + ('.exe' if sys.platform == 'win32' else ''))
        if path.is_file():
            return str(path)
    return shutil.which(name)
