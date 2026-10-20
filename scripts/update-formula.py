#!/usr/bin/env python3
"""Point Formula/soniccraft.rb at a SonicCraft release.

For each release archive URL in the formula, the script sets the release version and puts that archive's
SHA-256 from the release's SHA256SUMS on the `sha256` line that follows the URL. Everything else in the
formula is left as it is, so the formula stays the source of truth and the script only edits those lines.

    scripts/update-formula.py                      # check the current version's checksums, rewrite if needed
    scripts/update-formula.py --version 0.2.0      # point the formula at v0.2.0
    scripts/update-formula.py --version 0.2.0 --only-if-newer --verify
    scripts/update-formula.py --check              # exit 1 (and print a diff) if the formula is out of date

--verify downloads every archive and checks it against SHA256SUMS before anything is written.
In GitHub Actions, the result is also written to $GITHUB_OUTPUT (old-version, new-version, changed).
Python 3.9 or newer, standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY = "user-github-me/soniccraft"
# The archives the formula installs: the default (mp3) builds. Keep in sync with the on_* blocks.
TARGETS = (
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "aarch64-unknown-linux-gnu",
    "x86_64-unknown-linux-gnu",
)
VERSION_RE = r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?"
URL_RE = re.compile(
    r'^(?P<indent>[ \t]*)url "https://github\.com/(?P<repo>[^/"]+/[^/"]+)/releases/download/'
    rf'v(?P<version>{VERSION_RE})/soniccraft-v(?P=version)-(?P<target>[0-9A-Za-z_.-]+)\.tar\.gz"[ \t]*$'
)
SHA256_RE = re.compile(r'^(?P<indent>[ \t]*)sha256 "(?P<sha256>[0-9a-f]{64})"[ \t]*$')
VERSION_LINE_RE = re.compile(rf'^(?P<indent>[ \t]*)version "(?P<version>{VERSION_RE})"[ \t]*$')
USER_AGENT = "homebrew-soniccraft-update-formula"


class UpdateError(Exception):
    pass


def semver_key(version: str) -> tuple:
    """Sort key for MAJOR.MINOR.PATCH[-PRERELEASE] (SemVer 2.0 precedence, build metadata not supported)."""
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z.-]+))?", version)
    if not match:
        raise UpdateError(f"not a version: {version!r} (expected MAJOR.MINOR.PATCH[-PRERELEASE])")
    major, minor, patch, pre = match.groups()
    core = (int(major), int(minor), int(patch))
    if pre is None:
        return core + (1, ())
    # Numeric identifiers sort before alphanumeric ones, and numerically among themselves.
    idents = tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in pre.split("."))
    return core + (0, idents)


def fetch(url: str, attempts: int = 4) -> bytes:
    """GET a URL (following redirects), retrying transient failures with backoff."""
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise UpdateError(f"{url}: 404 Not Found") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
        if attempt < attempts:
            time.sleep(2**attempt)
    raise UpdateError(f"{url}: {last_error}")


def release_url(repo: str, version: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/v{version}/{name}"


def archive_name(version: str, target: str) -> str:
    return f"soniccraft-v{version}-{target}.tar.gz"


def parse_sums(text: str) -> dict[str, str]:
    """Parse `sha256sum` output: "<hex>  <name>" or "<hex> *<name>" per line."""
    sums = {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](\S+)", line)
        if not match:
            raise UpdateError(f"SHA256SUMS line {number} is not '<sha256>  <file>': {line!r}")
        sums[match.group(2)] = match.group(1).lower()
    return sums


def formula_version(text: str) -> tuple[str, str]:
    """The release version and repository that the formula's archive URLs point at."""
    found = {(m.group("version"), m.group("repo")) for m in map(URL_RE.match, text.splitlines()) if m}
    if not found:
        raise UpdateError("no release archive URLs found in the formula")
    if len(found) > 1:
        raise UpdateError(f"the formula's URLs disagree: {sorted(found)}")
    return found.pop()


