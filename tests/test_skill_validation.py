"""Schema-driven content validation tests for the motto-skill-registry."""

import os
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


# ---------------------------------------------------------------------------
# Helper: discover direct skill subdirectories
# ---------------------------------------------------------------------------

def _skill_dirs() -> list[Path]:
    """Direct subdirectories under skills/ (excluding hidden and nested subdirs)."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        p for p in SKILLS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def _skill_md_files() -> list[Path]:
    """All SKILL.md files found directly in skill directories."""
    return [
        d / "SKILL.md" for d in _skill_dirs()
        if (d / "SKILL.md").is_file()
    ]


# ---------------------------------------------------------------------------
# 1. Every skill directory must have a SKILL.md
# ---------------------------------------------------------------------------

def test_all_skill_directories_have_skill_md():
    """Check that every direct subdirectory under skills/ contains a SKILL.md file."""
    missing = []
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            missing.append(skill_dir.name)
    assert missing == [], (
        f"Skill directories missing SKILL.md: {', '.join(missing)}"
    )


# ---------------------------------------------------------------------------
# 2. Every SKILL.md must be readable as text
# ---------------------------------------------------------------------------

def test_all_skill_md_files_are_readable():
    """Verify every SKILL.md can be opened and read as UTF-8 text."""
    unreadable = []
    for skill_md in _skill_md_files():
        try:
            content = skill_md.read_text(encoding="utf-8")
            # Also verify we got something back (not just an empty string
            # masked by a successful read).
            if not content:
                unreadable.append(f"{skill_md.parent.name} (empty file)")
        except Exception as exc:
            unreadable.append(f"{skill_md.parent.name}: {exc}")
    assert unreadable == [], (
        f"Unreadable or empty SKILL.md files: {'; '.join(unreadable)}"
    )


# ---------------------------------------------------------------------------
# 3. No duplicate skill names (directory names)
# ---------------------------------------------------------------------------

def test_no_duplicate_skill_names():
    """Ensure no two skill directories share the same name."""
    names = [d.name for d in _skill_dirs()]
    seen = set()
    dupes = set()
    for name in names:
        if name in seen:
            dupes.add(name)
        seen.add(name)
    assert dupes == set(), (
        f"Duplicate skill directory names found: {', '.join(sorted(dupes))}"
    )


# ---------------------------------------------------------------------------
# 4. SKILL.md files must have meaningful (non-empty) content
# ---------------------------------------------------------------------------

def test_skill_md_files_not_empty():
    """Verify every SKILL.md has meaningful content beyond just YAML frontmatter.

    A SKILL.md that contains only a frontmatter block (``--- ... ---``) and
    nothing else is considered empty for the purpose of this test.
    """
    empty_or_stub = []
    for skill_md in _skill_md_files():
        content = skill_md.read_text(encoding="utf-8").strip()
        # Strip YAML frontmatter delimited by ---
        if content.startswith("---"):
            parts = content.split("---", 2)
            # parts[0] is empty (before first ---), parts[1] is the YAML,
            # parts[2] is the body after the closing ---
            if len(parts) >= 3:
                body = parts[2].strip()
            else:
                body = ""
        else:
            body = content

        if not body:
            empty_or_stub.append(skill_md.parent.name)

    assert empty_or_stub == [], (
        f"SKILL.md files with no body content: {', '.join(empty_or_stub)}"
    )


# ---------------------------------------------------------------------------
# 5. SKILL.md structure validation (size bounds)
# ---------------------------------------------------------------------------

def test_skill_structure_is_valid():
    """Validate SKILL.md files are within reasonable size bounds.

    Each SKILL.md must:
    - Not be empty (at least 10 bytes of raw content)
    - Not exceed a generous maximum (200 000 bytes)
    """
    MIN_BYTES = 10
    MAX_BYTES = 200_000
    violations = []
    for skill_md in _skill_md_files():
        size = skill_md.stat().st_size
        if size < MIN_BYTES:
            violations.append(f"{skill_md.parent.name}: {size} B (below {MIN_BYTES} B minimum)")
        elif size > MAX_BYTES:
            violations.append(f"{skill_md.parent.name}: {size} B (exceeds {MAX_BYTES} B maximum)")
    assert violations == [], (
        f"SKILL.md files outside size bounds: {'; '.join(violations)}"
    )


# ---------------------------------------------------------------------------
# 6. Import / smoke test
# ---------------------------------------------------------------------------

def test_import_smoke():
    """Smoke test: verify the skills directory exists and is accessible."""
    assert SKILLS_DIR.is_dir(), (
        f"Skills directory does not exist at {SKILLS_DIR}"
    )
    # Confirm we can list the directory contents
    entries = list(SKILLS_DIR.iterdir())
    assert len(entries) > 0, (
        f"Skills directory at {SKILLS_DIR} is empty"
    )
