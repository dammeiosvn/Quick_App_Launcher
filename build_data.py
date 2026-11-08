#!/usr/bin/env python3
"""Build or verify the data archive consumed by Quick App Launcher."""

import argparse
import base64
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
MEMBERS = (
    "Core.json",
    "IconDark.png",
    "IconLight.png",
    "MenuDark.json",
    "MenuLight.json",
    "SystemApps.json",
)
ROUTES = ["open_apps", "add_app", "manage_apps", "data", "settings"]
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def load_members():
    members = {name: (ROOT / "data" / name).read_bytes() for name in MEMBERS}
    core = json.loads(members["Core.json"])
    codes = set(core["languages"].values())
    if not {"vi-VN", "en-GB"} <= codes or codes != set(core["locales"]):
        raise ValueError("The language picker and translation files disagree")
    for locale in core["locales"].values():
        if any(not locale["ui"].get(route) for route in ROUTES):
            raise ValueError("A menu route is missing its localized title")
        if any(re.search(r"[\\;,\r\n]", locale["ui"][route]) for route in ROUTES):
            raise ValueError("A menu title contains a vCard control character")
    for theme in ("Dark", "Light"):
        if not members[f"Icon{theme}.png"].startswith(PNG_HEADER):
            raise ValueError(f"Invalid {theme} Home Screen icon")
        rows = json.loads(members[f"Menu{theme}.json"])["items"]
        if [row["id"] for row in rows] != ROUTES:
            raise ValueError(f"Invalid {theme} menu order or route IDs")
        if any(not base64.b64decode(row["photo"], validate=True).startswith(PNG_HEADER) for row in rows):
            raise ValueError(f"Invalid {theme} menu icon")
    catalog = json.loads(members["SystemApps.json"])
    bundle_ids = set()
    for title, card in catalog.items():
        if not title or re.search(r"[/\\\x00-\x1f]", title) or not card.startswith("BEGIN:VCARD\nVERSION:3.0\n"):
            raise ValueError(f"Invalid system app card for {title!r}")
        note = re.findall(r"^NOTE:([A-Za-z0-9][A-Za-z0-9.-]+)$", card, re.MULTILINE)
        if len(note) != 1 or note[0] in bundle_ids or not card.endswith("\nEND:VCARD\n"):
            raise ValueError(f"Missing or duplicate bundle ID for {title!r}")
        bundle_ids.add(note[0])
    if not catalog:
        raise ValueError("The system app catalog is empty")
    return members


def describe(version, archive):
    return {
        "schemaVersion": 1,
        "dataVersion": version,
        "minimumShortcutBuild": 1,
        "archive": f"launcher-data-v{version}.zip",
        "bytes": len(archive),
        "sha256": hashlib.sha256(archive).hexdigest(),
    }


def build(version, members, manifest_path):
    output = io.BytesIO()
    with ZipFile(output, "w") as package:
        for name, contents in members.items():
            entry = ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            package.writestr(entry, contents, ZIP_DEFLATED, compresslevel=9)
    archive = output.getvalue()
    manifest = describe(version, archive)
    archive_path = manifest_path.parent / manifest["archive"]
    if archive_path.exists() and archive_path.read_bytes() != archive:
        raise ValueError("This data version already has different bytes. Use a new version.")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(archive)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def verify(members, manifest_path):
    manifest = json.loads(manifest_path.read_bytes())
    version = manifest["dataVersion"]
    if type(version) is not int or not 1 <= version <= 999999:
        raise ValueError("Invalid data version")
    archive = (manifest_path.parent / f"launcher-data-v{version}.zip").read_bytes()
    if manifest != describe(version, archive):
        raise ValueError("The manifest does not match the archive")
    with ZipFile(io.BytesIO(archive)) as package:
        if package.namelist() != list(members):
            raise ValueError("Unexpected archive member list")
        for name, contents in members.items():
            if package.read(name) != contents:
                raise ValueError(f"The archive contains a stale copy of {name}")
    print(f"Verified data v{version}, {len(members)} files, {len(archive):,} bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--data-version", type=int)
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.data_version is not None and not 1 <= args.data_version <= 999999:
        parser.error("--data-version must be between 1 and 999999")
    manifest_path = ROOT / "dist" / "manifest.json"
    members = load_members()
    if args.data_version is not None:
        build(args.data_version, members, manifest_path)
    verify(members, manifest_path)


if __name__ == "__main__":
    main()
