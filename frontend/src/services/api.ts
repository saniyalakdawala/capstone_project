// Frontend API Service client connecting to FastAPI backend
const API_BASE = "http://127.0.0.1:8000/api";

export interface StudyArea {
  study_area_id: string;
  name: string;
  administrative_level: string;
  geometry: any;
  area_sq_km: number;
  population: number;
  elevation_mean_m: number;
  source: string;
}

export interface WeatherSummary {
  study_area_id: string;
  latest_observation: {
    observation_id: string;
    timestamp: string;
    rainfall_mm: number;
    temperature_c: number;
    humidity: number;
    wind_speed: number;
    source: string;
    observation_type: string;
  };
  past_24h_rainfall_mm: number;
  rainfall_trend_7d: Array<{ date: string; rainfall_mm: number; type: string }>;
  forecast_next_24h_mm: number;
  alert_level: string;
}

export interface ScenarioResult {
  scenario_id: string;
  scenario_name: string;
  rainfall_total_mm: number;
  duration_hours: number;
  summary_metrics: {
    rainfall_total_mm: number;
    high_risk_area_sqkm: number;
    moderate_risk_area_sqkm: number;
    estimated_exposed_population: number;
    exposed_hospitals_count: number;
    exposed_schools_count: number;
    affected_road_segments_count: number;
    affected_road_length_km: number;
    accessibility_reduction_pct: number;
  };
  ward_breakdown?: Record<string, any>;
  uncertainty_metadata?: any;
}

export interface ModelMetrics {
  model_name: string;
  model_version: string;
  last_evaluated: string;
  metrics: {
    roc_auc: number;
    pr_auc: number;
    f1_score: number;
    precision: number;
    recall: number;
    iou_metric: number;
  };
  baseline_comparison: {
    baseline_model: string;
    baseline_roc_auc: number;
    baseline_f1: number;
    auc_gain_pct: number;
    f1_gain_pct: number;
  };
  feature_importance: Array<{ feature: string; importance: number; percentage: number }>;
  confusion_matrix: {
    true_negative: number;
    false_positive: number;
    false_negative: number;
    true_positive: number;
  };
  spatial_kfold_summary: {
    method: string;
    mean_spatial_auc: number;
    spatial_auc_std: number;
    notes: string;
  };
  scientific_limitations: string[];
}

export interface PipelineStatus {
  pipeline_name: string;
  last_run_timestamp: string;
  total_connectors: number;
  sources: Array<{
    source_id: string;
    name: string;
    provider: string;
    license: string;
    spatial_resolution: string;
    temporal_revisit: string;
    auth_required: boolean;
    credentials_needed: string[];
    operational_status: string;
    last_run_status: string;
    records_ingested: number;
    is_demo_fallback: boolean;
    details: string;
  }>;
}

export const fetchHealth = async () => {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
};

export const fetchStudyAreas = async () => {
  const res = await fetch(`${API_BASE}/study-areas`);
  return res.json();
};

export const fetchStudyAreasGeoJSON = async () => {
  const res = await fetch(`${API_BASE}/study-areas/geojson`);
  return res.json();
};

export const fetchWeatherSummary = async (wardId: string = "MUM_WARD_L_KURLA") => {
  const res = await fetch(`${API_BASE}/weather?study_area_id=${wardId}`);
  return res.json();
};

export const fetchInfrastructureGeoJSON = async (type?: string) => {
  const url = type ? `${API_BASE}/infrastructure/geojson?feature_type=${type}` : `${API_BASE}/infrastructure/geojson`;
  const res = await fetch(url);
  return res.json();
};

export const fetchRoadsGeoJSON = async () => {
  const res = await fetch(`${API_BASE}/infrastructure/roads/geojson`);
  return res.json();
};

export const fetchWaterwaysGeoJSON = async () => {
  const res = await fetch(`${API_BASE}/infrastructure/waterways/geojson`);
  return res.json();
};

export const fetchOSMStatus = async () => {
  const res = await fetch(`${API_BASE}/infrastructure/osm/status`);
  return res.json();
};

export const fetchRiskMapGeoJSON = async (scenarioId: string = "SCEN_HEAVY_200MM") => {
  const res = await fetch(`${API_BASE}/risk-map?scenario_id=${scenarioId}`);
  return res.json();
};

export const fetchFloodEventsGeoJSON = async () => {
  const res = await fetch(`${API_BASE}/flood-events/geojson`);
  return res.json();
};

export const fetchScenarios = async () => {
  const res = await fetch(`${API_BASE}/scenarios`);
  return res.json();
};

export const createScenario = async (payload: any) => {
  const res = await fetch(`${API_BASE}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
};

export const fetchExposureAnalytics = async (scenarioId: string = "SCEN_HEAVY_200MM") => {
  const res = await fetch(`${API_BASE}/analytics/exposure?scenario_id=${scenarioId}`);
  return res.json();
};

export const calculateEmergencyRoute = async (payload: {
  origin: [number, number];
  destination_facility_id?: string;
  scenario_id?: string;
  avoid_high_risk_roads?: boolean;
}) => {
  const res = await fetch(`${API_BASE}/analytics/accessibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
};

export const fetchModelMetrics = async (): Promise<ModelMetrics> => {
  const res = await fetch(`${API_BASE}/models/metrics`);
  return res.json();
};

export const fetchPipelineStatus = async (): Promise<PipelineStatus> => {
  const res = await fetch(`${API_BASE}/data-pipeline/status`);
  return res.json();
};

export const triggerPipeline = async (sourceId?: string) => {
  const url = sourceId ? `${API_BASE}/data-pipeline/trigger?source_id=${sourceId}` : `${API_BASE}/data-pipeline/trigger`;
  const res = await fetch(url, { method: "POST" });
  return res.json();
};
