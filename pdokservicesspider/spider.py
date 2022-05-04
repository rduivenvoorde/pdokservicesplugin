#!/usr/bin/env python3
import logging
import json
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import pprint
import re
from cv2 import sort
import requests
from copy import deepcopy
from owslib.csw import CatalogueServiceWeb
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from owslib.wfs import WebFeatureService
from owslib.wcs import WebCoverageService
import warnings


CSW_URL = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw"
LOG_LEVEL = "INFO"
PROTOCOLS = ["OGC:WMS", "OGC:WFS", "OGC:WMTS", "OGC:WCS"]
SORTING_RULES = {
    0: {"names": ["opentopo+"], "types": ["wmts"]},
    10: {"names": ["^actueel_orthohr$"], "types": ["wmts"]},
    11: {"names": ["^actueel_ortho25$"], "types": ["wmts"]},
    12: {"names": ["^actueel_ortho25ir$"], "types": ["wmts"]},
    13: {"names": ["lufolabels"], "types": ["wmts"]},
    # 15: {'names': ['^\d{4}_ortho'], 'types': ['wmts']},
    # 16: {'names': ['^\d{4}_ortho+IR'], 'types': ['wmts']},
    20: {
        "names": ["landgebied", "provinciegebied", "gemeentegebied"],
        "types": ["wfs"],
    },
    30: {"names": ["top+"], "types": ["wmts"]},
    32: {
        "names": ["^standaard$", "^grijs$", "^pastel$", "^water$"],
        "types": ["wmts"],
    },  # BRT-lagen
    34: {"names": ["bgtstandaardv2", "bgtachtergrond"], "types": ["wmts"]},
    60: {"names": ["ahn3+"], "types": ["wmts"]},
    # 90: {'names': ['aan+'], 'types': ['wmts']},
}


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s: %(message)s",
)


def get_sorting_value(layer_info):
    if not "name" in layer_info:
        return 101
    layer_name = layer_info["name"].lower()
    for key, sorting_rule in SORTING_RULES.items():
        if layer_info["type"].lower() in sorting_rule["types"]:
            for name in sorting_rule["names"]:
                if re.search(name, layer_name) is not None:
                    return key
    if layer_info["type"].lower() == "wmts":
        return 99  # other wmts layers
    else:
        return 100  # all other layers


def is_popular(service):
    if service["type"].lower() == "wmts":
        return True
    return False


def join_lists_by_property(list_1, list_2, prop_name):
    lst = sorted(itertools.chain(list_1, list_2), key=lambda x: x[prop_name])
    result = []
    for k, v in itertools.groupby(lst, key=lambda x: x[prop_name]):
        d = {}
        for dct in v:
            d.update(dct)
        result.append(d)
    return result


def get_csw_results(protocol, maxresults=0):
    csw = CatalogueServiceWeb(CSW_URL)
    svc_owner = "Beheer PDOK"
    query = (
        f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}'"
        # to be able to check specific services:
        # f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}' AND any='zeegras'"
    )
    md_ids = []
    start = 1
    maxrecord = maxresults if (maxresults < 100 and maxresults != 0) else 100

    while True:
        csw.getrecords2(maxrecords=maxrecord, cql=query, startposition=start)
        result = [{"mdId": rec, "protocol": protocol} for rec in csw.records]
        md_ids.extend(result)
        if (
            maxresults != 0 and len(result) >= maxresults
        ):  # break only early when maxresults set
            break
        if csw.results["nextrecord"] != 0:
            start = csw.results["nextrecord"]
            continue
        break
    logging.info(f"Found {len(md_ids)} {protocol} services")
    return md_ids


def get_record_by_id(md_id):
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[md_id])
    return csw.records[md_id]


def get_service_url(result):
    md_id = result["mdId"]
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[md_id])
    record = csw.records[md_id]
    uris = record.uris
    service_url = ""

    if len(uris) > 0:
        service_url = uris[0]["url"]
        service_url = service_url.split("?")[0]
        service_str = result["protocol"].split(":")[1]
        if (
            "https://geodata.nationaalgeoregister.nl/tiles/service/wmts" in service_url
        ):  # shorten paths, some wmts services have redundant path elements in service_url
            service_url = "https://geodata.nationaalgeoregister.nl/tiles/service/wmts"

        if service_url.endswith(
            "/WMTSCapabilities.xml"
        ):  # handle cases for restful wmts url, assume kvp variant is supported
            service_url = service_url.replace("/WMTSCapabilities.xml", "")

        service_url = f"{service_url}?request=GetCapabilities&service={service_str}"
    else:
        error_message = (
            f"expected at least 1 service url in service record {md_id}, found 0"
        )
        logging.error(error_message)
    return {"mdId": md_id, "url": service_url}


