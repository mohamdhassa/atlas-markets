"""Exercise runner isolation and cleanup paths without needing a Docker daemon."""
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'ops/validate_release_candidate.sh'


@pytest.mark.parametrize('fail_migration',[False,True])
def test_runner_uses_disposable_network_and_cleans_only_owned_resources(tmp_path,fail_migration):
    fake=tmp_path/'docker'
    fake.write_text('''#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
with open(os.environ['DOCKER_TEST_LOG'],'a') as f:f.write(json.dumps(args)+'\\n')
if args[:2]==['network','create']:print('owned-network')
elif args and args[0]=='create':
    print('owned-postgres' if 'postgres:17-alpine' in args else 'owned-redis' if 'redis:7-alpine' in args else 'owned-app')
elif args and args[0]=='run' and 'upgrade' in args and os.environ.get('FAIL_TEST_MIGRATION')=='1':sys.exit(17)
''')
    fake.chmod(0o755)
    git=tmp_path/'git'
    git.write_text('''#!/usr/bin/env python3
import io, os, sys, tarfile
args=sys.argv[1:]
if args==['rev-parse','--show-toplevel']:print(os.environ['RUNNER_TEST_ROOT'])
elif 'archive' in args:
    with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
        content=b'FROM python:3.12-slim\\n'
        info=tarfile.TarInfo('Dockerfile');info.size=len(content)
        archive.addfile(info,io.BytesIO(content))
''')
    git.chmod(0o755)
    log=tmp_path/'calls.jsonl'
    commit='a'*40
    env={**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ['PATH'],
         'DOCKER_TEST_LOG':str(log),'RUNNER_TEST_ROOT':str(ROOT),
         'FAIL_TEST_MIGRATION':'1' if fail_migration else '0'}
    result=subprocess.run(['bash',str(RUNNER),commit],cwd=ROOT,env=env,text=True,capture_output=True)
    assert result.returncode==(17 if fail_migration else 0),result.stderr
    calls=[json.loads(line) for line in log.read_text().splitlines()]
    network=next(c for c in calls if c[:2]==['network','create'])
    assert '--internal' in network
    assert all('--publish' not in c and '-p' not in c and '--network=host' not in c for c in calls)
    removals=[c for c in calls if c and c[0]=='rm']
    removed={c[-1] for c in removals}
    assert removed==({'owned-postgres','owned-redis'} if fail_migration else {'owned-postgres','owned-redis','owned-app'})
    assert all('-v' in c for c in removals)  # Remove only disposable anonymous volumes too.
    assert ['network','rm','owned-network'] in calls
    assert not any('compose' in c for c in calls)
    assert '.env.oracle' not in '\n'.join(' '.join(c) for c in calls)
    assert ('PASS:' in result.stdout) is not fail_migration


def test_runner_rejects_unpinned_ref_before_docker():
    result=subprocess.run(['bash',str(RUNNER),'main'],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==2 and 'full-40-character-commit' in result.stderr
