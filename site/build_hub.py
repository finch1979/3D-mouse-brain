"""Build the Neuro Atlas hub — one page holding every human nervous-system viewer.

Assembles `site/dist/`:

    index.html            the hub: clickable nervous-system map + system list
    404.html              small "not found" that links home
    <slug>/index.html     a copy of each viewer, with navigation injected

Every viewer output in this repo is a *body fragment* — it starts at `<title>`
and ends at `</script>`, with no doctype/html/head/body tags and no charset
meta. So the injector appends the nav markup at the end of the copy and
prepends charset and viewport metadata at the front. It works on the copy in `dist/`, never
on the original, which matters because `limbic/` and `whole_brain/` are orphan
outputs with no build script left in the repo — they cannot be regenerated.

Adding a system later = one entry in SYSTEMS (plus a hotspot in the map if it
has an obvious anatomical home), then rebuild and redeploy.

    py -3.13 site/build_hub.py
    npx wrangler pages deploy site/dist --project-name=neuro-atlas
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

from hub_design import render_hub
from viewer_upgrade import prepare_viewer, viewer_upgrade

SITE_DIR = Path(__file__).resolve().parent
REPO = SITE_DIR.parent
DIST = SITE_DIR / "dist"

# --- the registry -----------------------------------------------------------
# `src` is repo-relative. `accent` is the viewer's own accent colour where it
# has one, so a card and its page match. `hotspot` names the map element that
# links here (None = listed but not on the map).
SYSTEMS = [
    {
        "slug": "auditory",
        "src": "human/outputs/auditory_system/human_auditory_system_3d.html",
        "accent": "#e0a458", "group": "input", "hotspot": "ear",
        "name": {"en": "Auditory &amp; vestibular", "zh": "聽覺與前庭系統"},
        "short": {"en": "Hearing", "zh": "聽覺"},
        "route": {"en": "cochlea → brainstem → MGB → temporal cortex",
                  "zh": "耳蝸 → 腦幹 → 內側膝狀體 → 顳葉"},
        "fact": {"en": "Full decussation at the trapezoid body — each ear reaches both cortices",
                 "zh": "在腦幹梯形體完全交叉,每隻耳朵的訊息都會抵達兩側皮質"},
        "source": "MNI152 · Harvard-Oxford",
    },
    {
        "slug": "visual",
        "src": "human/outputs/visual_system/human_visual_system_3d.html",
        "accent": "#5a8fe0", "group": "input", "hotspot": "eye",
        "name": {"en": "Visual system", "zh": "視覺系統"},
        "short": {"en": "Vision", "zh": "視覺"},
        "route": {"en": "retina → optic chiasm → LGN → V1",
                  "zh": "視網膜 → 視交叉 → 外側膝狀體 → 距狀溝 V1"},
        "fact": {"en": "Partial decussation — nasal fibres cross, temporal fibres stay",
                 "zh": "視交叉只有一半纖維交叉——鼻側交叉、顳側不交叉"},
        "source": "MNI152 · Harvard-Oxford",
    },
    {
        "slug": "olfactory",
        "src": "human/outputs/olfactory_system/human_olfactory_system_3d.html",
        "accent": "#8fbf7f", "group": "input", "hotspot": "nose",
        "name": {"en": "Olfactory system", "zh": "嗅覺系統"},
        "short": {"en": "Smell", "zh": "嗅覺"},
        "route": {"en": "epithelium → bulb → piriform cortex &amp; amygdala",
                  "zh": "嗅上皮 → 嗅球 → 梨狀皮質與杏仁核"},
        "fact": {"en": "The only sense that skips the thalamus — and never crosses the midline",
                 "zh": "唯一不經視丘直達皮質的感覺,而且完全同側、不交叉"},
        "source": "MNI152 · AAL3",
    },
    {
        "slug": "limbic",
        "src": "human/outputs/limbic/human_limbic_3d.html",
        "accent": "#c9a8ff", "group": "central", "hotspot": "limbic",
        "name": {"en": "Limbic system", "zh": "邊緣系統"},
        "short": {"en": "Limbic", "zh": "邊緣"},
        "route": {"en": "hippocampus · amygdala · cingulate · hypothalamus",
                  "zh": "海馬迴 · 杏仁核 · 扣帶迴 · 下視丘"},
        "fact": {"en": "The six limbic structures resolvable at this atlas's 500µm resolution",
                 "zh": "在此圖譜 500µm 解析度下可分辨出的六個邊緣結構"},
        "source": "Allen Human Brain Atlas",
    },
    {
        "slug": "motor-hippocampus",
        "src": "human/outputs/whole_brain/human_brain_3d.html",
        "accent": "#9fb3c8", "group": "central", "hotspot": "cortex",
        "name": {"en": "Motor cortex &amp; hippocampus", "zh": "運動皮質與海馬迴"},
        "short": {"en": "Cortex", "zh": "皮質"},
        "route": {"en": "precentral gyrus + hippocampal formation, in a translucent shell",
                  "zh": "中央前回與海馬迴,置於半透明全腦殼內"},
        "fact": {"en": "Where a surface structure and a deep one actually sit relative to each other",
                 "zh": "皮質表面結構與深部結構彼此的相對位置"},
        "source": "Allen Human Brain Atlas",
    },
    {
        "slug": "pain",
        "src": "human/outputs/pain_system/human_pain_system_3d.html",
        "accent": "#e0705a", "group": "output", "hotspot": "cord",
        "name": {"en": "Pain · reflex · motor", "zh": "痛覺 · 反射 · 運動"},
        "short": {"en": "Pain", "zh": "痛覺"},
        "route": {"en": "sole → spinal cord → cortex → back down to muscle",
                  "zh": "腳底 → 脊髓 → 皮質 → 再下行到肌肉"},
        "fact": {"en": "Four midline crossings in four different places — cord for pain, medulla for touch and motor",
                 "zh": "四個中線交叉發生在四個不同位置——痛覺在脊髓,觸覺與運動在延髓"},
        "source": "MNI152 · AAL3 · PAM50",
    },
    {
        "slug": "somatosensory",
        "src": "human/outputs/somatosensory_system/human_somatosensory_system_3d.html",
        "accent": "#c9a8ff", "group": "input", "hotspot": "hand",
        "name": {"en": "Somatosensory system", "zh": "體感覺系統"},
        "short": {"en": "Touch", "zh": "體感"},
        "route": {"en": "fingertip → cuneate nucleus → VPL → S1",
                  "zh": "指尖 → 楔狀核 → VPL → S1"},
        "fact": {"en": "Uncrossed for the entire cord — crosses in the medulla, the opposite of pain",
                 "zh": "整條脊髓不交叉,到延髓才交叉——與痛覺完全相反"},
        "source": "MNI152 · AAL3 · PAM50",
    },
    {
        "slug": "gustatory",
        "src": "human/outputs/gustatory_system/human_gustatory_system_3d.html",
        "accent": "#e08fb0", "group": "input", "hotspot": "tongue",
        "name": {"en": "Gustatory system", "zh": "味覺系統"},
        "short": {"en": "Taste", "zh": "味覺"},
        "route": {"en": "tongue → solitary nucleus → VPMpc → insula",
                  "zh": "舌 → 孤束核 → VPMpc → 島葉"},
        "fact": {"en": "Three cranial nerves, one relay — and barely any midline crossing",
                 "zh": "三條腦神經、一個中繼站,而且幾乎不越過中線"},
        "source": "MNI152 · AAL3",
    },
    {
        "slug": "vestibular",
        "src": "human/outputs/vestibular_system/human_vestibular_system_3d.html",
        "accent": "#5ac0c0", "group": "input", "hotspot": "vestibular",
        "name": {"en": "Vestibular system", "zh": "前庭系統"},
        "short": {"en": "Balance", "zh": "平衡"},
        "route": {"en": "canals → vestibular nuclei → cerebellum · eyes · cortex · cord",
                  "zh": "半規管 → 前庭核 → 小腦 · 眼睛 · 皮質 · 脊髓"},
        "fact": {"en": "Four outputs at once — balance is felt, not seen",
                 "zh": "一次分出四路——平衡是感覺出來的,不是看到的"},
        "source": "MNI152 · Diedrichsen 2009 · AAL3 · PAM50",
    },
    {
        "slug": "cerebellum",
        "src": "human/outputs/cerebellum_system/human_cerebellum_system_3d.html",
        "accent": "#6f8fe0", "group": "central", "hotspot": "cerebellum",
        "name": {"en": "Cerebellum &amp; motor control", "zh": "小腦與運動控制"},
        "short": {"en": "Cerebellum", "zh": "小腦"},
        "route": {"en": "M1 → pons → cerebellum → red nucleus/VL → back to M1",
                  "zh": "M1 → 橋腦 → 小腦 → 紅核/VL → 回到 M1"},
        "fact": {"en": "A loop, not a one-way street — it crosses twice, so right cerebellum steers right body",
                 "zh": "它是迴路不是單行道——交叉兩次,右小腦掌管右側身體"},
        "source": "MNI152 · Diedrichsen 2009 · AAL3 · PAM50",
    },
    {
        "slug": "sleep",
        "src": "human/outputs/sleep_arousal/human_sleep_arousal_3d.html",
        "accent": "#9a8fe8", "group": "central", "hotspot": "brainstem",
        "name": {"en": "Sleep &amp; arousal", "zh": "睡眠與覺醒"},
        "short": {"en": "Sleep", "zh": "睡眠"},
        "route": {"en": "reticular formation → thalamus → cortex · LC · VLPO switch",
                  "zh": "網狀結構 → 視丘 → 皮質 · 藍斑核 · VLPO 開關"},
        "fact": {"en": "Sleep is a switch, not a dimmer — VLPO actively inhibits every arousal nucleus",
                 "zh": "睡眠是開關不是調光器——VLPO 主動抑制所有覺醒核"},
        "source": "MNI152 · AAL3 · Harvard-Oxford",
    },
    {
        "slug": "autonomic",
        "src": "human/outputs/autonomic_system/human_autonomic_system_3d.html",
        "accent": "#7fc99a", "group": "output", "hotspot": "viscera",
        "name": {"en": "Autonomic system", "zh": "自律神經系統"},
        "short": {"en": "Autonomic", "zh": "自律"},
        "route": {"en": "hypothalamus → sympathetic chain · vagus → organs",
                  "zh": "下視丘 → 交感神經鏈 · 迷走神經 → 內臟"},
        "fact": {"en": "The vagus is ~80% sensory fibres — the body reports upward more than the brain commands",
                 "zh": "迷走神經約 80% 是感覺纖維——身體上報的比大腦下令的多"},
        "source": "MNI152 · PAM50",
    },
]

PLANNED = [
]

GROUPS = [
    ("input", {"en": "Sensory input", "zh": "感覺輸入"},
     {"en": "how the outside world gets in", "zh": "外界如何進入神經系統"}),
    ("central", {"en": "Central structures", "zh": "中樞結構"},
     {"en": "what the signal arrives at", "zh": "訊號抵達的地方"}),
    ("output", {"en": "Sensory → motor loop", "zh": "感覺 → 運動整合"},
     {"en": "the round trip, and back out to muscle", "zh": "完整的來回,一直到肌肉"}),
]


def bi(d: dict, extra: str = "") -> str:
    """A bilingual text node: JS swaps innerHTML between the two attributes."""
    return f'data-en="{d["en"]}" data-zh="{d["zh"]}"{extra}'


# --- the map ----------------------------------------------------------------
# A stylised sagittal brain (facing left) over a minimal body. NOT atlas
# geometry - the page says so out loud. viewBox is 0 0 440 660 and the figure
# stays inside x 90..320 so the label gutters never collide with it.
#
# Map labels are SHORT; the full name is on the card that lights up with the
# hotspot. Full names overflow the gutters, badly so in English.
def cerebrum_path(cx=208.0, cy=148.0, rx=104.0, ry=74.0,
                  lobes=9, depth=0.032, steps=200) -> str:
    """The cerebrum outline, generated rather than hand-drawn.

    An ellipse with a sinusoidal scallop on the dorsal rim, fading to nothing
    at the base, which is also flattened. Hand-tuned beziers kept reading as a
    featureless blob; the scallop is what makes it read as cortex.
    """
    pts = []
    for i in range(steps + 1):
        th = 2 * math.pi * i / steps
        up = max(0.0, math.sin(th))              # 1 at the vertex, 0 at the base
        r = 1 + depth * up * math.sin(lobes * th + 0.6)
        dx = rx * r * math.cos(th)
        dy = ry * r * math.sin(th)
        if dy < 0:
            dy *= 0.52                           # flatten the underside
        pts.append((cx + dx, cy - dy))
    return (f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
            + " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:]) + " Z")


def build_svg() -> str:
    live = {s["hotspot"]: s for s in SYSTEMS if s["hotspot"]}
    soon = {p["hotspot"]: p for p in PLANNED if p["hotspot"]}

    def hot(key: str, body: str, label_xy: tuple[float, float], anchor: str = "start") -> str:
        """One hotspot: <a> if the system exists, inert <g> if it is planned."""
        x, y = label_xy
        src = live.get(key) or soon[key]
        lab = (f'<text class="hot-label" x="{x}" y="{y}" text-anchor="{anchor}" '
               f'{bi(src["short"])}></text>')
        if key in live:
            return (f'<a class="hot" href="./{live[key]["slug"]}/" data-slug="{live[key]["slug"]}" '
                    f'style="--accent:{live[key]["accent"]}">{body}{lab}</a>')
        return f'<g class="hot hot--soon" data-soon="{key}">{body}{lab}</g>'

    return f"""
