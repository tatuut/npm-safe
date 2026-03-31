# npm-safe

Pre-install security gate for npm, pnpm, bun, and yarn. Blocks known-malicious packages **before** they touch your machine.

## Supported Package Managers

| PM | Lockfile | Transitive Dep Check |
|----|----------|---------------------|
| **npm** | package-lock.json | `--package-lock-only` |
| **pnpm** | pnpm-lock.yaml | `--lockfile-only` |
| **bun** | bun.lock (JSONC) | `--lockfile-only` |
| **yarn** (v2+) | yarn.lock | `--mode update-lockfile` |

> Yarn Classic (v1) is **not supported** &mdash; it lacks a lockfile-only mode, making it impossible to pre-check transitive dependencies safely.

## Quick Start

### bash (Git Bash / WSL / macOS / Linux)

```bash
mkdir -p ~/bin
cp safe.sh npm-safe-check.py vuls.json ~/bin/
chmod +x ~/bin/safe.sh

cat >> ~/.bashrc << 'EOF'
alias npm='~/bin/safe.sh npm'
alias pnpm='~/bin/safe.sh pnpm'
alias bun='~/bin/safe.sh bun'
alias yarn='~/bin/safe.sh yarn'
EOF
source ~/.bashrc
```

### PowerShell

```powershell
Copy-Item safe.ps1, npm-safe-check.py, vuls.json $HOME\bin\

Add-Content $PROFILE @'
function npm  { & $HOME\bin\safe.ps1 npm  @args }
function pnpm { & $HOME\bin\safe.ps1 pnpm @args }
function bun  { & $HOME\bin\safe.ps1 bun  @args }
function yarn { & $HOME\bin\safe.ps1 yarn @args }
'@
```

### Requirements

- Python 3.8+ (stdlib only, zero dependencies)
- One of: npm, pnpm, bun, yarn v2+

## How It Works

npm-safe wraps your package manager's `install` / `add` command with a 3-step check:

**Step 1 &mdash; CLI args** &ensp; Scans package names on the command line against a blocklist. Typosquats like `axois` (instead of `axios`) are caught here.

**Step 2 &mdash; Existing files** &ensp; Parses `package.json` and the lockfile for the active PM. Catches compromised versions already in your dependency tree.

**Step 3 &mdash; Transitive dependencies** &ensp; Runs a lockfile-only install (no `node_modules` touched, no scripts executed) to resolve the full dependency tree, then scans the updated lockfile. If a threat is found, the lockfile is rolled back.

### Verdict

| Result | Condition | Action |
|--------|-----------|--------|
| **DANGER** | Matches `dangerous` list or typosquat | **Install blocked** (exit 1) |
| **OK** | Matches `safe` list or not in blocklist | Silent pass |
| **Unverified** | In blocklist but version not yet confirmed | **Interactive prompt** (allow / deny / one-by-one) |

## Threat Examples

The blocklist (`vuls.json`) covers two categories. A few representative entries:

**Compromised legitimate packages** (specific versions only):

| Package | Dangerous | Safe | Type |
|---------|-----------|------|------|
| `axios` | 1.14.1, 0.30.4 | 1.14.0, 0.30.3 | RAT (remote access trojan) |
| `@solana/web3.js` | 1.95.6, 1.95.7 | 1.95.8+ | Private key exfiltration |

**Typosquats** (all versions dangerous):

| Package | Impersonates | Type |
|---------|-------------|------|
| `axois` | axios | Data theft |
| `loadsh` | lodash | Data theft |
| `expres` | express | Backdoor |

See [`vuls.json`](vuls.json) for the full list.

## Adding Threats

Edit `vuls.json` (no code changes needed):

```jsonc
{
  "exact": {
    "compromised-pkg": {
      "dangerous": ["3.2.1"],       // blocked versions
      "safe": ["3.2.0", "3.1.0"],   // verified-safe versions
      "type": "Backdoor",           // anything else -> interactive prompt
      "added": "2026-04-01"
    }
  },
  "all": {
    "typo-pkg": { "type": "Malware", "added": "2026-04-01" }
  }
}
```

## Performance

Lockfile checks are pure parsing &mdash; effectively instant. The only real cost is the transitive dependency resolution step.

| Check | What it does | Time |
|-------|-------------|------|
| package.json | JSON parse + dict lookup | **< 1ms** |
| package-lock.json (1,500 pkgs) | JSON parse + full scan | **~5ms** |
| pnpm-lock.yaml | Regex over text | **~10ms** |
| bun.lock | JSONC parse + packages scan | **~5ms** |
| yarn.lock | Line-by-line parse | **~10ms** |
| Transitive resolution | Lockfile-only install | **~2-8s** |

Total overhead for a typical `install`: **under 10 seconds**, most of which is the lockfile-only resolution that your PM would do anyway.

## Architecture

```
safe.sh / safe.ps1        <- Thin entry point (~20 lines, shared by all PMs)
  └─ npm-safe-check.py    <- All logic: check, interactive prompt, transitive resolution
       └─ vuls.json        <- Blocklist (edit without touching code)
```

| File | Description |
|------|-------------|
| `safe.sh` | bash wrapper &mdash; binds to each PM via alias |
| `safe.ps1` | PowerShell wrapper |
| `npm-safe-check.py` | Core checker: lockfile parsing, interactive prompt, dry-install |
| `vuls.json` | Threat definitions |

## Testing

```bash
python test_check.py
```

43 tests covering: CLI args, package.json, package-lock.json, pnpm-lock.yaml, bun.lock (JSONC), yarn.lock (v1/v2 format), and empty directories.

## Contributing

npm-safe is open source and **community-driven threat intelligence makes it stronger**. We especially welcome contributions to `vuls.json`.

### Report a malicious package

If you discover or hear about a compromised npm package, please [open an issue](../../issues) or submit a PR adding it to `vuls.json`. Include:

- Package name and dangerous version(s)
- Safe version(s) if known
- Type of threat (RAT, data theft, typosquat, etc.)
- Source link (advisory, blog post, tweet)

### Why contributing to vuls.json is safe

`vuls.json` is **append-only by design**. The worst case of a false positive is a package being temporarily blocked &mdash; an inconvenience, never a security incident. This means:

- Adding entries can never break your project or introduce vulnerabilities
- AI-assisted and automated threat feeds can safely append to `vuls.json` without human review of each entry
- Only *removing* entries could reduce security, and that requires careful review

This property makes npm-safe uniquely suited for **community-scale and automated threat collection**.

## References

- [Socket.dev Blog](https://socket.dev/blog) &mdash; Supply chain attack reports
- [GitHub Advisory Database](https://github.com/advisories) &mdash; Vulnerability database
- [Phylum Blog](https://blog.phylum.io) &mdash; Malware package analysis

## License

MIT
