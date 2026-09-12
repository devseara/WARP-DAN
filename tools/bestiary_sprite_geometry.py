"""Native SPR/ACT geometry used by synthetic Bestiary rendering."""

def frame_bounds(spr,frame):
    boxes=[]
    for layer in frame.layers:
        if layer.sprite_index<0:continue
        _,w,h=spr.get_rgba(layer.sprite_index,layer.sprite_type)
        assert layer.rotation==0,'Rotated ACT layer needs a transformed bounds calculation'
        w*=abs(layer.scale_x);h*=abs(layer.scale_y)
        boxes.append((layer.x-w/2,layer.y-h/2,layer.x+w/2,layer.y+h/2))
    return (min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))

