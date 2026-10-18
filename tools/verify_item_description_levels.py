"""Exercise equipment level ranges in the fresh x86 renderer, across all panes."""
from verify_item_description_native import VM, WIN
from verify_item_description_components import TripleVM, DETAIL
from verify_item_description_comparison import COMP
from verify_item_description_payload import rows_response, layout_lines


def checks(pe, manifest):
    # Native text receives Windows COLORREF (BGR), converted from the UI RGB.
    blue, red, ink = 0xD67B4C, 0x3F47D9, 0x63524A
    def rows(low, high=None, low_flags=1, high_flags=1):
        result=[(1,0,0,0,0,'Weight','40.0'),(1,0,0,0,0,'Weapon level','1')]
        if low is not None:result.append((10,0,0,low_flags,0,'Base level',str(low)))
        if high is not None:result.append((10,0,0,high_flags,0,'Maximum level',str(high)))
        return result
    def shown(v, window=WIN):
        v.draws=[];v.run('Draw',ecx=window)
        index=next(i for i,d in enumerate(v.draws) if d[1]==124 and d[2]=='Lv.:')
        label,value=v.draws[index:index+2]
        assert label[3:]==(ink,1) and value[4]==1,(label,value)
        assert value[0]>label[0] and value[1]==label[1]
        return value[2],value[3]
    cases=[(1,98,1,1,'1 - 98',blue),(85,98,1,1,'85 - 98',blue),
           (1,98,1,2,'1 - 98',red),(85,98,2,1,'85 - 98',red),
           (1,None,1,1,'1',blue),(85,None,2,1,'85',red),
           (0,None,1,1,'Any',blue),(0,98,1,1,'1 - 98',blue),
           (None,98,1,1,'1 - 98',blue),(1,0,1,2,'1',blue),
           (1,98,1,4,'1',blue),(1,'bad',1,2,'1',blue)]
    count=0
    # Reuse each pane through range/no-range switches to expose stale caches.
    for scope in (0,1,2,3):
        v=VM(pe,manifest)
        for low,high,lf,hf,expected,color in cases:
            v.open(scope=scope);assert v.receive(rows_response(v,rows(low,high,lf,hf)))
            assert shown(v)==(expected,color),(scope,low,high)
            assert not any('Maximum level' in line[-1] for line in layout_lines(v))
            count+=1
    # Approved range fits between the unchanged neighbors at both pane widths.
    for width in (288,360):
        v=VM(pe,manifest);v.open();assert v.receive(rows_response(v,rows(1,98)))
        v.set_size(WIN,[width,560]);assert shown(v)==('1 - 98',blue)
        band=[d for d in v.draws if d[1]==124]
        assert [d[2] for d in band]==['Lv.:','1 - 98','Weapon Lv.:','1','Weight:','40.0']
        # The VM's measured text width is six pixels per character.
        assert all(a[0]+len(a[2])*6<=b[0] for a,b in zip(band,band[1:])),band
    v=TripleVM(pe,manifest);v.open_pair()
    main_request,comparison_request=v.sent[-2:]
    def packet(request, content):
        saved=v.sent;v.sent=[request]
        try:return rows_response(v,content)
        finally:v.sent=saved
    # Open a component from the populated main pane while comparison is pending.
    main_rows=rows(1,98,1,2)+[(8,2,4001,0,1,'Slot 1','Installed card')]
    assert v.receive(packet(main_request,main_rows))
    v.run('Draw');v.click_card()
    v.now+=200;v.run('Process',ecx=DETAIL);component_request=v.sent[-1]
    # The later component reply arrives before the older comparison reply.
    assert v.receive(packet(component_request,rows(0)))
    assert v.receive(packet(comparison_request,rows(85,150)))
    assert shown(v,WIN)==('1 - 98',red)
    assert shown(v,COMP)==('85 - 150',blue)
    assert shown(v,DETAIL)==('Any',blue)
    assert shown(v,WIN)==('1 - 98',red),'another pane overwrote the main range'
    return {'cases':count,'widths':[288,360],'panes':3,
            'checks':['configured range and min-only/Any display','upper/lower eligibility colors',
                      'unknown/invalid/unlimited maximum fallback','all item scopes and cache reset',
                      'out-of-order pane isolation','unchanged font and aligned neighboring fields']}


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    import pefile
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    directory=parser.parse_args().directory
    manifest=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription']
    report=checks(pefile.PE(str(directory/'item-description.exe')),manifest)
    (directory/'level-range-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
