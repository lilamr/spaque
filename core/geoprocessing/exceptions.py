"""
core/geoprocessing/exceptions.py
"""


class GeoprocessError(Exception):
    """Raised when a geoprocessing operation fails."""


class MissingLayerError(GeoprocessError):
    """Raised when a required input layer is not specified."""


class InvalidParameterError(GeoprocessError):
    """Raised when operation parameters are invalid."""


class UnsupportedGeometryError(GeoprocessError):
    """Raised when the operation doesn't support the layer's geometry type."""
