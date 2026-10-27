import hashlib
import importlib.util
import json
from pathlib import Path
import uuid
import pytest

spec=importlib.util.spec_from_file_location('provisioner',Path('ops/ibkr-user/provisioner.py'))
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)


@pytest.fixture
def configured(tmp_path,monkeypatch):
    source=tmp_path/'source'
    for relative in ['ops/ibkr-user/compose.yml','tools/ibkr_bridge.py']:
        file=source/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('trusted-source')
    env={'ATLAS_PROVISION_API':'http://127.0.0.1:8100','ATLAS_PROVISION_TOKEN':'t'*48,
         'ATLAS_PROVISION_ROOT':str(tmp_path/'nodes'),'ATLAS_PROVISION_SOURCE':str(source),
         'ATLAS_PROVISION_IMAGE':'sha256:'+'a'*64,'ATLAS_PROVISION_NETWORK':'app-private',
         'ATLAS_PROVISION_COMPOSE_SHA256':hashlib.sha256(b'trusted-source').hexdigest(),
         'ATLAS_PROVISION_BRIDGE_SHA256':hashlib.sha256(b'trusted-source').hexdigest(),
         'ATLAS_PROVISION_MIN_MEMORY_MB':'1024'}
    original=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda self,*a,**kw:'MemAvailable: 999999999 kB' if str(self)=='/proc/meminfo' else original(self,*a,**kw))
    commands=[]
    instance=worker.Worker(env,run=lambda command,**kw:commands.append((command,kw)))
    key=uuid.uuid4()
    job={'job_id':str(key),'instance':'setup-'+key.hex,'account_id':'DUALICE123',
         'login':{'username':'paper_alice','password':'password-$(never-executed)'},'bridge_token':'x'*48,'lease_token':'l'*48}
    return instance,job,commands,env


def test_fixed_commands_permissions_and_stable_instance_retry(configured):
    w,job,commands,_=configured
    w.provision(job);w.provision(job)
    assert len(list(w.root.glob('setup-*')))==1
    assert len(commands)==6
    for command,options in commands:
        assert command[:2]==['docker','compose']
        assert options['timeout']==240 and options['check'] is True
        assert 'shell' not in options
        assert not any('password-' in arg for arg in command)
        assert 'atlas-ibkr-'+job['instance'] in command
        assert not any('down'==arg or 'prune'==arg for arg in command)
    secrets=w.root/job['instance']/'secrets'
    assert (secrets/'tws_password').read_text()==job['login']['password']
    assert (secrets/'tws_password').stat().st_mode&0o777==0o600
    assert secrets.stat().st_mode&0o777==0o700
    assert 'READ_ONLY_API=no' in (secrets.parent/'node.env').read_text()


def test_capacity_refuses_second_instance_without_touching_first(configured):
    w,job,commands,_=configured;w.provision(job);commands.clear()
    key=uuid.uuid4();other={**job,'job_id':str(key),'instance':'setup-'+key.hex}
    with pytest.raises(ValueError,match='NODE_CAPACITY'):w.provision(other)
    assert not commands


@pytest.mark.parametrize('field,value',[('instance','atlas-markets-prod-app'),('account_id','U_LIVE'),('job_id','../../etc')])
def test_api_payload_cannot_select_existing_production_resource(configured,field,value):
    w,job,commands,_=configured;job[field]=value
    with pytest.raises(ValueError):w.provision(job)
    assert not commands


def test_no_plain_http_remote_or_mutated_sources(configured):
    _,_,_,env=configured
    with pytest.raises(ValueError):worker.Worker({**env,'ATLAS_PROVISION_API':'http://remote.example'})
    with pytest.raises(ValueError):worker.Worker({**env,'ATLAS_PROVISION_COMPOSE_SHA256':'changed'})


def test_ack_retry_never_repeats_container_creation(configured,monkeypatch):
    w,job,commands,_=configured;acks=[]
    def api(path,payload=None):
        if path=='worker/claim':return job
        acks.append(path)
        if len(acks)<3:raise TimeoutError
    monkeypatch.setattr(w,'api',api)
    w.once()
    assert len(commands)==3 and len(acks)==3
