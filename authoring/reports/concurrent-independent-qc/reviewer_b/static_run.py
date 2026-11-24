import json,os,shutil,subprocess,tempfile
from pathlib import Path
stage=Path(tempfile.mkdtemp(prefix='reviewer-b-static-'));up=Path('/upstream');out=Path('/review/static');out.mkdir(exist_ok=True)
for name in ['ci_checks','tools/task-readme']:
    shutil.copytree(up/name,stage/name)
(stage/'.github').mkdir();shutil.copyfile(up/'.github/reviewer-pool.yml',stage/'.github/reviewer-pool.yml')
for name in ['task-readme-template.md','task-template.toml']:
    shutil.copyfile(up/name,stage/name)
result={}
for slug,domain,field,mount in [('meiotic-tract-inference','life-sciences','biology','/life'),('redox-mineral-equilibrium','physical-sciences','chemistry','/chem')]:
    target=Path('tasks')/domain/field/slug;shutil.copytree(mount,stage/target)
    rows={}
    for script in sorted((stage/'ci_checks').glob('check-*.sh')):
        p=subprocess.run(['bash',str(script),str(target)],cwd=stage,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        rows[script.name]=dict(returncode=p.returncode,output=p.stdout)
        (out/(slug+'-'+script.stem+'.log')).write_text(p.stdout)
    result[slug]=rows
(out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({task:{k:v['returncode'] for k,v in rows.items()} for task,rows in result.items()},indent=2))
