"""
Build a self-contained 3D viewer for MOp/MOs/RSP inside a whole-brain shell,
using REAL P15-shaped meshes extracted from the DeMBA "Allen segmentation"
P15 atlas (BrainGlobe Atlas API) - not the adult P56 shape.

Reuses the exact three.js + OrbitControls build already embedded in
atlas/P56/motor_cortex_3d.html (extracted to atlas/lib_three.min.js and
atlas/lib_OrbitControls.js) so no external network fetch is needed, and
mirrors that page's camera/legend/interaction design so the two 3D pages
feel like the same app.

Usage:
    python build_demba_p15_3d.py
"""

import base64
import json
import os

import numpy as np
import trimesh
from scipy.ndimage import zoom
from skimage import measure
from trimesh import smoothing
from brainglobe_atlasapi import BrainGlobeAtlas

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ATLAS_DIR = os.path.join(SCRIPT_DIR, "atlas")
OUT_DIR = os.path.join(ATLAS_DIR, "P15")
os.makedirs(OUT_DIR, exist_ok=True)

THREE_JS = open(os.path.join(ATLAS_DIR, "lib_three.min.js"), encoding="utf-8").read()
ORBIT_JS = open(os.path.join(ATLAS_DIR, "lib_OrbitControls.js"), encoding="utf-8").read()

ATLAS_NAME = "demba_allen_seg_dev_mouse_p15_25um"
RESOLUTION_UM = 25.0
# trimesh's simplify_quadric_decimation (fast-simplification backend) reliably
# punches small holes in these meshes regardless of target face count or input
# quality (verified: still non-watertight even decimating a clean, watertight
# source down to 200k faces). Building each mesh straight from a downsampled
# binary voxel mask via marching cubes - no decimation step at all - is what
# actually stays watertight, confirmed at this specific factor.
DOWNSAMPLE_FACTOR = 0.25
STRUCTURES = ["root", "MOp", "MOs", "RSP"]
OUT_FILE = "motor_cortex_3d_p15.html"


def mask_for(atlas, ann, acr):
    if acr == "root":
        return ann != 0
    descendants = atlas.get_structure_descendants(acr)
    ids = [atlas.structures[d]["id"] for d in descendants] + [atlas.structures[acr]["id"]]
    return np.isin(ann, ids)


def build_mesh_from_mask(mask, factor=DOWNSAMPLE_FACTOR, smooth_iterations=25):
    small = zoom(mask.astype(np.float32), factor, order=1)
    verts, faces, _normals, _values = measure.marching_cubes(small, level=0.5)
    verts = verts / factor * RESOLUTION_UM
    tm = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    smoothing.filter_taubin(tm, lamb=0.5, nu=-0.53, iterations=smooth_iterations)
    return tm


def f32_b64(arr):
    return base64.b64encode(arr.astype("<f4").tobytes()).decode("ascii")


def u32_b64(arr):
    return base64.b64encode(arr.astype("<u4").tobytes()).decode("ascii")