<svg id="map" viewBox="0 0 440 660" role="img" aria-labelledby="mapTitle">
  <title id="mapTitle" data-en="Nervous system navigation map" data-zh="神經系統導覽圖"></title>

  <!-- ---------- static frame: trunk, limbs, sulci ---------- -->
  <g class="frame">
    <path class="trunk" d="M 158 314 C 146 342 143 372 150 400
      C 155 421 159 434 161 444 L 251 444 C 253 434 257 421 262 400
      C 269 372 266 342 254 314 Z" />
    <path class="shoulder" d="M 160 316 C 190 306 222 306 252 316" />
    <path class="limb" d="M 158 322 L 116 388 L 100 420" />
    <path class="limb" d="M 190 444 L 180 596" />
    <path class="limb" d="M 226 444 L 240 596" />
    <path class="foot" d="M 164 600 L 194 600" />
    <path class="foot" d="M 228 600 L 258 600" />
  </g>

  <!-- ---------- hotspots ---------- -->
  {hot("cortex", f'<path class="hit-brain" d="{cerebrum_path()}" />'
                 '<ellipse class="hit-brain" cx="168" cy="182" rx="46" ry="20" '
                 'transform="rotate(-13 168 182)" />'
                 '<path class="leader" d="M 292 100 L 330 92" />', (336, 96), "start")}

  <!-- sulci sit on top of the cerebrum fill, and must not eat its hover -->
  <g class="sulci">
    <path d="M 140 126 C 168 146 190 168 196 194" />
    <path d="M 196 90 C 200 120 212 144 236 158" />
    <path d="M 256 96 C 250 126 252 150 266 166" />
  </g>

  {hot("limbic", '<ellipse class="hit-blob" cx="204" cy="162" rx="42" ry="22" />',
         (204, 167), "middle")}

  {hot("cerebellum", '<ellipse class="hit-blob" cx="290" cy="202" rx="32" ry="24" />'
        '<g class="foliate">'
        '<path d="M 266 192 C 282 188 300 192 314 200" />'
        '<path d="M 264 206 C 280 204 300 208 314 214" />'
        '</g>', (334, 198), "start")}

  {hot("brainstem", '<path class="hit-blob" d="M 217 180 C 219 216 216 252 218 298 '
        'L 234 298 C 234 252 233 216 235 178 Z" />'
        '<path class="leader" d="M 214 268 L 186 276" />', (182, 280), "end")}

  {hot("eye", '<circle class="hit-dot" cx="70" cy="162" r="13" />'
        '<circle class="pupil" cx="70" cy="162" r="4.5" />'
        '<path class="leader" d="M 83 164 L 108 170" />', (70, 136), "middle")}

  {hot("nose", '<path class="hit-dot-p" d="M 56 214 L 80 202 L 80 226 Z" />'
        '<path class="leader" d="M 82 214 L 120 198" />', (68, 246), "middle")}

  {hot("tongue", '<path class="hit-dot-p" d="M 74 266 '
        'C 90 260 110 264 114 272 C 108 280 86 282 74 276 Z" />', (94, 300), "middle")}

  {hot("ear", '<path class="hit-dot-p" d="M 250 230 '
        'C 268 224 280 236 278 252 C 276 268 262 276 250 272" />'
        '<path class="leader" d="M 252 242 L 234 214" />', (296, 260), "start")}

  {hot("vestibular", '<circle class="hit-dot" cx="263" cy="288" r="9" />'
        '<circle class="pupil" cx="263" cy="288" r="3.5" />'
        '<path class="leader" d="M 272 292 L 292 298" />', (298, 302), "start")}

  {hot("hand", '<circle class="hit-dot" cx="94" cy="428" r="13" />', (94, 456), "middle")}

  {hot("viscera", '<ellipse class="hit-blob" cx="200" cy="392" rx="31" ry="24" />',
         (300, 392), "start")}

  {hot("cord", '<path class="hit-cord" d="M 216 300 L 236 300 L 232 444 L 218 444 Z" />'
        '<g class="cord-ticks">'
        '<line x1="212" y1="328" x2="240" y2="328" /><line x1="212" y1="354" x2="240" y2="354" />'
        '<line x1="212" y1="380" x2="240" y2="380" /><line x1="212" y1="406" x2="240" y2="406" />'
        '<line x1="212" y1="432" x2="240" y2="432" />'
        '</g>'
        '<circle class="hit-dot" cx="168" cy="600" r="10" />'
        '<path class="leader" d="M 172 588 L 196 460 L 216 442" />'
        '<path class="leader" d="M 244 340 L 294 340" />', (300, 344), "start")}
