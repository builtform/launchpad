"""Read a canonical sibling from the installed plugin root."""

from pathlib import Path


def main() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    canonical = plugin_root / "canonical" / "lp-probe.md"
    if "LP_SECTION1_INSTALLED_ROOT_OK" not in canonical.read_text(encoding="utf-8"):
        raise SystemExit("installed-root marker not found")
    print("LP_SECTION1_INSTALLED_ROOT_OK")


if __name__ == "__main__":
    main()
