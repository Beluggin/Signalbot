"""
CODE READER - Self-Awareness Module for SignalBot

Lets SignalBot read its own source code. Trigger: "read code" in chat.
Expansion: Edit ALLOWED_ROOTS for broader filesystem access.
Security: Read-only. Binary files listed not read. Sensitive files filtered.
"""

import os
from pathlib import Path
from typing import List, Optional

SIGNALBOT_ROOT = Path(__file__).parent

ALLOWED_ROOTS = [
    SIGNALBOT_ROOT,
    # Future expansion:
    # Path("/home/luggin"),
    # Path("/"),
]

BLOCKED_PATTERNS = [
    ".env", ".git", "__pycache__", "*.pyc", ".venv",
    "node_modules", "*secret*", "*password*", "*api_key*",
    "*.sqlite", "*.db",
]

TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".html", ".css", ".js",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".conf",
    ".sh", ".bash", ".csv", ".xml", ".log",
}

MAX_READ_SIZE = 50000
MAX_TOTAL_CONTEXT = 200000
MAX_DEPTH = 5


def _is_allowed_path(path):
    resolved = path.resolve()
    for root in ALLOWED_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _is_blocked(name):
    name_lower = name.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.startswith("*") and pattern.endswith("*"):
            if pattern[1:-1] in name_lower:
                return True
        elif pattern.startswith("*"):
            if name_lower.endswith(pattern[1:]):
                return True
        elif pattern.endswith("*"):
            if name_lower.startswith(pattern[:-1]):
                return True
        else:
            if name_lower == pattern.lower():
                return True
    return False


def _is_text_file(path):
    return path.suffix.lower() in TEXT_EXTENSIONS


def _human_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def scan_directory(root=None, max_depth=MAX_DEPTH):
    """Scan directory tree and return formatted listing."""
    if root is None:
        root = SIGNALBOT_ROOT
    root = Path(root).resolve()
    if not _is_allowed_path(root):
        return f"[ACCESS DENIED] Path not in allowed roots: {root}"
    if not root.exists():
        return f"[NOT FOUND] {root}"
    lines = []
    _scan_recursive(root, lines, prefix="", depth=0, max_depth=max_depth)
    header = f"Directory: {root}\n{'=' * 50}\n"
    return header + "\n".join(lines)


def _scan_recursive(path, lines, prefix, depth, max_depth):
    if depth > max_depth:
        lines.append(f"{prefix}+-- ... (max depth reached)")
        return
    try:
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        lines.append(f"{prefix}+-- [permission denied]")
        return
    entries = [e for e in entries if not _is_blocked(e.name)]
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = "+-- "
        child_prefix = prefix + ("|   " if not is_last else "    ")
        if entry.is_dir():
            try:
                child_count = len([c for c in entry.iterdir() if not _is_blocked(c.name)])
            except PermissionError:
                child_count = "?"
            lines.append(f"{prefix}{connector}{entry.name}/  ({child_count} items)")
            _scan_recursive(entry, lines, child_prefix, depth + 1, max_depth)
        elif entry.is_file():
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            size_str = _human_size(size)
            ext = entry.suffix.lower()
            if _is_text_file(entry):
                tag = ext[1:] if ext else "text"
                lines.append(f"{prefix}{connector}{entry.name}  ({size_str}) [{tag}]")
            else:
                lines.append(f"{prefix}{connector}{entry.name}  ({size_str}) [binary]")


def read_file(filepath, max_size=MAX_READ_SIZE):
    """Read a file with security checks. Returns contents or error string."""
    path = Path(filepath).resolve()
    if not _is_allowed_path(path):
        return "[ACCESS DENIED] Not within allowed directories."
    if _is_blocked(path.name):
        return "[BLOCKED] This file is in the restricted list."
    if not path.exists():
        return f"[NOT FOUND] {filepath}"
    if not path.is_file():
        return f"[NOT A FILE] {filepath}"
    if not _is_text_file(path):
        size = path.stat().st_size
        return f"[BINARY FILE] {path.name} ({_human_size(size)}) -- cannot display."
    size = path.stat().st_size
    if size > max_size:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_size)
            return (
                f"== {path.name} ({_human_size(size)}) [TRUNCATED to {_human_size(max_size)}] ==\n"
                f"{content}\n"
                f"== [truncated -- {_human_size(size - max_size)} more] =="
            )
        except Exception as e:
            return f"[READ ERROR] {e}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return f"== {path.name} ({_human_size(size)}) ==\n{content}"
    except Exception as e:
        return f"[READ ERROR] {e}"


def read_multiple_files(filepaths, max_total=MAX_TOTAL_CONTEXT):
    """Read multiple files respecting total size budget."""
    results = []
    total_size = 0
    for fp in filepaths:
        if total_size >= max_total:
            results.append("[BUDGET EXCEEDED] Skipping remaining files.")
            break
        remaining = max_total - total_size
        content = read_file(fp, max_size=min(MAX_READ_SIZE, remaining))
        results.append(content)
        total_size += len(content)
    return "\n\n".join(results)


def handle_read_code(user_message):
    """
    Check if user wants to read code. Returns context string or None.

    Supports:
      "read code"            -> full directory tree
      "read code <filename>" -> tree + specific file contents
      "read file <path>"     -> specific file only
    """
    msg = user_message.strip().lower()

    if msg == "read code":
        tree = scan_directory()
        return (
            "[SELF-AWARENESS CONTEXT -- SignalBot Source Code]\n"
            "You are reading your own source code directory. "
            "Use this to accurately describe your architecture, "
            "capabilities, and implementation. Do NOT hallucinate "
            "features that are not in the code.\n\n"
            + tree + "\n\n"
            "You can see the file listing above. If the user asks "
            "about a specific module, refer to what you know about "
            "its purpose from the filenames and structure."
        )

    if msg.startswith("read code "):
        target = user_message.strip()[10:].strip()
        tree = scan_directory()
        candidates = []
        target_lower = target.lower()
        for root_path in ALLOWED_ROOTS:
            for dirpath, _, filenames in os.walk(root_path):
                if _is_blocked(os.path.basename(dirpath)):
                    continue
                for fname in filenames:
                    if _is_blocked(fname):
                        continue
                    if fname.lower() == target_lower or fname.lower().startswith(target_lower):
                        candidates.append(os.path.join(dirpath, fname))
        if not candidates:
            return (
                "[SELF-AWARENESS CONTEXT]\n"
                f"File '{target}' not found in the codebase.\n\n"
                + tree
            )
        best = None
        for c in candidates:
            if os.path.basename(c).lower() == target_lower:
                best = c
                break
        if not best:
            best = candidates[0]
        file_content = read_file(best)
        return (
            "[SELF-AWARENESS CONTEXT -- SignalBot Source Code]\n"
            "You are reading your own source code. Use this to "
            "accurately answer questions about your implementation.\n\n"
            "== DIRECTORY TREE ==\n" + tree + "\n\n"
            "== REQUESTED FILE ==\n" + file_content
        )

    if msg.startswith("read file "):
        filepath = user_message.strip()[10:].strip()
        content = read_file(filepath)
        return "[SELF-AWARENESS CONTEXT]\n" + content

    return None


if __name__ == "__main__":
    print("=== Directory Tree ===")
    print(scan_directory())
    print()
    print("=== Reading own source ===")
    print(read_file(__file__)[:500])
    print("...")
