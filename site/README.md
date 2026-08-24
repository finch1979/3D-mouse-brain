# site/ — the Neuro Atlas hub

**Live: https://neuro-atlas.pages.dev/**

One front page for every human nervous-system viewer in this repo: a clickable
nervous-system map on the left, a grouped system list on the right, and a
`規劃中` block for the systems still to come. Bilingual (中文 default), same
dark/mono design tokens as the viewers.

Unlike `mouse/` and `human/`, this is not a package — it is one script.
It must not import `mouse_atlas` or `human_atlas`; it only reads their built
outputs.

## Build and deploy

```bash
py -3.13 site/build_hub.py
npx wrangler pages deploy site/dist --project-name=neuro-atlas
```

`site/dist/` is gitignored — it is the hub page plus a *copy* of every viewer,
about 43 MB of duplicates. Rebuild it rather than committing it. Wrangler
hashes files, so redeploying after a change to one viewer only uploads that
viewer.

```
site/dist/
  index.html                 the hub
  404.html
  auditory/index.html        \
  visual/index.html           |
  olfactory/index.html        |  a copy of each viewer,
  limbic/index.html           |  with navigation injected
  motor-hippocampus/index.html|
  pain/index.html            /
```

## Adding a system

Add one entry to `SYSTEMS` in [build_hub.py](build_hub.py) — slug, source path,
accent colour, group, and the bilingual name/short/route/fact/source strings —
then rebuild and redeploy. If it has an obvious anatomical home, give it a
`hotspot` and draw that shape in `build_svg()`; otherwise set `hotspot: None`
and it is listed but not on the map. Moving something out of `PLANNED` into
`SYSTEMS` is the same edit in reverse.

## Two things worth knowing before you change this

**The viewers are body fragments.** Every `*/outputs/**.html` in this repo
starts at `<title>` and ends at `</script>` — no doctype, no `<html>`, no
`<head>`, no charset meta. So the injector *appends* the nav markup and
*prepends* a charset meta. There is no `</body>` to anchor on, and
`build_hub.py` asserts the `</script>` ending rather than silently shipping a
page with no way back to the hub.

**Injection happens on the copy, never the original.** `human/outputs/limbic/`
and `human/outputs/whole_brain/` are orphans — the scripts that built them are
gone, so they cannot be regenerated. Post-processing the copy in `dist/` is
what makes them work here, and it also leaves the six original per-system
deployments untouched:

| | |
|---|---|
| 聽覺 | https://human-auditory-system.pages.dev/ |
| 視覺 | https://human-visual-system.pages.dev/ |
| 嗅覺 | https://human-olfactory-system.pages.dev/ |
| 痛覺 | https://human-pain-system.pages.dev/ |
| 邊緣系統 | https://human-limbic-system.pages.dev/ |
| 運動皮質+海馬迴 | https://human-brain-motor-cortex-hippocampus.pages.dev/ |

Those still work and are not redirects. The hub is an addition, not a move.

## Language

The hub defaults to 中文 and writes the choice to `localStorage.neuroLang`.
Because everything now shares one origin, the injected snippet in the four
bilingual viewers reads that key and clicks their own `#langToggle` once if it
says `zh` — so a language picked on the hub carries through the site. The two
Allen-atlas pages have no i18n and are unaffected.
