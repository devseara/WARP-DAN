[CmdletBinding()]
param([string]$PackRoot = (Join-Path $PSScriptRoot '..\Images\CollectionUI'))
# Offline layout preview, using production BMPs and the QJS palette; not a live screenshot.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$pack = [IO.Path]::GetFullPath($PackRoot)
$source = [IO.File]::ReadAllText((Join-Path $PSScriptRoot '../Scripts/Patches/ItemCollectionUI.qjs'))
$palette = @{}
$paletteSource = [regex]::Match($source,'ItemCollectionUIStatic.Palette = \{([^}]+)\}').Groups[1].Value
foreach ($m in [regex]::Matches($paletteSource,'(\w+): 0xFF([0-9A-F]{6})')) {
	$palette[$m.Groups[1].Value] = [Drawing.ColorTranslator]::FromHtml('#'+$m.Groups[2].Value)
}
$font = [Drawing.Font]::new('Tahoma',11,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
$bold = [Drawing.Font]::new('Tahoma',11,[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
$bmp = [Drawing.Bitmap]::new(760,540)
$g = [Drawing.Graphics]::FromImage($bmp)
$g.TextRenderingHint = [Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
function Fill([string]$Name,[int]$X,[int]$Y,[int]$W,[int]$H) {
	$b = [Drawing.SolidBrush]::new($palette[$Name]); try { $g.FillRectangle($b,$X,$Y,$W,$H) } finally { $b.Dispose() }
}
function Label([string]$Text,[int]$X,[int]$Y,[string]$Color='Text',[bool]$Strong=$false) {
	$b = [Drawing.SolidBrush]::new($palette[$Color]); try { $g.DrawString($Text, $(if($Strong){$bold}else{$font}),$b,$X,$Y) } finally { $b.Dispose() }
}
function Center([string]$Text,[int]$X,[int]$Y,[int]$Width,[string]$Color='Text') {
	$size = $g.MeasureString($Text,$font); Label $Text ([int]($X+($Width-$size.Width)/2)) $Y $Color
}
function Asset([string]$Relative,[int]$X,[int]$Y,[bool]$Key=$true) {
	$image = [Drawing.Bitmap]::new((Join-Path $pack $Relative))
	try { if($Key){$image.MakeTransparent([Drawing.Color]::Magenta)}; $g.DrawImageUnscaled($image,$X,$Y) } finally { $image.Dispose() }
}
function Panel([int]$X,[int]$Y,[int]$W,[int]$H) {
	Fill Border ($X+2) $Y ($W-4) $H; Fill Border $X ($Y+2) $W ($H-4)
	Fill Panel ($X+2) ($Y+1) ($W-4) ($H-2); Fill Panel ($X+1) ($Y+2) ($W-2) ($H-4)
	Fill Highlight ($X+3) ($Y+2) ($W-6) 1
}
function Button([string]$Text,[int]$X,[int]$Y,[int]$W,[string]$State='out') {
	Asset "chrome/buttons/btn_$($State)_left.bmp" $X $Y
	$mid = [Drawing.Bitmap]::new((Join-Path $pack "chrome/buttons/btn_$($State)_mid.bmp"))
	try {
		for($x1=$X+6; $x1 -lt $X+$W-6; $x1+=6) {
			$width = [Math]::Min(6,$X+$W-6-$x1)
			$g.DrawImage($mid,[Drawing.Rectangle]::new($x1,$Y,$width,20),0,0,$width,20,[Drawing.GraphicsUnit]::Pixel)
		}
	} finally { $mid.Dispose() }
	Asset "chrome/buttons/btn_$($State)_right.bmp" ($X+$W-6) $Y
	Center $Text $X ($Y+2) $W
}
function Shell([int]$Tab) {
	Asset 'chrome/bg_collection.bmp' 0 17 $false; Asset 'chrome/title_bar_760.bmp' 0 0 $false
	Asset 'icons/icon_collection.bmp' 5 0
	Label 'ITEM COLLECTION' 27 1 'Highlight' $true; Asset 'source/native_close/sys_close_off.png' 744 3
	Panel 8 24 744 32; Panel 8 89 522 414; Panel 538 89 214 414; Panel 8 508 744 24
	Label 'Collected 128 / 642' 18 31; Fill Track 160 35 360 9; Fill TrackEdge 160 35 360 1; Fill Progress 160 36 72 8
	Panel 548 31 170 18; Label 'Search item name or ID' 551 33 'Muted'; Asset 'reused/search/btn_searchbar_normal.bmp' 718 31
	Asset 'chrome/poring_small.bmp' 539 56; Label "Poring's Collection" 574 59 'Text' $true
	Label 'A little treasure, every day.' 574 73 'Muted'
	$i=0; foreach($tabInfo in @(@('Items',8,108),@('Combo Collections',116,132),@('Total Bonuses',248,108))) {
		Button $tabInfo[0] $tabInfo[1] 62 $tabInfo[2] $(if($i -eq $Tab){'press'}else{'out'}); $i++
	}
	Label 'Item Collection is account-wide.' 18 514 'Secondary'; Label 'Zeny' 590 514 'Secondary'
	Asset 'reused/currency/icon_zeny.bmp' 628 507; Label '1,250,000' 663 514
}
try {
	Shell 0; Panel 360 62 170 23; Label 'All Items' 371 67; Label 'v' 516 67
	$i=0; foreach($label in @('All','Missing','Partial','Completed')) { Button $label (13+$i*101) 92 96 $(if($i-eq 0){'press'}else{'out'}); $i++ }
	$names=@('Poring Card','Knife','Cotton Shirt','Guard','Ribbon','Muffler','Shoes','Clip','Red Potion','Jellopy','Arrow','Apple','Blue Potion','Pearl','Emperium')
	$icons=@('card','weapon','armor','shield','headgear','garment','shoes','accessory','consumable','etc','ammo','pet','consumable','etc','cash')
	for($i=0;$i-lt 15;$i++) {
		$x=18+($i%5)*96; $y=132+[int][Math]::Floor($i/5)*131
		Panel ($x-5) ($y-18) 85 130
		if($i-eq 0){ Fill Selection ($x-6) ($y-19) 87 1; Fill Selection ($x-6) ($y+112) 87 1; Fill Selection ($x-6) ($y-19) 1 132; Fill Selection ($x+80) ($y-19) 1 132 }
		Label $names[$i] $x ($y-16)
		Asset "icons/category_$($icons[$i]).bmp" ($x+25) ($y+38)
		if($i%3-eq 0){ Asset 'icons/badge_complete.bmp' ($x+59) ($y+2) } elseif($i%3-eq 2){ Asset 'icons/badge_locked.bmp' ($x+59) ($y+2) }
		Fill Track ($x+1) ($y+102) 73 9; Fill TrackEdge ($x+1) ($y+102) 73 1
		$count=@(10,4,0)[$i%3]; if($count-gt 0){Fill Progress ($x+1) ($y+103) ([int](73*$count/10)) 8}; Center "$count / 10" $x ($y+101) 75
	}
	Fill ScrollTrack 516 128 9 352; Asset 'reused/scrollbar/btn_scroll_arrow_up.bmp' 516 116
	Asset 'reused/scrollbar/btn_scroll_arrow_down.bmp' 516 480
	Fill Border 516 128 9 24
	Center 'Poring Card' 548 99 194; Asset 'icons/category_card.bmp' 632 164
	Label 'Item ID 4001' 548 236 'Secondary'; Label '10 / 10 deposited' 548 254 'Secondary'
	Label 'Collection Bonus' 548 292 'Heading' $true; Fill Line 548 311 194 1; Label 'LUK +1' 554 320
	Label 'Deposit 100 / Withdraw 0 Zeny' 548 365
	Panel 603 390 86 24; Center '1' 603 393 86
	Asset 'reused/steppers/btn_minus_normal.bmp' 577 394; Asset 'reused/steppers/btn_plus_normal.bmp' 695 394
	Button 'Deposit' 553 422 184; Button 'Deposit All' 553 446 184 'over'; Button 'Withdraw' 553 470 184
	$bmp.Save((Join-Path $pack 'preview/chibi-items.png'),[Drawing.Imaging.ImageFormat]::Png)
	Shell 2
	Label 'Active Collection Bonuses' 23 105 'Text' $true
	$i=0; foreach($bonus in @(@('Maximum HP','+500'),@('Maximum SP','+80'),@('STR','+3'),@('AGI','+2'),@('VIT','+2'),@('INT','+3'),@('DEX','+2'),@('LUK','+1'))) {
		$y=130+$i*18; if($i%2){Fill AlternateRow 18 ($y-1) 492 17}; Label $bonus[0] 24 $y 'Secondary'; Label $bonus[1] 430 $y 'Heading'; $i++
	}
	Label 'Your collected treasures grant' 552 128 'Muted'; Label 'bonuses to your whole account.' 552 150 'Muted'
	Asset 'chrome/poring_large.bmp' 591 192; Center 'Little treasures, lasting bonuses.' 548 324 194 'Muted'
	$bmp.Save((Join-Path $pack 'preview/chibi-bonuses.png'),[Drawing.Imaging.ImageFormat]::Png)
} finally { $g.Dispose(); $bmp.Dispose(); $font.Dispose(); $bold.Dispose() }
Write-Host 'Offline production-asset previews written; item names/counts/bonuses are illustrative.'