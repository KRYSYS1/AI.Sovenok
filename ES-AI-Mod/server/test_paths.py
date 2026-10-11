"""Shared offline test paths, also importable by the game's Python 2 runner."""
import os
import tempfile


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSHOP_DEFAULT = r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310"
_GAME_DEFAULT = r"D:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer"


def optional_root(variable, default, absent):
    # An explicit absent override must never fall back to a live installation.
    if variable in os.environ:
        return os.path.abspath(os.environ[variable]) if os.environ[variable] else absent
    return default if os.path.isdir(default) else absent


WORKSHOP_ROOT = optional_root("ESAI_WORKSHOP_ROOT", _WORKSHOP_DEFAULT,
                              os.path.join(PROJECT_ROOT, ".missing-workshop"))
GAME_ROOT = optional_root("ESAI_GAME_ROOT", _GAME_DEFAULT,
                          os.path.join(PROJECT_ROOT, ".missing-game"))
TEMP = os.environ.get("ESAI_TEST_TEMP", tempfile.gettempdir())


def existing_paths(paths):
    return tuple(path for path in paths if os.path.exists(path))


ROOTS = (os.path.join(PROJECT_ROOT, "mod"),) + existing_paths((WORKSHOP_ROOT,))
