# Neuro Atlas site

The redesigned human and mouse hubs introduce a brain-surface illustration from
existing atlas geometry, a clear starting point, searchable topic cards, category
filters, bilingual navigation, and a linked anatomical map. Mouse cards identify
the atlas age and distinguish 2D sections from 3D viewers.

Viewer copies receive a responsive reading panel, accessible panel controls,
viewport metadata, and navigation back to their species hub. Scientific content,
embedded meshes, and the original viewer controls remain in the source outputs.
This worktree is a local redesign preview; no deployment has been performed.

## Build and preview

Run both commands from the repository root, in this order:

```powershell
rtk proxy py -3.13 site/build_hub.py
rtk proxy py -3.13 site/build_mouse.py
rtk proxy py -3.13 -m http.server 8767 --bind 127.0.0.1 --directory site/dist
```

Open [the human hub](http://localhost:8767/) or
[the mouse hub](http://localhost:8767/mouse/).
`build_hub.py` clears the previous `site/dist/`, including its mouse section;
`build_mouse.py` then adds the mouse pages. The generated directory is gitignored.
Building uses the tracked viewer outputs and needs no atlas download.

## Architecture

- `build_hub.py` owns the human registry, anatomical SVG map, 404 page, and copies
  of the 12 human viewers.
- `build_mouse.py` owns the mouse registry and map, copies three pathway viewers,
  and preserves the seven legacy viewers under `mouse/P56/`, `mouse/P15/`, and
  `mouse/P14/` so their cross-links and slice query parameters continue to work.
- `hub_design.py`, `brain_art.py`, and `templates/atlas.*` produce both homepages
  with inline CSS, JavaScript, and SVG.
- `viewer_upgrade.py` adds the interface only to assembled viewer copies,
  fits recognized 3D scenes into the available workspace, and provides a reset
  view control. Existing pointer picking remains relative to the canvas.

The site layer reads built files; it does not import `human_atlas` or
`mouse_atlas`. Those packages remain independent. Each viewer keeps its own
embedded three.js, OrbitControls, mesh/image data, and injected interface; no CDN
or neighboring runtime asset is required.

Source viewers are HTML fragments with no enclosing document tags. Build scripts
prepend charset and viewport metadata, then append navigation, language sync, and
the viewer interface. They also repair the mouse hippocampus section link and
keep the two orphan human viewers' cross-links within this site. Original outputs
are never rewritten. The limbic and whole-brain source outputs have no remaining
generators and cannot be regenerated here.

## Content and language

Add new topics to the relevant registry with bilingual names, pathway summaries,
source labels, and optional anatomical hotspots. Topic cards and filters are
assembled from that registry. The map is a schematic navigation diagram; the hero
uses atlas surface geometry. Pathway viewers combine atlas structures with
schematic teaching elements, as described by their existing source notes.

The site defaults to Traditional Chinese and stores the language in
`localStorage.neuroLang`. Bilingual viewers inherit that choice through their own
language control; older single-language viewers keep their existing content.

## Redesign validation

The assembled site contains two hubs, 22 viewers (19 in 3D and three 2D plates),
and a 404 page. All viewer routes were loaded in Chromium without application
errors. Generated relative links, viewport metadata, unique element IDs, and
inline JavaScript syntax were checked. Original viewer outputs are unchanged.

Browser checks cover Chinese/English search, category filters, empty/reset states,
language persistence, widths from 320 to 1440 pixels, exclusive viewer panels,
layer toggles, zoom/reset, and canvas-relative pointer coordinates. The 2D plates
retain their existing purpose-built interface; the new reading rail applies to
the 3D viewers. Existing atlas and scientific-content limitations still apply.
