"""Bounded JSON-only transfers of durable user data; never extract ZIP paths."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zipfile

MAX_FILES = 1000
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
ROOT_FILES = {"config.json", "es_characters.json", "story_events.json"}
MEMORY_PATH = re.compile(r"memory/(?:conversations/)?[A-Za-z0-9_-]+\.json\Z")


def _allowed(name):
    if any(part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(
            prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10))}
           for part in name.split("/")):
        return False
    return name in ROOT_FILES or name == "keys.json" or bool(MEMORY_PATH.fullmatch(name))


def _validate(name, data):
    def reject_constant(_):
        raise ValueError()

    try:
        value = json.loads(data.decode("utf-8-sig"), parse_constant=reject_constant)
        if not isinstance(value, (dict, list)):
            raise ValueError()
        if name in ROOT_FILES or name == "keys.json":
            if not isinstance(value, dict):
                raise ValueError()
        if name == "keys.json" and any(not isinstance(v, str) for v in value.values()):
            raise ValueError()
        if name == "config.json":
            for section in ("llm", "tts", "stt", "game_clock", "cameo", "story_events"):
                if section in value and not isinstance(value[section], dict):
                    raise ValueError()
            for section in value.values():
                if isinstance(section, dict):
                    for key in ("enabled", "show_time", "auto_primary"):
                        if key in section and not isinstance(section[key], bool):
                            raise ValueError()
        if name == "es_characters.json":
            if "characters" in value and (not isinstance(value["characters"], list) or
                    any(not isinstance(item, dict) for item in value["characters"])):
                raise ValueError()
            if "player" in value and not isinstance(value["player"], dict):
                raise ValueError()
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid JSON data: " + name) from None


def _target(directory, name):
    root = Path(directory).absolute()
    path = root.joinpath(*name.split("/"))
    # Reject symlinks/junctions in every component, including the data root.
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked data path is not supported")
    return path


def export_files(directory, include_keys=False):
    root = Path(directory)
    candidates = [root / name for name in sorted(ROOT_FILES)]
    if include_keys:
        candidates.append(root / "keys.json")
    for folder in (root / "memory", root / "memory" / "conversations"):
        _target(root, folder.relative_to(root).as_posix())
        if folder.is_dir():
            candidates.extend(sorted(folder.glob("*.json")))
    files = {}
    total = 0
    for path in candidates:
        name = path.relative_to(root).as_posix()
        if not _allowed(name):
            continue
        path = _target(root, name)
        if not path.exists():
            continue
        if not path.is_file() or path.stat().st_size > MAX_FILE:
            raise ValueError("Invalid file size: " + name)
        data = path.read_bytes()
        total += len(data)
        if len(data) > MAX_FILE or total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise ValueError("Transfer size limit exceeded")
        _validate(name, data)
        files[name] = data
    if not files:
        raise ValueError("No transferable user data")
    return files


def write_archive(destination, files):
    destination = Path(destination)
    fd, temporary = tempfile.mkstemp(prefix=".transfer-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_archive(source):
    files = {}
    total = 0
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > MAX_FILES:
            raise ValueError("Invalid archive file count")
        for info in entries:
            name = info.filename
            mode = info.external_attr >> 16
            if (info.orig_filename != name or not _allowed(name) or name in files or info.flag_bits & 1 or
                    stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or
                    info.file_size > MAX_FILE):
                raise ValueError("Unsupported archive entry")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("Transfer size limit exceeded")
            with archive.open(info) as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) != info.file_size or len(data) > MAX_FILE:
                raise ValueError("Invalid archive file size")
            _validate(name, data)
            files[name] = data
    return files


def import_files(directory, files):
    """Validate everything, back up replaced files, then commit with rollback."""
    if not files or len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_TOTAL:
        raise ValueError("Transfer size limit exceeded")
    targets = {}
    for name, data in files.items():
        if not _allowed(name) or len(data) > MAX_FILE:
            raise ValueError("Unsupported archive entry")
        _validate(name, data)
        target = _target(directory, name)
        if target.exists() and not target.is_file():
            raise ValueError("Destination is not a file")
        targets[name] = target
    backup_root = _target(directory, "import_backups")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=datetime.datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=backup_root))
    stage = Path(tempfile.mkdtemp(prefix=".import-", dir=directory))
    replaced = []
    created_dirs = []
    existed = {}
    try:
        for name, target in targets.items():
            existed[name] = target.exists()
            saved = backup / name
            if existed[name]:
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            staged = stage / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(files[name])
        for name, target in targets.items():
            _target(directory, name)
            missing = []
            parent = target.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                created_dirs.append(parent)
            os.replace(stage / name, target)
            replaced.append(name)
    except Exception:
        for name in reversed(replaced):
            if existed[name]:
                shutil.copy2(backup / name, targets[name])
            else:
                targets[name].unlink()
        for parent in reversed(created_dirs):
            parent.rmdir()
        raise
    finally:
        shutil.rmtree(stage)
    return backup
