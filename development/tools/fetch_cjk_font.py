"""Fetch the pinned official font and license; no executable or system installation."""
from pathlib import Path
import hashlib
import json
import urllib.request

DEV=Path(__file__).resolve().parents[1]
ROOT=DEV.parent
REV='523d033d6cb47f4a80c58a35753646f5c3608a78'
base=f'https://raw.githubusercontent.com/notofonts/noto-cjk/{REV}/'
folder=DEV/'assets/fonts/ui/noto-sans-sc'
folder.mkdir(parents=True,exist_ok=True)
rows=[]
expected={
    'NotoSansCJKsc-Regular.otf':'2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b',
    'OFL.txt':'6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2',
}
for remote,name in [('Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf','NotoSansCJKsc-Regular.otf'),('LICENSE','OFL.txt')]:
    path=folder/name
    if path.exists(): data=path.read_bytes()
    else:
        with urllib.request.urlopen(base+remote,timeout=45) as response: data=response.read()
    if hashlib.sha256(data).hexdigest()!=expected[name]:
        raise SystemExit(f'Pinned font/license hash mismatch; nothing overwritten: {path}')
    if name.endswith('.otf') and data[:4]!=b'OTTO': raise SystemExit('Not an OpenType font')
    if not path.exists():
        with path.open('xb') as output: output.write(data)
    rows.append(dict(path=path.relative_to(ROOT).as_posix(),url=base+remote,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
record=dict(project='notofonts/noto-cjk',version='Sans2.004',revision=REV,license='SIL Open Font License 1.1',files=rows)
(DEV/'assets/cjk-font-provenance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,indent=2))
