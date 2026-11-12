#!/usr/bin/env python3
"""Install the Firebase Android config and Gradle plugin after flutter create."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"
CONFIG_SOURCE = ROOT / "android_overlay" / "google-services.json"
PLUGIN_VERSION = "4.5.0"
EXPECTED_PACKAGE = "com.shaghelmokh.shaghel_mokh"


def insert_after_plugins_open(text: str, line: str) -> str:
    match = re.search(r"(?m)^plugins\s*\{", text)
    if not match:
        raise RuntimeError("Could not find a Gradle plugins { } block")
    insert_at = match.end()
    return text[:insert_at] + "\n" + line + text[insert_at:]


def configure_plugin() -> str:
    settings = next(
        (ANDROID / name for name in ("settings.gradle.kts", "settings.gradle") if (ANDROID / name).is_file()),
        None,
    )
    app_gradle = next(
        (ANDROID / "app" / name for name in ("build.gradle.kts", "build.gradle") if (ANDROID / "app" / name).is_file()),
        None,
    )
    if settings is None or app_gradle is None:
        raise RuntimeError("Generated Android Gradle files were not found")

    settings_text = settings.read_text()
    app_text = app_gradle.read_text()
    plugin_id = "com.google.gms.google-services"

    if plugin_id not in settings_text:
        if settings.suffix == ".kts":
            line = f'    id("{plugin_id}") version "{PLUGIN_VERSION}" apply false'
        else:
            line = f"    id '{plugin_id}' version '{PLUGIN_VERSION}' apply false"
        try:
            settings_text = insert_after_plugins_open(settings_text, line)
        except RuntimeError:
            # Older Flutter Gradle layout: register the plugin on the root buildscript classpath.
            root_gradle = next(
                (ANDROID / name for name in ("build.gradle", "build.gradle.kts") if (ANDROID / name).is_file()),
                None,
            )
            if root_gradle is None:
                raise
            root_text = root_gradle.read_text()
            dep_match = re.search(r"(?m)^\s*dependencies\s*\{", root_text)
            if not dep_match:
                raise RuntimeError("Could not find root Gradle dependencies block for Google Services plugin")
            if root_gradle.suffix == ".kts":
                classpath = f'    classpath("com.google.gms:google-services:{PLUGIN_VERSION}")\n'
            else:
                classpath = f"    classpath 'com.google.gms:google-services:{PLUGIN_VERSION}'\n"
            root_text = root_text[:dep_match.end()] + "\n" + classpath + root_text[dep_match.end():]
            root_gradle.write_text(root_text)
    settings.write_text(settings_text)

    if plugin_id not in app_text:
        app_plugins = re.search(r"(?m)^plugins\s*\{", app_text)
        if app_plugins:
            if app_gradle.suffix == ".kts":
                line = f'    id("{plugin_id}")'
            else:
                line = f"    id '{plugin_id}'"
            app_text = insert_after_plugins_open(app_text, line)
        else:
            if app_gradle.suffix == ".kts":
                app_text += f'\napply(plugin = "{plugin_id}")\n'
            else:
                app_text += f"\napply plugin: '{plugin_id}'\n"
        app_gradle.write_text(app_text)
    return f"Configured {plugin_id} {PLUGIN_VERSION} in {settings.name} and {app_gradle.name}"


def main() -> None:
    if not CONFIG_SOURCE.is_file():
        raise FileNotFoundError(f"Missing Firebase config: {CONFIG_SOURCE}")
    config = json.loads(CONFIG_SOURCE.read_text())
    clients = config.get("client", [])
    package_names = {
        c.get("client_info", {}).get("android_client_info", {}).get("package_name")
        for c in clients
    }
    if EXPECTED_PACKAGE not in package_names:
        raise ValueError(
            f"Firebase package mismatch. Expected {EXPECTED_PACKAGE}, got {sorted(str(x) for x in package_names)}"
        )

    app_dir = ANDROID / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_SOURCE, app_dir / "google-services.json")
    print(configure_plugin())
    print(f"Copied Firebase configuration to {app_dir / 'google-services.json'}")


if __name__ == "__main__":
    main()
