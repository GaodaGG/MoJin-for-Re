"""Exercise real prepared-input rejection before any compiler can consume it."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import prepared_game as prepared

ROOT=Path(__file__).resolve().parents[2]
BASE=(ROOT/'development/tests/prepared-integrity').resolve()
BASE.mkdir(parents=True,exist_ok=True)
fixture=Path(tempfile.mkdtemp(prefix='inputs-',dir=BASE)).resolve()
assert fixture.is_relative_to(BASE) and fixture!=BASE
original_root=prepared.ROOT; original_dev=prepared.DEV
original_payload=prepared.PREPARED
results=[]
try:
    payload=fixture/'development/prepared/game'
    shutil.copytree(original_payload,payload)
    for name in (*prepared.GENERATOR_INPUTS,'development/assets/disc-manifest.json'):
        target=fixture/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target)
    prepared.ROOT=fixture; prepared.DEV=fixture/'development'
    prepared.verify(payload)
    def rejected(name):
        try: prepared.verify(payload)
        except (AssertionError,FileNotFoundError): results.append(dict(case=name,rejected=True))
        else: raise AssertionError('Bad prepared input was accepted: '+name)
    missing=payload/'mojin_recomp_125.c'; held=fixture/'held.c'
    missing.rename(held); rejected('missing compilation unit'); held.rename(missing)
    unexpected=payload/'mojin_recomp_999.c'
    unexpected.write_text('/* extra input must not enter Make wildcards */\n')
    rejected('unexpected compilation unit'); unexpected.unlink()
    image=payload/'mojin_image.bin'; held=fixture/'held-image.bin'
    image.rename(held); image.write_text('version https://git-lfs.github.com/spec/v1\n')
    rejected('unresolved LFS pointer'); image.unlink(); held.rename(image)
    generator=fixture/'development/tools/codegen.py'
    old=generator.read_bytes(); generator.write_bytes(old+b'\n# changed lowering input\n')
    rejected('stale generated code after generator edit'); generator.write_bytes(old)
    prepared.verify(payload)
finally:
    prepared.ROOT=original_root; prepared.DEV=original_dev
    # This exact fresh temporary target is verified before recursive removal.
    assert fixture.resolve().is_relative_to(BASE) and fixture.resolve()!=BASE
    shutil.rmtree(fixture)
prepared.verify(original_payload)
record=dict(cases=results,original_inputs_unchanged=True)
(ROOT/'development/evidence/prepared-integrity-test.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
