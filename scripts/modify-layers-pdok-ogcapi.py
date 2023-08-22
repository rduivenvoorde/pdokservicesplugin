import json
import os
import shutil
import requests
import sys

# python script to modify layers-pdok for the plugin.
# provide a single parameter to determine behaviour of the script, either:
# ogcapi `python3 ./scripts/modify-layers-pdok-ogcapi.py ogcapi`: Adds ogcapi test records to layers-pdok.json and creates a copy
# original `python3 ./scripts/modify-layers-pdok-ogcapi.py original`: Replaces layers-pdok.json with the original copy and removes the copy


def extend_layer_pdok_ogcapi(urls_oaf = [], urls_oat = []):
        layers_pdok = []
        layers_pdok = retrieve_layers_from_oat_endpoint(urls_oat)
        layers_pdok.extend(retrieve_layers_from_oaf_endpoint(urls_oaf))
        return layers_pdok
    
def retrieve_layers_from_oat_endpoint(urls = []):
    oat_layers = []
    for url in urls:
        url_info = requests.get(url).json()
        dataset_title = url_info.get('title', url.split('/')[-1])
        # For the two test datasets, we hardcode some information for now which can not yet be retrieved from the endpoint
        if 'bag' in url:
            tms = "EPSG:28992,EPSG:3857,EPSG:4258"
            dataset_md_id = "aa3b5e6e-7baa-40c0-8972-3353e927ec2f"
            service_md_id = ""
        elif 'bgt' in url:
            tms = "EPSG:28992"
            dataset_md_id = "2cb4769c-b56e-48fa-8685-c48f61b9a319"
            service_md_id = "356fc922-f910-4874-b72a-dbb18c1bed3e"

        dataset_abstract = url_info.get('description', "Geen abstract gevonden")
        service_type = "api tiles"#"oat"
        styles = requests.get(url + "/styles").json()
        tiles_info = requests.get(url + "/tiles").json()
        tile_object = {
            "name": dataset_title,
            "title": dataset_title,
            "abstract": dataset_abstract,
            "dataset_md_id": dataset_md_id,
            "styles": [{"title": style["title"], "name": style["id"]} for style in styles["styles"]],
            "default": styles["default"],
            "tilematrixsets": tms,
            "service_url": url,
            "service_title": tiles_info["title"],
            "service_abstract": tiles_info["description"],
            "service_type": service_type,
            "service_md_id": service_md_id,
        }
        oat_layers.append(tile_object)
    return oat_layers
    
def retrieve_layers_from_oaf_endpoint(urls = []):
    oaf_layers = []
    for url in urls:
        url_layer = []
        url_info = requests.get(url).json()
        service_title = url_info['title'] if 'title' in url_info else url.split('/')[-1]
        service_abstract = url_info['description'] if 'description' in url_info else  "Geen abstract gevonden"
        service_type = 'api features'#"oapif"
        collection_json = requests.get(url + "/collections").json()
        for collection in collection_json["collections"]:
            collection_name = collection["id"]
            collection_title = collection["title"]
            collection_abstract = collection["description"] if "description" in collection else "Geen abstract gevonden"
            url_layer.append(
                {
                    "name": collection_name,
                    "title": collection_title,
                    "abstract": collection_abstract,
                    "dataset_md_id": "",
                    "service_url": url,
                    "service_title": service_title,
                    "service_abstract": service_abstract,
                    "service_type": service_type,
                    "service_md_id": "",
                }
            )
        oaf_layers.extend(url_layer)
    return oaf_layers

def original_layers_pdok():
    # Find backup or print if not exists
    if os.path.exists(backup_file_path):
        shutil.copy2(backup_file_path, layers_location)
        os.remove(backup_file_path)
        print(f"Backup copy '{backup_file_path}'replaces layers-pdok.json and backup file removed")
    else :
        print(f"No backup found at '{backup_file_path}': No files replaced")
    return

def add_ogcapi_records():
    # Checkout if layers-pdok.json exists
    if not os.path.exists(layers_location):
        print(f"There is no layers-pdok.json file in the correct location: {resources_folder}")
        sys.exit(1)

    # Create a backup copy of the original file if it doesn't exist
    if not os.path.exists(backup_file_path):
        shutil.copy2(layers_location, backup_file_path)
        print(f"Backup copy '{backup_file_path}' created with original layers-pdok.json")
    else :
        print(f"Backup already exists '{backup_file_path}': No copy made")


    # For testing the plugin with ogcapi features & tiles: extend original layers-pdok.json
    extra_records_layers_pdok = extend_layer_pdok_ogcapi(urls_oaf = urls_oaf, urls_oat = urls_oat)

    # Load existing data from the JSON file (if it exists)
    try:
        with open(layers_location, 'r', encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    all_ogcapi_records_exist = all(record in data for record in extra_records_layers_pdok)

    if not all_ogcapi_records_exist:
        extra_records_layers_pdok.extend(data)
        write_to_layers_file(extra_records_layers_pdok)
        print("layers-pdok.json updated succesfully")
    else :
        write_to_layers_file(data)
        print(f"All ogcapi records already exist in '{layers_location}': Nothing added") 
    return

# Save the updated data back to the JSON file
def write_to_layers_file(datafile):
    with open(layers_location, 'w') as file:
        json.dump(datafile, file, indent=4)
    return


# We add OAF layers to layers_pdok list 
urls_oaf = [
    "https://demo.ldproxy.net/daraa", 
    "https://test.haleconnect.de/ogcapi/datasets/hydro-example",
    "https://test.haleconnect.de/ogcapi/datasets/simplified-addresses"
]
urls_oat = [
    "https://api.pdok.nl/lv/bag/ogc/v0_1", 
    "https://api.pdok.nl/lv/bgt/ogc/v1_0"
]

# Get correct directory of target and this
current_directory = os.path.dirname(os.path.abspath(__file__))
resources_folder = os.path.join(current_directory, '..', 'pdokservicesplugin', 'resources')
backup_file_path =  os.path.join(resources_folder,'layers-pdok-ORIGINAL-COPY.json')
layers_location = os.path.join(resources_folder,'layers-pdok.json')
allowed_args = ['ogcapi', 'original']
# Check for the correct number of command-line arguments
if len(sys.argv) != 2:
    print("Usage: modify-layers-pdok-ogcapi.py [ogcapi|original]")
    sys.exit(1)

if sys.argv[1] not in allowed_args:
    print(f"Arg {sys.argv[1]} not allowed, only [ogcapi|original] allowed")
    sys.exit(1)
else :
    mode = sys.argv[1]
    if mode == 'ogcapi':
        add_ogcapi_records()
    else : # mode == 'original'
        original_layers_pdok()


