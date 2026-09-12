"""Activate a verified local Bestiary expansion with backups and zero-player gating.

Only the known mapserv/charserv batch supervisors may be stopped. Servers receive
one graceful Ctrl+C request; no server is force-killed. Mail rows and WALs are
preserved. This command never resets research progress or claim receipts.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
import pymysql
from bestiary_release_support import connection_settings

ROOT=Path(__file__).resolve().parents[1]

def ps(code):
    r=subprocess.run(['powershell','-NoProfile','-Command',code],capture_output=True,text=True,check=True)
    return r.stdout.strip()

def quote(value):return "'"+str(value).replace("'","''")+"'"
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def processes():
    raw=ps("Get-CimInstance Win32_Process -Filter \"name='map-server.exe' OR name='char-server.exe' OR name='login-server.exe' OR name='cmd.exe'\" | Select-Object Name,ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
    data=json.loads(raw) if raw else [];return data if isinstance(data,list) else [data]

def table_snapshot(connection,table):
    with connection.cursor() as cur:
        cur.execute('SHOW KEYS FROM `'+table+'` WHERE Key_name=\'PRIMARY\'');keys=sorted(cur.fetchall(),key=lambda row:row[3]);columns=[r[4] for r in keys]
        if not columns:raise RuntimeError('Mail table lacks a primary key: '+table)
        order=','.join('`'+c.replace('`','``')+'`' for c in columns)
        cur.execute('SELECT * FROM `'+table+'` ORDER BY '+order);rows=cur.fetchall()
    raw=json.dumps(rows,default=lambda x:x.hex() if isinstance(x,bytes) else str(x),ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}

def engines(connection):
    with connection.cursor() as cur:
        cur.execute("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('mail','mail_attachments')")
        result=dict(cur.fetchall())
    if set(result)!={'mail','mail_attachments'} or any(e not in ('MyISAM','InnoDB') for e in result.values()):raise RuntimeError('Unexpected mail tables or engines')
    return result

def start(server,name,logs):
    wrapper={'login-server.exe':'logserv.bat','char-server.exe':'charserv.bat','map-server.exe':'mapserv.bat'}[name]
    stdout=logs/(name+'.out.log');stderr=logs/(name+'.err.log')
    code='Start-Process -FilePath '+quote(os.environ.get('COMSPEC','C:/Windows/System32/cmd.exe'))+' -ArgumentList '+quote('/k '+wrapper+' on')+' -WorkingDirectory '+quote(server)+' -WindowStyle Hidden -RedirectStandardOutput '+quote(stdout)+' -RedirectStandardError '+quote(stderr)+' -PassThru | Select-Object -ExpandProperty Id'
    # A detached Windows descendant can inherit anonymous capture pipes and
    # keep communicate() waiting after PowerShell exits. Use files for launch.
    launch_out=logs/(name+'.launcher.stdout');launch_err=logs/(name+'.launcher.stderr')
    with launch_out.open('w',encoding='utf-8') as stdout, launch_err.open('w',encoding='utf-8') as stderr:
        subprocess.run(['powershell','-NoProfile','-Command',code],stdout=stdout,stderr=stderr,check=True)
    return int(launch_out.read_text(encoding='utf-8').strip())

def wait_ready(server,name,logs,needle,timeout=90):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        output=''.join(p.read_text(encoding='utf-8',errors='replace') for p in logs.glob(name+'.*.log'))
        clean=re.sub(r'\x1b\[[0-9;]*m','',output)
        if needle in clean:
            matches=[p for p in processes() if p['Name']==name and Path(p['ExecutablePath']).resolve()==server/name]
            if len(matches)==1:return {'pid':matches[0]['ProcessId'],'ready_line':next(line for line in clean.splitlines() if needle in line)}
        if 'Bestiary research disabled:' in clean or 'Bestiary persistence handshake/commit failed' in clean:raise RuntimeError('Bestiary initialization failed; inspect '+str(logs))
        time.sleep(0.5)
    raise RuntimeError(name+' readiness timed out; inspect '+str(logs))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');ap.add_argument('--build',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--activate',action='store_true');ap.add_argument('--start-login',action='store_true',help='Explicitly authorized startup of an already-stopped local login server');args=ap.parse_args()
    server=args.server.resolve();build=args.build.resolve();out=args.output.resolve()
    proof=json.loads((build/'build-result.json').read_text(encoding='utf-8'));assert proof['passed']
    assert all(digest(server/name)==sha for name,sha in proof['source_sha256'].items()),'Sources changed after verification build'
    for row in proof['targets']:assert digest(Path(row['binary']))==row['sha256']
    for part in ['research/core-test','research/sql-test','native/yaml-test']:
        result=json.loads((ROOT/'Outputs/Bestiary/verification'/part/'verification.json').read_text(encoding='utf-8'));assert result['passed']
    cfg=connection_settings(server);connection=pymysql.connect(**cfg)
    with connection.cursor() as cur:cur.execute('SELECT COUNT(*) FROM `char` WHERE online<>0');online=cur.fetchone()[0]
    if online:raise RuntimeError('Refusing maintenance while characters are online: '+str(online))
    all_processes=processes();targets={}
    for name,wrapper in [('map-server.exe','mapserv.bat'),('char-server.exe','charserv.bat')]:
        matches=[p for p in all_processes if p['Name']==name and p['ExecutablePath'] and Path(p['ExecutablePath']).resolve()==server/name]
        shell=re.escape(os.environ.get('COMSPEC','C:/Windows/System32/cmd.exe'))
        expected=re.compile(r'^(?:cmd(?:\.exe)?|"'+shell+r'"|'+shell+r')\s+/k\s+'+re.escape(wrapper)+r'\s+on\s*$',re.I)
        if not matches:
            if any(p['Name'].lower()=='cmd.exe' and expected.fullmatch(p['CommandLine'] or '') for p in all_processes):raise RuntimeError('Auto-restart supervisor active without its server; wait for it before activation')
            targets[name]=(None,None);continue
        if len(matches)!=1:raise RuntimeError('Expected at most one local '+name)
        process=matches[0];parent=next((p for p in all_processes if p['ProcessId']==process['ParentProcessId']),None)
        if not parent or parent['Name'].lower()!='cmd.exe' or not expected.fullmatch(parent['CommandLine'] or ''):raise RuntimeError('Unrecognized server supervisor; refusing to stop it')
        targets[name]=(process,parent)
    before_engines=engines(connection)
    dump=Path('C:/Users/Administrator/Documents/Ragnarok/03_laragon/bin/mysql/mariadb-10.6.3-winx64/bin/mysqldump.exe');assert dump.is_file()
    if not args.activate:
        print(json.dumps({'ready':True,'online':online,'mail_engines':before_engines,'targets':{k:(v[0]['ProcessId'] if v[0] else None) for k,v in targets.items()},'activation_requested':False}));connection.close();return
    out.mkdir(parents=True,exist_ok=False);backup=out/'backup';backup.mkdir();logs=out/'logs';logs.mkdir()
    manifest={'server':str(server),'stage':'preflight','mail_engines_before':before_engines,'original_processes':{k:({'pid':v[0]['ProcessId'],'supervisor':v[1]['ProcessId']} if v[0] else None) for k,v in targets.items()},'running_binaries_before':{name:digest(server/name) for name in targets},'forced_server_termination':False}
    def record(stage):manifest['stage']=stage;(out/'deployment.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(stage,flush=True)
    for name in targets:
        shutil.copy2(server/name,backup/name)
        pdb=(server/name).with_suffix('.pdb')
        if pdb.exists():shutil.copy2(pdb,backup/pdb.name)
    shutil.copy2(server/'db/bestiary_research.yml',backup/'expanded-bestiary_research.yml')
    record('backups-prepared')
    for name,(process,parent) in targets.items():
        if process is None:
            record(name+'-already-stopped');continue
        # Stop only the whitelisted auto-restart shell, leaving its server alive.
        ps('Stop-Process -Id '+str(parent['ProcessId'])+' -ErrorAction Stop')
        subprocess.run([sys.executable,str(ROOT/'tools/bestiary_console_control.py'),str(process['ProcessId']),'--stop'],check=True)
        until=time.monotonic()+90
        while any(p['ProcessId']==process['ProcessId'] for p in processes()):
            if time.monotonic()>until:raise RuntimeError('Graceful shutdown timed out; no force termination: '+name)
            time.sleep(0.25)
        record(name+'-stopped-gracefully')
    assert not any(p['Name'] in targets and p['ExecutablePath'] and Path(p['ExecutablePath']).resolve().parent==server for p in processes())
    for path in (server/'save').glob('bestiary-*'):
        if path.is_dir():shutil.copytree(path,backup/'wal'/path.name)
    before={table:table_snapshot(connection,table) for table in before_engines};manifest['mail_rows_before']=before
    env=os.environ.copy();env['MYSQL_PWD']=cfg['password']
    command=[str(dump),'--host='+cfg['host'],'--port='+str(cfg['port']),'--user='+cfg['user'],'--protocol=tcp','--skip-lock-tables','--skip-comments','--result-file='+str(backup/'mail-before.sql'),cfg['database'],'mail','mail_attachments']
    result=subprocess.run(command,env=env,capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Mail backup failed: '+result.stderr)
    assert (backup/'mail-before.sql').stat().st_size>0;manifest['mail_backup_sha256']=digest(backup/'mail-before.sql');record('mail-backed-up')
    with connection.cursor() as cur:
        for table,engine in before_engines.items():
            if engine!='InnoDB':cur.execute('ALTER TABLE `'+table+'` ENGINE=InnoDB')
    after={table:table_snapshot(connection,table) for table in before_engines};assert before==after,'Mail row identity changed during engine conversion'
    assert all(engine=='InnoDB' for engine in engines(connection).values());manifest['mail_rows_after']=after;record('mail-converted-and-verified')
    for row in proof['targets']:
        path=Path(row['binary'])
        if path.name not in targets:continue
        shutil.copy2(path,server/path.name)
        if path.with_suffix('.pdb').exists():shutil.copy2(path.with_suffix('.pdb'),server/path.with_suffix('.pdb').name)
        assert digest(server/path.name)==row['sha256']
    record('binaries-installed')
    if args.start_login:
        login=[p for p in processes() if p['Name']=='login-server.exe' and p['ExecutablePath'] and Path(p['ExecutablePath']).resolve()==server/'login-server.exe']
        if not login:
            manifest['login_supervisor']=start(server,'login-server.exe',logs)
            manifest['login']=wait_ready(server,'login-server.exe',logs,'The login-server is ready')
    manifest['char_supervisor']=start(server,'char-server.exe',logs)
    manifest['char']=wait_ready(server,'char-server.exe',logs,'Bestiary account research ready')
    manifest['map_supervisor']=start(server,'map-server.exe',logs)
    manifest['map']=wait_ready(server,'map-server.exe',logs,'Bestiary research synchronized')
    manifest['mail_engines_after']=engines(connection);connection.close();record('active-and-synchronized')

if __name__=='__main__':main()
