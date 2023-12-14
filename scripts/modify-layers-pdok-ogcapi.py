#!/usr/bin/env python3
"""Modify/extend layers-pdok.json with OGC:API records for tiles/features from PDOK

This script allows the user to modify the layers-pdok.json file which is used in the
pdokservicesplugin. The records are generated in this script by requesting 
various API endpoints that are conform the OGC:API standards, especially useful when there are no
NGR-records for these OGC:API services.

To run this script, one has to provide one/multiple parameters. For the first parameter,
a mode should be provided: [ogcapi|original]
The remaining parameters should all be urls to landing pages of ogcapi's containing
either OGC:API tiles or OGC:API features sets.  

Run the following command from the root of the repository:
`python3 ./scripts/modify-layers-pdok-ogcapi.py ogcapi URL1 URL2`: Adds ogcapi test records to 
layers-pdok.json for tiles/features and creates a copy of the original file. Here, URL1 URL2 should be 
the landing pages of ogcapi endpoints that are publicly accesible containing tiles/features. At least one 
URL should be given as argument when using ogcapi mode to add records to layers-pdok.json.

`python3 ./scripts/modify-layers-pdok-ogcapi.py original`: Replaces layers-pdok.json 
with the copy file (containing the original .json file) and removes the copy.

"""

import argparse
import json
import os
import shutil
import requests
import sys
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

EMPTY = ""
API_FEATURES = "api features"
API_TILES = "api tiles"


def extend_layer_pdok_ogcapi(urls):
    ogcapi_records = []
    for landing_page in urls:
        try:
            landing_page_json = requests.get(landing_page).json()
            links = landing_page_json.get("links", [])
            visited_href = []
            for link in links:
                href = link.get("href", "")
                if href.endswith("tiles") and href not in visited_href:
                    visited_href.append(href)
                    ogcapi_records.append(
                        retrieve_layers_from_oat_endpoint(landing_page)
                    )
                if href.endswith("collections") and href not in visited_href:
                    visited_href.append(href)
                    ogcapi_records.extend(
                        retrieve_layers_from_oaf_endpoint(landing_page)
                    )
        except Exception as error:
            logger.info(
                f"There was an error requesting the url: {landing_page}. Either this url does not exists or raised an exception: {error}. We continue with the next url."
            )
            continue
    return ogcapi_records


def retrieve_layers_from_oat_endpoint(url):
    url_info = requests.get(url).json()
    dataset_title = url_info.get("title", url.split("/")[-1])
    tiles_info = requests.get(url + "/tiles").json()
    dataset_abstract = url_info.get("description", "Geen abstract gevonden")
    styles = requests.get(url + "/styles").json()
    tiles = requests.get(url + "/tiles").json()
    return {
        "name": dataset_title,
        "title": dataset_title,
        "abstract": dataset_abstract,
        "dataset_md_id": EMPTY,
        "styles": [
            {
                "id": style["id"],
                "name": style["title"],
                "url": next(
                    link["href"]
                    for link in style["links"]
                    if link["rel"] == "stylesheet"
                ),
            }
            for style in styles["styles"]
        ],
        "tiles": [
            {
                "title": tiles["title"],
                "abstract": tiles["description"],
                "tilesets": [
                    {
                        "tileset_id": tileset["tileMatrixSetId"],
                        "tileset_crs": tileset["crs"],
                        "tileset_max_zoomlevel": get_max_zoomlevel(
                            get_self_link(tileset["links"])
                        ),
                    }
                    for tileset in tiles["tilesets"]
                ],
            }
        ],
        "service_url": url,
        "service_title": tiles_info["title"],
        "service_abstract": tiles_info["description"],
        "service_type": API_TILES,
        "service_md_id": EMPTY,
    }


def get_self_link(links):
    for link in links:
        if link.get("rel") == "self":
            return link.get("href")
    return links[0].get("href")


