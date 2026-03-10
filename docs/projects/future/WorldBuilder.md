FinalJourney — World-Compiled Generative Story Engine
Core Idea

Current AI image tools generate isolated frames.

FinalJourney generates persistent worlds.

Users provide a folder of reference media (images and optionally video).
The system infers:

characters

environments

props

visual style

relationships

The system previews its interpretation before committing compute.

When accepted, the system compiles a reusable “world artifact” that can later generate:

images

scenes

sequences

video

3D renderable assets

This artifact can be queried like a runtime world model.

End-to-End Flow
1. Storyboard Input

User drops a folder into the application.

Example:

/storyboard
  01_dad_working.jpg
  02_kids_backyard.jpg
  03_dog.jpg
  04_house_evening.jpg
  05_family_couch.mp4

Media types:

images

short video clips

optional text notes

Goal: infer the creative world state.

2. Asset Extraction Phase

The system analyzes the folder.

Outputs:

characters
environments
props
style
relationships

Technologies involved:

Image understanding

Used to identify recurring people, animals, objects.

Options:

CLIP / SigLIP embeddings (probably a good option)

Florence-2 vision model (probably a good option)

GPT-4o vision or equivalent (probably a good option)

Purpose:

cluster similar faces

detect environment patterns

extract props

Face and identity clustering

Group images into character identities.

Options:

InsightFace (probably a good option)

FaceNet (probably a good option)

Output:

character_001
character_002
character_003
dog
Environment clustering

Detect recurring locations.

Options:

CLIP embedding similarity (probably a good option)

DINOv2 visual embeddings (probably a good option)

Output:

environment.house
environment.backyard
environment.kitchen
Prop extraction

Recurring objects:

laptop
yellow_table
couch
dog

Tech:

GroundingDINO (probably a good option)

SAM2 segmentation (probably a good option)

Style inference

Determine visual style.

Examples:

warm cinematic photography
anime
illustrated
watercolor

Tech:

CLIP style embeddings (probably a good option)

LLaVA style classification (probably a good option)

3. Preview Mode (Key UX)

The system generates predicted scenes before committing compute.

Interface:

Left panel:

imported storyboard images

Right panel:

predicted scenes

Example preview grid:

Dad working at desk
Kids playing backyard
Dog watching yard
Family couch scene

User actions:

remove scenes

add images

reorder storyboard

adjust style knobs

Goal: steer the world inference before expensive generation.

4. World Compilation

User clicks Generate World.

This step builds the persistent artifact.

The world artifact contains:

characters
environment models
prop models
style profile
base prompts
generation config
Character model generation

Purpose: maintain identity across scenes.

Tech:

LoRA training (probably a good option)

Tools:

OneTrainer (probably a good option)

Kohya trainer (probably a good option)

Output:

character_dad.lora
character_emily.lora
character_ben.lora
character_dog.lora
Environment modeling

Goal: recreate consistent locations.

Tech options:

DreamBooth environment embeddings (probably a good option)

ControlNet depth maps (probably a good option)

Output:

environment_backyard.embedding
environment_house.embedding
Style model

Defines visual aesthetic.

Tech options:

Style LoRA (probably a good option)

prompt templates (probably a good option)

Output:

style_family_cinematic.lora
5. World Artifact

Final compiled artifact:

family_world.fjw

Contents:

/world
  /characters
     dad.lora
     emily.lora
     ben.lora

  /environments
     house.embedding
     backyard.embedding

  /props
     yellow_table.json
     couch.json

  /style
     cinematic_style.json

  /prompts
     base_prompts.yaml

  /metadata
     world_manifest.json

Portable.

Reusable.

Shareable.

6. Scene Generation

Once world exists, scenes can be generated.

Example query:

scene:
  characters: [emily, ben]
  location: backyard
  action: drawing at table
  time: sunset

Generation pipeline:

Base model:

SDXL (probably a good option)

Flux (probably a good option)

Guidance:

LoRA characters

IP-Adapter references (probably a good option)

ControlNet pose (probably a good option)

Output:

consistent scene images.

7. Storyboard Engine

Users define sequences.

Example:

scene 1: dad working late
scene 2: kids playing outside
scene 3: dad joins them

Engine generates the sequence.

8. Video Generation

Optional step.

Generate animated sequences.

Options:

LTX-Video (probably a good option)

CogVideoX (probably a good option)

Process:

image → short video clip

Example:

4-second scene

subtle motion

