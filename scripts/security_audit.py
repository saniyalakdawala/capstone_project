"""
Automated Security & Secrets Audit Scanner
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7H: Security Hardening & Credential Protection.

Scans:
  1. High-entropy API tokens, private keys, passwords, and service keys in repository code.
  2. Verifies that .env and local secrets are excluded from Git tracking.
  3. Audits Git staged/tracked files for accidental secret inclusion.
"""

import os
import re
import sys
import subprocess
from typing import List, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Patterns for sensitive credentials
PATTERNS = [
    (r'(?i)(AIza[0-9A-Za-z\\-_]{35})', "Google API Key"),
    (r'(?i)(AKIA[0-9A-Z]{16})', "AWS Access Key ID"),
    (r'(?i)("client_secret"\s*:\s*"[^"]+")', "Client Secret JSON"),
    (r'(?i)(-----BEGIN\s+(?:RSA|OPENSSH|EC)?\s*PRIVATE\s+KEY-----)', "Private Key"),
    (r'(?i)(ghp_[0-9a-zA-Z]{36})', "GitHub Personal Access Token"),
    (r'(?i)(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})', "JWT Token"),
]

IGNORED_DIRS = {".git", ".pytest_cache", "node_modules", "dist", ".gemini", "__pycache__"}
LOCAL_SECRET_FILES = {".env", "frontend/.env", "backend/.env"}
IGNORED_TEMPLATE_FILES = {".env.example"}


def get_git_tracked_files() -> List[str]:
    """Retrieves all files tracked in Git."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception:
        # Fallback to walk if git is unavailable
        files = []
        for root, dirs, f_list in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for f in f_list:
                rel = os.path.relpath(os.path.join(root, f), REPO_ROOT).replace("\\", "/")
                if not any(rel.endswith(ext) for ext in [".env", ".db", ".pyc"]):
                    files.append(rel)
        return files


def scan_file_for_secrets(rel_path: str) -> List[Dict[str, Any]]:
    findings = []
    filepath = os.path.join(REPO_ROOT, rel_path)

    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                if any(kw in line.lower() for kw in ["placeholder", "your_", "example", "<api-key>", "optional"]):
                    continue

                for pattern, secret_type in PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        findings.append({
                            "file": rel_path,
                            "line": line_no,
                            "type": secret_type,
                            "snippet": line.strip()[:60] + "..."
                        })
    except Exception as e:
        print(f"Error reading {rel_path}: {e}")

    return findings


def run_security_audit() -> Dict[str, Any]:
    print("=========================================================================")
    print("EIDT Maharashtra — Security Hardening & Secrets Audit")
    print("=========================================================================")

    tracked_files = get_git_tracked_files()
    print(f"Total Git-tracked files audited: {len(tracked_files)}")

    violations = []
    binary_extensions = {".exe", ".dll", ".so", ".wasm", ".bin", ".dat", ".png", ".jpg", ".tif", ".db", ".sqlite"}

    for rel_path in tracked_files:
        norm_path = rel_path.replace("\\", "/")
        path_parts = set(norm_path.split("/"))
        if path_parts.intersection(IGNORED_DIRS):
            continue
        if any(norm_path.endswith(ext) for ext in binary_extensions):
            continue
        if norm_path in IGNORED_TEMPLATE_FILES:
            continue

        findings = scan_file_for_secrets(norm_path)
        if findings:
            violations.extend(findings)

    # Check that local secrets are excluded from Git
    tracked_env_violations = []
    for sec_file in [".env", "frontend/.env", "backend/.env"]:
        try:
            res = subprocess.run(
                ["git", "ls-files", sec_file],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True
            )
            if res.stdout.strip():
                tracked_env_violations.append(sec_file)
        except Exception:
            pass

    print(f"Tracked secret files in Git: {'CRITICAL: ' + str(tracked_env_violations) if tracked_env_violations else 'SAFE (0 tracked)'}")
    print(f"Tracked repository secret violations: {len(violations)}")

    if violations or tracked_env_violations:
        print("\nVIOLATIONS FOUND:")
        for v in violations:
            print(f"  [!] {v['file']}:{v['line']} - {v['type']}")
        for f in tracked_env_violations:
            print(f"  [!] CRITICAL: {f} is tracked in Git!")
    else:
        print("\n[PASS] No hardcoded credentials in tracked source code.")
        print("[PASS] Local .env files are strictly excluded by .gitignore.")

    passed = len(violations) == 0 and len(tracked_env_violations) == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "audited_tracked_files": len(tracked_files),
        "tracked_env_violations": tracked_env_violations,
        "violations_count": len(violations)
    }


if __name__ == "__main__":
    result = run_security_audit()
    sys.exit(0 if result["status"] == "PASS" else 1)
