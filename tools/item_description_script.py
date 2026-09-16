"""Read-only script structure helpers. Never execute a Ragnarok script.

Keep control statements, strings and comments intact as single units so an
untranslated condition cannot accidentally become an unconditional bonus.
"""
import re


def mask_script(source, strings=False):
    out=list(source);i=0
    while i<len(source):
        if source.startswith('//',i):
            end=source.find('\n',i);end=len(source) if end<0 else end
            for n in range(i,end):out[n]=' '
            i=end
        elif source.startswith('/*',i):
            end=source.find('*/',i+2)
            if end<0:raise ValueError('unterminated comment')
            end+=2
            for n in range(i,end):out[n]=' ' if source[n]!='\n' else '\n'
            i=end
        elif source[i]=='"':
            end=i+1
            while end<len(source):
                if source[end]=='\\':end+=2;continue
                if source[end]=='"':break
                end+=1
            if end>=len(source):raise ValueError('unterminated string')
            if strings:
                for n in range(i,end+1):out[n]=' '
            i=end+1
        else:i+=1
    return ''.join(out)


class ScriptReader:
    def __init__(self,source):
        self.clean=mask_script(source);self.mask=mask_script(source,strings=True)
    def space(self,pos):
        while pos<len(self.mask) and self.mask[pos].isspace():pos+=1
        return pos
    def word(self,pos):
        match=re.match(r'[A-Za-z_]\w*',self.mask[pos:])
        return match[0].lower() if match else ''
    def balanced(self,pos,opening,closing):
        if pos>=len(self.mask) or self.mask[pos]!=opening:raise ValueError('expected '+opening)
        depth=1;pos+=1
        while pos<len(self.mask):
            if self.mask[pos]==opening:depth+=1
            elif self.mask[pos]==closing:
                depth-=1
                if not depth:return pos+1
            pos+=1
        raise ValueError('unbalanced script')
    def statement(self,pos,depth=0):
        if depth>64:raise ValueError('script nesting limit')
        pos=self.space(pos)
        if pos>=len(self.mask):raise ValueError('missing statement')
        if self.mask[pos]=='{':return self.balanced(pos,'{','}')
        word=self.word(pos)
        if word in ('if','for','while','switch'):
            end=self.balanced(self.space(pos+len(word)),'(',')')
            end=self.statement(end,depth+1)
            if word=='if':
                following=self.space(end)
                if self.word(following)=='else':end=self.statement(following+4,depth+1)
            return end
        if word=='do':
            end=self.statement(pos+2,depth+1);following=self.space(end)
            if self.word(following)!='while':raise ValueError('incomplete do/while')
            end=self.balanced(self.space(following+5),'(',')');end=self.space(end)
            if self.mask[end:end+1]!=';':raise ValueError('missing loop terminator')
            return end+1
        parens=0;brackets=0
        for end in range(pos,len(self.mask)):
            char=self.mask[end]
            if char=='(':parens+=1
            elif char==')':parens-=1
            elif char=='[':brackets+=1
            elif char==']':brackets-=1
            elif char in '{}':raise ValueError('unexpected script block')
            elif char==';' and parens==0 and brackets==0:return end+1
            if min(parens,brackets)<0:raise ValueError('unbalanced expression')
        raise ValueError('missing statement terminator')
    def units(self):
        pos=0
        while self.space(pos)<len(self.mask):
            start=self.space(pos);end=self.statement(start)
            yield start,end,self.clean[start:end]
            pos=end


# Unknown flow-changing commands stop extraction. Only these statements/getters
# are known to let subsequent top-level bonuses execute regardless of a branch.
SAFE_COMMANDS={'if','else','bonus','bonus2','bonus3','bonus4','bonus5','skill','addtoskill',
               'autobonus','autobonus2','autobonus3'}
SAFE_CALLS={'if','getrefine','getenchantgrade','getskilllv','readparam','countitem',
            'isequipped','isequippedcnt','getequipid','getequiprefinerycnt','getcharid',
            'getbasejob','getjobname','getgroupid','getrandomoptinfo','strcharinfo','gettime','min','max','pow'}


def continues(script):
    code=mask_script(script,strings=True)
    if re.search(r'\b(?:end|return|goto|close|close2|break|continue|for|while|do|switch|callfunc|callsub)\b',code,re.I):return False
    if re.search(r'(?:^|[;{}])\s*[A-Za-z_]\w*\s*:',code):return False # labels may be reached through unsupported jumps
    calls=re.findall(r'\b([A-Za-z_]\w*)\s*\(',code)
    if any(name.lower() not in SAFE_CALLS for name in calls):return False
    commands=re.findall(r'(?:^|[;{}])\s*(?:else\s+)?([A-Za-z_]\w*)\b',code)
    if any(name.lower() not in SAFE_COMMANDS for name in commands):return False
    return True


def reachable_units(script):
    """Yield complete top-level units only until an unknown control-flow barrier."""
    for start,end,unit in ScriptReader(script).units():
        yield start,end,unit
        if not continues(unit):break
