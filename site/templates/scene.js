(function createAnatomicalScene(atlas) {
  'use strict';
  const {scene, camera, renderer, controls, meshes, regions, nodes, axes, extent} = atlas;
  // Presentation only: never edit atlas buffers, coordinates or object scales.
  const container = renderer.domElement.parentElement;
  const svgNS = 'http://www.w3.org/2000/svg';
  const mobileView = window.matchMedia('(max-width:760px)');
  const state = {shell:32, labels:mobileView.matches ? 'off' : 'smart', selected:null, preset:'overview'};
  let labelsChosen = false;
  const originalSprites = [];
  const root = meshes.root;
  const skull = meshes.skull;
  controls.autoRotate = false;

  function make(tag, className, parent) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (parent) parent.appendChild(el);
    return el;
  }
  function svg(tag, parent, attributes={}) {
    const el = document.createElementNS(svgNS, tag);
    for (const [key,value] of Object.entries(attributes)) el.setAttribute(key,value);
    if (parent) parent.appendChild(el);
    return el;
  }
  function chinese() {
    const button = document.getElementById('langToggle');
    return button ? /^(EN|English)$/i.test(button.textContent.trim()) : document.documentElement.lang.startsWith('zh');
  }
  const text = (zh,en) => chinese() ? zh : en;
  const clean = value => String(value || '').replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]+[a-c]?\s*/,'');
  function visible(object) {
    for (let current=object; current; current=current.parent) if (!current.visible) return false;
    return true;
  }

  // One anatomical shell, with view-dependent edge shading on its exact mesh.
  // The old expanded "skull" is a schematic size reference, hidden by default.
  let shellMaterial;
  if (root) {
    shellMaterial = new THREE.ShaderMaterial({
      uniforms:{opacity:{value:state.shell/100}, surfaceColor:{value:new THREE.Color('#a4c4c8')}},
      vertexShader:`varying vec3 viewNormal; varying vec3 viewPosition;
        void main(){vec4 p=modelViewMatrix*vec4(position,1.0);viewPosition=p.xyz;
        viewNormal=normalize(normalMatrix*normal);gl_Position=projectionMatrix*p;}`,
      fragmentShader:`uniform float opacity; uniform vec3 surfaceColor;
        varying vec3 viewNormal; varying vec3 viewPosition;
        void main(){vec3 n=normalize(viewNormal);vec3 v=normalize(-viewPosition);
        float edge=pow(1.0-abs(dot(n,v)),2.7);
        float light=0.55+0.45*max(0.0,dot(n,normalize(vec3(-0.35,0.6,0.7))));
        vec3 color=mix(surfaceColor*0.5,surfaceColor,edge)*light;
        gl_FragColor=vec4(color,opacity*(0.06+edge*0.85));}`,
      transparent:true, depthWrite:false, side:THREE.FrontSide,
    });
    root.material = shellMaterial;
  }
  if (skull) {
    skull.visible = false;
    const checkbox = document.querySelector('input[data-target="skull"]');
    if (checkbox) checkbox.checked = false;
  }

  // Retain atlas and pathway colors; use a quieter, satin material response.
  Object.entries(meshes).forEach(([key,mesh]) => {
    if (key === 'root' || key === 'skull' || !mesh.material?.isMeshStandardMaterial) return;
    const material = mesh.material.clone();
    material.roughness = 0.32;
    material.metalness = 0.08;
    material.emissive.copy(material.color);
    material.emissiveIntensity = 0.075;
    mesh.material = material;
  });
  const glowCanvas = document.createElement('canvas');
  glowCanvas.width = glowCanvas.height = 32;
  const context = glowCanvas.getContext('2d');
  const gradient = context.createRadialGradient(16,16,1,16,16,15);
  gradient.addColorStop(0,'rgba(255,255,255,1)');
  gradient.addColorStop(.28,'rgba(255,255,255,.9)');
  gradient.addColorStop(1,'rgba(255,255,255,0)');
  context.fillStyle = gradient; context.fillRect(0,0,32,32);
  const glow = new THREE.CanvasTexture(glowCanvas);
  scene.traverse(object => {
    if (object.isSprite) { originalSprites.push(object); object.visible=false; }
    if (object.isMesh && object.geometry?.type === 'TubeGeometry') {
      object.material = object.material.clone();
      object.material.emissiveIntensity = 0.24;
      object.material.roughness = 0.3;
      object.material.metalness = 0.12;
    }
    if (object.isMesh && object.material?.wireframe) {
      object.material = object.material.clone();
      object.material.opacity = 0.3;
      object.material.depthWrite = false;
    }
    if (object.isPoints) {
      object.material = object.material.clone();
      object.material.map = glow;
      object.material.alphaTest = 0.01;
      object.material.needsUpdate = true;
    }
  });
  const softLight = new THREE.DirectionalLight(0xd8fff0,0.48);
  scene.add(softLight);

  const overlay = make('div',null,container); overlay.id='naSceneOverlay';
  const connectors = svg('svg',overlay,{class:'na-connectors','aria-hidden':'true'});
  const caption = make('div','na-stage-caption',overlay);
  make('div','na-stage-kicker',caption).textContent='ANATOMICAL VIEW / 01';
  const stageTitle = make('div','na-stage-title',caption);
  const stageSub = make('div','na-stage-sub',caption);
  const mobileAnnotations = make('button','na-mobile-annotations',caption);
  mobileAnnotations.type='button';
  mobileAnnotations.setAttribute('aria-controls','naSceneOverlay');
  mobileAnnotations.addEventListener('click',()=>{
    labelsChosen=true;
    state.labels=state.labels==='off' ? 'smart' : 'off';
    if(state.labels==='off')select(null);
    syncControls();update(true);
  });
  const orientation = make('div',null,overlay); orientation.id='naOrientation';
  const compass = svg('svg',orientation,{viewBox:'0 0 80 70','aria-hidden':'true'});
  const axisDirections = axes.length ? axes.filter(axis=>axis.key !== 'posterior').map(axis=>({
    direction:axis.sprite.position.clone().normalize(),
    label:{anterior:'A',superior:'S',right_axis:'R'}[axis.key] || axis.key,
    color:{anterior:'#86c7bd',superior:'#d6c09b',right_axis:'#aabce5'}[axis.key] || '#b1c1c5',
  })) : [
    {direction:new THREE.Vector3(-1,0,0),label:'A',color:'#86c7bd'},
    {direction:new THREE.Vector3(0,-1,0),label:'S',color:'#d6c09b'},
  ];
  axisDirections.forEach(axis => {
    axis.line=svg('line',compass,{x1:40,y1:35,stroke:axis.color,'stroke-width':1.25});
    axis.text=svg('text',compass,{fill:axis.color,'text-anchor':'middle','dominant-baseline':'central'});
    axis.text.textContent=axis.label;
  });
  svg('circle',compass,{cx:40,cy:35,r:2,fill:'#d7e9e3'});
  const orientationCaption = make('span',null,orientation);
  const scale = make('div',null,overlay); scale.id='naScale';
  const scaleLine = make('div','na-scale-line',scale);
  const scaleText = make('span',null,scale);
  const stageNote = make('div','na-stage-note',overlay);
  const detail = make('div',null,overlay); detail.id='naNodeDetail'; detail.hidden=true;
  const detailName=make('strong',null,detail);
  const detailMeta=make('span',null,detail);
  const detailClose=make('button','na-detail-close',detail); detailClose.type='button';detailClose.textContent='×';
  detailClose.addEventListener('click',()=>select(null));

  // De-duplicate branch-shared annotations, while retaining every visibility source.
  const entries=[];
  const byKey=new Map();
  nodes.forEach(node => {
    const position=node.mesh.getWorldPosition(new THREE.Vector3());
    const key=clean(node.text.en)+'|'+position.toArray().map(n=>Math.round(n)).join(',');
    let entry=byKey.get(key);
    if (!entry) {
      entry={refs:[],text:node.text,color:node.color,kind:'pathway',position:new THREE.Vector3(),
        surface:meshes[node.regionKey]};
      byKey.set(key,entry); entries.push(entry);
    }
    entry.refs.push(node);
  });
  if (!nodes.length) Object.entries(meshes).forEach(([key,mesh]) => {
    if (key==='root' || key==='skull') return;
    mesh.geometry.computeBoundingBox();
    entries.push({mesh,surface:mesh,regionKey:key,refs:[],text:{en:regions[key]?.name || key,zh:regions[key]?.name || key},
      color:mesh.material.color?.getHex() || 0x84dcc5,kind:'atlas',position:new THREE.Vector3()});
  });
  // Legacy Papez-loop labels carry their exact waypoint as build-time metadata.
  originalSprites.filter(sprite=>sprite.userData.neuroAnchor).forEach(sprite=>{
    entries.push({source:sprite.parent,anchor:sprite.userData.neuroAnchor,refs:[],
      text:{en:sprite.userData.neuroText,zh:sprite.userData.neuroText},
      color:0xe0a458,kind:'pathway',position:new THREE.Vector3()});
  });
  entries.forEach((entry,index) => {
    entry.index=index; entry.number=String(index+1).padStart(2,'0');
    // Annotation ink is independent of tissue color. A dark halo preserves the
    // boundary on lit surfaces; the original anatomy and legend keep their hues.
    const hue={};
    new THREE.Color(entry.surface?.material.color || entry.color).getHSL(hue);
    entry.hex=entry.surface ? (hue.h<.12 || hue.h>.91 ? '#80e5f2' : '#ffbd83')
      : '#'+Number(entry.color).toString(16).padStart(6,'0');
    entry.line=svg('path',connectors,{fill:'none',stroke:entry.hex,'stroke-width':.8,'stroke-opacity':.52});
    entry.dot=svg('circle',connectors,{r:entry.surface?4.5:3,fill:entry.hex,stroke:'#0b1418','stroke-width':2});
    entry.line.style.setProperty('--node-color',entry.hex);
    entry.dot.style.setProperty('--node-color',entry.hex);
    entry.button=make('button','na-callout',overlay); entry.button.type='button';
    entry.button.dataset.region=entry.regionKey || entry.refs[0]?.regionKey || '';
    entry.dot.dataset.region=entry.button.dataset.region;
    entry.button.style.setProperty('--node-color',entry.hex);
    make('span','na-callout-number',entry.button).textContent=entry.number;
    const copy=make('span','na-callout-copy',entry.button);
    entry.name=make('strong',null,copy);entry.meta=make('small',null,copy);
    entry.button.addEventListener('click',()=>{select(state.selected===entry ? null : entry);update(true);});
    entry.button.addEventListener('mouseenter',()=>entry.line.style.strokeOpacity='1');
    entry.button.addEventListener('mouseleave',()=>entry.line.style.strokeOpacity='.52');
  });
  function label(entry) {return clean(entry.text[chinese() ? 'zh' : 'en'] || entry.text.en);}
  function kind(entry) {return entry.kind==='atlas' ? text('圖譜結構','ATLAS STRUCTURE') : text('路徑節點','PATHWAY NODE');}
  function updateDetail(entry) {
    detailName.textContent=label(entry);
    detail.style.setProperty('--node-color',entry.hex);
    detailMeta.textContent=kind(entry)+' · '+(entry.surface
      ? entry.surfaceVisible
        ? text('標記落在此結構的可見表面','Marker on this structure’s visible surface')
        : text('此結構目前無可見表面；請旋轉或放大視角，或關閉遮擋圖層','No surface visible here. Rotate or zoom in, or hide an overlapping layer.')
      : text('引線指向原始示意節點座標','Leader ends at the original schematic waypoint'));
  }
  function select(entry) {
    state.selected=entry;detail.hidden=!entry;
    if (entry) updateDetail(entry);
    entries.forEach(item=>{
      item.button.classList.toggle('is-selected',item===entry);
      item.button.setAttribute('aria-pressed',String(item===entry));
      item.listButton?.classList.toggle('is-selected',item===entry);
      item.listButton?.setAttribute('aria-pressed',String(item===entry));
    });
  }

  const display=make('section',null);display.id='naDisplayDesign';
  const displayHeader=make('header',null,display);
  const displayHeading=make('h3',null,displayHeader);
  const displaySub=make('small',null,displayHeader);
  const presets=make('div','na-render-presets',display);
  const presetButtons={};
  ['overview','focus'].forEach(mode=>{
    const button=make('button',null,presets);button.type='button';button.dataset.mode=mode;presetButtons[mode]=button;
    button.addEventListener('click',()=>{state.preset=mode;setShell(mode==='overview' ? 32 : 8);syncControls();});
  });
  const rangeRow=make('div','na-range-row',display);
  const rangeLabel=make('label',null,rangeRow);rangeLabel.htmlFor='naShellOpacity';
  const rangeValue=make('output',null,rangeRow);rangeValue.htmlFor='naShellOpacity';
  const range=make('input',null,rangeRow);range.id='naShellOpacity';range.type='range';range.min=0;range.max=60;range.step=1;range.value=state.shell;
  range.addEventListener('input',()=>{state.preset='custom';setShell(Number(range.value));syncControls();});
  range.disabled=!root;
  const labelTitle=make('p','na-label-title',display);
  const labelModes=make('div','na-label-modes',display);
  const labelButtons={};
  ['smart','all','off'].forEach(mode=>{
    const button=make('button',null,labelModes);button.type='button';labelButtons[mode]=button;
    button.addEventListener('click',()=>{labelsChosen=true;state.labels=mode;if(mode==='off')select(null);syncControls();update(true);});
  });
  const explanation=make('p','na-layer-explanation',display);
  const nodeList=make('div','na-node-list');
  const listHeading=make('h3',null,nodeList);
  entries.forEach(entry=>{
    entry.listButton=make('button','na-node-item',nodeList);entry.listButton.type='button';entry.listButton.style.setProperty('--node-color',entry.hex);
    make('small',null,entry.listButton).textContent=entry.number;
    entry.listName=make('span','na-node-item-title',entry.listButton);
    entry.listStatus=make('span','na-node-status',entry.listButton);
    entry.listButton.addEventListener('click',()=>{select(state.selected===entry ? null : entry);update(true);});
  });
  function setShell(value) {state.shell=value;if(shellMaterial) shellMaterial.uniforms.opacity.value=value/100;range.value=value;rangeValue.textContent=value+'%';}
  function syncControls() {
    Object.entries(presetButtons).forEach(([key,button])=>{button.classList.toggle('active',key===state.preset);button.setAttribute('aria-pressed',String(key===state.preset));});
    Object.entries(labelButtons).forEach(([key,button])=>{button.classList.toggle('active',key===state.labels);button.setAttribute('aria-pressed',String(key===state.labels));});
    setShell(state.shell);
    mobileAnnotations.textContent=state.labels==='off' ? text('顯示節點','Show nodes') : text('收起節點','Hide nodes');
    mobileAnnotations.setAttribute('aria-pressed',String(state.labels!=='off'));
  }
  let previousLanguage;
  function translate() {
    previousLanguage=chinese();
    stageTitle.textContent=text('結構與訊號的空間關係','Structure, space & signal');
    stageSub.textContent=mobileView.matches ? text('拖曳旋轉 · 雙指縮放','Drag to rotate · Pinch to zoom')
      : text('拖曳旋轉 · 點選標註查看節點','Drag to rotate · Select an annotation');
    orientationCaption.textContent=text('解剖方向','ORIENTATION');
    orientation.title=text('A 前方 · S 上方 · R 右側（有標示時）','A anterior · S superior · R right (when shown)');
    displayHeading.textContent=text('圖層呈現','Anatomical display');
    displaySub.textContent='MATERIAL / ANNOTATION';
    presetButtons.overview.textContent=text('解剖全貌','Anatomy');
    presetButtons.focus.textContent=text('路徑聚焦','Pathway focus');
    rangeLabel.textContent=text('腦表面輪廓','Brain surface');
    labelTitle.textContent=text('節點標註','Node annotations');
    labelButtons.smart.textContent=text('重點','Key nodes');
    labelButtons.all.textContent=text('詳細','Detailed');
    labelButtons.off.textContent=text('關閉','Off');
    explanation.textContent=text('只調整材質與標註，保留網格尺寸及原始座標。虛線球體為示意節點；頭部大小示意預設隱藏。','Materials and annotations change; mesh dimensions and coordinates stay intact. Wireframe nodes are schematic; the approximate head shell starts hidden.');
    listHeading.textContent=text('節點索引','NODE INDEX');
    detailClose.setAttribute('aria-label',text('清除節點選取','Clear node selection'));
    entries.forEach(entry=>{
      entry.name.textContent=label(entry);entry.meta.textContent=kind(entry);
      entry.button.setAttribute('aria-label',entry.number+' · '+label(entry));
      entry.button.title=label(entry)+' · '+kind(entry);entry.listName.textContent=label(entry);
    });
    if (state.selected) select(state.selected);
    syncControls();
  }
    function mount() {
      document.getElementById('naPane-guide')?.appendChild(stageNote);
    const pane=document.getElementById('naPane-layers');
    if (pane && display.parentElement!==pane) {pane.prepend(display);pane.appendChild(nodeList);}
  }

  function createSurfacePicker() {
    // A small, cached ID pass identifies the frontmost tissue. Sharing geometry
    // with presentation-free proxies preserves the atlas, including every hole
    // and separate hemisphere. Root/skull are transparent context, not targets.
    const surfaces=entries.filter(entry=>entry.surface);
    if(!surfaces.length)return {refresh(){}};
    const pickScene=new THREE.Scene();
    const lateral=axes.length?'x':'z';
    const records=Object.entries(meshes).filter(([key])=>key!=='root' && key!=='skull').map(([key,mesh],index)=>{
      const material=new THREE.ShaderMaterial({uniforms:{regionId:{value:(index+1)/255}},
        vertexShader:`varying float lateralPosition;
          void main(){lateralPosition=position.${lateral};gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
        fragmentShader:`uniform float regionId; varying float lateralPosition;
          void main(){gl_FragColor=vec4(regionId,step(0.0,lateralPosition),0.0,1.0);}`,
        side:mesh.material.side,blending:THREE.NoBlending,toneMapped:false});
      const proxy=new THREE.Mesh(mesh.geometry,material);
      proxy.matrixAutoUpdate=false;pickScene.add(proxy);
      mesh.geometry.computeBoundingBox();
      return {mesh,proxy,id:index+1};
    });
    const byMesh=new Map(records.map(record=>[record.mesh,record]));
    const target=new THREE.WebGLRenderTarget(1,1,{minFilter:THREE.NearestFilter,
      magFilter:THREE.NearestFilter,depthBuffer:true,stencilBuffer:false});
    target.texture.generateMipmaps=false;
    target.texture.encoding=THREE.LinearEncoding;
    const ray=new THREE.Raycaster();
    const ndc=new THREE.Vector2(), preferred=new THREE.Vector3(), local=new THREE.Vector3();
    const clip=new THREE.Vector3(), size=new THREE.Vector3();
    const oldViewport=new THREE.Vector4(),oldScissor=new THREE.Vector4(),oldColor=new THREE.Color();
    let signature='',pixels=new Uint8Array(4),pw=1,ph=1;
    function refresh(width,height) {
      if (!surfaces.length || width<1 || height<1) return;
      const next=[width,height,...camera.matrixWorld.elements,...camera.projectionMatrix.elements,
        ...records.flatMap(({mesh})=>[visible(mesh),...mesh.matrixWorld.elements]),
        ...surfaces.flatMap(entry=>entry.refs.flatMap(ref=>[visible(ref.mesh),...ref.mesh.matrixWorld.elements]))].join(',');
      if (next===signature) return;
      signature=next;
      ph=192;pw=Math.max(1,Math.min(512,Math.round(ph*width/height)));
      if(target.width!==pw || target.height!==ph) {
        target.setSize(pw,ph);pixels=new Uint8Array(pw*ph*4);
      }
      records.forEach(({mesh,proxy})=>{
        proxy.visible=visible(mesh);proxy.matrix.copy(mesh.matrixWorld);
      });
      const oldTarget=renderer.getRenderTarget(),oldAlpha=renderer.getClearAlpha();
      const oldAutoClear=renderer.autoClear,oldScissorTest=renderer.getScissorTest();
      renderer.getClearColor(oldColor);renderer.getViewport(oldViewport);renderer.getScissor(oldScissor);
      try {
        renderer.setRenderTarget(target);renderer.setViewport(0,0,pw,ph);renderer.setScissorTest(false);
        renderer.setClearColor(0x000000,0);renderer.autoClear=true;
        renderer.render(pickScene,camera);
        renderer.readRenderTargetPixels(target,0,0,pw,ph,pixels);
      } finally {
        renderer.setRenderTarget(oldTarget);renderer.setViewport(oldViewport);renderer.setScissor(oldScissor);
        renderer.setScissorTest(oldScissorTest);renderer.setClearColor(oldColor,oldAlpha);renderer.autoClear=oldAutoClear;
      }
      const visibleProxies=records.filter(record=>record.proxy.visible).map(record=>record.proxy);
      const occupied=[];
      const idAt=(x,y)=>x<0 || y<0 || x>=pw || y>=ph ? 0 : pixels[(y*pw+x)*4];
      surfaces.forEach(entry=>{
        entry.surfaceVisible=false;
        const record=byMesh.get(entry.surface);
        if (!record?.proxy.visible) return;
        const ref=entry.refs.find(ref=>visible(ref.mesh));
        if (entry.refs.length && !ref) return;
        const box=entry.surface.geometry.boundingBox;
        box.getSize(size);
        if(ref) ref.mesh.getWorldPosition(preferred);
        else {
          box.getCenter(preferred);
          // A preference only; an actual surface intersection is always required.
          preferred[lateral]+=size[lateral]*(entry.index%2 ? -.24 : .24);
          entry.surface.localToWorld(preferred);
        }
        local.copy(preferred);entry.surface.worldToLocal(local);
        const side=local[lateral]>=0?1:-1;
        const bilateral=box.min[lateral]<-size[lateral]*.2 && box.max[lateral]>size[lateral]*.2;
        const constrainSide=!!ref && bilateral && Math.abs(local[lateral])>size[lateral]*.04;
        clip.copy(preferred).project(camera);
        const tx=(clip.x+1)*pw/2,ty=(clip.y+1)*ph/2;
        const candidates=[];
        for(let y=0;y<ph;y++) for(let x=0;x<pw;x++) {
          if(idAt(x,y)!==record.id) continue;
          // Green encodes hemisphere before ranking, preventing a nearer,
          // contralateral surface from displacing every valid candidate.
          if(constrainSide && (pixels[(y*pw+x)*4+1]>127 ? 1 : -1)!==side) continue;
          let clearance=0;
          for(let step=1;step<=5;step++) {
            if(idAt(x-step,y)!==record.id || idAt(x+step,y)!==record.id ||
              idAt(x,y-step)!==record.id || idAt(x,y+step)!==record.id) break;
            clearance=step;
          }
          let score=((x-tx)**2+(y-ty)**2)/(ph*ph)-clearance*.003;
          occupied.forEach(point=>{score+=.04*Math.max(0,1-Math.hypot(x-point.x,y-point.y)/14);});
          if(candidates.length===20 && score>=candidates[candidates.length-1].score) continue;
          candidates.push({x,y,score});candidates.sort((a,b)=>a.score-b.score);
          if(candidates.length>20)candidates.pop();
        }
        for(const point of candidates) {
          ndc.set((point.x+.5)/pw*2-1,(point.y+.5)/ph*2-1);
          ray.setFromCamera(ndc,camera);
          // Verify against all tissue, so even a one-pixel ID edge cannot place
          // an anchor through a foreground structure or onto a different mesh.
          const hit=ray.intersectObjects(visibleProxies,false)[0];
          if(!hit || hit.object!==record.proxy) continue;
          local.copy(hit.point);entry.surface.worldToLocal(local);
          if(constrainSide && local[lateral]*side<=0) continue;
          entry.position.copy(hit.point);entry.surfaceVisible=true;occupied.push(point);break;
        }
      });
    }
    window.addEventListener('pagehide',()=>{
      target.dispose();records.forEach(({proxy})=>proxy.material.dispose());
    },{once:true});
    return {refresh};
  }
  const surfacePicker=createSurfacePicker();
  const projected=new THREE.Vector3();
  const direction=new THREE.Vector3();
  const cameraPosition=new THREE.Vector3();
  const inverse=new THREE.Quaternion();
  const targetVector=new THREE.Vector3();
  let lastUpdate=-Infinity;
  function update(force=false) {
    const now=performance.now();
    if (!force && now-lastUpdate<33) return;
    lastUpdate=now;mount();
    if (previousLanguage!==chinese()) translate();
    const width=container.clientWidth,height=container.clientHeight;
    const mobile=mobileView.matches;
    scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
    surfacePicker.refresh(width,height);
    softLight.position.copy(camera.position).addScaledVector(camera.up,extent*.7);
    originalSprites.forEach(sprite=>{sprite.visible=false;});
    const active=[];
    entries.forEach(entry=>{
      const ref=entry.refs.find(ref=>visible(ref.mesh));
      const on=entry.source ? visible(entry.source) : entry.mesh ? visible(entry.mesh) : !!ref;
      entry.listButton.hidden=!on;
      entry.button.hidden=true;entry.line.style.display='none';entry.dot.style.display='none';
      if (!on) {if(state.selected===entry)select(null);return;}
      const obscured=entry.surface && !entry.surfaceVisible;
      entry.listStatus.textContent=obscured ? text('未顯露','OUT OF VIEW') : '';
      entry.listButton.classList.toggle('is-obscured',!!obscured);
      entry.listButton.title=label(entry)+(obscured ? text('：旋轉、放大視角或關閉遮擋圖層',': rotate, zoom in or hide an overlapping layer') : '');
      if(state.selected===entry)updateDetail(entry);
      if(obscured)return;
      if (entry.surface) { /* The picker supplies an exact visible triangle hit. */ }
      else if (entry.source) entry.position.copy(entry.anchor).applyMatrix4(entry.source.matrixWorld);
      else ref.mesh.getWorldPosition(entry.position);
      projected.copy(entry.position).project(camera);
      if (projected.z<-1 || projected.z>1 || Math.abs(projected.x)>1.12 || Math.abs(projected.y)>1.12) return;
      entry.x=(projected.x+1)*width/2;entry.y=(1-projected.y)*height/2;
      active.push(entry);
    });
    const top=mobile ? 98 : 100;
    const bottom=height-(mobile ? 95 : 84);
    const capacity=Math.max(1,Math.floor((bottom-top)/50));
    const limit=state.labels==='smart' ? (mobile?2:Math.min(8,capacity*2)) : (mobile?3:capacity*2);
    let chosen=[];
    if(state.labels!=='off') {
      if(active.length<=limit) chosen=active.slice();
      else {
        for(let i=0;i<limit;i++) chosen.push(active[Math.round(i*(active.length-1)/Math.max(1,limit-1))]);
        if(state.selected && active.includes(state.selected) && !chosen.includes(state.selected)) chosen[chosen.length-1]=state.selected;
      }
    } else if(state.selected && active.includes(state.selected)) chosen=[state.selected];
    const sorted=chosen.slice().sort((a,b)=>a.x-b.x);
    const left=sorted.slice(0,Math.ceil(sorted.length/2));
    const right=sorted.slice(Math.ceil(sorted.length/2));
    const labelWidth=mobile ? Math.min(139,width*.39) : Math.min(215,width*.24);
    function place(list,isLeft) {
      list.sort((a,b)=>a.y-b.y);
      const ys=list.map((entry,index)=>Math.max(top+index*50,Math.min(bottom-(list.length-1-index)*50,entry.y-22)));
      for(let i=1;i<ys.length;i++)ys[i]=Math.max(ys[i],ys[i-1]+50);
      list.forEach((entry,index)=>{
        const x=isLeft?16:width-labelWidth-16;
        const y=ys[index];
        entry.button.hidden=false;entry.button.style.left=x+'px';entry.button.style.top=y+'px';entry.button.style.width=labelWidth+'px';
        const edgeX=isLeft?x+labelWidth:x;
        const elbowX=isLeft?edgeX+13:edgeX-13;
        entry.line.style.display='';entry.dot.style.display='';
        entry.line.setAttribute('d',`M${entry.x.toFixed(1)} ${entry.y.toFixed(1)} L${elbowX} ${y+22} L${edgeX} ${y+22}`);
        entry.dot.setAttribute('cx',entry.x);entry.dot.setAttribute('cy',entry.y);
      });
    }
    if (mobile) {
      // Opt-in, compact numbered targets centered on the actual projected point.
      // Never put full-width cards across the model or shift anatomical anchors.
      const placed=[];
      chosen.sort((a,b)=>(b===state.selected)-(a===state.selected)||a.index-b.index).forEach(entry=>{
        const x=entry.x-22,y=entry.y-22;
        if(x<4 || x+44>width-4 || y<90 || y+44>height-48)return;
        if(placed.some(other=>Math.abs(other.x-x)<48 && Math.abs(other.y-y)<48))return;
        placed.push({x,y});
        entry.button.hidden=false;entry.button.style.left=x+'px';entry.button.style.top=y+'px';entry.button.style.width='44px';
      });
    } else {place(left,true);place(right,false);}
    inverse.copy(camera.quaternion).invert();
    axisDirections.forEach(axis=>{
      direction.copy(axis.direction).applyQuaternion(inverse);
      axis.line.setAttribute('x2',40+direction.x*23);axis.line.setAttribute('y2',35-direction.y*23);
      axis.text.setAttribute('x',40+direction.x*31);axis.text.setAttribute('y',35-direction.y*31);
      axis.line.style.opacity=direction.z<0?'.38':'1';axis.text.style.opacity=direction.z<0?'.55':'1';
    });
    camera.getWorldPosition(cameraPosition);camera.getWorldDirection(direction);
    const depth=targetVector.copy(controls.target).sub(cameraPosition).dot(direction);
    const pixelsPerUnit=height*camera.projectionMatrix.elements[5]/(2*Math.max(1,depth));
    const idealMm=80/pixelsPerUnit/1000;
    const magnitude=Math.pow(10,Math.floor(Math.log10(idealMm)));
    const value=[1,2,5,10].filter(value=>value*magnitude<=idealMm).pop() || 1;
    const mm=value*magnitude;
    scaleLine.style.width=Math.max(1,mm*1000*pixelsPerUnit)+'px';
    const compressed=document.getElementById('scaleToggle')?.checked===false;
    scale.hidden=compressed;
    scaleText.textContent=Number(mm.toPrecision(3))+' mm · '+text('焦平面參考尺','at focus plane');
    stageNote.textContent=compressed ? text('目前為壓縮示意模式','COMPRESSED TEACHING VIEW') : text('原始網格比例 · 連線為示意','ATLAS PROPORTIONS · SCHEMATIC CONNECTIONS');
  }
  document.addEventListener('keydown',event=>{if(event.key==='Escape' && state.selected)select(null);});
  document.addEventListener('change',()=>update(true));
  window.addEventListener('resize',()=>update(true));
  mobileView.addEventListener('change',()=>{
    if(!labelsChosen)state.labels=mobileView.matches ? 'off' : 'smart';
    translate();update(true);
  });
  document.getElementById('langToggle')?.addEventListener('click',()=>{translate();update(true);});
  const scaleToggle=document.getElementById('scaleToggle');
  if(scaleToggle)scaleToggle.checked=true;
  translate();syncControls();update(true);
  return {update, mount, state};
})