</svg>
"""


# --- the list ---------------------------------------------------------------


# --- the hub page -----------------------------------------------------------

NOT_FOUND = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>404 · Neuro Atlas</title>
<style>
  html, body { margin: 0; height: 100%; background: #12151a; color: #e9edf1;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
  div { height: 100%; display: flex; flex-direction: column; gap: 14px;
    align-items: center; justify-content: center; text-align: center; padding: 20px; }
  p { margin: 0; color: #8b96a3; font-size: 13px; }
  b { font-size: 15px; color: #e9edf1; letter-spacing: 0.08em; }
  a { color: #e0a458; font-size: 13px; text-decoration: none;
      border: 1px solid #2b323d; border-radius: 10px; padding: 9px 18px; }
  a:hover { border-color: #e0a458; }
</style>
</head>
<body>
<div>
  <b>404</b>
  <p>這個路徑沒有對應的系統 &middot; no system at this path</p>
  <a href="/">&larr; NEURO ATLAS</a>
</div>
</body>
</html>
"""

# --- injected into each viewer copy -----------------------------------------
NAV_SNIPPET = """
<style>
  #neuroNav {
    position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 60;
    display: flex; gap: 9px; align-items: center; padding: 7px 15px; border-radius: 999px;
    background: rgba(27, 32, 40, 0.88); border: 1px solid #2b323d;
    backdrop-filter: blur(10px); text-decoration: none; white-space: nowrap;
    font: 11.5px/1 ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
    letter-spacing: 0.06em; color: #8b96a3;
    transition: color 0.15s ease, border-color 0.15s ease;
  }
  #neuroNav:hover { color: #e9edf1; border-color: #5c6672; }
  @media (max-width: 720px) { #neuroNav { font-size: 10.5px; padding: 6px 12px; } }
</style>
<a id="neuroNav" href="../" title="Neuro Atlas"><span>&larr;</span><span>NEURO ATLAS &middot; 神經系統首頁</span></a>
"""