def rewrite(text: str, version: str, sums: dict[str, str], repo: str) -> str:
    """Return the formula with every archive URL, its sha256 line and any version line set to `version`."""
    lines = text.splitlines(keepends=True)
    seen = []
    index = 0
    while index < len(lines):
        line = lines[index]
        version_line = VERSION_LINE_RE.match(line.rstrip("\n"))
        if version_line:
            lines[index] = f'{version_line.group("indent")}version "{version}"\n'
        url = URL_RE.match(line.rstrip("\n"))
        if not url:
            index += 1
            continue
        target = url.group("target")
        if target not in TARGETS:
            raise UpdateError(f"line {index + 1}: unexpected target {target!r} (known: {', '.join(TARGETS)})")
        if url.group("repo") != repo:
            raise UpdateError(f"line {index + 1}: URL points at {url.group('repo')}, expected {repo}")
        name = archive_name(version, target)
        if name not in sums:
            raise UpdateError(f"SHA256SUMS of v{version} has no {name}")
        sha_index = index + 1
        while sha_index < len(lines) and not lines[sha_index].strip():
            sha_index += 1
        sha = SHA256_RE.match(lines[sha_index].rstrip("\n")) if sha_index < len(lines) else None
        if not sha:
            raise UpdateError(f"line {index + 1}: the URL of {target} is not followed by a sha256 line")
        lines[index] = f'{url.group("indent")}url "{release_url(repo, version, name)}"\n'
        lines[sha_index] = f'{sha.group("indent")}sha256 "{sums[name]}"\n'
        seen.append(target)
        index = sha_index + 1
    missing = [target for target in TARGETS if target not in seen]
    duplicates = sorted({target for target in seen if seen.count(target) > 1})
    if missing or duplicates:
        raise UpdateError(f"the formula must have one URL per target; missing {missing}, repeated {duplicates}")
    return "".join(lines)


def verify_archives(repo: str, version: str, sums: dict[str, str]) -> None:
    for target in TARGETS:
        name = archive_name(version, target)
        digest = hashlib.sha256(fetch(release_url(repo, version, name))).hexdigest()
        if digest != sums[name]:
            raise UpdateError(f"{name}: downloaded SHA-256 {digest} does not match SHA256SUMS {sums[name]}")
        print(f"verified {name} {digest}")


def github_output(**values: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--formula", type=Path, default=root / "Formula" / "soniccraft.rb")
    parser.add_argument("--version", help="release version, e.g. 0.2.0 or v0.2.0 (default: the formula's)")
    parser.add_argument("--sums", type=Path, help="read SHA256SUMS from this file instead of the release")
    parser.add_argument("--only-if-newer", action="store_true", help="leave the formula alone unless newer")
    parser.add_argument("--verify", action="store_true", help="download each archive and check its SHA-256")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if the formula would change")
    args = parser.parse_args(argv)

    text = args.formula.read_text(encoding="utf-8")
    current, repo = formula_version(text)
    if repo != REPOSITORY:
        raise UpdateError(f"the formula's URLs point at {repo}, expected {REPOSITORY}")
    version = (args.version or current).removeprefix("v")
    semver_key(version)  # rejects anything that is not MAJOR.MINOR.PATCH[-PRERELEASE]

    if args.only_if_newer and semver_key(version) <= semver_key(current):
        print(f"soniccraft {current} is up to date (requested {version})")
        github_output(**{"old-version": current, "new-version": current, "changed": "false"})
        return 0

    if args.sums:
        sums_text = args.sums.read_text(encoding="utf-8")
    else:
        sums_text = fetch(release_url(repo, version, "SHA256SUMS")).decode("utf-8")
    sums = parse_sums(sums_text)
    updated = rewrite(text, version, sums, repo)
    if args.verify:
        verify_archives(repo, version, sums)

    changed = updated != text
    if args.check:
        if changed:
            sys.stdout.writelines(
                difflib.unified_diff(
                    text.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    f"a/{args.formula.name}",
                    f"b/{args.formula.name} (v{version})",
                )
            )
            print(f"{args.formula} is out of date for v{version}", file=sys.stderr)
            return 1
        print(f"{args.formula} matches the SHA256SUMS of v{version}")
        return 0

    if changed:
        args.formula.write_text(updated, encoding="utf-8")
        print(f"soniccraft {current} -> {version}: updated {args.formula}")
    else:
        print(f"soniccraft {version}: {args.formula} already matches SHA256SUMS")
    for target in TARGETS:
        name = archive_name(version, target)
        print(f"  {sums[name]}  {name}")
    github_output(**{"old-version": current, "new-version": version, "changed": str(changed).lower()})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except UpdateError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
