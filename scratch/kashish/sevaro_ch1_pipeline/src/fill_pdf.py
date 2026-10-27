
import argparse, json, yaml
from pathlib import Path
from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName

def fill_acroform(src_pdf_path: str, dst_pdf_path: str, field_values: dict, flatten: bool=True):
    pdf = PdfReader(src_pdf_path)
    if not hasattr(pdf, 'Root') or not hasattr(pdf.Root, 'AcroForm'):
        raise RuntimeError("PDF has no AcroForm fields")
    fields = pdf.Root.AcroForm.Fields
    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfName('true')))
    for f in fields:
        name = f.T[1:-1] if f.T else None
        if name and name in field_values and field_values[name] != "":
            f.V = str(field_values[name])
            f.AP = None
    PdfWriter().write(dst_pdf_path, pdf)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    profile = json.loads(Path(args.profile).read_text())
    mapping = yaml.safe_load(Path(args.mapping).read_text())

    field_values = {}
    for row in mapping.get("fields", []):
        fid = (row.get("field_id") or "").strip()
        val = row.get("value","")
        if fid:
            field_values[fid] = val

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fill_acroform(args.pdf, args.out, field_values, flatten=True)
    print(f"Wrote {args.out}")
