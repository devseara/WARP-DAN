param(
	[string]$PackRoot = (Join-Path $PSScriptRoot '..\Images\CollectionUI')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$resolvedPackRoot = [System.IO.Path]::GetFullPath($PackRoot)
$sourceTitlePath = Join-Path $resolvedPackRoot 'source\title_bar_470.bmp'
$chromeRoot = Join-Path $resolvedPackRoot 'chrome'
$iconRoot = Join-Path $resolvedPackRoot 'icons'
$previewRoot = Join-Path $resolvedPackRoot 'preview'

foreach ($requiredPath in @($sourceTitlePath, (Join-Path $resolvedPackRoot 'reused'))) {
	if (-not (Test-Path -LiteralPath $requiredPath)) {
		throw "Missing required collection UI source: $requiredPath"
	}
}

foreach ($directoryPath in @($chromeRoot, $iconRoot, $previewRoot)) {
	if (-not (Test-Path -LiteralPath $directoryPath)) {
		New-Item -ItemType Directory -Path $directoryPath | Out-Null
	}
}

function New-Bitmap24 {
	param(
		[int]$Width,
		[int]$Height,
		[System.Drawing.Color]$Color
	)

	$bitmap = [System.Drawing.Bitmap]::new(
		$Width,
		$Height,
		[System.Drawing.Imaging.PixelFormat]::Format24bppRgb
	)
	$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
	try {
		$graphics.Clear($Color)
	}
	finally {
		$graphics.Dispose()
	}
	return $bitmap
}

function Save-Bitmap24 {
	param(
		[System.Drawing.Bitmap]$Bitmap,
		[string]$Path
	)

	if (Test-Path -LiteralPath $Path) {
		Remove-Item -LiteralPath $Path
	}
	$Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Bmp)
	$probe = [System.Drawing.Bitmap]::new($Path)
	try {
		if ($probe.PixelFormat -ne [System.Drawing.Imaging.PixelFormat]::Format24bppRgb) {
			throw "Generated BMP is not 24-bpp RGB: $Path ($($probe.PixelFormat))"
		}
	}
	finally {
		$probe.Dispose()
	}
}

function Set-RectPixels {
	param(
		[System.Drawing.Bitmap]$Bitmap,
		[int]$X,
		[int]$Y,
		[int]$Width,
		[int]$Height,
		[System.Drawing.Color]$Color
	)

	for ($pixelY = $Y; $pixelY -lt ($Y + $Height); $pixelY++) {
		for ($pixelX = $X; $pixelX -lt ($X + $Width); $pixelX++) {
			$Bitmap.SetPixel($pixelX, $pixelY, $Color)
		}
	}
}

function New-CollectionTitle {
	param([string]$SourcePath)

	$source = [System.Drawing.Bitmap]::new($SourcePath)
	try {
		if ($source.Width -ne 470 -or $source.Height -ne 17) {
			throw "Expected the approved 470x17 title bar, got $($source.Width)x$($source.Height)."
		}

		$targetWidth = 760
		$leftWidth = 60
		$repeatStart = 60
		$repeatEnd = 384
		$repeatWidth = $repeatEnd - $repeatStart + 1
		$rightStart = 385
		$rightWidth = $source.Width - $rightStart
		$rightTargetStart = $targetWidth - $rightWidth
		$target = New-Bitmap24 -Width $targetWidth -Height 17 -Color ([System.Drawing.Color]::Black)

		for ($pixelY = 0; $pixelY -lt 17; $pixelY++) {
			for ($pixelX = 0; $pixelX -lt $targetWidth; $pixelX++) {
				if ($pixelX -lt $leftWidth) {
					$sourceX = $pixelX
				}
				elseif ($pixelX -ge $rightTargetStart) {
					$sourceX = $rightStart + ($pixelX - $rightTargetStart)
				}
				else {
					$sourceX = $repeatStart + (($pixelX - $leftWidth) % $repeatWidth)
				}
				$target.SetPixel($pixelX, $pixelY, $source.GetPixel($sourceX, $pixelY))
			}
		}
		return $target
	}
	finally {
		$source.Dispose()
	}
}