9. 3D Character Extraction (optional future)

Convert characters to 3D assets.

Options:

Wonder3D (probably a good option)

TripoSR (probably a good option)

Output:

character_dad.glb

Allows:

game engines

animation tools

10. Query API

Once world exists:

Example API:

render_scene(world_id, scene_config)
render_video(world_id, sequence)
get_character(world_id, character_name)
Core System Components
media_ingest
asset_extraction
world_inference
preview_engine
world_compiler
scene_renderer
video_renderer
artifact_registry
Technology Stack

Compute:

NVIDIA 4090 local GPU

Core models:

SDXL (probably a good option)

Flux (probably a good option)

Vision:

CLIP / SigLIP (probably a good option)

Florence-2 (probably a good option)

Identity:

InsightFace (probably a good option)

Generation guidance:

LoRA

ControlNet

IP-Adapter

Video:

LTX-Video (probably a good option)

3D:

Wonder3D (probably a good option)

Pipeline orchestration:

Python workflows (probably a good option)

UI:

Electron / Tauri desktop (probably a good option)

Why This Is Different

Current tools:

prompt → image

FinalJourney:

assets → world → scenes → story

The artifact is a world, not an image.

Does It Fit Orket?

Possibly, but not necessarily.

It depends whether Orket wants to support AI capability pipelines.

This concept is essentially:

media_pipeline

That could live as:

orket/extensions/media_world_engine

But it could also be its own project.

Most Novel Parts

Two pieces stand out.

1. Folder → World inference

Turning raw reference images into a structured world.

2. Preview-before-compile UX

Preventing expensive training runs before users approve the inferred world.

Honest Scope Assessment

This is not a small project.

But it is technically coherent and composed of existing tools.

The real innovation would be:

UX

world modeling

workflow integration

Not the raw models.

-----

MVP (2–3 weeks)
Goal

Prove one thing:

Can a user drop a folder of images, preview the inferred world, approve it, and then generate a small set of consistent scenes from that world?

Not video.
Not 3D.
Not full multi-character perfection.

Just:

folder → preview → world pack → 6–12 usable scenes

If that works and feels magical, the larger idea is real.

What the MVP does
User flow

User drops a folder of images into the app.

App scans images and infers:

likely characters

likely environments

likely props

likely style

App shows:

imported image grid

generated preview panel

User can:

exclude bad images

rename characters

tag environment names

pick a style preset

User clicks Build World

System creates a lightweight world pack

User can generate:

portrait of character

character in known environment

two characters in simple scene

6–12 storyboard frames

That is enough to prove the concept.

What the MVP does not do

Cut all of this from v1:

video generation

3D extraction

full autonomous story generation

complex multi-scene narrative planning

production-grade training pipeline

cloud sync / sharing

collaboration

deep editing UI

perfect house reconstruction

robust identity preservation across every pose/outfit

Those are later.

MVP artifact

Instead of a giant world blob, build a small world pack.

Example:

family_world_pack/
  manifest.json
  characters/
    dad/
      refs/
      embedding.json
      chosen_images.json
    emily/
      refs/
      embedding.json
    ben/
      refs/
      embedding.json
  environments/
    backyard/
      refs/
      embedding.json
    desk/
      refs/
      embedding.json
  props/
    yellow_table.json
    dog.json
  style/
    style_profile.json
  prompts/
    base_scene_templates.json

This is enough for reuse without overengineering.

Core MVP components
1. Folder ingest

Drop a local folder and enumerate images.

Tech:

Python backend (probably a good option)

simple desktop UI or local web app (probably a good option)

2. Image clustering

Group similar faces and similar environments.

Tech:

InsightFace for face embeddings (probably a good option)

CLIP or SigLIP for environment/style similarity (probably a good option)

Outputs:

character clusters

environment clusters

possible props

3. Preview UI

This is the most important MVP feature.

Layout:

center/left: imported image grid

right: inferred clusters + preview scenes

bottom or side panel: controls

User actions:

exclude image

merge/split character cluster

rename cluster

mark “older child” / “younger child”

rename environment: “backyard,” “desk,” “living room”

choose style preset

This is where the magic is.

4. World pack builder

No LoRA training yet unless needed. Start lighter.

World pack contains:

selected refs per character

selected refs per environment

style preset

prompt templates

metadata

5. Scene renderer

Generate a limited set of scenes from templates.

Examples:

[character] portrait

[character] in [environment]

[character_a] and [character_b] in [environment]

