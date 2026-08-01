# content-toolkit v0.1 Implementation Plan

**Author**: Foad Shafighi
**Date**: 2026-05-25
**Status**: DRAFT (ready for review + open-decisions confirmation, then LOCK)
**Target repo**: NEW private GitHub repo `builtform/content-toolkit` (to be created; mirrors `builtform/growth-toolkit` repo pattern)
**Implementing session location**: this plan will be executed from a `growth-toolkit`-style session in the new content-toolkit repo
**Parent context**: companion to `LaunchPad` plugin (free, public); content-toolkit is the paid private-repo plugin in the same product family
**Time budget**: 4-6 weeks of focused part-time work for v0.1 ship (Slices A-D = MVP sellable; Slices E-I = full v0.1)

---

## 1. Why this plan exists

`content-toolkit` is a new paid plugin for Claude Code, distributed as a private GitHub repo behind a paid access tier (matching the `growth-toolkit` business model). It packages curated content-production workflows (image, video, audio, 3D, LoRA training) that combine multiple backends (fal.ai, Google Gemini, Stability AI, ComfyUI local or hosted) into repeatable, brand-aware production pipelines.

The free companion is the `LaunchPad` plugin, which ships thin per-backend wrappers (`/lp-nano-banana`, plus future `/lp-stable-diffusion` and `/lp-flux`). LaunchPad gives raw API access; content-toolkit ships the **recipes and orchestration** that turn raw API access into a one-person creative agency.

**Audience**: solopreneurs and small studios in content-heavy domains, with a specific focus on the AEC industry (architects, interior designers, lighting designers) and content creators (bloggers, course authors, founders).

**Business model**: tiered private-repo access. Buyers bring their own API keys for backends (fal.ai, Google, Replicate, ComfyUI Cloud, etc.). The plugin orchestrates; we never run inference or hold customer keys.

**Pricing tiers** (target, can adjust at launch):

- **Starter** ($147 one-time) — plugin + 10 core workflows + setup guide
- **Pro** ($497 one-time) — Starter + full workflow library (~30 workflows) + LoRA cookbook + 4-hour course + private community + 90 days updates
- **Pro Subscription** ($39/mo) — Pro + ongoing workflow updates (2-4/mo) + monthly office hours

---

## 2. Product strategy & scope decisions

### 2.1 What is "in scope" for v0.1

- Plugin scaffold + brand profile system
- Atomic image commands (hero, product, thumbnail, social, illustration, architectural-render, interior-scene, lighting-study, mood-board)
- Flexible LoRA training pipeline covering 6 archetypes (subject, style, material, lighting, spatial-typology, sketch-pair)
- Brand-locked hero image workflow (the BuiltForm dogfooding case)
- 3 AEC-specific workflows (sketch-to-render, lighting study, interior scene)
- 4 video/multi-modal workflows (video ad, explainer video, product video, voiceover)
- Editing & post commands (upscale, bg-remove, bg-replace, relight, inpaint, restore, style-transfer)
- 3D commands for product mockups and AEC use cases
- Content authoring helpers (blog asset pack, launch bundle)
- Brand init + brand audit
- v0.1 documentation + 5 starter case studies (BuiltForm posts)

### 2.2 What is "out of scope" for v0.1 (deferred to v0.2+)

- The 4-hour course content (parallel work stream, not blocked by plugin shipping)
- Private community setup (Discord/Slack — operational, not code)
- Subscription billing/license-key mechanism (start with manual GitHub access grants)
- Multi-language support
- Cloud-hosted user dashboard
- Any SaaS or hosted-inference offering — explicitly NOT a SaaS, plugin is BYO-keys forever

### 2.3 Hard rules (do not violate during implementation)

1. **No SaaS surface**: the plugin never holds, proxies, or stores customer API keys. Every backend call uses the customer's own credentials loaded from their `.env.local`.
2. **BYO-keys**: every backend (fal.ai, Google, Stability, Replicate, ComfyUI Cloud, ViewComfy, RunPod) is plugged in via env vars. Plugin reads keys, never persists them.
3. **No em dashes in any output**: per project-wide writing rule. Use commas, colons, periods, semicolons, or parentheses. Applies to skill/agent/command descriptions, generated content, documentation, and code comments. En dashes (–) acceptable for ranges and bullets.
4. **Commercial-safe by default**: every shipped workflow defaults to a commercially-safe model (Flux schnell, SDXL, Flux pro via API, Nano Banana via Google, SD 3.5 under-$1M tier). Flux dev workflows MUST display a license-warning banner when invoked.
5. **Brand prefix convention**: all commands, agents, and skills use the `content-` prefix (matches `growth-` in growth-toolkit). No abbreviations like `ct-`.
6. **Dogfood before ship**: every workflow must be used on a real BuiltForm.ai or AEC project before being marked "ready" in the workflow registry.
7. **Reproducibility**: every generated artifact gets a sidecar JSON with all parameters (prompt, seed, model, LoRA weights, etc.) so any output can be regenerated or revised later.

---

## 3. Architecture

### 3.1 Repository structure

