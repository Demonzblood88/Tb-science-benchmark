import hashlib,json,subprocess,sys
from pathlib import Path
up=Path('/upstream');corpus=Path('/corpus');out=Path('/review/static')
manifest=json.loads(Path('/life/authoring/provenance/pinned_similarity_corpus_manifest.json').read_text())
records=[]
for item in manifest['records']:
    if not item['upstream_path'].endswith('/instruction.md'):continue
    path=corpus/item['upstream_path'];raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==item['sha256']
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['git_blob']
    records.append(item['upstream_path'])
assert len(records)==97
result=dict(corpus_commit=manifest['commit'],verified_instruction_blobs=len(records),tasks={})
for kind in ['life','chem']:
    p=subprocess.run([sys.executable,'-B',str(up/'ci_checks/check-similarity.py'),'/'+kind,str(corpus/'tasks'),str(corpus/'lite')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    assert p.returncode==0,p.stdout
    result['tasks'][kind]=dict(returncode=p.returncode,stdout=p.stdout)
(out/'similarity_receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
