// Connectivity Explorer page layer: region graph, network propagation,
// edge inspection/tracing, and the "Virtual Mouse Neural Controller"
// running-wheel behavior. Read into mouse_atlas.build.mouse_connectivity's
// CUSTOM_JS at build time and injected verbatim into the shared viewer
// template's custom-code slot (mouse/src/mouse_atlas/render/
// viewer_template.html), which sits inside that template's main IIFE, so
// THREE / scene / meshes / EXTENT / STRINGS / LANG / applyLang are
// already in scope by the time this file's top-level
// code runs. The PAYLOAD assignment just below carries a build-time
// placeholder token, substituted by mouse_connectivity.py with the page's
// connectivity document (see connectivity_data.py) before this file is
// valid JS on its own - so do not repeat that exact placeholder text
// anywhere else in this file, including in comments: the substitution is
// a plain string replace and would rewrite every occurrence.
//
// WHAT THIS PAGE IS: a region-level projection graph you can click
// through, plus a network diffusion model you can run. What it is NOT: a
// connectome simulation. Allen connectivity data is mesoscale axonal
// projection density, not synapse-level wiring, and the propagation
// carries no spike timing. The running-wheel layer is an engineered,
// computational visualization - not real neuronal, spinal or muscular
// physiology - and is labelled as such throughout.
//
// SITE-LAYER COLLISION RULE - site/viewer_upgrade.py's prepare_viewer()
// patches the deployed viewer's last <script> block by literal
// str.replace against a short list of exact strings (the camera/renderer
// constructor lines, the animate()/render() lines, the resize listener,
// the HOVER_NODES declaration); reproducing one of those verbatim here,
// even inside a comment, would silently misroute that patch and break
// the deployed (not raw) page. The full list lives as a Python comment
// in mouse_atlas.build.mouse_connectivity, right above where this file
// gets read in - deliberately NOT copied here, so quoting one for
// documentation can't accidentally recreate the exact collision it
// warns about. Also forbidden anywhere in this file: the handful of
// site-layer sentinel ids that make prepare_viewer() or the deployed
// rail bail out or misfire if they appear where they're not expected
// (see tests/test_connectivity.py's FORBIDDEN_IDS for the exact list -
// again deliberately not reproduced here), and any double-underscore
// placeholder besides the PAYLOAD one below (the shared template's own
// leftover-token scan would reject it).
// tests/test_connectivity.py asserts all of this against the built
// CUSTOM_JS string, so a violation fails before it ships.
//
// No randomness anywhere in the propagation path (propagate() below) -
// same input must always give the same output. Every node/edge/model
// element carries one of four evidence classes (EXPERIMENTAL /
// ATLAS-DERIVED / COMPUTATIONAL / SCHEMATIC); don't add one without.
  (function connectivityLayer() {
    const PAYLOAD = __CONN_JSON__;
    const CONN = PAYLOAD.graph;
    const SYSTEMS = PAYLOAD.systems || {};
    const P = CONN.propagation;
    const EDGE_CLASS = (CONN.edges[0] || {}).evidence_class || "EXPERIMENTAL";
    const NODE_KEYS = CONN.nodes.map((n) => n.acronym);
    const BY_KEY = {};
    const IDX = {};
    const POS = {};
    CONN.nodes.forEach((n, i) => {
      BY_KEY[n.acronym] = n;
      IDX[n.acronym] = i;
      POS[n.acronym] = new THREE.Vector3(n.pos_um[0], n.pos_um[1], n.pos_um[2]);
    });
    // Phase 3 evidence label. The shared site scene layer (scene.js) styles
    // every connection tube as "schematic" in its stage note. This page's
    // edges are measured, so override that text; the fallback in scene.js
    // keeps every other viewer byte-identical. Bilingual: scene.js passes
    // its current language in.
    window.NEURO_CONNECTIONS_LABEL = (zh) => zh
      ? "\u539f\u59cb\u7db2\u683c\u6bd4\u4f8b \u00b7 Allen \u5be6\u6e2c\u9023\u7dda"
      : "ATLAS PROPORTIONS \u00b7 EXPERIMENTAL CONNECTIONS";
    // warm, so the network layer never blends into the region palette
    // (LGd orange is the only warm region, and it is small)
    const EDGE_COLOR = 0xffc266;
    const EDGE_HOT = 0xff9a3c;
    // Fixed activity display scale (VISUALIZATION ONLY). Because the scale is
    // fixed relative to the seed amplitude (1.0), the same activity always maps
    // to the same brightness at any step: strong early signal -> bright, late
    // residual -> faint. The raw simulated values are never modified.
    const ACTIVITY_GAMMA = 0.45;   // display = activity ** 0.45
    const ACTIVITY_FLOOR = 0.005;  // below this, no highlighting at all
    // Emissive intensity cap. emissive keeps the region's own colour (no
    // white tint), so a higher cap brightens the same hue rather than
    // washing it out; 1.1 makes the wave visible without a per-step scale.
    const ACTIVITY_CAP = 1.1;
    // one propagation step every 650 ms (sequential, followable)
    const STEP_MS = 650;
    const TRACE_MS = 520;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---- panel styling (scoped; the rail restyles .legend-* for us) ----
    const style = document.createElement("style");
    style.id = "connStyle";
    style.textContent = [
      "#connBlock{margin-top:10px}",
      "#connBlock .conn-sub{font-size:11px;letter-spacing:.08em;text-transform:uppercase;",
      "opacity:.62;margin:8px 0 4px}",
      "#connBlock .conn-row{display:flex;align-items:center;gap:8px;min-height:28px;",
      "padding:2px 0;font-size:12px}",
      "#connBlock .conn-row .conn-acr{flex:0 0 46px;font-weight:600}",
      "#connBlock .conn-row--link{cursor:pointer;border-radius:5px;padding-left:5px;padding-right:5px}",
      "#connBlock .conn-row--link:hover{background:rgba(255,255,255,.07)}",
      "#connBlock .conn-row--link[aria-pressed='true']{background:rgba(255,154,60,.18)}",
      "#connBlock .conn-bar{flex:1 1 auto;height:7px;border-radius:4px;",
      "background:rgba(255,255,255,.12);overflow:hidden}",
      "#connBlock .conn-bar>span{display:block;height:100%;border-radius:4px;",
      "background:var(--accent,#84dcc5)}",
      "#connBlock .conn-val{flex:0 0 40px;text-align:right;opacity:.7;",
      "font-variant-numeric:tabular-nums}",
      "#connBlock .conn-pick{width:100%;text-align:left;background:transparent;",
      "border:1px solid rgba(255,255,255,.14);border-radius:7px;color:inherit;",
      "font:inherit;padding:7px 9px;margin:3px 0;min-height:44px;cursor:pointer}",
      "#connBlock .conn-pick[aria-pressed='true']{border-color:var(--accent,#84dcc5);",
      "background:rgba(132,220,197,.14)}",
      "#connBlock .conn-sys{display:flex;align-items:center;justify-content:space-between;",
      "width:100%;background:transparent;border:0;color:inherit;font:inherit;",
      "font-size:10px;letter-spacing:.1em;text-transform:uppercase;opacity:.62;",
      "padding:8px 2px 4px;cursor:pointer;text-align:left}",
      "#connBlock .conn-sys:hover{opacity:.92}",
      "#connBlock .conn-sys .chevron{font-size:10px;opacity:.75}",
      "#connBlock .conn-sys-body{margin:0 0 4px}",
      "#connBlock .conn-btns{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}",
      "#connBlock .conn-btns button{flex:1 1 auto;min-height:40px;min-width:64px;",
      "background:transparent;border:1px solid rgba(255,255,255,.14);border-radius:7px;",
      "color:inherit;font:inherit;font-size:12px;padding:6px 8px;cursor:pointer}",
      "#connBlock .conn-btns button[aria-pressed='true']{border-color:var(--accent,#84dcc5);",
      "background:rgba(132,220,197,.14)}",
      "#connBlock .conn-trace{display:flex;align-items:center;gap:6px;margin:8px 0;flex-wrap:wrap}",
      "#connBlock .conn-trace select{flex:1 1 110px;min-height:36px;background:rgba(255,255,255,.05);",
      "color:inherit;border:1px solid rgba(255,255,255,.16);border-radius:6px;padding:4px 6px;",
      "font:inherit;font-size:12px}",
      "#connBlock .conn-trace button{min-height:36px;background:transparent;",
      "border:1px solid rgba(255,255,255,.16);border-radius:6px;color:inherit;font:inherit;",
      "font-size:12px;padding:4px 10px;cursor:pointer}",
      "#connBlock .conn-slider{display:flex;align-items:center;gap:8px;margin:8px 0}",
      "#connBlock .conn-slider input{flex:1 1 auto;accent-color:var(--accent,#84dcc5)}",
      "#connBlock .conn-note{font-size:11px;line-height:1.5;opacity:.62;margin-top:8px}",
      "#connBlock .conn-src{font-size:11px;line-height:1.6;opacity:.68;margin-top:6px}",
      "#connBlock .conn-src b{opacity:.85;font-weight:600}",
      "#connBlock .conn-tag{display:inline-block;font-size:9px;letter-spacing:.06em;",
      "border:1px solid rgba(255,255,255,.22);border-radius:4px;padding:0 4px;",
      "margin-left:4px;opacity:.75;vertical-align:1px}",
      "#connBlock .conn-detail{margin:8px 0;padding:8px 10px;border:1px solid rgba(255,154,60,.35);",
      "border-radius:8px;background:rgba(0,0,0,.18);font-size:11.5px;line-height:1.55}",
      "#connBlock .conn-detail-head{display:flex;align-items:center;justify-content:space-between;",
      "gap:8px;margin-bottom:4px}",
      "#connBlock .conn-detail-head b{font-size:12px}",
      "#connBlock .conn-detail-head button{background:transparent;border:0;color:inherit;",
      "font-size:16px;line-height:1;cursor:pointer;opacity:.7;padding:0 2px}",
      "#connBlock .conn-detail-line{opacity:.85}",
      "#connBlock .conn-detail-note{opacity:.62;margin-top:4px}",
      "#connBlock .run-btns{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}",
      "#connBlock .run-btns button{flex:1 1 auto;min-height:40px;min-width:60px;background:transparent;",
      "border:1px solid rgba(255,255,255,.16);border-radius:7px;color:inherit;font:inherit;",
      "font-size:12px;padding:6px 8px;cursor:pointer}",
      "#connBlock .run-btns button:hover{border-color:var(--accent,#84dcc5)}",
      "#connBlock #runStart[aria-pressed='true']{border-color:var(--accent,#84dcc5);",
      "background:rgba(132,220,197,.14)}",
      "#connBlock .run-wheel-row{display:flex;gap:10px;align-items:center;margin:6px 0}",
      "#connBlock .run-wheel{flex:0 0 104px;width:104px;height:104px}",
      "#connBlock .run-wheel .run-rim{fill:none;stroke:rgba(255,255,255,.32);stroke-width:3}",
      "#connBlock .run-wheel .run-spoke{stroke:rgba(255,255,255,.5);stroke-width:1.5}",
      "#connBlock .run-wheel .run-hub{fill:var(--accent,#84dcc5)}",
      "#connBlock .run-wheel .run-mouse{fill:none;stroke:#e9edf1;stroke-width:2}",
      "#connBlock .run-readouts{flex:1 1 auto;font-size:11.5px;line-height:1.75}",
      "#connBlock .run-readouts b{font-variant-numeric:tabular-nums}",
      "#connBlock #runTrace{width:100%;height:120px;display:block;margin:6px 0;",
      "border:1px solid rgba(255,255,255,.12);border-radius:6px;background:rgba(0,0,0,.22)}",
      "#connBlock .run-trace-legend{display:flex;flex-direction:column;gap:3px;",
      "font-size:10.5px;opacity:.88;margin-top:2px}",
      "#connBlock .run-trace-legend div{display:flex;align-items:center;gap:6px}",
      "#connBlock .run-trace-legend i{width:9px;height:9px;border-radius:2px;flex:none}",
      "#connBlock .run-trace-legend b{margin-left:auto;font-variant-numeric:tabular-nums}",
      "#connBlock .run-dev{margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.12);",
      "font-size:11px}",
      "#connBlock .run-dev label{display:flex;align-items:center;gap:6px;opacity:.85}",
      "#connBlock .run-dev input[type=range]{width:100%;accent-color:var(--accent,#84dcc5)}",
      "#connBlock .run-info{margin-top:8px;font-size:10.5px;line-height:1.6;opacity:.66}",
      "#mouseStage{position:fixed;right:18px;top:186px;z-index:45;",
      "width:214px;padding:10px 12px 12px;background:rgba(15,27,32,.92);",
      "border:1px solid #2c4148;border-radius:10px;backdrop-filter:blur(10px);",
      "color:#e9edf1;font:12px/1.4 -apple-system,'Segoe UI',system-ui,sans-serif;",
      "box-shadow:0 10px 30px rgba(0,0,0,.4)}",
      "#mouseStage .ms-title{font-size:10px;letter-spacing:.1em;text-transform:uppercase;",
      "opacity:.65;margin-bottom:4px}",
      "#mouseStage .ms-cta{font-size:11.5px;line-height:1.35;margin-bottom:8px;opacity:.88}",
      "#mouseStage .ms-btns{display:flex;gap:6px;margin-bottom:8px}",
      "#mouseStage .ms-btns button{flex:1 1 auto;min-height:38px;background:transparent;",
      "border:1px solid rgba(255,255,255,.18);border-radius:7px;color:inherit;font:inherit;",
      "font-size:12px;cursor:pointer}",
      "#mouseStage .ms-btns button:hover{border-color:#84dcc5}",
      // primary CTA styling: filled, not just outlined, so Start reads as
      // the one thing to press on first landing. This array is JS, so a
      // "//" line between string elements is a real comment, stripped
      // before the strings are joined into CSS text.
      "#mouseStage #mouseStart{background:#84dcc5;border-color:#84dcc5;color:#0c1512;",
      "font-weight:600}",
      "#mouseStage #mouseStart:hover{background:#9ee6d1;border-color:#9ee6d1}",
      "#mouseStage #mouseStart[aria-pressed='true']{background:rgba(132,220,197,.14);",
      "border-color:#84dcc5;color:inherit;font-weight:400}",
      "#mouseStage #mouseStart.ms-pulse{animation:msPulse 1.8s ease-in-out infinite}",
      "@keyframes msPulse{0%,100%{box-shadow:0 0 0 0 rgba(132,220,197,.55)}",
      "50%{box-shadow:0 0 0 7px rgba(132,220,197,0)}}",
      "@media (prefers-reduced-motion: reduce){#mouseStage #mouseStart.ms-pulse{animation:none}}",
      "#mouseStage svg{display:block;width:100%;height:auto}",
      "#mouseStage .ms-rim{fill:none;stroke:rgba(255,255,255,.32);stroke-width:3}",
      "#mouseStage .ms-spoke{stroke:rgba(255,255,255,.45);stroke-width:1.5}",
      "#mouseStage .ms-stand{stroke:rgba(255,255,255,.3);stroke-width:3}",
      "#mouseStage .ms-body{fill:#d8d2c4;stroke:#2b323d;stroke-width:1.2}",
      "#mouseStage .ms-head{fill:#e2ddd0;stroke:#2b323d;stroke-width:1.2}",
      "#mouseStage .ms-ear{fill:#e8b9b0;stroke:#2b323d;stroke-width:1}",
      "#mouseStage .ms-eye{fill:#1b2028}",
      "#mouseStage .ms-tail{fill:none;stroke:#c9b7a8;stroke-width:2}",
      "#mouseStage .ms-leg{stroke:#2b323d;stroke-width:2.4;stroke-linecap:round}",
      "#mouseStage .ms-readout{display:flex;justify-content:space-between;font-size:11px;",
      "opacity:.82;margin-top:6px}",
      "#mouseStage .ms-caption{font-size:9.5px;line-height:1.4;opacity:.55;margin-top:8px;",
      "padding-top:7px;border-top:1px solid rgba(255,255,255,.12)}",
      "@media (max-width:760px){#mouseStage{top:132px;transform:none;right:12px;width:150px;",
      "padding:8px 9px 10px}}",
      "#connEmpty{font-size:12px;opacity:.55;padding:4px 0}",
    ].join("");
    document.head.appendChild(style);

    // ---- DOM, appended inside #legendBody so the deployed rail adopts it ----
    const host = document.createElement("div");
    host.id = "connBlock";
    host.innerHTML = [
      '<div class="legend-title" data-conn-en="Virtual Mouse Neural Controller" data-conn-zh="虛擬小鼠神經控制器"></div>',
      '<div id="runPanel">',
      '<div class="run-btns">',
      '<button type="button" id="runStart" aria-pressed="false" data-conn-en="Start running" data-conn-zh="開始跑步"></button>',
      '<button type="button" id="runStop" data-conn-en="Stop input" data-conn-zh="停止輸入"></button>',
      '<button type="button" id="runReset" data-conn-en="Reset" data-conn-zh="重設"></button>',
      "</div>",
      '<div class="run-wheel-row">',
      '<svg class="run-wheel" viewBox="0 0 100 100" aria-hidden="true">',
      '<circle class="run-rim" cx="50" cy="50" r="44"></circle>',
      '<g id="runWheelSpokes">',
      '<line class="run-spoke" x1="50" y1="8" x2="50" y2="92"></line>',
      '<line class="run-spoke" x1="8" y1="50" x2="92" y2="50"></line>',
      '<line class="run-spoke" x1="20" y1="20" x2="80" y2="80"></line>',
      '<line class="run-spoke" x1="80" y1="20" x2="20" y2="80"></line>',
      "</g>",
      '<circle class="run-hub" cx="50" cy="50" r="4"></circle>',
      '<g class="run-mouse"><ellipse cx="49" cy="56" rx="9" ry="6"></ellipse>',
      '<circle cx="59" cy="52" r="3.4"></circle>',
      '<path d="M40 56 q-8 2 -12 -3"></path></g>',
      "</svg>",
      '<div class="run-readouts">',
      '<div><span data-conn-en="Mouse state" data-conn-zh="小鼠狀態"></span>: <b id="runState">STOPPED</b></div>',
      '<div><span data-conn-en="Speed" data-conn-zh="速度"></span>: <b id="runSpeed">0.0</b> cm/s</div>',
      '<div><span data-conn-en="Distance" data-conn-zh="距離"></span>: <b id="runDist">0</b> cm</div>',
      '<div><span data-conn-en="Motor drive" data-conn-zh="運動驅動"></span>: <b id="runDrive">0.00</b></div>',
      '<div><span data-conn-en="Time" data-conn-zh="時間"></span>: <b id="runTime">0.0</b> s</div>',
      "</div>",
      "</div>",
      '<canvas id="runTrace" width="300" height="120"></canvas>',
      '<div class="run-trace-legend">',
      '<div><i style="background:#84dcc5"></i>',
      '<span data-conn-en="CA1 LFP-like (synthetic theta)" data-conn-zh="CA1 合成 LFP(theta)"></span>',
      '<b id="runTheta"></b></div>',
      '<div><i style="background:#e8c46a"></i>',
      '<span data-conn-en="Motor drive (engineered decoder)" data-conn-zh="運動驅動(工程解碼)"></span>',
      '<b id="runMotorVal">0.00</b></div>',
      '<div><i style="background:#e88b6a"></i>',
      '<span data-conn-en="Wheel speed (virtual)" data-conn-zh="輪速(虛擬)"></span>',
      '<b id="runSpeedVal">0.0 cm/s</b></div>',
      "</div>",
      '<div class="run-dev">',
      '<label><input type="checkbox" id="runDevToggle" /> ',
      '<span data-conn-en="Developer motor test" data-conn-zh="開發者運動測試"></span></label>',
      '<input type="range" id="runDevSlider" min="0" max="1" step="0.01" value="0" />',
      '<span id="runDevVal">0.00</span>',
      "</div>",
      '<div class="run-info" id="runInfo"></div>',
      "</div>",
      '<div class="legend-title" data-conn-en="Connectivity" data-conn-zh="連結"></div>',
      '<div id="connPick"></div>',
      '<div class="conn-btns" id="connFilter">',
      '<button type="button" data-dir="both" aria-pressed="true" data-conn-en="Both" data-conn-zh="雙向"></button>',
      '<button type="button" data-dir="out" aria-pressed="false" data-conn-en="Outgoing" data-conn-zh="向外"></button>',
      '<button type="button" data-dir="in" aria-pressed="false" data-conn-en="Incoming" data-conn-zh="向內"></button>',
      "</div>",
      '<div class="conn-slider" id="connSliderRow">',
      '<span data-conn-en="Edges per direction" data-conn-zh="每方向連線數"></span>',
      '<input type="range" id="connSlider" min="1" max="10" value="10" />',
      '<span class="conn-val" id="connSliderVal">10</span>',
      "</div>",
      '<div class="conn-sub" data-conn-en="Outgoing" data-conn-zh="向外投射"></div>',
      '<div id="connOut"></div>',
      '<div class="conn-sub" data-conn-en="Incoming" data-conn-zh="向內接收"></div>',
      '<div id="connIn"></div>',
      '<div class="conn-detail" id="connDetail" hidden></div>',
      '<div class="conn-trace">',
      '<span class="conn-sub" style="margin:0" data-conn-en="Trace to" data-conn-zh="追蹤至"></span>',
      '<select id="connTraceTo" aria-label="trace target"></select>',
      '<button type="button" id="connTraceBtn" data-conn-en="Trace" data-conn-zh="追蹤"></button>',
      '<button type="button" id="connTraceClear" data-conn-en="Clear path" data-conn-zh="清除路徑"></button>',
      "</div>",
      '<div class="conn-btns">',
      '<button type="button" id="connFocus" aria-pressed="false" data-conn-en="Focus neighbours" data-conn-zh="聚焦鄰居"></button>',
      "</div>",
      '<div class="legend-title" style="padding-top:12px" data-conn-en="Stimulation" data-conn-zh="刺激模擬"></div>',
      '<div class="conn-btns">',
      '<button type="button" id="connRun" data-conn-en="Stimulate" data-conn-zh="開始刺激"></button>',
      '<button type="button" id="connReset" data-conn-en="Reset" data-conn-zh="重設"></button>',
      "</div>",
      '<div class="conn-sub"><span id="connStepLabel"></span></div>',
      '<div id="connActivity"></div>',
      '<div class="conn-note" id="connModelNote"></div>',
      '<div class="legend-title" style="padding-top:12px" data-conn-en="Data source" data-conn-zh="資料來源"></div>',
      '<div class="conn-src" id="connSrc"></div>',
    ].join("");

    const legendBody = document.getElementById("legendBody");
    const legendNote = document.getElementById("txtLegendNote");
    if (legendNote && legendNote.parentNode === legendBody) {
      legendBody.insertBefore(host, legendNote);
    } else {
      legendBody.appendChild(host);
    }
    document.getElementById("legendPanel").classList.remove("collapsed");

    // ---- 3D edges: CatmullRom tube, radius and opacity driven by weight ----
    function buildEdge(a, b, w) {
      const p0 = POS[a];
      const p1 = POS[b];
      const len = p0.distanceTo(p1);
      const out = p0.clone().lerp(p1, 0.5);
      if (out.lengthSq() < 1e-6) out.set(0, 0, 1);
      out.normalize();
      const c1 = p0.clone().lerp(p1, 0.28).addScaledVector(out, len * 0.22);
      const c2 = p0.clone().lerp(p1, 0.72).addScaledVector(out, len * 0.22);
      const curve = new THREE.CatmullRomCurve3([p0, c1, c2, p1], false, "catmullrom", 0.5);
      const geom = new THREE.TubeGeometry(
        curve, Math.max(24, Math.round(28 + 44 * w)), EXTENT * (0.0018 + 0.0052 * w), 8, false);
      // depthTest off, like the template's hover leader line: the centroids
      // these curves join sit INSIDE opaque region meshes, so a depth-tested
      // tube is invisible in every default view. These curves show network
      // relationships, not axon trajectories, so drawing them over the
      // anatomy is honest as well as legible. renderOrder stays below the
      // label sprites
      // (998+) so text still wins.
      const mat = new THREE.MeshStandardMaterial({
        color: EDGE_COLOR, emissive: EDGE_COLOR, emissiveIntensity: 0.35,
        roughness: 0.4, metalness: 0.1,
        transparent: true, opacity: 0.45 + 0.45 * w,
        depthWrite: false, depthTest: false,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 900;
      mesh.userData.curve = curve; // kept for path tracing (Phase 3)
      return mesh;
    }

    const edgeGroup = new THREE.Group();
    scene.add(edgeGroup);
    // Every edge gets a resident mesh; visibility is driven per selected
    // region below. 136 thin tubes are cheap to keep, and building them all
    // makes the "top N for THIS region" rule exact: the old global
    // top-50-then-filter could leave a low-weight region showing nothing.
    const EDGES = CONN.edges
      .slice()
      .sort((x, y) => y.normalized_weight - x.normalized_weight)
      .map((e) => {
        const mesh = buildEdge(e.source, e.target, e.normalized_weight);
        mesh.visible = false;
        edgeGroup.add(mesh);
        return { edge: e, mesh: mesh, baseOpacity: mesh.material.opacity };
      });

    // Per-region rankings (both directions), strongest first.
    const OUT_BY = {};
    const IN_BY = {};
    NODE_KEYS.forEach((k) => { OUT_BY[k] = []; IN_BY[k] = []; });
    EDGES.forEach((rec) => {
      OUT_BY[rec.edge.source].push(rec.edge);
      IN_BY[rec.edge.target].push(rec.edge);
    });
    NODE_KEYS.forEach((k) => {
      OUT_BY[k].sort((a, b) => b.normalized_weight - a.normalized_weight);
      IN_BY[k].sort((a, b) => b.normalized_weight - a.normalized_weight);
    });
    const MAX_PER_DIR = Math.max(1, NODE_KEYS.reduce(
      (m, k) => Math.max(m, OUT_BY[k].length, IN_BY[k].length), 1));

    // edge lookup for tracing / list-row selection
    const REC_BY_PAIR = new Map();
    const NEIGHBORS = {};
    NODE_KEYS.forEach((k) => { NEIGHBORS[k] = new Set(); });
    EDGES.forEach((rec) => {
      REC_BY_PAIR.set(rec.edge.source + ">" + rec.edge.target, rec);
      NEIGHBORS[rec.edge.source].add(rec.edge.target);
      NEIGHBORS[rec.edge.target].add(rec.edge.source);
    });

    // the one moving dot used by path tracing; deterministic, no RNG
    const pulse = new THREE.Mesh(
      new THREE.SphereGeometry(EXTENT * 0.013, 12, 12),
      new THREE.MeshBasicMaterial({
        color: 0xfff2cc, transparent: true, opacity: 0.95,
        depthWrite: false, depthTest: false,
      }));
    pulse.renderOrder = 1002;
    pulse.visible = false;
    scene.add(pulse);

    // ---- activity paint: never cache material, scene.js swaps them later ----
    const baseline = new Map();
    function baseOf(mat) {
      let b = baseline.get(mat.uuid);
      if (!b) {
        b = { em: mat.emissive.clone(), i: mat.emissiveIntensity };
        baseline.set(mat.uuid, b);
      }
      return b;
    }
    function paint(key, a) {
      const mesh = meshes[key];
      const mat = mesh && mesh.material;
      if (!mat || !mat.emissive) return;
      const b = baseOf(mat);
      // Keep the anatomical base colour. Activity raises emissive INTENSITY
      // only, up to a conservative cap, so active regions glow in their own
      // hue instead of being tinted white.
      mat.emissive.copy(b.em);
      mat.emissiveIntensity = b.i + a * (ACTIVITY_CAP - b.i);
    }

    // ---- display scaling (VISUALIZATION ONLY) ----------------------------
    // One fixed scale for the whole simulation, relative to the seed amplitude
    // of 1.0: display = activity ** 0.45, with a visibility floor. No per-step
    // max normalization, so a given activity value always has the same
    // brightness regardless of step, and late residual activity stays faint.
    // Read-only: this never feeds back into propagate() or the stored frames.
    function displayValue(v) {
      if (!(v >= ACTIVITY_FLOOR)) return 0;
      return Math.min(1, Math.pow(v, ACTIVITY_GAMMA));
    }
    function fmtActivity(v) {
      if (!(v > 0)) return "0.00";
      return v >= 0.01 ? v.toFixed(2) : v.toFixed(3);
    }

    // ---- the model: deterministic, no RNG, clipped every step ----
    function propagate(seedKey) {
      const n = NODE_KEYS.length;
      const frames = [];
      let cur = new Float64Array(n);
      cur[IDX[seedKey]] = 1;
      frames.push(Float64Array.from(cur));
      for (let s = 0; s < P.steps; s++) {
        const nx = new Float64Array(n);
        for (let i = 0; i < n; i++) nx[i] = P.decay * cur[i];
        for (const e of CONN.edges) {
          nx[IDX[e.target]] += P.gain * e.normalized_weight * cur[IDX[e.source]];
        }
        for (let i = 0; i < n; i++) nx[i] = Math.min(P.clip[1], Math.max(P.clip[0], nx[i]));
        frames.push(nx);
        cur = nx;
      }
      return frames;
    }

    // ---- strongest weighted path: the viewer mirror of Python
    // connectivity_data.strongest_path(). Shortest path on cost -log(weight)
    // maximizes the product of normalized weights. Selection scans nodes in
    // graph order, so ties break exactly like the Python reference. This is a
    // display aid, not a claim about signal routing.
    function strongestPath(src, tgt) {
      if (!BY_KEY[src] || !BY_KEY[tgt]) return null;
      const dist = {};
      const prev = {};
      const done = {};
      NODE_KEYS.forEach((k) => { dist[k] = Infinity; prev[k] = null; done[k] = false; });
      dist[src] = 0;
      while (true) {
        let u = null;
        let best = Infinity;
        for (const k of NODE_KEYS) {
          if (!done[k] && dist[k] < best) { best = dist[k]; u = k; }
        }
        if (u === null || u === tgt) break;
        done[u] = true;
        for (const e of OUT_BY[u]) {
          const w = e.normalized_weight;
          if (!(w > 0)) continue;
          const nd = dist[u] - Math.log(w);
          if (nd < dist[e.target]) { dist[e.target] = nd; prev[e.target] = u; }
        }
      }
      if (!isFinite(dist[tgt])) return null;
      const path = [];
      let cur = tgt;
      while (cur !== null) { path.push(cur); cur = prev[cur]; }
      path.reverse();
      return path[0] === src ? path : null;
    }

    // ---- state ----
    let selected = NODE_KEYS[0];
    let direction = "both";
    let shown = Math.min(10, MAX_PER_DIR);
    let run = null;
    let selectedEdge = null;   // edge object highlighted from the lists / tube
    let focusMode = false;     // dim non-neighbour regions
    let traceNodes = [];       // region acronyms on the traced path
    let traceRecs = [];        // edge records on the traced path
    let traceRun = null;       // {t0} while the pulse is animating
    let detailMsg = "";        // transient message in the detail card
    const sysOpen = {};

    const slider = document.getElementById("connSlider");
    slider.max = String(Math.min(50, MAX_PER_DIR));
    slider.value = String(shown);
    document.getElementById("connSliderVal").textContent = String(shown);
    document.getElementById("connSliderRow").style.display = MAX_PER_DIR > 1 ? "flex" : "none";

    function nameOf(key) {
      const n = BY_KEY[key];
      if (!n) return key;
      return LANG === "zh" ? n.name_zh : n.name_en;
    }

    function rowsFor(dir) {
      const ranked = dir === "out" ? OUT_BY[selected] : IN_BY[selected];
      return ranked.slice(0, shown);
    }

    // focus dimming touches OPACITY only: the activity paint() owns emissive,
    // and scene.js owns the region materials, so opacity is the safe channel.
    const meshBase = new Map();
    function setMeshDim(key, dim) {
      const mesh = meshes[key];
      const mat = mesh && mesh.material;
      if (!mat) return;
      if (!meshBase.has(mat.uuid)) {
        meshBase.set(mat.uuid, {
          opacity: mat.opacity, transparent: mat.transparent, depthWrite: mat.depthWrite,
        });
      }
      const b = meshBase.get(mat.uuid);
      if (dim) {
        mat.transparent = true; mat.depthWrite = false; mat.opacity = b.opacity * 0.16;
      } else {
        mat.transparent = b.transparent; mat.depthWrite = b.depthWrite; mat.opacity = b.opacity;
      }
    }

    function applyVisualState() {
      const neigh = NEIGHBORS[selected] || new Set();
      let dimmed = 0;
      NODE_KEYS.forEach((k) => {
        const dim = focusMode && k !== selected && !neigh.has(k);
        if (dim) dimmed += 1;
        setMeshDim(k, dim);
      });
      // observable state for QA / debugging (no visual effect)
      host.dataset.connDimmed = String(dimmed);
      const pathSet = new Set(traceRecs);
      EDGES.forEach((rec) => {
        const m = rec.mesh.material;
        if (!m) return;
        let op = rec.baseOpacity;
        if (traceRecs.length) op = pathSet.has(rec) ? Math.min(1, op + 0.4) : op * 0.15;
        if (selectedEdge) op = (rec.edge === selectedEdge) ? Math.min(1, rec.baseOpacity + 0.5) : op * 0.25;
        m.opacity = op;
        const hot = rec.edge === selectedEdge || pathSet.has(rec);
        m.color.setHex(hot ? EDGE_HOT : EDGE_COLOR);
        m.emissive.setHex(hot ? EDGE_HOT : EDGE_COLOR);
      });
    }

    function renderEdges() {
      const set = new Set();
      if (direction !== "in") OUT_BY[selected].slice(0, shown).forEach((e) => set.add(e));
      if (direction !== "out") IN_BY[selected].slice(0, shown).forEach((e) => set.add(e));
      traceRecs.forEach((rec) => set.add(rec.edge));
      EDGES.forEach((rec) => {
        rec.mesh.visible = set.has(rec.edge) || rec.edge === selectedEdge;
      });
      applyVisualState();
    }

    function renderLists() {
      [["connOut", "out"], ["connIn", "in"]].forEach(([id, dir]) => {
        const box = document.getElementById(id);
        const rows = rowsFor(dir);
        const dim = (direction !== "both" && direction !== dir);
        box.style.opacity = dim ? "0.35" : "1";
        if (!rows.length) {
          box.innerHTML = '<div id="connEmpty">' +
            (LANG === "zh" ? "此方向沒有連線。" : "No connections in this direction.") + "</div>";
          return;
        }
        box.innerHTML = rows.map((e) => {
          const other = dir === "out" ? e.target : e.source;
          const w = e.normalized_weight;
          const isSel = !!(selectedEdge &&
            e.source === selectedEdge.source && e.target === selectedEdge.target);
          return '<div class="conn-row conn-row--link" role="button" tabindex="0" data-pair="' +
            e.source + ">" + e.target + '" aria-pressed="' + isSel + '" title="' + nameOf(other) +
            " (n=" + e.n_experiments + ')">' +
            '<span class="conn-acr">' + other + "</span>" +
            '<span class="conn-bar"><span style="width:' + (w * 100).toFixed(1) + '%"></span></span>' +
            '<span class="conn-val">' + w.toFixed(2) + "</span></div>";
        }).join("");
      });
    }

    // Grouped picker: one collapsible section per system, in the order the
    // systems first appear in the graph (NODE_SPECS is already sorted that
    // way). Keeps 17 regions scannable instead of a flat wall of buttons.
    function pickerGroups() {
      const order = [];
      const groups = {};
      NODE_KEYS.forEach((k) => {
        const s = BY_KEY[k].system || "other";
        if (!groups[s]) { groups[s] = []; order.push(s); }
        groups[s].push(k);
      });
      return { order: order, groups: groups };
    }

    function renderPicker() {
      const { order, groups } = pickerGroups();
      document.getElementById("connPick").innerHTML = order.map((s) => {
        const sm = SYSTEMS[s] || { en: s, zh: s };
        const open = sysOpen[s] !== false;
        const body = groups[s].map((k) =>
          '<button type="button" class="conn-pick" data-key="' + k + '" aria-pressed="' +
          (k === selected) + '"><b>' + k + "</b> &middot; " + nameOf(k) + "</button>").join("");
        return '<button type="button" class="conn-sys" data-sys="' + s +
          '" aria-expanded="' + open + '"><span>' + (LANG === "zh" ? sm.zh : sm.en) +
          '</span><span class="chevron">' + (open ? "\u25be" : "\u25b8") + "</span></button>" +
          '<div class="conn-sys-body" style="display:' + (open ? "block" : "none") + '">' +
          body + "</div>";
      }).join("");
    }

    // `frame` is the raw activity (numbers shown verbatim); `disp` is the
    // gamma-scaled display intensity that drives the bars and the 3D glow.
    function renderActivity(frame, step, disp) {
      const label = document.getElementById("connStepLabel");
      label.textContent = (LANG === "zh" ? "步驟 " : "Step ") + step + " / " + P.steps;
      const order = NODE_KEYS.map((k, i) => [k, frame ? frame[i] : 0, disp ? disp[i] : 0])
        .sort((a, b) => b[1] - a[1]);
      document.getElementById("connActivity").innerHTML = order.map(([k, v, d]) =>
        '<div class="conn-row"><span class="conn-acr">' + k + "</span>" +
        '<span class="conn-bar"><span style="width:' + (d * 100).toFixed(1) + '%"></span></span>' +
        '<span class="conn-val">' + fmtActivity(v) + "</span></div>").join("");
    }

    function clearActivity() {
      run = null;
      NODE_KEYS.forEach((k) => paint(k, 0));
      EDGES.forEach((rec) => {
        const m = rec.mesh.material;
        if (m && m.emissive) m.emissiveIntensity = 0.35;
      });
      host.dataset.connActive = "0";
      renderActivity(null, 0);
    }

    function renderTraceOptions() {
      const sel = document.getElementById("connTraceTo");
      if (!sel) return;
      const prev = sel.value;
      sel.innerHTML = NODE_KEYS.filter((k) => k !== selected).map((k) =>
        '<option value="' + k + '">' + k + " &middot; " + nameOf(k) + "</option>").join("");
      if (prev && prev !== selected && BY_KEY[prev]) sel.value = prev;
    }

    function evidenceTag(t) { return '<span class="conn-tag">' + t + "</span>"; }

    function renderDetail() {
      const box = document.getElementById("connDetail");
      if (!box) return;
      if (selectedEdge) {
        const e = selectedEdge;
        const raw = (e.raw_weight >= 1) ? e.raw_weight.toFixed(3) : e.raw_weight.toPrecision(3);
        box.hidden = false;
        box.innerHTML =
          '<div class="conn-detail-head"><b>' + e.source + " &rarr; " + e.target + "</b>" +
          '<button type="button" id="connDetailClose" aria-label="close">\u00d7</button></div>' +
          '<div class="conn-detail-line">' + nameOf(e.source) + "</div>" +
          '<div class="conn-detail-line">&darr;</div>' +
          '<div class="conn-detail-line">' + nameOf(e.target) + "</div>" +
          '<div class="conn-detail-line">raw ' + raw + " &middot; " + (e.units || "") + "</div>" +
          '<div class="conn-detail-line">normalized ' + e.normalized_weight.toFixed(3) + "</div>" +
          '<div class="conn-detail-line">n = ' + e.n_experiments + "</div>" +
          '<div class="conn-detail-note">' + (LANG === "zh" ? e.note_zh : e.note_en) + "</div>" +
          '<div class="conn-detail-line">' + evidenceTag(e.evidence_class) + "</div>";
        document.getElementById("connDetailClose").addEventListener("click", () => selectEdge(null));
        return;
      }
      if (traceNodes.length > 1) {
        box.hidden = false;
        const hops = [];
        for (let i = 0; i < traceNodes.length - 1; i++) {
          hops.push(REC_BY_PAIR.get(traceNodes[i] + ">" + traceNodes[i + 1]));
        }
        box.innerHTML =
          '<div class="conn-detail-head"><b>' + traceNodes.join(" &rarr; ") + "</b>" +
          '<button type="button" id="connDetailClose" aria-label="close">\u00d7</button></div>' +
          hops.map((rec) => rec ? ('<div class="conn-detail-line">' + rec.edge.source + " &rarr; " +
            rec.edge.target + " &middot; norm " + rec.edge.normalized_weight.toFixed(3) +
            " &middot; n=" + rec.edge.n_experiments + "</div>") : "").join("") +
          '<div class="conn-detail-note">' + (LANG === "zh"
            ? "最強加權路徑(依 normalized_weight 乘積)。此為呈現輔助,並非訊號傳遞路徑的主張。"
            : "Strongest weighted path (product of normalized weights). A display aid, not a claim about signal routing.") + "</div>" +
          '<div class="conn-detail-line">' + evidenceTag(EDGE_CLASS) + "</div>";
        document.getElementById("connDetailClose").addEventListener("click", () => clearTrace());
        return;
      }
      if (detailMsg) {
        box.hidden = false;
        box.innerHTML = '<div class="conn-detail-line">' + detailMsg + "</div>";
        return;
      }
      box.hidden = true;
      box.innerHTML = "";
    }

    function selectEdge(edge) {
      selectedEdge = edge || null;
      if (selectedEdge) {
        traceNodes = []; traceRecs = []; traceRun = null; pulse.visible = false;
      }
      detailMsg = "";
      renderLists();
      renderEdges();
      renderDetail();
    }

    function clearTrace() {
      traceNodes = []; traceRecs = []; traceRun = null; pulse.visible = false;
      detailMsg = "";
      renderDetail();
      renderEdges();
    }

    function traceTo(target) {
      if (!target || target === selected) return;
      const path = strongestPath(selected, target);
      if (!path || path.length < 2) {
        traceNodes = []; traceRecs = []; traceRun = null; pulse.visible = false;
        selectedEdge = null;
        detailMsg = LANG === "zh" ? "此方向找不到路徑。" : "No path found in this direction.";
        renderLists();
        renderEdges();
        renderDetail();
        return;
      }
      selectedEdge = null;
      detailMsg = "";
      traceNodes = path;
      traceRecs = [];
      for (let i = 0; i < path.length - 1; i++) {
        const rec = REC_BY_PAIR.get(path[i] + ">" + path[i + 1]);
        if (rec) traceRecs.push(rec);
      }
      traceRun = reduced ? null : { t0: performance.now() };
      renderLists();
      renderEdges();
      renderDetail();
    }

    function selectRegion(key) {
      if (!BY_KEY[key]) return;
      selected = key;
      selectedEdge = null;
      detailMsg = "";
      traceNodes = []; traceRecs = []; traceRun = null; pulse.visible = false;
      renderPicker();
      renderTraceOptions();
      renderLists();
      renderEdges();
      renderDetail();
    }

    // ---- hover tooltip: name a connection tube the instant the pointer
    // touches it, without needing a click. Edges only (regions already get
    // scene.js's own hover callouts). Suppressed while a mouse button is
    // held so it never fights with orbit-dragging. ----
    const edgeTip = document.createElement("div");
    edgeTip.id = "edgeTip";
    edgeTip.hidden = true;
    document.body.appendChild(edgeTip);
    const edgeTipStyle = document.createElement("style");
    edgeTipStyle.textContent = [
      "#edgeTip{position:fixed;z-index:50;pointer-events:none;max-width:240px;",
      "padding:7px 10px;border-radius:8px;background:rgba(15,20,26,.94);",
      "border:1px solid rgba(255,194,102,.45);color:#e9edf1;",
      "font:12px/1.4 -apple-system,'Segoe UI',system-ui,sans-serif;",
      "box-shadow:0 8px 22px rgba(0,0,0,.35)}",
      "#edgeTip b{color:#ffc266}",
      "#edgeTip .edge-tip-val{opacity:.7;font-size:11px;margin-top:2px}",
    ].join("");
    document.head.appendChild(edgeTipStyle);

    function showEdgeTip(edge, clientX, clientY) {
      edgeTip.innerHTML =
        "<b>" + edge.source + "</b> &rarr; <b>" + edge.target + "</b><br />" +
        "<span>" + nameOf(edge.source) + " &rarr; " + nameOf(edge.target) + "</span>" +
        '<div class="edge-tip-val">' +
        (LANG === "zh" ? "強度 " : "weight ") + edge.normalized_weight.toFixed(2) +
        " &middot; n=" + edge.n_experiments + "</div>";
      edgeTip.style.left = Math.min(window.innerWidth - 250, clientX + 14) + "px";
      edgeTip.style.top = Math.max(8, clientY - 40) + "px";
      edgeTip.hidden = false;
    }
    function hideEdgeTip() { edgeTip.hidden = true; }

    // ---- click a region in 3D as well as in the list; tubes first, so a
    // ---- click on a drawn connection inspects that edge (best-effort) ----
    (function pickInScene() {
      const ray = new THREE.Raycaster();
      const pt = new THREE.Vector2();
      const targets = NODE_KEYS.map((k) => meshes[k]).filter(Boolean);
      const edgeMeshes = EDGES.map((rec) => rec.mesh);
      const canvas = renderer.domElement;
      let downAt = null;
      canvas.addEventListener("pointerdown", (ev) => { downAt = [ev.clientX, ev.clientY]; });
      canvas.addEventListener("pointerup", (ev) => {
        if (!downAt) return;
        const moved = Math.abs(ev.clientX - downAt[0]) + Math.abs(ev.clientY - downAt[1]);
        downAt = null;
        if (moved > 6) return;
        const r = canvas.getBoundingClientRect();
        pt.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
        pt.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
        ray.setFromCamera(pt, camera);
        const eHits = ray.intersectObjects(edgeMeshes.filter((m) => m.visible), false);
        if (eHits.length) {
          const rec = EDGES.find((cand) => cand.mesh === eHits[0].object);
          if (rec) { selectEdge(rec.edge); return; }
        }
        const hits = ray.intersectObjects(targets.filter((m) => m.visible), false);
        if (!hits.length) return;
        const hit = hits[0].object;
        const key = NODE_KEYS.find((k) => meshes[k] === hit);
        if (key) selectRegion(key);
      });
      canvas.addEventListener("pointermove", (ev) => {
        if (ev.buttons !== 0) { hideEdgeTip(); return; } // dragging/orbiting
        const r = canvas.getBoundingClientRect();
        pt.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
        pt.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
        ray.setFromCamera(pt, camera);
        const eHits = ray.intersectObjects(edgeMeshes.filter((m) => m.visible), false);
        if (!eHits.length) { hideEdgeTip(); canvas.style.cursor = ""; return; }
        const rec = EDGES.find((cand) => cand.mesh === eHits[0].object);
        if (!rec) { hideEdgeTip(); return; }
        canvas.style.cursor = "pointer";
        showEdgeTip(rec.edge, ev.clientX, ev.clientY);
      });
      canvas.addEventListener("pointerleave", hideEdgeTip);
    })();

    // ---- controls ----
    document.getElementById("connPick").addEventListener("click", (ev) => {
      const sysBtn = ev.target.closest(".conn-sys");
      if (sysBtn) {
        const s = sysBtn.dataset.sys;
        sysOpen[s] = sysOpen[s] === false; // undefined => open, first click closes
        renderPicker();
        return;
      }
      const btn = ev.target.closest(".conn-pick");
      if (btn) selectRegion(btn.dataset.key);
    });
    document.getElementById("connFilter").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-dir]");
      if (!btn) return;
      direction = btn.dataset.dir;
      document.querySelectorAll("#connFilter button").forEach((b) => {
        b.setAttribute("aria-pressed", String(b.dataset.dir === direction));
      });
      renderLists();
      renderEdges();
    });
    ["connOut", "connIn"].forEach((id) => {
      const box = document.getElementById(id);
      box.addEventListener("click", (ev) => {
        const row = ev.target.closest(".conn-row--link");
        if (!row) return;
        const rec = REC_BY_PAIR.get(row.dataset.pair);
        if (rec) selectEdge(rec.edge);
      });
      box.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const row = ev.target.closest(".conn-row--link");
        if (!row) return;
        ev.preventDefault();
        const rec = REC_BY_PAIR.get(row.dataset.pair);
        if (rec) selectEdge(rec.edge);
      });
    });
    document.getElementById("connTraceBtn").addEventListener("click", () => {
      traceTo(document.getElementById("connTraceTo").value);
    });
    document.getElementById("connTraceClear").addEventListener("click", clearTrace);
    document.getElementById("connFocus").addEventListener("click", () => {
      focusMode = !focusMode;
      document.getElementById("connFocus").setAttribute("aria-pressed", String(focusMode));
      renderEdges();
    });
    slider.addEventListener("input", () => {
      shown = parseInt(slider.value, 10);
      document.getElementById("connSliderVal").textContent = String(shown);
      renderLists();
      renderEdges();
    });
    document.getElementById("connRun").addEventListener("click", () => {
      const frames = propagate(selected);
      if (reduced) {
        // no animation for reduced-motion users: show the final step, but
        // still via the display transform so it is visible
        run = null;
        const last = frames[frames.length - 1];
        const disp = last.map((v) => displayValue(v));
        NODE_KEYS.forEach((k, i) => paint(k, disp[i]));
        EDGES.forEach((rec) => {
          const m = rec.mesh.material;
          if (!m || !m.emissive) return;
          const s = disp[IDX[rec.edge.source]];
          m.emissiveIntensity = 0.35 + 0.9 * P.gain * rec.edge.normalized_weight * s;
        });
        renderActivity(last, P.steps, disp);
        host.dataset.connActive = String(disp.filter((d) => d > 0).length);
        host.dataset.connPeak = (Math.max.apply(null, Array.from(disp)) || 0).toFixed(3);
        return;
      }
      run = { frames: frames, t0: performance.now() };
    });
    document.getElementById("connReset").addEventListener("click", clearActivity);

    // ================================================================
    // Phase 4: Virtual Mouse Running-Wheel behavior layer.
    // Four separate systems, all downstream of the SAME raw network
    // activity the Stimulate view uses:
    //   brainStep()   -> raw activity (existing recurrence + engineered cue)
    //   decodeMotor() -> motorDrive (engineered readout; RAW activity only)
    //   stepWheelPhysics() -> wheel physics
    //   theta/LFP     -> synthetic CA1-like signal
    // Display scaling (displayValue/paint) is visualization only and is
    // NEVER read by any of the four systems above.
    // ================================================================
    const RUN = PAYLOAD.running || {};
    const RC = {
      motorWeights: RUN.motor_weights || { MOp: 0.5, MOs: 0.5 },
      threshold: (RUN.motor_threshold != null) ? RUN.motor_threshold : 0.05,
      maxSpeed: RUN.max_speed_cms || 30,
      driveGain: RUN.drive_gain || 20,
      drag: RUN.drag || 1.5,
      radius: RUN.wheel_radius_cm || 8,
      cueInput: (RUN.run_cue_input != null) ? RUN.run_cue_input : 1.0,
      brainStepHz: RUN.brain_step_hz || 8,
      stopEps: (RUN.stop_speed_eps != null) ? RUN.stop_speed_eps : 0.2,
      lfp: RUN.lfp || { base_hz: 6, span_hz: 3, half_sat_cms: 10,
                        amp_base: 0.3, amp_span: 0.7, noise_amp: 0.02, seed: 1234 },
    };
    const SIM = {
      active: false, cue: 0, time: 0, brainAcc: 0, traceAcc: 0,
      activity: new Float64Array(NODE_KEYS.length),
      velocity: 0, distance: 0, angle: 0,
      motorDrive: 0, motorRaw: 0,
      lfpPhase: 0, lfpIndex: 0, thetaHz: RC.lfp.base_hz,
      trace: [], devDrive: null,
    };
    const TRACE_SECONDS = 8;
    const TRACE_HZ = 30;
    const RUN_STATE_ZH = { RUNNING: "跑步中", COASTING: "滑行", STOPPED: "停止" };

    function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
    function motorRegions() { return Object.keys(RC.motorWeights); }
    function rawOf(acr) { const i = IDX[acr]; return i === undefined ? 0 : SIM.activity[i]; }

    // B. motor decoder: engineered readout from RAW activity only
    function decodeMotor() {
      let raw = 0;
      for (const r of motorRegions()) raw += (RC.motorWeights[r] || 0) * rawOf(r);
      SIM.motorRaw = raw;
      return clamp01((raw - RC.threshold) / (1 - RC.threshold));
    }

    // A. one network diffusion step, the existing recurrence, plus the
    // engineered run cue injected as an additive input at the motor regions
    function brainStep() {
      const n = NODE_KEYS.length;
      const nx = new Float64Array(n);
      for (let i = 0; i < n; i++) nx[i] = P.decay * SIM.activity[i];
      for (const e of CONN.edges) {
        nx[IDX[e.target]] += P.gain * e.normalized_weight * SIM.activity[IDX[e.source]];
      }
      if (SIM.cue > 0) {
        for (const r of motorRegions()) {
          if (IDX[r] !== undefined) nx[IDX[r]] += SIM.cue * RC.cueInput;
        }
      }
      for (let i = 0; i < n; i++) nx[i] = Math.min(P.clip[1], Math.max(P.clip[0], nx[i]));
      SIM.activity = nx;
    }

    // C. first-order wheel physics. The button never sets velocity directly.
    function stepWheelPhysics(drive, dt) {
      const accel = RC.driveGain * drive - RC.drag * SIM.velocity;
      SIM.velocity = Math.min(RC.maxSpeed, Math.max(0, SIM.velocity + accel * dt));
      SIM.distance += SIM.velocity * dt;
      SIM.angle += (SIM.velocity / RC.radius) * dt;
    }

    // D. synthetic CA1 theta-like LFP: a documented model mapping, not a
    // fitted equation. Frequency depends on wheel speed, never on display.
    function thetaFrequency(v) {
      return RC.lfp.base_hz + RC.lfp.span_hz * v / (v + RC.lfp.half_sat_cms);
    }
    function thetaAmplitude(v) {
      return RC.lfp.amp_base + RC.lfp.amp_span * clamp01(v / RC.maxSpeed);
    }
    function noiseAt(i) {
      const x = Math.sin((i + 1) * 12.9898 + RC.lfp.seed * 0.001) * 43758.5453;
      const f = x - Math.floor(x);
      return f * 2 - 1;
    }
    function updateLfpSample(dt) {
      const v = SIM.velocity;
      const f = thetaFrequency(v);
      SIM.thetaHz = f;
      SIM.lfpPhase += 2 * Math.PI * f * dt;
      const value = thetaAmplitude(v) * Math.sin(SIM.lfpPhase) +
        RC.lfp.noise_amp * noiseAt(SIM.lfpIndex);
      SIM.lfpIndex += 1;
      return value;
    }

    function runStateLabel() {
      if (SIM.velocity <= RC.stopEps) return "STOPPED";
      return SIM.cue > 0 ? "RUNNING" : "COASTING";
    }

    function paintSimulation() {
      let peak = 0;
      NODE_KEYS.forEach((k, i) => {
        const d = displayValue(SIM.activity[i]);
        paint(k, d);
        if (d > peak) peak = d;
      });
      EDGES.forEach((rec) => {
        const m = rec.mesh.material;
        if (!m || !m.emissive) return;
        const s = displayValue(SIM.activity[IDX[rec.edge.source]]);
        m.emissiveIntensity = 0.35 + 0.9 * P.gain * rec.edge.normalized_weight * s;
      });
      host.dataset.connActive = String(NODE_KEYS.reduce((c, k, i) =>
        c + (displayValue(SIM.activity[i]) > 0 ? 1 : 0), 0));
      host.dataset.connPeak = peak.toFixed(3);
      host.dataset.runSpeed = SIM.velocity.toFixed(2);
      host.dataset.runDrive = SIM.motorDrive.toFixed(3);
    }

    function updateRunReadouts() {
      const st = runStateLabel();
      document.getElementById("runState").textContent = (LANG === "zh") ? RUN_STATE_ZH[st] : st;
      document.getElementById("runSpeed").textContent = SIM.velocity.toFixed(1);
      document.getElementById("runDist").textContent = String(Math.round(SIM.distance));
      document.getElementById("runDrive").textContent = SIM.motorDrive.toFixed(2);
      document.getElementById("runTime").textContent = SIM.time.toFixed(1);
      document.getElementById("runTheta").textContent = "\u03b8 " + SIM.thetaHz.toFixed(1) + " Hz";
      document.getElementById("runMotorVal").textContent = SIM.motorDrive.toFixed(2);
      document.getElementById("runSpeedVal").textContent = SIM.velocity.toFixed(1) + " cm/s";
      const spokes = document.getElementById("runWheelSpokes");
      if (spokes) {
        const deg = (SIM.angle * 180 / Math.PI) % 360;
        spokes.setAttribute("transform", "rotate(" + deg.toFixed(1) + " 50 50)");
      }
    }

    function renderSimActivity() {
      const label = document.getElementById("connStepLabel");
      label.textContent = (LANG === "zh" ? "跑步模擬 " : "Running ") + SIM.time.toFixed(1) + " s";
      const disp = NODE_KEYS.map((k, i) => displayValue(SIM.activity[i]));
      const order = NODE_KEYS.map((k, i) => [k, SIM.activity[i], disp[i]])
        .sort((a, b) => b[1] - a[1]);
      document.getElementById("connActivity").innerHTML = order.map(([k, v, d]) =>
        '<div class="conn-row"><span class="conn-acr">' + k + "</span>" +
        '<span class="conn-bar"><span style="width:' + (d * 100).toFixed(1) + '%"></span></span>' +
        '<span class="conn-val">' + fmtActivity(v) + "</span></div>").join("");
    }

    function drawTrace() {
      const cv = document.getElementById("runTrace");
      if (!cv || !cv.getContext) return;
      const ctx = cv.getContext("2d");
      const W = cv.width, H = cv.height;
      const lanes = 3, laneH = H / lanes, pad = 8;
      const usable = laneH - pad * 2;
      const yOf = (vn, lane) => lane * laneH + pad + (1 - clamp01(vn)) * usable;
      ctx.clearRect(0, 0, W, H);
      // lane backgrounds + a visible zero baseline in every lane, so a stopped
      // value reads as "zero here", not as a missing line
      for (let lane = 0; lane < lanes; lane++) {
        ctx.fillStyle = "rgba(255,255,255,.035)";
        ctx.fillRect(0, lane * laneH + 1, W, laneH - 2);
        ctx.strokeStyle = "rgba(255,255,255,.16)";
        ctx.lineWidth = 1;
        const by = yOf(lane === 0 ? 0.5 : 0.0, lane);
        ctx.beginPath(); ctx.moveTo(0, by); ctx.lineTo(W, by); ctx.stroke();
      }
      const n = SIM.trace.length;
      if (n < 2) return;
      const cap = TRACE_SECONDS * TRACE_HZ;
      const x = (idx) => (idx / (cap - 1)) * W;
      const series = (get, norm, color, lane) => {
        ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.beginPath();
        for (let i = 0; i < n; i++) {
          const px = x(cap - n + i), py = yOf(norm(get(SIM.trace[i])), lane);
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.stroke();
      };
      series((s) => s.lfp, (v) => (v + 1) / 2, "#84dcc5", 0);   // CA1 LFP-like
      series((s) => s.motor, (v) => v, "#e8c46a", 1);           // motor drive
      series((s) => s.speed, (v) => v / RC.maxSpeed, "#e88b6a", 2); // wheel speed
    }

    function updateSimulation(dt) {
      if (!SIM.active) return;
      SIM.time += dt;
      const stepSec = 1 / RC.brainStepHz;
      SIM.brainAcc += dt;
      let guard = 0;
      while (SIM.brainAcc >= stepSec && guard < 5) {
        brainStep(); SIM.brainAcc -= stepSec; guard += 1;
      }
      const drive = (SIM.devDrive != null) ? SIM.devDrive : decodeMotor();
      SIM.motorDrive = drive;
      stepWheelPhysics(drive, dt);
      const lfp = updateLfpSample(dt);
      SIM.traceAcc += dt;
      if (SIM.traceAcc >= 1 / TRACE_HZ) {
        SIM.traceAcc = 0;
        SIM.trace.push({ lfp: lfp, motor: drive, speed: SIM.velocity });
        while (SIM.trace.length > TRACE_SECONDS * TRACE_HZ) SIM.trace.shift();
        renderSimActivity();
      }
      paintSimulation();
      updateRunReadouts();
      drawTrace();
    }

    // the rail panel and the right-side mouse stage share this one controller
    function setRunPressed(pressed) {
      ["runStart", "mouseStart"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.setAttribute("aria-pressed", String(pressed));
      });
    }

    function resetSimulation() {
      SIM.active = false; SIM.cue = 0; SIM.time = 0; SIM.brainAcc = 0; SIM.traceAcc = 0;
      SIM.activity = new Float64Array(NODE_KEYS.length);
      SIM.velocity = 0; SIM.distance = 0; SIM.angle = 0;
      SIM.motorDrive = 0; SIM.motorRaw = 0;
      SIM.lfpPhase = 0; SIM.lfpIndex = 0; SIM.thetaHz = RC.lfp.base_hz;
      SIM.trace = []; SIM.devDrive = null;
      const toggle = document.getElementById("runDevToggle"); if (toggle) toggle.checked = false;
      const range = document.getElementById("runDevSlider"); if (range) range.value = "0";
      const devVal = document.getElementById("runDevVal"); if (devVal) devVal.textContent = "0.00";
      setRunPressed(false);
      clearActivity();     // reset the impulse animation and the activity panel
      paintSimulation();   // re-paint all-zero region activity
      updateRunReadouts();
      updateMouseStage();
      drawTrace();
    }

    function startRunning() {
      clearActivity();     // stop any impulse playback so the two do not fight
      SIM.active = true;
      SIM.cue = 1;
      setRunPressed(true);
      // one-time onboarding cue: stop drawing attention once it has done its job
      const cta = document.getElementById("mouseStart");
      if (cta) cta.classList.remove("ms-pulse");
    }
    function stopInput() {
      SIM.cue = 0;
      setRunPressed(false);
    }

    function updateBehaviorLang() {
      const lines = (LANG === "zh") ? [
        "<b>神經活動</b>:腦區層連結模型",
        "<b>運動輸出</b>:由 MOp/MOs 活動的工程解碼",
        "<b>跑輪</b>:簡易虛擬物理模型",
        "<b>CA1 訊號</b>:合成 theta 類 LFP 視覺化",
        "<span style='opacity:.7'>網路傳播、運動解碼與合成 LFP 為計算視覺化模型," +
        "不代表完整的神經元、脊髓或肌肉生理模擬。</span>",
      ] : [
        "<b>Neural activity</b>: region-level connectivity model",
        "<b>Motor output</b>: engineered decoder from MOp/MOs activity",
        "<b>Wheel</b>: simple virtual physics model",
        "<b>CA1 signal</b>: synthetic theta-like LFP visualization",
        "<span style='opacity:.7'>Network propagation, motor decoding and synthetic LFP are " +
        "computational visualizations. They do not reproduce complete neuronal, spinal or " +
        "muscular physiology.</span>",
      ];
      document.getElementById("runInfo").innerHTML = lines.join("<br />");
      updateRunReadouts();
    }

    document.getElementById("runStart").addEventListener("click", startRunning);
    document.getElementById("runStop").addEventListener("click", stopInput);
    document.getElementById("runReset").addEventListener("click", resetSimulation);
    document.getElementById("runDevToggle").addEventListener("change", (ev) => {
      if (ev.target.checked) {
        SIM.active = true;
        SIM.devDrive = parseFloat(document.getElementById("runDevSlider").value) || 0;
      } else {
        SIM.devDrive = null;
      }
    });
    document.getElementById("runDevSlider").addEventListener("input", (ev) => {
      const value = parseFloat(ev.target.value) || 0;
      document.getElementById("runDevVal").textContent = value.toFixed(2);
      if (document.getElementById("runDevToggle").checked) {
        SIM.active = true;
        SIM.devDrive = value;
      }
    });

    // ---- right-side virtual mouse stage: a mouse running on a wheel. The
    // gait and wheel rotation are read OUT of the shared SIM state, so this
    // is a downstream view of the same neural controller, not a separate
    // animation. It lives outside the rail so it is always visible. ----
    const stage = document.createElement("div");
    stage.id = "mouseStage";
    stage.innerHTML = [
      '<div class="ms-title" data-conn-en="Virtual mouse on wheel" data-conn-zh="虛擬小鼠跑滾輪"></div>',
      '<div class="ms-cta" data-conn-en="Press Start to see the brain drive a running mouse." ' +
        'data-conn-zh="按下開始，看大腦活動驅動小鼠跑步。"></div>',
      '<div class="ms-btns">',
      '<button type="button" id="mouseStart" class="ms-pulse" aria-pressed="false" ' +
        'data-conn-en="▶ Start running" data-conn-zh="▶ 開始跑步"></button>',
      '<button type="button" id="mouseStop" data-conn-en="Stop" data-conn-zh="停止"></button>',
      "</div>",
      '<svg viewBox="0 0 200 152" aria-hidden="true">',
      '<line class="ms-stand" x1="100" y1="126" x2="100" y2="146"></line>',
      '<line class="ms-stand" x1="72" y1="146" x2="128" y2="146"></line>',
      '<circle class="ms-rim" cx="100" cy="72" r="54"></circle>',
      '<circle class="ms-rim" cx="100" cy="72" r="48"></circle>',
      '<g id="mouseWheelSpokes">',
      '<line class="ms-spoke" x1="100" y1="24" x2="100" y2="120"></line>',
      '<line class="ms-spoke" x1="52" y1="72" x2="148" y2="72"></line>',
      '<line class="ms-spoke" x1="66" y1="38" x2="134" y2="106"></line>',
      '<line class="ms-spoke" x1="134" y1="38" x2="66" y2="106"></line>',
      "</g>",
      '<g id="msMouse">',
      '<path class="ms-tail" id="msTail" d="M82 106 q-18 6 -26 -6"></path>',
      '<ellipse class="ms-body" cx="100" cy="104" rx="19" ry="10"></ellipse>',
      '<circle class="ms-head" cx="120" cy="99" r="7"></circle>',
      '<circle class="ms-ear" cx="116" cy="93" r="3"></circle>',
      '<circle class="ms-eye" cx="122" cy="98" r="1.3"></circle>',
      '<line class="ms-leg" id="msLegFL" x1="110" y1="110" x2="112" y2="118"></line>',
      '<line class="ms-leg" id="msLegFR" x1="106" y1="111" x2="108" y2="118"></line>',
      '<line class="ms-leg" id="msLegBL" x1="90" y1="111" x2="88" y2="118"></line>',
      '<line class="ms-leg" id="msLegBR" x1="86" y1="110" x2="84" y2="118"></line>',
      "</g>",
      "</svg>",
      '<div class="ms-readout"><span data-conn-en="Speed" data-conn-zh="速度"></span>',
      '<b id="msSpeed">0.0 cm/s</b></div>',
      '<div class="ms-readout"><span data-conn-en="State" data-conn-zh="狀態"></span>',
      '<b id="msState">STOPPED</b></div>',
      '<div class="ms-caption" data-conn-en="Driven by this page’s simulated network activity — ' +
        'an engineered visualization, not real muscle or spinal physiology." ' +
        'data-conn-zh="由本頁模擬的神經活動驅動，' +
        '屬工程化視覺化，並非真實肌肉或' +
        '脊髓生理。"></div>',
    ].join("");
    document.body.appendChild(stage);

    function updateMouseStage() {
      const spokes = document.getElementById("mouseWheelSpokes");
      if (spokes) {
        spokes.setAttribute("transform",
          "rotate(" + ((SIM.angle * 180 / Math.PI) % 360).toFixed(1) + " 100 72)");
      }
      const running = SIM.velocity > RC.stopEps;
      // gait phase comes from distance travelled, so the legs stop when the
      // wheel stops and speed up as it speeds up
      const phase = SIM.distance * 1.5;
      const swing = running ? 5 : 0;
      const a = Math.sin(phase) * swing;
      const b = Math.sin(phase + Math.PI) * swing;
      const setLeg = (id, x, y) => {
        const el = document.getElementById(id);
        if (el) { el.setAttribute("x2", x.toFixed(1)); el.setAttribute("y2", y.toFixed(1)); }
      };
      setLeg("msLegFL", 112 + a, 118); setLeg("msLegFR", 108 + b, 118);
      setLeg("msLegBL", 88 + b, 118); setLeg("msLegBR", 84 + a, 118);
      const mouse = document.getElementById("msMouse");
      if (mouse) {
        mouse.setAttribute("transform",
          "translate(0," + (running ? (Math.sin(phase * 2) * 1.3).toFixed(2) : "0") + ")");
      }
      const tail = document.getElementById("msTail");
      if (tail) {
        tail.setAttribute("d", "M82 106 q-18 " +
          (6 + (running ? Math.sin(phase) * 3 : 0)).toFixed(1) + " -26 -6");
      }
      const sp = document.getElementById("msSpeed");
      if (sp) sp.textContent = SIM.velocity.toFixed(1) + " cm/s";
      const st = document.getElementById("msState");
      if (st) {
        const label = runStateLabel();
        st.textContent = (LANG === "zh") ? RUN_STATE_ZH[label] : label;
      }
      stage.dataset.mouseRunning = running ? "1" : "0";
      stage.dataset.gait = phase.toFixed(2);
    }

    document.getElementById("mouseStart").addEventListener("click", startRunning);
    document.getElementById("mouseStop").addEventListener("click", stopInput);

    // ---- one master loop: the existing impulse animation and the behavior
    // simulation share this rAF clock; there is no second timer ----
    let lastFrameMs = performance.now();
    (function connTick() {
      const nowMs = performance.now();
      const dt = Math.min(0.1, (nowMs - lastFrameMs) / 1000);
      lastFrameMs = nowMs;
      if (SIM.active) {
        updateSimulation(dt);
      } else if (run) {
        const elapsed = (performance.now() - run.t0) / STEP_MS;
        const step = Math.min(P.steps, Math.floor(elapsed));
        const frac = Math.min(1, elapsed - step);
        const a = run.frames[step];
        const b = run.frames[Math.min(P.steps, step + 1)];
        // raw, unmodified simulated activity at this instant
        const now = NODE_KEYS.map((k, i) => a[i] + (b[i] - a[i]) * frac);
        // one fixed display scale for the whole run (no per-step max): the
        // same activity value always has the same brightness at any step
        const shown = now.map((v) => displayValue(v));
        NODE_KEYS.forEach((k, i) => paint(k, shown[i]));
        // QA: report the PEAK region's actual material state
        let peakI = 0;
        shown.forEach((d, i) => { if (d > shown[peakI]) peakI = i; });
        const peakMesh = meshes[NODE_KEYS[peakI]];
        if (peakMesh && peakMesh.material && peakMesh.material.emissive) {
          host.dataset.connGlow = peakMesh.material.emissiveIntensity.toFixed(3) +
            "/" + peakMesh.material.emissive.getHexString() + "/" + NODE_KEYS[peakI];
        }
        EDGES.forEach((rec) => {
          const m = rec.mesh.material;
          if (!m || !m.emissive) return;
          // direction cue: an edge glows with its SOURCE's visible activity
          const src = shown[IDX[rec.edge.source]];
          m.emissiveIntensity = 0.35 + 0.9 * P.gain * rec.edge.normalized_weight * src;
        });
        renderActivity(now, step, shown);
        host.dataset.connActive = String(shown.filter((d) => d > 0).length);
        host.dataset.connPeak = (Math.max.apply(null, Array.from(shown)) || 0).toFixed(3);
        if (elapsed >= P.steps) run = null;
      }
      // trace pulse: deterministic (time-based, no RNG), loops until cleared
      if (traceRecs.length) {
        if (reduced) {
          const last = traceRecs[traceRecs.length - 1].mesh.userData.curve;
          if (last) { pulse.position.copy(last.getPointAt(0.999)); pulse.visible = true; }
        } else if (traceRun) {
          const span = traceRecs.length * TRACE_MS;
          const el = (performance.now() - traceRun.t0) % span;
          const i = Math.min(traceRecs.length - 1, Math.floor(el / TRACE_MS));
          const t = (el - i * TRACE_MS) / TRACE_MS;
          const curve = traceRecs[i].mesh.userData.curve;
          if (curve) {
            pulse.position.copy(curve.getPointAt(Math.max(0, Math.min(0.999, t))));
            pulse.visible = true;
          }
        }
      } else {
        pulse.visible = false;
      }
      updateMouseStage();
      requestAnimationFrame(connTick);
    })();

    // ---- bilingual: chain onto the template's applyLang, no template edit ----
    function connApplyLang(lang) {
      document.querySelectorAll("[data-conn-en]").forEach((el) => {
        el.innerHTML = lang === "zh" ? el.dataset.connZh : el.dataset.connEn;
      });
      const prov = CONN.provenance;
      const tag = (t) => '<span class="conn-tag">' + t + "</span>";
      // Tag connectivity with the evidence class carried by the data, not a
      // literal: the page is built from source="allen" (EXPERIMENTAL), but a
      // future mock build would label itself with its own class correctly.
      document.getElementById("connSrc").innerHTML = (lang === "zh" ? [
        "<b>圖譜</b>:" + prov.atlas_space + tag("ATLAS-DERIVED"),
        "<b>年齡</b>:" + prov.age,
        "<b>幾何</b>:Allen 實驗圖譜網格" + tag("ATLAS-DERIVED"),
        "<b>連結</b>:" + prov.dataset + "(下載 " + prov.download_date + ")" + tag(EDGE_CLASS),
        "<b>傳播</b>:網路擴散模型" + tag("COMPUTATIONAL"),
        "<b>正規化</b>:" + prov.normalization,
        "<b>授權</b>:" + prov.license,
      ] : [
        "<b>Atlas</b>: " + prov.atlas_space + tag("ATLAS-DERIVED"),
        "<b>Age</b>: " + prov.age,
        "<b>Geometry</b>: Allen experimental atlas mesh" + tag("ATLAS-DERIVED"),
        "<b>Connectivity</b>: " + prov.dataset + " (downloaded " + prov.download_date + ")" +
          tag(EDGE_CLASS),
        "<b>Propagation</b>: network diffusion model" + tag("COMPUTATIONAL"),
        "<b>Normalization</b>: " + prov.normalization,
        "<b>License</b>: " + prov.license,
      ]).join("<br />");
      document.getElementById("connModelNote").textContent = lang === "zh"
        ? "模型:" + P.model + "(decay " + P.decay + "、gain " + P.gain + "、" +
          P.steps + " 步)。此活動傳播為依據解剖投射強度建立的網路層級視覺化,不代表真實神經元放電時間或生理訊號傳導速度。" +
          "亮度僅為顯示轉換:全場使用固定尺度 display = 活動量^0.45(低於 0.005 不顯示),不影響計算;" +
          "面板數字為未經修改的原始活動值。"
        : "Model: " + P.model + " (decay " + P.decay + ", gain " + P.gain + ", " +
          P.steps + " steps). Connectivity propagation is a network-level visualization " +
          "based on anatomical projection strength. It is not a physiological prediction " +
          "of neuronal spike timing. Glow is a display transform only: a fixed scale " +
          "display = activity^0.45 (below 0.005 not shown) is used for the whole run; the " +
          "panel numbers are the unmodified raw activity values.";
      updateBehaviorLang();
      renderPicker();
      renderTraceOptions();
      renderLists();
      renderDetail();
    }
    const baseApplyLang = applyLang;
    applyLang = function () { baseApplyLang(); connApplyLang(LANG); };

    renderPicker();
    renderTraceOptions();
    renderLists();
    renderEdges();
    clearActivity();
    renderDetail();
    updateBehaviorLang();
    paintSimulation();
    updateRunReadouts();
    drawTrace();
  })();