[character] performing [simple action]

Use defaults heavily.

Best MVP technical strategy
Do not start with per-character LoRA training

That makes the MVP slower and heavier.

Start with:

reference image selection

face clustering

image prompt scaffolding

image-to-image / reference-guided generation where possible

That lets you prove UX first.

If later you find consistency is too weak, add LoRA as Phase 2, not MVP.

MVP stack
Backend

Python + FastAPI (probably a good option)

Reason:

easy model integration

easy local orchestration

good fit for GPU workflows

Frontend

Two good choices:

React + Tauri (probably a good option)

React + Electron (probably a good option)

My bias:

Tauri if you want lighter desktop feel

Electron if you want fastest familiar app shell

Local model orchestration

ComfyUI backend workflows (probably a good option)

Reason:

already solves a lot of local generation plumbing

good for future expansion

visual workflow debugging helps

Embeddings / inference

InsightFace (probably a good option)

CLIP / SigLIP (probably a good option)

Base image model

SDXL (probably a good option)

Reason:

stable, flexible, easy to integrate locally

Prompt/runtime storage

JSON manifests for MVP (probably a good option)

Not DB first.

Just use files.

What “preview mode” means in the MVP

Do not overcomplicate this.

Preview mode is:

show inferred clusters

generate cheap rough previews

let user refine

only then render final images

Cheap previews can be:

low-res scene thumbnails

template-based rough renders

moodboard-style composites

The point is not quality.
The point is confidence before long render time.

Exact MVP UI
Screen 1 — Import

folder picker

thumbnail grid of imported images

“Analyze World” button

Screen 2 — Analyze

Three panels:

Left

Imported images

Center

Inferred clusters:

Character A

Character B

Character C

Backyard

Desk

Dog

Yellow table

Right

Preview scenes:

Dad at desk

Older child at table

Younger child in yard

Family couch

Controls:

exclude image

rename cluster

assign age rank

choose style

Screen 3 — Build World

review summary

click build

save world pack

Screen 4 — Generate

Prompt-less or low-prompt scene buttons:

Portrait

In environment

Pair scene

Storyboard set of 6

MVP generation modes

Keep it tiny.

Mode 1 — Portrait

Generate a clean portrait of one character from the world pack.

Mode 2 — Character + Environment

Example:

Jon at desk

Emily in backyard

Ben at yellow table

Mode 3 — Pair scene

Two characters in one scene.

Mode 4 — Storyboard 6-pack

Generate six scenes from templates:

desk at night

backyard daytime

couch scene

child at table

dog in yard

quiet family moment

That alone would feel like a product.

What proves success

The MVP wins if the user says:

“This actually understood my folder and gave me a usable world.”

Not perfect identity.
Not production cinema.

Just:

good clustering

good previews

good enough consistent scenes

usable output faster than Pinterest + Midjourney chaos

Suggested week-by-week plan
Week 1
Goal: ingest + infer + preview

Build:

folder import

image thumbnail grid

face clustering

environment clustering

basic cluster rename UI

style preset selector

Deliverable:

user drops folder, sees inferred world structure

Week 2
Goal: preview + world pack + first renders

Build:

preview scene generator

world pack manifest output

simple generation templates

render 3–6 scenes

Deliverable:

user can approve inferred world and get scene outputs

Week 3
Goal: polish and prove value

Build:

exclude/merge/split cluster controls

better prompt templates

save/load world pack

storyboard 6-pack mode

basic run history

Deliverable:

coherent demo that feels like a real workflow

Minimal data model
Character
{
  "id": "char_dad",
  "name": "Dad",
  "role": "parent",
  "reference_images": ["img_01.jpg", "img_03.jpg"],
  "attributes": {
    "age_rank": "adult"
  }
}
Environment
{
  "id": "env_backyard",
  "name": "Backyard",
  "reference_images": ["img_09.jpg", "img_11.jpg"]
}
World pack manifest
{
  "world_id": "family_world_001",
  "characters": ["char_dad", "char_emily", "char_ben"],
  "environments": ["env_backyard", "env_desk"],
  "style": "warm_cinematic_family"
}
Biggest risk in the MVP

The risk is simple:

without training, identity consistency may still be weak.

That’s okay for MVP as long as you position it correctly:

This version proves:

world inference

preview UX

reusable world pack

guided scene generation

If consistency is not good enough, the next phase adds:

optional LoRA training

stronger reference conditioning

richer controls

