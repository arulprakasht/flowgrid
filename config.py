# config.py

# === Redis Configuration ===
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# === Simulation Configuration ===
NUM_VEHICLES = 4
NUM_ORDERS = 4
GRID_SIZE = 20  # 20x20 = rough King County in miles
DEPOT = (10, 2)  # grid coordinates, adjust for SODO area

# === Map Configuration (Seattle Center) ===
SEATTLE_CENTER = (-122.3301, 47.5952)  # SODO Seattle
GRID_MILES = 20
OSM_BASEMAP = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"

# === Vehicle Icon ===
TRUCK_ICON_URL = "https://cdn-icons-png.flaticon.com/512/616/616492.png"
