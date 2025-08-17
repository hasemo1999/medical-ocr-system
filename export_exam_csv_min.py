import os, csv, sys
from pathlib import Path

ENC = "utf-8-sig"

# kbn → 短い検査名（要望どおり：FAF/OCTA/OCT/VF など）
KBN_SHORT = {
	"kensa": "VF",
	"oct2": "OCT",
	"angio": "OCTA",
	"gantei2": "Fundus",
	"kowagantei": "Fundus",
	"keikou": "FAF",
	"kowaspe": "Spec",
	"kowatopo": "Topo",
	"kowaslit": "Slit",
	"kowaetc": "OCT(old)",
	"krt2-2": "Chart(new)",
	"old": "Chart(old)",
	"hoken": "ID",
	"ope": "Ope",
}

def load_csv(path: str):
	if not os.path.isfile(path):
		return []
	# UTF-8(BOM) 優先、ダメなら cp932 を試す
	try:
		with open(path, "r", encoding=ENC, newline="") as f:
			return list(csv.DictReader(f))
	except UnicodeDecodeError:
		try:
			with open(path, "r", encoding="cp932", newline="") as f:
				return list(csv.DictReader(f))
		except Exception:
			return []

def write_csv(path: str, rows: list, cols: list):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding=ENC, newline="") as f:
		w = csv.DictWriter(f, fieldnames=cols)
		w.writeheader()
		for r in rows:
			w.writerow(r)

def eye_jp(code: str):
	m = {"OD":"右","OS":"左","OU":"両眼","NA":"", "":"", None:""}
	return m.get((code or "").strip(), code or "")

def to_file_uri(root: str, rel: str):
	if not root or not rel:
		return ""
	p = os.path.abspath(os.path.join(root, rel))
	return "file:///" + p.replace("\\", "/")

def shorten_tail(path_like: str, nseg: int = 2, maxlen: int = 50):
	"""相対パスの末尾を短く表示（…/下位nseg階層まで、超長は省略）"""
	if not path_like:
		return ""
	parts = Path(path_like).as_posix().split("/")
	tail = "/".join(parts[-(nseg+1):]) if len(parts) >= nseg+1 else "/".join(parts)
	return ("…" + tail[-maxlen:]) if len(tail) > maxlen else tail

def find_store_root(cli_root: str, folder: str):
	if cli_root:
		return cli_root
	env = os.environ.get("ASSET_STORE_ROOT", "")
	if env:
		return env
	for cand in [os.path.join(folder, "store_root.txt"), os.path.join(os.path.dirname(folder), "store_root.txt")]:
		if os.path.isfile(cand):
			try:
				return open(cand, "r", encoding="utf-8").read().strip()
			except Exception:
				pass
	return ""

def load_image_root_from_config(folder: str) -> str:
	"""path_config.json があれば image_root を読む。無ければ D:\\画像 を返す。"""
	cfg_candidates = [
		os.path.join(os.getcwd(), 'path_config.json'),
		os.path.join(os.path.dirname(folder), 'path_config.json'),
	]
	import json
	for p in cfg_candidates:
		if os.path.isfile(p):
			try:
				with open(p, 'r', encoding='utf-8') as f:
					cfg = json.load(f)
				return cfg.get('image_root', r'D:\\画像')
			except Exception:
				continue
	return r'D:\\画像'

def parse_params_from_filename(file_value: str) -> dict:
	"""ファイル名の &key=value を辞書化（URLデコード、拡張子除去）。"""
	import urllib.parse
	params = {}
	if not file_value:
		return params
	base = os.path.basename(file_value)
	try:
		decoded = urllib.parse.unquote(base)
	except Exception:
		decoded = base
	part = decoded
	amp = part.find('&')
	if amp >= 0:
		part = part[amp+1:]
	lowered = part.lower()
	for ext in ('.jpg','.jpeg','.png','.tif','.tiff','.bmp','.webp'):
		if lowered.endswith(ext):
			part = part[:-(len(ext))]
			break
	for seg in part.split('&'):
		if '=' in seg:
			k, v = seg.split('=', 1)
			params[k] = v
	return params

def load_patient_txt(pid: str, image_root: str) -> dict:
	"""D:\\画像\\<pid>\\&pidnum=<pid>.txt を読み、pname/pkana/pbirth を返す。"""
	import codecs
	dir_path = os.path.join(image_root, str(pid))
	file_path = os.path.join(dir_path, f'&pidnum={pid}.txt')
	if not os.path.isfile(file_path):
		return {}
	text = ''
	for enc in ('utf-8', 'cp932', 'shift_jis'):
		try:
			with codecs.open(file_path, 'r', encoding=enc, errors='replace') as f:
				text = f.read()
				break
		except Exception:
			continue
	res = {}
	for line in text.splitlines():
		line = line.strip('\ufeff').strip()
		if not line or line.startswith('['):
			continue
		if '=' in line:
			k, v = line.split('=', 1)
			k = k.strip(); v = v.strip()
			if k in ('pname', 'pkana', 'pbirth'):
				res[k] = v
	return res