function New-CollectionBody {
	$outerBorder = [System.Drawing.Color]::FromArgb(137, 166, 201)
	$innerBorder = [System.Drawing.Color]::FromArgb(216, 226, 238)
	$white = [System.Drawing.Color]::FromArgb(255, 255, 255)
	$body = New-Bitmap24 -Width 760 -Height 523 -Color $white

	for ($pixelX = 0; $pixelX -lt $body.Width; $pixelX++) {
		$body.SetPixel($pixelX, 0, $outerBorder)
		$body.SetPixel($pixelX, $body.Height - 1, $outerBorder)
		$body.SetPixel($pixelX, 1, $innerBorder)
		$body.SetPixel($pixelX, $body.Height - 2, $innerBorder)
	}
	for ($pixelY = 0; $pixelY -lt $body.Height; $pixelY++) {
		$body.SetPixel(0, $pixelY, $outerBorder)
		$body.SetPixel($body.Width - 1, $pixelY, $outerBorder)
		$body.SetPixel(1, $pixelY, $innerBorder)
		$body.SetPixel($body.Width - 2, $pixelY, $innerBorder)
	}
	return $body
}

function New-CollectionIcon {
	$magenta = [System.Drawing.Color]::FromArgb(255, 0, 255)
	$outline = [System.Drawing.Color]::FromArgb(45, 76, 116)
	$gold = [System.Drawing.Color]::FromArgb(196, 145, 47)
	$paper = [System.Drawing.Color]::FromArgb(255, 248, 211)
	$paperShade = [System.Drawing.Color]::FromArgb(224, 229, 225)
	$blue = [System.Drawing.Color]::FromArgb(83, 132, 192)
	$pink = [System.Drawing.Color]::FromArgb(239, 128, 143)
	$black = [System.Drawing.Color]::FromArgb(38, 48, 58)
	$icon = New-Bitmap24 -Width 16 -Height 16 -Color $magenta

	Set-RectPixels $icon 2 2 12 12 $outline
	Set-RectPixels $icon 3 3 10 10 $gold
	Set-RectPixels $icon 4 4 8 8 $paper
	Set-RectPixels $icon 7 4 1 8 $blue
	Set-RectPixels $icon 8 5 3 1 $paperShade
	Set-RectPixels $icon 5 5 2 1 $paperShade
	Set-RectPixels $icon 5 7 5 3 $pink
	Set-RectPixels $icon 6 6 3 1 $pink
	$icon.SetPixel(6, 8, $black)
	$icon.SetPixel(9, 8, $black)
	$icon.SetPixel(7, 10, $black)
	$icon.SetPixel(8, 10, $black)
	return $icon
}

function New-LockBadge {
	$magenta = [System.Drawing.Color]::FromArgb(255, 0, 255)
	$outline = [System.Drawing.Color]::FromArgb(44, 48, 55)
	$metal = [System.Drawing.Color]::FromArgb(242, 244, 246)
	$shade = [System.Drawing.Color]::FromArgb(166, 174, 185)
	$badge = New-Bitmap24 -Width 16 -Height 16 -Color $magenta

	Set-RectPixels $badge 5 2 6 1 $outline
	Set-RectPixels $badge 4 3 2 5 $outline
	Set-RectPixels $badge 10 3 2 5 $outline
	Set-RectPixels $badge 6 3 4 1 $metal
	Set-RectPixels $badge 6 4 4 3 $magenta
	Set-RectPixels $badge 3 7 10 7 $outline
	Set-RectPixels $badge 4 8 8 5 $metal
	Set-RectPixels $badge 4 12 8 1 $shade
	Set-RectPixels $badge 7 9 2 3 $outline
	return $badge
}

function New-CompleteBadge {
	$magenta = [System.Drawing.Color]::FromArgb(255, 0, 255)
	$outline = [System.Drawing.Color]::FromArgb(36, 116, 51)
	$green = [System.Drawing.Color]::FromArgb(77, 174, 83)
	$highlight = [System.Drawing.Color]::FromArgb(121, 205, 116)
	$white = [System.Drawing.Color]::FromArgb(255, 255, 255)
	$badge = New-Bitmap24 -Width 16 -Height 16 -Color $magenta

	for ($pixelY = 1; $pixelY -le 14; $pixelY++) {
		for ($pixelX = 1; $pixelX -le 14; $pixelX++) {
			$deltaX = $pixelX - 7.5
			$deltaY = $pixelY - 7.5
			$distance = ($deltaX * $deltaX) + ($deltaY * $deltaY)
			if ($distance -le 45) {
				$badge.SetPixel($pixelX, $pixelY, $outline)
			}
			if ($distance -le 32) {
				$badge.SetPixel($pixelX, $pixelY, $green)
			}
		}
	}
	Set-RectPixels $badge 5 3 4 1 $highlight
	$checkPixels = @(
		@(4,8), @(5,9), @(6,10),
		@(7,9), @(8,8), @(9,7), @(10,6), @(11,5),
		@(7,10), @(8,9), @(9,8), @(10,7)
	)
	foreach ($checkPixel in $checkPixels) {
		$badge.SetPixel($checkPixel[0], $checkPixel[1], $white)
	}
	return $badge
}

