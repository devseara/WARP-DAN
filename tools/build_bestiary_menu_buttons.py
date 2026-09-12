"""Export the illustrated Bestiary icon into native Renewal/Classic BMP states.

Artwork is generated with imagegen; this script performs deterministic sizing,
color-key conversion and composition with the extracted native Classic frame.
It does not draw substitute button chrome or redraw the journal artwork.
"""
from pathlib import Path
import hashlib,json
from PIL import Image, ImageDraw, ImageEnhance

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'Images/BestiaryUI/source/menuicon'
STATES=('normal','mouseon','pressed')
KEY=(255,0,255)


def alpha_image(bitmap):
    image=bitmap.convert('RGBA')
    pixels=list(image.get_flattened_data())
    image.putdata([(r,g,b,0 if (r>=248 and g<4 and b>=248) else 255) for r,g,b,_ in pixels])
    return image


def button(width,height,state):
    classic=width==32
    with Image.open(SOURCE/'journal-native.png') as source:
        source=source.convert('RGBA')
        bounds=source.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
        if not bounds:raise ValueError('Journal source has no visible artwork')
        icon=source.crop(bounds)
    icon.thumbnail((23,24) if classic else (34,34),Image.Resampling.LANCZOS)
    if state!='normal':
        alpha=icon.getchannel('A')
        icon=ImageEnhance.Brightness(icon.convert('RGB')).enhance(1.15 if state=='mouseon' else 0.88).convert('RGBA')
        icon.putalpha(alpha)
    if classic:
        with Image.open(SOURCE/f'classic_frame_{state}.bmp') as frame:output=frame.convert('RGB')
        assert output.size==(32,34)
    else:
        output=Image.new('RGB',(width,height),KEY)
    x=(width-icon.width)//2+(1 if classic and state=='pressed' else 0)
    y=(height-icon.height)//2+(1 if state=='pressed' else 0)
    mask=icon.getchannel('A').point(lambda a:255 if a>=128 else 0)
    output.paste(icon.convert('RGB'),(x,y),mask)
    # Native RGB565 loading treats this entire bucket as color-key pixels.
    assert not any(r>=248 and g<4 and b>=248 and (r,g,b)!=KEY for r,g,b in output.get_flattened_data())
    return output


def main():
    out=ROOT/'Images/BestiaryUI/menuicon';out.mkdir(parents=True,exist_ok=True)
    review=ROOT/'Outputs/Bestiary';review.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(610,350),'#24232a');draw=ImageDraw.Draw(sheet)
    manifest={'source_sha256':hashlib.sha256((SOURCE/'journal-native.png').read_bytes()).hexdigest(),'files':{}}
    for row,(theme,width,height,prefix) in enumerate([('Renewal',45,41,''),('Classic',32,34,'old_')]):
        draw.text((14,row*170+8),theme+' / normal, hover, pressed',fill='white')
        for col,state in enumerate(STATES):
            im=button(width,height,state);name=f'bt_bestiary_{prefix}{state}.bmp';im.save(out/name)
            display=alpha_image(im)
            sheet.paste(display.resize((width*3,height*3),Image.Resampling.NEAREST),(14+col*155,32+row*170),display.resize((width*3,height*3),Image.Resampling.NEAREST))
            sheet.paste(display,(498,42+row*170+col*42),display)
            manifest['files'][name]={'size':[width,height],'sha256':hashlib.sha256((out/name).read_bytes()).hexdigest()}
    sheet.save(review/'menu-button-preview.png')
    # Comparison uses real native assets at 1x and 3x; it is an asset preview.
    comparison=Image.new('RGB',(610,350),'#24232a');d=ImageDraw.Draw(comparison)
    for row,prefix in enumerate(('', 'old_')):
        d.text((14,8+row*170),('Renewal' if not prefix else 'Classic')+' / native icons + Bestiary',fill='white')
        names=[f'bt_{n}_{prefix}normal.bmp' for n in ('quest','item','skill','achievement')]
        images=[Image.open(SOURCE/n).convert('RGB') for n in names]
        images.append(Image.open(out/f'bt_bestiary_{prefix}normal.bmp').convert('RGB'))
        for col,im in enumerate(images):
            display=alpha_image(im);large=display.resize((im.width*2,im.height*2),Image.Resampling.NEAREST)
            comparison.paste(large,(14+col*118,29+row*170),large)
            comparison.paste(display,(40+col*118,119+row*170),display)
    comparison.save(review/'menu-native-comparison.png')
    (review/'native-button-assets.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Exported six native-style Bestiary button BMPs and native-icon comparisons.')

if __name__=='__main__':main()
