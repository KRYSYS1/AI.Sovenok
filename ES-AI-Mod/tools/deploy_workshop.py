"""Offline, allowlisted Workshop snapshots and explicitly authorized patch installs."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import tempfile
import textwrap


PROJECT = Path(__file__).resolve().parents[1]
WORKSHOP = Path(r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310")
PYTHON2 = Path(r"D:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer\lib\windows-i686\python.exe")
POLICY = json.loads(Path(__file__).with_name("workshop_manifest.json").read_text(encoding="utf-8"))
CANONICAL_PLAYER_NAME = "Семён"
CANONICAL_PLAYER_PERSONA = "Обычный молодой человек из России 2020-х, который таинственным образом попал в пионерлагерь «Совёнок» 1980-х. Иногда упоминает вещи из будущего — девушки считают это его странноватым юмором."
PATHS = tuple(sorted(["server/" + p for p in POLICY["server"]] + POLICY["client"] + POLICY["assets"]))


class DeploymentError(ValueError):
    pass


def safe_path(root, name):
    """Reject Windows aliases and reparse points even when run on another OS."""
    if (not isinstance(name, str) or name not in PATHS or "\\" in name
            or PureWindowsPath(name).is_absolute() or ":" in name
            or any(p in ("", ".", "..") or p.endswith((".", " ")) for p in name.split("/"))):
        raise DeploymentError("Unallowlisted path: %r" % name)
    root = Path(os.path.abspath(root))
    for part in (root, *root.parents):
        if part.is_symlink() or (part.exists() and getattr(part.stat(), "st_file_attributes", 0) & 1024):
            raise DeploymentError("Symlink/reparse root: %s" % part)
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink() or (path.exists() and getattr(path.stat(), "st_file_attributes", 0) & 1024):
            raise DeploymentError("Symlink/reparse path: %s" % path)
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_files(root, dev=False, missing=False):
    result = {}
    for name in PATHS:
        # Development clients/assets are under mod/, Workshop clients are flat.
        base = Path(root) / "mod" if dev and not name.startswith("server/") else Path(root)
        path = safe_path(base, name)
        if not path.exists() and missing:
            result[name] = None
        else:
            result[name] = path.read_bytes()
    return result


def trees(files):
    result = {}
    for name, data in files.items():
        if data is not None and name.endswith((".py", ".pyw")):
            text = data.decode("utf-8-sig")
            compile(text, name, "exec")  # Compile in memory; never create pycache or execute modules.
            result[Path(name).stem] = ast.parse(text, filename=name)
    return result


def exports(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.Import):
            names.update(n.asname or n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(n.asname or n.name for n in node.names)
    return names


def init_blocks(data):
    lines = data.decode("utf-8-sig").splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if re.match(r"^init(?:\s+[-\d]+)?\s+python:\s*$", line):
            body = []
            for next_line in lines[i + 1:]:
                if next_line.strip() and not next_line.startswith((" ", "\t")):
                    break
                body.append(next_line)
            blocks.append(textwrap.dedent("\n".join(body)))
    return blocks


def embedded_defaults(tree, required=True):
    assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG" for t in n.targets)]
    if not assignments and not required:
        return None  # Development retains local config.json, not Workshop defaults.
    if len(assignments) != 1 or len(assignments[0].targets) != 1:
        raise DeploymentError("One static DEFAULT_CONFIG literal is required")
    literal = assignments[0].value
    if sum(1 for _ in ast.walk(literal)) > 512:
        raise DeploymentError("Static defaults exceed literal bounds")

    def read(node, allowed, depth=0):
        if depth > 12:
            raise DeploymentError("Static defaults exceed nesting bounds")
        if isinstance(allowed, dict):
            if not isinstance(node, ast.Dict):
                raise DeploymentError("Static defaults must be a dictionary literal")
            result = {}
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or type(key.value) is not str or key.value not in allowed:
                    raise DeploymentError("Unallowlisted static defaults; user data/secrets refused")
                if key.value in result:
                    raise DeploymentError("Duplicate static default field")
                result[key.value] = read(value, allowed[key.value], depth + 1)
            if set(result) != set(allowed):
                raise DeploymentError("Missing static default fields")
            return result
        if (not isinstance(node, ast.Constant) or type(node.value) is not type(allowed)
                or node.value != allowed):
            raise DeploymentError("Nonstatic default value; user data/secrets refused")
        return node.value

    return read(literal, POLICY["static_defaults"])


def validate(files, workshop=True, python2=None):
    if set(files) != set(PATHS) or any(b is None for b in files.values()):
        raise DeploymentError("Incomplete runtime closure; all registry files are required")
    parsed = trees(files)
    seed = json.loads(files["server/es_characters.json"].decode("utf-8-sig"))
    if (not isinstance(seed, dict) or not isinstance(seed.get("characters"), list)
            or not seed["characters"] or not isinstance(seed.get("emotion_synonyms_ru"), dict)
            or not isinstance(seed.get("player", {}), dict)):
        raise DeploymentError("Invalid packaged character seed schema")
    ids = set()
    for character in seed["characters"]:
        if (not isinstance(character, dict) or not isinstance(character.get("id"), str)
                or not character["id"] or character["id"] in ids
                or not isinstance(character.get("name"), str)
                or not isinstance(character.get("persona"), str)):
            raise DeploymentError("Invalid packaged character entry")
        ids.add(character["id"])
    def credential_fields(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if re.search(r"api.?key|secret|password|token|authorization|credential", key, re.I):
                    raise DeploymentError("Credential field in packaged character seed")
                credential_fields(item)
        elif isinstance(value, list):
            for item in value:
                credential_fields(item)
    credential_fields(seed)
    player = seed.get("player", {})
    private_player = (player.get("id") != "player"
                      or player.get("name") != CANONICAL_PLAYER_NAME
                      or player.get("persona") not in ("", CANONICAL_PLAYER_PERSONA)
                      or bool(set(player) - {"id", "name", "persona"}))
    optional = set(POLICY["optional_imports"])
    for module, tree in parsed.items():
        for node in ast.walk(tree):
            imports = [n.name for n in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    raise DeploymentError("Unsupported relative import in " + module)
                imports = [node.module]
            for imported in imports:
                top = imported.split(".")[0]
                if top not in parsed and top not in sys.stdlib_module_names and top not in optional:
                    raise DeploymentError("Missing dependency: %s -> %s" % (module, imported))
                if isinstance(node, ast.ImportFrom) and top in parsed:
                    absent = {n.name for n in node.names} - exports(parsed[top])
                    if absent:
                        raise DeploymentError("Missing import exports: %s -> %s %s" % (module, top, sorted(absent)))
    if workshop:
        loader = parsed["config_loader"]
        strings = {n.value for n in ast.walk(loader) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if not {"user_data_dir", "save_keys", "save_config"} <= exports(loader) or not {"AI.Sovenok", "LOCALAPPDATA"} <= strings:
            raise DeploymentError("Not Workshop flavor: external user_data_dir/keys contract missing")
        launcher = parsed["settings"]
        required = {"run_settings_window", "_log_window_error", "_show_error_box"}
        imported = {a.name for n in ast.walk(launcher) if isinstance(n, ast.ImportFrom)
                    and n.module == "settings_window" for a in n.names}
        if not required <= imported:
            raise DeploymentError("Workshop launcher helper contract missing")
    embedded_defaults(parsed["config_loader"], required=workshop)
    blocks = [b for n, data in files.items() if n.endswith(".rpy") for b in init_blocks(data)]
    status = "unavailable: init blocks not Python-2-verified; no full Ren'Py load"
    if python2 and Path(python2).is_file():
        code = "import ast,json,sys\nfor s in json.load(sys.stdin): compile(s, '<renpy-init>', 'exec', ast.PyCF_ONLY_AST, 1)\n"
        proc = subprocess.run([str(python2), "-c", code], input=json.dumps(blocks),
                              text=True, capture_output=True, timeout=60)
        if proc.returncode:
            raise DeploymentError("Python 2 init syntax failed: " + proc.stderr.strip())
        status = "%s init blocks compiled with Python 2; no full Ren'Py load" % len(blocks)
    return {"python_modules": len(parsed), "renpy": status, "sanitized_defaults": True,
             "character_seed": {"schema_valid": True, "custom_player": private_player,
                                "npc_personas": "preserved; manual privacy review required before publication"},
            "optional_dependencies": sorted(optional), "dynamic_imports": "not executed or fully resolved"}


def flavor_preserved(source, baseline):
    # No automatic merging. Retain existing public loader/launcher/provider contracts.
    old = trees(baseline)
    new = trees(source)
    for name in POLICY["flavor_sensitive"]:
        dev_path = PROJECT / (name if name.startswith("server/") else "mod/" + name)
        if dev_path.is_file() and baseline[name] is not None:
            dev = dev_path.read_bytes()
            if dev != baseline[name] and source[name] == dev:
                raise DeploymentError("Development replacement of divergent Workshop file refused: " + name)
        if not name.endswith((".py", ".pyw")) or baseline[name] is None:
            continue
        module = Path(name).stem
        if module == "config_loader" and not exports(old[module]) <= exports(new[module]):
            raise DeploymentError("Workshop config exports would be lost")
        provider_keys = lambda tree: {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                                     and isinstance(n.value, str) and n.value.endswith("_api_key")}
        if not provider_keys(old[module]) <= provider_keys(new[module]):
            raise DeploymentError("Workshop provider keys would be lost: " + name)
        user_refs = lambda tree: sum(isinstance(n, ast.Name) and n.id == "user_data_dir"
                                    or isinstance(n, ast.Attribute) and n.attr == "user_data_dir"
                                    for n in ast.walk(tree))
        if user_refs(new[module]) < user_refs(old[module]):
            raise DeploymentError("Workshop user-data routing would be lost: " + name)


def new_external_dir(path, forbidden):
    path = Path(os.path.abspath(path))
    if not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise DeploymentError("Output must be absent with an existing parent: " + str(path))
    # Check every ancestor and keep outputs outside installations and userdata.
    safe_path(path.parent, PATHS[0])
    for root in forbidden:
        root = Path(os.path.abspath(root))
        if path == root or root in path.parents or path in root.parents:
            raise DeploymentError("Output overlaps protected root: " + str(root))
    if any(p.lower() == "ai.sovenok" for p in path.parts):
        raise DeploymentError("Output cannot be in user data")
    return path


def protected_roots(*roots):
    return (*roots, PROJECT, WORKSHOP,
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AI.Sovenok")


def build(bundle, source, target, python2=None):
    bundle = new_external_dir(bundle, protected_roots(source, target))
    data = read_files(source)
    baseline = read_files(target, missing=True)
    validation = validate(data, python2=python2)
    if validation["character_seed"]["custom_player"]:
        raise DeploymentError("Customized player in packaged seed; privacy review required before building")
    flavor_preserved(data, baseline)
    entries = [{"path": n, "sha256": digest(data[n]),
                "base_sha256": digest(baseline[n]) if baseline[n] is not None else None} for n in PATHS]
    marker = digest(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())
    manifest = {"schema": 1, "flavor": "workshop", "build_id": marker,
                "files": entries, "validation": validation}
    bundle.mkdir()
    for name, content in data.items():
        path = safe_path(bundle, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    verify(bundle, target, python2)
    return manifest


def verify(bundle, target=None, python2=None):
    bundle = Path(bundle)
    safe_path(bundle, PATHS[0])
    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink() or getattr(path.stat(), "st_file_attributes", 0) & 1024:
            raise DeploymentError("Bundle contains a reparse point")
        if path.is_file() and relative not in (*PATHS, "manifest.json"):
            raise DeploymentError("Bundle contains unallowlisted content: " + relative)
    manifest_path = bundle / "manifest.json"
    if manifest_path.is_symlink() or getattr(manifest_path.stat(), "st_file_attributes", 0) & 1024:
        raise DeploymentError("Manifest is a reparse point")
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    entries = manifest.get("files", [])
    if manifest.get("schema") != 1 or manifest.get("flavor") != "workshop":
        raise DeploymentError("Unsupported bundle schema/flavor")
    names = [e["path"] for e in entries]
    if names != list(PATHS):
        raise DeploymentError("Manifest paths must exactly match the ordered whitelist")
    if manifest.get("build_id") != digest(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()):
        raise DeploymentError("Build marker mismatch")
    data = read_files(bundle)
    baseline = read_files(target, missing=True) if target is not None else None
    for entry in entries:
        name = entry["path"]
        if digest(data[name]) != entry["sha256"]:
            raise DeploymentError("Bundle hash mismatch: " + name)
        base = entry["base_sha256"]
        if base is not None and not re.fullmatch(r"[0-9a-f]{64}", str(base)):
            raise DeploymentError("Invalid baseline hash")
        if baseline is not None:
            actual = digest(baseline[name]) if baseline[name] is not None else None
            if actual != base:
                raise DeploymentError("Target changed since build: " + name)
    validation = validate(data, python2=python2)
    if validation["character_seed"]["custom_player"]:
        raise DeploymentError("Customized player in packaged seed; privacy review required before verification")
    if baseline is not None:
        flavor_preserved(data, baseline)
    return manifest, data, baseline, validation


def apply(bundle, target, backup, python2=None):
    absolute = Path(os.path.abspath(target))
    if absolute == PROJECT or PROJECT in absolute.parents or any(p.lower() == "ai.sovenok" for p in absolute.parts):
        raise DeploymentError("Apply target cannot be development or user data")
    manifest, data, baseline, validation = verify(bundle, target, python2)
    backup = new_external_dir(backup, protected_roots(target, bundle))
    changed = [n for n in PATHS if data[n] != baseline[n]]
    backup.mkdir()
    for name in changed:
        if baseline[name] is not None:
            path = safe_path(backup, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(baseline[name])
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    committed = []
    staged = []
    try:
        # Stage next to destination for same-filesystem atomic replacement.
        for name in changed:
            path = safe_path(target, name)
            if not path.parent.is_dir():
                raise DeploymentError("Target parent must already exist: " + str(path.parent))
            fd, temp = tempfile.mkstemp(prefix=".esai-stage-", dir=path.parent)
            staged.append(temp)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data[name])
                stream.flush()
                os.fsync(stream.fileno())
        verify(bundle, target, python2)
        for name, temp in zip(changed, staged):
            path = safe_path(target, name)
            current = path.read_bytes() if path.exists() else None
            if current != baseline[name]:
                raise DeploymentError("Concurrent target edit: " + name)
            os.replace(temp, path)
            committed.append(name)
    except Exception as error:
        conflicts = []
        for name in reversed(committed):
            try:
                path = safe_path(target, name)
                if not path.exists() or path.read_bytes() != data[name]:
                    conflicts.append(name)
                    continue
                if baseline[name] is None:
                    path.unlink()  # Only remove an unchanged file created by this apply.
                else:
                    fd, temp = tempfile.mkstemp(prefix=".esai-rollback-", dir=path.parent)
                    staged.append(temp)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(baseline[name])
                    os.replace(temp, path)
            except Exception:
                conflicts.append(name)
        raise DeploymentError("Apply failed; best-effort rollback; conflicts=%s; backup=%s; %s"
                              % (conflicts, backup, error)) from error
    finally:
        for temp in staged:
            if os.path.exists(temp):
                os.unlink(temp)
    return {"changed": changed, "backup": str(backup), "validation": validation,
            "compiled_files": "untouched; restart Ren'Py to regenerate from changed source"}


def check(project, target, python2=None):
    dev = read_files(project, dev=True, missing=True)
    installed = read_files(target, missing=True)
    result = {"files": [], "validation": validate(installed, python2=python2)}
    # Explicit registry assets may be Workshop-only.
    dev_complete = dict(dev)
    for name in PATHS:
        if dev_complete[name] is None and name in POLICY["assets"]:
            dev_complete[name] = installed[name]
    result["development_validation"] = validate(dev_complete, workshop=False, python2=python2)
    for name in PATHS:
        a, b = dev[name], installed[name]
        same = a == b
        semantic = same
        if a is not None and b is not None and name.endswith((".py", ".pyw")):
            semantic = ast.dump(ast.parse(a.decode("utf-8-sig"))) == ast.dump(ast.parse(b.decode("utf-8-sig")))
        result["files"].append({"path": name, "comparison": "shared" if same else
                                "semantic-shared" if semantic else "divergent" if a is not None and b is not None else "missing-in-one-root",
                                "flavor_sensitive": name in POLICY["flavor_sensitive"]})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--build", metavar="BUNDLE")
    action.add_argument("--verify", metavar="BUNDLE")
    action.add_argument("--apply", metavar="BUNDLE")
    parser.add_argument("--target", type=Path, default=WORKSHOP)
    parser.add_argument("--project", type=Path, default=PROJECT)
    parser.add_argument("--source", type=Path, help="Explicit staged Workshop-flavor root, never automatic dev copying")
    parser.add_argument("--flavor", choices=["workshop"])
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--python2", type=Path, default=PYTHON2)
    args = parser.parse_args(argv)
    if args.source is not None and (not args.build or args.flavor != "workshop"):
        parser.error("--source requires --build and explicit --flavor workshop")
    if args.apply and args.backup is None:
        parser.error("--apply requires an explicit external --backup directory")
    try:
        if args.build:
            result = build(args.build, args.source or args.target, args.target, args.python2)
        elif args.verify:
            manifest, _, _, validation = verify(args.verify, args.target, args.python2)
            result = {"build_id": manifest["build_id"], "validation": validation, "target_preconditions": "passed"}
        elif args.apply:
            result = apply(args.apply, args.target, args.backup, args.python2)
        else:
            result = check(args.project, args.target, args.python2)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, SyntaxError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("Workshop deployment refused: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