function Draw-PreviewLabel {
	param(
		[System.Drawing.Graphics]$Graphics,
		[System.Drawing.Font]$Font,
		[string]$Text,
		[float]$X,
		[float]$Y
	)
	$Graphics.DrawString($Text, $Font, [System.Drawing.Brushes]::Black, $X, $Y)
}

function Draw-MagentaKeyedPreview {
	param(
		[System.Drawing.Graphics]$Graphics,
		[System.Drawing.Bitmap]$Bitmap,
		[int]$X,
		[int]$Y,
		[int]$Width,
		[int]$Height
	)

	$magenta = [System.Drawing.Color]::FromArgb(255, 0, 255)
	$imageAttributes = [System.Drawing.Imaging.ImageAttributes]::new()
	try {
		$imageAttributes.SetColorKey($magenta, $magenta)
		$destination = [System.Drawing.Rectangle]::new($X, $Y, $Width, $Height)
		$Graphics.DrawImage(
			$Bitmap,
			$destination,
			0,
			0,
			$Bitmap.Width,
			$Bitmap.Height,
			[System.Drawing.GraphicsUnit]::Pixel,
			$imageAttributes
		)
	}
	finally {
		$imageAttributes.Dispose()
	}
}

function New-NineSliceButtonPreview {
	param(
		[string]$ButtonRoot,
		[string]$State,
		[int]$Width = 160
	)

	$left = [System.Drawing.Bitmap]::new((Join-Path $ButtonRoot "btn_${State}_left.bmp"))
	$middle = [System.Drawing.Bitmap]::new((Join-Path $ButtonRoot "btn_${State}_mid.bmp"))
	$right = [System.Drawing.Bitmap]::new((Join-Path $ButtonRoot "btn_${State}_right.bmp"))
	try {
		foreach ($slice in @($left, $middle, $right)) {
			if ($slice.Width -ne 6 -or $slice.Height -ne 20) {
				throw "Expected a 6x20 generic button slice for state '$State'."
			}
		}

		$button = New-Bitmap24 -Width $Width -Height 20 -Color ([System.Drawing.Color]::FromArgb(255, 0, 255))
		$graphics = [System.Drawing.Graphics]::FromImage($button)
		try {
			$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
			$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
			$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::None
			$graphics.DrawImageUnscaled($left, 0, 0)

			$middleRight = $Width - $right.Width
			for ($targetX = $left.Width; $targetX -lt $middleRight; $targetX += $middle.Width) {
				$tileWidth = [Math]::Min($middle.Width, $middleRight - $targetX)
				$destination = [System.Drawing.Rectangle]::new($targetX, 0, $tileWidth, 20)
				$source = [System.Drawing.Rectangle]::new(0, 0, $tileWidth, 20)
				$graphics.DrawImage(
					$middle,
					$destination,
					$source,
					[System.Drawing.GraphicsUnit]::Pixel
				)
			}

			$graphics.DrawImageUnscaled($right, $middleRight, 0)
		}
		finally {
			$graphics.Dispose()
		}
		return $button
	}
	finally {
		$left.Dispose()
		$middle.Dispose()
		$right.Dispose()
	}
}

function Draw-PreviewCenteredLabel {
	param(
		[System.Drawing.Graphics]$Graphics,
		[System.Drawing.Font]$Font,
		[string]$Text,
		[int]$X,
		[int]$Y,
		[int]$Width,
		[int]$Height,
		[System.Drawing.Color]$Color
	)

	$format = [System.Drawing.StringFormat]::new()
	$brush = [System.Drawing.SolidBrush]::new($Color)
	try {
		$format.Alignment = [System.Drawing.StringAlignment]::Center
		$format.LineAlignment = [System.Drawing.StringAlignment]::Center
		$bounds = [System.Drawing.RectangleF]::new($X, $Y, $Width, $Height)
		$Graphics.DrawString($Text, $Font, $brush, $bounds, $format)
	}
	finally {
		$brush.Dispose()
		$format.Dispose()
	}
}

