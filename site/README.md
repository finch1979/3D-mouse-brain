# Neuro Atlas site

The redesigned human and mouse hubs introduce a brain-surface illustration from
existing atlas geometry, a clear starting point, searchable topic cards, category
filters, bilingual navigation, and an anatomical topic index. Mouse cards identify
the atlas age and distinguish 2D sections from 3D viewers.

Viewer copies receive a responsive reading panel, accessible panel controls,
viewport metadata, and navigation back to their species hub. Scientific content,
embedded meshes, and the original viewer controls remain in the source outputs.
Production site: [Neuro Atlas](https://neuro-atlas.pages.dev/) and
[Mouse Atlas](https://neuro-atlas.pages.dev/mouse/).

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

## Production deployment

The Cloudflare Pages project is `neuro-atlas`, with `main` as its production
branch. It uses Direct Upload; pushing GitHub alone does not deploy the site.
After building both species and checking the output, deploy from a clean checkout
of the release commit:

```powershell
rtk proxy npx wrangler pages deploy site/dist --project-name=neuro-atlas --branch=main
```

Verify both hubs and their viewer routes at the production URL after deployment.
Previous production deployments remain available in Cloudflare Pages for rollback.

## Architecture

The adult mouse extension adds nine systems: auditory, somatosensory, gustatory,
vestibular, cerebellum, limbic, pain, sleep and autonomic. The assembled site now
has 34 HTML pages, including 28 shared 3D viewers. Existing numbered mouse entries
keep their numbers; new entries follow them. `P56/pathway_meshes/systems.json`
provides the new hub entries without importing atlas packages into site assembly.

Before site assembly, new viewers can be reproduced from this checkout with:

```powershell
rtk proxy py -3.13 scripts/mouse_systems.py fetch
rtk proxy py -3.13 scripts/mouse_systems.py build
```

Fetch and build are separate; the build is offline. The launcher deliberately
selects this checkout's package even when another C: copy is installed. Individual
systems accept `build auditory`, etc., and have their own `mouse_atlas.build.mouse_*`
module entrypoints. Scientific scope, connection evidence and data terms are in
`docs/architecture/mouse-systems-evidence.md`; source checksums, atlas IDs,
hemisphere-aware anchors and citation IDs accompany each output in its manifest.
Approximate cell-population markers are not segmented anatomy. No conduction
timing animation is enabled. Raw meshes retain Allen Institute data rights.

- `build_hub.py` owns the human registry, anatomical index, 404 page, and copies
  of the 12 human viewers.
- `build_mouse.py` owns the mouse registry and map, copies three pathway viewers,
  and preserves the seven legacy viewers under `mouse/P56/`, `mouse/P15/`, and
  `mouse/P14/` so their cross-links and slice query parameters continue to work.
- `hub_design.py`, `brain_art.py`, and `templates/atlas.*` produce both homepages
  with inline CSS, JavaScript, and SVG.
- `navigation_map.py` provides the shared numbered index. Its brain illustration
  is a uniformly scaled atlas projection with filled lighting contours. Topic
  links are grouped by brain structures, sensory entry points, and body connections;
  their numbers match the cards. They are navigation controls, not anatomical
  attachment points. Both desktop and mobile show the index.
- `viewer_upgrade.py` adds the interface only to assembled viewer copies,
  fits recognized 3D scenes into the available workspace, and provides a reset
  view control. Existing pointer picking remains relative to the canvas.
- `templates/scene.js` and `scene.css` style the actual 3D scene and its projected
  annotations. They are inlined into the copied viewer, alongside its existing
  application script; three.js and OrbitControls remain unchanged.

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
source labels, and an optional hotspot to include it in the anatomical index.
Topic cards and filters are assembled from that registry. The index and hero use
atlas surface geometry; the index preserves the brain's projected proportions
without a schematic body drawing. Planned topics remain in their separate list.
Pathway viewers combine atlas structures with
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

The anatomical index was checked in both languages at 320, 390, 800, 1024 and
1440 pixels on both hubs. All 17 navigation entries match their card numbers and
destinations, with no label overlap or horizontal overflow. Keyboard focus also
highlights the matching card, and Enter opens the existing viewer route.

## Anatomical layer design

Open [the visual-system layer panel](http://localhost:8767/visual/?panel=layers)
to compare the new scene with the earlier renderer. The layer panel provides
anatomy/pathway presentation presets, brain-surface opacity, and key/detailed/off
annotation modes. The exact atlas shell receives a transparent rim material;
the approximate expanded head shell starts hidden. Tissue, pathway colors and
schematic wireframe markers retain their original identities.

Projected callouts replace overlapping 3D text. Structure annotations end at an
exact triangle intersection on their own visible tissue, including named brain
endpoints in pathway viewers. A cached object-ID pass finds exposed surfaces;
a raycast against all tissue confirms the first intersection and rejects points
behind another region. Hemisphere checks keep bilateral pathway labels on their
original side. Context shells are excluded from the surface check.

Warm or cyan annotation ink contrasts with the original tissue palette, and a
dark marker outline stays legible on lit surfaces. The hippocampus opens from an
anterior-oblique angle exposing CA1, CA2, CA3 and DG. Only the camera changes.
Occluded or very small surfaces have no leader; their node-index entries explain
how to rotate, zoom in or hide overlapping layers. Hidden pathways lose their
annotations. Shared branch labels are deduplicated, and the index remains usable
when screen space limits callouts. Schematic waypoints, tract-level aliases and
the limbic Papez loop retain their original coordinates and visibility controls.

The orientation indicator follows each source's coordinate convention. The
millimeter reference bar is calibrated at the orbit target's depth and updates
with perspective zoom; it is not a universal ruler for every depth in the scene.
The pain viewer now starts in its existing true-scale mode. Its optional native
compressed teaching mode remains available, with a visible note and no mm bar.

On phones (up to 760 CSS pixels wide), annotations start hidden so the model
is unobstructed. "Show nodes" reveals compact numbered markers with 44-pixel
touch targets; tapping one opens a dismissible detail card. Full names remain
available in the layer panel's node index. Markers stay at their projected
anatomical points, and colliding markers are omitted. Desktop callouts keep
their existing layout. An explicit annotation choice survives resizing;
otherwise the default follows the viewport.

The schematic-node notice and proportions note live in the reading guide,
instead of overlaying the brain. Their bilingual explanations remain available
when the guide is opened.

Run the mobile regression against an assembled site with:

```powershell
rtk proxy py -3.13 tests/check_mobile_annotations.py --site site/dist
```

All 101 atlas regions across 19 3D viewers retain byte-identical position, normal,
and triangle-index payloads. No atlas vertices or anatomical transforms are
changed by the styling layer. Browser checks cover all 19 renderers, annotation
collisions, hidden branches, layer presets, language changes, mobile placement,
and the pain/Papez mode controls. Surface checks additionally cover six atlas-only
viewers and thirteen pathway viewers at multiple angles, with independent
first-hit and hemisphere verification. Three 2D plates retain their existing layout.
