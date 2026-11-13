import json, re, subprocess, sys, tempfile, yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ecm-engine"))
from ecm_engine.billing import reconcile_invoice

cfg = yaml.safe_load(open("ecm_v2.yaml", encoding="utf-8"))
cfg["button_card_templates"].pop("ecm_title", None)

rows = json.loads((Path(__file__).resolve().parents[1] / "ecm-engine" / "billing_invoices.json").read_text(encoding="utf-8"))
bill_lines = ["| Periodo | Prelievo rete | Bolletta |", "|---|---:|---:|"]
for row in rows:
    bill_lines.append(f"| {row['period']} | {row['f1_kwh'] + row['f23_kwh']} kWh | {reconcile_invoice(row)} € |")
bill_lines.append("\nI totali includono IVA, accise e canone TV; febbraio–marzo include uno sconto una tantum di 20 €.")
for view in cfg["views"]:
    if view.get("path") == "costi":
        for section in view.get("sections", []):
            for card in section.get("cards", []):
                if card.get("content") == "__BILLING_HISTORY__":
                    card["content"] = "\n".join(bill_lines)

def walk(o, fn):
    if isinstance(o, dict):
        for k, v in list(o.items()):
            o[k] = walk(v, fn)
        return fn(o)
    if isinstance(o, list):
        return [walk(x, fn) for x in o]
    return fn(o)

def conv(o):
    # ecm_title -> heading nativo
    if isinstance(o, dict) and o.get("template") == "ecm_title":
        return {"type": "heading", "heading": o["name"], "icon": o["icon"]}
    return o
cfg = walk(cfg, conv)

js = []
def grab(o):
    if isinstance(o, str) and "[[[" in o:
        js.append(re.search(r"\[\[\[(.*)\]\]\]", o, re.S).group(1))
    return o
walk(cfg, grab)
src = "const bodies=" + json.dumps(js) + ";let bad=0;bodies.forEach((b,i)=>{try{new Function('states','entity','variables','user','hass','html',b)}catch(e){bad++;console.log('ERR',i,e.message,b.slice(0,120))}});console.log(bodies.length,'templates,',bad,'errori');process.exit(bad?1:0)"
with tempfile.TemporaryDirectory() as temp_dir:
    js_path = Path(temp_dir) / "check_templates.js"
    js_path.write_text(src, encoding="utf-8")
    r = subprocess.run(["node", str(js_path)], capture_output=True, text=True)
print(r.stdout, r.stderr)
if r.returncode: sys.exit(1)

# entità referenziate
ents = sorted(set(re.findall(r"\b(?:sensor|input_[a-z]+|automation|binary_sensor)\.[a-z0-9_]+", json.dumps(cfg))))
open("entities_v2.txt", "w", encoding="utf-8").write("\n".join(e for e in ents if e != "input_select.select_option" and e != "input_button.press"))
json.dump({"version": 1, "minor_version": 1, "key": "lovelace.ecm_v2", "data": {"config": cfg}},
          open("lovelace.ecm_v2", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ok", len(json.dumps(cfg)), "byte;", len(ents), "entità")