The actual MVP pitch

Not:

“Generate consistent cinematic universes.”

Too big.

Instead:

Drop a folder. Get a reusable visual world. Generate scenes from it.

That is understandable and demoable.

Why this is the right 2–3 week cut

Because it proves the novel parts:

folder-to-world inference

preview-before-commit

reusable world pack

scene generation from the pack

It avoids the heavy parts:

video

full identity training

3D

giant orchestration layer

-----

Implementation Plan
MVP objective

Build a local desktop app that lets a user:

Drop a folder of images

See inferred character/environment clusters

Refine that inference in a preview UI

Build a reusable world pack

Generate 6–12 guided scenes from that world pack

This MVP proves:

folder-to-world inference

preview-before-commit UX

reusable world pack

guided scene generation

It does not include:

video

3D

cloud sync

collaboration

full autonomous storytelling

mandatory LoRA training

1. Proposed architecture
High-level structure
finaljourney/
  apps/
    desktop/
    api/
  packages/
    core/
    schemas/
    ui/
  data/
    worlds/
    runs/
    cache/
  scripts/
Runtime model
Desktop app

UI shell for:

folder import

preview/refinement

world build

scene generation

React + Tauri (probably a good option)

Local API service

Python service responsible for:

media ingest

image analysis

clustering

prompt/template generation

image rendering orchestration

FastAPI (probably a good option)

Image generation backend

For MVP:

call a local generation service/workflow

keep this replaceable

ComfyUI backend integration (probably a good option)

2. Module breakdown
apps/desktop

Owns:

screens

user interactions

local state for current session

world pack browser

render request UI

Main modules:

apps/desktop/src/
  screens/
    ImportScreen.tsx
    AnalyzeScreen.tsx
    BuildWorldScreen.tsx
    GenerateScreen.tsx
  components/
    ImageGrid.tsx
    ClusterPanel.tsx
    PreviewPanel.tsx
    SceneCard.tsx
    StyleSelector.tsx
    WorldSummary.tsx
  hooks/
  api/
  state/
apps/api

Owns:

REST endpoints

orchestration

persistence calls

model calls

apps/api/
  app/
    main.py
    routes/
      ingest.py
      analyze.py
      worlds.py
      render.py
    services/
      ingest_service.py
      cluster_service.py
      preview_service.py
      world_builder.py
      render_service.py
    models/
    storage/
packages/core

Owns core domain logic:

cluster normalization

world pack assembly

scene template expansion

deterministic config shaping

packages/core/
  world/
  clustering/
  prompts/
  rendering/
packages/schemas

Owns JSON schemas / typed contracts.

packages/schemas/
  world_pack.schema.json
  character.schema.json
  environment.schema.json
  render_request.schema.json
  preview_scene.schema.json
3. Core data model
Imported asset
{
  "asset_id": "img_0001",
  "path": "/storyboard/01_dad_working.jpg",
  "media_type": "image",
  "width": 1536,
  "height": 2048
}
Character cluster
{
  "cluster_id": "char_001",
  "name": "Unlabeled Character 1",
  "kind": "character",
  "reference_asset_ids": ["img_0001", "img_0004"],
  "attributes": {
    "age_rank": "adult",
    "notes": ""
  }
}
Environment cluster
{
  "cluster_id": "env_001",
  "name": "Backyard",
  "kind": "environment",
  "reference_asset_ids": ["img_0010", "img_0011"]
}
Prop
{
  "prop_id": "prop_yellow_table",
  "name": "Yellow Table",
  "reference_asset_ids": ["img_0012"]
}
Style profile
{
  "style_id": "warm_cinematic_family",
  "preset": "warm_cinematic_family",
  "guidance_notes": [
    "natural light",
    "documentary family tone",
    "soft warm interiors"
  ]
}
World pack manifest
{
  "world_id": "world_20260310_001",
  "name": "Family World",
  "characters": ["char_dad", "char_emily", "char_ben"],
  "environments": ["env_backyard", "env_desk"],
  "props": ["prop_yellow_table", "prop_dog"],
  "style_profile": "warm_cinematic_family",
  "created_at": "2026-03-10T22:00:00Z"
}
4. Storage layout

Use filesystem storage for MVP.

data/
  cache/
    ingest/
    embeddings/
    thumbnails/
  worlds/
    world_20260310_001/
      manifest.json
      assets.json
      characters/
        char_dad.json
        char_emily.json
        char_ben.json
      environments/
        env_backyard.json
        env_desk.json
      props/
        yellow_table.json
        dog.json
      style/
        style_profile.json
      prompts/
        base_scene_templates.json
  runs/
    run_20260310_001/
      request.json
      outputs/
      metadata.json

