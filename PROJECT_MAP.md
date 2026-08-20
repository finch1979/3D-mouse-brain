# Project map

```
mouse brain/
├─ README.md              what this repo is, install, how to run a script
├─ AGENTS.md               conventions for adding to this repo
├─ PROJECT_MAP.md          this file
├─ .gitignore
│
├─ mouse/                  independent mouse sub-project
│  ├─ pyproject.toml         `mouse_atlas` package definition
│  ├─ src/mouse_atlas/
│  │  ├─ fetch/                talks to the Allen Brain Map API only
│  │  │  ├─ atlas_3d.py          downloads CCFv3 structure meshes (.obj)
│  │  │  └─ atlas_plate.py       downloads coronal reference-atlas plates
│  │  ├─ build/                 turns fetched/generated data into finished HTML
│  │  │  ├─ plate_atlas.py       2D interactive plate viewers (P56/P14/P15)
│  │  │  ├─ demba_p15.py         P15 coronal slice viewer (DeMBA, BrainGlobe)
│  │  │  └─ demba_p15_3d.py      P15 3D structure viewer (DeMBA, BrainGlobe)
│  │  └─ common/                shared path & config helpers (paths.py, config.py)
│  ├─ configs/                per-mouse-age atlas settings (p14/p15/p56.yaml)
│  ├─ data/cache/             raw Allen API responses (gitignored, regenerable)
│  │  ├─ P14/
│  │  └─ P56/
│  └─ outputs/                the built deliverables — open these .html directly
│     ├─ P14/                   2D sagittal plate (Developing Mouse Atlas)
│     ├─ P15/                   2D coronal plate + 3D viewer (DeMBA)
│     └─ P56/                   2D coronal plate + 3D viewers (adult CCFv3)
│
├─ human/                  independent human sub-project
│  ├─ pyproject.toml         `human_atlas` package definition
│  ├─ src/human_atlas/
│  │  ├─ build/
│  │  │  └─ human_auditory.py   builds the 聽覺系統 auditory/vestibular pathway viewer
│  │  ├─ render/
│  │  │  └─ bake_meshes.py      .obj -> base64 REGIONS blob (viewer mesh embedding)
│  │  └─ common/                shared path helpers (paths.py)
│  ├─ data/cache/             raw downloaded atlas volumes (gitignored, regenerable)
│  │  └─ human_auditory/
│  └─ outputs/                the built deliverables — open these .html directly
│     ├─ whole_brain/
│     ├─ limbic/
│     └─ auditory_system/       聽覺系統 (auditory + vestibular pathway viewer)
│
├─ web/lib/                vendored three.js + OrbitControls (reference copy;
│                           every viewer inlines its own, nothing loads this)
│
├─ tests/                  (reserved)
├─ docs/
│  ├─ architecture/          (reserved)
│  └─ workflows/             (reserved)
├─ scripts/                (reserved for one-off/dev-utility scripts)
│
└─ external/
   └─ brainglobe-atlasapi/   vendored third-party package (gitignored)
```

`mouse/` and `human/` are intentionally independent — no shared Python
package. Only `web/lib/` and `external/` are shared at the repo root.
