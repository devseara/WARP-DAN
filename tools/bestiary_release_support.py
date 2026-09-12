"""Bestiary release preflight and additive SQL installation; never stop services."""
from pathlib import Path
import hashlib,json,subprocess,re

TABLES={
'bestiary_streams':['stream','sequence'],
'bestiary_accounts':['account_id','revision'],
'bestiary_progress':['account_id','mob_id','kills','first_seen','last_seen'],
'bestiary_milestones':['account_id','source','target','tier','points','earned'],
'bestiary_claims':['account_id','reward_id','reward_version','claimed','recipient','mail_id'],
'bestiary_entitlements':['account_id','kind','entitlement_id'],
'bestiary_preferences':['account_id','mob_id','favorite','tracked']}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def require_stopped():
    script="Get-CimInstance Win32_Process -Filter \"name='map-server.exe' OR name='char-server.exe' OR name='MSBuild.exe' OR name='cl.exe' OR name='link.exe'\" | Select-Object Name,ProcessId | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,check=True)
    if result.stdout.strip():raise RuntimeError('Stop map/char services and finish concurrent builds before installation: '+result.stdout.strip())

def connection_settings(server):
    values={};seen=set()
    def read(path):
        path=path.resolve()
        if path in seen or not path.is_file():return
        seen.add(path)
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('//') or ':' not in line:continue
            key,value=line.split(':',1);key=key.strip();value=value.split('//',1)[0].strip()
            if key=='import':read(server/value)
            else:values[key]=value
    read(server/'conf/inter_athena.conf')
    return dict(host=values['char_server_ip'],port=int(values['char_server_port']),user=values['char_server_id'],password=values['char_server_pw'],database=values['char_server_db'],charset='utf8mb4',autocommit=True)

def migrate(server,build):
    import pymysql
    require_stopped();cfg=connection_settings(server);migration=server/'sql-files/upgrades/2026-09-12-bestiary-research.sql'
    connection=pymysql.connect(**cfg);existing={}
    try:
        with connection.cursor() as cur:
            for table in [*TABLES,'mail','mail_attachments']:
                cur.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',(table,));row=cur.fetchone()
                if row:
                    if row[0]!='InnoDB':raise RuntimeError('Nontransactional table: '+table)
                    cur.execute('SHOW CREATE TABLE `'+table+'`');existing[table]=cur.fetchone()[1]
                    if table in TABLES:
                        cur.execute('SHOW COLUMNS FROM `'+table+'`');assert [r[0] for r in cur.fetchall()]==TABLES[table],table+' schema mismatch'
                elif table in ['mail','mail_attachments']:raise RuntimeError('Missing normal mail schema: '+table)
            (build/'sql-schema-before.json').write_text(json.dumps(existing,indent=2),encoding='utf-8')
            for statement in migration.read_text(encoding='utf-8').split(';'):
                statement=re.sub(r'--[^\n]*','',statement).strip()
                if statement:
                    if not statement.startswith('CREATE TABLE IF NOT EXISTS bestiary_'):raise RuntimeError('Migration must remain strictly additive')
                    cur.execute(statement)
            for table,columns in TABLES.items():
                cur.execute('SHOW COLUMNS FROM `'+table+'`');assert [r[0] for r in cur.fetchall()]==columns
                cur.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',(table,));assert cur.fetchone()[0]=='InnoDB'
    finally:connection.close()
    report={'migration_sha256':sha(migration),'created_tables':[t for t in TABLES if t not in existing],'verified_tables':list(TABLES),'existing_rows_modified':False}
    (build/'sql-installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report