This keeps everything inspectable and portable.

5. API design
Ingest
POST /ingest/folder

Input:

{
  "folder_path": "C:/Users/Jon/Pictures/storyboard"
}

Output:

{
  "session_id": "sess_001",
  "asset_count": 42
}
GET /ingest/{session_id}/assets

Returns imported assets and thumbnails.

Analyze
POST /analyze/{session_id}

Runs:

face clustering

environment clustering

style inference

prop detection

Output:

{
  "characters": [...],
  "environments": [...],
  "props": [...],
  "style_candidates": [...]
}
POST /analyze/{session_id}/refine

User adjustments:

rename cluster

exclude asset

merge cluster

split cluster

set age rank

Preview
POST /preview/{session_id}

Generates low-cost preview scenes.

Input:

{
  "style_preset": "warm_cinematic_family",
  "scene_templates": [
    "character_at_desk",
    "child_in_backyard",
    "family_couch"
  ]
}

Output:

{
  "preview_scenes": [...]
}
World build
POST /worlds/build

Input:

{
  "session_id": "sess_001",
  "world_name": "Family World"
}

Output:

{
  "world_id": "world_20260310_001",
  "path": "data/worlds/world_20260310_001"
}
GET /worlds/{world_id}

Returns manifest and metadata.

GET /worlds/{world_id}/summary

Returns world summary for UI.

Render
POST /render/scene

Input:

{
  "world_id": "world_20260310_001",
  "template": "character_in_environment",
  "characters": ["char_emily"],
  "environment": "env_backyard",
  "props": ["prop_yellow_table"]
}

Output:

{
  "run_id": "run_001",
  "status": "queued"
}
POST /render/storyboard

Input:

{
  "world_id": "world_20260310_001",
  "preset": "storyboard_6_pack"
}

Output:

{
  "run_id": "run_002",
  "status": "queued"
}
GET /render/runs/{run_id}

Returns run status and output paths.

6. Screen-by-screen UX
Screen 1 — Import

Purpose:

choose folder

confirm asset count

inspect raw imported images

UI elements:

folder picker

thumbnail grid

image count

“Analyze World” button

Key interaction:

user immediately sees that the app recognized their media

Screen 2 — Analyze

Purpose:

show inferred world structure

Layout:

left: imported image grid

center: inferred clusters

right: preview suggestions

Cluster sections:

Characters

Environments

Props

Style

Actions:

exclude image

rename character/environment

merge clusters

split cluster

mark older child / younger child

choose primary style preset

This is the most important screen in the MVP.

Screen 3 — Build World

Purpose:

confirm and compile world pack

UI:

world summary card

character list

environment list

style profile

“Build World” button

Output:

local world pack created

move user to generate screen

Screen 4 — Generate

Purpose:

generate scenes from world pack

Modes:

Portrait

In Environment

Pair Scene

Storyboard 6-Pack

Each generation request:

uses defaults heavily

allows a few optional overrides

Output grid:

rendered images

per-run metadata

rerun button

7. Rendering strategy for MVP
Preview rendering

Cheap, low-res, fast.

Purpose:

confidence, not final quality

Possible approach:

prompt-template preview only

optionally low-step SDXL renders

Final rendering

More expensive, but still bounded.

Use:

base model: SDXL (probably a good option)

structured prompt templates

reference-image-assisted conditioning where available (probably a good option)

No mandatory per-character training in MVP.

8. Prompt/template system

Use strongly typed template presets, not freeform prompting.

Example templates
portrait
{
  "id": "portrait",
  "prompt_template": "{character_name}, portrait, {style_preset}, high detail, natural lighting"
}
character_in_environment
{
  "id": "character_in_environment",
  "prompt_template": "{character_name} in {environment_name}, {style_preset}, candid cinematic composition"
}
pair_scene
{
  "id": "pair_scene",
  "prompt_template": "{character_a} and {character_b} in {environment_name}, {style_preset}, natural interaction"
}
storyboard_6_pack

Fixed scene set:

parent at desk

older child outside

younger child outside

dog in yard

family couch

quiet family moment

This keeps the MVP deterministic and demoable.

9. Concrete implementation order
Phase A — foundation

Build:

folder import

thumbnail generation