def main():
    print(f"Loading {ATLAS_NAME} ...")
    atlas = BrainGlobeAtlas(ATLAS_NAME)
    ann = atlas.annotation

    raw = {}
    for acr in STRUCTURES:
        print(f"  building {acr} mesh from voxel mask ...")
        mask = mask_for(atlas, ann, acr)
        # 0.25 is the one factor verified watertight for all four structures;
        # nearby values (0.12-0.45) break watertightness on one structure or
        # another unpredictably, so don't tune this per-structure
        tm = build_mesh_from_mask(mask, factor=DOWNSAMPLE_FACTOR)
        raw[acr] = tm
        print(f"    {acr}: {len(tm.faces)} faces, watertight={tm.is_watertight}, euler={tm.euler_number}")

    root_v = raw["root"].vertices
    center = (root_v.min(axis=0) + root_v.max(axis=0)) / 2.0
    extent = float((root_v.max(axis=0) - root_v.min(axis=0)).max())
    print(f"center={center}, extent={extent:.1f}")

    # so build_demba_p15.py can point its "locate in 3D" button at an exact
    # plane position instead of guessing - both scripts read the same
    # atlas.annotation voxel grid at RESOLUTION_UM, so
    # scene_x = voxel_row * RESOLUTION_UM - center[0] is exact, not approximate
    with open(os.path.join(OUT_DIR, "mesh_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"center": center.tolist(), "extent": extent, "resolution_um": RESOLUTION_UM}, f)

    colors = {}
    for acr in STRUCTURES:
        info = atlas.structures[acr]
        r, g, b = info["rgb_triplet"]
        colors[acr] = f"{r:02x}{g:02x}{b:02x}"
    names = {
        "MOp": "Primary motor area",
        "MOs": "Secondary motor area",
        "RSP": "Retrosplenial area",
    }

    regions_js_parts = []
    for acr in ["MOp", "MOs", "RSP", "root"]:
        mesh = raw[acr]
        verts = (mesh.vertices - center).astype(np.float32)
        faces = mesh.faces.astype(np.uint32).reshape(-1)
        # trimesh's angle/area-weighted vertex normals look far smoother under
        # specular lighting than THREE.BufferGeometry.computeVertexNormals(),
        # which visibly "sparkles" on a decimated mesh - bake them in instead
        norms = mesh.vertex_normals.astype(np.float32)
        pos_b64 = f32_b64(verts.reshape(-1))
        idx_b64 = u32_b64(faces)
        norm_b64 = f32_b64(norms.reshape(-1))
        color = "CCCCCC" if acr == "root" else colors[acr]
        regions_js_parts.append(
            f'"{acr}":{{"color":"{color}","pos_b64":"{pos_b64}","idx_b64":"{idx_b64}","norm_b64":"{norm_b64}"}}'
        )
    regions_js = "{" + ",".join(regions_js_parts) + "}"

    order_js = json.dumps(["root", "MOp", "MOs", "RSP"])
    legend_rows = ""
    for acr, color, label, name in [
        ("MOp", colors["MOp"], "MOp", names["MOp"]),
        ("MOs", colors["MOs"], "MOs", names["MOs"]),
        ("RSP", colors["RSP"], "RSP", names["RSP"]),
    ]:
        legend_rows += f'''
          <label class="legend-row" data-acr="{acr}">
            <input type="checkbox" checked data-target="{acr}" />
            <span class="swatch" style="--swatch:#{color}"></span>
            <span class="legend-text">
              <span class="legend-acr">{label}</span>
              <span class="legend-name">{name}</span>
            </span>
          </label>'''
    legend_rows += '''
          <label class="legend-row legend-row--outline" data-acr="root">
            <input type="checkbox" checked data-target="root" />
            <span class="swatch swatch--outline"></span>
            <span class="legend-text">
              <span class="legend-acr">outline</span>
              <span class="legend-name">whole-brain shell</span>
            </span>
          </label>'''

    html = TEMPLATE.format(
        three_js=THREE_JS,
        orbit_js=ORBIT_JS,
        extent=extent,
        regions_js=regions_js,
        order_js=order_js,
        legend_rows=legend_rows,
    )

    out_path = os.path.join(OUT_DIR, OUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({os.path.getsize(out_path) / 1024 / 1024:.2f} MB)")


TEMPLATE = """<title>Motor &amp; Retrosplenial Cortex &middot; P15</title>
<style>
  :root {{
    --bg: #12151a;
    --panel: rgba(27, 32, 40, 0.86);
    --panel-border: #2b323d;
    --text: #e9edf1;
    --text-dim: #8b96a3;
    --text-faint: #5c6672;
    --accent: #e0a458;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, "Segoe UI", system-ui, Roboto, sans-serif;
  }}

  * {{ box-sizing: border-box; }}

  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    overflow: hidden;
  }}

  #scene {{
    position: fixed;
    inset: 0;
    display: block;
  }}

  #scene canvas {{
    display: block;
    width: 100%;
    height: 100%;
  }}

  .ui {{
    position: fixed;
    pointer-events: none;
    z-index: 10;
  }}

  nav.crossnav {{
    position: fixed;
    top: 20px;
    right: 32px;
    z-index: 11;
    display: flex;
    gap: 6px;
    pointer-events: auto;
  }}

  .nav-link {{
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--text-dim);
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid var(--panel-border);
    background: rgba(18, 21, 26, 0.75);
    backdrop-filter: blur(10px);
  }}

  .nav-link:hover {{ color: var(--text); border-color: var(--text-faint); }}

  .nav-link.active {{
    color: #12151a;
    background: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
  }}

  header.ui {{
    top: 0;
    left: 0;
    right: 0;
    padding: 28px 32px 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  .eyebrow {{
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-faint);
  }}

  h1 {{
    margin: 0;
    font-family: var(--mono);
    font-weight: 600;
    font-size: clamp(20px, 2.6vw, 30px);
    letter-spacing: 0.01em;
    text-wrap: balance;
    color: var(--text);
  }}

  h1 .accent {{ color: var(--accent); }}

  .subtitle {{
    font-size: 13px;
    color: var(--text-dim);
    max-width: 52ch;
    line-height: 1.5;
  }}

  .caveat {{
    font-size: 12px;
    color: var(--accent);
    max-width: 52ch;
    line-height: 1.5;
    margin-top: 2px;
  }}

  .panel {{
    pointer-events: auto;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    border-radius: 10px;
  }}

  .legend {{
    left: 24px;
    bottom: 24px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 240px;
  }}

  .legend-title {{
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    padding: 0 0 8px 2px;
  }}

  .legend-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 6px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s ease;
  }}

  .legend-row:hover {{ background: rgba(255, 255, 255, 0.045); }}

  .legend-row input {{
    appearance: none;
    width: 13px;
    height: 13px;
    border: 1.5px solid var(--text-faint);
    border-radius: 3px;
    margin: 0;
    flex: none;
    position: relative;
    cursor: pointer;
  }}

  .legend-row input:checked {{
    border-color: var(--accent);
    background: var(--accent);
  }}

  .legend-row input:checked::after {{
    content: "";
    position: absolute;
    left: 3px;
    top: 0px;
    width: 3px;
    height: 7px;
    border: solid #12151a;
    border-width: 0 1.6px 1.6px 0;
    transform: rotate(40deg);
  }}

  .swatch {{
    width: 12px;
    height: 12px;
    border-radius: 3px;
    background: var(--swatch, #888);
    flex: none;
  }}

  .swatch--outline {{
    background: transparent;
    border: 1.5px solid var(--text-faint);
  }}

  .legend-text {{
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }}

  .legend-acr {{
    font-family: var(--mono);
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text);
  }}

  .legend-name {{
    font-size: 11px;
    color: var(--text-faint);
  }}

  .legend-row--outline {{ margin-top: 4px; padding-top: 10px; border-top: 1px solid var(--panel-border); }}

  .slice-panel {{
    left: 24px;
    top: 130px;
    padding: 12px 14px;
    max-width: 260px;
    display: none;
  }}

  .slice-panel.show {{ display: block; }}

  .slice-panel .legend-title {{ padding-bottom: 4px; }}

  .slice-panel .slice-label {{
    font-size: 12.5px;
    color: var(--text);
    line-height: 1.5;
  }}

  .slice-panel .slice-note {{
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 6px;
    line-height: 1.5;
  }}

  .hint {{
    right: 24px;
    bottom: 24px;
    padding: 10px 14px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.7;
  }}

  .hint b {{ color: var(--text-dim); }}

  .loading {{
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--mono);
    font-size: 13px;
    color: var(--text-faint);
    z-index: 5;
    transition: opacity 0.3s ease;
  }}

  .loading.hidden {{ opacity: 0; pointer-events: none; }}
</style>

<div id="scene"></div>
<div class="loading" id="loading">Loading meshes&hellip;</div>

<nav class="crossnav">
  <a class="nav-link" href="../P56/coronal_section289_interactive.html">P56 &middot; Coronal</a>
  <a class="nav-link" href="../P14/sagittal_p14_section144_interactive.html">P14 &middot; Sagittal</a>
  <a class="nav-link" href="coronal_p15_demba_interactive.html">P15 &middot; Coronal (DeMBA)</a>
  <a class="nav-link" href="../P56/motor_cortex_3d.html">3D (P56 adult)</a>
  <a class="nav-link active" href="motor_cortex_3d_p15.html">3D (P15)</a>
</nav>

<header class="ui">
  <span class="eyebrow">DeMBA (Kim Lab) &middot; Allen CCFv3 segmentation warped to P15 &middot; structure meshes</span>
  <h1>Motor <span class="accent">&amp;</span> Retrosplenial Cortex <span class="accent">&middot; P15</span></h1>
  <span class="subtitle">Primary &amp; secondary motor areas (MOp / MOs) and retrosplenial area (RSP), reconstructed as real 3D surfaces at their actual P15 shape and proportions, inside a translucent P15 whole-brain shell.</span>
  <span class="caveat">Boundaries are the adult CCFv3 ontology non-linearly registered onto this age's brain shape, not independently re-annotated at P15.</span>
</header>

<div class="panel slice-panel ui" id="slicePanel">
  <div class="legend-title">2D Section Locator</div>
  <div class="slice-label" id="sliceLabel"></div>
  <div class="slice-note" id="sliceNote"></div>
</div>

<div class="panel legend ui">
  <div class="legend-title">Structures</div>
  {legend_rows}
</div>

<div class="panel hint ui">
  <b>drag</b> orbit &nbsp; <b>scroll</b> zoom &nbsp; <b>right-drag</b> pan<br />
  25&nbsp;&micro;m voxel space &middot; centered on P15 brain centroid
</div>

{three_js}
{orbit_js}
<script>
const REGIONS = {regions_js};
const ORDER = {order_js};
const EXTENT = {extent};
</script>
<script>
(function () {{
  function b64ToFloat32(b64) {{
    const bin = atob(b64);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
    return new Float32Array(buf);
  }}
  function b64ToUint32(b64) {{
    const bin = atob(b64);
    const buf = new ArrayBuffer(bin.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) view[i] = bin.charCodeAt(i);
    return new Uint32Array(buf);
  }}

  const container = document.getElementById("scene");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 1, EXTENT * 6);
  // y = dorsal(-)/ventral(+) in this scene's data; three.js treats +Y as
  // screen-up by default, which would render ventral facing up. Flip the
  // camera's up vector so dorsal (where MOp/MOs/RSP sit) renders up top.
  camera.up.set(0, -1, 0);
  const dist = EXTENT * 1.35;
  // camera sits on the dorsal (-y) side to face MOp/MOs/RSP directly.
  camera.position.set(dist * 0.55, -dist * 0.42, dist * 0.75);

  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x12151a, 1);
  renderer.outputEncoding = THREE.sRGBEncoding;
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = EXTENT * 0.15;
  controls.maxDistance = EXTENT * 3;
  controls.autoRotate = !reduceMotion;
  controls.autoRotateSpeed = 0.7;
  controls.addEventListener("start", () => {{ controls.autoRotate = false; }});
  controls.target.set(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xaebfd4, 0x14171c, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(EXTENT * 0.6, EXTENT * 0.9, EXTENT * 0.7);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x8fb4ff, 0.3);
  fill.position.set(-EXTENT * 0.7, -EXTENT * 0.2, -EXTENT * 0.5);
  scene.add(fill);

  const meshes = {{}};

  ORDER.forEach((acr) => {{
    const s = REGIONS[acr];
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(b64ToFloat32(s.pos_b64), 3));
    if (s.norm_b64) {{
      geom.setAttribute("normal", new THREE.BufferAttribute(b64ToFloat32(s.norm_b64), 3));
    }} else {{
      geom.computeVertexNormals();
    }}
    geom.setIndex(new THREE.BufferAttribute(b64ToUint32(s.idx_b64), 1));

    let mat, mesh;
    if (acr === "root") {{
      mat = new THREE.MeshStandardMaterial({{
        color: 0x7c8b99,
        transparent: true,
        opacity: 0.07,
        side: THREE.BackSide,
        depthWrite: false,
        roughness: 1,
      }});
      mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 10;
    }} else {{
      mat = new THREE.MeshStandardMaterial({{
        color: parseInt(s.color, 16),
        roughness: 0.45,
        metalness: 0.05,
        side: THREE.DoubleSide,
      }});
      mesh = new THREE.Mesh(geom, mat);
    }}
    scene.add(mesh);
    meshes[acr] = mesh;
  }});

  document.querySelectorAll(".legend-row input").forEach((el) => {{
    el.addEventListener("change", () => {{
      const target = meshes[el.dataset.target];
      if (target) target.visible = el.checked;
    }});
  }});

  // ---- optional 2D-section locator plane, driven by URL params ----
  // ?axis=x|y|z & pos=<scene units> & label=<text>
  // axis meaning in this scene: x = anterior(-)/posterior(+), y = dorsal(-)/ventral(+), z = medial-lateral
  (function addSliceLocator() {{
    const params = new URLSearchParams(window.location.search);
    const axis = params.get("axis");
    const pos = parseFloat(params.get("pos"));
    const label = params.get("label");
    const approx = params.get("approx") === "1";
    if (!axis || Number.isNaN(pos)) return;

    const SPAN = EXTENT * 1.3;
    const planeGeom = new THREE.PlaneGeometry(SPAN, SPAN);
    const planeMat = new THREE.MeshBasicMaterial({{
      color: 0xe0a458,
      transparent: true,
      opacity: 0.16,
      side: THREE.DoubleSide,
      depthWrite: false,
    }});
    const plane = new THREE.Mesh(planeGeom, planeMat);

    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(planeGeom),
      new THREE.LineBasicMaterial({{ color: 0xe0a458, transparent: true, opacity: 0.55 }})
    );
    plane.add(edges);

    if (axis === "x") {{
      plane.rotation.y = Math.PI / 2;
      plane.position.x = pos;
    }} else if (axis === "y") {{
      plane.rotation.x = Math.PI / 2;
      plane.position.y = pos;
    }} else if (axis === "z") {{
      plane.position.z = pos;
    }}
    plane.renderOrder = 20;
    scene.add(plane);

    const panel = document.getElementById("slicePanel");
    const labelEl = document.getElementById("sliceLabel");
    const noteEl = document.getElementById("sliceNote");
    if (panel && label) {{
      labelEl.textContent = decodeURIComponent(label);
      noteEl.textContent = approx
        ? "Plane position is approximate."
        : "Exact voxel-row position - this P15 3D model and the P15 coronal plate come from the same DeMBA volume, so this plane marks precisely where that 2D slice was cut.";
      panel.classList.add("show");
    }}
  }})();

  function resize() {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }}
  window.addEventListener("resize", resize);

  function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }}
  animate();

  document.getElementById("loading").classList.add("hidden");
}})();
</script>
"""

if __name__ == "__main__":
    main()
