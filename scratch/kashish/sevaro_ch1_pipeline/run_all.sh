#!/usr/bin/env bash
set -e
CV="${1:-/mnt/data/CV Mehra_Set 2.pdf}"
FORM="${2:-/mnt/data/Weehope Umakeit App - TX_Set 2.pdf}"

python src/extract_cv.py --cv "$CV" --out out/provider_profile.json
python src/list_form_fields.py --pdf "$FORM" --out_csv out/form_fields.csv --out_json out/form_fields.json
python src/generate_mapping_template.py --profile out/provider_profile.json --out templates/mapping.yaml

echo "Now open templates/mapping.yaml and fill 'field_id' with ids from out/form_fields.csv"
echo "Then run:"
echo "python src/fill_pdf.py --pdf "$FORM" --profile out/provider_profile.json --mapping templates/mapping.yaml --out out/filled_Texas_App_Mehra.pdf"