# Only for the pages that have an EN/中文 button: follow the hub's choice.
LANG_SNIPPET = """
<script>
(function () {
  var want = null;
  try { want = localStorage.getItem("neuroLang"); } catch (e) {}
  if (want !== "zh") return;
  var btn = document.getElementById("langToggle");
  if (btn) btn.click();   // viewers start in English
})();
</script>
"""


def assemble() -> list[tuple[str, int, bool]]:
    # Clear the contents rather than the directory itself: on Windows a dev
    # server running inside dist/ holds a lock on the folder, and rebuilding
    # while previewing is the normal case.
    DIST.mkdir(parents=True, exist_ok=True)
    for child in DIST.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    report = []
    for s in SYSTEMS:
        src = REPO / s["src"]
        if not src.exists():
            sys.exit(f"ERROR: missing viewer source {src}")
        html = src.read_text(encoding="utf-8")
        if not html.rstrip().endswith("</script>"):
            sys.exit(f"ERROR: {src} does not end with </script> - injection anchor moved")
        if "neuroNav" in html:
            sys.exit(f"ERROR: {src} already contains the nav - refusing to double-inject")

        # Keep the orphan viewers' cross-links inside this assembled site.
        html = html.replace(
            'href="https://human-brain-motor-cortex-hippocampus.pages.dev/"',
            'href="../motor-hippocampus/"',
        ).replace(
            'href="https://human-limbic-system.pages.dev/"',
            'href="../limbic/"',
        )
        bilingual = 'id="langToggle"' in html
        html = prepare_viewer(html)
        # The viewers are body fragments with no <head>: the charset meta has to
        # be prepended so the file is self-describing however it gets served.
        out = ('<meta charset="utf-8" />\n'
               '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
               + html.rstrip("\n") + "\n" + NAV_SNIPPET)
        if bilingual:
            out += LANG_SNIPPET
        out += viewer_upgrade()

        dest = DIST / s["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
        report.append((s["slug"], dest.stat().st_size, bilingual))

    hub = render_hub("human", SYSTEMS, GROUPS, PLANNED, build_svg(), REPO)
    (DIST / "index.html").write_text(hub, encoding="utf-8")
    (DIST / "404.html").write_text(NOT_FOUND, encoding="utf-8")
    return report


def main() -> None:
    report = assemble()
    hub_kb = (DIST / "index.html").stat().st_size / 1024
    total = sum(sz for _, sz, _ in report)

    print(f"\nhub          {hub_kb:8.1f} KB  index.html")
    print(f"404          {(DIST / '404.html').stat().st_size / 1024:8.1f} KB")
    for slug, size, bilingual in report:
        print(f"  {slug:20s} {size / 1e6:6.2f} MB  nav=yes  lang-sync={'yes' if bilingual else 'n/a'}")
    print(f"\n{len(report)} viewers + hub + 404 -> {DIST}  ({total / 1e6:.1f} MB)")
    print("next: py -3.13 site/build_mouse.py   (adds the /mouse/ section)")
    print("deploy: npx wrangler pages deploy site/dist --project-name=neuro-atlas")


if __name__ == "__main__":
    main()
