"""Read-only release and preservation audit; never invokes an evaluated model."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASELINE = json.loads((WORK / 'prior_tasks_baseline.json').read_text(encoding='utf-8'))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def preservation():
    missing, changed = [], []
    for entries in BASELINE.values():
        for entry in entries:
            path = ROOT / entry['path']
            if not path.is_file():
                missing.append(entry['path'])
            elif sha(path.read_bytes()) != entry['sha256']:
                changed.append(entry['path'])
    return dict(recorded_files=sum(map(len, BASELINE.values())), missing=missing,
                changed=changed, passed=not missing and not changed,
                scope='Previously recorded published/reference files only; caches and scratch excluded')

def archive_audit(path):
    forbidden = re.compile(rb'(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    result = dict(archive=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes()),
                  bytes=path.stat().st_size, members=[], unsafe_paths=[],
                  secret_pattern_files=[], byte_differences=[], missing_source=[])
    with zipfile.ZipFile(path) as archive:
        result['zip_integrity_error'] = archive.testzip()
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = PurePosixPath(member.filename)
            if name.is_absolute() or '..' in name.parts or not member.filename.startswith('tasks/'):
                result['unsafe_paths'].append(member.filename)
                continue
            data = archive.read(member)
            source = ROOT / Path(*name.parts)
            result['members'].append(dict(path=member.filename, bytes=len(data), sha256=sha(data)))
            if not source.is_file():
                result['missing_source'].append(member.filename)
            elif data != source.read_bytes():
                result['byte_differences'].append(member.filename)
            if forbidden.search(data) or name.name in {'auth.json', '.env'}:
                result['secret_pattern_files'].append(member.filename)
    result['passed'] = not any(result[key] for key in [
        'zip_integrity_error', 'unsafe_paths', 'secret_pattern_files',
        'byte_differences', 'missing_source'])
    return result

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('archives', nargs='*', type=Path)
    parser.add_argument('--output', default='root_release_audit.json')
    args = parser.parse_args()
    git = subprocess.run(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    (WORK / 'git_status_read_only.txt').write_text(git.stdout, encoding='utf-8', newline='\n')
    report = dict(prior_tasks=preservation(),
                  archives=[archive_audit(path.resolve()) for path in args.archives],
                  model_attempts=0, success_rate=None, model_status='USER_LOCAL_ONLY',
                  git_mutated=False, secret_scan='Pattern scan only; no credentials inspected')
    (WORK / args.output).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(prior_tasks=report['prior_tasks'], archives=[
        {k:v for k,v in item.items() if k!='members'} for item in report['archives']]), indent=2))

if __name__ == '__main__':
    main()
