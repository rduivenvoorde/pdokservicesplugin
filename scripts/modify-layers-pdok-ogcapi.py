#!/usr/bin/env python3
"""Modify/extend layers-pdok.json with OGC:API records for tiles from PDOK

This script allows the user modify the layers-pdok.json file which is used in the
pdokservicesplugin. The records are generated in this script by requesting 
various API endpoints that are conform the OGC:API standards.

To run this script, one has to provide a single parameter: [ogcapi|original]

Run the following command from the root of the repository:
`python3 ./scripts/modify-layers-pdok-ogcapi.py ogcapi`: Adds ogcapi test records to 
layers-pdok.json for tiles and creates a copy of the original file

`python3 ./scripts/modify-layers-pdok-ogcapi.py original`: Replaces layers-pdok.json 
with the copy file (containing the original .json file) and removes the copy.

The URL endpoints that are used in this script to add layers are defined in "URLS_OAT". 
By modifying this constant, other endpoints can be added locally 
without this service having a record in NGR.  
"""

import json
import os
import shutil
import requests
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

log = logging.getLogger(__name__)

URLS_OAT = [
    "https://api.pdok.nl/lv/bag/ogc/v1_0",
    "https://api.pdok.nl/lv/bgt/ogc/v1_0",
]
BAG_DATASET_MD_ID = "aa3b5e6e-7baa-40c0-8972-3353e927ec2f"
BAG_SERVICE_MD_ID = "b0f20313-2892-415e-82c1-bf77a984e8d8"
BGT_DATASET_MD_ID = "2cb4769c-b56e-48fa-8685-c48f61b9a319"
BGT_SERVICE_MD_ID = "356fc922-f910-4874-b72a-dbb18c1bed3e"


def extend_layer_pdok_ogcapi(urls_oat=[]):
    layers_pdok = []
    layers_pdok = retrieve_layers_from_oat_endpoint(urls_oat)
    return layers_pdok


def retrieve_layers_from_oat_endpoint(urls=[]):
    oat_layers = []
    for url in urls:
        url_info = requests.get(url).json()
        dataset_title = url_info.get("title", url.split("/")[-1])
        tiles_info = requests.get(url + "/tiles").json()
        if "bag" in url:
            dataset_md_id = BAG_DATASET_MD_ID
            service_md_id = BAG_SERVICE_MD_ID
        elif "bgt" in url:
            dataset_md_id = BGT_DATASET_MD_ID
            service_md_id = BGT_SERVICE_MD_ID

        dataset_abstract = url_info.get("description", "Geen abstract gevonden")
        service_type = "api tiles"
        styles = requests.get(url + "/styles").json()
        tiles = requests.get(url + "/tiles").json()
        tile_object = {
            "name": dataset_title,
            "title": dataset_title,
            "abstract": dataset_abstract,
            "dataset_md_id": dataset_md_id,
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
                            "tileset_crs": tileset["crs"]
                        }
                        for tileset in tiles["tilesets"]
                    ]
                }
            ],
            "service_url": url,
            "service_title": tiles_info["title"],
            "service_abstract": tiles_info["description"],
            "service_type": service_type,
            "service_md_id": service_md_id,
        }
        oat_layers.append(tile_object)
    return oat_layers


def original_layers_pdok(layers_location, backup_file_path):
    # Find backup or print if not exists
    if os.path.exists(backup_file_path):
        shutil.copy2(backup_file_path, layers_location)
        os.remove(backup_file_path)
        log.info(
            f"Backup copy '{backup_file_path}'replaces layers-pdok.json and backup file removed"
        )
    else:
        log.info(f"No backup found at '{backup_file_path}': No files replaced")
    return


def add_ogcapi_records(layers_location, resources_folder, backup_file_path):
    # Checkout if layers-pdok.json exists
    if not os.path.exists(layers_location):
        log.info(
            f"There is no layers-pdok.json file in the correct location: {resources_folder}"
        )
        sys.exit(1)

    # Create a backup copy of the original file if it doesn't exist
    if not os.path.exists(backup_file_path):
        shutil.copy2(layers_location, backup_file_path)
        log.info(
            f"Backup copy '{backup_file_path}' created with original layers-pdok.json"
        )
    else:
        log.info(f"Backup already exists '{backup_file_path}': No copy made")

    # For testing the plugin with ogcapi tiles: extend original layers-pdok.json
    extra_records_layers_pdok = extend_layer_pdok_ogcapi(
        urls_oat=URLS_OAT
    )

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
        log.info("layers-pdok.json updated succesfully")
    else:
        write_to_layers_file(data, layers_location)
        log.info(f"All ogcapi records already exist in '{layers_location}': Nothing added")
    return


def write_to_layers_file(datafile, layers_location):
    with open(layers_location, "w") as file:
        json.dump(datafile, file, indent=4)
    return


def main():
    current_directory = os.path.dirname(os.path.abspath(__file__))
    resources_folder = os.path.join(
        current_directory, "..", "pdokservicesplugin", "resources"
    )
    backup_file_path = os.path.join(resources_folder, "layers-pdok-ORIGINAL-COPY.json")
    layers_location = os.path.join(resources_folder, "layers-pdok.json")
    allowed_args = ["ogcapi", "original"]
    # Check for the correct number of command-line arguments
    if len(sys.argv) != 2:
        log.info("Usage: modify-layers-pdok-ogcapi.py [ogcapi|original]")
        sys.exit(1)

    if sys.argv[1] not in allowed_args:
        log.info(f"Arg {sys.argv[1]} not allowed, only [ogcapi|original] allowed")
        sys.exit(1)
    else:
        mode = sys.argv[1]
        if mode == "ogcapi":
            add_ogcapi_records(
                layers_location=layers_location,
                resources_folder=resources_folder,
                backup_file_path=backup_file_path,
            )
        else:  # mode == 'original'
            original_layers_pdok(
                layers_location=layers_location, backup_file_path=backup_file_path
            )


if __name__ == "__main__":
    main()
