# Doubao virtual try-on skill

This Codex skill generates photorealistic try-on images from:

1. one real-person reference photo; and
2. one or more outfit-item collage images.

All visual understanding, generation, and auditing calls go to Volcengine Ark.
The workflow does not fall back to a local model or another image provider.

## What is included

```text
skills/doubao-virtual-try-on/
├── SKILL.md
├── agents/openai.yaml
├── references/api-contract.md
└── scripts/
    ├── virtual_try_on.py
    └── batch_virtual_try_on.py
```

- `virtual_try_on.py` handles one outfit board.
- `batch_virtual_try_on.py` handles two or more outfits for the same person. It
  reuses the accepted source framing for every look, then performs a strict
  cross-look consistency audit.
- Both entry points require only Python 3.10+ and its standard library.

## Install

Build the deterministic shareable archive:

```bash
python3 scripts/package_doubao_skill.py
```

Install from the repository:

```bash
mkdir -p "$HOME/.codex/skills"
cp -R skills/doubao-virtual-try-on "$HOME/.codex/skills/"
```

Or unzip the packaged archive into `$HOME/.codex/skills`:

```bash
unzip dist/skills/doubao-virtual-try-on-v1.4.3.zip -d "$HOME/.codex/skills"
```

Restart Codex after installation. Invoke the skill as
`$doubao-virtual-try-on`, or ask for “豆包真人穿搭试穿”.

## Authentication

Create an Ark API key with access to both pinned models, then expose it only at
runtime:

```bash
export ARK_API_KEY="your-key"
```

Do not put the key in a command argument, image path, checked-in environment
file, output directory, or issue/PR text. If `ARK_API_KEY` is absent and the
script has an interactive terminal, it requests the key using a hidden prompt.

## Quick start: one outfit

```bash
python3 skills/doubao-virtual-try-on/scripts/virtual_try_on.py \
  "/absolute/path/person.jpg" \
  "/absolute/path/outfit-board.jpg" \
  --output-dir "/absolute/path/output/single"
```

Add a composition/realism reference when needed:

```bash
python3 skills/doubao-virtual-try-on/scripts/virtual_try_on.py \
  "/absolute/path/person.jpg" \
  "/absolute/path/outfit-board.jpg" \
  --style-reference "/absolute/path/target-look.jpg" \
  --output-dir "/absolute/path/output/single"
```

The style reference influences composition and realism only. It is not an
identity or clothing source.

## Quick start: multiple outfits, same person

Use one batch call rather than separate single-look calls:

```bash
python3 skills/doubao-virtual-try-on/scripts/batch_virtual_try_on.py \
  "/absolute/path/person.jpg" \
  "/absolute/path/outfit-01.jpg" \
  "/absolute/path/outfit-02.jpg" \
  "/absolute/path/outfit-03.jpg" \
  --output-dir "/absolute/path/output/batch"
```

Batch mode locks the source face, visible body landmarks, pose, head scale,
camera distance, crop, and background across looks. It does not invent a
canonical body from a cropped portrait. The same neck-through-calves eligibility
gate used by single-look mode applies before paid generation.

## CLI contract

Common options:

| Option | Default | Meaning |
| --- | --- | --- |
| `--size` | `2K` | Ark output size |
| `--watermark` | off | Request an API watermark |
| `--api-base` | Ark Beijing v3 endpoint | Override only for compatible Ark deployments |
| `--understanding-model` | `doubao-seed-2-0-lite-260428` | Understanding/audit model |
| `--image-model` | `doubao-seedream-5-0-260128` | Generation model |
| `--version` | — | Print the skill CLI version |

Single-look controls:

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-attempts` | `2` | Maximum generation/audit attempts; accepts 1–3 |
| `--style-reference` | none | Optional composition/realism image |

Batch controls:

| Option | Default | Meaning |
| --- | --- | --- |
| `--anchor-attempts` | `2` | Maximum identity-anchor attempts; accepts 1–3 |
| `--look-attempts` | `2` | Maximum attempts per outfit; accepts 1–3 |
| `--workers` | `2` | Concurrent look workers; accepts 1–2 |

Use attempt limits of `1` when avoiding automatic paid quality retries is more
important than audit recovery.

## Outputs

The output directory is the durable integration boundary. Scripts print
progress for humans and write structured JSON for programs.

Single-look output:

```text
output/
├── analysis.json
├── generation-attempt-N.json
├── attempt-N.jpg
├── audit-attempt-N.json
├── manifest.json
└── result.jpg
```

`manifest.json` records the selected attempt, model IDs, resolved input paths,
and relative result filename. The final stdout line also includes
`RESULT=/absolute/path/result.jpg`.

Batch output:

```text
output/
├── identity-analysis.json
├── identity-anchor/
├── look-01/
├── look-02/
├── cross-look-audit.json
└── manifest.json
```

Read `manifest.json` first. Treat `cross_look_pass: false` as a failed set even
when individual looks passed; `cross-look-audit.json` identifies outliers and
recommended corrections.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Generation completed; batch cross-look audit passed |
| `1` | Input, authentication, API, download, or processing error |
| `3` | Batch generated, but the strict cross-look audit failed |
| `130` | Interrupted by the user |

## HTTP/API behavior

The exact request and response shapes are documented in
[`references/api-contract.md`](../skills/doubao-virtual-try-on/references/api-contract.md).
The scripts call:

- `POST /chat/completions` for visual understanding and audits;
- `POST /images/generations` for multi-reference Seedream generation.

Local JPEG, PNG, and WebP inputs are sent as base64 data URLs over HTTPS.
Generation responses may contain a signed URL or base64 image. Signed URLs are
used only to download the result and are removed from persisted response JSON.

Transient HTTP `408`, `409`, `429`, `500`, `502`, `503`, and `504` responses use
bounded exponential backoff. Authentication and permission errors are returned
immediately in sanitized form.

## Validation and packaging

Run the offline checks:

```bash
pnpm test:doubao-skill
python3 scripts/package_doubao_skill.py
```

The packager validates the required layout, rejects symlinks and likely embedded
Ark credentials, and emits a deterministic ZIP. It never performs a paid API
call.

For an end-to-end check, run one single-look request with
`--max-attempts 1`. A live check requires an authorized key, consumes Ark
quota, and writes its diagnostics under the chosen output directory.

## Troubleshooting

- `Ark HTTP 401` or `403`: verify `ARK_API_KEY`, model access, and account
  permissions. Do not switch providers as a fallback.
- `Ark HTTP 429`: wait for quota/rate-limit recovery or reduce batch concurrency
  with `--workers 1`.
- Missing accessories or garment mismatch: inspect the selected audit and retry
  recommendations; use a clearer outfit board with separated items.
- Face or head-size drift across looks: use batch mode in one call. Never run
  each outfit independently.
- Body shape differs from the person: use a source that passes the
  neck-through-calves gate. The workflow preserves visible landmarks and does
  not synthesize a replacement body from a cropped portrait.
- `cross_look_pass` is false: inspect the outlier indices in
  `cross-look-audit.json` and regenerate those looks before sharing the set.
