
import argparse, csv, json
from pathlib import Path
from pdfrw import PdfReader

def list_fields(pdf_path: str):
    pdf = PdfReader(pdf_path)
    fields = []
    try:
        acro = pdf.Root.AcroForm
        for f in acro.Fields:
            name = str(getattr(f, 'T', '')).strip('()')
            ftype = str(getattr(f, 'FT', ''))
            fields.append({"field_id": name, "type": ftype})
    except Exception:
        pass
    return fields

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out_csv", default="out/form_fields.csv")
    ap.add_argument("--out_json", default="out/form_fields.json")
    args = ap.parse_args()
    fields = list_fields(args.pdf)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["field_id","type"])
        w.writeheader()
        w.writerows(fields)
    Path(args.out_json).write_text(json.dumps(fields, indent=2))
    print(f"Wrote {args.out_csv} and {args.out_json} (found {len(fields)} fields).")
