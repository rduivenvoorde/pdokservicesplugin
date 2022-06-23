from enum import Enum
import json
from qgis.core import QgsWkbTypes
import urllib.parse
from osgeo import ogr

from .http_client import get_request_json

SERVICE_ENDPOINT = "https://geodata.nationaalgeoregister.nl/locatieserver/v3"
REV_SERVICE_ENDPOINT = "https://geodata.nationaalgeoregister.nl/locatieserver/v4"


class Projection(Enum):
    def __str__(self):
        return str(self.value)

    EPSG_4326 = "EPSG:4326"
    EPSG_28992 = "EPSG:28992"


proj_mapping = {
    Projection.EPSG_28992: "_rd",
    Projection.EPSG_4326: "_ll",
}


class LsType(Enum):
    adres = "adres"
    appartementsrecht = "appartementsrecht"
    buurt = "buurt"
    gemeente = "gemeente"
    hectometerpaal = "hectometerpaal"
    perceel = "perceel"
    postcode = "postcode"
    provincie = "provincie"
    weg = "weg"
    wijk = "wijk"
    waterschap = "waterschap"
    woonplaats = "woonplaats"

    def geom_type(self) -> QgsWkbTypes:
        geom_type_mapping = {
            "adres": QgsWkbTypes.Point,
            "appartementsrecht": QgsWkbTypes.MultiPoint,
            "buurt": QgsWkbTypes.MultiPolygon,
            "gemeente": QgsWkbTypes.MultiPolygon,
            "hectometerpaal": QgsWkbTypes.Point,
            "perceel": QgsWkbTypes.Polygon,
            "postcode": QgsWkbTypes.Point,
            "provincie": QgsWkbTypes.MultiPolygon,
            "weg": QgsWkbTypes.MultiLineString,
            "wijk": QgsWkbTypes.MultiPolygon,
            "waterschap": QgsWkbTypes.MultiPolygon,
            "woonplaats": QgsWkbTypes.MultiPolygon,
        }
        return geom_type_mapping[self.value]


class TypeFilter:
    # Default types requested, match default types of LS service, see:
    # https://github.com/PDOK/locatieserver/wiki/API-Locatieserver#31request-url
    default_types = [
        LsType.gemeente,
        LsType.woonplaats,
        LsType.weg,
        LsType.adres,
        LsType.postcode,
    ]

    def __init__(self, filter_types: "list[LsType]"):
        self.types: "list[LsType]" = filter_types

    @classmethod  # cls==self for class methods see https://stackoverflow.com/a/4795306/1763690
    def new_with_default_values(cls):
        "Initialize TypeFilter with default values"
        return cls(cls.default_types)

    def add_type(self, type: LsType):
        self.types.append(type)

    def __str__(self):
        filter_types_str = list(map(lambda x: x.value, self.types))
        filter_types_str = " OR ".join(filter_types_str)
        return urllib.parse.quote(f"type:({filter_types_str})")

    def rev_geo_filter(self):
        filter_types_str = list(map(lambda x: f"type={x.value}", self.types))
        return "&".join(filter_types_str)


def url_encode_query_string(query_string):
    return urllib.parse.quote(query_string)


def suggest_query(
    query,
    type_filter=TypeFilter.new_with_default_values(),
    rows=10,
) -> "list[dict]":
    """

    Returns list of dict with fields: type, weergavenaam, id score
    For example:
        {
            "type": "gemeente",
            "weergavenaam": "Gemeente Amsterdam",
            "id": "gem-0b2a8b92856b27f86fbd67ab35808ebf",
            "score": 19.91312
        }
    Raises PdokServicesNetworkException when request fails
    """
    if len(type_filter.types) == 0:
        return []
    # TODO: add fields filter, with fl=id,geometrie_ll/rd or *
    query = url_encode_query_string(query)
    query_string = f"q={query}&rows={rows}&fq={type_filter}"
    url = f"{SERVICE_ENDPOINT}/suggest?{query_string}"
    content_obj = get_request_json(url)
    result = content_obj["response"]["docs"]
    return result


def convert_to_geojson(result_item, proj: Projection):

    geom_name = get_the_geom(result_item, proj)
    wkt = result_item[geom_name]
    geom = ogr.CreateGeometryFromWkt(wkt)
    geojson = geom.ExportToJson()
    data = json.loads(geojson)
    result_item = process_geom_fields(result_item, proj)

    data["properties"] = {}
    for attr, value in result_item.items():
        data["properties"][attr] = value
    data["id"] = data["properties"]["id"]
    return data


def get_the_geom(result_item, proj):
    geom_suffix = proj_mapping[proj]
    geom_name = f"geometrie{geom_suffix}"
    result = {}
    if geom_name in result_item:
        result.update(
            {"wkt_geom": result_item[geom_name]}
        )  # Note: dict.update modifies IN place (no return value)
    centroid_name = f"centroide{geom_suffix}"
    result.update(
        {"wkt_centroid": result_item[centroid_name]}
    )  # Note: dict.update modifies IN place (no return value), see https://peps.python.org/pep-0584/
    return result


def remove_redundant_geom_fields(result_item, proj: Projection):
    for geom_type in ["centroide", "geometrie"]:
        for p in Projection:
            geom_suffix = proj_mapping[p]
            geom_name = f"{geom_type}{geom_suffix}"
            result_item.pop(geom_name, None)
    return result_item


def process_geom_fields(result_item, proj: Projection):
    geoms = get_the_geom(result_item, proj)
    result_item = remove_redundant_geom_fields(result_item, proj)
    result_item.update(geoms)  # Note: dict.update modifies IN place (no return value)
    return result_item


def free_query(
    query, proj: Projection, type_filter=TypeFilter.new_with_default_values(), rows=10
) -> "list[dict]":
    """
    Raises PdokServicesNetworkException when request fails
    """
    query = url_encode_query_string(query)
    query_string = f"q={query}&rows={rows}"
    url = f"{SERVICE_ENDPOINT}/free?{query_string}&fq={type_filter}"
    content_obj = get_request_json(url)

    result = content_obj["response"]["docs"]
    filter_result = [process_geom_fields(item, proj) for item in result]
    return filter_result


def reverse_lookup(
    x, y, fields, type_filter=TypeFilter.new_with_default_values()
) -> "list[dict]":
    """
    Reverse geocoder lookup, x and y coordinates in EPSG:28992

    Raises PdokServicesNetworkException when request fails
    """
    rev_geo_type_filter = type_filter.rev_geo_filter()
    fields_query_string = url_encode_query_string(",".join(fields))
    url = f"{REV_SERVICE_ENDPOINT}/revgeo/?X={x}&Y={y}&{rev_geo_type_filter}&fl={fields_query_string}"  # {rev_geo_type_filter}
    content_obj = get_request_json(url)
    result = content_obj["response"]["docs"]
    return result


def get_lookup_object_url(object_id: str) -> str:
    object_id = url_encode_query_string(object_id)
    query_string = f"id={object_id}&fl=*"  # return all fields with fl=*
    url = f"{SERVICE_ENDPOINT}/lookup?{query_string}"
    return url


def lookup_object(object_id: str, proj: Projection) -> dict:
    """
    Raises PdokServicesNetworkException when request fails
    """
    # TODO: add fields filter, with fl=id,geometrie_ll/rd or fl=*
    url = get_lookup_object_url(object_id)
    content_obj = get_request_json(url)
    if content_obj["response"]["numFound"] != 1:
        return None
    result = content_obj["response"]["docs"][0]
    filter_result = process_geom_fields(result, proj)
    return filter_result
