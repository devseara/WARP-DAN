"""Shared semantic checks for the emitted inventory/cart category menu code."""
import struct

LABELS=['All Items','Usable','Equipment','Miscelleneous','Card','Ammunition','Costume','Shadow Gear','Pet']

def check_dropdown(m, inventory, output):
    m.inventory([(2,501,12,0,'Red Potion'),(3,1201,1,4,'Knife'),(4,909,5,3,'Jellopy'),
                 (5,4001,1,6,'Poring Card'),(6,1750,91,10,'Arrow'),(7,19500,1,5,'Costume Hat'),
                 (8,24000,1,5,'Shadow Armor'),(9,9001,1,7,'Pet Egg'),(10,10013,1,5,'Pet Accessory'),
                 (11,19501,1,5,'Metadata Costume'),(12,1201,1,4,'Knife')])
    m.w(m.slots[7]+8,0x400);m.w(m.slots[8]+8,0x10000)
    m.pet_eggs.add(9001);m.pet_gear.add(10013);m.costumes.add(19501)
    expected=[list(range(2,13)),[2],[3,12],[4],[5],[6],[7,11],[8],[9,10]]
    cats=[0,1,2,3,4,5,7,8,9] if inventory else list(range(9))
    prefix='inventory' if inventory else 'cart'
    def menu():
        width=m.r(m.obj+0x14);m.click(width-(27 if inventory else 47),35)
        m.texts=[];m.rebuild()
        assert [t[0] for t in m.texts if t[0] in LABELS]==LABELS, 'Nine exact category labels/order'
        assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0, 'Menu exposes an underlying item'
    for row,(cat,slots) in enumerate(zip(cats,expected)):
        menu()
        m.click(80,52+row*24);m.rebuild()
        assert m.state(12)==cat and m.state(20)==len(slots),(prefix,row,m.state(12),m.state(20))
        cols=(m.r(m.obj+0x14)-72)//32
        actual=[struct.unpack_from('<I',m.selected(58+i%cols*32,60+i//cols*32),4)[0] for i in range(len(slots))]
        assert actual==slots,(prefix,row,actual,slots)
    menu();m.preview(output/(prefix+'-nine-categories.png'))
    count=len(m.actions);m.invoke(m.c['right'],m.obj,(90,60));assert len(m.actions)==count, 'Popup right-click activated an item'
    # Right-click may close Cart's menu; use the arrow to reach a known open state.
    m.rebuild()
    if not inventory:menu()
    m.click(80,52+2*24);m.rebuild();m.search('kNi')
    assert m.state(20)==2
    menu();m.click(80,52+8*24);m.rebuild();assert m.state(20)==0, 'Category ignored the active search'
    m.search('');assert m.state(20)==2
    # Dropdown geometry must follow the resized right edge, including the last row.
    m.w(0x955980,1280);m.w(0x95598B,1024)
    m.invoke(m.c['event'],m.obj,(0,14,7,344,328,0));m.rebuild()
    menu();m.click(280,52+8*24);m.rebuild();assert m.state(12)==cats[8] and m.state(20)==2
    # All remains separate from the sidebar-only Favorites category.
    menu();m.click(80,52);m.rebuild();assert m.state(20)==11
    m.preview(output/(prefix+'-filters-resized.png'))