def get_max_zoomlevel(tileset_url):
    tileset_info = requests.get(tileset_url).json()
    tile_matrix_limits = tileset_info.get("tileMatrixSetLimits", [])
    max_tile_matrix_zoom = max(
        (int(limit.get("tileMatrix")) for limit in tile_matrix_limits), default=None
    )
    return max_tile_matrix_zoom


def retrieve_layers_from_oaf_endpoint(url):
    url_info = requests.get(url).json()
    service_title = url_info["title"] if "title" in url_info else url.split("/")[-1]
    service_abstract = url_info["description"] if "description" in url_info else ""
    collection_json = requests.get(url + "/collections").json()
    return [
        {
            "name": collection["id"],
            "title": collection["title"],
            "abstract": collection["description"]
            if "description" in collection
            else "",
            "dataset_md_id": EMPTY,
            "service_url": url,
            "service_title": service_title,
            "service_abstract": service_abstract,
            "service_type": API_FEATURES,
            "service_md_id": EMPTY,
        }
        for collection in collection_json["collections"]
    ]


def original_layers_pdok(layers_location, backup_file_path):
    # Find backup or print if not exists
    if os.path.exists(backup_file_path):
        shutil.copy2(backup_file_path, layers_location)
        os.remove(backup_file_path)
        logger.info(
            f"Backup copy '{backup_file_path}'replaces layers-pdok.json and backup file removed"
        )
    else:
        logger.info(f"No backup found at '{backup_file_path}': No files replaced")


def add_ogcapi_records(layers_location, resources_folder, backup_file_path, urls=[]):
    # Checkout if layers-pdok.json exists
    if not os.path.exists(layers_location):
        logger.info(
            f"There is no layers-pdok.json file in the correct location: {resources_folder}"
        )
        sys.exit(1)

    # Create a backup copy of the original file if it doesn't exist
    if not os.path.exists(backup_file_path):
        shutil.copy2(layers_location, backup_file_path)
        logger.info(
            f"Backup copy '{backup_file_path}' created with original layers-pdok.json"
        )
    else:
        logger.info(f"Backup already exists '{backup_file_path}': No copy made")

    extra_records_layers_pdok = extend_layer_pdok_ogcapi(urls=urls)

    # Load existing data from the JSON file (if it exists)
    try:
        with open(layers_location, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    all_ogcapi_records_exist = all(
        record in data for record in extra_records_layers_pdok
    )

    if not all_ogcapi_records_exist:
        extra_records_layers_pdok.extend(data)
        write_to_layers_file(extra_records_layers_pdok, layers_location)
        logger.info("layers-pdok.json updated succesfully")
    else:
        write_to_layers_file(data, layers_location)
        logger.info(
            f"All ogcapi records already exist in '{layers_location}': Nothing added"
        )


def write_to_layers_file(datafile, layers_location):
    with open(layers_location, "w") as file:
        json.dump(datafile, file, indent=4)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", help="Choose one of [ogcapi|original]", choices=["ogcapi", "original"]
    )
    parser.add_argument("urls", nargs="*", help="Url(s) of ogcapi landing page(s)")
    args: argparse.Namespace = parser.parse_args()
    return args.mode, args.urls


def main():
    current_directory = os.path.dirname(os.path.abspath(__file__))
    resources_folder = os.path.join(
        current_directory, "..", "pdokservicesplugin", "resources"
    )
    backup_file_path = os.path.join(resources_folder, "layers-pdok-ORIGINAL-COPY.json")
    layers_location = os.path.join(resources_folder, "layers-pdok.json")
    mode, urls = parse_args()

    if mode == "original":
        original_layers_pdok(
            layers_location=layers_location, backup_file_path=backup_file_path
        )
        sys.exit(0)

    if not urls:
        logger.error(
            "Provide one or multiple urls of ogcapi landing pages when using this mode"
        )
        sys.exit(1)

    add_ogcapi_records(
        layers_location=layers_location,
        resources_folder=resources_folder,
        backup_file_path=backup_file_path,
        urls=urls,
    )


if __name__ == "__main__":
    main()
