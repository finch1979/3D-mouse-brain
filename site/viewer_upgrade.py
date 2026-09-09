"""Presentation layer for assembled viewer copies; source atlases stay untouched.

Append ``viewer_upgrade()`` after the existing navigation and language snippets.
The script moves existing controls without replacing them, preserving the viewer's
event listeners, translations, scientific notes, and embedded offline assets.
"""


def prepare_viewer(html: str) -> str:
    """Fit known 3D viewers to their workspace without touching vendored scripts.

    Original pointer handlers already use the canvas bounding rectangle. Only
    the final application script needs its full-window dimensions replaced.
    Unrecognized viewers and 2D plates are returned unchanged.
    """
    start = html.rfind("<script>")
    end = html.rfind("</script>")
    script = html[start:end]
    camera_anchor = "  const camera = new THREE.PerspectiveCamera("
    renderer_anchor = "  const renderer = new THREE.WebGLRenderer("
    resize_anchor = '  window.addEventListener("resize", resize);'
    if (start < 0 or 'id="scene"' not in html or
            not all(anchor in script for anchor in
                    (camera_anchor, renderer_anchor, resize_anchor,
                     'const container = document.getElementById("scene")'))):
        return html
    if "naViewport" in script:
        return html
    script = script.replace("window.innerWidth", "Math.max(1, container.clientWidth)")
    script = script.replace("window.innerHeight", "Math.max(1, container.clientHeight)")
    script = script.replace(camera_anchor, '  container.dataset.naViewport = "true";\n' + camera_anchor, 1)
    script = script.replace(renderer_anchor,
        "  camera.position.setLength(Math.max(camera.position.length(), EXTENT * 1.85));\n" + renderer_anchor, 1)
    script = script.replace("    camera.updateProjectionMatrix();",
        "    camera.zoom = Math.min(1, camera.aspect) * 0.92;\n    camera.updateProjectionMatrix();")
    script = script.replace("renderer.setClearColor(0x12151a, 1)", "renderer.setClearColor(0x0b1418, 1)")
    script = script.replace(resize_anchor, resize_anchor + """
  const naDefaultPosition = camera.position.clone();
  const naDefaultTarget = controls.target.clone();
  document.addEventListener('neuro-reset-view', () => {
    camera.position.copy(naDefaultPosition);
    controls.target.copy(naDefaultTarget);
    controls.autoRotate = false;
    controls.update();
    resize();
  });
""", 1)
    return html[:start] + script + html[end:]


