# config.py

# === Redis Configuration ===
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# === Simulation Configuration ===
NUM_VEHICLES = 5
NUM_ORDERS = 50
GRID_SIZE = 20  # 20x20 = rough King County in miles
DEPOT = (0, 0)

# === Map Configuration (Seattle Center) ===
SEATTLE_CENTER = (-122.335167, 47.608013)  # (longitude, latitude)
GRID_MILES = 20
OSM_BASEMAP = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"

# === Vehicle Icon ===
TRUCK_ICON_URL = "https://cdn-icons-png.flaticon.com/512/616/616492.png"