```
content-toolkit/
├── .claude-plugin/
│   └── plugin.json                       # Plugin metadata (name, version, description, author, license)
├── README.md                             # Public-facing readme (sales-oriented, links to private docs)
├── LICENSE.md                            # Single-seat commercial license terms
├── CHANGELOG.md                          # Versioned change log
├── .gitignore
├── commands/                             # Slash-command spec files (.md, Claude Code format)
│   ├── content-brand-init.md
│   ├── content-brand-audit.md
│   ├── content-hero-image.md
│   ├── content-product-shot.md
│   ├── content-product-variants.md
│   ├── content-thumbnail.md
│   ├── content-social-card.md
│   ├── content-illustration.md
│   ├── content-architectural-render.md
│   ├── content-interior-scene.md
│   ├── content-lighting-study.md
│   ├── content-mood-board.md
│   ├── content-lora-train.md
│   ├── content-lora-curate.md
│   ├── content-lora-evaluate.md
│   ├── content-lora-gen.md
│   ├── content-lora-stack.md
│   ├── content-lora-library.md
│   ├── content-video-ad.md
│   ├── content-explainer-video.md
│   ├── content-product-video.md
│   ├── content-bg-music.md
│   ├── content-voiceover.md
│   ├── content-captions.md
│   ├── content-upscale.md
│   ├── content-bg-remove.md
│   ├── content-bg-replace.md
│   ├── content-relight.md
│   ├── content-inpaint.md
│   ├── content-restore.md
│   ├── content-style-transfer.md
│   ├── content-3d-mockup.md
│   ├── content-room-3d.md
│   ├── content-floor-plan-to-3d.md
│   ├── content-blog-pack.md
│   └── content-launch-pack.md
├── agents/                               # Sub-agents
│   ├── content-prompt-engineer.md        # Rewrites briefs into model-optimal prompts
│   ├── content-art-director.md           # Multi-round critique loop on outputs
│   ├── content-comfy-orchestrator.md     # Manages ComfyUI workflow submissions
│   ├── content-lora-curator.md           # Pre-training image curation + caption suggestion
│   └── content-brand-keeper.md           # Enforces brand profile across generations
├── skills/                               # Process skills
│   ├── content-runner/SKILL.md           # Backend dispatcher (fal/google/stability/comfy)
│   ├── content-workflow-loader/SKILL.md  # Loads and parameterizes workflow YAMLs
│   ├── content-brand-loader/SKILL.md     # Loads brand.yml and applies to prompts/params
│   ├── content-lora-cookbook/SKILL.md    # LoRA training recipes by archetype
│   └── content-comfy-setup/SKILL.md      # Detects local vs hosted ComfyUI, validates endpoints
├── scripts/                              # Python implementation
│   ├── content_toolkit/
│   │   ├── __init__.py
│   │   ├── backends/
│   │   │   ├── fal.py                    # fal.ai client
│   │   │   ├── google.py                 # Gemini image client (Nano Banana family)
│   │   │   ├── stability.py              # Stability v2beta client
│   │   │   ├── replicate.py              # Replicate client (includes fofr/any-comfyui-workflow)
│   │   │   └── comfy.py                  # ComfyUI HTTP client (local + hosted)
│   │   ├── brand.py                      # Brand profile loader + validator
│   │   ├── workflows.py                  # Workflow YAML parser + executor
│   │   ├── lora.py                       # LoRA training orchestration
│   │   ├── output.py                     # Save outputs + sidecar metadata
│   │   ├── prompts.py                    # Prompt templates + augmentation
│   │   └── cli.py                        # Single CLI entry: `content-toolkit run <workflow> ...`
│   ├── tests/
│   │   ├── test_backends.py
│   │   ├── test_brand.py
│   │   ├── test_workflows.py
│   │   ├── test_lora.py
│   │   └── fixtures/
│   ├── pyproject.toml
│   └── requirements.txt
├── workflows/                            # Workflow recipe YAMLs
│   ├── brand-locked-hero-images.yml
│   ├── lora-train-and-deploy.yml
│   ├── aec-sketch-to-render.yml
│   ├── aec-lighting-study.yml
│   ├── aec-interior-scene.yml
│   ├── blog-post-asset-pack.yml
│   ├── product-launch-bundle.yml
│   ├── video-ad-production.yml
│   ├── explainer-video.yml
│   └── thumbnail-factory.yml
├── comfy-workflows/                      # ComfyUI API-format JSON workflows
│   ├── sdxl-hero-multi-cn.json
│   ├── flux-character-consistency-ipadapter.json
│   ├── sdxl-architectural-render-canny.json
│   ├── flux-architectural-render-depth.json
│   ├── ic-light-relight.json
│   └── ... (~15-20 in v0.1)
├── docs/
│   ├── README.md                         # Customer-facing entry
│   ├── INSTALL.md                        # Plugin install + env setup
│   ├── BACKENDS.md                       # Per-backend setup (fal, google, stability, comfy)
│   ├── BRAND_PROFILE.md                  # How to set up brand.yml
│   ├── playbooks/
│   │   ├── builtform-hero-images.md
│   │   ├── aec-firm-style-lora.md
│   │   ├── lighting-design-presentation.md
│   │   └── ... (~10 playbooks at v0.1)
│   └── case-studies/                     # Real outputs from BuiltForm + AEC dogfood
└── examples/
    ├── brand-builtform/                  # Sample brand profile for BuiltForm
    ├── brand-aec-firm/                   # Sample AEC firm brand profile
    └── prompts/                          # Tested prompt templates
```

### 3.2 Backend dispatcher pattern

All backends implement a common Python interface:

```python
class Backend(Protocol):
    name: str
    def generate_image(self, prompt: str, **params) -> ImageResult: ...
    def edit_image(self, image: Path, instruction: str, **params) -> ImageResult: ...
    def supports(self, capability: str) -> bool: ...
```

Each command/workflow declares the capability it needs (e.g., `image_generation`, `image_editing`, `controlnet`, `lora_training`, `video_generation`, `tts`); the dispatcher picks the backend based on:

1. Workflow's explicit `backend:` field if set
2. Customer's `.content-toolkit/config.yml` preferences
3. Default per-capability table (e.g., `image_generation` → fal.ai/flux-pro, `lora_training` → fal.ai/flux-lora-fast-training)

### 3.3 Brand profile structure

`.content-toolkit/brand.yml` in the customer's project:

```yaml
version: 1
name: builtform
description: "AI engineering blog with editorial illustration style"

style:
  references:
    - path: brand/builtform/style-refs/01-hero.png
    - path: brand/builtform/style-refs/02-illustration.png
    - path: brand/builtform/style-refs/03-mood.png
  canonical_prompt_suffix: "editorial illustration, muted palette, painterly, single subject, soft lighting"
  canonical_negative: "photorealistic, busy composition, harsh shadows, text, watermark, cluttered"
  aspect_default: "16:9"
  lora:
    path: .content-toolkit/loras/builtform-style.safetensors
    trigger: "BFSTYLE"
    weight: 0.7
  ipadapter:
    weight: 0.65

palette:
  primary: "#1a1a2e"
  secondary: "#e8d5b7"
  accent: "#c97064"

voice:
  tts_model: "fal-ai/elevenlabs/tts/turbo-v2.5"
  voice_id: "rachel"
  style: "warm, conversational, mid-pace"

output:
  base_path: "./content/generated"
  per_post_subdir: true
  sidecar_metadata: true

backends:
  image: "comfy_hosted" # OR "fal" OR "comfy_local" OR "google"
  video: "fal"
  tts: "fal"
  lora_training: "fal"
  comfy_endpoint: "https://replicate.com/fofr/any-comfyui-workflow"
  comfy_local_url: "http://localhost:8188"
```

### 3.4 Output structure

Every generated artifact saves to `{brand.output.base_path}/{type}/{slug-or-timestamp}/`:

```
content/generated/
├── hero/
│   └── 2026-05-25-ai-engineering-101/
│       ├── hero.png                 # final output
│       ├── hero-2k.png              # upscaled
│       ├── sidecar.json             # full reproduction metadata
│       ├── variations/              # rejected candidates
│       └── prompt.txt               # human-readable prompt used
├── thumbnail/
├── social/
├── video/
└── lora/
```

Sidecar JSON schema:

```json
{
  "command": "content-hero-image",
  "workflow": "brand-locked-hero-images",
  "brand": "builtform",
  "input": { "topic": "AI engineering 101", "aspect": "16:9" },
  "backend": "comfy_hosted",
  "model": "flux-dev",
  "seed": 4823910,
  "prompt": "...",
  "negative_prompt": "...",
  "loras": [{ "path": "builtform-style.safetensors", "weight": 0.7, "trigger": "BFSTYLE" }],
  "controlnets": [],
  "ipadapter_refs": ["brand/builtform/style-refs/01-hero.png"],
  "params": { "steps": 30, "cfg": 4.5, "sampler": "dpmpp_2m" },
  "generated_at": "2026-05-25T14:32:18Z",
  "duration_ms": 18432,
  "cost_usd": 0.034,
  "reproduce_with": "content-toolkit run hero-images --topic 'AI engineering 101' --seed 4823910"
}
```

### 3.5 Backend default decisions

| Capability                         | Default backend                                                       | Reason                                                            |
| ---------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Image gen (open-weight)            | fal.ai (Flux schnell/pro, SDXL)                                       | Cheapest, fastest, commercial-safe                                |
| Image gen (Google)                 | Google direct via Gemini API                                          | Cheaper than fal.ai for Nano Banana                               |
| Image gen (granular)               | Hosted ComfyUI (Replicate `fofr/any-comfyui-workflow` default)        | Customer with M2 Pro 16 GB cannot run Flux locally; hosted scales |
| Image gen (granular, opt-in local) | Local ComfyUI at `http://localhost:8188`                              | Power users with rigs                                             |
| Image editing                      | Flux Kontext via fal.ai                                               | Best editing model                                                |
| Inpaint/outpaint                   | Stability AI v2beta OR Flux Fill via fal.ai                           | Customer choice                                                   |
| Upscale                            | Clarity Upscaler via fal.ai                                           | Best price/quality                                                |
| Background removal                 | Bria via fal.ai                                                       | Industry standard                                                 |
| Relighting                         | IC-Light v2 via fal.ai                                                | Best directional control                                          |
| ControlNet                         | Hosted ComfyUI (multi-CN) OR fal.ai SDXL ControlNet Union (single CN) | Auto-pick based on workflow needs                                 |
| LoRA training                      | fal.ai (flux-lora-fast-training, flux-lora-portrait-trainer)          | $2.40 min, fastest iteration                                      |
| Video gen                          | fal.ai (Veo 3.1, Kling, Wan, Hailuo)                                  | Single key for all major models                                   |
| TTS                                | fal.ai (ElevenLabs Turbo v2.5, MiniMax Speech 2.8 HD)                 | Single key, quality range                                         |
| STT                                | fal.ai (Whisper Large v3)                                             | Cheapest                                                          |
| 3D mesh                            | fal.ai (Hunyuan3D 2, Pixal3D)                                         | Best 1-image-to-mesh                                              |
| Talking heads                      | fal.ai (Hedra Character 3, HeyGen Avatar V)                           | Customer choice                                                   |

---

## 4. Phase 2 implementation slices

Phase 2 is split into 9 sequential slices A-I. Slices A-D are the MVP sellable v0.1 (Starter tier deliverable). Slices E-I complete the full v0.1 (Pro tier deliverable). Each slice is independently shippable.

### 4.1 Slice A: Plugin scaffold + brand system

**Goal**: empty plugin shell that installs cleanly, holds the brand profile system, and runs one round-trip test.

**Deliverables**:

- New private GitHub repo `builtform/content-toolkit` created
- `.claude-plugin/plugin.json` with name=content-toolkit, version=0.1.0, description, author
- `README.md` (sales-oriented public-facing entry)
- `LICENSE.md` (single-seat commercial license; matches growth-toolkit terms)
- `CHANGELOG.md` (Keep-a-Changelog format)
- `.gitignore` (Python, .env.local, .content-toolkit/loras/\*.safetensors, generated outputs)
- `scripts/pyproject.toml` (Python 3.11+, pytest, ruff, pyright)
- `scripts/content_toolkit/__init__.py`
- `scripts/content_toolkit/brand.py` — load + validate brand.yml against JSON schema
- `scripts/content_toolkit/cli.py` — CLI entry point with `init`, `validate`, `run` subcommands
- `commands/content-brand-init.md` — interactive brand profile setup
- `commands/content-brand-audit.md` — runs sample generations to validate brand consistency
- `skills/content-brand-loader/SKILL.md` — process skill consumed by all other commands
- `examples/brand-builtform/brand.yml` — reference brand profile
- `docs/INSTALL.md` — installation guide
- `docs/BRAND_PROFILE.md` — brand profile schema doc
- `scripts/tests/test_brand.py` — brand load/validate tests (8-10 tests)

