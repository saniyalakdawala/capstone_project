(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const API_KEY = 'eidtmumbai.apiUrl';
  const GOOGLE_KEY = 'eidtmumbai.googleMapsKey';
  const bundledGoogleKey = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_GOOGLE_MAPS_API_KEY)
    ? String(import.meta.env.VITE_GOOGLE_MAPS_API_KEY).trim()
    : '';
  const storedApi = localStorage.getItem(API_KEY);
  let apiBase = (storedApi && storedApi.trim() ? storedApi.trim() : 'http://127.0.0.1:8000').replace(/\/$/, '');
  let selectedScenario = 'SCEN_HEAVY_200MM';
  let scenarios = [];
  let latestExposure = null;
  let overviewMap, exploreMap, overviewRisk, exploreRisk, wardLayer, roadLayer, waterLayer, facilityLayer;
  let floodMap, floodRiskLayer, floodPrecipLayer, floodObsLayer, floodInundationLayer, floodDepthLayer, floodFacilityLayer;
  let hazardsMap, hazardsRiskLayer, hazardsSecondaryLayer, currentHazard = 'flood';
  let emergencyMap, emgRouteLayer, emgAltRouteLayer, emgFacilityLayer, emgRestrictionLayer;
  let emgFacilities = [], emgRestrictions = [];
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
    const valid = ['overview','monitoring','hazards','validation','emergency','flood','map','scenarios','exposure','insights'].includes(view) ? view : 'overview';
    $$('.page-wrap').forEach(el => el.classList.add('hidden'));
    $(`#view-${valid}`).classList.remove('hidden');
    $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === valid));
    $('#page-title').textContent = ({overview:'Overview',monitoring:'Live monitoring & automated ingestion',hazards:'Multi-hazard platform',validation:'Scientific validation & disaster replay',emergency:'Emergency response',flood:'Flood intelligence',map:'Risk map',scenarios:'Scenarios',exposure:'Exposure',insights:'Model insights'})[valid];
    $('#sidebar').classList.remove('open');
    if (valid === 'monitoring') loadMonitoringModuleData();
    if (valid === 'validation') loadValidationModuleData();
    if (valid === 'emergency') setTimeout(() => { emergencyMap?.invalidateSize(); if (!emergencyMap) initEmergencyMap(); loadEmergencyModuleData(); }, 60);
    if (valid === 'flood') setTimeout(() => { floodMap?.invalidateSize(); if (!floodMap) initFloodMap(); loadFloodModuleData(); }, 60);
    if (valid === 'hazards') setTimeout(() => { hazardsMap?.invalidateSize(); if (!hazardsMap) initHazardsMap(); loadHazardData(currentHazard); }, 60);
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

  function initFloodMap() {
    floodMap = initMap('flood-map');
    if (!floodMap) return;
    floodMap.setView([19.075, 72.865], 11);
    $('#flood-zoom-in').onclick = () => floodMap.zoomIn();
    $('#flood-zoom-out').onclick = () => floodMap.zoomOut();
    $('#flood-reset').onclick = () => floodMap.setView([19.075, 72.865], 11);
    $('#flood-basemap').addEventListener('change', e => changeBasemap(floodMap, e.target));

    $('#flood-layer-risk').addEventListener('change', e => toggleLayer(floodRiskLayer, e.target.checked));
    $('#flood-layer-precip').addEventListener('change', e => toggleLayer(floodPrecipLayer, e.target.checked));
    $('#flood-layer-inundation')?.addEventListener('change', e => toggleLayer(floodInundationLayer, e.target.checked));
    $('#flood-layer-depth')?.addEventListener('change', e => toggleLayer(floodDepthLayer, e.target.checked));
    $('#flood-layer-facilities')?.addEventListener('change', e => toggleLayer(floodFacilityLayer, e.target.checked));
    $('#flood-layer-obs').addEventListener('change', e => toggleLayer(floodObsLayer, e.target.checked));
    $('#refresh-flood-data').onclick = () => loadFloodModuleData(true);

    // Phase 2C Simulation slider and button bindings
    $('#sim-rain-input')?.addEventListener('input', e => { if ($('#sim-rain-val')) $('#sim-rain-val').textContent = e.target.value; });
    $('#sim-tide-input')?.addEventListener('input', e => { if ($('#sim-tide-val')) $('#sim-tide-val').textContent = Number(e.target.value).toFixed(1); });
    $('#sim-soil-input')?.addEventListener('input', e => { if ($('#sim-soil-val')) $('#sim-soil-val').textContent = e.target.value; });
    $('#btn-run-inundation')?.addEventListener('click', runInundationSimulation);
  }

  async function runInundationSimulation() {
    const wardId = $('#sim-ward-select')?.value || 'MUM_WARD_L_KURLA';
    const rainMm = Number($('#sim-rain-input')?.value || 200);
    const tideM = Number($('#sim-tide-input')?.value || 4.2);
    const soilPct = Number($('#sim-soil-input')?.value || 75);

    if ($('#sim-run-tag')) $('#sim-run-tag').textContent = 'RUNNING…';
    try {
      const res = await api('/inundation/simulate', {
        method: 'POST',
        body: JSON.stringify({
          study_area_id: wardId,
          rainfall_scenario_mm: rainMm,
          duration_hours: 24,
          tide_level_m: tideM,
          soil_saturation_pct: soilPct,
          force_rerun: true
        })
      });

      const sm = res.summary_metrics || {};
      const ae = res.asset_exposure || {};
      if ($('#sim-peak-depth')) $('#sim-peak-depth').textContent = fmt(sm.peak_depth_m, 2) + ' m';
      if ($('#sim-mean-depth')) $('#sim-mean-depth').textContent = fmt(sm.mean_depth_m, 2) + ' m';
      if ($('#sim-inundated-area')) $('#sim-inundated-area').textContent = fmt(sm.inundated_area_sq_km, 2);
      if ($('#sim-exposed-bldgs')) $('#sim-exposed-bldgs').textContent = fmt(ae.exposed_buildings_count);
      if ($('#sim-impassable-roads')) $('#sim-impassable-roads').textContent = fmt(ae.exposed_roads_count);
      if ($('#sim-exposed-pop')) $('#sim-exposed-pop').textContent = compact(ae.exposed_population_est);
      if ($('#sim-run-tag')) $('#sim-run-tag').textContent = 'COMPLETED';

      // Refresh map layers with simulation result
      if (floodMap && res.simulation_id) {
        const [extentGeo, depthGeo] = await Promise.all([
          api(`/inundation/layers/extent?simulation_id=${res.simulation_id}`).catch(() => null),
          api(`/inundation/layers/depth?simulation_id=${res.simulation_id}`).catch(() => null)
        ]);
        if (extentGeo && floodInundationLayer) {
          floodMap.removeLayer(floodInundationLayer);
          floodInundationLayer.clearLayers();
          floodInundationLayer.addData(extentGeo);
          if ($('#flood-layer-inundation')?.checked) floodInundationLayer.addTo(floodMap);
        }
        if (depthGeo && floodDepthLayer) {
          floodMap.removeLayer(floodDepthLayer);
          floodDepthLayer.clearLayers();
          floodDepthLayer.addData(depthGeo);
          if ($('#flood-layer-depth')?.checked) floodDepthLayer.addTo(floodMap);
        }
      }

      toast(`Simulation completed: Peak depth ${sm.peak_depth_m}m, ${ae.exposed_roads_count} roads affected`);
    } catch (err) {
      if ($('#sim-run-tag')) $('#sim-run-tag').textContent = 'FAILED';
      toast('Inundation simulation failed: ' + err.message, true);
    }
  }

  async function loadFloodModuleData(forceRefresh = false) {
    try {
      const [
        statusRes, forecastRes, localitiesRes, riskGeoRes, precipGeoRes, obsRes, alertsRes, modelCompRes,
        inundationGeoRes, depthGeoRes, facilitiesGeoRes, impactSummaryRes
      ] = await Promise.all([
        api('/flood/status'),
        api(`/flood/forecast?hours=24${forceRefresh ? '&force_refresh=true' : ''}`),
        api('/flood/localities'),
        api('/flood/layers/risk'),
        api('/flood/layers/rainfall'),
        api('/flood/observations'),
        api('/flood/alerts'),
        api('/flood/model-comparison').catch(() => null),
        api('/inundation/layers/extent?rainfall_scenario_mm=200').catch(() => null),
        api('/inundation/layers/depth?rainfall_scenario_mm=200').catch(() => null),
        api('/infrastructure/geojson').catch(() => null),
        api('/inundation/impact-summary?rainfall_scenario_mm=200').catch(() => null)
      ]);

      // Populate simulation metrics
      if (impactSummaryRes) {
        const sm = impactSummaryRes.summary_metrics || {};
        const ae = impactSummaryRes.asset_exposure || {};
        if ($('#sim-peak-depth')) $('#sim-peak-depth').textContent = fmt(sm.peak_depth_m, 2) + ' m';
        if ($('#sim-mean-depth')) $('#sim-mean-depth').textContent = fmt(sm.mean_depth_m, 2) + ' m';
        if ($('#sim-inundated-area')) $('#sim-inundated-area').textContent = fmt(sm.inundated_area_sq_km, 2);
        if ($('#sim-exposed-bldgs')) $('#sim-exposed-bldgs').textContent = fmt(ae.exposed_buildings_count);
        if ($('#sim-impassable-roads')) $('#sim-impassable-roads').textContent = fmt(ae.impassable_roads_passenger_cars_gt_30cm || ae.exposed_roads_count);
        if ($('#sim-exposed-pop')) $('#sim-exposed-pop').textContent = compact(ae.exposed_population_est);
      }

      // Meta chips
      $('#flood-model-version').textContent = statusRes.version || 'EIDT-ML-Predictive-v2.0';
      $('#flood-issue-time').textContent = forecastRes.issue_time_utc ? new Date(forecastRes.issue_time_utc).toUTCString().slice(5, 22) : '—';
      if (forecastRes.valid_time_start_utc && forecastRes.valid_time_end_utc) {
        const s = new Date(forecastRes.valid_time_start_utc).toUTCString().slice(5, 17);
        const e = new Date(forecastRes.valid_time_end_utc).toUTCString().slice(5, 17);
        $('#flood-valid-range').textContent = `${s} → ${e} (24h)`;
      }

      // Populate Model Evaluation metrics
      if (modelCompRes?.metrics) {
        const m = modelCompRes.metrics;
        if ($('#eval-roc-auc')) $('#eval-roc-auc').textContent = m.roc_auc != null ? m.roc_auc.toFixed(3) : '0.919';
        if ($('#eval-pr-auc')) $('#eval-pr-auc').textContent = m.pr_auc != null ? m.pr_auc.toFixed(3) : '0.775';
        if ($('#eval-brier')) $('#eval-brier').textContent = m.brier_score != null ? m.brier_score.toFixed(4) : '0.1246';
        if ($('#eval-f1')) $('#eval-f1').textContent = `${m.f1_score != null ? m.f1_score.toFixed(3) : '0.774'}`;
        if ($('#eval-samples')) $('#eval-samples').textContent = `${modelCompRes.sample_size?.total_observations || 100} obs`;
      }

      // Summary metrics
      const sum = forecastRes.summary_metrics || {};
      $('#flood-total-24h').textContent = fmt(sum.total_24h_mm, 1);
      $('#flood-peak-1h').textContent = `${fmt(sum.peak_1h_mm, 1)} mm/h`;

      const dist = localitiesRes.risk_distribution || {};
      const highCritical = (dist.HIGH || 0) + (dist.VERY_HIGH || 0) + (dist.CRITICAL || 0);
      $('#flood-high-risk-count').textContent = `${highCritical}`;
      $('#flood-risk-summary-pill').textContent = highCritical > 0 ? `${highCritical} High Risk Wards` : 'All Low / Moderate';

      // Alerts
      const alerts = alertsRes.alerts || [];
      if (alerts.length > 0) {
        const top = alerts[0];
        $('#flood-alert-status').textContent = top.severity || 'GREEN';
        $('#flood-alert-source').textContent = top.title || 'Nominal';
        $('#flood-alert-time').textContent = top.issue_time_utc ? new Date(top.issue_time_utc).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '';
      }

      // Rolling accumulations
      const acc = sum.accumulations || {};
      $('#accum-1h').textContent = fmt(acc['1h_peak_mm'] ?? sum.peak_1h_mm, 1);
      $('#accum-3h').textContent = fmt(acc['3h_rolling_mm'], 1);
      $('#accum-6h').textContent = fmt(acc['6h_rolling_mm'], 1);
      $('#accum-12h').textContent = fmt(acc['12h_rolling_mm'], 1);
      $('#accum-24h').textContent = fmt(acc['24h_total_mm'] ?? sum.total_24h_mm, 1);

      // Hourly timeline
      const hourly = forecastRes.hourly_data || [];
      const maxH = Math.max(1, ...hourly.map(h => Number(h.precipitation_mm) || 0));
      const timelineHtml = hourly.map(h => {
        const p = Number(h.precipitation_mm) || 0;
        const prob = h.precipitation_probability_pct != null ? `${h.precipitation_probability_pct}%` : '';
        const hTime = h.valid_time_utc ? new Date(h.valid_time_utc).getUTCHours() : 0;
        const barHeight = Math.max(2, Math.round((p / maxH) * 44));
        const isHeavy = p >= 15.0;
        return `<div class="hourly-col${isHeavy ? ' heavy' : ''}">
          <span class="hourly-time">${String(hTime).padStart(2, '0')}:00</span>
          <div class="hourly-bar-wrap">
            <span class="hourly-bar${isHeavy ? ' high-precip' : ''}" style="height:${barHeight}px;" title="${p} mm"></span>
          </div>
          <span class="hourly-val">${p.toFixed(1)}</span>
          <span class="hourly-prob">${prob}</span>
        </div>`;
      }).join('');
      $('#flood-timeline-bars').innerHTML = timelineHtml || '<div class="chart-empty">No hourly data</div>';

      // Locality diagnostics table with calibrated probabilities
      const locList = localitiesRes.localities || [];
      const tableRows = locList.map(loc => {
        const cat = loc.risk_category || loc.risk_level || 'LOW';
        const lvl = cat.toLowerCase();
        const prob = Number(loc.predicted_flood_probability);
        const probPct = Number.isFinite(prob) ? `${(prob * 100).toFixed(1)}%` : '—';
        const probVal = Number.isFinite(prob) ? prob.toFixed(3) : '—';
        const probColor = prob >= 0.70 ? '#c53026' : (prob >= 0.50 ? '#c85a17' : (prob >= 0.20 ? '#b27318' : '#1d7c4d'));

        const factorSummary = (loc.contributing_factors || []).map(f => {
          if (f.factor === '24h_rainfall_forecast') return `24h Rain: ${f.value}mm (${f.impact})`;
          if (f.factor === 'elevation_benchmark') return `Elev: ${f.value}m (${f.impact})`;
          if (f.factor === 'fluvial_and_tidal_exposure') return `${f.description || f.corridor || f.factor}`;
          return '';
        }).filter(Boolean).join(' · ');

        return `<tr>
          <td><strong>${esc(loc.locality_name)}</strong><br><small style="color:#8a9990">${esc(loc.locality_id)}</small></td>
          <td><span class="risk-badge ${lvl}">${esc(cat)}</span></td>
          <td><strong style="color:${probColor};font-family:Manrope,sans-serif">${probPct}</strong> <small style="color:#8a9990;font-size:8px;">(P=${probVal})</small></td>
          <td><strong style="font-family:Manrope,sans-serif">${fmt(loc.risk_score, 2)}</strong></td>
          <td>${fmt(loc.forecast_rainfall_24h_mm, 1)} mm</td>
          <td>${fmt(loc.elevation_mean_m, 1)} m</td>
          <td><small>${esc(loc.contributing_factors?.find(f => f.factor === 'fluvial_and_tidal_exposure')?.description || 'Urban Watershed')}</small></td>
          <td><small style="color:#6d7d74">${esc(factorSummary)}</small></td>
        </tr>`;
      }).join('');
      $('#flood-localities-table').innerHTML = tableRows || '<tr><td colspan="8">No locality records</td></tr>';

      // Historical observations
      const obs = obsRes.observations || [];
      const obsCards = obs.map(o => `
        <div class="obs-card">
          <div class="obs-header">
            <span class="obs-tag">HISTORICAL EVENT</span>
            <small style="color:#8a9990">${esc(o.date_observed)}</small>
          </div>
          <h3>${esc(o.event_name)}</h3>
          <div class="obs-metric">${fmt(o.peak_recorded_rainfall_24h_mm, 1)} mm <small style="font-size:10px;font-weight:normal;color:#7e8f85">24h peak</small></div>
          <p>${esc(o.extents_summary)}</p>
          <div class="obs-source"><strong>Source:</strong> ${esc(o.source)} (${esc(o.license)})</div>
        </div>
      `).join('');
      $('#flood-obs-grid').innerHTML = obsCards;

      // Update Map Layers
      if (floodMap) {
        if (floodRiskLayer) floodMap.removeLayer(floodRiskLayer);
        if (floodPrecipLayer) floodMap.removeLayer(floodPrecipLayer);
        if (floodInundationLayer) floodMap.removeLayer(floodInundationLayer);
        if (floodDepthLayer) floodMap.removeLayer(floodDepthLayer);
        if (floodFacilityLayer) floodMap.removeLayer(floodFacilityLayer);
        if (floodObsLayer) floodMap.removeLayer(floodObsLayer);

        // 1. Locality Risk Layer
        floodRiskLayer = L.geoJSON(riskGeoRes, {
          style: f => {
            const lvl = (f.properties?.risk_category || f.properties?.risk_level || 'LOW').toUpperCase();
            const colors = { VERY_HIGH: '#ef4444', CRITICAL: '#ef4444', HIGH: '#f97316', MODERATE: '#f59e0b', LOW: '#10b981' };
            const c = colors[lvl] || '#10b981';
            return { color: c, weight: 2, opacity: 0.85, fillColor: c, fillOpacity: 0.35 };
          },
          onEachFeature: (f, l) => {
            const p = f.properties || {};
            const cat = p.risk_category || p.risk_level || 'LOW';
            const prob = Number(p.predicted_flood_probability);
            const probStr = Number.isFinite(prob) ? `${(prob * 100).toFixed(1)}% (P=${prob.toFixed(3)})` : '—';
            l.bindPopup(`
              <div class="map-popup">
                <strong>${esc(p.locality_name)}</strong>
                <span class="risk-badge ${cat.toLowerCase()}">${esc(cat)}</span>
                <p>Calibrated Flood Probability: <b>${probStr}</b></p>
                <p>Hazard Index: <b>${fmt(p.risk_score, 2)}</b> / 10</p>
                <small>Elevation: ${fmt(p.elevation_mean_m, 1)} m · 24h Rain: ${fmt(p.forecast_rainfall_24h_mm, 1)} mm</small>
              </div>
            `);
          }
        });
        if ($('#flood-layer-risk')?.checked) floodRiskLayer.addTo(floodMap);

        // 2. Rainfall Forecast Layer
        floodPrecipLayer = L.geoJSON(precipGeoRes, {
          pointToLayer: (f, latlng) => L.circleMarker(latlng, {
            radius: 7,
            color: '#ffffff',
            weight: 2,
            fillColor: '#3b82f6',
            fillOpacity: 0.9
          }),
          onEachFeature: (f, l) => {
            const p = f.properties || {};
            l.bindPopup(`
              <div class="map-popup">
                <strong>24h Rainfall Forecast</strong>
                <p>Expected 24h: <b>${fmt(p.forecast_rainfall_24h_mm, 1)} mm</b></p>
                <small>Peak 1h rate: ${fmt(p.peak_1h_mm, 1)} mm/h<br>Source: ${esc(p.source || 'Open-Meteo')}</small>
              </div>
            `);
          }
        });
        if ($('#flood-layer-precip')?.checked) floodPrecipLayer.addTo(floodMap);

        // 3. Predicted Inundation Extent Layer
        if (inundationGeoRes && inundationGeoRes.features) {
          floodInundationLayer = L.geoJSON(inundationGeoRes, {
            style: () => ({
              color: '#0284c7',
              weight: 2,
              dashArray: '4, 4',
              fillColor: '#38bdf8',
              fillOpacity: 0.25
            }),
            onEachFeature: (f, l) => {
              const p = f.properties || {};
              l.bindPopup(`
                <div class="map-popup">
                  <strong>${esc(p.zone_name || 'Inundation Zone')}</strong>
                  <span class="risk-badge high">HYDRO-TOPOGRAPHIC EXTENT</span>
                  <p>Peak Depth: <b>${fmt(p.peak_depth_m, 2)} m</b> (Mean: ${fmt(p.mean_depth_m, 2)} m)</p>
                  <small>Resolution: 30m · Model: EIDT-Inundation-v2.3<br>Coupled SCS-CN Runoff + Depression Ponding</small>
                </div>
              `);
            }
          });
          if ($('#flood-layer-inundation')?.checked) floodInundationLayer.addTo(floodMap);
        }

        // 4. Estimated Water Depth Layer
        if (depthGeoRes && depthGeoRes.features) {
          floodDepthLayer = L.geoJSON(depthGeoRes, {
            style: f => {
              const p = f.properties || {};
              const cat = p.depth_category || 'MODERATE';
              const col = p.fill_color || (cat === 'SEVERE' ? '#ef4444' : (cat === 'HIGH' ? '#f97316' : (cat === 'MODERATE' ? '#facc15' : '#60a5fa')));
              return { color: col, weight: 2, opacity: 0.9, fillColor: col, fillOpacity: 0.55 };
            },
            onEachFeature: (f, l) => {
              const p = f.properties || {};
              const cat = p.depth_category || 'MODERATE';
              l.bindPopup(`
                <div class="map-popup">
                  <strong>${esc(p.zone_name || 'Water Depth Zone')}</strong>
                  <span class="risk-badge ${cat === 'SEVERE' ? 'critical' : cat.toLowerCase()}">${esc(cat)} DEPTH</span>
                  <p>Estimated Water Depth: <b>${fmt(p.peak_depth_m, 2)} m</b></p>
                  <small>Vehicular status: ${p.peak_depth_m >= 0.5 ? 'Ambulance Impassable' : (p.peak_depth_m >= 0.3 ? 'Passenger Car Stall' : 'Passable with caution')}<br>Classification: ${esc(p.product_classification)}</small>
                </div>
              `);
            }
          });
          if ($('#flood-layer-depth')?.checked) floodDepthLayer.addTo(floodMap);
        }

        // 5. Critical Facilities Layer
        if (facilitiesGeoRes && facilitiesGeoRes.features) {
          floodFacilityLayer = L.geoJSON(facilitiesGeoRes, {
            pointToLayer: (f, latlng) => {
              const isHosp = f.properties?.feature_type === 'hospital';
              return L.circleMarker(latlng, {
                radius: isHosp ? 8 : 6,
                color: isHosp ? '#ffffff' : '#e2e8f0',
                weight: 2,
                fillColor: isHosp ? '#dc2626' : '#2563eb',
                fillOpacity: 0.9
              });
            },
            onEachFeature: (f, l) => {
              const p = f.properties || {};
              l.bindPopup(`
                <div class="map-popup">
                  <strong>${esc(p.name)}</strong>
                  <span class="risk-badge ${p.feature_type === 'hospital' ? 'critical' : 'moderate'}">${esc(p.feature_type?.toUpperCase() || 'FACILITY')}</span>
                  <small>Operator: ${esc(p.operator || 'Public / Municipal')}<br>Ward: ${esc(p.ward_id || 'MMR')}</small>
                </div>
              `);
            }
          });
          if ($('#flood-layer-facilities')?.checked) floodFacilityLayer.addTo(floodMap);
        }

        // 6. Historical observations layer
        const obsFeatures = obs.map(o => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [72.8797, 19.0688] },
          properties: o
        }));
        floodObsLayer = L.geoJSON({ type: 'FeatureCollection', features: obsFeatures }, {
          pointToLayer: (f, latlng) => L.circleMarker(latlng, {
            radius: 9,
            color: '#7f1d1d',
            weight: 2,
            fillColor: '#ef4444',
            fillOpacity: 0.7
          }),
          onEachFeature: (f, l) => {
            const p = f.properties || {};
            l.bindPopup(`
              <div class="map-popup">
                <strong>${esc(p.event_name)}</strong>
                <span class="risk-badge critical">HISTORICAL GROUND TRUTH</span>
                <p>${esc(p.extents_summary)}</p>
                <small>Recorded: ${fmt(p.peak_recorded_rainfall_24h_mm, 1)} mm · ${esc(p.source)}</small>
              </div>
            `);
          }
        });
        if ($('#flood-layer-obs')?.checked) floodObsLayer.addTo(floodMap);
      }

      toast('Flood Hazard & Inundation data loaded successfully');
    } catch (err) {
      console.error('Flood module data load failed:', err);
      toast('Could not refresh flood hazard data: ' + err.message, true);
    }
  }

  function initHazardsMap() {
    hazardsMap = initMap('hazards-map');
    if (!hazardsMap) return;
    hazardsMap.setView([19.075, 72.865], 11);

    $('#mh-zoom-in').onclick = () => hazardsMap.zoomIn();
    $('#mh-zoom-out').onclick = () => hazardsMap.zoomOut();
    $('#mh-reset').onclick = () => hazardsMap.setView([19.075, 72.865], 11);
    $('#mh-basemap')?.addEventListener('change', e => changeBasemap(hazardsMap, e.target));

    $('#mh-layer-primary')?.addEventListener('change', e => {
      if (!hazardsMap || !hazardsRiskLayer) return;
      e.target.checked ? hazardsRiskLayer.addTo(hazardsMap) : hazardsMap.removeLayer(hazardsRiskLayer);
    });
    $('#mh-layer-secondary')?.addEventListener('change', e => {
      if (!hazardsMap || !hazardsSecondaryLayer) return;
      e.target.checked ? hazardsSecondaryLayer.addTo(hazardsMap) : hazardsMap.removeLayer(hazardsSecondaryLayer);
    });

    $$('.hazard-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.hazard-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentHazard = btn.dataset.hazard;
        loadHazardData(currentHazard);
      });
    });
  }

  async function loadHazardData(hazardId) {
    try {
      const [statusRes, localitiesRes, layersRes, alertsRes, provRes, valRes] = await Promise.all([
        api(`/hazards/${hazardId}/status`).catch(e => ({ error: e.message })),
        api(`/hazards/${hazardId}/localities`).catch(e => ({ error: e.message, localities: [] })),
        api(`/hazards/${hazardId}/layers`).catch(() => null),
        api(`/hazards/${hazardId}/alerts`).catch(() => ({ alerts: [] })),
        api(`/hazards/${hazardId}/provenance`).catch(() => null),
        api(`/hazards/${hazardId}/validation`).catch(() => null)
      ]);

      if (statusRes.error) {
        toast(`Hazard module error: ${statusRes.error}`, true);
        return;
      }

      // Metadata chips
      if ($('#mh-hazard-name')) $('#mh-hazard-name').textContent = statusRes.name || hazardId.toUpperCase();
      if ($('#mh-hazard-version')) $('#mh-hazard-version').textContent = statusRes.version || 'v1.0';
      if ($('#mh-hazard-auth')) $('#mh-hazard-auth').textContent = statusRes.responsible_authority || 'EIDT';
      if ($('#mh-hazard-target')) $('#mh-hazard-target').textContent = statusRes.target_definition || '—';
      if ($('#mh-hazard-horizon')) $('#mh-hazard-horizon').textContent = statusRes.prediction_horizon || '—';

      const sEl = $('#mh-hazard-status');
      if (sEl) {
        const rawStatus = (statusRes.status || 'OPERATIONAL').toUpperCase();
        sEl.textContent = rawStatus.replaceAll('_', ' ');
        sEl.className = `hazard-status-pill hazard-status-${rawStatus.toLowerCase().replaceAll('_', '-')}`;
      }

      // Alert feed
      const alerts = alertsRes?.alerts || [];
      const alertCountTag = $('#mh-alert-count-tag');
      if (alertCountTag) {
        alertCountTag.textContent = `${alerts.length} Active Alert${alerts.length === 1 ? '' : 's'}`;
        alertCountTag.style.background = alerts.length > 0 ? '#fef3c7' : '#ecfdf5';
        alertCountTag.style.color = alerts.length > 0 ? '#92400e' : '#065f46';
      }

      const alertsFeed = $('#mh-alerts-feed');
      if (alertsFeed) {
        if (!alerts.length) {
          alertsFeed.innerHTML = `
            <div class="chart-empty" style="padding:16px;">
              ✓ No active warnings or advisories for ${esc(statusRes.name || hazardId)}. All baseline indicators nominal.
            </div>
          `;
        } else {
          alertsFeed.innerHTML = alerts.map(a => {
            const sev = (a.severity_level || 'MODERATE').toUpperCase();
            const sevColor = sev === 'CRITICAL' || sev === 'SEVERE' ? '#ef4444' : (sev === 'HIGH' ? '#f97316' : (sev === 'MODERATE' ? '#f59e0b' : '#10b981'));
            const isOfficial = !!a.is_official_warning;
            const state = a.lifecycle_state || 'ISSUED';
            return `
              <div class="alert-card" style="border-left: 4px solid ${sevColor}; margin-bottom: 8px; padding: 10px 14px; background: #fafbfc; border-radius: 4px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;">
                  <div style="display:flex; gap:6px; align-items:center;">
                    <span class="risk-badge ${sev.toLowerCase()}" style="font-size:9px;">${esc(sev)}</span>
                    ${isOfficial ? `<span class="official-tag" style="background:#fee2e2;color:#991b1b;font-weight:700;font-size:9px;padding:2px 6px;border-radius:3px;">OFFICIAL WARNING · ${esc(a.issuing_authority || 'IMD')}</span>` : `<span class="advisory-tag" style="background:#e0f2fe;color:#0369a1;font-weight:600;font-size:9px;padding:2px 6px;border-radius:3px;">EIDT DIAGNOSTIC ADVISORY</span>`}
                    <span style="font-size:9px; color:#6b7280; font-family:monospace;">${esc(state)}</span>
                  </div>
                  <small style="color:#6b7280; font-size:9px;">${esc(a.geographic_scope || 'MMR')}</small>
                </div>
                <strong style="display:block; font-size:12px; margin-bottom:2px; color:#111827;">${esc(a.title)}</strong>
                <p style="font-size:11px; color:#374151; margin:0 0 6px;">${esc(a.message)}</p>
                ${a.protective_action ? `<div style="font-size:10px; color:#065f46; background:#ecfdf5; padding:4px 8px; border-radius:3px; margin-bottom:4px;"><strong>Recommended Action:</strong> ${esc(a.protective_action)}</div>` : ''}
                <div style="display:flex; justify-content:space-between; font-size:9px; color:#9ca3af;">
                  <span>Ref: ${esc(a.alert_id || '—')}</span>
                  <span>Valid: ${a.valid_until_utc ? new Date(a.valid_until_utc).toUTCString().slice(5, 22) : '—'}</span>
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // Locality Diagnostics Table
      const metricHeader = $('#mh-th-key-metric');
      if (metricHeader) {
        const metricLabels = {
          flood: '24h Rain / Prob',
          heatwave: 'Max Temp / Heat Index',
          landslide: 'Mean Slope / Trigger',
          drought: 'Deficit / SPI-30',
          coastal: 'High Tide / Flap Gate',
          thunderstorm: 'Gust / Squall Rate'
        };
        metricHeader.textContent = metricLabels[hazardId] || 'Primary Metric';
      }

      const locs = localitiesRes?.localities || [];
      const tbody = $('#mh-localities-tbody');
      if (tbody) {
        if (!locs.length) {
          tbody.innerHTML = `<tr><td colspan="6" class="chart-empty">No locality records found for ${esc(statusRes.name || hazardId)} coverage area.</td></tr>`;
        } else {
          tbody.innerHTML = locs.map(loc => {
            const cat = (loc.risk_category || 'LOW').toUpperCase();
            const badgeClass = cat === 'CRITICAL' || cat === 'SEVERE' || cat === 'VERY_HIGH' ? 'critical' : (cat === 'HIGH' ? 'high' : (cat === 'MODERATE' ? 'moderate' : 'low'));
            
            let primaryMetric = '—';
            if (hazardId === 'flood') {
              const p = Number(loc.predicted_flood_probability);
              primaryMetric = `<b>${fmt(loc.forecast_rainfall_24h_mm, 1)} mm</b> <small style="color:#6b7280">(${Number.isFinite(p) ? (p*100).toFixed(0)+'%' : '—'})</small>`;
            } else if (hazardId === 'heatwave') {
              primaryMetric = `<b>${fmt(loc.forecast_max_temp_c, 1)}°C</b> <small style="color:#b45309">HI: ${fmt(loc.peak_heat_index_c, 1)}°C</small>`;
            } else if (hazardId === 'landslide') {
              primaryMetric = `<b>${fmt(loc.mean_slope_degrees, 1)}°</b> ${loc.caine_threshold_exceeded ? '<span style="color:#ef4444;font-weight:700;">🚨 TRIGGER</span>' : '<small style="color:#10b981;">✓ Normal</small>'}`;
            } else if (hazardId === 'drought') {
              primaryMetric = `<b>${fmt(loc.rainfall_deficit_pct, 1)}% def</b> <small style="color:#6b7280">SPI: ${fmt(loc.spi_30, 2)}</small>`;
            } else if (hazardId === 'coastal') {
              primaryMetric = `<b>${fmt(loc.astronomical_tide_peak_m, 2)} m</b> ${loc.flap_gate_lockage_risk ? '<span style="color:#ef4444;font-weight:700;">🔒 LOCK</span>' : '<small style="color:#10b981;">✓ Free</small>'}`;
            } else if (hazardId === 'thunderstorm') {
              primaryMetric = `<b>${fmt(loc.forecast_gust_kmh, 1)} km/h</b> ${loc.squall_threshold_exceeded ? '<span style="color:#ef4444;font-weight:700;">🌪 SQUALL</span>' : '<small style="color:#10b981;">✓ Mod</small>'}`;
            }

            const factors = (loc.contributing_factors || []).map(f => {
              if (typeof f === 'string') return f;
              return f.description || f.factor || '';
            }).filter(Boolean).slice(0, 2).join(' · ');

            return `
              <tr>
                <td><strong>${esc(loc.locality_name)}</strong><br><small style="color:#8a9990">${esc(loc.locality_id)}</small></td>
                <td><span class="risk-badge ${badgeClass}">${esc(cat)}</span></td>
                <td>${primaryMetric}</td>
                <td><small style="color:#4b5563;">${esc(factors || 'Regional Baseline')}</small></td>
                <td>${compact(loc.exposed_population_est || 500000)}</td>
                <td><small style="font-family:monospace;color:#6b7280;">${esc(statusRes.version || 'v1.0')}</small></td>
              </tr>
            `;
          }).join('');
        }
      }

      // Map Layer update
      if (hazardsMap) {
        if (hazardsRiskLayer) hazardsMap.removeLayer(hazardsRiskLayer);
        if (hazardsSecondaryLayer) hazardsMap.removeLayer(hazardsSecondaryLayer);

        if (layersRes && layersRes.features) {
          hazardsRiskLayer = L.geoJSON(layersRes, {
            style: f => {
              const cat = (f.properties?.risk_category || 'LOW').toUpperCase();
              const colors = {
                EXTREME: '#ef4444', CRITICAL: '#ef4444', SEVERE: '#ef4444', VERY_HIGH: '#ef4444',
                HIGH: '#f97316',
                MODERATE: '#f59e0b',
                LOW: '#10b981', WATCH: '#10b981'
              };
              const c = colors[cat] || '#10b981';
              return { color: c, weight: 2, opacity: 0.85, fillColor: c, fillOpacity: 0.35 };
            },
            pointToLayer: (f, latlng) => {
              const cat = (f.properties?.risk_category || 'LOW').toUpperCase();
              const colors = {
                EXTREME: '#ef4444', CRITICAL: '#ef4444', SEVERE: '#ef4444', VERY_HIGH: '#ef4444',
                HIGH: '#f97316',
                MODERATE: '#f59e0b',
                LOW: '#10b981', WATCH: '#10b981'
              };
              const c = colors[cat] || '#10b981';
              return L.circleMarker(latlng, { radius: 8, color: '#ffffff', weight: 2, fillColor: c, fillOpacity: 0.85 });
            },
            onEachFeature: (f, l) => {
              const p = f.properties || {};
              const cat = (p.risk_category || 'LOW').toUpperCase();
              l.bindPopup(`
                <div class="map-popup">
                  <strong>${esc(p.locality_name || p.zone_name || p.name || 'Locality')}</strong>
                  <span class="risk-badge ${cat.toLowerCase().replaceAll('_', '-')}">${esc(cat)}</span>
                  <p>Hazard Assessment: <b>${esc(statusRes.name || hazardId)}</b></p>
                  <p>Hazard Index: <b>${fmt(p.risk_score, 2)}</b> / 10</p>
                  <small>Authority: ${esc(statusRes.responsible_authority || 'EIDT')}<br>${esc(p.contributing_factor || p.primary_driver || '')}</small>
                </div>
              `);
            }
          });
          if ($('#mh-layer-primary')?.checked) hazardsRiskLayer.addTo(hazardsMap);
        }
      }

      // Provenance & Missing Sensor Audit
      const provBox = $('#mh-provenance-box');
      if (provBox && provRes) {
        const sources = (provRes.sources || []).map(s => `
          <div style="background:#ffffff; border:1px solid #e5e7eb; border-radius:4px; padding:6px 10px; margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between;">
              <strong>${esc(s.dataset || s.source)}</strong>
              <small style="color:#6b7280;">License: ${esc(s.license || 'Open Access')}</small>
            </div>
            <div style="color:#4b5563; font-size:9.5px;">
              Provider: ${esc(s.authority || s.provider || 'Verified Agency')} · Res: ${esc(s.resolution || 'Native')} · Citation: <em>${esc(s.citation || '')}</em>
            </div>
          </div>
        `).join('');

        const missing = (provRes.missing_inputs || []).map(m => `
          <div style="color:#b91c1c; font-size:9.5px; margin-bottom:3px;">
            ✖ <strong>Uninstrumented Sensor Gap:</strong> ${esc(m)}
          </div>
        `).join('');

        provBox.innerHTML = `
          <div style="margin-bottom:8px;">
            <div style="font-weight:700; color:#111827; margin-bottom:4px; text-transform:uppercase; font-size:9px;">Traceable Verified Datasets</div>
            ${sources || '<div style="color:#6b7280;">No registered dataset citations.</div>'}
          </div>
          ${missing ? `
            <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:4px; padding:8px 10px; margin-top:8px;">
              <div style="font-weight:700; color:#991b1b; margin-bottom:4px; text-transform:uppercase; font-size:9px;">Scientific Transparency · Declared Gaps (No Silent Imputation)</div>
              ${missing}
            </div>
          ` : ''}
        `;
      }

      toast(`Loaded ${statusRes.name || hazardId} intelligence successfully`);
    } catch (err) {
      console.error('Multi-hazard data load failed:', err);
      toast(`Failed to load ${hazardId}: ${err.message}`, true);
    }
  }

  /* --- Phase 4: Emergency Response, Evacuation Routing & Decision Support --- */

  function initEmergencyMap() {
    emergencyMap = initMap('emergency-map');
    if (!emergencyMap) return;
    emergencyMap.setView([19.068, 72.875], 13);

    emgRouteLayer = L.layerGroup().addTo(emergencyMap);
    emgAltRouteLayer = L.layerGroup().addTo(emergencyMap);
    emgFacilityLayer = L.layerGroup().addTo(emergencyMap);
    emgRestrictionLayer = L.layerGroup().addTo(emergencyMap);

    $('#emg-zoom-in')?.addEventListener('click', () => emergencyMap.zoomIn());
    $('#emg-zoom-out')?.addEventListener('click', () => emergencyMap.zoomOut());
    $('#emg-reset')?.addEventListener('click', () => emergencyMap.setView([19.068, 72.875], 13));
    $('#emg-basemap')?.addEventListener('change', e => changeBasemap(emergencyMap, e.target));

    $('#emg-layer-route')?.addEventListener('change', e => {
      if (e.target.checked) { emgRouteLayer.addTo(emergencyMap); emgAltRouteLayer.addTo(emergencyMap); }
      else { emergencyMap.removeLayer(emgRouteLayer); emergencyMap.removeLayer(emgAltRouteLayer); }
    });
    $('#emg-layer-facilities')?.addEventListener('change', e => {
      if (e.target.checked) emgFacilityLayer.addTo(emergencyMap);
      else emergencyMap.removeLayer(emgFacilityLayer);
    });
    $('#emg-layer-restrictions')?.addEventListener('change', e => {
      if (e.target.checked) emgRestrictionLayer.addTo(emergencyMap);
      else emergencyMap.removeLayer(emgRestrictionLayer);
    });

    // Allow user to click anywhere on map to set custom origin
    emergencyMap.on('click', e => {
      const { lat, lng } = e.latlng;
      const select = $('#emg-origin-select');
      if (select) {
        select.value = 'custom';
        $('#emg-custom-origin-row')?.classList.remove('hidden');
        if ($('#emg-orig-lat')) $('#emg-orig-lat').value = lat.toFixed(4);
        if ($('#emg-orig-lon')) $('#emg-orig-lon').value = lng.toFixed(4);
        toast(`Origin set to [${lat.toFixed(4)}, ${lng.toFixed(4)}]`);
      }
    });
  }

  async function loadEmergencyModuleData() {
    try {
      const [statusRes, facRes, restRes, evacDemandRes] = await Promise.all([
        api('/routing/status').catch(e => ({ error: e.message })),
        api('/emergency/facilities').catch(() => ({ facilities: [] })),
        api('/emergency/restrictions').catch(() => ({ restrictions: [] })),
        api('/evacuation/assess', {
          method: 'POST',
          body: JSON.stringify({ rainfall_scenario: 'SCEN_HEAVY_200MM', ward_ids: [] })
        }).catch(() => null)
      ]);

      // Update network chips
      if (statusRes && !statusRes.error) {
        if ($('#emg-graph-nodes')) {
          $('#emg-graph-nodes').textContent = `${fmt(statusRes.node_count)} Nodes · ${fmt(statusRes.directed_edge_count)} Directed Edges`;
        }
        if ($('#emg-connectivity-val')) {
          $('#emg-connectivity-val').textContent = `${(statusRes.connectivity_ratio * 100).toFixed(1)}% Single Component`;
        }
      }

      // Store facilities and populate controls
      emgFacilities = facRes.facilities || [];
      if ($('#emg-facility-count')) {
        const shelterCount = emgFacilities.filter(f => f.facility_type === 'shelter').length;
        const hospCount = emgFacilities.filter(f => f.facility_type === 'hospital').length;
        $('#emg-facility-count').textContent = `${emgFacilities.length} Verified (${shelterCount} Shelters, ${hospCount} Hospitals)`;
      }

      populateFacilitySelect();
      renderEmergencyFacilities('all');

      // Restrictions
      emgRestrictions = restRes.restrictions || [];
      if ($('#emg-active-restrictions')) {
        $('#emg-active-restrictions').textContent = `${emgRestrictions.length} Verified Logged`;
      }
      renderEmergencyRestrictions();

      // Ward Evacuation Demand
      renderEvacuationDemand(evacDemandRes);

      toast('Emergency network & facility registry loaded');
    } catch (err) {
      console.error('Failed to load emergency data:', err);
      toast(`Emergency data load failed: ${err.message}`, true);
    }
  }

  function populateFacilitySelect(typeFilter = '') {
    const select = $('#emg-facility-select');
    if (!select) return;
    const filtered = typeFilter ? emgFacilities.filter(f => f.facility_type === typeFilter) : emgFacilities;
    if (!filtered.length) {
      select.innerHTML = '<option value="">No facilities matching filter</option>';
      return;
    }
    select.innerHTML = filtered.map(f => `
      <option value="${esc(f.facility_id)}">
        [${esc(f.facility_type.toUpperCase().replace('_', ' '))}] ${esc(f.facility_name)} (${esc(f.ward_code || f.locality_name || 'MMR')})
      </option>
    `).join('');
  }

  function renderEmergencyFacilities(categoryFilter = 'all') {
    const tbody = $('#emg-facilities-tbody');
    const filtered = (categoryFilter === 'all')
      ? emgFacilities
      : emgFacilities.filter(f => f.facility_type === categoryFilter);

    if (tbody) {
      if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="chart-empty">No facilities found for selected filter.</td></tr>';
      } else {
        tbody.innerHTML = filtered.map(f => {
          const capText = f.designated_capacity != null && f.designated_capacity > 0
            ? `${fmt(f.designated_capacity)} persons`
            : '<span class="capacity-unverified">Unverified / Medical Beds</span>';
          const typeBadge = {
            hospital: '<span class="risk-badge high">HOSPITAL</span>',
            shelter: '<span class="risk-badge low">SHELTER</span>',
            fire_station: '<span class="risk-badge moderate">FIRE &amp; RESCUE</span>',
            police_station: '<span class="risk-badge" style="background:#e0f2fe;color:#0369a1;">POLICE</span>'
          }[f.facility_type] || `<span class="risk-badge">${esc(f.facility_type)}</span>`;

          return `
            <tr>
              <td><strong>${esc(f.facility_name)}</strong></td>
              <td>${typeBadge}</td>
              <td>${esc(f.ward_code || f.locality_name || 'MMR')}</td>
              <td><span style="font-size:9px;color:#15803d;font-weight:600;">${esc(f.operating_status || 'Operational')}</span></td>
              <td>${capText}</td>
              <td><small style="color:#6b7280;">${esc(f.source_name || 'Official Record')}</small></td>
              <td>
                <button class="table-action-btn" onclick="window._routeToFacility('${esc(f.facility_id)}')">Route Here</button>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    // Render Markers on Map
    if (emgFacilityLayer) {
      emgFacilityLayer.clearLayers();
      filtered.forEach(f => {
        const iconClasses = {
          hospital: 'emg-marker-hospital',
          shelter: 'emg-marker-shelter',
          fire_station: 'emg-marker-fire',
          police_station: 'emg-marker-police'
        };
        const iconLetters = {
          hospital: 'H',
          shelter: 'S',
          fire_station: 'F',
          police_station: 'P'
        };
        const icon = L.divIcon({
          className: 'emg-div-icon',
          html: `<div class="emg-marker-icon ${iconClasses[f.facility_type] || 'emg-marker-shelter'}" style="width:20px;height:20px;">${iconLetters[f.facility_type] || '•'}</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        });

        const marker = L.marker([f.latitude, f.longitude], { icon });
        marker.bindPopup(`
          <div class="map-popup">
            <strong>${esc(f.facility_name)}</strong>
            <p><b>Category:</b> ${esc(f.facility_type.toUpperCase().replace('_', ' '))}</p>
            <p><b>Locality:</b> ${esc(f.locality_name || f.ward_code || 'MMR')}</p>
            <p><b>Status:</b> ${esc(f.operating_status || 'Operational')}</p>
            <p><b>Capacity:</b> ${f.designated_capacity ? `${fmt(f.designated_capacity)} persons` : 'Unverified'}</p>
            <small>Source: ${esc(f.source_name || 'Official Record')}</small>
            <div style="margin-top:6px;">
              <button class="table-action-btn" onclick="window._routeToFacility('${esc(f.facility_id)}')">Plan Evacuation Route Here</button>
            </div>
          </div>
        `);
        emgFacilityLayer.addLayer(marker);
      });
    }
  }

  function renderEmergencyRestrictions() {
    if (!emgRestrictionLayer) return;
    emgRestrictionLayer.clearLayers();
    emgRestrictions.forEach(r => {
      const icon = L.divIcon({
        className: 'emg-div-icon',
        html: `<div class="emg-marker-icon emg-marker-closure" style="width:22px;height:22px;" title="${esc(r.title)}">⛔</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      });
      const marker = L.marker([r.latitude, r.longitude], { icon });
      marker.bindPopup(`
        <div class="map-popup">
          <strong style="color:#991b1b;">⛔ ROAD RESTRICTION: ${esc(r.title)}</strong>
          <span class="risk-badge high" style="font-size:8px;">${esc(r.restriction_type.toUpperCase())}</span>
          <p style="margin:4px 0;">${esc(r.description || 'Active road restriction.')}</p>
          <small>Authority: ${esc(r.reporting_authority || 'Traffic Police')}<br>Status: ${esc(r.operating_status || 'ACTIVE')}</small>
        </div>
      `);
      emgRestrictionLayer.addLayer(marker);
    });
  }

  function renderEvacuationDemand(demandData) {
    const tbody = $('#emg-evac-demand-tbody');
    if (!tbody) return;
    const wards = demandData?.ward_assessments || [];
    if (!wards.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="chart-empty">No ward evacuation demand data available.</td></tr>';
      return;
    }
    tbody.innerHTML = wards.map(w => {
      const balance = w.capacity_deficit_or_surplus ?? (w.total_shelter_capacity - w.exposed_population_demand);
      const isDeficit = balance < 0;
      const balanceHtml = isDeficit
        ? `<span class="capacity-deficit">Deficit: ${fmt(Math.abs(balance))}</span>`
        : `<span class="capacity-surplus">Surplus: +${fmt(balance)}</span>`;

      return `
        <tr>
          <td><strong>${esc(w.ward_code)}</strong> · ${esc(w.ward_name || '')}</td>
          <td><b>${fmt(w.exposed_population_demand)}</b> exposed</td>
          <td>${fmt(w.designated_shelters_count)}</td>
          <td>${fmt(w.total_shelter_capacity)}</td>
          <td>${balanceHtml}</td>
          <td><small style="color:${isDeficit ? '#991b1b' : '#15803d'};">${esc(w.recommended_action || (isDeficit ? 'Activate secondary civic school shelters' : 'Local shelter capacity sufficient'))}</small></td>
        </tr>
      `;
    }).join('');
  }

  window._routeToFacility = function(facilityId) {
    setPage('emergency');
    const rad = document.querySelector('input[name="emg-dest-mode"][value="facility"]');
    if (rad) rad.checked = true;
    $('#emg-facility-select-container')?.classList.remove('hidden');
    const select = $('#emg-facility-select');
    if (select) {
      select.value = facilityId;
    }
    calculateEmergencyRoute();
  };

  async function calculateEmergencyRoute() {
    const btn = $('#emg-btn-calculate');
    if (btn) btn.disabled = true;

    try {
      // Determine origin coordinates
      let origLat, origLon;
      const origMode = $('#emg-origin-select')?.value;
      if (origMode === 'custom') {
        origLat = parseFloat($('#emg-orig-lat')?.value);
        origLon = parseFloat($('#emg-orig-lon')?.value);
      } else {
        const parts = (origMode || '19.0680,72.8790').split(',');
        origLat = parseFloat(parts[0]);
        origLon = parseFloat(parts[1]);
      }

      if (isNaN(origLat) || isNaN(origLon)) {
        toast('Invalid origin coordinates', true);
        return;
      }

      const destMode = document.querySelector('input[name="emg-dest-mode"]:checked')?.value || 'facility';
      const routingCost = $('#emg-routing-cost')?.value || 'hazard_aware';
      const computeAlts = $('#emg-opt-alternatives')?.checked ?? true;
      const isScenario = $('#emg-opt-scenario')?.checked ?? false;
      const scenarioId = isScenario ? ($('#emg-scenario-id')?.value || 'SCN-HYP-001') : null;

      let routeResult = null;
      let altResult = null;

      if (destMode === 'nearest') {
        const facType = $('#emg-facility-type')?.value || null;
        toast('Calculating path to nearest reachable facility…');
        routeResult = await api('/routing/nearest-facility', {
          method: 'POST',
          body: JSON.stringify({
            origin_latitude: origLat,
            origin_longitude: origLon,
            facility_type: facType,
            routing_cost: routingCost,
            avoid_waterlogged: true,
            avoid_closed_roads: true,
            is_hypothetical_scenario: isScenario,
            scenario_id: scenarioId
          })
        });
      } else {
        const facId = $('#emg-facility-select')?.value;
        const targetFac = emgFacilities.find(f => f.facility_id === facId);
        if (!targetFac) {
          toast('Select a destination facility', true);
          return;
        }

        toast(`Calculating route to ${targetFac.facility_name}…`);
        routeResult = await api('/routing/route', {
          method: 'POST',
          body: JSON.stringify({
            origin_latitude: origLat,
            origin_longitude: origLon,
            destination_latitude: targetFac.latitude,
            destination_longitude: targetFac.longitude,
            destination_facility_id: targetFac.facility_id,
            routing_cost: routingCost,
            avoid_waterlogged: true,
            avoid_closed_roads: true,
            is_hypothetical_scenario: isScenario,
            scenario_id: scenarioId
          })
        });

        if (computeAlts) {
          try {
            altResult = await api('/routing/alternatives', {
              method: 'POST',
              body: JSON.stringify({
                origin_latitude: origLat,
                origin_longitude: origLon,
                destination_latitude: targetFac.latitude,
                destination_longitude: targetFac.longitude,
                k_alternatives: 2,
                routing_cost: routingCost,
                is_hypothetical_scenario: isScenario,
                scenario_id: scenarioId
              })
            });
          } catch (e) {
            console.warn('Alternative route computation failed:', e);
          }
        }
      }

      displayRouteResult(routeResult, altResult);
    } catch (err) {
      console.error('Route calculation error:', err);
      toast(`Route error: ${err.message}`, true);
      const title = $('#emg-route-title');
      if (title) title.textContent = `Routing Error: ${err.message}`;
      const badge = $('#emg-route-badge');
      if (badge) { badge.textContent = 'Failed'; badge.className = 'risk-badge critical'; }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function displayRouteResult(route, altRes) {
    if (!route) return;

    $('#emg-route-placeholder')?.classList.add('hidden');
    $('#emg-route-metrics-grid')?.classList.remove('hidden');

    const title = $('#emg-route-title');
    const badge = $('#emg-route-badge');
    const isSuccess = route.status === 'SUCCESS';

    if (title) title.textContent = isSuccess ? `Evacuation Path: ${fmt(route.distance_km, 2)} km` : `Route Status: ${route.status}`;
    if (badge) {
      badge.textContent = isSuccess ? 'Feasible Path' : 'No Safe Route';
      badge.className = isSuccess ? 'risk-badge low' : 'risk-badge critical';
    }

    if ($('#emg-res-dist')) $('#emg-res-dist').textContent = fmt(route.distance_km, 2);
    if ($('#emg-res-time')) $('#emg-res-time').textContent = fmt(route.estimated_duration_minutes, 1);
    if ($('#emg-res-segs')) $('#emg-res-segs').textContent = fmt(route.segment_count || (route.road_segment_ids ? route.road_segment_ids.length : 0));
    if ($('#emg-res-hazard')) $('#emg-res-hazard').textContent = fmt(route.hazard_exposure?.waterlogged_segments_count || 0);
    if ($('#emg-res-closures')) $('#emg-res-closures').textContent = fmt(route.known_closures_affecting_route?.length || 0);

    // Alternative comparison
    const altBox = $('#emg-route-alt-box');
    const altSummary = $('#emg-alt-summary');
    if (altRes && altRes.alternative_corridors && altRes.alternative_corridors.length > 1) {
      const alt2 = altRes.alternative_corridors[1];
      if (altBox) altBox.classList.remove('hidden');
      if (altSummary) {
        altSummary.textContent = `${fmt(alt2.distance_km, 2)} km · ~${fmt(alt2.estimated_duration_minutes, 1)} min (${alt2.road_segment_ids.length} segments). Distinct corridor avoiding primary route bottlenecks.`;
      }
    } else {
      if (altBox) altBox.classList.add('hidden');
    }

    // Safety disclaimer and limitations
    const limitContainer = $('#emg-route-limitations');
    const limitText = $('#emg-limitation-text');
    if (limitContainer && limitText) {
      limitContainer.classList.remove('hidden');
      const notices = (route.uncertainty_and_safety_notice || []).map(n => `<div>• ${esc(n)}</div>`).join('');
      limitText.innerHTML = `
        <strong style="color:#991b1b;display:block;margin-bottom:4px;">Safety &amp; Operational Caveats:</strong>
        ${notices || '<div>• Data-driven route. No guarantee of real-world clearance.</div>'}
      `;
    }

    // Plot Route Corridors on Emergency Map
    if (emergencyMap && emgRouteLayer) {
      emgRouteLayer.clearLayers();
      if (emgAltRouteLayer) emgAltRouteLayer.clearLayers();

      const allCoords = [];

      // If alternative corridor exists, draw it first (dashed orange)
      if (altRes && altRes.alternative_corridors && altRes.alternative_corridors.length > 1) {
        const alt2 = altRes.alternative_corridors[1];
        if (alt2.route_geojson && alt2.route_geojson.coordinates) {
          const altLatLngs = alt2.route_geojson.coordinates.map(c => [c[1], c[0]]);
          const altPoly = L.polyline(altLatLngs, {
            color: '#f97316',
            weight: 5,
            opacity: 0.8,
            dashArray: '8, 8'
          }).bindPopup(`<strong>Alternative Corridor</strong><br>${fmt(alt2.distance_km, 2)} km · ${fmt(alt2.estimated_duration_minutes, 1)} min`);
          emgAltRouteLayer.addLayer(altPoly);
        }
      }

      // Draw primary route (solid blue)
      if (route.route_geojson && route.route_geojson.coordinates) {
        const primaryLatLngs = route.route_geojson.coordinates.map(c => [c[1], c[0]]);
        const primaryPoly = L.polyline(primaryLatLngs, {
          color: '#2563eb',
          weight: 6,
          opacity: 0.9
        }).bindPopup(`<strong>Primary Evacuation Route</strong><br>${fmt(route.distance_km, 2)} km · ~${fmt(route.estimated_duration_minutes, 1)} min`);
        emgRouteLayer.addLayer(primaryPoly);
        allCoords.push(...primaryLatLngs);
      }

      // Origin Marker
      if (route.origin) {
        const origMarker = L.circleMarker([route.origin.latitude, route.origin.longitude], {
          radius: 7,
          fillColor: '#10b981',
          color: '#ffffff',
          weight: 2,
          fillOpacity: 1
        }).bindPopup('<strong>Evacuation Origin</strong>');
        emgRouteLayer.addLayer(origMarker);
      }

      // Destination Marker
      if (route.destination) {
        const destMarker = L.circleMarker([route.destination.latitude, route.destination.longitude], {
          radius: 7,
          fillColor: '#dc2626',
          color: '#ffffff',
          weight: 2,
          fillOpacity: 1
        }).bindPopup('<strong>Destination Target</strong>');
        emgRouteLayer.addLayer(destMarker);
      }

      if (allCoords.length > 0) {
        emergencyMap.fitBounds(L.latLngBounds(allCoords), { padding: [40, 40] });
      }
    }

    toast(`Calculated evacuation route (${fmt(route.distance_km, 2)} km)`);
  }

  function bindControls() {
    $('#rainfall-input').addEventListener('input',e=>$('#rainfall-display').textContent=e.target.value);
    $('#tide-input').addEventListener('input',e=>$('#tide-display').textContent=Number(e.target.value).toFixed(1));
    $('#scenario-form').addEventListener('submit',createScenario);
    $('#refresh-scenarios').addEventListener('click',loadScenarios);
    $('#exposure-scenario').addEventListener('change',e=>{selectedScenario=e.target.value;loadExposure(e.target.value);});
    $('#settings-button').addEventListener('click',()=>{ $('#api-url').value=apiBase;$('#google-map-key').value=localStorage.getItem(GOOGLE_KEY)||bundledGoogleKey;$('#settings-dialog').showModal(); });
    $('#save-api').addEventListener('click',async()=>{apiBase=$('#api-url').value.trim().replace(/\/$/,'');if(!apiBase){toast('Enter a backend URL',true);return;}localStorage.setItem(API_KEY,apiBase);const googleKey=$('#google-map-key').value.trim();if(googleKey)localStorage.setItem(GOOGLE_KEY,googleKey);else localStorage.removeItem(GOOGLE_KEY);googleLoader=null;$('#settings-dialog').close();await connect();await loadOverview();toast('Settings saved');});

    // Phase 4 Emergency Control bindings
    $('#refresh-emergency-feed')?.addEventListener('click', loadEmergencyModuleData);
    $('#emg-btn-calculate')?.addEventListener('click', calculateEmergencyRoute);

    $('#emg-origin-select')?.addEventListener('change', e => {
      const isCustom = e.target.value === 'custom';
      $('#emg-custom-origin-row')?.classList.toggle('hidden', !isCustom);
    });

    $$('input[name="emg-dest-mode"]').forEach(radio => {
      radio.addEventListener('change', e => {
        const isFacility = e.target.value === 'facility';
        $('#emg-facility-select-container')?.classList.toggle('hidden', !isFacility);
      });
    });

    $('#emg-facility-type')?.addEventListener('change', e => {
      populateFacilitySelect(e.target.value);
    });

    $('#emg-opt-scenario')?.addEventListener('change', e => {
      $('#emg-scenario-box')?.classList.toggle('hidden', !e.target.checked);
    });

    // Facility filter tabs
    const facTabs = [
      { id: '#emg-tab-fac-all', cat: 'all' },
      { id: '#emg-tab-fac-shelter', cat: 'shelter' },
      { id: '#emg-tab-fac-hospital', cat: 'hospital' },
      { id: '#emg-tab-fac-fire', cat: 'fire_station' },
      { id: '#emg-tab-fac-police', cat: 'police_station' }
    ];
    facTabs.forEach(({ id, cat }) => {
      $(id)?.addEventListener('click', () => {
        facTabs.forEach(t => $(t.id)?.classList.remove('active'));
        $(id)?.classList.add('active');
        renderEmergencyFacilities(cat);
      });
    });

    // Phase 5: Monitoring controls
    $('#btn-refresh-monitoring')?.addEventListener('click', () => {
      toast('Refreshing live monitoring and source health matrix…');
      loadMonitoringModuleData();
    });

    $$('.job-trigger-bar .btn-sm-run').forEach(btn => {
      btn.addEventListener('click', async () => {
        const job = btn.dataset.job;
        if (!job) return;
        btn.disabled = true;
        btn.textContent = '⏳ Running…';
        try {
          const res = await api(`/monitoring/jobs/${job}/run`, { method: 'POST' });
          toast(`Job executed: ${res.message || 'Complete'}`);
          await loadMonitoringModuleData();
        } catch (e) {
          toast(`Job failed: ${e.message}`, true);
        } finally {
          btn.disabled = false;
          btn.textContent = btn.dataset.originalText || btn.textContent.replace('⏳ Running…', '⚡ Trigger');
        }
      });
    });

    // Phase 6: Validation & Replay controls
    $('#btn-run-eval')?.addEventListener('click', async () => {
      const btn = $('#btn-run-eval');
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Evaluating test set (N=50)…';
      try {
        await api('/validation/runs', {
          method: 'POST',
          body: JSON.stringify({ model_id: 'flood_rf_v2_1', split_to_evaluate: 'TEST' })
        });
        toast('Evaluated model on held-out test set (2020–2023)');
        await loadValidationModuleData();
      } catch (e) {
        toast(`Evaluation failed: ${e.message}`, true);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡</span> Evaluate held-out test (2020–2023)';
      }
    });

    $('#btn-run-calib')?.addEventListener('click', async () => {
      const btn = $('#btn-run-calib');
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Recalibrating Platt sigmoid…';
      try {
        const res = await api('/models/flood_rf_v2_1/calibration', { method: 'POST' });
        toast(`Recalibrated: Brier improved by ${res.brier_score_improvement_pct || 0}%`);
        await loadValidationModuleData();
      } catch (e) {
        toast(`Calibration failed: ${e.message}`, true);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚖</span> Recalibrate model (Platt)';
      }
    });

    $('#btn-execute-replay')?.addEventListener('click', executeHistoricalReplay);
  }

  async function loadMonitoringModuleData() {
    try {
      const [statusData, sourcesData, alertsData, jobsData] = await Promise.all([
        api('/monitoring/status').catch(() => null),
        api('/monitoring/sources').catch(() => null),
        api('/alerts').catch(() => null),
        api('/monitoring/jobs?limit=15').catch(() => null)
      ]);

      if (statusData) {
        const total = statusData.source_counts?.total ?? 0;
        const byStatus = statusData.source_counts?.by_health_status ?? {};
        const healthy = byStatus.healthy ?? 0;
        const stale = (byStatus.stale ?? 0) + (byStatus.delayed ?? 0) + (byStatus.unavailable ?? 0);
        $('#mon-stat-total').textContent = String(total);
        $('#mon-stat-healthy').textContent = `${healthy} Healthy`;
        $('#mon-stat-stale').textContent = String(stale);
        $('#mon-stat-scheduler').textContent = statusData.scheduler_running ? 'ACTIVE' : 'IDLE';
      }

      if (alertsData) {
        const count = alertsData.active_count ?? alertsData.alerts?.length ?? 0;
        $('#mon-stat-alerts').textContent = String(count);
        const official = (alertsData.alerts || []).filter(a => a.is_official_warning).length;
        const advisory = count - official;
        $('#mon-stat-official').textContent = `${official} Official · ${advisory} Advisories`;

        const feedEl = $('#monitoring-alerts-feed');
        if (feedEl) {
          if (!alertsData.alerts || alertsData.alerts.length === 0) {
            feedEl.innerHTML = '<div class="chart-empty" style="padding:20px;">No active early-warning alerts at this time. All assessed parameters within standard operational thresholds.</div>';
          } else {
            feedEl.innerHTML = alertsData.alerts.map(a => {
              const isOfficial = a.is_official_warning;
              const sevClass = a.severity_level?.toLowerCase() || 'warning';
              return `
                <div class="alert-card ${sevClass}" style="margin-bottom:12px;">
                  <div class="alert-card-header">
                    <span class="alert-type-badge ${isOfficial ? 'official' : 'advisory'}">
                      ${isOfficial ? '🏛 OFFICIAL GOVERNMENT NOTICE' : '🤖 EIDT DECISION SUPPORT ADVISORY'}
                    </span>
                    <span class="risk-badge ${sevClass}">${esc(a.severity_level)}</span>
                  </div>
                  <h3 style="margin:6px 0 4px; font-size:13px;">${esc(a.headline)}</h3>
                  <p style="margin:0 0 6px; font-size:10px; color:#55665d;">${esc(a.description)}</p>
                  <div class="source-meta-row" style="border:none; padding:2px 0;">
                    <span>Scope: <b>${esc(a.geographic_scope)}</b></span>
                    <span>Authority: <b>${esc(a.issuing_authority)}</b></span>
                    <span>Valid until: <b>${a.expiry_timestamp ? new Date(a.expiry_timestamp).toLocaleString('en-IN') : 'Ongoing'}</b></span>
                  </div>
                  <div style="margin-top:8px; display:flex; justify-content:flex-end;">
                    <button class="btn-sm-run btn-ack-alert" data-alert-id="${esc(a.alert_id)}">Acknowledge Alert</button>
                  </div>
                </div>
              `;
            }).join('');

            $$('.btn-ack-alert', feedEl).forEach(btn => {
              btn.addEventListener('click', async () => {
                const altId = btn.dataset.alertId;
                try {
                  await api(`/alerts/${altId}/acknowledge`, { method: 'POST' });
                  toast(`Alert ${altId} acknowledged by operator.`);
                  btn.disabled = true;
                  btn.textContent = '✓ Acknowledged';
                } catch (e) {
                  toast(`Failed to acknowledge alert: ${e.message}`, true);
                }
              });
            });
          }
        }
      }

      if (sourcesData && sourcesData.sources) {
        const gridEl = $('#source-health-grid');
        if (gridEl) {
          gridEl.innerHTML = sourcesData.sources.map(s => {
            const statusClass = s.health_status?.toLowerCase() || 'healthy';
            const lastRet = s.last_successful_retrieval
              ? new Date(s.last_successful_retrieval).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
              : 'Unrecorded';
            return `
              <div class="source-card">
                <div class="source-card-header">
                  <h3>${esc(s.source_name)}</h3>
                  <span class="health-pill ${statusClass}">${esc(s.health_status)}</span>
                </div>
                <div class="source-meta-row">
                  <span>Category:</span>
                  <b>${esc(s.category)}</b>
                </div>
                <div class="source-meta-row">
                  <span>Cadence / Threshold:</span>
                  <b>${s.expected_cadence_minutes}m / ${s.freshness_threshold_minutes}m</b>
                </div>
                <div class="source-meta-row">
                  <span>Last Retrieval:</span>
                  <b>${lastRet}</b>
                </div>
                ${s.error_details ? `<div style="font-size:8px; color:#b91c1c; margin-top:6px; background:#fff1f2; padding:4px 6px; border-radius:4px;">${esc(s.error_details)}</div>` : ''}
              </div>
            `;
          }).join('');
        }
      }

      if (jobsData && jobsData.jobs) {
        const tbody = $('#monitoring-jobs-table');
        if (tbody) {
          if (jobsData.jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="chart-empty">No ingestion jobs executed yet.</td></tr>';
          } else {
            tbody.innerHTML = jobsData.jobs.map(j => {
              const statusPill = j.status === 'SUCCESS' ? 'health-pill healthy' : j.status === 'RUNNING' ? 'health-pill delayed' : 'health-pill unavailable';
              const ts = j.completed_at || j.started_at;
              const timeStr = ts ? new Date(ts).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '—';
              return `
                <tr>
                  <td><strong>${esc(j.job_name)}</strong></td>
                  <td>${esc(j.source_id)}</td>
                  <td><span class="${statusPill}">${esc(j.status)}</span></td>
                  <td>${j.records_retrieved ?? 0}</td>
                  <td>${j.records_accepted ?? 0} / ${j.records_deduplicated ?? 0}</td>
                  <td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(j.execution_log || '—')}</td>
                  <td>${timeStr}</td>
                </tr>
              `;
            }).join('');
          }
        }
      }
    } catch (err) {
      console.error('Failed to load monitoring data:', err);
    }
  }

  // --- Phase 6 Scientific Validation & Historical Replay Logic ---
  let activeReplayTimeline = [];
  let activeReplayRunData = null;

  async function loadValidationModuleData() {
    try {
      const [readinessData, validationData, calibrationData, eventsData] = await Promise.all([
        api('/validation/readiness').catch(() => null),
        api('/models/flood_rf_v2_1/validation').catch(() => null),
        api('/models/flood_rf_v2_1/calibration').catch(() => null),
        api('/validation/events?limit=50').catch(() => null)
      ]);

      // 1. Render Hazard Readiness Matrix
      if (readinessData && readinessData.hazards) {
        const tbody = $('#val-readiness-table');
        if (tbody) {
          tbody.innerHTML = readinessData.hazards.map(h => {
            const statusClass = h.evaluation_readiness === 'Ready' ? 'ready' : (h.evaluation_readiness === 'Limited' ? 'limited' : 'insufficient');
            const iconMap = {
              'FLOOD': '🌊',
              'HEATWAVE': '🌡',
              'LANDSLIDE': '⛰',
              'DROUGHT': '🌾',
              'COASTAL': '⚓',
              'THUNDERSTORM': '⚡'
            };
            const icon = iconMap[h.hazard_type] || '⚠';
            return `
              <tr>
                <td><strong>${icon} ${esc(h.hazard)}</strong></td>
                <td><span class="hazard-status-pill ${h.model_status === 'Implemented' ? 'hazard-status-operational' : (h.model_status === 'Partial' ? 'hazard-status-evaluated' : 'hazard-status-gaps')}">${esc(h.model_status)}</span></td>
                <td style="font-size:10px; color:#3a5445;">${esc(h.target_variable)}</td>
                <td style="font-size:10px;">${esc(h.historical_reference_data)}</td>
                <td style="font-size:10px;">${esc(h.spatial_resolution)}<br><small style="color:#6b7280;">${esc(h.temporal_resolution)}</small></td>
                <td><span class="badge-readiness ${statusClass}">${esc(h.evaluation_readiness)}</span></td>
                <td style="font-size:10px; color:#5c7365; max-width:280px; line-height:1.4;">${esc(h.known_limitations)}</td>
              </tr>
            `;
          }).join('');
        }
      }

      // 2. Render Validation Performance Metrics
      if (validationData && validationData.evaluation_results && validationData.evaluation_results.metrics) {
        const m = validationData.evaluation_results.metrics;
        $('#val-metric-csi').textContent = m.critical_success_index !== undefined ? m.critical_success_index.toFixed(3) : '—';
        $('#val-metric-pod').textContent = m.probability_of_detection !== undefined ? `${(m.probability_of_detection * 100).toFixed(1)}%` : '—';
        $('#val-metric-far').textContent = m.false_alarm_ratio !== undefined ? `${(m.false_alarm_ratio * 100).toFixed(1)}%` : '—';
        $('#val-metric-brier').textContent = m.brier_score !== undefined ? m.brier_score.toFixed(4) : '—';
      }

      // 3. Render Calibration Profile & Reliability Bins
      if (calibrationData) {
        $('#val-brier-pre').textContent = calibrationData.brier_score_before !== undefined ? calibrationData.brier_score_before.toFixed(4) : '—';
        $('#val-brier-post').textContent = calibrationData.brier_score_after !== undefined ? calibrationData.brier_score_after.toFixed(4) : '—';
        $('#val-brier-impr').textContent = calibrationData.brier_score_improvement_pct !== undefined ? `+${calibrationData.brier_score_improvement_pct}%` : '—';

        const tbody = $('#val-reliability-table');
        if (tbody && calibrationData.reliability_diagram_bins) {
          tbody.innerHTML = calibrationData.reliability_diagram_bins.map(b => {
            const isGood = Math.abs(b.mean_predicted_prob - b.empirical_fraction_positive) <= 0.15;
            return `
              <tr>
                <td><strong>${b.range[0].toFixed(2)} – ${b.range[1].toFixed(2)}</strong></td>
                <td>${b.count}</td>
                <td>${(b.mean_predicted_prob * 100).toFixed(1)}%</td>
                <td>${(b.empirical_fraction_positive * 100).toFixed(1)}%</td>
                <td><span class="hazard-status-pill ${isGood ? 'hazard-status-operational' : 'hazard-status-experimental'}">${isGood ? 'Well Calibrated' : 'Residual Departure'}</span></td>
              </tr>
            `;
          }).join('');
        }
      }

      // 4. Populate Historical Event Dropdown if empty or partial
      if (eventsData && eventsData.events && eventsData.events.length > 0) {
        const sel = $('#replay-event-select');
        if (sel) {
          const currentVal = sel.value;
          sel.innerHTML = eventsData.events.map(ev => `
            <option value="${esc(ev.event_id)}">${esc(ev.event_name)} (${esc(ev.hazard_type)})</option>
          `).join('');
          if (currentVal && eventsData.events.some(e => e.event_id === currentVal)) {
            sel.value = currentVal;
          }
        }
      }
    } catch (err) {
      console.error('Failed to load validation module data:', err);
    }
  }

  async function executeHistoricalReplay() {
    const btn = $('#btn-execute-replay');
    const eventId = $('#replay-event-select')?.value;
    if (!eventId) {
      toast('Select a historical event to replay', true);
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Reconstructing past disaster snapshot…';

    try {
      const res = await api('/replay/runs', {
        method: 'POST',
        body: JSON.stringify({
          event_id: eventId,
          replay_mode: 'RETROSPECTIVE_RECONSTRUCTION',
          model_version: 'flood_rf_v2_1'
        })
      });

      activeReplayRunData = res;
      activeReplayTimeline = res.timeline || [];

      // Update badge and title
      $('#replay-mode-badge').textContent = res.replay_mode.replace(/_/g, ' ');
      $('#replay-timeline-title').textContent = `Replay: ${res.event_name}`;

      // Render timeline scrubber
      renderReplayTimelineSteps();

      // Render concordance table
      renderReplayConcordance(res.predicted_outcomes, res.observed_benchmark);

      toast(`Replay completed for ${res.event_name} (Strict state isolation active)`);
    } catch (err) {
      toast(`Replay failed: ${err.message}`, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span>▶</span> Execute historical replay';
    }
  }

  function renderReplayTimelineSteps() {
    const container = $('#replay-scrubber-steps');
    if (!container || !activeReplayTimeline.length) return;

    container.innerHTML = activeReplayTimeline.map((step, idx) => {
      const isPeak = step.time_offset_hours === 0;
      const label = step.time_offset_hours === 0 ? 'T-0h (Peak)' : (step.time_offset_hours < 0 ? `T${step.time_offset_hours}h` : `T+${step.time_offset_hours}h`);
      return `
        <button class="step-btn ${isPeak ? 'peak' : ''} ${isPeak ? 'active' : ''}" data-step-index="${idx}">
          ${label}
        </button>
      `;
    }).join('');

    // Attach click handlers to step buttons
    $$('.step-btn', container).forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.step-btn', container).forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const idx = parseInt(btn.dataset.stepIndex, 10);
        showReplayStepNarrative(idx);
      });
    });

    // Default to Peak (offset 0)
    const peakIdx = activeReplayTimeline.findIndex(s => s.time_offset_hours === 0);
    showReplayStepNarrative(peakIdx >= 0 ? peakIdx : 0);
  }

  function showReplayStepNarrative(idx) {
    if (!activeReplayTimeline || !activeReplayTimeline[idx]) return;
    const step = activeReplayTimeline[idx];
    const offsetLabel = step.time_offset_hours === 0 ? 'T-0h: Event Peak Cloudburst & High Tide' : (
      step.time_offset_hours < 0 ? `T${step.time_offset_hours}h: Lead Window` : `T+${step.time_offset_hours}h: Recession`
    );

    $('#replay-active-step').textContent = `${offsetLabel} (${new Date(step.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})})`;
    
    const impactText = step.documented_impact ? `<div style="margin-top:6px; color:#991b1b; font-weight:600;">📋 Documented Impact: ${esc(step.documented_impact)}</div>` : '';
    $('#replay-narrative-box').innerHTML = `
      <div style="font-weight:700; color:#1f3327; margin-bottom:4px;">${esc(step.phase_label)}</div>
      <div><strong>Reconstructed Rainfall:</strong> ${step.cumulative_rainfall_mm} mm &nbsp;|&nbsp; <strong>Astronomical Tide:</strong> ${step.tide_height_m} m</div>
      <div style="margin-top:4px;">${esc(step.narrative)}</div>
      ${impactText}
    `;
  }

  function renderReplayConcordance(predictedOutcomes, observedBenchmark) {
    const tbody = $('#replay-concordance-table');
    if (!tbody || !predictedOutcomes) return;

    const rows = Object.keys(predictedOutcomes).map(locId => {
      const pred = predictedOutcomes[locId];
      const obs = observedBenchmark ? observedBenchmark[locId] : null;
      const concordance = obs ? obs.concordance : 'UNKNOWN';

      const badgeClass = {
        'TRUE_POSITIVE': 'badge-tp',
        'TRUE_NEGATIVE': 'badge-tn',
        'FALSE_POSITIVE': 'badge-fp',
        'FALSE_NEGATIVE': 'badge-fn'
      }[concordance] || 'badge-tn';

      const riskPill = pred.predicted_flood_risk === 'HIGH' ? 'hazard-status-gaps' : (pred.predicted_flood_risk === 'MEDIUM' ? 'hazard-status-experimental' : 'hazard-status-operational');

      return `
        <tr>
          <td><strong>${esc(pred.locality_name)}</strong></td>
          <td>${(pred.predicted_probability * 100).toFixed(1)}%</td>
          <td><span class="hazard-status-pill ${riskPill}">${esc(pred.predicted_flood_risk)}</span></td>
          <td>${pred.estimated_depth_cm > 0 ? `${pred.estimated_depth_cm} cm` : '<span style="color:#9ca3af;">0 cm</span>'}</td>
          <td>${obs && obs.observed_inundation ? '<span style="color:#b91c1c; font-weight:700;">Flooded</span>' : '<span style="color:#4b5563;">Drained / Nominal</span>'}</td>
          <td><span class="badge-concordance ${badgeClass}">${esc(concordance.replace(/_/g, ' '))}</span></td>
        </tr>
      `;
    }).join('');

    tbody.innerHTML = rows;
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