$title = New-CollectionTitle -SourcePath $sourceTitlePath
$body = New-CollectionBody
$collectionIcon = New-CollectionIcon
$lockBadge = New-LockBadge
$completeBadge = New-CompleteBadge

try {
	Save-Bitmap24 $title (Join-Path $chromeRoot 'title_bar_760.bmp')
	Save-Bitmap24 $body (Join-Path $chromeRoot 'bg_collection.bmp')
	Save-Bitmap24 $collectionIcon (Join-Path $iconRoot 'icon_collection.bmp')
	Save-Bitmap24 $lockBadge (Join-Path $iconRoot 'badge_locked.bmp')
	Save-Bitmap24 $completeBadge (Join-Path $iconRoot 'badge_complete.bmp')
}
finally {
	$title.Dispose()
	$body.Dispose()
	$collectionIcon.Dispose()
	$lockBadge.Dispose()
	$completeBadge.Dispose()
}

$sheet = New-Bitmap24 -Width 1200 -Height 980 -Color ([System.Drawing.Color]::FromArgb(244, 246, 249))
$sheetGraphics = [System.Drawing.Graphics]::FromImage($sheet)
$sheetGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$sheetGraphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
$sheetGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::None
$titleFont = [System.Drawing.Font]::new('Segoe UI', 18, [System.Drawing.FontStyle]::Bold)
$labelFont = [System.Drawing.Font]::new('Segoe UI', 11, [System.Drawing.FontStyle]::Regular)
$buttonFont = [System.Drawing.Font]::new('Segoe UI', 9, [System.Drawing.FontStyle]::Regular)

