#!/usr/bin/env bash
# bash script to generate config for https://github.com/rduivenvoorde/pdokservicesplugin with ngr-services-spider
# requires:
# - docker
# - jq

set -euo pipefail
PROGRAM_NAME=$(basename "$0")

function usage {
    echo "Script to update PDOK layers config file"
    echo ""
    echo "Usage:"
    echo "  $PROGRAM_NAME [options]"
    echo ""
    echo "Options:"
    echo "  -c    COMPACT_JSON    Compact instead of pretty-printed JSON output."
    echo "  -o    OUTPUT_FILE     Output file [default: /pdokservicesplugin/resources/layers-pdok.json]."
    echo "  -n    NR_OF_SERVICES  Number of services to index per protocol [default: -1]."
    echo "  -p    PROTOCOL_LIST   Comma separated list of protocols to index services for [default: OGC:WMTS,OGC:WMS,OGC:WFS,OGC:WCS]."
    exit 1
}

script_dir=$(dirname $(realpath $BASH_SOURCE))
layers_config_file=$(realpath "${script_dir}/../pdokservicesplugin/resources/layers-pdok.json")

output_file=-
nr_of_services=-1
protocol_list="OGC:WMTS,OGC:WMS,OGC:WFS,OGC:WCS"
pretty=true
while getopts "hcn:o:p:" arg; do
  case $arg in 
    h) usage;;
    c) pretty=false;;
    n) nr_of_services=$OPTARG;;
    o) output_file=$OPTARG;;
    p) protocol_list=$OPTARG;;
    *) print_usage
  esac
done
shift $((OPTIND-1)) # remove optionals arguments in case positional arguments follow

if [[ $output_file == "-" ]];then
    output_file="$layers_config_file"
fi

output_dir=$(dirname "$(realpath "$output_file")")
spider_output=/output_dir/$(basename "$output_file")

cat <<EOF > /tmp/sorting-rules.json
[
  { "index": 0, "names": ["opentopo+"], "types": ["OGC:WMTS"] },
  { "index": 10, "names": ["^actueel_orthohr$"], "types": ["OGC:WMTS"] },
  { "index": 11, "names": ["^actueel_ortho25$"], "types": ["OGC:WMTS"] },
  { "index": 12, "names": ["^actueel_ortho25ir$"], "types": ["OGC:WMTS"] },
  { "index": 12, "names": ["lufolabels"], "types": ["OGC:WMTS"] },
  {
    "index": 20,
    "names": ["landgebied", "provinciegebied", "gemeentegebied"],
    "types": ["OGC:WFS"]
  },
  { "index": 30, "names": ["top+"], "types": ["OGC:WMTS"] },
  {
    "index": 32,
    "names": ["^standaard$", "^grijs$", "^pastel$", "^water$"],
    "types": ["OGC:WMTS"]
  },
  {
    "index": 34,
    "names": ["bgtstandaardv2", "bgtachtergrond"],
    "types": ["OGC:WMTS"]
  },
  { "index": 60, "names": ["ahn3+"], "types": ["OGC:WMTS"] }
]
EOF

nr_svc_flag=""
if [[ $nr_of_services -ne "-1" ]];then
  nr_svc_flag="-n ${nr_of_services}"
fi

docker run -v "/${output_dir}:/output_dir" -v /tmp:/tmp pdok/ngr-services-spider layers $nr_svc_flag --snake-case -s /tmp/sorting-rules.json -m flat -p "$protocol_list" "$spider_output" --jq-filter '.layers[] |= with_entries( 
  if .key == "service_protocol" then
    .value = (.value | split(":")[1] | ascii_downcase) | .key = "service_type" 
  elif .key == "service_metadata_id" then 
    .key = "service_md_id" 
  elif .key == "dataset_metadata_id" then 
    .key = "dataset_md_id" 
  elif .key == "styles" then
    .value = (.value | map(del(.legend_url)))
  else 
    (.) 
  end
) | .layers |= map(
  if .service_type == "wmts" then
    del(.styles)
  else
    (.)
  end
) | .layers'

echo "INFO: output written to $(realpath "${output_file}")"

if [[ $pretty == true ]];then
  temp_file=$(mktemp --suffix=.json -u)
  mv "$output_file" "$temp_file"
  jq < "$temp_file" > "$output_file"
fi