**Backend client stubs** (full impl in Slice B):

- `scripts/content_toolkit/backends/fal.py` — `FalBackend` class with `__init__(api_key)` reading from env
- `scripts/content_toolkit/backends/google.py` — `GoogleBackend` stub
- `scripts/content_toolkit/backends/stability.py` — `StabilityBackend` stub
- `scripts/content_toolkit/backends/comfy.py` — `ComfyBackend` stub (supports local + hosted endpoints)

**Acceptance criteria**:

- `pip install -e .` succeeds in `scripts/`
- `content-toolkit --version` prints `0.1.0`
- `content-toolkit init` creates `.content-toolkit/brand.yml` from template
- `content-toolkit validate` round-trips a valid brand.yml
- All ~10 brand tests pass
- Plugin installs in Claude Code via `/plugin install` from the private repo

**Time**: 2-3 days

### 4.2 Slice B: Atomic image commands (Foundation)

**Goal**: ship the 10 most-reached-for atomic image commands. No multi-step workflows yet, but each command is brand-aware (reads brand.yml) and produces a sidecar.

**Deliverables**:

**Commands (10):**

- `commands/content-hero-image.md` — brand-locked hero image; defaults to fal.ai Flux Pro; auto-applies brand style suffix
- `commands/content-product-shot.md` — Flux Kontext compositing
- `commands/content-product-variants.md` — N variations of same product with consistent identity
- `commands/content-thumbnail.md` — bg-remove + upscale + text overlay
- `commands/content-social-card.md` — Twitter/LinkedIn OG card with brand template
- `commands/content-illustration.md` — stylized illustration in chosen aesthetic
- `commands/content-architectural-render.md` — sketch/CAD → render via ControlNet
- `commands/content-interior-scene.md` — empty room → furnished
- `commands/content-lighting-study.md` — same space, N lighting scenarios
- `commands/content-mood-board.md` — brief → 6-12 reference grid

**Python implementation:**

- `scripts/content_toolkit/backends/fal.py` — full impl: text-to-image (Flux Pro, Flux schnell, SDXL), image-to-image, edit (Flux Kontext), upscale, bg-remove
- `scripts/content_toolkit/backends/google.py` — full impl: Nano Banana generate + edit
- `scripts/content_toolkit/backends/comfy.py` — full impl: `/prompt`, WebSocket listener, `/view`, `/upload/image`, `/object_info`, polling
- `scripts/content_toolkit/output.py` — save image + write sidecar JSON
- `scripts/content_toolkit/prompts.py` — prompt augmentation, brand suffix injection

**Agents (2):**

- `agents/content-prompt-engineer.md` — receives raw user intent, rewrites into model-optimal prompt with brand context
- `agents/content-brand-keeper.md` — validates prompts and outputs against brand profile

**Skill (1):**

- `skills/content-runner/SKILL.md` — backend dispatcher, picks backend per command per capability per brand config

**Tests:**

- `scripts/tests/test_backends.py` — fal + google + comfy round-trip tests with VCR cassettes for HTTP (~20-25 tests)
- `scripts/tests/test_output.py` — sidecar generation, output path resolution (~6-8 tests)

**Acceptance criteria**:

- Each of 10 commands runs end-to-end against fal.ai with a real API key
- Each output produces correct sidecar JSON with reproduce_with command
- Brand profile suffix/negative are auto-applied without user intervention
- Total tests passing: ~50

**Time**: 1 week

### 4.3 Slice C: Brand-locked hero workflow (BuiltForm dogfood)

**Goal**: ship the every.to-style hero image workflow end-to-end. This is the MVP demo and the BuiltForm dogfood case.

**Deliverables**:

**Workflow YAML:**

- `workflows/brand-locked-hero-images.yml` — multi-step recipe:
  1. Extract concept from input (post title or brief)
  2. Agent rewrites concept into 1-2 sentence visual description
  3. Submit ComfyUI workflow with IPAdapter style refs + (optional) style LoRA + canonical prompt + negatives
  4. Generate 4 candidate variations (different seeds)
  5. Agent picks best 2 based on brand fit + concept clarity
  6. Upscale chosen to 2K via Clarity Upscaler
  7. Save to `{output.base_path}/hero/{post-slug}/` with sidecar
  8. Optionally generate matching square thumbnail crop

**ComfyUI workflows (3):**

- `comfy-workflows/sdxl-hero-ipadapter-style.json` — SDXL + IPAdapter Plus + style refs
- `comfy-workflows/flux-hero-ipadapter-style.json` — Flux dev/schnell + IPAdapter + style refs
- `comfy-workflows/flux-hero-style-lora.json` — Flux + brand style LoRA

**Python implementation:**

- `scripts/content_toolkit/workflows.py` — YAML parser, step executor, parameter substitution, error handling
- `scripts/content_toolkit/backends/replicate.py` — Replicate client; default backend for ComfyUI via `fofr/any-comfyui-workflow`

**Agent:**

- `agents/content-art-director.md` — picks best 2 from 4 candidates, runs critique loop

**Skill:**

- `skills/content-workflow-loader/SKILL.md` — loads workflows/\*.yml, validates, parameterizes

**Documentation:**

- `docs/playbooks/builtform-hero-images.md` — step-by-step playbook for BuiltForm-style hero workflow
- `docs/case-studies/builtform-2026-05-hero.md` — first dogfooded case (run on a real BuiltForm post)

**Dogfooding requirement**:

- Run workflow on 5 real BuiltForm.ai posts
- Capture before/after for case study
- Iterate on workflow YAML based on real-use friction

**Acceptance criteria**:

- `/content-hero-image "post-title-or-brief"` runs end-to-end and produces publication-ready hero
- Style consistency across 5 dogfooded posts is visually verifiable
- Workflow completes in under 60s with hosted ComfyUI default backend
- Cost per hero is under $0.50 (target: $0.20-0.30)
- 5 BuiltForm posts shipped with auto-generated heroes

**Time**: 3-4 days plus 5 dogfood post cycles (can run in parallel)

### 4.4 Slice D: LoRA training suite (AEC archetypes)

