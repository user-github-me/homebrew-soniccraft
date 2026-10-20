# Homebrew tap for SonicCraft

[![tests](https://github.com/user-github-me/homebrew-soniccraft/actions/workflows/tests.yml/badge.svg)](https://github.com/user-github-me/homebrew-soniccraft/actions/workflows/tests.yml)

[SonicCraft](https://github.com/user-github-me/soniccraft) compiles declarative YAML or JSON audio timelines
(TTS speech, music beds, sound effects) into ducked, loudness-mastered audio with matching subtitles. It
ships as a CLI and an MCP server. This tap installs its prebuilt release binaries on macOS and Linux.

## Install

```sh
brew install user-github-me/soniccraft/soniccraft
```

Since Homebrew 6, formulae from taps outside Homebrew load only when you trust them. Installing by the full
name trusts just this formula ([Tap Trust](https://docs.brew.sh/Tap-Trust)). To use the short name:

```sh
brew tap user-github-me/soniccraft
brew trust --formula user-github-me/soniccraft/soniccraft
brew install soniccraft
```

In a `Brewfile`:

```ruby
tap "user-github-me/soniccraft"
brew "user-github-me/soniccraft/soniccraft", trusted: true
```

Then:

```sh
soniccraft --version
soniccraft init demo                            # a starter timeline and royalty-free demo assets
soniccraft render demo/timeline.yaml            # mastered audio and subtitles
claude mcp add soniccraft -- soniccraft mcp     # register the MCP server with Claude Code
```

`brew upgrade soniccraft` picks up new releases once the tap has them (see [Updates](#updates)).

## What it installs

| Path | Contents |
|---|---|
| `bin/soniccraft` | the CLI; `soniccraft mcp` runs the MCP server |
| `bin/soniccraft-mcp` | the same MCP server, for clients that cannot pass arguments |
| `$(brew --prefix soniccraft)/` | `README.md`, `CHANGELOG.md`, `LICENSE-MIT`, `LICENSE-APACHE`, `THIRD-PARTY-LICENSES.txt` and `licenses/` |

The formula downloads the default release archive, `soniccraft-v<version>-<target>.tar.gz`, from the
[project's GitHub releases](https://github.com/user-github-me/soniccraft/releases), and Homebrew checks it
against the SHA-256 that the formula copies from the release's `SHA256SUMS`. Nothing is compiled.

| Platform | Archive |
|---|---|
| macOS on Apple silicon (macOS 11 or newer) | `aarch64-apple-darwin` |
| macOS on Intel (macOS 11 or newer) | `x86_64-apple-darwin` |
| Linux x86_64 (glibc 2.35 or newer) | `x86_64-unknown-linux-gnu` |
| Linux arm64 (glibc 2.35 or newer) | `aarch64-unknown-linux-gnu` |

Good to know:

- **ffmpeg is optional, so it is not a dependency.** soniccraft encodes wav, mp3 and flac itself. ogg, opus
  and m4a output, and input formats it cannot decode itself, need `ffmpeg` on `PATH`:
  `brew install ffmpeg`. Homebrew's ffmpeg brings more than a dozen other formulae, which most timelines
  never use.
- **Developer tools are needed, though nothing is built.** The tap ships no bottles, and Homebrew treats a
  formula without a bottle as a source build: it wants the Xcode Command Line Tools on macOS, or gcc or
  clang on Linux. Homebrew's install script sets these up. If `brew install` says the formula "must be
  built from source", run `xcode-select --install` (macOS) or install `build-essential` (Debian, Ubuntu).
- **Intel Macs** have been a [Tier 3](https://docs.brew.sh/Support-Tiers) Homebrew platform since
  September 2026. The formula still installs the `x86_64-apple-darwin` build, and CI still tests it.

## Licenses

SonicCraft is MIT OR Apache-2.0. The default release builds that this tap installs statically link the LAME
MP3 encoder (LGPL-2.0-or-later) through the mp3lame crates (LGPL-3.0-only), so the formula declares
`(MIT OR Apache-2.0) AND LGPL-2.0-or-later AND LGPL-3.0-only`, and Homebrew applies
[`HOMEBREW_FORBIDDEN_LICENSES`](https://docs.brew.sh/Licence-Guidelines#specifying-forbidden-licences) to it.
The license texts, and how to rebuild with a modified LAME, are in `$(brew --prefix soniccraft)/licenses/`.
For a build without LGPL code, use the `-no-mp3` release archives, or build from source with
`cargo install --locked --path crates/soniccraft-cli --no-default-features` (mp3 output then goes through
ffmpeg).

The tap itself (formula, scripts and workflows) is MIT licensed: see [LICENSE](LICENSE).

## Updates

[`update.yml`](.github/workflows/update.yml) runs every day at 06:41 UTC, and on demand:

1. It asks GitHub for the latest published release of `user-github-me/soniccraft`. Drafts and pre-releases
   are never the latest release.
2. If that release is newer than the formula, [`scripts/update-formula.py`](scripts/update-formula.py)
   sets the new version in the four archive URLs, takes their `sha256` values from the release's
   `SHA256SUMS`, and downloads each archive to check it against those values.
3. [`tests.yml`](.github/workflows/tests.yml) installs and tests the rewritten formula on all four platforms.
4. Only if every test passes is the change committed as `soniccraft <version>` and pushed to `main`.

It needs nothing but the repository's own `GITHUB_TOKEN`: the release is public and the push goes to this
repository. To run it now, or to point the formula at a specific release:

```sh
gh workflow run update.yml --repo user-github-me/homebrew-soniccraft
gh workflow run update.yml --repo user-github-me/homebrew-soniccraft -f version=0.2.0
```

The script also runs locally (Python 3.9 or newer, standard library only):

```sh
scripts/update-formula.py --version 0.2.0 --verify   # rewrite Formula/soniccraft.rb for v0.2.0
scripts/update-formula.py --check                    # exit 1 if the formula doesn't match its SHA256SUMS
```

Two GitHub rules apply:

- GitHub disables scheduled workflows in a public repository after 60 days without activity. If that
  happens, enable `update` again in the Actions tab, or run it once by hand.
- Pushes made with `GITHUB_TOKEN` start no workflow runs, so a version-bump commit has no `tests` run of its
  own. Its tests are the `test` jobs of the `update` run that pushed it.

## Tests

[`tests.yml`](.github/workflows/tests.yml) runs on every push to `main`, on every pull request and on
demand:

| Runner | Archive tested |
|---|---|
| `macos-latest` (macOS 26, Apple silicon) | `aarch64-apple-darwin` |
| `macos-15-intel` | `x86_64-apple-darwin` |
| `ubuntu-latest` (Ubuntu 24.04) | `x86_64-unknown-linux-gnu` |
| `ubuntu-24.04-arm` | `aarch64-unknown-linux-gnu` |

Each job sets up Homebrew with [setup-homebrew](https://github.com/Homebrew/actions/tree/main/setup-homebrew),
which taps and trusts this checkout, installs the formula, and runs `brew test`, `brew linkage --test` and
`brew audit --strict --online`. The formula's test checks both binaries' versions, renders a mock-voice
timeline to WAV with subtitles, and completes an MCP `initialize` handshake. The Linux x86_64 job also runs
`brew style` on the whole tap, `brew readall` and `brew audit --strict` for every OS and architecture, and
`brew livecheck`.
A separate job checks every URL and `sha256` against the release, and checks that the update script
turns an older formula back into this one.

## Working on the formula

Homebrew only loads formulae from taps, so edit the tapped copy:

```sh
brew tap user-github-me/soniccraft
brew trust user-github-me/soniccraft
cd "$(brew --repository user-github-me/soniccraft)"
# edit Formula/soniccraft.rb, then:
brew install --formula --verbose user-github-me/soniccraft/soniccraft   # brew reinstall after more edits
brew test user-github-me/soniccraft/soniccraft
brew audit --strict --online user-github-me/soniccraft/soniccraft
brew style user-github-me/soniccraft
```