def main(folder: str, store_root: str = "", out_folder: str = ""):
	folder = os.path.abspath(folder)
	store_root = find_store_root(store_root, folder)
	image_root = load_image_root_from_config(folder)

	# 前提：records.csv（ルーター出力）と、patients.csv（無ければ patient_master.csv）が同フォルダ
	recs = load_csv(os.path.join(folder, "records.csv"))
	pats = load_csv(os.path.join(folder, "patients.csv")) or load_csv(os.path.join(folder, "patient_master.csv"))
	reg  = load_csv(os.path.join(store_root, "asset_registry.csv")) if store_root else []

	# 柔軟な患者インデックス（列名ゆれ対策）
	def build_patient_index(rows: list) -> dict:
		idx = {}
		for r in rows:
			pid = r.get("patient_id") or r.get("pid") or r.get("pidnum") or ""
			pid = str(pid).strip()
			if not pid:
				continue
			pname = r.get("pname") or r.get("patient_name") or r.get("name") or ""
			pkana = r.get("pkana") or r.get("kana") or ""
			idx[pid] = {"pname": pname, "pkana": pkana}
		return idx

	pmap = build_patient_index(pats)

	# 事前に患者ごとの hoken（保険証）から pbirth/pkana を優先抽出
	pid_to_ins = {}
	for r in recs:
		pid = str(r.get('patient_id','') or '').strip()
		if not pid:
			continue
		kbn = (r.get('kbn','') or '').lower()
		if kbn == 'hoken':
			params = parse_params_from_filename(r.get('file',''))
			if params:
				entry = pid_to_ins.get(pid, {})
				if params.get('pbirth'):
					entry['pbirth'] = params.get('pbirth')
				if params.get('pkana'):
					entry['pkana'] = params.get('pkana')
				pid_to_ins[pid] = entry
	rmap = { r.get("base",""): r for r in reg }  # base = 拡張子なしファイル名（CASのレジストリ）

	out = []
	for r in recs:
		pid = r.get("patient_id","")
		if not pid:
			continue
		kbn = (r.get("kbn","") or "").lower()
		# 検査日：kbn=old等 date_applicable=0 は空
		vdate = r.get("visit_date","") if str(r.get("date_applicable","1")).lower() in {"1","true"} else ""
		pr = pmap.get(pid, {})
		# 追加フォールバック: ファイル名から pname/pkana を拾う
		params_from_file = parse_params_from_filename(r.get('file',''))

		fname_from_rec = r.get("pname","")
		fkana_from_rec = r.get("pkana","")
		fbirth_from_rec = r.get("pbirth","")
		if not (pr.get("pname") or pr.get("pkana")):
			if params_from_file.get('pname') and not fname_from_rec:
				fname_from_rec = params_from_file.get('pname')
			if params_from_file.get('pkana') and not fkana_from_rec:
				fkana_from_rec = params_from_file.get('pkana')
			if params_from_file.get('pbirth') and not fbirth_from_rec:
				fbirth_from_rec = params_from_file.get('pbirth')

		# 保険証からの補完
		ins = pid_to_ins.get(pid, {})
		if ins.get('pbirth') and not fbirth_from_rec:
			fbirth_from_rec = ins.get('pbirth')
		if ins.get('pkana') and not fkana_from_rec:
			fkana_from_rec = ins.get('pkana')

		# テキストファイルからの最終フォールバック
		txt = load_patient_txt(pid, image_root)
		if not (pr.get('pname') or fname_from_rec) and txt.get('pname'):
			fname_from_rec = txt.get('pname')
		if not (pr.get('pkana') or fkana_from_rec) and txt.get('pkana'):
			fkana_from_rec = txt.get('pkana')
		if not fbirth_from_rec and txt.get('pbirth'):
			fbirth_from_rec = txt.get('pbirth')
		base = r.get("base") or os.path.splitext(r.get("file",""))[0]
		regrow = rmap.get(base, {})
		thumb_rel = regrow.get("thumb_relpath","")
		orig_rel  = regrow.get("orig_relpath","")

		out.append({
			"患者ID": pid,
			"患者名": (pr.get("pname") or fname_from_rec or ""),
			"フリガナ": (pr.get("pkana") or fkana_from_rec or ""),
			"生年月日": (fbirth_from_rec or ""),
			"検査名": KBN_SHORT.get(kbn, kbn or ""),
			"検査日": vdate,
			"眼": eye_jp(r.get("eye","")),
			"ファイル名": os.path.basename(r.get("file","")),
			"原本（末尾表示）": shorten_tail(orig_rel or r.get("file",""), nseg=2, maxlen=50),
			"サムネURI": to_file_uri(store_root, thumb_rel),
			"原本URI": to_file_uri(store_root, orig_rel),
		})

	cols = ["患者ID","患者名","フリガナ","生年月日","検査名","検査日","眼","ファイル名","原本（末尾表示）","サムネURI","原本URI"]
	target_dir = out_folder or folder
	out_csv = os.path.join(target_dir, "検査画像.csv")
	write_csv(out_csv, out, cols)
	print(f"作成: {out_csv}")

if __name__ == "__main__":
	folder = sys.argv[1] if len(sys.argv)>=2 else "."
	store_root = sys.argv[2] if len(sys.argv)>=3 else ""
	out_folder = sys.argv[3] if len(sys.argv)>=4 else ""
	main(folder, store_root, out_folder)