**Goal**: ship a flexible LoRA training pipeline covering 6 archetypes. Critical for the AEC audience (architects, interior designers, lighting designers) who need style/material/lighting LoRAs, not just headshots.

**Deliverables**:

**Commands (6):**

- `commands/content-lora-train.md` — interactive LoRA training pipeline; asks archetype, source folder, base model, backend
- `commands/content-lora-curate.md` — pre-training image curation (dedup, validate resolutions, suggest captions, flag bad images)
- `commands/content-lora-evaluate.md` — post-training quality check with 12 eval prompts
- `commands/content-lora-gen.md` — inference with trained LoRA, auto-injects trigger word
- `commands/content-lora-stack.md` — stack multiple LoRAs with weight tuning
- `commands/content-lora-library.md` — register/list/remove LoRAs in `.content-toolkit/loras.yml`

**Python implementation:**

- `scripts/content_toolkit/lora.py` — LoRA training orchestration
  - `train(archetype, image_dir, base_model, trainer_backend) -> LoraResult`
  - `curate(image_dir) -> CurationReport` (uses Florence-2 or BLIP-2 for auto-caption via fal.ai)
  - `evaluate(lora_path, archetype) -> EvalReport` (12 eval prompts per archetype)
  - `register(lora_path, metadata) -> None` (writes to `.content-toolkit/loras.yml`)

**Archetype parameter presets** (in `skills/content-lora-cookbook/SKILL.md`):

| Archetype     | Use case                                        | Training steps | LoRA rank | Learning rate | Caption style                                                         |
| ------------- | ----------------------------------------------- | -------------- | --------- | ------------- | --------------------------------------------------------------------- |
| `subject`     | Specific person/building/product                | 1000-1500      | 16        | 1e-4          | "[trigger], [subject description], [context]"                         |
| `style`       | Visual aesthetic / firm's house style           | 1500-2500      | 32        | 5e-5          | "[trigger] style, [scene description]"                                |
| `material`    | Material category (concrete, oak, steel)        | 800-1200       | 8         | 1e-4          | "[trigger] material, [surface description]"                           |
| `lighting`    | Lighting scenario (uplight, daylight, dramatic) | 800-1200       | 8         | 1e-4          | "[trigger] lighting, [scene description]"                             |
| `typology`    | Space type (boutique retail, co-working)        | 1500-2000      | 16        | 5e-5          | "[trigger] space, [scene description]"                                |
| `sketch-pair` | Sketch-to-render translation                    | 1500-2500      | 32        | 5e-5          | "[trigger], [render description]" (paired with sketch via ControlNet) |

**Backends:**

- Default trainer: `fal-ai/flux-lora-fast-training` (Flux schnell for commercial-safe; Flux dev with license warning)
- SDXL trainer: `replicate/sdxl-lora-trainer` for Flux-license-averse customers
- Cost transparency: every training run shows estimated cost before launch (typically $2.40-12)

**Agent:**

- `agents/content-lora-curator.md` — interactive curation, auto-caption, quality scoring

**Skill:**

- `skills/content-lora-cookbook/SKILL.md` — archetype recipes, trigger word conventions, eval prompt templates, troubleshooting

**Documentation:**

- `docs/playbooks/aec-firm-style-lora.md` — train your firm's visual language as a LoRA
- `docs/playbooks/lighting-scenarios-lora.md` — train a lighting LoRA for repeatable design presentations
- `docs/playbooks/material-library-lora.md` — material LoRAs for materials boards

**Dogfooding requirement**:

- Train BuiltForm style LoRA (style archetype)
- Train one AEC sample LoRA (lighting or material; whichever the user has training data for)
- Verify both work in inference + stack together

**Acceptance criteria**:

- `/content-lora-train` runs interactively, completes a training job, downloads safetensors, registers in library
- All 6 archetypes have documented presets and eval prompt sets
- BuiltForm style LoRA trained and visually validated
- Cost transparency working (shows estimate before launch)
- License warnings shown when training on Flux dev

**Time**: 1 week

**Slice D ships the Starter-tier MVP** (Slices A+B+C+D = the $147 product).

---

### 4.5 Slice E: AEC-specific workflows

**Goal**: ship 3 deep AEC workflows that use the foundation from Slices A-D.

**Deliverables**:

**Workflow YAMLs (3):**

- `workflows/aec-sketch-to-render.yml` — sketch/CAD → photorealistic render via ControlNet (canny or depth) + optional firm LoRA + material/lighting LoRAs stacked
- `workflows/aec-lighting-study.yml` — base scene + N lighting scenarios (daylight/dusk/dramatic/ambient/task/accent); uses IC-Light or lighting LoRAs
- `workflows/aec-interior-scene.yml` — empty room photo → furnished + styled; brand/firm style applied

**ComfyUI workflows (4):**

- `comfy-workflows/sdxl-architectural-render-canny.json` — SDXL + Canny ControlNet for line-drawing-to-render
- `comfy-workflows/flux-architectural-render-depth.json` — Flux + Depth ControlNet for spatial precision
- `comfy-workflows/ic-light-relight-directional.json` — IC-Light v2 with directional controls
- `comfy-workflows/sdxl-multi-lora-stacking.json` — stacks 3-4 LoRAs (firm style + material + lighting) on SDXL base

**Commands** (already created in Slice B, now wired to these workflows):

- `/content-architectural-render` → triggers `aec-sketch-to-render`
- `/content-lighting-study` → triggers `aec-lighting-study`
- `/content-interior-scene` → triggers `aec-interior-scene`

**Documentation:**

- `docs/playbooks/aec-sketch-to-render.md`
- `docs/playbooks/aec-lighting-presentation.md`
- `docs/playbooks/aec-interior-staging.md`

**Dogfooding requirement**:

- Run sketch-to-render on at least 2 real architectural sketches
- Run lighting study on at least 1 real interior scene
- Capture case studies

**Acceptance criteria**:

- 3 workflows execute end-to-end with both hosted and local ComfyUI backends
- Sketch-to-render produces visually coherent results with line preservation
- Lighting study produces 4+ distinct lighting variants of same scene with consistent geometry
- 3 case studies documented

