(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const API_KEY = 'eidtmumbai.apiUrl';
  const GOOGLE_KEY = 'eidtmumbai.googleMapsKey';
  const bundledGoogleKey = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_GOOGLE_MAPS_API_KEY)
    ? String(import.meta.env.VITE_GOOGLE_MAPS_API_KEY).trim()
    : 'AIzaSyBEDAqe_TxNEY3FuY_ZvLUJIw7QoqsaEC4';
  const storedApi = localStorage.getItem(API_KEY);
  let apiBase = (storedApi && storedApi.trim() ? storedApi.trim() : 'http://127.0.0.1:8000').replace(/\/$/, '');
  let selectedScenario = 'SCEN_HEAVY_200MM';
  let scenarios = [];
  let latestExposure = null;
  let overviewMap, exploreMap, overviewRisk, exploreRisk, wardLayer, roadLayer, waterLayer, facilityLayer;
  let googleLoader;
  let toastTimer;

  const fmt = (value, digits = 0) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-IN', { maximumFractionDigits: digits }) : '—';
  const compact = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}m` : n >= 100_000 ? `${(n / 100_000).toFixed(1)}L` : fmt(n);
  };
  const esc = (s = '') => String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function toast(message, error = false) {
    const el = $('#toast'); el.textContent = message; el.className = `toast visible${error ? ' error' : ''}`;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 3200);
  }
  async function api(path, options = {}) {
    const response = await fetch(`${apiBase}/api${path}`, { ...options, headers: { ...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.headers || {}) } });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try { const data = await response.json(); detail = data.detail || detail; } catch {}
      throw new Error(detail);
    }
    return response.json();
  }
  function connection(online) {
    $('#api-dot').classList.toggle('offline', !online);
    $('#api-label').textContent = online ? 'Backend connected' : 'Backend unavailable';
    $('#api-label').title = apiBase;
    $('#api-label').style.color = online ? '' : '#b36b57';
  }
  function setPage(view) {
    const valid = ['overview','map','scenarios','exposure','insights'].includes(view) ? view : 'overview';
    $$('.page-wrap').forEach(el => el.classList.add('hidden'));
    $(`#view-${valid}`).classList.remove('hidden');
    $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === valid));
    $('#page-title').textContent = ({overview:'Overview',map:'Risk map',scenarios:'Scenarios',exposure:'Exposure',insights:'Model insights'})[valid];
    $('#sidebar').classList.remove('open');
    if (valid === 'map') setTimeout(() => { exploreMap?.invalidateSize(); if (!exploreMap) initExploreMap(); }, 60);
    if (valid === 'overview') setTimeout(() => overviewMap?.invalidateSize(), 60);
    if (valid === 'scenarios') loadScenarios();
    if (valid === 'exposure') loadExposure($('#exposure-scenario').value || selectedScenario);
    location.hash = valid;
  }
  function bindNavigation() {
    $$('.nav-item').forEach(el => el.addEventListener('click', e => { e.preventDefault(); setPage(el.dataset.view); }));
    $$('[data-goto]').forEach(el => el.addEventListener('click', () => setPage(el.dataset.goto)));
    $('#menu-button').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
    window.addEventListener('hashchange', () => setPage(location.hash.slice(1)));
  }
  function initMap(elementId) {
    if (!window.L) return null;
    const el = document.getElementById(elementId);
    if (!el) return null;
    if (el._leaflet_id) {
      el._leaflet_id = null;
    }
    const map = L.map(elementId, { zoomControl: false, scrollWheelZoom: false }).setView([19.076, 72.8777], 11);
    map._eidBasemaps = {
      osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 })
    };
    map._eidBasemaps.osm.addTo(map);
    map._eidCurrentBasemap = 'osm';
    return map;
  }
  function loadExternalScript(id, src) {
    return new Promise((resolve, reject) => {
      const existing = document.getElementById(id);
      if (existing?.dataset.loaded === 'true') { resolve(); return; }
      const script = existing || Object.assign(document.createElement('script'), { id, src, async: true });
      script.onload = () => { script.dataset.loaded = 'true'; resolve(); };
      script.onerror = () => reject(new Error('Could not load Google Maps. Check your key and internet connection.'));
      if (!existing) document.head.appendChild(script);
    });
  }
  async function ensureGoogleMutant() {
    const key = localStorage.getItem(GOOGLE_KEY)?.trim() || bundledGoogleKey;
    if (!key) throw new Error('Add a Google Maps JavaScript API key in settings to use Google basemaps.');
    if (window.google?.maps && window.L?.gridLayer?.googleMutant) return;
    if (!googleLoader) googleLoader = (async () => {
      if (!window.google?.maps) await loadExternalScript('google-maps-js-api', `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly`);
      if (!window.L?.gridLayer?.googleMutant) await loadExternalScript('leaflet-google-mutant', 'https://unpkg.com/leaflet.gridlayer.googlemutant@0.16.0/dist/Leaflet.GoogleMutant.js');
      if (!window.L?.gridLayer?.googleMutant) throw new Error('Google map layer could not be initialized.');
    })().catch(error => { googleLoader = null; throw error; });
    return googleLoader;
  }
  async function changeBasemap(map, select) {
    if (!map || !select) return;
    const requested = select.value;
    if (requested === 'osm') {
      if (map._eidGoogleLayer) map.removeLayer(map._eidGoogleLayer);
      map._eidBasemaps.osm.addTo(map); map._eidCurrentBasemap = 'osm'; setMapAttribution(map, 'osm'); return;
    }
    try {
      await ensureGoogleMutant();
      const nextLayer = L.gridLayer.googleMutant({ type: requested, maxZoom: 21 });
      if (map._eidGoogleLayer) map.removeLayer(map._eidGoogleLayer);
      map.removeLayer(map._eidBasemaps.osm);
      map._eidGoogleLayer = nextLayer;
      map._eidGoogleLayer.addTo(map); map._eidCurrentBasemap = requested;
      setMapAttribution(map, 'google');
    } catch (error) {
      select.value = map._eidCurrentBasemap || 'osm';
      toast(error.message, true);
      if (!(localStorage.getItem(GOOGLE_KEY)?.trim() || bundledGoogleKey)) {
        $('#google-map-key').value = bundledGoogleKey;
        $('#settings-dialog').showModal();
      }
    }
  }
  function setMapAttribution(map, source) {
    const id = map?.getContainer()?.id === 'map' ? '#overview-attribution' : '#explore-attribution';
    $(id).textContent = source === 'google' ? 'Google Maps' : '© OpenStreetMap contributors';
  }
  const riskStyle = feature => {
    const c = (feature.properties?.risk_category || 'HIGH').toUpperCase();
    const color = c === 'CRITICAL' ? '#c66359' : c === 'HIGH' ? '#df8b60' : '#d8b367';
    return { color, weight: 2, opacity: .75, fillColor: color, fillOpacity: .24 };
  };
  function riskPopup(feature, layer) {
    const p = feature.properties || {};
    layer.bindPopup(`<div class="map-popup"><strong>${esc(p.name || 'Flood risk zone')}</strong><span class="table-risk ${(p.risk_category || '').toLowerCase()}">${esc(p.risk_category || 'Modeled')}</span><p>Estimated depth: ${fmt(p.estimated_depth_m,2)} m</p><small>${esc(p.primary_driver || 'Scenario-based estimate')}</small></div>`);
  }
  function initOverviewMap() {
    overviewMap = initMap('map'); if (!overviewMap) { $('#map').innerHTML = '<div class="chart-empty">Map library unavailable. Check your internet connection.</div>'; return; }
    overviewMap.setView([19.075,72.865], 12);
    loadRiskLayer(overviewMap, 'overview');
    $('#overview-basemap').addEventListener('change', e => changeBasemap(overviewMap, e.target));
    $('#zoom-in').onclick = () => overviewMap.zoomIn(); $('#zoom-out').onclick = () => overviewMap.zoomOut();
    $('#reset-map').onclick = () => overviewMap.setView([19.075,72.865],12);
  }
  async function loadRiskLayer(map, target, scenarioId = selectedScenario) {
    try {
      const data = await api(`/analytics/risk-map?scenario_id=${encodeURIComponent(scenarioId)}`);
      const old = target === 'overview' ? overviewRisk : exploreRisk; if (old) map.removeLayer(old);
      const layer = L.geoJSON(data, { style:riskStyle, onEachFeature:riskPopup }); layer.addTo(map);
      if (target === 'overview') overviewRisk = layer; else exploreRisk = layer;
    } catch (e) { if (target === 'overview') $('#map-updated').textContent = 'Risk layer unavailable · check backend connection'; }
  }
  function initExploreMap() {
    exploreMap = initMap('explore-map'); if (!exploreMap) return;
    exploreMap.setView([19.075,72.865],12);
    loadRiskLayer(exploreMap,'explore',$('#map-scenario').value || selectedScenario);
    $('#explore-zoom-in').onclick = () => exploreMap.zoomIn(); $('#explore-zoom-out').onclick = () => exploreMap.zoomOut();
    $('#explore-reset').onclick = () => exploreMap.setView([19.075,72.865],12);
    loadMapLayers();
    $('#explore-basemap').addEventListener('change', e => changeBasemap(exploreMap, e.target));
    $('#map-scenario').addEventListener('change', e => loadRiskLayer(exploreMap,'explore',e.target.value));
    $('#layer-wards').addEventListener('change', e => toggleLayer(wardLayer,e.target.checked));
    $('#layer-roads').addEventListener('change', async e => { if (e.target.checked && !roadLayer) roadLayer = await geoLayer('/infrastructure/roads/geojson?limit=2500', {style:f=>({color:'#8d9e91',weight:1,opacity:.48}),onEachFeature:(f,l)=>l.bindPopup(esc(f.properties?.name || f.properties?.road_class || 'Road segment'))}); toggleLayer(roadLayer,e.target.checked); });
    $('#layer-water').addEventListener('change', e => toggleLayer(waterLayer,e.target.checked));
    $('#layer-facilities').addEventListener('change', async e => { if (e.target.checked && !facilityLayer) await refreshFacilities(); toggleLayer(facilityLayer,e.target.checked); });
    $('#facility-filter').addEventListener('change', refreshFacilities);
  }
  function toggleLayer(layer, enabled) { if (!exploreMap || !layer) return; enabled ? layer.addTo(exploreMap) : exploreMap.removeLayer(layer); }
  async function geoLayer(path, opts = {}) { const data = await api(path); return L.geoJSON(data, opts); }
  async function loadMapLayers() {
    try { wardLayer = await geoLayer('/study-areas/geojson',{style:{color:'#75947d',weight:1,fillColor:'#d8e5d8',fillOpacity:.08},onEachFeature:(f,l)=>l.bindPopup(`<strong>${esc(f.properties?.name || 'Study area')}</strong><br>${fmt(f.properties?.population)} residents`)}); toggleLayer(wardLayer,true); } catch {}
    try { waterLayer = await geoLayer('/infrastructure/waterways/geojson',{style:{color:'#629bb0',weight:2.4,opacity:.8}}); toggleLayer(waterLayer,$('#layer-water').checked); } catch {}
    if ($('#layer-facilities').checked) refreshFacilities();
  }
  async function refreshFacilities() {
    try {
      if (facilityLayer) exploreMap.removeLayer(facilityLayer);
      const type = $('#facility-filter').value;
      const data = await api(`/infrastructure/geojson${type ? `?feature_type=${encodeURIComponent(type)}` : ''}`);
      facilityLayer = L.geoJSON(data,{pointToLayer:(feature,latlng)=>L.circleMarker(latlng,{radius:5,color:'#fff',weight:1.5,fillColor:feature.properties?.feature_type==='hospital'?'#c46f61':feature.properties?.feature_type==='school'?'#698b71':'#6e9ab0',fillOpacity:.95}),onEachFeature:(f,l)=>l.bindPopup(`<strong>${esc(f.properties?.name || 'Facility')}</strong><br><small>${esc(f.properties?.feature_type || 'Infrastructure')}</small>`)});
      if ($('#layer-facilities').checked) facilityLayer.addTo(exploreMap);
    } catch { toast('Could not load infrastructure layer',true); }
  }
  function fillScenarioSelects() {
    const options = scenarios.map(s=>`<option value="${esc(s.scenario_id)}">${esc(s.scenario_name)} · ${fmt(s.rainfall_total_mm)} mm</option>`).join('');
    ['map-scenario','exposure-scenario'].forEach(id=>{ const el=$(`#${id}`); const prior=el.value; el.innerHTML=options || '<option value="SCEN_HEAVY_200MM">Heavy rainfall · 200 mm</option>'; if ([...el.options].some(o=>o.value===prior)) el.value=prior; else if ([...el.options].some(o=>o.value===selectedScenario)) el.value=selectedScenario; });
  }
  async function loadOverview() {
    const tasks = [loadWeather(),loadScenarios()];
    try { latestExposure = await api(`/analytics/exposure?scenario_id=${encodeURIComponent(selectedScenario)}`); renderExposure(latestExposure); } catch { $('#ward-list').innerHTML='<div class="chart-empty">Exposure data is unavailable. Check the backend connection.</div>'; }
    await Promise.allSettled(tasks);
  }
  async function loadWeather() {
    try {
      const data = await api('/weather');
      $('#rain-value').textContent=fmt(data.past_24h_rainfall_mm,1); $('#forecast-value').textContent=fmt(data.forecast_next_24h_mm,1);
      const alert=data.alert_level || 'Normal'; $('#rain-alert').textContent=alert.replace(/\s*\([^)]*\)/,'');
      $('#weather-alert').innerHTML=`<i></i>${esc(alert.split('(')[0].trim())}`;
      const rain=Number(data.past_24h_rainfall_mm)||0; $('#rain-trend').textContent=rain>=115.6?'Heavy rainfall':rain>=64.5?'Elevated':'Within normal range';
      $('#weather-observed').textContent=new Date(data.latest_observation.timestamp).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
      $('#weather-source').textContent=data.latest_observation.source || 'Weather station';
      const level=rain>=204.4?'danger':rain>=64.5?'warning':''; $('#weather-alert').className=`weather-alert ${level}`;
      const trend=data.rainfall_trend_7d || []; const max=Math.max(1,...trend.map(x=>Number(x.rainfall_mm)||0));
      $('#rain-chart').innerHTML=trend.length?trend.map((x,i)=>`<div class="rain-bar-group"><div class="rain-bar ${i===trend.length-1?'today':''}" style="height:${Math.max(4,(Number(x.rainfall_mm)||0)/max*82)}%" data-value="${fmt(x.rainfall_mm,1)}"></div><span class="rain-day">${esc(x.date || '')}</span></div>`).join(''):'<div class="chart-empty">No recent observations</div>';
    } catch { $('#rain-alert').textContent='Weather data unavailable'; $('#rain-chart').innerHTML='<div class="chart-empty">Could not reach the weather endpoint.</div>'; $('#weather-alert').innerHTML='<i></i>Offline'; }
  }
  async function loadScenarios() {
    try {
      scenarios=await api('/scenarios'); fillScenarioSelects();
      const selectScenario=scenarios.find(s=>s.scenario_id===selectedScenario) || scenarios.find(s=>s.rainfall_total_mm>=180) || scenarios[0];
      if (selectScenario) { selectedScenario=selectScenario.scenario_id; fillScenarioSelects(); }
      renderScenarioChart(); renderSavedScenarios();
      const exp=await api(`/analytics/exposure?scenario_id=${encodeURIComponent(selectedScenario)}`); latestExposure=exp; renderExposure(exp);
      if (overviewMap) loadRiskLayer(overviewMap,'overview',selectedScenario);
    } catch { $('#scenario-chart').innerHTML='<div class="chart-empty">Scenario comparisons are unavailable.</div>'; $('#saved-scenario-list').innerHTML='<div class="chart-empty">Could not load saved scenarios.</div>'; }
  }
  function renderScenarioChart() {
    const rows=(latestExposure?.scenario_comparisons || []).slice().sort((a,b)=>a.rainfall_mm-b.rainfall_mm);
    if (!rows.length) { $('#scenario-chart').innerHTML='<div class="chart-empty">No scenario results are available yet.</div>'; return; }
    const maxArea=Math.max(1,...rows.map(s=>Number(s.high_risk_area_sqkm)||0));
    const maxPop=Math.max(1,...rows.map(s=>Number(s.exposed_population)||0));
    $('#scenario-chart').innerHTML=rows.slice(-6).map(s=>`<div class="scenario-column" title="${esc(s.scenario_name)}"><div class="scenario-bars"><i class="scenario-bar" style="height:${Math.max(5,(Number(s.high_risk_area_sqkm)||0)/maxArea*100)}%" data-value="${fmt(s.high_risk_area_sqkm,1)} km²"></i><i class="scenario-bar people-bar" style="height:${Math.max(5,(Number(s.exposed_population)||0)/maxPop*100)}%" data-value="${fmt(s.exposed_population)} people"></i></div><span class="scenario-label">${fmt(s.rainfall_mm)} mm</span></div>`).join('');
  }
  function renderExposure(data) {
    if (!data) return;
    const s=data.summary || {}, selected=data.selected_scenario || {};
    $('#population-value').textContent=compact(s.estimated_exposed_population); $('#area-value').textContent=fmt(s.high_risk_area_sqkm,1);
    $('#facility-value').textContent=fmt(s.exposed_hospitals_count); $('#facility-count').textContent=fmt(s.exposed_hospitals_count);
    $('#population-change').textContent=`${fmt(selected.rainfall_total_mm)} mm scenario`; $('#risk-pill').textContent=(selected.rainfall_total_mm||0)>=200?'HIGH SCENARIO':'MODELED';
    $('#population-track').style.width=`${Math.min(100,(Number(s.estimated_exposed_population)||0)/1000000*100)}%`;
    $('#area-track').style.width=`${Math.min(100,(Number(s.high_risk_area_sqkm)||0)/50*100)}%`;
    $('#facility-track').style.width=`${Math.min(100,(Number(s.exposed_hospitals_count)||0)/12*100)}%`;
    $('#exposure-pop').textContent=fmt(s.estimated_exposed_population); $('#exposure-area').textContent=fmt(s.high_risk_area_sqkm,2);
    $('#exposure-roads').textContent=fmt(s.affected_road_segments_count); $('#exposure-hospitals').textContent=fmt(s.exposed_hospitals_count);
    $('#exposure-scenario-name').textContent=selected.scenario_name || 'Selected scenario';
    const wards=(data.ward_exposure||[]).slice().sort((a,b)=>(Number(b.exposed_population)||0)-(Number(a.exposed_population)||0));
    const max=Math.max(1,...wards.map(w=>Number(w.exposed_population)||0));
    $('#ward-list').innerHTML=wards.length?wards.slice(0,5).map(w=>`<div class="ward-row"><span class="ward-name">${esc(w.ward_name)}</span><span class="ward-bar"><i style="width:${(Number(w.exposed_population)||0)/max*100}%"></i></span><span class="ward-count">${compact(w.exposed_population)}</span></div>`).join(''):'<div class="chart-empty">No ward-level estimates available.</div>';
    $('#exposure-table').innerHTML=wards.map(w=>`<tr><td>${esc(w.ward_name)}</td><td><span class="table-risk ${(w.risk_category||'').toLowerCase()}">${esc(w.risk_category || 'Unknown')}</span></td><td>${fmt(w.exposed_population)}</td><td>${fmt(w.high_risk_area_km2,2)} km²</td><td><span class="inline-bar"><i style="width:${(Number(w.exposed_population)||0)/max*100}%"></i></span></td></tr>`).join('') || '<tr><td colspan="5">Ward detail is not available.</td></tr>';
    $('#exposure-limits').innerHTML=(data.limitations||[]).map(t=>`<div>• ${esc(t)}</div>`).join('');
    renderScenarioChart();
  }
  function renderSavedScenarios() {
    const recent=scenarios.slice(0,6);
    $('#saved-scenario-list').innerHTML=recent.length?recent.map(s=>`<div class="saved-row"><div><strong>${esc(s.scenario_name)}</strong><small>${new Date(s.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})} · ${fmt(s.duration_hours)}h duration</small></div><span class="saved-rain">${fmt(s.rainfall_total_mm)} mm</span></div>`).join(''):'<div class="chart-empty">Create your first scenario using the form above.</div>';
  }
  async function loadExposure(scenarioId) {
    try { const data=await api(`/analytics/exposure?scenario_id=${encodeURIComponent(scenarioId)}`); latestExposure=data; renderExposure(data); }
    catch { $('#exposure-table').innerHTML='<tr><td colspan="5">Exposure data could not be loaded. Check backend connection.</td></tr>'; }
  }
  async function loadInsights() {
    try {
      const [metrics,research]=await Promise.all([api('/models/metrics'),api('/models/research-questions')]);
      $('#model-name').textContent=metrics.model_name || 'Flood risk classification'; $('#model-version').textContent=metrics.model_version || '—';
      const m=metrics.metrics||{}; $('#auc-score').textContent=fmt(m.roc_auc,3); $('#f1-score').textContent=fmt(m.f1_score,3);
      const feats=metrics.feature_importance||[]; const max=Math.max(1,...feats.map(x=>Number(x.importance)||0));
      $('#feature-list').innerHTML=feats.map(f=>`<div><div class="feature-row-head"><span>${esc((f.feature||f.name||'').replaceAll('_',' '))}</span><b>${fmt(f.importance,3)}</b></div><div class="feature-track"><i style="width:${Number(f.importance)/max*100}%"></i></div></div>`).join('') || '<div class="chart-empty">Feature importance is unavailable.</div>';
      $('#model-limitations').innerHTML=(metrics.scientific_limitations||[]).map(x=>`<li>${esc(x)}</li>`).join('') || '<li>No limitations supplied.</li>';
      const entries=Object.entries(research);
      $('#research-list').innerHTML=entries.map(([key,item],i)=>`<div class="research-card"><span class="rq">RESEARCH QUESTION 0${i+1}</span><h3>${esc(item.question||'')}</h3><p>${esc(item.conclusion||'')}</p></div>`).join('');
    } catch { $('#model-name').textContent='Model metrics unavailable'; $('#feature-list').innerHTML='<div class="chart-empty">Could not load model evaluation data.</div>'; }
  }
  async function createScenario(event) {
    event.preventDefault(); const button=$('#run-scenario'); button.disabled=true; button.innerHTML='<span>◌</span> Running simulation…';
    const rainfall=Number($('#rainfall-input').value), duration=Number($('#duration-input').value), drainage=Number($('#drainage-input').value);
    const payload={study_area_id:'MUM_WARD_L_KURLA',scenario_name:$('#scenario-name').value.trim(),rainfall_total_mm:rainfall,duration_hours:duration,assumptions:{soil_saturation_pct:75,drainage_efficiency_pct:drainage,high_tide_height_m:Number($('#tide-input').value)},mitigation_features:{mithi_river_desilting:$('#mitigation-desilt').checked,additional_pumping_stations:$('#mitigation-pumps').checked,holding_ponds_active:$('#mitigation-ponds').checked}};
    try {
      const result=await api('/scenarios',{method:'POST',body:JSON.stringify(payload)});
      const scenario=result.scenario||{}, sim=result.simulation_result||{}, m=sim.summary_metrics||{}; selectedScenario=scenario.scenario_id;
      $('#scenario-result').className='panel result-placeholder result-success';
      $('#scenario-result').innerHTML=`<div class="result-icon">✓</div><h2>Simulation complete</h2><p>${esc(scenario.scenario_name)} · ${fmt(scenario.rainfall_total_mm)} mm over ${fmt(scenario.duration_hours)} hours</p><div class="result-metrics"><div class="result-metric"><strong>${fmt(m.estimated_exposed_population)}</strong><span>People exposed</span></div><div class="result-metric"><strong>${fmt(m.high_risk_area_sqkm,2)} km²</strong><span>High risk area</span></div><div class="result-metric"><strong>${fmt(m.exposed_hospitals_count)}</strong><span>Hospitals exposed</span></div></div><div class="eyebrow">WARD EXPOSURE</div><div class="ward-list">${Object.values(sim.ward_breakdown||{}).slice().sort((a,b)=>(b.exposed_pop||0)-(a.exposed_pop||0)).slice(0,4).map(w=>`<div class="ward-row"><span class="ward-name">${esc(w.name)}</span><span class="ward-bar"><i style="width:${Math.min(100,(w.exposed_pop||0)/Math.max(1,m.estimated_exposed_population||1)*100)}%"></i></span><span class="ward-count">${compact(w.exposed_pop)}</span></div>`).join('')}</div><p>Estimated runoff: ${fmt(sim.uncertainty_metadata?.effective_runoff_mm,1)} mm · Mitigation benefit: ${fmt(sim.uncertainty_metadata?.mitigation_benefit_pct,1)}%</p><button class="button button-dark" id="view-result-exposure">View exposure details</button>`;
      $('#view-result-exposure').onclick=()=>{setPage('exposure');$('#exposure-scenario').value=selectedScenario;loadExposure(selectedScenario);};
      await loadScenarios(); toast('Scenario saved and simulation completed');
    } catch (e) { toast(`Simulation failed: ${e.message}`,true); }
    finally { button.disabled=false;button.innerHTML='<span>▶</span> Run simulation'; }
  }
  function bindControls() {
    $('#rainfall-input').addEventListener('input',e=>$('#rainfall-display').textContent=e.target.value);
    $('#tide-input').addEventListener('input',e=>$('#tide-display').textContent=Number(e.target.value).toFixed(1));
    $('#scenario-form').addEventListener('submit',createScenario);
    $('#refresh-scenarios').addEventListener('click',loadScenarios);
    $('#exposure-scenario').addEventListener('change',e=>{selectedScenario=e.target.value;loadExposure(e.target.value);});
    $('#settings-button').addEventListener('click',()=>{ $('#api-url').value=apiBase;$('#google-map-key').value=localStorage.getItem(GOOGLE_KEY)||bundledGoogleKey;$('#settings-dialog').showModal(); });
    $('#save-api').addEventListener('click',async()=>{apiBase=$('#api-url').value.trim().replace(/\/$/,'');if(!apiBase){toast('Enter a backend URL',true);return;}localStorage.setItem(API_KEY,apiBase);const googleKey=$('#google-map-key').value.trim();if(googleKey)localStorage.setItem(GOOGLE_KEY,googleKey);else localStorage.removeItem(GOOGLE_KEY);googleLoader=null;$('#settings-dialog').close();await connect();await loadOverview();toast('Settings saved');});
  }
  async function connect() {
    try {
      await api('/health');
      connection(true);
      return true;
    } catch {
      if (apiBase.includes('127.0.0.1')) {
        const alt = apiBase.replace('127.0.0.1', 'localhost');
        try {
          const res = await fetch(`${alt}/api/health`);
          if (res.ok) {
            apiBase = alt;
            connection(true);
            return true;
          }
        } catch {}
      } else if (apiBase.includes('localhost')) {
        const alt = apiBase.replace('localhost', '127.0.0.1');
        try {
          const res = await fetch(`${alt}/api/health`);
          if (res.ok) {
            apiBase = alt;
            connection(true);
            return true;
          }
        } catch {}
      }
      connection(false);
      return false;
    }
  }
  async function start() {
    const now = new Date();
    $('#today-date').textContent=now.toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'});
    $('#today-eyebrow').textContent=now.toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long'}).toUpperCase();
    bindNavigation();bindControls();initOverviewMap();
    const initial=location.hash.slice(1); if(initial && initial!=='overview') setPage(initial);
    await connect();
    await loadOverview();
    loadInsights();
    setInterval(connect,30000);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