def viewer_upgrade() -> str:
    """Return a self-contained, progressively applied viewer interface."""
    return r"""
<style id="neuroViewerUpgradeStyle">
  #neuroNav { min-height:40px; border-radius:6px; }
  a:focus-visible, button:focus-visible, input:focus-visible,
  [role="button"]:focus-visible, canvas:focus-visible {
    outline:2px solid #84dcc5; outline-offset:4px;
  }
  body.na-upgrade {
    --bg:#0b1418; --panel:rgba(15,27,32,.96); --panel-border:#2c4148;
    --text:#f1f0e8; --text-dim:#b1c1c5; --text-faint:#9cb0b5;
    --sans:"Segoe UI","Microsoft JhengHei","PingFang TC",system-ui,sans-serif;
    font-family:var(--sans);
  }
  .na-upgrade #scene[data-na-viewport] { inset:66px 0 0; }
  .na-upgrade.na-panel-open #scene[data-na-viewport] { left:370px; }
  body.na-upgrade::before {
    content:""; position:fixed; inset:0 0 auto; height:66px; z-index:25;
    background:rgba(11,20,24,.94); border-bottom:1px solid #26383e;
    pointer-events:none;
  }
  .na-upgrade #neuroNav {
    left:20px; top:13px; transform:none; padding:0 12px; color:#d9e8e7;
    border-color:#31494f; background:transparent; font-size:11px;
    letter-spacing:.035em;
  }
  .na-upgrade #neuroNav:hover { border-color:#84dcc5; color:#84dcc5; }
  .na-upgrade #langToggle {
    right:20px; top:13px; min-height:40px; min-width:62px; z-index:60;
    border-radius:6px; padding:8px 14px; background:transparent;
  }
  #naWorkspaceTitle {
    position:fixed; top:23px; left:360px; right:110px; z-index:30;
    color:#adbfbe; font:12px/20px var(--sans); letter-spacing:.025em;
    overflow:hidden; white-space:nowrap; text-overflow:ellipsis;
    pointer-events:none;
  }
  #naRail {
    position:fixed; top:84px; bottom:90px; left:20px; width:330px;
    display:flex; flex-direction:column; z-index:32; overflow:hidden;
    border:1px solid #31464d; border-radius:8px;
    background:rgba(13,25,30,.97); box-shadow:0 14px 50px #0003;
    color:var(--text); backdrop-filter:blur(16px);
  }
  #naRail[hidden], #naRail [hidden] { display:none!important; }
  .na-rail-top {
    min-height:50px; padding:8px 12px 8px 20px; display:flex;
    align-items:center; justify-content:space-between; gap:12px;
    border-bottom:1px solid #2b3e44; flex:none;
  }
  #naRailLabel { font:10px/1.5 var(--mono); letter-spacing:.14em; color:#84dcc5; }
  #naClose {
    width:34px; height:34px; border:1px solid transparent; border-radius:4px;
    padding:0; background:transparent; color:#c9d9d8; font:24px/1 var(--sans);
    cursor:pointer;
  }
  #naClose:hover { border-color:#4d686f; background:#1c3239; }
  .na-pane { overflow-y:auto; overscroll-behavior:contain; padding:22px 20px; }
  #naRail .ui, #naRail .panel, #naRail nav.crossnav {
    position:static; inset:auto; transform:none; width:auto; min-width:0;
    max-width:none; max-height:none; margin:0; padding:0; pointer-events:auto;
    background:transparent; border:0; border-radius:0; box-shadow:none;
    backdrop-filter:none;
  }
  #naRail header.ui { display:flex; flex-direction:column; gap:15px; }
  #naRail .eyebrow { font:10px/1.75 var(--mono); letter-spacing:.08em; color:#9bafb3; }
  #naRail h1 { font:600 26px/1.3 var(--sans); letter-spacing:-.025em; }
  #naRail h1 #txtTitleMain { display:block; margin-bottom:8px; }
  #naRail h1 #txtTitleSuffix { font-size:19px; font-weight:500; letter-spacing:-.01em; }
  #naRail .subtitle { display:block; font:13px/1.85 var(--sans); max-width:none; color:#bac9cb; }
  #naRail .subtitle b, #naRail .step b { color:#f1f0e8; }
  #naRail .caveat { font:12px/1.75 var(--sans); color:#d8cda7; }
  #naRail .walk { align-self:stretch; margin-top:8px; border-top:1px solid #30444a; padding-top:17px; }
  #naRail .walk-title, #naRail .legend-title--toggle, #naRail .hint-title--toggle {
    min-height:36px; display:flex; align-items:center; justify-content:space-between;
    text-align:left; font:600 12px/1.5 var(--sans); color:#e3eae5;
    letter-spacing:.04em; padding:0 0 10px;
  }
  #naRail .walk-body { max-height:none; padding:0; overflow:visible; margin-top:12px; gap:22px; }
  #naRail .step { font:13px/1.85 var(--sans); color:#b8c8ca; padding-left:14px; border-color:#416d6c; }
  #naRail .step-tag { font:600 13px/1.6 var(--sans); color:#dfebe5; margin-bottom:8px; letter-spacing:0; }
  #naRail .legend-body { overflow:visible; }
  #naRail .legend-row { min-height:48px; padding:9px 5px; gap:10px; border-radius:4px; }
  #naRail .legend-row:hover { background:#1b3238; }
  #naRail .legend-row input { width:16px; height:16px; border-color:#9db3b7; }
  #naRail .legend-row input:checked::after { left:4px; top:1px; }
  #naRail .legend-text { line-height:1.5; }
  #naRail .legend-acr { font-size:12px; }
  #naRail .legend-name { font:12px/1.6 var(--sans); color:#b4c5c8; }
  #naRail .legend-title { color:#abc0c2; font-size:11px; }
  #naRail .legend-note { margin-top:16px; padding:14px 0 0; color:#b6c8c6; font:12px/1.8 var(--sans); }
  #naRail .hint { text-align:left; }
  #naRail .hint-body { font:13px/1.85 var(--sans); color:#b8c8ca; }
  #naRail .hint b { color:#e5eee6; font-weight:600; }
  #naRail nav.crossnav { display:flex; flex-wrap:wrap; gap:8px; margin-top:22px; }
  #naRail nav.crossnav a { white-space:normal; line-height:1.5; }
  #naTools {
    position:fixed; left:20px; bottom:22px; width:330px; z-index:40;
    display:grid; grid-template-columns:repeat(3,1fr); gap:5px; padding:5px;
    background:#0f2026; border:1px solid #31474e; border-radius:8px;
    box-shadow:0 5px 20px #0002;
  }
  #naTools button {
    display:flex; align-items:center; justify-content:center; gap:7px;
    min-height:43px; border:1px solid transparent; border-radius:4px;
    background:transparent; color:#b5c8c9; font:500 12px/1.4 var(--sans);
    cursor:pointer;
  }
  #naTools button svg { width:15px; height:15px; flex:none; }
  #naTools button:hover { color:#edf2e7; border-color:#3b5a62; }
  #naTools button[aria-pressed="true"] { background:#d6e7de; color:#112e31; }
  #naEvidence {
    position:fixed; right:22px; bottom:25px; z-index:26; max-width:min(420px,40vw);
    padding:7px 11px; color:#bbc9c8; background:#0c1a20e8;
    border:1px solid #344a50; border-radius:4px; font:11px/1.6 var(--sans);
    pointer-events:none;
  }
  #naEvidence::before { content:""; display:inline-block; width:9px; height:9px;
    border:1px dashed #afc5bd; margin-right:8px; vertical-align:middle; }
  .na-upgrade #hoverPanel, .na-upgrade #slicePanel {
    top:86px; right:22px; left:auto; bottom:auto; max-width:250px;
    border-radius:6px; padding:13px 16px; z-index:29;
  }
  .na-upgrade .hover-label { font:13px/1.7 var(--sans); }
  .na-upgrade canvas:focus-visible { outline-offset:-5px; }
  .na-zoom { display:flex; flex-wrap:wrap; gap:8px; margin:22px 0 12px; }
  .na-zoom button {
    flex:1; min-height:42px; background:#1a3239; color:#d8e6df;
    border:1px solid #456269; border-radius:4px; font:13px var(--sans); cursor:pointer;
  }
  .na-zoom .na-reset { flex-basis:100%; }
  .na-keyboard-note { color:#9fb7ba; font:12px/1.8 var(--sans); margin:12px 0 0; }
  .na-upgrade ::-webkit-scrollbar { width:5px; height:5px; }
  .na-upgrade ::-webkit-scrollbar-thumb { background:#3a565d; border-radius:5px; }
  @media (max-width:760px) {
    .na-upgrade #scene[data-na-viewport],
    .na-upgrade.na-panel-open #scene[data-na-viewport] { inset:104px 0 90px; }
    body.na-upgrade::before { height:104px; }
    .na-upgrade #neuroNav { left:12px; top:10px; font-size:10px; max-width:calc(100% - 100px); }
    .na-upgrade #langToggle { right:12px; top:10px; min-height:40px; }
    #naWorkspaceTitle { left:18px; right:18px; top:68px; font-size:13px; color:#e0e9e3; }
    #naRail {
      left:12px; right:12px; top:auto; bottom:calc(86px + env(safe-area-inset-bottom));
      width:auto; max-height:52vh; max-height:52dvh; border-radius:10px;
    }
    .na-pane { padding:17px 18px; }
    #naRail h1 { font-size:22px; }
    #naRail h1 #txtTitleSuffix { font-size:17px; }
    #naRail .subtitle, #naRail .step { font-size:13px; line-height:1.8; }
    #naTools { left:12px; right:12px; bottom:calc(16px + env(safe-area-inset-bottom)); width:auto; }
    #naTools button { min-height:44px; }
    #naEvidence {
      right:12px; left:12px; bottom:calc(83px + env(safe-area-inset-bottom));
      max-width:none; width:fit-content; font-size:10px; padding:5px 9px;
    }
    .na-upgrade.na-panel-open #naEvidence { display:none; }
    .na-upgrade #hoverPanel, .na-upgrade #slicePanel {
      top:116px; right:12px; max-width:min(250px,calc(100vw - 24px));
      padding:10px 12px; font-size:12px;
    }
    .na-upgrade.na-panel-open #hoverPanel { max-height:18vh; overflow-y:auto; }
  }
  @media (max-height:520px) and (max-width:760px) {
    #naRail { top:110px; max-height:none; }
    .na-rail-top { min-height:42px; }
  }
  @media (prefers-reduced-motion:reduce) {
    .na-upgrade *, .na-upgrade *::before, .na-upgrade *::after { transition:none!important; scroll-behavior:auto!important; }
  }
</style>
<script id="neuroViewerUpgradeScript">
(function () {
  'use strict';
  if (document.getElementById('naRail')) return;
  if (!document.querySelector('meta[name="viewport"]')) {
    const viewport = document.createElement('meta');
    viewport.name = 'viewport'; viewport.content = 'width=device-width, initial-scale=1';
    document.head.appendChild(viewport);
  }
  const scene = document.getElementById('scene');
  const header = document.querySelector('header.ui');
  const legend = document.getElementById('legendPanel') || document.querySelector('.legend.ui');
  // The 2D comparison pages retain their purpose-built layout.
  if (!scene || !header || !legend) return;
  document.body.classList.add('na-upgrade');

  const hint = document.getElementById('hintPanel') || document.querySelector('.hint.ui');
  const langButton = document.getElementById('langToggle');
  const heading = header.querySelector('h1');
  const labels = {
    guide:['Reading guide','閱讀指南'], layers:['Layers','圖層'], controls:['Controls','操作'],
    guideTitle:['FIELD NOTES / 01','閱讀指南 / 01'], layersTitle:['ANATOMY / 02','解剖圖層 / 02'],
    controlsTitle:['EXPLORE / 03','探索工具 / 03'],
    close:['Close panel and explore the model','收起面板，探索模型'],
    toolbar:['Viewer panels','檢視面板'],
    evidence:['Wireframe nodes are schematic, not segmented anatomy.','線框節點為示意定位，並非真實分割構造。'],
    zoomIn:['+ Zoom in','＋ 放大'], zoomOut:['− Zoom out','− 縮小'],
    reset:['Reset view','重設視角'],
    keyboard:['Tab moves between controls. Enter or Space opens a panel. Esc closes it. Focus the model and use + / − to zoom.',
      'Tab 切換控制項，Enter 或空白鍵開啟面板，Esc 收起面板。聚焦模型後，可按 ＋ / − 縮放。'],
    canvas:['Interactive 3D atlas. Drag to rotate; use + and - to zoom.','互動 3D 圖譜。拖曳旋轉，按 ＋ 和 − 縮放。']
  };
  function isChinese() {
    if (langButton) return /^(EN|English)$/i.test(langButton.textContent.trim());
    return document.documentElement.lang.toLowerCase().startsWith('zh');
  }
  function translate(key) { return labels[key][isChinese() ? 1 : 0]; }
  function element(tag, id, className) {
    const node = document.createElement(tag);
    if (id) node.id = id;
    if (className) node.className = className;
    return node;
  }
  const workspaceTitle = element('div','naWorkspaceTitle');
  document.body.appendChild(workspaceTitle);
  const rail = element('aside','naRail');
  rail.setAttribute('aria-labelledby','naRailLabel');
  const railTop = element('div',null,'na-rail-top');
  const railLabel = element('span','naRailLabel');
  const close = element('button','naClose'); close.type = 'button'; close.textContent = '×';
  railTop.append(railLabel,close); rail.appendChild(railTop);
  const panes = {};
  ['guide','layers','controls'].forEach(key => {
    const pane = element('section','naPane-' + key,'na-pane');
    pane.tabIndex = -1; pane.setAttribute('aria-labelledby','naButton-' + key);
    pane.hidden = true; panes[key] = pane; rail.appendChild(pane);
  });
  panes.guide.appendChild(header);
  const crossnav = document.querySelector('nav.crossnav');
  if (crossnav) panes.guide.appendChild(crossnav);
  panes.layers.appendChild(legend);
  if (hint) panes.controls.appendChild(hint);
  document.body.appendChild(rail);

  const tools = element('nav','naTools');
  const buttons = {};
  const paths = {
    guide:'<path d="M3 3h6a3 3 0 0 1 3 3v15a4 4 0 0 0-4-3H3zM21 3h-6a3 3 0 0 0-3 3v15a4 4 0 0 1 4-3h5z"/>',
    layers:'<path d="m12 3 10 5-10 5L2 8zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
    controls:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>'
  };
  ['guide','layers','controls'].forEach(key => {
    const button = element('button','naButton-' + key);
    button.type = 'button'; button.setAttribute('aria-controls',panes[key].id);
    button.setAttribute('aria-pressed','false');
    button.innerHTML = '<svg viewBox="0 0 24 26" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths[key] + '</svg><span></span>';
    button.addEventListener('click',event => {
      select(active === key ? null : key);
      if (active && event.detail === 0) panes[key].focus({preventScroll:true});
    });
    buttons[key] = button; tools.appendChild(button);
  });
  document.body.appendChild(tools);
  const note = document.getElementById('txtLegendNote');
  let evidence = null;
  if (note && /schematic|示意/.test(note.textContent)) {
    evidence = element('div','naEvidence'); document.body.appendChild(evidence);
  }
  const canvas = scene.querySelector('canvas');
  function zoom(delta) {
    if (canvas) canvas.dispatchEvent(new WheelEvent('wheel', {deltaY:delta,bubbles:true,cancelable:true}));
  }
  const zoomButtons = element('div',null,'na-zoom');
  const zoomIn = element('button'); zoomIn.type = 'button'; zoomIn.addEventListener('click',() => zoom(-140));
  const zoomOut = element('button'); zoomOut.type = 'button'; zoomOut.addEventListener('click',() => zoom(140));
  zoomButtons.append(zoomIn,zoomOut);
  const reset = element('button',null,'na-reset'); reset.type = 'button';
  reset.addEventListener('click',() => document.dispatchEvent(new Event('neuro-reset-view')));
  if (scene.dataset.naViewport) zoomButtons.appendChild(reset);
  if (canvas) panes.controls.appendChild(zoomButtons);
  const keyboardNote = element('p',null,'na-keyboard-note'); panes.controls.appendChild(keyboardNote);
  if (canvas) {
    canvas.tabIndex = 0;
    canvas.addEventListener('keydown',event => {
      if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(-140); }
      if (event.key === '-' || event.key === '_') { event.preventDefault(); zoom(140); }
    });
  }

  // Upgrade the original click-only disclosure headers, retaining their handlers.
  [['walkToggle','walkPanel','walkBody'],['legendToggle','legendPanel','legendBody'],['hintToggle','hintPanel','hintBody']].forEach(ids => {
    const toggle = document.getElementById(ids[0]);
    const panel = document.getElementById(ids[1]);
    if (!toggle || !panel) return;
    panel.classList.remove('collapsed');
    toggle.tabIndex = 0; toggle.setAttribute('role','button'); toggle.setAttribute('aria-controls',ids[2]);
    function expanded() { toggle.setAttribute('aria-expanded',String(!panel.classList.contains('collapsed'))); }
    expanded(); new MutationObserver(expanded).observe(panel,{attributes:true,attributeFilter:['class']});
    toggle.addEventListener('keydown',event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle.click(); }
    });
  });
  let active = null;
  function select(key, restoreFocus) {
    active = key; rail.hidden = !key;
    document.body.classList.toggle('na-panel-open',Boolean(key));
    Object.keys(panes).forEach(name => {
      panes[name].hidden = name !== key;
      buttons[name].setAttribute('aria-pressed',String(name === key));
    });
    if (key) railLabel.textContent = translate(key + 'Title');
    if (scene.dataset.naViewport) window.dispatchEvent(new Event('resize'));
    if (restoreFocus && canvas) canvas.focus({preventScroll:true});
  }
  close.addEventListener('click',() => select(null,true));
  document.addEventListener('keydown',event => {
    if (event.key === 'Escape' && active) { event.preventDefault(); select(null,true); }
  });
  tools.addEventListener('keydown',event => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    const list = Object.values(buttons); const index = list.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? list.length-1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length;
    list[next].focus();
  });
  function updateLanguage() {
    document.documentElement.lang = isChinese() ? 'zh-Hant' : 'en';
    workspaceTitle.textContent = heading ? heading.textContent.replace(/\s+/g,' ').trim() : document.title;
    Object.keys(buttons).forEach(key => { buttons[key].querySelector('span').textContent = translate(key); });
    tools.setAttribute('aria-label',translate('toolbar'));
    close.setAttribute('aria-label',translate('close')); close.title = translate('close');
    if (active) railLabel.textContent = translate(active + 'Title');
    if (evidence) evidence.textContent = translate('evidence');
    zoomIn.textContent = translate('zoomIn'); zoomOut.textContent = translate('zoomOut');
    reset.textContent = translate('reset');
    keyboardNote.textContent = translate('keyboard');
    if (canvas) canvas.setAttribute('aria-label',translate('canvas'));
  }
  if (langButton) langButton.addEventListener('click',() => {
    updateLanguage();
    try { localStorage.setItem('neuroLang',isChinese() ? 'zh' : 'en'); } catch (error) {}
  });
  updateLanguage();
  select(window.matchMedia('(max-width:760px)').matches ? null : 'guide');
})();
</script>
"""
