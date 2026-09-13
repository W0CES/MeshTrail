import json
import tomllib
from pathlib import Path

from meshtrail_plugin import __version__

ROOT = Path(__file__).parents[1]


def test_manifest_package_and_defaults_match() -> None:
    manifest = json.loads((ROOT / "openhop-plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    defaults = json.loads((ROOT / "config.default.json").read_text(encoding="utf-8"))

    assert manifest["schema"] == 1
    assert manifest["id"] == "openhop.meshtrail"
    assert manifest["runtime"] == {"type": "python", "entrypoint": "meshtrail-openhop"}
    assert manifest["config"]["defaults"] == defaults
    assert manifest["version"] == project["version"] == __version__
    assert defaults["meshcore_host"] == "127.0.0.1"
    assert defaults["meshcore_port"] == 5003
    assert manifest["ui"] == {"type": "application", "entry": "ui/index.html"}
    assert defaults["max_active_players"] == 3
    assert defaults["active_player_timeout_seconds"] == 900


def test_packaged_logo_and_container_smoke_files_exist() -> None:
    assert (ROOT / "meshtrail_plugin" / "assets" / "meshtrail-logo.png").is_file()
    assert (ROOT / "meshtrail_plugin" / "assets" / "meshtrail-catalog-card.png").is_file()
    assert (ROOT / "scripts" / "container_smoke.py").is_file()
    assert (ROOT / "tests" / "Dockerfile.smoke").is_file()
    assert (ROOT / "ui" / "index.html").is_file()
    assert (ROOT / "ui" / "app.js").is_file()
    assert (ROOT / "ui" / "styles.css").is_file()

