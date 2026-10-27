#!/usr/bin/env python3
"""Trusted operator worker. No shell commands or container specs from API payloads."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.pending')
    with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as file:
        file.write(value)
    os.replace(temp,path)
    os.chmod(path,0o600)


class Worker:
    def __init__(self,env=None,run=subprocess.run):
        env=os.environ if env is None else env
        self.base=env['ATLAS_PROVISION_API'].rstrip('/')
        parsed=urllib.parse.urlsplit(self.base)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}:
            raise ValueError('NODE_POLICY_INVALID')
        if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost'}):
            raise ValueError('NODE_POLICY_INVALID')
        self.token=env['ATLAS_PROVISION_TOKEN']
        if len(self.token)<32:raise ValueError('NODE_POLICY_INVALID')
        self.root=Path(env['ATLAS_PROVISION_ROOT']).resolve()
        self.source=Path(env['ATLAS_PROVISION_SOURCE']).resolve()
        self.image=env['ATLAS_PROVISION_IMAGE']
        self.network=env['ATLAS_PROVISION_NETWORK']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}',self.image) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',self.network):
            raise ValueError('NODE_POLICY_INVALID')
        self.maximum=int(env.get('ATLAS_PROVISION_MAX_INSTANCES','1'))
        if not 1<=self.maximum<=10:raise ValueError('NODE_POLICY_INVALID')
        self.minimum_memory=int(env.get('ATLAS_PROVISION_MIN_MEMORY_MB','2048'))
        if self.minimum_memory<1024:raise ValueError('NODE_POLICY_INVALID')
        # Operator freezes these hashes during installation, never from a job.
        for relative,key in [('ops/ibkr-user/compose.yml','ATLAS_PROVISION_COMPOSE_SHA256'),
                             ('tools/ibkr_bridge.py','ATLAS_PROVISION_BRIDGE_SHA256')]:
            if hashlib.sha256((self.source/relative).read_bytes()).hexdigest()!=env[key]:
                raise ValueError('NODE_POLICY_INVALID')
        self.run=run
        self.opener=urllib.request.build_opener(NoRedirect)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.root,0o700)

    def api(self,path,payload=None):
        data=json.dumps(payload or {}).encode()
        request=urllib.request.Request(self.base+'/ibkr/onboarding/'+path,data=data,
            headers={'X-Atlas-Provisioner':self.token,'Content-Type':'application/json'},method='POST')
        with self.opener.open(request,timeout=20) as response:
            if response.status==204:return None
            return json.loads(response.read(65536))

    def compose(self,directory,*args):
        # Fixed argv, fixed source, no shell, bounded time, never logs expanded env/secrets.
        command=['docker','compose','--env-file',str(directory/'node.env'),
                 '-p','atlas-ibkr-'+directory.name,
                 '-f',str(self.source/'ops/ibkr-user/compose.yml'),*args]
        self.run(command,check=True,timeout=240,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def provision(self,job):
        key=uuid.UUID(job['job_id']);instance='setup-'+key.hex
        if job.get('instance')!=instance or not re.fullmatch(r'DU[A-Z0-9]{3,32}',job['account_id']):
            raise ValueError('NODE_POLICY_INVALID')
        login=job['login'];name=login['username'];password=login['password'];token=job['bridge_token']
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,128}',name) or not 1<=len(password)<=256 or any(c in password for c in '\x00\r\n') or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):
            raise ValueError('NODE_POLICY_INVALID')
        directory=self.root/instance
        if directory.is_symlink():raise ValueError('NODE_POLICY_INVALID')
        if not directory.exists():
            if len(list(self.root.glob('setup-*')))>=self.maximum:raise ValueError('NODE_CAPACITY')
            available=next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            if available<self.minimum_memory*1024:raise ValueError('NODE_CAPACITY')
            directory.mkdir(mode=0o700)
            atomic(directory/'identity.json',json.dumps({'job_id':str(key),'account_id':job['account_id']}))
        identity=json.loads((directory/'identity.json').read_text())
        if identity!={'job_id':str(key),'account_id':job['account_id']}:raise ValueError('NODE_POLICY_INVALID')
        secret_dir=directory/'secrets';secret_dir.mkdir(exist_ok=True,mode=0o700)
        if secret_dir.is_symlink():raise ValueError('NODE_POLICY_INVALID')
        atomic(secret_dir/'tws_password',password)
        atomic(secret_dir/'bridge_token',token)
        if not (secret_dir/'vnc_password').exists():
            import secrets
            atomic(secret_dir/'vnc_password',secrets.token_hex(4))
        # Derive unique loopback ports from operator-reserved pool; Docker rejects collisions.
        # A persisted port assignment never changes when other instance directories appear.
        port_file=directory/'ports.json'
        if port_file.exists():ports=json.loads(port_file.read_text())
        else:
            allocated={}
            for old in self.root.glob('setup-*/ports.json'):
                allocated.update({p:True for p in json.loads(old.read_text()).values()})
            pair=next(((19000+i,20000+i) for i in range(self.maximum)
                       if 19000+i not in allocated and 20000+i not in allocated),None)
            if pair is None:raise ValueError('NODE_CAPACITY')
            ports={'vnc':pair[0],'bridge':pair[1]};atomic(port_file,json.dumps(ports))
        values={'IBKR_INSTANCE':instance,'TWS_USERID':name,'IBKR_ACCOUNT_ID':job['account_id'],
                'IBKR_SECRET_DIR':str(secret_dir),'IBKR_BRIDGE_SOURCE':str(self.source/'tools/ibkr_bridge.py'),
                'IBKR_VNC_HOST_PORT':str(ports['vnc']),'IBKR_BRIDGE_HOST_PORT':str(ports['bridge']),
                'ATLAS_APP_IMAGE':self.image,'ATLAS_APP_NETWORK':self.network,'READ_ONLY_API':'no'}
        if any('\n' in v or '\r' in v or '$' in v for v in values.values()):raise ValueError('NODE_POLICY_INVALID')
        atomic(directory/'node.env',''.join(k+'='+v+'\n' for k,v in values.items()))
        self.compose(directory,'config','--quiet')
        self.compose(directory,'up','-d','--force-recreate','settings-init','ib-gateway')
        # The bridge retries until the owner approves broker login; do not wait for MFA here.
        self.compose(directory,'up','-d','--no-deps','--force-recreate','bridge')

    def once(self):
        job=self.api('worker/claim')
        if not job:return
        code=None
        try:self.provision(job)
        except ValueError as exc:code=str(exc) if str(exc) in {'NODE_CAPACITY','NODE_POLICY_INVALID'} else 'NODE_START_FAILED'
        except Exception:code='NODE_START_FAILED'
        payload={'lease_token':job['lease_token'],'outcome':'FAILED' if code else 'STARTED','error_code':code}
        # Retrying acknowledgments never reruns Docker. Unknown completion stays leased.
        for attempt in range(3):
            try:
                self.api('worker/'+job['job_id']+'/ack',payload)
                print(json.dumps({'job_id':job['job_id'],'status':code or 'LOGIN_REQUIRED'}),flush=True)
                return
            except urllib.error.HTTPError as exc:
                if exc.code==409:return
            except Exception:pass
        print('ACK_FAILED_REQUIRES_OPERATOR_REVIEW',flush=True)


def main():
    import fcntl
    os.umask(0o077)
    worker=Worker()
    lock=(worker.root/'worker.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        try:worker.once()
        except Exception:print('WORKER_REQUEST_FAILED',flush=True)
        time.sleep(30)


if __name__=='__main__':main()
