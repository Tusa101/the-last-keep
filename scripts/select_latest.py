#!/usr/bin/env python3
"""Find newest semver ZIP in repository root and safely extract it to _game/."""
import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import zipfile

MAX_UNCOMPRESSED=80*1024*1024
MAX_FILES=1500
VERSION=re.compile(r'(?i)(?:^|[_-])v(\d+)_(\d+)(?:_(\d+))?(?=\.zip$)')

def version(name):
    m=VERSION.search(name)
    return tuple(map(int,(m.group(1),m.group(2),m.group(3) or '0'))) if m else None

def select(root):
    candidates=[(version(p.name),p.name,p) for p in root.glob('*.zip') if version(p.name)]
    if not candidates: raise ValueError('No versioned ZIP at repository root. Expected *_v1_3.zip')
    return max(candidates)[2]

def unpack(archive,destination):
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>MAX_FILES or sum(i.file_size for i in infos)>MAX_UNCOMPRESSED:
            raise ValueError('ZIP exceeds file count or size limit')
        paths=[]
        for i in infos:
            p=PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or not p.parts or ':' in p.parts[0]:
                raise ValueError('Unsafe archive path: '+i.filename)
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlinks are forbidden: '+i.filename)
            paths.append(p)
        # Allow a single enclosing folder or archive files at root.
        filepaths=[p for p,i in zip(paths,infos) if not i.is_dir()]
        prefix=filepaths[0].parts[0] if filepaths and all(len(p.parts)>1 and p.parts[0]==filepaths[0].parts[0] for p in filepaths) else None
        for i,p in zip(infos,paths):
            parts=p.parts[1:] if prefix else p.parts
            if not parts or i.is_dir(): continue
            target=destination.joinpath(*parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(i) as source, target.open('wb') as sink: shutil.copyfileobj(source,sink)
    if not (destination/'package.json').is_file() or not (destination/'index.html').is_file():
        raise ValueError('Archive must contain a Vite project with package.json and index.html')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.');ap.add_argument('--output',default='_game');args=ap.parse_args()
    root=Path(args.root).resolve();chosen=select(root)
    print(f'Selected latest version: {chosen.name}',flush=True)
    unpack(chosen,Path(args.output).resolve())
    print('Extracted to:',Path(args.output).resolve())
