"""Read local Bestiary SQL connection settings without logging credentials."""

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
