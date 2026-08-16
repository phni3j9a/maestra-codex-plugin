#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

EXPECTED_SKILLS = {"using-maestra", "doctor", "spec", "plan", "run", "gate", "finish"}
ALLOWED_CATEGORIES = {
    "Productivity",
    "Creativity",
    "Developer Tools",
    "Business & Operations",
    "Data & Analytics",
    "Communication",
    "Education & Research",
    "Security",
    "Finance",
    "Healthcare",
    "Travel",
    "Entertainment",
    "Other",
}
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
AT_MENTION_RE = re.compile(r"(?<![\w.-])@[A-Za-z0-9_]", re.UNICODE)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_json_object(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Missing JSON file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid JSON at {path}: {exc}") from exc
    require(isinstance(data, dict), f"JSON root must be an object: {path}")
    return data


def require_text(
    value: Any,
    field: str,
    *,
    max_length: int,
    single_line: bool = False,
) -> str:
    require(isinstance(value, str), f"{field} must be a string")
    require(bool(value.strip()), f"{field} must be non-empty")
    require(len(value) <= max_length, f"{field} exceeds {max_length} characters ({len(value)})")
    require(CONTROL_RE.search(value) is None, f"{field} contains unsupported control characters")
    if single_line:
        require("\n" not in value and "\r" not in value, f"{field} must fit on one line")
    return value


def normalized_prompt(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _srgb_luminance_component(value: int) -> float:
    component = value / 255.0
    return component / 12.92 if component <= 0.04045 else math.pow((component + 0.055) / 1.055, 2.4)


def luminance(color: str) -> float:
    red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    return (
        0.2126 * _srgb_luminance_component(red)
        + 0.7152 * _srgb_luminance_component(green)
        + 0.0722 * _srgb_luminance_component(blue)
    )


def contrast_ratio(left: str, right: str) -> float:
    lighter, darker = sorted((luminance(left), luminance(right)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"SKILL.md is not valid UTF-8: {path}") from exc
    require(text.startswith("---\n"), f"SKILL.md must start with YAML front matter: {path}")
    closing = text.find("\n---\n", 4)
    require(closing != -1, f"SKILL.md front matter is not closed: {path}")
    frontmatter: dict[str, str] = {}
    for line_number, raw in enumerate(text[4:closing].splitlines(), start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        require(":" in raw, f"Malformed front matter at {path}:{line_number}")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        require(key and value, f"Empty front matter field at {path}:{line_number}")
        require(key not in frontmatter, f"Duplicate front matter key {key!r}: {path}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        frontmatter[key] = value
    body = text[closing + len("\n---\n") :]
    require(bool(body.strip()), f"Skill body must be non-empty: {path}")
    return frontmatter, body


def parse_simple_two_level_yaml(path: Path) -> dict[str, Any]:
    """Parse Maestra's deliberately tiny agents/openai.yaml shape without runtime dependencies."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValidationError(f"Agent metadata is not valid UTF-8: {path}") from exc
    result: dict[str, Any] = {}
    current: str | None = None
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        require(indent in {0, 2}, f"Unsupported YAML indentation at {path}:{line_number}")
        stripped = raw.strip()
        require(":" in stripped, f"Malformed YAML at {path}:{line_number}")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if indent == 0:
            require(not raw_value, f"Top-level YAML field must be a mapping at {path}:{line_number}")
            require(key not in result, f"Duplicate top-level YAML field {key!r}: {path}")
            result[key] = {}
            current = key
            continue
        require(current is not None and isinstance(result.get(current), dict), f"Nested YAML field has no parent: {path}:{line_number}")
        require(bool(raw_value), f"Empty YAML scalar at {path}:{line_number}")
        if raw_value in {"true", "false"}:
            value: Any = raw_value == "true"
        elif len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Malformed quoted YAML scalar at {path}:{line_number}: {exc}") from exc
        elif len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == "'":
            value = raw_value[1:-1].replace("''", "'")
        else:
            value = raw_value
        mapping = result[current]
        require(key not in mapping, f"Duplicate YAML field {current}.{key}: {path}")
        mapping[key] = value
    return result


def validate_manifest(plugin_root: Path) -> dict[str, Any]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = load_json_object(manifest_path)

    name = require_text(manifest.get("name"), "name", max_length=64, single_line=True)
    require(PLUGIN_NAME_RE.fullmatch(name) is not None, "name must use ASCII letters, digits, '_' or '-' and start alphanumeric")
    version = require_text(manifest.get("version"), "version", max_length=64, single_line=True)
    require(SEMVER_RE.fullmatch(version) is not None, "version must be semantic versioning")
    require_text(manifest.get("description"), "description", max_length=1024)

    author = manifest.get("author")
    require(isinstance(author, dict), "author must be an object")
    author_name = require_text(author.get("name"), "author.name", max_length=120)

    interface = manifest.get("interface")
    require(isinstance(interface, dict), "interface must be an object")
    require_text(interface.get("displayName"), "interface.displayName", max_length=30, single_line=True)
    require_text(interface.get("shortDescription"), "interface.shortDescription", max_length=30, single_line=True)
    require_text(interface.get("longDescription"), "interface.longDescription", max_length=4000)
    developer = require_text(interface.get("developerName"), "interface.developerName", max_length=80, single_line=True)
    require(developer == author_name, "interface.developerName must match author.name for this release")

    category = interface.get("category", "Other")
    require(isinstance(category, str) and category in ALLOWED_CATEGORIES, f"Unknown interface.category: {category!r}")

    capabilities = interface.get("capabilities", [])
    require(isinstance(capabilities, list), "interface.capabilities must be a list")
    require(len(capabilities) <= 20, "interface.capabilities may contain at most 20 entries")
    for index, capability in enumerate(capabilities):
        require_text(capability, f"interface.capabilities[{index}]", max_length=120, single_line=True)

    prompts = interface.get("defaultPrompt", [])
    if isinstance(prompts, str):
        prompts = [prompts]
    require(isinstance(prompts, list), "interface.defaultPrompt must be a string or list of strings")
    require(len(prompts) <= 3, "interface.defaultPrompt may contain at most three prompts")
    normalized: set[str] = set()
    for index, prompt in enumerate(prompts):
        prompt = require_text(prompt, f"interface.defaultPrompt[{index}]", max_length=128, single_line=True)
        require(AT_MENTION_RE.search(prompt) is None, f"interface.defaultPrompt[{index}] must not contain an @mention")
        key = normalized_prompt(prompt)
        require(key not in normalized, "interface.defaultPrompt entries must be unique")
        normalized.add(key)

    for field, background, minimum in (("brandColor", "#FFFFFF", 2.0), ("brandColorDark", "#212121", 2.0)):
        value = interface.get(field)
        if value is None:
            continue
        require(isinstance(value, str) and HEX_COLOR_RE.fullmatch(value) is not None, f"interface.{field} must be a six-digit hex color")
        ratio = contrast_ratio(value, background)
        require(ratio >= minimum, f"interface.{field} contrast is {ratio:.2f}:1; requires at least {minimum}:1")

    require(manifest.get("skills") == "./skills/", "skills must be exactly './skills/'")
    require((plugin_root / "skills").is_dir(), "Declared skills directory is missing")

    generic = load_json_object(plugin_root / "plugin.json")
    for key in ("name", "version", "description"):
        require(generic.get(key) == manifest.get(key), f"plugin.json {key} must match .codex-plugin/plugin.json")
    require(generic.get("author", {}).get("name") == author_name, "plugin.json author.name must match")

    return {
        "name": name,
        "version": version,
        "display_name": interface["displayName"],
        "short_description_length": len(interface["shortDescription"]),
        "default_prompts": len(prompts),
        "brand_color_contrast": round(contrast_ratio(interface["brandColor"], "#FFFFFF"), 2) if interface.get("brandColor") else None,
    }


def validate_skills(plugin_root: Path, plugin_name: str) -> list[dict[str, Any]]:
    skills_root = plugin_root / "skills"
    actual = {path.name for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")}
    require(actual == EXPECTED_SKILLS, f"Expected Skills {sorted(EXPECTED_SKILLS)}, found {sorted(actual)}")
    seen_names: set[str] = set()
    result: list[dict[str, Any]] = []
    for directory_name in sorted(actual):
        skill_dir = skills_root / directory_name
        require(not skill_dir.is_symlink(), f"Skill directory may not be a symlink: {skill_dir}")
        manifest_path = skill_dir / "SKILL.md"
        require(manifest_path.is_file() and not manifest_path.is_symlink(), f"Missing regular SKILL.md: {manifest_path}")
        frontmatter, body = parse_frontmatter(manifest_path)
        name = require_text(frontmatter.get("name"), f"{directory_name}.name", max_length=64, single_line=True)
        require(SKILL_NAME_RE.fullmatch(name) is not None, f"Unsupported Skill name: {name!r}")
        require(name == directory_name, f"Skill name {name!r} must match directory {directory_name!r}")
        require(name not in seen_names, f"Duplicate Skill name: {name}")
        seen_names.add(name)
        description = require_text(frontmatter.get("description"), f"{name}.description", max_length=1024)
        require(len(f"{plugin_name}:{name}") <= 64, f"Combined Skill identity exceeds 64 characters: {plugin_name}:{name}")

        agent_path = skill_dir / "agents" / "openai.yaml"
        require(agent_path.is_file() and not agent_path.is_symlink(), f"Missing regular agents/openai.yaml: {agent_path}")
        metadata = parse_simple_two_level_yaml(agent_path)
        require(set(metadata).issubset({"interface", "policy", "dependencies"}), f"Unsupported top-level agent metadata key in {agent_path}")
        agent_interface = metadata.get("interface")
        require(isinstance(agent_interface, dict), f"interface mapping is required: {agent_path}")
        require_text(agent_interface.get("display_name"), f"{name}.interface.display_name", max_length=80, single_line=True)
        require_text(agent_interface.get("short_description"), f"{name}.interface.short_description", max_length=240, single_line=True)
        if "default_prompt" in agent_interface:
            require_text(agent_interface["default_prompt"], f"{name}.interface.default_prompt", max_length=512, single_line=True)
        policy = metadata.get("policy")
        require(isinstance(policy, dict), f"policy mapping is required: {agent_path}")
        require(set(policy).issubset({"products", "allow_implicit_invocation"}), f"Unsupported policy field: {agent_path}")
        require(policy.get("allow_implicit_invocation") is False, f"{name} must set allow_implicit_invocation: false")

        result.append({
            "name": name,
            "description_length": len(description),
            "body_characters": len(body),
            "explicit_only": True,
        })
    return result


def validate_tree(plugin_root: Path) -> None:
    require(plugin_root.is_dir(), f"Plugin root does not exist: {plugin_root}")
    require((plugin_root / "README.md").is_file(), "Plugin README.md is required")
    require((plugin_root / "LICENSE").is_file(), "Plugin LICENSE is required")
    for path in plugin_root.rglob("*"):
        require(not path.is_symlink(), f"Plugin release may not contain symlinks: {path}")
        if path.is_file():
            require(path.stat().st_size <= 100 * 1024 * 1024, f"Plugin member exceeds 100 MiB: {path}")


def validate_plugin(plugin_root: Path) -> dict[str, Any]:
    plugin_root = plugin_root.expanduser().resolve()
    validate_tree(plugin_root)
    manifest = validate_manifest(plugin_root)
    skills = validate_skills(plugin_root, manifest["name"])
    return {
        "status": "pass",
        "plugin_root": str(plugin_root),
        "manifest": manifest,
        "skills": skills,
        "skill_count": len(skills),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Maestra against Codex skills-only plugin constraints")
    parser.add_argument("plugin_root", nargs="?", default=str(Path(__file__).resolve().parents[1] / "plugins" / "maestra"))
    args = parser.parse_args()
    try:
        result = validate_plugin(Path(args.plugin_root))
    except ValidationError as exc:
        print(f"validate-plugin: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
