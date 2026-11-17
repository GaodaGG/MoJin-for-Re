"""Read this pinned title's ABI from its freshly relocated program image.

The ELF module GP field itself has a PRX relocation. Adding the load base to
that raw word is not its relocated value. No prior analysis JSON is required.
"""
import hashlib
import struct
from pathlib import Path
from inspect_input import elf

ELF_SHA='0a25b484b3b324879d2d951172bf44aff8b13bf11bb6a958ff060be8ea4b8b12'
IMAGE_SHA='aa17cb3f96155592be82a9a0629ec876b61169e3dd3e7ab4e5d8b5e6da53d2f4'
BASE=0x08804000


def load_image(image_path):
    image=Path(image_path).read_bytes()
    assert hashlib.sha256(image).hexdigest()==IMAGE_SHA, 'Unvalidated relocated image'
    # Section offset/entry were established from the exact ELF above. The image
    # digest binds this entire layout, so no ELF/ISO is required at probe time.
    offset=0x16b258
    gp=struct.unpack_from('<I',image,offset+32)[0]
    assert gp==0x08a21660
    return dict(entry_point=0x08804114,load_base=BASE,module=dict(gp=gp),
                source_elf_sha256=ELF_SHA,relocated_image_sha256=IMAGE_SHA,
                module_info_image_offset=offset,elf_opened=False,
                meaning='GP from exact hash-bound relocated image; ELF identity is provenance only')


def load(elf_path, image_path):
    raw=Path(elf_path).read_bytes(); image=Path(image_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==ELF_SHA, 'Wrong title input version'
    assert hashlib.sha256(image).hexdigest()==IMAGE_SHA, 'Unvalidated relocated image'
    info=elf(raw)
    assert info['type']=='0xffa0' and info['machine']==8
    sections=[s for s in info['sections'] if s['name']=='.rodata.sceModuleInfo']
    assert len(sections)==1 and sections[0]['size']==52
    section=sections[0]; offset=int(section['address'],16)
    assert 0 <= offset <= len(image)-52
    gp=struct.unpack_from('<I',image,offset+32)[0]
    raw_gp=struct.unpack_from('<I',raw,section['offset']+32)[0]
    entry=BASE+int(info['entry'],16)
    assert BASE <= entry < BASE+len(image) and BASE <= gp < BASE+len(image)
    return dict(entry_point=entry,load_base=BASE,module=dict(gp=gp),
                source_elf_sha256=ELF_SHA,relocated_image_sha256=IMAGE_SHA,
                module_info_image_offset=offset,raw_gp_word=raw_gp,
                meaning='Module GP read after PRX relocation, not raw ELF word plus load base')
