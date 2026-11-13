"""Package tracked project source and complete Git history, excluding runtime credentials/cache."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


ROOT=Path(__file__).resolve().parent.parent


def package(output):
    output=output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Write the ZIP outside the source repository')
    status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT).decode()
    if status.strip():
        raise RuntimeError('Commit the source before packaging so ZIP content matches Git HEAD')
    files=[x for x in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if x]
    forbidden={'.env','runtime','node_modules','.venv','work','__pycache__','pytest-cache-files-'}
    if any(any(part in forbidden or part.startswith('pytest-cache-files-') for part in Path(name).parts) for name in files):
        raise RuntimeError('Tracked runtime/credential file found; do not package')
    # Local source ZIP includes the complete object database and refs, never global Git config/credentials.
    git_dir=ROOT/'.git'
    if not git_dir.is_dir():
        raise RuntimeError('A standalone .git directory is required for the employer archive')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Bundled skill assets can legitimately have epoch timestamps; ZIP starts at 1980.
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as archive:
        for name in files:
            archive.write(ROOT/name,'stackbridge-youtube/'+name)
        for path in git_dir.rglob('*'):
            if path.is_file() and not path.name.endswith('.lock'):
                archive.write(path,'stackbridge-youtube/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert 'stackbridge-youtube/.git/HEAD' in names
        assert 'stackbridge-youtube/README.md' in names
        assert not any('/.env'==n[-5:] or '/runtime/' in n or '/ai/dialogues/' in n for n in names)
    return {'file':str(output),'bytes':output.stat().st_size,'files':len(names),
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    print(json.dumps(package(parser.parse_args().output),ensure_ascii=False))

