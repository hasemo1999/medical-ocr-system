import os, sys, csv, html

CSS = """
body{font-family:ui-sans-serif,system-ui,Segoe UI,Meiryo,Arial; margin:16px}
h1{font-size:18px;margin:0 0 8px}
.controls{display:flex;gap:8px;align-items:center;margin:8px 0}
input[type=text]{padding:6px 8px;border:1px solid #ccc;border-radius:6px;min-width:260px}
.table-wrap{height:80vh;overflow:auto;border:1px solid #ddd;border-radius:8px}
table{border-collapse:collapse;width:100%}
th,td{padding:8px 10px;border-bottom:1px solid #eee;white-space:nowrap}
thead th{position:sticky;top:0;background:#fff;z-index:2;border-bottom:2px solid #ddd}
tbody tr:nth-child(even){background:#fafafa}
.badge{display:inline-block;padding:2px 6px;border:1px solid #ddd;border-radius:999px;font-size:12px}
a{color:#0b69c7;text-decoration:none}
a:hover{text-decoration:underline}
"""

JS = """
function filterTable(){
  const q = document.getElementById('q').value.toLowerCase();
  const rows = document.querySelectorAll('tbody tr');
  rows.forEach(tr=>{
    const hit = tr.textContent.toLowerCase().includes(q);
    tr.style.display = hit ? '' : 'none';
  });
}
"""

def to_html_row(row, headers):
    tds=[]
    for h in headers:
        v = row.get(h,"")
        # file:// を自動でリンク
        if isinstance(v,str) and v.startswith("file:///"):
            tds.append(f'<td><a href="{html.escape(v)}" target="_blank">{html.escape(os.path.basename(v))}</a></td>')
        else:
            tds.append(f"<td>{html.escape(v)}</td>")
    return "<tr>"+"".join(tds)+"</tr>"

def main(csv_path, html_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    headers = rows[0].keys() if rows else []
    thead = "<tr>"+"".join(f"<th>{html.escape(h)}</th>" for h in headers)+"</tr>"
    tbody = "\n".join(to_html_row(r, headers) for r in rows)
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<style>{CSS}</style><title>{html.escape(os.path.basename(csv_path))}</title>
</head><body>
<h1>{html.escape(os.path.basename(csv_path))}</h1>
<div class="controls">
  <input id="q" type="text" placeholder="検索（全列対象）" oninput="filterTable()">
  <span class="badge">{len(rows)} 行</span>
</div>
<div class="table-wrap"><table>
<thead>{thead}</thead>
<tbody>{tbody}</tbody>
</table></div>
<script>{JS}</script>
</body></html>"""
    with open(html_path, "w", encoding="utf-8", newline="") as f:
        f.write(doc)
    print(f"作成: {html_path}")

if __name__ == "__main__":
    if len(sys.argv)<3:
        print("Usage: python csv_to_html_sticky.py <input.csv> <output.html>")
        sys.exit(0)
    main(sys.argv[1], sys.argv[2])



