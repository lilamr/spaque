"""
utils/constants.py — App-wide constants
"""

# ── Geometry types ────────────────────────────────────────────────────────────
GEOM_ICONS = {
    "POINT": "📍",
    "MULTIPOINT": "📍",
    "LINESTRING": "〰",
    "MULTILINESTRING": "〰",
    "POLYGON": "🔷",
    "MULTIPOLYGON": "🔷",
    "GEOMETRY": "🌐",
    "GEOMETRYCOLLECTION": "🌐",
    "TABLE": "📋",
}

# ── Spatial predicates ────────────────────────────────────────────────────────
SPATIAL_PREDICATES = [
    "ST_Intersects",
    "ST_Contains",
    "ST_Within",
    "ST_Overlaps",
    "ST_Touches",
    "ST_Crosses",
    "ST_Covers",
    "ST_CoveredBy",
    "ST_Disjoint",
]

# ── Join types ────────────────────────────────────────────────────────────────
JOIN_TYPES = ["INNER", "LEFT OUTER", "RIGHT OUTER", "FULL OUTER"]

# ── Colormaps ─────────────────────────────────────────────────────────────────
COLORMAPS = [
    "viridis", "plasma", "inferno", "magma",
    "Blues", "Greens", "Reds", "Oranges", "Purples",
    "RdYlGn", "RdYlBu", "Spectral", "coolwarm",
    "tab10", "Set1", "Set2",
]

# ── Area unit divisors ────────────────────────────────────────────────────────
AREA_UNITS = {
    "m²": 1,
    "ha": 10_000,
    "km²": 1_000_000,
}

# ── Default EPSG codes ────────────────────────────────────────────────────────
COMMON_SRID = {
    "WGS 84 (EPSG:4326)": 4326,
    "Web Mercator (EPSG:3857)": 3857,
    "UTM Zone 47S (EPSG:32747)": 32747,
    "UTM Zone 48S (EPSG:32748)": 32748,
    "UTM Zone 49S (EPSG:32749)": 32749,
    "UTM Zone 50S (EPSG:32750)": 32750,
    "UTM Zone 51S (EPSG:32751)": 32751,
    "UTM Zone 47N (EPSG:32647)": 32647,
    "UTM Zone 48N (EPSG:32648)": 32648,
    "DGN95 (EPSG:4755)": 4755,
}

# ── Query operators ───────────────────────────────────────────────────────────
QUERY_OPERATORS = {
    "=":            "=",
    "≠":            "!=",
    ">":            ">",
    "≥":            ">=",
    "<":            "<",
    "≤":            "<=",
    "LIKE":         "LIKE",
    "NOT LIKE":     "NOT LIKE",
    "ILIKE":        "ILIKE",
    "NOT ILIKE":    "NOT ILIKE",
    "IS NULL":      "IS NULL",
    "IS NOT NULL":  "IS NOT NULL",
    "IN":           "IN",
    "NOT IN":       "NOT IN",
    "BETWEEN":      "BETWEEN",
    "NOT BETWEEN":  "NOT BETWEEN",
}

# ── SQL numeric types ─────────────────────────────────────────────────────────
NUMERIC_TYPES = {
    "integer", "bigint", "smallint", "numeric",
    "double precision", "real", "float", "decimal",
}

# ── Max preview rows ──────────────────────────────────────────────────────────
MAX_TABLE_ROWS = 5000
MAX_ATTRIBUTE_COLS_DISPLAY = 30
