"""Test the actual char research service against a separately created local SQL database."""
from pathlib import Path
import subprocess,os,json,uuid,re,concurrent.futures
ROOT=Path(__file__).resolve().parents[1]
from bestiary_release_support import connection_settings
import pymysql

def main():
    server=ROOT.parent/'BanquetOfHeroes';out=ROOT/'Outputs/Bestiary/verification/research/sql-test';out.mkdir(parents=True,exist_ok=True)
    source=(server/'src/char/int_mail.cpp').read_text(encoding='utf-8');a=source.index('int32 mail_savemessage_in_transaction(');b=source.index('int32 mail_timer_sub(',a)
    (out/'bestiary_mail_under_test.inc').write_text(source[a:b],encoding='utf-8')
    vc=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Tools/MSVC/14.51.36231');sdk=Path('C:/Program Files (x86)/Windows Kits/10');version='10.0.26100.0'
    env=os.environ.copy();env['INCLUDE']=';'.join(str(p) for p in [vc/'include',sdk/'Include'/version/'ucrt',sdk/'Include'/version/'shared',sdk/'Include'/version/'um'])
    env['LIB']=';'.join(str(p) for p in [vc/'lib/x64',sdk/'Lib'/version/'ucrt/x64',sdk/'Lib'/version/'um/x64'])
    includes=[out,server/'src',server/'3rdparty/mysql/include',server/'3rdparty/rapidyaml/src',server/'3rdparty/rapidyaml/ext/c4core/src',server/'3rdparty/libconfig']
    cmd=[str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++17','/EHsc','/MT','/O2','/Gy','/DWIN32','/D_CRT_SECURE_NO_WARNINGS',*[f'/I{p}' for p in includes],str(ROOT/'tools/native/bestiary_research_sql_test.cpp'),str(server/'src/common/database.cpp'),str(server/'src/common/sql.cpp'),str(server/'src/common/strlib.cpp'),str(server/'.vs/build/ryml.lib'),str(server/'3rdparty/mysql/lib/x64/libmysql.lib'),f'/Fe:{out}/research-sql-test.exe',f'/Fo:{out}/','/link','/OPT:REF','ws2_32.lib']
    run=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True);(out/'build.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError((run.stdout+run.stderr)[-6500:])
    cfg=connection_settings(server);connection=pymysql.connect(**cfg);name='codex_bestiary_v9_'+uuid.uuid4().hex[:12]
    assert re.fullmatch(r'\w+',cfg['database']) and re.fullmatch(r'codex_bestiary_v9_[0-9a-f]{12}',name)
    with connection.cursor() as cur:
        cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
        for table in ['char','mail','mail_attachments']:cur.execute(f'CREATE TABLE `{name}`.`{table}` LIKE `{cfg["database"]}`.`{table}`')
        cur.execute(f'USE `{name}`')
        for statement in (server/'sql-files/upgrades/2026-09-12-bestiary-research.sql').read_text(encoding='utf-8').split(';'):
            statement=re.sub(r'--[^\n]*','',statement).strip()
            if statement:cur.execute(statement)
        cur.execute("INSERT INTO `char` (char_id,account_id,char_num,name) VALUES (2000000,2000000,0,'BestiaryTestA'),(2000001,2000000,1,'BestiaryTestB'),(2000002,2000001,0,'BestiaryOther')")
    # Credentials remain in the child environment; neither argv nor reports contain them.
    env.update(BESTIARY_TEST_HOST=cfg['host'],BESTIARY_TEST_PORT=str(cfg['port']),BESTIARY_TEST_USER=cfg['user'],BESTIARY_TEST_PASSWORD=cfg['password'],BESTIARY_TEST_DB=name)
    env['PATH']=str(server)+os.pathsep+str(server/'3rdparty/mysql/lib/x64')+os.pathsep+env.get('PATH','')
    (out/'fixture.json').write_text(json.dumps({'database':name,'production_modified':False},indent=2),encoding='utf-8')
    def execute(mode):
        result=subprocess.run([str(out/'research-sql-test.exe'),mode],cwd=server,env=env,capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError(f'SQL test {mode} failed {result.returncode}: '+result.stdout+result.stderr)
        return result.stdout.strip()
    # Only these empty cloned test tables are converted; live engines are untouched.
    with connection.cursor() as cur:
        for table in ('mail','mail_attachments'):cur.execute(f'ALTER TABLE `{name}`.`{table}` ENGINE=MyISAM')
    checks=[execute('mail_guard')]
    with connection.cursor() as cur:
        for table in ('mail','mail_attachments'):cur.execute(f'ALTER TABLE `{name}`.`{table}` ENGINE=InnoDB')
    checks += [execute('setup'),execute('expansion')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(execute,['concurrent']*8):pass
    with connection.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM bestiary_claims WHERE account_id=2000000 AND reward_id=4');assert cur.fetchone()[0]==1
        cur.execute('SELECT COUNT(*) FROM mail_attachments a JOIN bestiary_claims c ON c.mail_id=a.id WHERE c.account_id=2000000 AND c.reward_id=4 AND a.nameid=602');assert cur.fetchone()[0]==1
    checks.append('Eight simultaneous actual-service claim processes created one reward claim and one mail attachment.')
    checks.append(execute('claim_all'))
    connection.close()
    report={'passed':True,'checks':checks,'fixture':name,'production_modified':False,'boundaries':'Actual char service, YAML, SQL driver and current mail insertion; socket/log/timer shims.'}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