**Time**: 1 week

### 4.6 Slice F: Video and multi-modal workflows

**Goal**: ship video-gen, voice, and explainer workflows. These leverage fal.ai's video model catalog.

**Deliverables**:

**Commands (6):**

- `commands/content-video-ad.md` — short-form ad: keyframe → animation → audio overlay → captions
- `commands/content-explainer-video.md` — talking-head from photo + script (Hedra/HeyGen) with brand background
- `commands/content-product-video.md` — product photo → 360° rotation or use-case animation
- `commands/content-bg-music.md` — music bed matching mood (MusicGen/Stable Audio)
- `commands/content-voiceover.md` — script → professional voiceover with brand voice
- `commands/content-captions.md` — auto burned-in captions

**Workflow YAMLs (4):**

- `workflows/video-ad-production.yml` — keyframe (Flux) + animation (Wan/Kling) + voiceover (ElevenLabs) + music (MusicGen) + captions
- `workflows/explainer-video.yml` — Hedra avatar + script → talking head with brand BG
- `workflows/product-video.yml` — single photo → 360° via Wan i2v
- `workflows/course-module-video.yml` — composite for course module intro (used for course content production)

**Python implementation:**

- `scripts/content_toolkit/backends/fal.py` — extend with video endpoints (Veo 3.1, Kling, Wan, Hailuo, Sora 2), TTS endpoints (ElevenLabs Turbo, MiniMax 2.8 HD, Gemini Flash TTS), STT (Whisper), music (MusicGen, Stable Audio), avatars (Hedra, HeyGen)
- `scripts/content_toolkit/video.py` — video composition helpers (ffmpeg subprocess for caption burn-in, audio mixing, caption styling)

**Documentation:**

- `docs/playbooks/short-form-video-ad.md`
- `docs/playbooks/course-intro-video.md`
- `docs/playbooks/product-video-360.md`

**Dependencies**:

- Customer machine needs `ffmpeg` installed; `INSTALL.md` documents this
- Set hard cost-warning thresholds (Veo 3.1 at $0.20-0.40/sec adds up fast); confirm-before-spend for video calls over $1

**Acceptance criteria**:

- Each of 6 commands runs end-to-end
- Video ad workflow produces a 6-second branded video with synced audio
- Explainer video workflow produces a 30-second talking head
- Cost warnings displayed before any video generation
- 3 case studies documented

**Time**: 1 week

### 4.7 Slice G: Editing and post-production commands

**Goal**: ship the editing toolset. These are mostly thin wrappers around fal.ai endpoints but with brand-aware defaults.

**Deliverables**:

**Commands (7):**

- `commands/content-upscale.md` — quality-tier-aware upscaler (Clarity for photographic, AuraSR for illustrative, ESRGAN for retro)
- `commands/content-bg-remove.md` — Bria with edge refinement
- `commands/content-bg-replace.md` — bg-remove + new bg gen in one call
- `commands/content-relight.md` — IC-Light v2 with directional controls
- `commands/content-inpaint.md` — smart inpaint with auto-mask from text description
- `commands/content-restore.md` — old photo restoration
- `commands/content-style-transfer.md` — apply style ref to source image

**Python implementation:**

- All endpoints in `backends/fal.py` (extend Slice B impl)
- Auto-mask helper using Florence-2 grounding for `/content-inpaint`

**Documentation:**

- `docs/playbooks/thumbnail-cleanup.md` (uses upscale + bg-remove)
- `docs/playbooks/historical-photo-restoration.md`

**Acceptance criteria**:

- All 7 commands run with brand-aware defaults
- Auto-mask inpaint works for common targets ("remove the watermark", "remove the person on the left")

**Time**: 3-4 days

### 4.8 Slice H: Content authoring helpers + 3D

**Goal**: ship the higher-order workflows that bundle multiple commands into "create everything for X" calls. These are flagship sellable features.

**Deliverables**:

**Commands (5):**

- `commands/content-blog-pack.md` — one command per blog post: hero + social card + 3 in-body illustrations + sidebar thumbnail
- `commands/content-launch-pack.md` — product launch bundle: hero + 5 social variants + 1 video + voiceover
- `commands/content-3d-mockup.md` — photo → 3D mesh (Hunyuan3D)
- `commands/content-room-3d.md` — interior photo → rough 3D room
- `commands/content-floor-plan-to-3d.md` — 2D floor plan → 3D massing

**Workflow YAMLs (3):**

- `workflows/blog-post-asset-pack.yml`:
  1. Read post markdown (or accept summary)
  2. Agent extracts title, key concept, 3 sub-themes
  3. Parallel: hero (brand-locked workflow) + social card + 3 illustrations + thumbnail
  4. All saved to `{output}/posts/{slug}/`
  5. Emit manifest with Markdown image refs ready to paste
- `workflows/product-launch-bundle.yml` — full launch asset pack
- `workflows/thumbnail-factory.yml` — bg-remove + upscale + text overlay as a pipeline

**Python implementation:**

- `scripts/content_toolkit/backends/fal.py` — 3D endpoints (Hunyuan3D 2, Pixal3D, Trellis)
- `scripts/content_toolkit/parallel.py` — async parallel execution of independent workflow steps

**Documentation:**

- `docs/playbooks/blog-post-asset-pack.md`
- `docs/playbooks/product-launch-bundle.md`
- `docs/playbooks/3d-product-mockup.md`

**Dogfooding requirement**:

- Run blog-pack on the next 5 BuiltForm posts (extends Slice C dogfood)
- Run launch-pack on at least one product launch (BuiltForm or growth-toolkit/launchpad release)

**Acceptance criteria**:

- `/content-blog-pack` produces complete asset pack in under 3 minutes for a typical post
- `/content-launch-pack` produces full launch bundle in under 10 minutes
- 5+ blog posts shipped with full asset packs
- Manifest output is paste-ready for Markdown

**Time**: 1 week

### 4.9 Slice I: Documentation, examples, and ship prep

