[CmdletBinding()]
param([string]$PackRoot = (Join-Path $PSScriptRoot '..\Images\CollectionUI'))

# Asset compilation only: the mascot artwork is the checked-in imagegen source.
# Preserve its alpha until the final exact-magenta, 24-bpp client conversion.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$pack = [IO.Path]::GetFullPath($PackRoot)
foreach ($relative in @('chrome/buttons', 'source/menuicon', 'menuicon', 'preview')) {
	$null = New-Item -ItemType Directory -Force -Path (Join-Path $pack $relative)
}
function New-Canvas([int]$Width, [int]$Height, [Drawing.Color]$Color) {
	$bmp = [Drawing.Bitmap]::new($Width, $Height, [Drawing.Imaging.PixelFormat]::Format24bppRgb)
	$g = [Drawing.Graphics]::FromImage($bmp)
	try { $g.Clear($Color) } finally { $g.Dispose() }
	return $bmp
}
function Save-Bmp([Drawing.Bitmap]$Bitmap, [string]$Relative) {
	$Bitmap.Save((Join-Path $pack $Relative), [Drawing.Imaging.ImageFormat]::Bmp)
}
function Color([string]$Hex) { return [Drawing.ColorTranslator]::FromHtml($Hex) }
$magenta = Color '#FF00FF'
$source = [Drawing.Bitmap]::new((Join-Path $pack 'source/poring_collector.png'))
try {
	if ($source.GetPixel(0, 0).A -ne 0) { throw 'Poring source must retain a transparent background.' }
	# Find conservative alpha bounds using a small probe, then sample the original.
	$probe = [Drawing.Bitmap]::new(128, 128, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
	$g = [Drawing.Graphics]::FromImage($probe)
	try { $g.DrawImage($source, 0, 0, 128, 128) } finally { $g.Dispose() }
	$minX = 127; $minY = 127; $maxX = 0; $maxY = 0
	for ($y = 0; $y -lt 128; $y++) {
		for ($x = 0; $x -lt 128; $x++) {
			if ($probe.GetPixel($x, $y).A -gt 16) {
				$minX = [Math]::Min($minX, $x); $minY = [Math]::Min($minY, $y)
				$maxX = [Math]::Max($maxX, $x); $maxY = [Math]::Max($maxY, $y)
			}
		}
	}
	$probe.Dispose()
	$scaleX = $source.Width / 128.0; $scaleY = $source.Height / 128.0
	$crop = [Drawing.RectangleF]::new(
		[Math]::Max(0, $minX - 1) * $scaleX, [Math]::Max(0, $minY - 1) * $scaleY,
		($maxX - $minX + 3) * $scaleX, ($maxY - $minY + 3) * $scaleY)
	function New-Mascot([int]$Width, [int]$Height, [int]$ArtWidth, [int]$ArtHeight, [string]$State) {
		$target = New-Canvas $Width $Height $magenta
		$rgba = [Drawing.Bitmap]::new($ArtWidth, $ArtHeight, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
		$g = [Drawing.Graphics]::FromImage($rgba)
		try {
			$g.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
			$g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
			$g.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
			$ratio = [Math]::Min($ArtWidth / $crop.Width, $ArtHeight / $crop.Height)
			$aw = [int][Math]::Round($crop.Width * $ratio); $ah = [int][Math]::Round($crop.Height * $ratio)
			$destination = [Drawing.RectangleF]::new(($ArtWidth-$aw)/2, ($ArtHeight-$ah)/2, $aw, $ah)
			$g.DrawImage($source, $destination, $crop, [Drawing.GraphicsUnit]::Pixel)
		} finally { $g.Dispose() }
		$offsetX = [int][Math]::Floor(($Width-$ArtWidth)/2)
		$offsetY = [int][Math]::Floor(($Height-$ArtHeight)/2)
		if ($State -eq 'pressed') { $offsetY++ }
		for ($y = 0; $y -lt $ArtHeight; $y++) {
			for ($x = 0; $x -lt $ArtWidth; $x++) {
				$p = $rgba.GetPixel($x,$y)
				if ($p.A -lt 160) { continue }
				$r = [int]$p.R; $green = [int]$p.G; $b = [int]$p.B
				if ($State -eq 'mouseon') {
					$r = [Math]::Min(255,$r+16); $green = [Math]::Min(255,$green+12); $b = [Math]::Min(255,$b+8)
				} elseif ($State -eq 'pressed') {
					$r = [int]($r*0.90); $green = [int]($green*0.90); $b = [int]($b*0.90)
				} elseif ($State -eq 'disabled') {
					$gray = [int](0.299*$r+0.587*$green+0.114*$b)
					$r = $gray; $green = $gray; $b = $gray
				}
				$target.SetPixel($x+$offsetX,$y+$offsetY,[Drawing.Color]::FromArgb($r,$green,$b))
			}
		}
		$rgba.Dispose()
		return $target
	}
	foreach ($theme in @(@('',45,41,36,38), @('old_',32,34,28,30))) {
		foreach ($state in @('normal','mouseon','pressed','disabled')) {
			$bmp = New-Mascot $theme[1] $theme[2] $theme[3] $theme[4] $state
			try { Save-Bmp $bmp "source/menuicon/bt_itemcollection_$($theme[0])$state.bmp" } finally { $bmp.Dispose() }
		}
	}
	Copy-Item -LiteralPath (Join-Path $pack 'source/menuicon/bt_itemcollection_normal.bmp') -Destination (Join-Path $pack 'source/menuicon/bt_itemcollection.bmp') -Force
	Copy-Item -LiteralPath (Join-Path $pack 'source/menuicon/bt_itemcollection_pressed.bmp') -Destination (Join-Path $pack 'source/menuicon/bt_itemcollection_press.bmp') -Force
	foreach ($asset in @(@('chrome/poring_small.bmp',28,30,27,29), @('chrome/poring_large.bmp',108,116,106,114), @('icons/icon_collection.bmp',16,16,14,15))) {
		$bmp = New-Mascot $asset[1] $asset[2] $asset[3] $asset[4] 'normal'
		try { Save-Bmp $bmp $asset[0] } finally { $bmp.Dispose() }
	}
} finally { $source.Dispose() }

# Collection-owned variants of the native 6/6/6 x 20 tileable button geometry.
$states = @{
	out = @('#C5D1DC','#F4F7FB','#FFFFFF','#E3EBF5')
	over = @('#A4BBD7','#EAF3FE','#FFFFFF','#D8E7F8')
	press = @('#C5D1DC','#DDEBFC','#CCE1FB','#829ECA')
	disable = @('#C5D1DC','#F1F4F7','#F7FAFD','#DFE5ED')
}
foreach ($state in @('out','over','press','disable')) {
	$palette = $states[$state]
	$bmp = New-Canvas 18 20 $magenta
	$g = [Drawing.Graphics]::FromImage($bmp)
	$brushes = @($palette | ForEach-Object { [Drawing.SolidBrush]::new((Color $_)) })
	try {
		$g.FillRectangle($brushes[0],2,0,14,20); $g.FillRectangle($brushes[0],0,2,18,16)
		$g.FillRectangle($brushes[1],2,1,14,18); $g.FillRectangle($brushes[1],1,2,16,16)
		$g.FillRectangle($brushes[2],3,2,12,1); $g.FillRectangle($brushes[3],2,17,14,2)
	} finally { $g.Dispose(); foreach ($brush in $brushes) { $brush.Dispose() } }
	for ($i=0; $i -lt 3; $i++) {
		$slice = $bmp.Clone([Drawing.Rectangle]::new($i*6,0,6,20),[Drawing.Imaging.PixelFormat]::Format24bppRgb)
		try { Save-Bmp $slice "chrome/buttons/btn_$($state)_$(@('left','mid','right')[$i]).bmp" } finally { $slice.Dispose() }
	}
	$bmp.Dispose()
}
& (Join-Path $PSScriptRoot 'build_item_collection_menu_buttons.ps1') -PackRoot $pack
Write-Host 'Chibi Collection assets compiled: exact-magenta BMPs, 2 themes, 4 states, 12 control slices.'
# Distinct active paths avoid the old Item Collection art already in update.grf.
foreach ($theme in @('', 'old_')) {
	foreach ($state in @('normal', 'mouseon', 'pressed')) {
		Copy-Item -LiteralPath (Join-Path $pack "menuicon/bt_itemcollection_$theme$state.bmp") -Destination (Join-Path $pack "menuicon/bt_itemcollection_poring_$theme$state.bmp") -Force
	}
}
