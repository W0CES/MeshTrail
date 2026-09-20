import json
from pathlib import Path

import pytest

from scripts.check_release_version import check_release_version

ROOT = Path(__file__).parents[1]


def test_current_release_version_matches() -> None:
    assert check_release_version("v0.5.0", ROOT) == "0.5.0"


def test_noncanonical_release_tag_is_rejected() -> None:
    with pytest.raises(ValueError, match="vMAJOR.MINOR.PATCH"):
        check_release_version("release-0.5.0", ROOT)


def test_mismatched_manifest_version_is_rejected(tmp_path: Path) -> None:
    for path in ("pyproject.toml", "openhop-plugin.json"):
        (tmp_path / path).write_bytes((ROOT / path).read_bytes())
    package = tmp_path / "meshtrail_plugin"
    package.mkdir()
    (package / "__init__.py").write_bytes((ROOT / "meshtrail_plugin" / "__init__.py").read_bytes())

    manifest_path = tmp_path / "openhop-plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "0.6.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="openhop-plugin.json=0.6.0"):
        check_release_version("v0.5.0", tmp_path)
