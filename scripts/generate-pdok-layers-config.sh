#!/usr/bin/env bash
# bash script to generate config for https://github.com/rduivenvoorde/pdokservicesplugin with ngr-services-spider
set -euo pipefail

output_file="$1"
nr_of_services=${2:--} # configure nr of services to index, for debugging

output_dir=$(dirname "$(realpath "$output_file")")
output_file_real=$output_dir/$(basename "$output_file")
output_file_base=$(basename "$output_file_real")
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
if [[ $nr_of_services != "-" ]];then
  nr_svc_flag="-n ${nr_of_services}"
fi

docker run -v "${output_dir}:/output_dir" -v /tmp:/tmp "pdok/ngr-services-spider:0.6.0" layers $nr_svc_flag --snake-case --pretty -s /tmp/sorting-rules.json -m flat -p OGC:WMS,OGC:WFS,OGC:WCS,OGC:WMTS "/output_dir/${output_file_base}" --jq-filter '.layers[] |= with_entries(
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
) | .layers'

echo "INFO: output written to $(realpath "${output_file}")"
