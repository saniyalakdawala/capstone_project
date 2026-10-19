# Mumbai Flood Intelligence frontend

A lightweight frontend for the existing FastAPI backend. It does not change the backend or database.

## Run locally

1. Start the backend from the `backend` directory:

   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. In this directory, install the frontend development dependency and start Vite:

   ```bash
   npm install
   npm run dev
   ```

3. Open the URL printed by Vite (normally `http://127.0.0.1:5173`).

The page connects to `http://127.0.0.1:8000` by default. Use the gear button at the bottom of the sidebar to set another FastAPI address. Both maps include OpenStreetMap and Google Street, Satellite, and Terrain basemaps. OpenStreetMap works by default; Google basemaps require a Google Maps JavaScript API key with Maps JavaScript API enabled. The frontend reads `VITE_GOOGLE_MAPS_API_KEY` from the shared project `.env` file. If it is unset, add a key in the settings dialog. Browser keys are visible to users, so restrict the key to your website and Maps JavaScript API in Google Cloud. Map tiles, fonts, Leaflet, and the Google map plugin are loaded from public CDNs and need an internet connection.

## Included screens

- Overview with current weather, scenario exposure, ward estimates, and a risk map
- Map explorer with ward, road, waterway, and facility layers
- Scenario creation using the existing `/api/scenarios` endpoint
- Ward-level exposure details and model limitations
- Model metrics, feature importance, and the project's research questions
