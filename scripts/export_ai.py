"""Copy original project-native JSONL snapshots into a separate, private review ZIP.

This intentionally never places full logs inside the submission source tree.
The user must review them because the tool may have injected unrelated context/account metadata.
"""
import argparse
import datetime
import hashlib
import json
import time
import zipfile
from pathlib import Path


def export(sessions,workspace,output):
    manifest={'purpose':'PRIVATE REVIEW ONLY — do not submit before explicit user review',
              'exported_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'format':'Unmodified bytes of complete native JSONL records at snapshot time',
              'files':[]}
    output=output.resolve()
    source_root=Path(__file__).resolve().parent.parent
    if output.is_relative_to(source_root):
        raise ValueError('Private originals must remain outside the submission source tree')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for session in sessions:
            data=session.read_bytes()
            if data and not data.endswith(b'\n'):
                time.sleep(.2)
                data=session.read_bytes()
                if not data.endswith(b'\n'):
                    raise RuntimeError('Native log is being written; retry after the current record is complete')
            rows=[json.loads(line) for line in data.splitlines() if line.strip()]
            meta=rows[0].get('payload',{})
            if Path(meta.get('cwd','')).resolve()!=workspace.resolve():
                raise ValueError('Refusing a session from a different workspace')
            if meta.get('thread_source')=='guardian_review':
                raise ValueError('Platform approval history is not the project implementation dialogue')
            name='native/'+session.name
            archive.writestr(name,data)
            manifest['files'].append({'filename':name,'sha256':hashlib.sha256(data).hexdigest(),
                                      'bytes':len(data),'records':len(rows),'session_id':meta.get('id'),
                                      'warning':'May include injected memory, account identifiers and platform instructions. Not a cleaned transcript.'})
        archive.writestr('REVIEW_FIRST.txt',
            'LOCAL PRIVATE REVIEW ONLY\nThese are original native files, not paraphrases or recreated logs.\n'
            'They may contain context automatically inserted by Codex from other projects and account metadata.\n'
            'They are deliberately excluded from the source submission archive pending user review.\n'
            'No files were sent to the employer or uploaded to a remote service.\n')
        archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return {'output':str(output),'files':len(manifest['files']),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--session',type=Path,action='append',required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.session,args.workspace,args.output),ensure_ascii=False))