try {
	Draw-PreviewLabel $sheetGraphics $titleFont 'Banquet of Heroes - Collection UI production assets' 20 14
	Draw-PreviewLabel $sheetGraphics $labelFont 'New collection-owned chrome (24-bpp BI_RGB)' 20 54

	$titlePreview = [System.Drawing.Bitmap]::new((Join-Path $chromeRoot 'title_bar_760.bmp'))
	$bodyPreview = [System.Drawing.Bitmap]::new((Join-Path $chromeRoot 'bg_collection.bmp'))
	$iconPreview = [System.Drawing.Bitmap]::new((Join-Path $iconRoot 'icon_collection.bmp'))
	$lockPreview = [System.Drawing.Bitmap]::new((Join-Path $iconRoot 'badge_locked.bmp'))
	$completePreview = [System.Drawing.Bitmap]::new((Join-Path $iconRoot 'badge_complete.bmp'))
	try {
		$sheetGraphics.DrawImage($titlePreview, 20, 80, 760, 17)
		$sheetGraphics.DrawImage($bodyPreview, 20, 112, 380, 262)
		Draw-MagentaKeyedPreview $sheetGraphics $iconPreview 430 112 128 128
		Draw-MagentaKeyedPreview $sheetGraphics $lockPreview 580 112 128 128
		Draw-MagentaKeyedPreview $sheetGraphics $completePreview 730 112 128 128
		Draw-PreviewLabel $sheetGraphics $labelFont 'white body 760x523 (shown 50%)' 20 380
		Draw-PreviewLabel $sheetGraphics $labelFont 'collection icon' 442 246
		Draw-PreviewLabel $sheetGraphics $labelFont 'locked badge' 592 246
		Draw-PreviewLabel $sheetGraphics $labelFont 'complete badge' 738 246
	}
	finally {
		$titlePreview.Dispose()
		$bodyPreview.Dispose()
		$iconPreview.Dispose()
		$lockPreview.Dispose()
		$completePreview.Dispose()
	}

	Draw-PreviewLabel $sheetGraphics $labelFont 'Byte-identical reused controls' 20 425
	$previewFiles = @(
		@('Close: normal', 'reused\close\btn_close_normal.bmp', 20, 460, 64, 64, $true),
		@('Close: hover', 'reused\close\btn_close_mouseon.bmp', 115, 460, 64, 64, $true),
		@('Search field', 'reused\search\searchbar_bg.bmp', 210, 470, 242, 36, $true),
		@('Search action', 'reused\search\btn_searchbar_normal.bmp', 475, 460, 78, 54, $true),
		@('Zeny', 'reused\currency\icon_zeny.bmp', 580, 455, 84, 75, $true),
		@('Fallback art', 'reused\artwork\fallback_question_mark.bmp', 700, 435, 150, 200, $false)
	)
	foreach ($previewFile in $previewFiles) {
		$assetPath = Join-Path $resolvedPackRoot $previewFile[1]
		if (-not (Test-Path -LiteralPath $assetPath)) {
			continue
		}
		$asset = [System.Drawing.Bitmap]::new($assetPath)
		try {
			if ($previewFile[6]) {
				Draw-MagentaKeyedPreview $sheetGraphics $asset $previewFile[2] $previewFile[3] $previewFile[4] $previewFile[5]
			}
			else {
				$sheetGraphics.DrawImage($asset, $previewFile[2], $previewFile[3], $previewFile[4], $previewFile[5])
			}
			Draw-PreviewLabel $sheetGraphics $labelFont $previewFile[0] $previewFile[2] ($previewFile[3] + $previewFile[5] + 4)
		}
		finally {
			$asset.Dispose()
		}
	}

	Draw-PreviewLabel $sheetGraphics $labelFont 'Generic 6x20 nine-slice actions assembled at 160x20 with runtime labels' 20 690
	$buttonRoot = Join-Path $resolvedPackRoot 'reused\buttons\generic'
	$buttonPreviews = @(
		@('out', 'Deposit 1', 'Normal', 20, 725),
		@('over', 'Deposit All', 'Hover', 220, 725),
		@('press', 'Withdraw', 'Pressed', 20, 780),
		@('disable', 'Withdraw', 'Disabled', 220, 780)
	)
	foreach ($buttonPreview in $buttonPreviews) {
		$button = New-NineSliceButtonPreview -ButtonRoot $buttonRoot -State $buttonPreview[0] -Width 160
		try {
			Draw-MagentaKeyedPreview $sheetGraphics $button $buttonPreview[3] $buttonPreview[4] 160 20
			Draw-PreviewCenteredLabel $sheetGraphics $buttonFont $buttonPreview[1] $buttonPreview[3] $buttonPreview[4] 160 20 ([System.Drawing.Color]::FromArgb(32, 52, 78))
			Draw-PreviewLabel $sheetGraphics $labelFont $buttonPreview[2] $buttonPreview[3] ($buttonPreview[4] + 24)
		}
		finally {
			$button.Dispose()
		}
	}

	Draw-PreviewLabel $sheetGraphics $labelFont 'Deposit, Withdraw, Activate, tabs, and filters are runtime text.' 20 845
	Draw-PreviewLabel $sheetGraphics $labelFont 'Card artwork remains dynamic: collection\\<identified-resource>.bmp at native 75x100.' 20 875
	Draw-PreviewLabel $sheetGraphics $labelFont 'Transparent irregular assets use exact #FF00FF color key; opaque art/body/title never use color-key drawing.' 20 905

	$contactSheetPath = Join-Path $previewRoot 'contact-sheet.png'
	if (Test-Path -LiteralPath $contactSheetPath) {
		Remove-Item -LiteralPath $contactSheetPath
	}
	$sheet.Save($contactSheetPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
	$titleFont.Dispose()
	$labelFont.Dispose()
	$buttonFont.Dispose()
	$sheetGraphics.Dispose()
	$sheet.Dispose()
}

Get-ChildItem -LiteralPath $resolvedPackRoot -Recurse -Filter '*.bmp' |
	Sort-Object FullName |
	ForEach-Object {
		$bitmapProbe = [System.Drawing.Bitmap]::new($_.FullName)
		try {
			[PSCustomObject]@{
				Path = $_.FullName.Substring($resolvedPackRoot.Length + 1)
				Size = "$($bitmapProbe.Width)x$($bitmapProbe.Height)"
				PixelFormat = $bitmapProbe.PixelFormat
				SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
			}
		}
		finally {
			$bitmapProbe.Dispose()
		}
	} |
	Format-Table -AutoSize