async def get_data_asynchronous(results, fun):
    result = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                fun,
                *(in_result,),
            )
            for in_result in results
        ]
        for task_result in await asyncio.gather(*tasks):
            result.append(task_result)
        return result


def get_cap(result):
    function_mapping = {
        "OGC:WMS": get_wms_cap,
        "OGC:WFS": get_wfs_cap,
        "OGC:WCS": get_wcs_cap,
        "OGC:WMTS": get_wmts_cap,
    }
    result = function_mapping[result["protocol"]](result)
    return result


def get_wcs_cap(result):
    def convert_layer(lyr):
        return {"name": lyr, "title": wcs[lyr].title, "layers": wcs[lyr].id}

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(f"{md_id} - {url}")
        wcs = WebCoverageService(url, version="2.0.1")
        title = wcs.identification.title
        abstract = wcs.identification.abstract
        keywords = wcs.identification.keywords
        getcoverage_op = next(
            (x for x in wcs.operations if x.name == "GetCoverage"), None
        )
        result["formats"] = ",".join(getcoverage_op.formatOptions)
        layers = list(wcs.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"mdId: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WCS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wfs_cap(result):
    def convert_layer(lyr):
        return {"name": lyr, "title": wfs[lyr].title, "layers": wfs[lyr].id}

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(f"{md_id} - {url}")
        wfs = WebFeatureService(url, version="2.0.0")
        title = wfs.identification.title
        abstract = wfs.identification.abstract
        keywords = wfs.identification.keywords
        getfeature_op = next(
            (x for x in wfs.operations if x.name == "GetFeature"), None
        )
        result["formats"] = ",".join(getfeature_op.formatOptions)
        layers = list(wfs.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WFS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wms_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wms[lyr].title,
            "styles": list(wms[lyr].styles.keys())
            if len(list(wms[lyr].styles.keys())) > 0
            else "",
            "crs": ",".join([x[4] for x in wms[lyr].crs_list]),
            "minscale": wms[lyr].min_scale_denominator.text
            if wms[lyr].min_scale_denominator is not None
            else "",
            "maxscale": wms[lyr].max_scale_denominator.text
            if wms[lyr].max_scale_denominator is not None
            else "",
        }

    try:
        url = result["url"]
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return result
        md_id = result["mdId"]
        logging.info(f"{md_id} - {url}")
        wms = WebMapService(url, version="1.3.0")
        title = wms.identification.title
        abstract = wms.identification.abstract
        keywords = wms.identification.keywords
        getmap_op = next((x for x in wms.operations if x.name == "GetMap"), None)
        result["imgformats"] = ",".join(getmap_op.formatOptions)
        layers = list(wms.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WMS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wmts_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wmts[lyr].title,
            "tilematrixsets": ",".join(list(wmts[lyr].tilematrixsetlinks.keys())),
            "imgformats": ",".join(wmts[lyr].formats),
        }

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(f"{md_id} - {url}")
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return result
        wmts = WebMapTileService(url)
        title = wmts.identification.title
        abstract = wmts.identification.abstract
        keywords = wmts.identification.keywords
        layers = list(wmts.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"unexpected error occured while retrieving cap doc, md-identifier {md_id}, url: {url}"
        logging.exception(message)
    return result


def flatten_service(service):
    def flatten_layer_wms(layer):
        def flatten_styles(stylename):
            layer_copy = deepcopy(
                layer
            )  #  to prevent the same layer object to be modified each iteration
            fields = ["imgformats", "url"]  # fields not renamed
            for field in fields:
                layer_copy[field] = service[field]
            layer_copy["servicetitle"] = service["title"]
            layer_copy["type"] = service["protocol"].split(":")[1].lower()
            layer_copy["layers"] = layer_copy["name"]
            layer_copy["abstract"] = service["abstract"] if (not None) else ""
            layer_copy["md_id"] = service["mdId"]
            layer_copy["style"] = stylename
            layer_copy.pop("name", None)
            return layer_copy

        styles = layer["styles"]
        layer.pop("styles", None)
        return list(map(flatten_styles, styles))

    def flatten_layer_wcs(layer):
        fields = ["url"]
        for field in fields:
            layer[field] = service[field]
        layer["servicetitle"] = service["title"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["title"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer_wfs(layer):
        fields = ["url"]
        for field in fields:
            layer[field] = service[field]
        layer["servicetitle"] = service["title"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer_wmts(layer):
        layer["servicetitle"] = service["title"]
        layer["url"] = service["url"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer(layer):
        fun_mapping = {
            "OGC:WMS": flatten_layer_wms,
            "OGC:WFS": flatten_layer_wfs,
            "OGC:WCS": flatten_layer_wcs,
            "OGC:WMTS": flatten_layer_wmts,
        }
        return fun_mapping[service["protocol"]](layer)

    result = list(map(flatten_layer, service["layers"]))
    return result


def sort_service_layers(services):
    sorted_layer_dict = {}
    for service in services["services"]:
        sorting_value = get_sorting_value(service)
        if sorting_value in sorted_layer_dict:
            sorted_layer_dict[sorting_value].append(service)
        else:
            sorted_layer_dict[sorting_value] = [service]
    output_dict = {"services": []}
    for key in sorted(sorted_layer_dict.keys()):
        if len(sorted_layer_dict[key]) == 0:
            logging.info(f"no layers found for sorting rule: {SORTING_RULES[key]}")
        output_dict["services"] += sorted_layer_dict[key]
    return output_dict


def main(out_file, number_records, sort, pretty, protocols):
    if protocols:
        protocols = protocols.split(",")
    else:
        protocols = PROTOCOLS

    csw_results = list(
        map(
            lambda x: get_csw_results(x, number_records),
            protocols,
        )
    )
    csw_results = [
        item for sublist in csw_results for item in sublist
    ]  # flatten list of lists
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(get_data_asynchronous(csw_results, get_service_url))
    loop.run_until_complete(future)
    get_record_results = join_lists_by_property(csw_results, future.result(), "mdId")
    get_record_results = filter(
        lambda x: "url" in x and x["url"], get_record_results
    )  # filter out results without serviceurl

    # delete duplicate service entries, some service endpoint have multiple service records
    new_dict = dict()
    for obj in get_record_results:
        new_dict[obj["url"]] = obj

    get_record_results_filtered = [value for key, value in new_dict.items()]

    nr_services = len(get_record_results_filtered)

    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(
        get_data_asynchronous(get_record_results_filtered, get_cap)
    )
    loop.run_until_complete(future)
    cap_results = future.result()
    failed_services = list(filter(lambda x: "layers" not in x, cap_results))
    failed_svc_urls = map(lambda x: x["url"], failed_services)
    nr_failed_services = len(failed_services)
    cap_results = filter(
        lambda x: "layers" in x, cap_results
    )  # filter out services where getcap req failed
    config = list(map(flatten_service, cap_results))

    # each services returns as a list of layers, flatten list, see https://stackoverflow.com/a/953097
    config = [item for sublist in config for item in sublist]
    wms_layers = list(filter(lambda x: isinstance(x, list), config))
    config = list(filter(lambda x: isinstance(x, dict), config))
    # wms layers are nested one level deeper, due to exploding layers on styles
    wms_layers = [item for sublist in wms_layers for item in sublist]
    config.extend(wms_layers)
    nr_layers = len(config)

    services = {"services": config}
    if sort:
        logging.info(f"sorting services")
        services = sort_service_layers(services)

    with open(out_file, "w") as f:
        if pretty:
            json.dump(services, f, indent=4)
        else:
            json.dump(services, f)

    logging.info(f"indexed {nr_services} services with {nr_layers} layers")
    if nr_failed_services > 0:
        logging.info(f"failed to index {nr_failed_services} services")
        failed_svc_urls_str = "\n".join(failed_svc_urls)
        logging.info(f"failed service urls:\n{failed_svc_urls_str}")
    logging.info(f"output written to {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate XML against schema")
    parser.add_argument(
        "output_file", metavar="output-file", type=str, help="JSON output file"
    )
    parser.add_argument(
        "-n",
        "--number",
        action="store",
        type=int,
        default=0,
        help="nr of records to retrieve per service type",
    )
    parser.add_argument(
        "-p",
        "--protocols",
        action="store",
        type=str,
        default="",
        help="service type protocols to query, comma separated",
    )

    parser.add_argument(
        "--sort",
        action="store_true",
        help="sort service layers based on default sorting rules",
    )

    parser.add_argument(
        "--pretty", dest="pretty", action="store_true", help="pretty JSON output"
    )
    parser.add_argument(
        "--warnings",
        dest="show_warnings",
        action="store_true",
        help="show user warnings - owslib tends to show warnings about capabilities",
    )
    args = parser.parse_args()

    if args.show_warnings:
        main(args.output_file, args.number, args.sort, args.pretty, args.protocols)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            main(args.output_file, args.number, args.sort, args.pretty, args.protocols)