**Goal**: production-ready docs, case studies, examples, and final QA before tagging v0.1.0.

**Deliverables**:

**Documentation:**

- Complete `docs/README.md` with full command + workflow index
- Complete `docs/INSTALL.md` with step-by-step setup (Python, env vars per backend, optional ComfyUI install, ffmpeg)
- Complete `docs/BACKENDS.md` with per-backend setup, pricing notes, recommended tiers
- Complete `docs/BRAND_PROFILE.md` with full schema reference + 3 example profiles
- 10+ playbooks in `docs/playbooks/`
- 10+ case studies in `docs/case-studies/` (real outputs with side-by-side before/after)

**Examples:**

- `examples/brand-builtform/` — full BuiltForm brand profile + style LoRA + sample outputs
- `examples/brand-aec-firm/` — sample AEC firm profile + LoRA stack + sample outputs
- `examples/prompts/` — tested prompt templates per command

**Testing & QA:**

- All test suites passing: target ~100-150 tests total
- Manual QA pass: every command and workflow run end-to-end against fal.ai + at least one hosted ComfyUI backend
- Cost reconciliation: actual vs estimated spend within 10% across QA pass
- License warnings verified to fire on Flux dev paths

**Release:**

- CHANGELOG.md entry for v0.1.0
- Tag `v0.1.0` on main
- Private GitHub release with install instructions
- Customer onboarding doc (how to get plugin access, set up keys, run brand-init)

**Acceptance criteria**:

- All 30+ commands documented in docs/README.md command index
- All 10+ workflows documented in docs/README.md workflow index
- All test suites green
- README.md sales page complete with feature list and pricing tiers
- LICENSE.md and CHANGELOG.md current
- v0.1.0 tagged

**Time**: 3-5 days

---

## 5. Cross-cutting concerns

### 5.1 Cost tracking and warnings

Every command/workflow estimates cost before execution. Show estimate inline:

```
$ /content-video-ad "BuiltForm v2 launch"
Estimated cost: $2.40 (6s Veo 3.1 + voiceover + music + captions)
Proceed? [Y/n]
```

Hard thresholds:

- Under $0.10: no prompt
- $0.10-$1.00: show estimate inline, default Y
- Over $1.00: show estimate, require explicit Y
- Over $5.00: require explicit `--yes-spend-{amount}` flag

Track cumulative session spend in `.content-toolkit/session.json`; expose `content-toolkit spend` to show breakdown.

### 5.2 Env var conventions

Standard env var names (all loaded from `.env.local`):

- `FAL_KEY` — fal.ai
- `GOOGLE_API_KEY` — Google Gemini
- `STABILITY_API_KEY` — Stability AI
- `REPLICATE_API_TOKEN` — Replicate
- `COMFY_LOCAL_URL` — local ComfyUI (default `http://localhost:8188`)
- `COMFY_HOSTED_URL` — hosted ComfyUI endpoint (e.g., Replicate `fofr/any-comfyui-workflow`)
- `COMFY_HOSTED_KEY` — auth for hosted Comfy (Replicate token or ViewComfy key)
- `ELEVENLABS_API_KEY` — direct (optional; otherwise proxied through fal.ai)

### 5.3 License-warning protocol

When any command/workflow defaults to Flux dev or Flux Kontext dev:

```
⚠️  This workflow uses FLUX.1 [dev], which is governed by the BFL Non-Commercial License.
   For commercial use (SaaS, revenue-generating products, customer-facing deliverables),
   you need a paid commercial license (~$35/mo from bfl.ai/licensing).
   For commercial-safe alternatives, use:
   - --model=flux-schnell (Apache 2.0, fully commercial)
   - --model=flux-pro (commercial via API ToS)
   - --model=sdxl (CreativeML Open RAIL-M, fully commercial)
   Continue with Flux dev? [y/N]
```

Customer can suppress per-session with `--accept-flux-dev-license` flag.

### 5.4 ComfyUI workflow JSON management

All ComfyUI workflow JSONs in `comfy-workflows/` use the API format (Settings → Enable Dev mode → Save (API Format)). Each JSON is parameterized by Python wrapper:

```python
def render_workflow(template_path, params):
    workflow = json.load(open(template_path))
    # Replace specific node inputs with params
    workflow["6"]["inputs"]["text"] = params["prompt"]
    workflow["7"]["inputs"]["text"] = params["negative"]
    workflow["10"]["inputs"]["image"] = params["uploaded_image_name"]
    workflow["12"]["inputs"]["strength"] = params["lora_weight"]
    return workflow
```

Workflow JSONs are versioned in the repo. Custom-node dependencies declared in `comfy-workflows/MANIFEST.yml`:

```yaml
workflows:
  sdxl-hero-ipadapter-style:
    custom_nodes:
      - ComfyUI_IPAdapter_plus
      - ComfyUI-Custom-Scripts
    models:
      - sd_xl_base_1.0.safetensors
      - ip-adapter-plus_sdxl_vit-h.safetensors
```

`/content-comfy-setup` skill checks the user's local or hosted ComfyUI for these deps and instructs install/upload if missing.

### 5.5 Brand-locked output enforcement

Every image-generating command:

1. Loads brand.yml via `content-brand-loader` skill
2. Appends `brand.style.canonical_prompt_suffix` to user prompt
3. Appends `brand.style.canonical_negative` to negative prompt
4. Sets aspect ratio from `brand.style.aspect_default` if not specified
5. Applies brand LoRA if configured
6. Applies IPAdapter refs if configured
7. Validates output via `content-brand-keeper` agent (optional, opt-in)

User can override per-call with `--no-brand` or `--brand=other-profile`.

### 5.6 Reproducibility contract

Every generated artifact MUST be reproducible:

- Sidecar JSON includes the exact `reproduce_with` command
- Seeds always recorded (random if not specified, but recorded after generation)
- Workflow YAMLs versioned in repo with semver tags
- LoRA files versioned by hash in `.content-toolkit/loras.yml`
- ComfyUI workflow JSONs in `comfy-workflows/` versioned in repo

---

## 6. Open decisions (CONFIRM BEFORE LOCKING)

