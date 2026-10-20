class Soniccraft < Formula
  desc "Declarative multi-track audio engine for AI agents"
  homepage "https://github.com/user-github-me/soniccraft"
  # SonicCraft itself is MIT OR Apache-2.0. These are the default (mp3) release builds, which statically
  # link the LAME MP3 encoder (LGPL-2.0-or-later) through the mp3lame crates (LGPL-3.0-only).
  license all_of: [
    { any_of: ["MIT", "Apache-2.0"] },
    "LGPL-2.0-or-later",
    "LGPL-3.0-only",
  ]

  # Release tags are pushed before their draft release is reviewed and published, so the newest tag can
  # have no downloads yet: follow the latest published release, as scripts/update-formula.py does.
  livecheck do
    url :stable
    strategy :github_latest
  end

  # scripts/update-formula.py rewrites these URLs and checksums from the release's SHA256SUMS.
  on_macos do
    on_arm do
      url "https://github.com/user-github-me/soniccraft/releases/download/v0.1.0/soniccraft-v0.1.0-aarch64-apple-darwin.tar.gz"
      sha256 "8a6e0a992573436a645d23b09c5fd3be8e794897a11362034d066b23a1fa5ac7"
    end
    on_intel do
      url "https://github.com/user-github-me/soniccraft/releases/download/v0.1.0/soniccraft-v0.1.0-x86_64-apple-darwin.tar.gz"
      sha256 "bd926e0308fd3d4933261fc96956fbc83f468f6dc70c5d1712f375cca2dd4775"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/user-github-me/soniccraft/releases/download/v0.1.0/soniccraft-v0.1.0-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "94a7d31e3c045554e4a456c704ef5983b24777b02a569dab17245972309e0e0d"
    end
    on_intel do
      url "https://github.com/user-github-me/soniccraft/releases/download/v0.1.0/soniccraft-v0.1.0-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "cdd6de8af10e47b7b9c40da2e9c0bdc723effd039e172384c2aa49b131615293"
    end
  end

  def install
    bin.install "soniccraft", "soniccraft-mcp"
    # Homebrew moves README.md, CHANGELOG.md, LICENSE-MIT and LICENSE-APACHE into the prefix by itself.
    # The LGPL also requires LAME's license texts (licenses/) to accompany the binaries.
    prefix.install "THIRD-PARTY-LICENSES.txt", "licenses"
  end

  def caveats
    <<~EOS
      soniccraft writes wav, mp3 and flac without ffmpeg. ogg, opus and m4a output, and
      less common input formats, need ffmpeg on PATH:
        brew install ffmpeg

      These binaries statically link the LAME MP3 encoder (LGPL). Its license texts and
      the licenses of every bundled crate are in:
        #{opt_prefix}
    EOS
  end

  test do
    assert_match "soniccraft #{version}", shell_output("#{bin}/soniccraft --version")
    assert_match "soniccraft-mcp #{version}", shell_output("#{bin}/soniccraft-mcp --version")

    # The built-in mock voice is deterministic and offline: no API keys, network or ffmpeg.
    (testpath/"timeline.yaml").write <<~YAML
      version: "1.0"
      output:
        format: wav
      tracks:
        - id: voice
          type: speech
          sequence:
            - id: hello
              provider: mock
              voice_id: brew
              text: "Hello from Homebrew."
    YAML
    system bin/"soniccraft", "validate", "timeline.yaml"
    system bin/"soniccraft", "render", "timeline.yaml", "--output", "hello.wav", "--subtitles", "--quiet"
    assert_equal "RIFF", File.binread(testpath/"hello.wav", 4)
    assert_equal "WAVE", File.binread(testpath/"hello.wav", 4, 8)
    assert_match "Hello from Homebrew.", (testpath/"hello.vtt").read

    # The MCP server answers an initialize request on stdin and exits at end of input.
    request = {
      jsonrpc: "2.0",
      id:      1,
      method:  "initialize",
      params:  {
        protocolVersion: "2025-06-18",
        capabilities:    {},
        clientInfo:      { name: "homebrew-test", version: version.to_s },
      },
    }
    response = JSON.parse(pipe_output("#{bin}/soniccraft mcp", "#{JSON.generate(request)}\n", 0))
    assert_equal version.to_s, response.dig("result", "serverInfo", "version")
  end
end
