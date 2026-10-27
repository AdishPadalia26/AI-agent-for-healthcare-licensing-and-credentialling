import csv, yaml, re
from difflib import get_close_matches
from pathlib import Path

def normalize(s):
    return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def auto_map(mapping_path, fields_csv, out_path=None):
    with open(mapping_path) as f:
        mapping = yaml.safe_load(f)
    with open(fields_csv, newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = [r['field_id'] for r in reader]

    logicals = [m['logical_key'] for m in mapping['fields']]
    suggestions = {}
    for key in logicals:
        best = get_close_matches(normalize(key), [normalize(f) for f in fieldnames], n=1, cutoff=0.3)
        if best:
            # find original field name with same normalized text
            match_idx = [normalize(f) for f in fieldnames].index(best[0])
            suggestions[key] = fieldnames[match_idx]
        else:
            suggestions[key] = ""
    # update mapping
    for f in mapping['fields']:
        if not f.get('field_id'):
            f['field_id'] = suggestions.get(f['logical_key'], "")
    out_path = out_path or mapping_path
    with open(out_path, 'w') as f:
        yaml.safe_dump(mapping, f, sort_keys=False)
    print(f"Updated {out_path} with auto-mapped field_ids")

if __name__ == "__main__":
    auto_map("templates/mapping.yaml", "out/form_fields.csv")