The implementing session should NOT start implementation until these are confirmed by Foad:

1. **Default ComfyUI backend**: confirm hosted (Replicate `fofr/any-comfyui-workflow`) as default vs ViewComfy vs Comfy Cloud vs RunComfy. Recommendation: **Replicate `fofr/any-comfyui-workflow`** because it's pay-per-second, no subscription, accepts arbitrary workflow JSON, and the customer already has a Replicate token from other content-toolkit flows.

2. **Repo creation**: confirm new private GitHub repo at `github.com/builtform/content-toolkit` (vs sub-folder in existing repo). Recommendation: **new private repo** to match growth-toolkit distribution pattern.

3. **Python or TypeScript for backend wrapper**: confirm Python (matches LaunchPad and growth-toolkit script convention). Recommendation: **Python**.

4. **License terms**: confirm single-seat commercial license, no redistribution, perpetual access for purchasers. Recommendation: **lift growth-toolkit LICENSE.md verbatim** with name change.

5. **Pricing tier names**: confirm Starter/Pro/Pro-Subscription names + prices ($147/$497/$39mo). Open to alternatives.

6. **Course content**: confirm course is OUT OF SCOPE for v0.1 plugin ship (separate parallel work stream). Recommendation: **yes, out of scope**. Plugin ships first; course recorded after plugin is stable using the plugin to produce its own assets (perfect dogfooding loop).

7. **AEC focus depth**: confirm AEC is a HEADLINE audience (3 dedicated workflows + LoRA archetypes for material/lighting/typology) but not the ONLY audience (general content creators also served). Recommendation: **confirmed; AEC is a strong vertical pillar but the plugin is broadly applicable**.

8. **fal.ai vs Replicate as primary backend for non-Comfy work**: confirm fal.ai as default. Recommendation: **fal.ai** because single key unlocks image+video+audio+3D+LoRA training in one billing relationship.

---

## 7. Implementation sequencing

Recommended sequence (sequential where dependencies exist; parallelizable elsewhere):

```
Week 1:  Slice A (scaffold + brand)            [3 days]
Week 1:  Slice B start (atomic images)         [parallel, 2 days into week 2]
Week 2:  Slice B finish + Slice C start
Week 3:  Slice C finish (hero workflow) + BuiltForm dogfood (5 posts)
Week 4:  Slice D (LoRA training suite)
         ===> STARTER TIER MVP SHIPPABLE HERE ===
Week 5:  Slice E (AEC workflows) + Slice G (editing) in parallel
Week 6:  Slice F (video/multi-modal)
Week 7:  Slice H (content authoring + 3D)
Week 8:  Slice I (docs + examples + ship prep)
         ===> v0.1.0 TAG + FULL PRO TIER SHIPPABLE ===
```

Total: ~8 weeks part-time, faster if dedicated. Starter tier can ship at end of Week 4 to start generating revenue while Pro tier completes.

---

## 8. Acceptance criteria for v0.1.0 ship

- All 30+ commands implemented and documented
- All 10+ workflows implemented and documented
- Brand profile system complete with schema validation
- LoRA training pipeline covers all 6 archetypes
- BuiltForm dogfood: at least 5 blog posts shipped with auto-generated heroes + asset packs
- AEC dogfood: at least 2 sketch-to-render case studies + 1 lighting study + 1 trained AEC LoRA
- 100-150 tests passing across `scripts/tests/`
- Documentation complete: README, INSTALL, BACKENDS, BRAND_PROFILE, 10+ playbooks, 10+ case studies
- Cost tracking and warning system working
- License-warning protocol firing on Flux dev paths
- All env vars documented; no hardcoded keys anywhere
- Plugin installs cleanly in Claude Code via `/plugin install` from private repo
- v0.1.0 tagged with CHANGELOG entry

---

## 9. Out-of-band considerations for implementing session

**Things this plan deliberately does NOT prescribe** (implementer discretion):

- Exact Python package choices (requests vs httpx; pydantic v2 fine)
- Test framework specifics (pytest assumed; choice of VCR library open)
- Linting/formatting (ruff + pyright recommended; matches LaunchPad)
- CI setup (GitHub Actions matching growth-toolkit pattern; not blocking for v0.1)
- Pre-commit hooks (lefthook recommended; matches LaunchPad)
- Exact UI/UX of interactive commands (`/content-brand-init`, `/content-lora-train` flows have flexibility)

**Things the implementing session MUST consult Foad on**:

- Any deviation from the 8 open decisions in Section 6
- Any backend choice change (e.g., choosing fal.ai over Google for Nano Banana, which is a documented bad decision per prior research)
- Any addition of a backend not listed in Section 3.5 backend defaults table
- Any change to the `content-` command prefix convention
- Any introduction of SaaS-style functionality (proxying keys, hosted endpoints, etc.) — this violates the BYO-keys rule

**Things to reference for prior context**:

- LaunchPad plugin structure (`plugins/launchpad/` in the LaunchPad repo) as the architectural model
- growth-toolkit plugin distribution model
- This plan's prior conversation transcripts for design rationale (research on fal.ai, ComfyUI, Stability AI, Flux licensing, hosted ComfyUI options) — Foad has these and can share if implementer needs them

---

## 10. References

- LaunchPad plugin structure: `plugins/launchpad/` in `builtform/LaunchPad` repo
- growth-toolkit plugin (private): `builtform/growth-toolkit`
- ComfyUI API format docs: https://docs.comfy.org/
- fal.ai model catalog: https://fal.ai/models
- Replicate fofr/any-comfyui-workflow: https://replicate.com/fofr/any-comfyui-workflow
- Stability AI v2beta: https://platform.stability.ai/docs/api-reference
- Google Gemini Image API: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-image
- Flux licensing: https://bfl.ai/legal/non-commercial-license-terms
- IPAdapter for ComfyUI: https://github.com/cubiq/ComfyUI_IPAdapter_plus
- IC-Light: https://github.com/lllyasviel/IC-Light

---

**End of plan. Ready for review + open-decisions confirmation, then LOCK.**