session model

API shell

desktop shell

Phase B — inference

Build:

face embeddings and clustering

image embeddings for environment clustering

style preset assignment

prop tagging placeholder

Phase C — preview UX

Build:

cluster cards

rename/exclude actions

scene preview list

refine action loop

Phase D — world pack

Build:

manifest serializer

save/load world pack

summary page

Phase E — rendering

Build:

template engine

render request system

output browser

storyboard 6-pack

10. First 10 tickets
Ticket 1 — Desktop shell + routing

Create Tauri/React app shell with routes:

/import

/analyze

/build

/generate

Acceptance:

app opens

route navigation works

Ticket 2 — FastAPI service bootstrap

Create API service with health endpoint and route structure.

Acceptance:

/health returns OK

desktop can call API

Ticket 3 — Folder ingest + thumbnail pipeline

User selects folder; backend enumerates images and creates thumbnails.

Acceptance:

session created

thumbnails generated

import grid populated

Ticket 4 — Asset metadata persistence

Persist imported asset metadata and session state to disk.

Acceptance:

session can reload without reimporting folder

Ticket 5 — Face clustering service

Use InsightFace (probably a good option) to cluster recurring faces.

Acceptance:

detected character clusters returned with reference asset lists

Ticket 6 — Environment clustering service

Use CLIP/SigLIP embeddings (probably a good option) to cluster similar environments.

Acceptance:

environment clusters returned separately from characters

Ticket 7 — Analyze screen with editable clusters

Display clusters in UI with rename and exclude actions.

Acceptance:

user can rename clusters

user can exclude assets

edits persist in session state

Ticket 8 — Preview scene generator

Generate lightweight preview scene suggestions from cluster state.

Acceptance:

preview panel shows 3–6 suggested scenes

previews update after refinement

Ticket 9 — World pack builder

Serialize selected clusters and style preset into filesystem world pack.

Acceptance:

world folder created

manifest and child objects saved

world reload works

Ticket 10 — Render pipeline + storyboard 6-pack

Generate scenes from a world pack using template presets.

Acceptance:

user selects storyboard 6-pack

run executes

output images appear in generate screen

run metadata stored

11. Suggested backlog after first 10 tickets
Ticket 11

Merge/split cluster controls

Ticket 12

Age-rank metadata for child ordering

Ticket 13

Prop detection and tagging

Ticket 14

Style preset editor

Ticket 15

Run history browser

Ticket 16

World pack import/export

Ticket 17

Reference-strength controls for generation

Ticket 18

Optional LoRA training spike

12. Risks and mitigations
Risk 1 — Identity consistency too weak

Mitigation:

position MVP as “world inference + guided generation”

keep LoRA out of first cut

add optional training as next phase

Risk 2 — Preview generation too slow

Mitigation:

use low-res or metadata-driven preview tiles

decouple preview from final render quality

Risk 3 — Clustering errors frustrate users

Mitigation:

build simple correction affordances early:

rename

exclude

merge/split later

Risk 4 — ComfyUI integration complexity

Mitigation:

isolate rendering adapter behind one service interface

keep render backend swappable

13. MVP success criteria

The MVP is successful if a user can say:

I dropped in a folder, the app mostly understood the people and places, I corrected a few things, built a world pack, and got a reusable set of scenes out of it.

Not:

perfect identity

perfect world reconstruction

perfect cinema

Just:

understandable

guided

faster and more structured than Pinterest + MidJourney chaos

14. Recommendation on whether this fits Orket

This MVP can fit Orket only if you treat it as:

an AI capability pipeline with reusable artifacts

It does not fit if Orket’s purpose stays tightly centered on requirement gathering, orchestration, and engineering workflows only.

So for now, I would capture it as one of these:

Independent product concept

Experimental Orket extension

Incubator project adjacent to Orket

That keeps the idea alive without forcing it into the core prematurely.

15. Final recommended MVP stack
Frontend

React

Tauri (probably a good option)

Backend

Python

FastAPI (probably a good option)

Local inference

InsightFace (probably a good option)

CLIP or SigLIP (probably a good option)

Rendering

ComfyUI adapter (probably a good option)

SDXL (probably a good option)

Persistence

filesystem JSON manifests (probably a good option)

Packaging

local desktop app with bundled Python service (probably a good option)

16. The shortest summary

FinalJourney MVP is:

Drop a folder.
See the inferred world.
Refine it.
Build a world pack.
Generate scenes from it.