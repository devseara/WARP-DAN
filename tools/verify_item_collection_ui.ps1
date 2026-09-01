[CmdletBinding()]
param(
    [switch]$SourceOnly
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$itemPath = Join-Path $repo 'Scripts\Patches\ItemCollectionUI.qjs'
$autoPath = Join-Path $repo 'Scripts\Patches\AutoCombatUI.qjs'
$pinPath = Join-Path $repo 'Scripts\Patches\InGamePincodeUI.qjs'
$menuPath = Join-Path $repo 'Scripts\Patches\ROGlobalZeroMenu.qjs'
$newButtonPath = Join-Path $repo 'Scripts\Patches\NewButtonVisibility.qjs'
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Read-Qjs {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    Assert-True ($bytes.Length -gt 2) "$Path is empty"
    Assert-True (-not ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) "$Path has a UTF-8 BOM"
    Assert-True ($bytes[0] -eq 0x2F -and $bytes[1] -eq 0x2A) "$Path must start with /*"
    $text = $utf8.GetString($bytes)
    Assert-True (-not [regex]::IsMatch($text, '(?<!\r)\n')) "$Path contains LF-only line endings"
    $doubleCr = [string][char]13 + [char]13 + [char]10
    Assert-True (-not $text.Contains($doubleCr)) "$Path contains doubled CR line endings"
    return $text
}

function Assert-Contains {
    param([string]$Text, [string]$Needle, [string]$Message)
    Assert-True ($Text.Contains($Needle)) $Message
}

function Get-SourceSlice {
    param([string]$Text, [string]$Start, [string]$End)
    $startIndex = $Text.IndexOf($Start, [StringComparison]::Ordinal)
    Assert-True ($startIndex -ge 0) "source slice start missing: $Start"
    $endIndex = $Text.IndexOf($End, $startIndex + $Start.Length, [StringComparison]::Ordinal)
    Assert-True ($endIndex -gt $startIndex) "source slice end missing: $End"
    return $Text.Substring($startIndex, $endIndex - $startIndex)
}

function Assert-HelperAbi {
    param(
        [string]$Text,
        [string]$Name,
        [string]$NextName,
        [string]$Save,
        [string]$Restore
    )
    $section = Get-SourceSlice $Text $Name $NextName
    Assert-Contains $section $Save "$Name does not save its callee-saved register set"
    Assert-Contains $section $Restore "$Name does not restore its callee-saved register set/stack"
}

$item = Read-Qjs $itemPath
$auto = Read-Qjs $autoPath
$pin = Read-Qjs $pinPath
$menu = Read-Qjs $menuPath
$newButtons = Read-Qjs $newButtonPath

Assert-Contains $item 'PacketMagic: 0x49554F43' 'COUI magic mismatch'
Assert-Contains $item 'RequestSize: 64' 'request size mismatch'
Assert-Contains $item 'SnapshotHeaderSize: 56' 'snapshot header mismatch'
Assert-Contains $item 'SnapshotMaximumSize: 1556' 'snapshot maximum mismatch'
Assert-Contains $item 'PayloadSize: 1500' 'payload size mismatch'
Assert-Contains $item 'CardRowSize: 100' 'card row size mismatch'
Assert-Contains $item 'ComboRowSize: 400' 'combo row size mismatch'
Assert-Contains $item 'ComboRows: 2' 'combo page capacity mismatch'
Assert-Contains $item 'ComboMembers: 6' 'combo member bound mismatch'
Assert-Contains $item 'TotalRowSize: 64' 'total row size mismatch'
Assert-Contains $item 'TextFontSelector: 0' 'stock UI font selector mismatch'
Assert-Contains $item 'TextHeight: 11' 'stock UI text height mismatch'
Assert-Contains $item 'MoneyBufferSize: 16' 'money formatter buffer mismatch'
Assert-Contains $item 'CardComplete: 1 << 0' 'card flag contract mismatch'
Assert-Contains $item 'ComboReady: 1 << 0' 'combo READY flag mismatch'
Assert-Contains $item 'ComboActive: 1 << 1' 'combo ACTIVE flag mismatch'
Assert-Contains $item 'SnapshotFlagTruncated: 1 << 6' 'snapshot TRUNCATED flag mismatch'
Assert-Contains $item 'CapabilityStorageReady: 1 << 4' 'STORAGE_READY capability mismatch'
Assert-Contains $item 'StateAcceptedRequest: 80' 'accepted request state missing'
Assert-Contains $item 'StateComboId: 100' 'stable combo selection state missing'
Assert-Contains $item 'StateComboMemberIndex: 104' 'combo member index state missing'
Assert-Contains $item 'StateComboMemberId: 108' 'combo member target state missing'
Assert-Contains $item 'StateMutationPending: 112' 'single-flight mutation state missing'
Assert-Contains $item 'StateSearchEdit: 116' 'native search edit pointer state missing'
Assert-Contains $item 'StateCategory: 120' 'item category state missing'
Assert-Contains $item 'StateCategoryDropdown: 124' 'category dropdown state missing'
Assert-Contains $item 'StateScrollbarDragOffset: 128' 'scrollbar drag offset state missing'
Assert-Contains $item 'StateSize: 132' 'collection state size mismatch'
Assert-Contains $item 'ItemCategoryShift: 8' 'item category wire shift mismatch'
Assert-Contains $item 'CategoryCount: 15' 'all-item category count mismatch'
Assert-Contains $item 'WindowId: 0x3F3' 'Item Collection top-level window ID mismatch'
Assert-Contains $item 'ControlScrollbarThumb: 42' 'scrollbar thumb control missing'
Assert-Contains $item 'ControlScrollbarTrack: 43' 'scrollbar track control missing'
Assert-Contains $item 'ScrollbarTrackTop: 128' 'scrollbar top geometry mismatch'
Assert-Contains $item 'ScrollbarTrackBottom: 480' 'scrollbar bottom geometry mismatch'
Assert-Contains $item 'ScrollbarThumbHeight: 24' 'scrollbar thumb height mismatch'
Assert-Contains $item 'ScrollbarThumbTravel: 328' 'scrollbar thumb travel mismatch'
Assert-Contains $item 'snapshot_regressed' 'revision-regression branch missing'
Assert-Contains $item 'Copy only mutationResult' 'current-request error preservation branch missing'
Assert-Contains $item 'c.TargetLeaf + "\\" + relative' 'fixed asset runtime root is not composed from item_collection'
Assert-Contains $item 'TargetLeaf: "item_collection"' 'fixed asset root mismatch'
Assert-Contains $item 'c.buildResourcePath("collection\\%s.bmp")' 'dynamic art must remain collection\<stem>.bmp'
Assert-Contains $item 'c.buildResourcePath("item\\%s.bmp")' 'stock item icon fallback path missing'
Assert-Contains $item 'ItemInfoIdentifiedResourceOffset: 0x58' 'identified-resource offset mismatch'
Assert-Contains $item 'ItemInfoStringCapacityOffset: 0x14' 'identified-resource string layout mismatch'
Assert-Contains $item 'command: "/itemcollection"' 'slash opener missing'
Assert-Contains $item 'SearchTextSize: 28' 'search wire buffer size mismatch'
Assert-Contains $item 'SearchMaximumChars: 27' 'search NUL bound mismatch'
Assert-Contains $item 'SearchDebounceMs: 250' 'search debounce mismatch'
Assert-Contains $item 'buildSearchNativeInput' 'native search synchronization helper missing'
Assert-Contains $item 'UIEditCtrlConstructor: 0x00817DA0' 'native edit constructor profile missing'
Assert-Contains $item 'UIEditCtrlGetText: 0x008210A0' 'native edit GetText profile missing'
Assert-Contains $item 'UIEditCtrlObjectSize: 0x11C' 'native edit object size mismatch'
Assert-Contains $item 'WindowManagerSetFocusEdit: 0x00A4B760' 'SetFocusEdit profile missing'
Assert-Contains $item 'WindowManagerGetFocusEdit: 0x00A33100' 'GetFocusEdit profile missing'
Assert-Contains $item 'WindowAddChild: 0x00A1B780' 'native child ownership profile missing'
Assert-Contains $item 'timeGetTime' 'search timing API missing'
Assert-Contains $item 'StateSearchSubmitPending' 'search debounce pending state missing'
Assert-Contains $item 'search: "native-ui-edit-ctrl-debounce"' 'search diagnostics mismatch'
Assert-Contains $item 'c.pushImm(a, c.UIEditCtrlObjectSize)' 'native edit allocation missing'
Assert-Contains $item 'a.call(c.UIEditCtrlConstructor)' 'native edit construction missing'
Assert-Contains $item 'a.call(c.WindowAddChild)' 'native edit parent ownership missing'
Assert-Contains $item 'a.call(c.WindowManagerSetFocusEdit)' 'native edit focus transfer missing'
Assert-Contains $item 'a.call(c.UIEditCtrlGetText)' 'native edit text retrieval missing'
Assert-True (-not $item.Contains('GetAsyncKeyState')) 'lossy frame-polled search remains'
Assert-True (-not $item.Contains('DispatchMessageA')) 'synthetic message-loop search hook remains'
Assert-True (-not $item.Contains('TranslateMessage')) 'synthetic message translation dependency remains'
Assert-Contains $item 'Search item name or ID' 'general item search placeholder missing'
Assert-Contains $item 'tabs: ["Items", "Combo Collections", "Total Bonuses"]' 'Items tab terminology missing'
Assert-Contains $item '"All Items", "Cards", "Weapons", "Armor", "Shields"' 'primary item categories missing'
Assert-Contains $item '"Consumables", "Etc", "Ammo", "Pet Items", "Shadow Gear"' 'extended item categories missing'
Assert-Contains $item 'ControlCategoryDropdown: 30' 'category dropdown control missing'
Assert-Contains $item 'ControlCategoryBase: 300' 'category dropdown row controls missing'
Assert-Contains $item 'emitCategoryDropdown' 'category dropdown field renderer missing'
Assert-Contains $item 'emitCategoryDropdownPopup' 'category dropdown popup renderer missing'
Assert-Contains $item 'An open category popup owns the first click' 'dropdown click-through guard missing'
Assert-Contains $item 'category_popup_click_${category}_next' 'dropdown row selection loop missing'
Assert-Contains $item 'c.emitSendRequest(a, senderVir, c.MessageNavigate, c.ActionNone)' 'dropdown selection does not navigate once'
Assert-Contains $item '{saveDefault: true}' 'asset-copy choice is not persisted'
Assert-Contains $item 'Static labels use NUL-terminated mode' 'category string spill guard missing'
Assert-True (-not $item.Contains('paths.categories')) 'text-only stock dropdown still loads category textures'
Assert-True (-not $item.Contains('category_icon_')) 'stock dropdown still draws a non-native category icon'
Assert-True (-not $item.Contains('ControlCategoryPrevious')) 'obsolete previous-category control remains'
Assert-True (-not $item.Contains('ControlCategoryNext')) 'obsolete next-category control remains'
$categoryDropdownSection = Get-SourceSlice $item 'emitCategoryDropdown = function' 'emitFilters = function'
Assert-True (([regex]::Matches($categoryDropdownSection, 'strings\.categories\[category\]\.vir')).Count -eq 2) 'category dropdown must draw exactly one closed label and one popup-row label'
Assert-Contains $categoryDropdownSection 'const y = 87 + category * 18;' 'category popup does not assign one fixed row per item family'
Assert-True (-not [regex]::IsMatch($categoryDropdownSection, 'strings\.categories\[category\]\.vir,[\s\S]{0,100}0xFF172237,\s*0,\s*\d+')) 'category label uses a fixed native character count and can spill into adjacent strings'
Assert-Contains $item 'stateVir + c.StateCategory' 'category state is not serialized'
Assert-Contains $item 'paths.itemArtFormat.vir' 'item icon fallback is not wired to item rows'
Assert-Contains $item 'Copy the complete bounded ASCII query' 'request query copy missing'
Assert-True (-not $item.Contains('Search requires native edit input')) 'disabled search placeholder remains'
Assert-Contains $item 'card_shell_${index}_next' 'card shell-first draw pass missing'
Assert-Contains $item 'card_content_${index}_next' 'card content draw pass missing'
Assert-Contains $item 'const top = 114 + row * 131;' 'card hit geometry mismatch'
Assert-Contains $item 'const y = 119 + index * 181;' 'combo row geometry mismatch'
Assert-Contains $item 'x, y + 39, 0, `combo_art_${index}_${member}`' 'combo art must use full-height drawing'
Assert-Contains $item 'ControlComboMemberBase: 200' 'combo member control range missing'
Assert-Contains $item 'stateVir + c.StateComboMemberId, stateVir + c.StateQuantity' 'combo member quantity mutation target missing'
Assert-Contains $item 'stateVir + c.StateComboMemberId' 'combo member mutation target missing'
Assert-Contains $item 'combo_deposit_all_' 'combo Deposit All button missing'
Assert-Contains $item 'combo_withdraw_' 'combo Withdraw button missing'
Assert-Contains $item 'selection_combo_fallback' 'combo selection preservation fallback missing'
Assert-Contains $item 'StateMutationPending' 'mutation pending gate missing'
Assert-Contains $item 'Saving collection change...' 'mutation pending status missing'
Assert-Contains $item 'Storage save failed.' 'exact database error text missing'
Assert-True (-not $item.Contains('The server rejected the last request.')) 'generic mutation rejection remains'
Assert-Contains $item 'stateVir + c.StateReady); a.dword(0)' 'navigation does not hide stale payload'
Assert-Contains $item 'stateVir + c.StateRowCount); a.dword(0)' 'navigation does not clear stale row count'
Assert-Contains $item '0x83, 0x7D, 0x0C, c.ActionSelect' 'same-page selection preservation gate missing'
Assert-Contains $item 'same schema/page: no flicker' 'selection no-flicker contract missing'
Assert-Contains $item 'StateScrollbarDragOffset' 'thumb pointer offset is not retained'
Assert-True (-not $item.Contains('a.call(c.WindowCaptureSet)')) 'scrollbar thumb still shares native title-drag capture'
Assert-Contains $item 'c.ControlScrollbarTrack' 'scrollbar track paging is not wired'
Assert-Contains $item 'c.ScrollbarTrackBottom - c.ScrollbarThumbHeight' 'thumb is not clamped above the down arrow'
Assert-Contains $item 'ROGlobalZeroMenu.ItemCollectionRoute.v1' 'order-independent menu route registration missing'
Assert-Contains $item 'requestVir: toggle.vir' 'menu bridge does not publish Item Collection request target'
Assert-Contains $item 'visiblePhy: menuButtonVisible.phy' 'menu bridge does not publish visibility ownership'
Assert-Contains $item 'bt_itemcollection_old_pressed.bmp' 'Classic menu button deployment list missing'
Assert-Contains $item 'font selector 0, height 11' 'stock font-face contract missing'
Assert-Contains $item 'feeFormat: text("Deposit %s / Withdraw %s Zeny")' 'fee text does not consume grouped strings'
Assert-Contains $item 'buildFormatU32Commas' 'bounded comma formatter missing'
Assert-Contains $item 'c.MoneyBufferSize' 'money buffers are not allocated from the documented bound'
Assert-True (-not [regex]::IsMatch($item, 'c\.emitText\([^\r\n]*,\s*(10|11|12|13|14|15|16),\s*0x')) 'per-call emitText height override remains'
Assert-True (-not [regex]::IsMatch($item, 'c\.emitCenteredText\([^\r\n]*,\s*(10|11|12|13|14|15|16),\s*0x')) 'per-call centered-text height override remains'

# Source-level x86 ABI audit. Helpers either save the exact nonvolatile set
# they use, use PUSHAD/POPAD, or restore ESI before a stock tail jump.
Assert-HelperAbi $item 'buildRequestSender = function' 'buildSnapshotReceiver = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC2, 0x10, 0x00'
Assert-HelperAbi $item 'buildSearchNativeInput = function' 'buildSnapshotReceiver = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC3'
Assert-HelperAbi $item 'buildSnapshotReceiver = function' 'buildFillRect = function' '0x9C, 0x60' '0x61, 0x9D'
Assert-HelperAbi $item 'buildFillRect = function' 'buildColorKeyBlit = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x5D, 0xC2, 0x18, 0x00'
Assert-HelperAbi $item 'buildColorKeyBlit = function' 'emitLoadSurface = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC2, 0x10, 0x00'
Assert-HelperAbi $item 'buildDynamicPathDraw = function' 'buildNineSliceButton = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x5D, 0xC2, 0x18, 0x00'
Assert-HelperAbi $item 'buildNineSliceButton = function' 'buildItemResourceResolver = function' '0x53, 0x56, 0x57' '0x5F, 0x5E, 0x5B, 0x5D, 0xC2, 0x1C, 0x00'
Assert-HelperAbi $item 'buildItemResourceResolver = function' 'emitDrawCollectionArt = function' '0x55, 0x8B, 0xEC, 0x56' '0x5E, 0x5D, 0xC2, 0x04, 0x00'
Assert-HelperAbi $item 'buildFormatU32Commas = function' 'emitFormatU32Commas = function' '0x53, 0x56, 0x57, 0x83, 0xEC, 0x10' '0x83, 0xC4, 0x10, 0x5F, 0x5E, 0x5B, 0x5D, 0xC2, 0x08, 0x00'
Assert-HelperAbi $item 'buildDraw = function' 'emitSendRequest = function' '0x53, 0x56, 0x57, 0x8B, 0xF1' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC3'
Assert-HelperAbi $item 'buildMouseDown = function' 'buildMouseMove = function' '0x53, 0x56, 0x57, 0x8B, 0xF1' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC2, 0x08, 0x00'
Assert-HelperAbi $item 'buildMouseMove = function' 'buildMouseUp = function' '0x53, 0x56, 0x57, 0x8B, 0xF1' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D'
Assert-HelperAbi $item 'buildMouseUp = function' 'buildMouseWheel = function' '0x53, 0x56, 0x57, 0x8B, 0xF1' '0x5F, 0x5E, 0x5B, 0x8B, 0xE5, 0x5D, 0xC2, 0x08, 0x00'
Assert-HelperAbi $item 'buildMouseWheel = function' 'buildDestructor = function' '0x56, 0x8B, 0xF1' '0x5E, 0x5D, 0xC2, 0x04, 0x00'
Assert-HelperAbi $item 'buildDestructor = function' 'cloneFrameVtable = function' '0x53, 0x56, 0x8B, 0xF1' '0x8B, 0xCE, 0x5E, 0x5B'
Assert-HelperAbi $item 'buildToggle = function' 'assertCode = function' '0x9C, 0x60' '0x61, 0x9D, 0xC3'

$fillRectSection = Get-SourceSlice $item 'buildFillRect = function' 'buildColorKeyBlit = function'
Assert-Contains $fillRectSection '0x8B, 0x55, 0x18, 0x85, 0xD2' 'FillRect height<=0 guard missing'
Assert-Contains $fillRectSection '0x8B, 0x55, 0x14, 0x85, 0xD2' 'FillRect width<=0 guard missing'
Assert-Contains $fillRectSection '0x8B, 0x4E, c.WindowHeightOffset, 0x2B, 0xC8' 'FillRect vertical remaining-space clip missing'
Assert-Contains $fillRectSection '0x8B, 0xCB, 0x2B, 0xC8' 'FillRect horizontal remaining-space clip missing'
$progressSection = Get-SourceSlice $item 'emitProgress = function' 'emitSummaryProgress = function'
Assert-Contains $progressSection 'a.emit(0x85, 0xC0); a.jcc(0x84, `${label}_done`);' 'zero-width progress does not return before FillRect'
Assert-Contains $progressSection 'a.emit(0x3D); a.dword(width); a.jcc(0x86, `${label}_width_ok`);' 'progress fill is not clamped to the bar width'
$moneySection = Get-SourceSlice $item 'buildFormatU32Commas = function' 'emitFormatU32Commas = function'
Assert-Contains $moneySection '0x8D, 0x7C, 0x24, 0x0F, 0xC6, 0x07, 0x00' 'money formatter lacks its fixed local buffer terminator'
Assert-Contains $moneySection '0x83, 0xFB, 0x03' 'money formatter lacks three-digit grouping'
Assert-Contains $moneySection '0xC6, 0x07, 0x2C' 'money formatter lacks comma insertion'
Assert-True (([regex]::Matches($item, 'a\.call\(c\.TextDraw\);')).Count -eq 2) 'TextDraw bypasses the normalized text helpers'

foreach ($text in @($item, $auto, $pin)) {
    Assert-Contains $text 'SharedPacket0BEF.Router.v3' 'canonical shared router v3 key missing'
    Assert-Contains $text 'couiHandlerCellPhy' 'COUI handler cell missing'
    Assert-Contains $text 'couiHandlerCellVir' 'COUI handler cell address missing'
}
Assert-Contains $auto 'CollectionUiMagic: 0x49554F43' 'AutoCombat router lacks COUI magic'
Assert-Contains $pin 'CouiMagic: 0x49554F43' 'PIN router lacks COUI magic'
Assert-True (-not $item.Contains('Packet0BEF.Wrapper')) 'obsolete outer-wrapper cache remains'
Assert-True (-not $item.Contains('installSharedPacketWrapper')) 'obsolete wrapper installer remains'

Assert-Contains $menu 'AutoHuntButtonWindowId: 0x3F2' 'Auto Hunt child ID changed'
Assert-Contains $menu 'ItemCollectionButtonWindowId: 0x3F4' 'Item Collection child ID missing'
Assert-Contains $menu 'buildOptionalButtonMouseUp' 'optional Item Collection mouse-up route missing'
Assert-Contains $menu 'ROGlobalZeroMenu.ItemCollectionRoute.v1' 'RO Global menu does not publish Item Collection route cells'
Assert-Contains $menu 'bt_itemcollection_normal.bmp' 'New UI Item Collection normal image missing'
Assert-Contains $menu 'bt_itemcollection_old_pressed.bmp' 'Classic Item Collection pressed image missing'
Assert-Contains $menu 'theme.stateVir, loadTheme.vir, 1' 'Item Collection is not placed in control-row column 2'
Assert-Contains $menu '[buttonState.vir, itemButtonState.vir]' 'native hit testing does not include both custom buttons'
Assert-Contains $menu '[ensureAutoHunt.vir, ensureItemCollection.vir]' 'layout does not ensure both custom buttons'
Assert-Contains $menu '[syncAutoHunt.vir, syncItemCollection.vir]' 'layout does not sync both custom buttons'
Assert-Contains $newButtons 'ItemCollectionUI.MenuButton.v1' 'Show/Hide Buttons lacks Item Collection bridge'
Assert-Contains $newButtons "'Item Collection'" 'Show/Hide Buttons lacks Item Collection label'

# Model the canonical shared-cell contract in every consumer order. The real
# QJS sources above are separately asserted to use this same v3 key and cell
# names; this catches a future selection-order regression in the test oracle.
$orders = @(
    @('AHUI', 'PINC', 'COUI'),
    @('AHUI', 'COUI', 'PINC'),
    @('PINC', 'AHUI', 'COUI'),
    @('PINC', 'COUI', 'AHUI'),
    @('COUI', 'AHUI', 'PINC'),
    @('COUI', 'PINC', 'AHUI')
)
foreach ($order in $orders) {
    $route = @{
        version = 3
        fallback = 0x00C9E1DD
        AHUI = 0
        PINC = 0
        COUI = 0
    }
    foreach ($consumer in $order) {
        $route[$consumer] = switch ($consumer) {
            'AHUI' { 0x10001000 }
            'PINC' { 0x10002000 }
            'COUI' { 0x10003000 }
        }
    }
    Assert-True ($route.AHUI -eq 0x10001000) "AHUI lost in order $order"
    Assert-True ($route.PINC -eq 0x10002000) "PINC lost in order $order"
    Assert-True ($route.COUI -eq 0x10003000) "COUI lost in order $order"
    Assert-True ($route.fallback -eq 0x00C9E1DD) "fallback changed in order $order"
}
$migrated = @{ AHUI = 0x10001000; PINC = 0x10002000; COUI = 0; fallback = 0x00C9E1DD }
$migrated.COUI = 0x10003000
Assert-True ($migrated.AHUI -ne 0 -and $migrated.PINC -ne 0 -and $migrated.COUI -ne 0) 'v2-to-v3 migration oracle lost a handler'

function Get-SnapshotDisposition {
    param(
        [uint32]$Requested,
        [uint32]$Accepted,
        [uint32]$Revision,
        [uint32]$IncomingRequest,
        [uint32]$IncomingRevision,
        [uint32]$MutationResult
    )
    if ($IncomingRequest -ne $Requested -or $IncomingRequest -lt $Accepted) {
        return 'ignore'
    }
    if ($IncomingRevision -lt $Revision) {
        if ($MutationResult -ne 0) {
            return 'error-only'
        }
        return 'ignore'
    }
    return 'full'
}
Assert-True ((Get-SnapshotDisposition 8 7 40 7 41 0) -eq 'ignore') 'older request was not rejected'
Assert-True ((Get-SnapshotDisposition 8 7 40 8 39 0) -eq 'ignore') 'regressing revision was not rejected'
Assert-True ((Get-SnapshotDisposition 8 7 40 8 39 5) -eq 'error-only') 'current-request error was not preserved'
Assert-True ((Get-SnapshotDisposition 8 7 40 8 40 5) -eq 'full') 'current non-regressing error snapshot was rejected'
Assert-True ((Get-SnapshotDisposition 8 7 40 9 41 0) -eq 'ignore') 'unknown future request was accepted'

function Get-PackedItemFilterOracle {
    param([uint16]$Progress, [uint16]$Category)
    Assert-True ($Progress -le 3) 'progress filter exceeds v1 range'
    Assert-True ($Category -lt 15) 'item category exceeds v1 range'
    return [uint16](($Category -shl 8) -bor $Progress)
}

$packedItemFilter = Get-PackedItemFilterOracle 2 7
Assert-True (($packedItemFilter -band 0x00FF) -eq 2) 'packed progress filter is not in the low byte'
Assert-True (($packedItemFilter -shr 8) -eq 7) 'packed item category is not in the high byte'
$rowFlagsWithCategory = [uint32](0x00000002 -bor (14 -shl 8))
Assert-True (($rowFlagsWithCategory -band 0x00000F00) -shr 8 -eq 14) 'row category flag extraction mismatch'

function Format-U32CommaOracle {
    param([uint64]$Value)
    Assert-True ($Value -le [uint32]::MaxValue) 'comma oracle input exceeds uint32'
    $result = $Value.ToString([Globalization.CultureInfo]::InvariantCulture)
    for ($index = $result.Length - 3; $index -gt 0; $index -= 3) {
        $result = $result.Insert($index, ',')
    }
    return $result
}

$moneyCases = @(
    @{ Value = [uint64]0; Expected = '0' },
    @{ Value = [uint64]999; Expected = '999' },
    @{ Value = [uint64]1000; Expected = '1,000' },
    @{ Value = [uint64]999999; Expected = '999,999' },
    @{ Value = [uint64]1000000; Expected = '1,000,000' },
    @{ Value = [uint64][uint32]::MaxValue; Expected = '4,294,967,295' }
)
foreach ($moneyCase in $moneyCases) {
    $actual = Format-U32CommaOracle $moneyCase.Value
    Assert-True ($actual -eq $moneyCase.Expected) "comma formatting mismatch for $($moneyCase.Value): $actual"
    Assert-True ($actual.Length -le 13) "comma output exceeded uint32 character bound: $actual"
}

function Get-ClippedFillOracle {
    param(
        [int64]$SurfaceWidth,
        [int64]$WindowHeight,
        [int64]$X,
        [int64]$Y,
        [int64]$Width,
        [int64]$Height
    )
    if ($SurfaceWidth -le 0 -or $WindowHeight -le 0 -or
        $X -lt 0 -or $Y -lt 0 -or $Width -le 0 -or $Height -le 0 -or
        $X -ge $SurfaceWidth -or $Y -ge $WindowHeight) {
        return @{ Width = [int64]0; Height = [int64]0; Writes = [int64]0 }
    }
    $clippedWidth = [Math]::Min($Width, $SurfaceWidth - $X)
    $clippedHeight = [Math]::Min($Height, $WindowHeight - $Y)
    return @{
        Width = $clippedWidth
        Height = $clippedHeight
        Writes = $clippedWidth * $clippedHeight
    }
}

Assert-True ((Get-ClippedFillOracle 760 540 10 10 0 7).Writes -eq 0) 'zero-width FillRect would write'
Assert-True ((Get-ClippedFillOracle 760 540 10 10 7 0).Writes -eq 0) 'zero-height FillRect would write'
$rightEdge = Get-ClippedFillOracle 760 540 759 100 10 3
Assert-True ($rightEdge.Width -eq 1 -and $rightEdge.Writes -eq 3) 'FillRect right-edge clipping is not surfaceWidth-x'
$bottomEdge = Get-ClippedFillOracle 760 540 100 539 3 10
Assert-True ($bottomEdge.Height -eq 1 -and $bottomEdge.Writes -eq 3) 'FillRect bottom-edge clipping is not windowHeight-y'
$cornerEdge = Get-ClippedFillOracle 760 540 759 539 10 10
Assert-True ($cornerEdge.Width -eq 1 -and $cornerEdge.Height -eq 1 -and $cornerEdge.Writes -eq 1) 'FillRect corner clipping mismatch'

function Get-ProgressWidthOracle {
    param([uint64]$Current, [uint64]$Total, [uint64]$Width)
    if ($Total -eq 0 -or $Width -eq 0) {
        return [uint64]0
    }
    return [Math]::Min([uint64](($Current * $Width) / $Total), $Width)
}

Assert-True ((Get-ProgressWidthOracle 0 10 73) -eq 0) '0/10 progress would paint a green fill'
Assert-True ((Get-ProgressWidthOracle 0 3 73) -eq 0) '0/3 progress would paint a green fill'
Assert-True ((Get-ProgressWidthOracle 5 10 73) -eq 36) '5/10 progress width mismatch'
Assert-True ((Get-ProgressWidthOracle 11 10 73) -eq 73) 'over-complete progress was not clamped'

function Get-ScrollbarThumbOracle {
    param([int]$Page, [int]$PageCount)
    if ($PageCount -le 1) { return 128 }
    return 128 + [Math]::Floor(($Page * 328) / ($PageCount - 1))
}

function Get-ScrollbarPageOracle {
    param([int]$ThumbY, [int]$PageCount)
    if ($PageCount -le 1) { return 0 }
    $relative = [Math]::Max(0, [Math]::Min(328, $ThumbY - 128))
    return [Math]::Floor((($relative * ($PageCount - 1)) + 164) / 328)
}

Assert-True ((Get-ScrollbarThumbOracle 0 20) -eq 128) 'first page thumb is not at track top'
$lastThumb = Get-ScrollbarThumbOracle 19 20
Assert-True ($lastThumb -eq 456) 'last page thumb is not clamped above the down arrow'
Assert-True (($lastThumb + 24) -eq 480) 'thumb bottom overlaps the down arrow'
Assert-True ((Get-ScrollbarPageOracle 128 20) -eq 0) 'top drag does not resolve first page'
Assert-True ((Get-ScrollbarPageOracle 456 20) -eq 19) 'bottom drag does not resolve last page'
Assert-True ((Get-ScrollbarPageOracle 292 20) -eq 10) 'mid-track drag rounding changed'

$forbidden = @(
    'RecvStrip',
    'ws2_32.recv',
    'FindFunc("recv"',
    'CustomDLL.',
    'new Date('
)
foreach ($token in $forbidden) {
    Assert-True (-not $item.Contains($token)) "forbidden ItemCollectionUI token: $token"
}

$patchTable = [System.IO.File]::ReadAllText((Join-Path $repo 'Tables\Patch.yml'))
$uiPatches = [System.IO.File]::ReadAllText((Join-Path $repo 'Patches\UI.yml'))
$manifest = [System.IO.File]::ReadAllText((Join-Path $repo 'Images\CollectionUI\asset-manifest.yml'))
$readme = [System.IO.File]::ReadAllText((Join-Path $repo 'Images\CollectionUI\README.md'))
$coexistenceProfile = [System.IO.File]::ReadAllText((Join-Path $repo 'profiles\item_collection_ui_coexistence_test.yml'))
$menuOrderProfile = [System.IO.File]::ReadAllText((Join-Path $repo 'profiles\item_collection_ui_menu_order_test.yml'))
$menuReverseProfile = [System.IO.File]::ReadAllText((Join-Path $repo 'profiles\item_collection_ui_menu_reverse_order_test.yml'))
Assert-Contains $patchTable '381 : ItemCollectionUI' 'Tables/Patch.yml registration missing'
Assert-Contains $uiPatches '- ItemCollectionUI:' 'UI patch entry missing'
Assert-True ($uiPatches.IndexOf('- ItemCollectionUI:') -lt $uiPatches.IndexOf('- ROGlobalZeroMenu:')) 'Item Collection must execute before RO Global Menu in normal GUI builds'
Assert-Contains $manifest "RuntimeRoot: 'data\texture\" 'asset manifest runtime root prefix missing'
Assert-Contains $manifest "\item_collection'" 'asset manifest runtime root mismatch'
Assert-Contains $readme '\item_collection\' 'asset README runtime root missing'
Assert-Contains $readme 'collection\<identified-resource>.bmp' 'asset README dynamic-art contract missing'
Assert-Contains $coexistenceProfile '- InGamePincodeUI' 'coexistence profile lacks PINC'
Assert-Contains $coexistenceProfile '- AutoCombatUI' 'coexistence profile lacks AHUI'
Assert-Contains $coexistenceProfile '- ItemCollectionUI' 'coexistence profile lacks COUI'
foreach ($profile in @($menuOrderProfile, $menuReverseProfile)) {
    Assert-Contains $profile '- AutoCombatUI' 'menu profile lacks Auto Hunt'
    Assert-Contains $profile '- ROGlobalZeroUITheme' 'menu profile lacks RO Global theme state'
    Assert-Contains $profile '- ROGlobalZeroMenu' 'menu profile lacks RO Global menu'
    Assert-Contains $profile '- ItemCollectionUI' 'menu profile lacks Item Collection'
}

$assets = Join-Path $repo 'Images\CollectionUI'
$requiredAssets = @(
    'chrome\title_bar_760.bmp',
    'chrome\bg_collection.bmp',
    'icons\icon_collection.bmp',
    'icons\badge_locked.bmp',
    'icons\badge_complete.bmp',
    'reused\artwork\fallback_question_mark.bmp',
    'reused\close\btn_close_normal.bmp',
    'reused\buttons\generic\btn_out_left.bmp',
    'reused\buttons\generic\btn_disable_right.bmp',
    'reused\search\searchbar_bg.bmp',
    'reused\scrollbar\btn_scroll_arrow_up.bmp',
    'reused\steppers\btn_plus_press.bmp',
    'reused\currency\icon_zeny.bmp'
)
$categoryAssetNames = @(
    'all', 'card', 'weapon', 'armor', 'shield',
    'headgear', 'garment', 'shoes', 'accessory', 'consumable',
    'etc', 'ammo', 'pet', 'shadow', 'cash'
)
foreach ($categoryAssetName in $categoryAssetNames) {
    $requiredAssets += "icons\category_$categoryAssetName.bmp"
    Assert-Contains $item "icons/category_$categoryAssetName.bmp" "category asset is not deployed: $categoryAssetName"
}
foreach ($menuAsset in @(
    'bt_itemcollection.bmp',
    'bt_itemcollection_disabled.bmp',
    'bt_itemcollection_normal.bmp',
    'bt_itemcollection_mouseon.bmp',
    'bt_itemcollection_press.bmp',
    'bt_itemcollection_pressed.bmp',
    'bt_itemcollection_old_disabled.bmp',
    'bt_itemcollection_old_normal.bmp',
    'bt_itemcollection_old_mouseon.bmp',
    'bt_itemcollection_old_pressed.bmp'
)) {
    $requiredAssets += "menuicon\$menuAsset"
    Assert-Contains $item $menuAsset "menu button asset is not deployed: $menuAsset"
}
foreach ($asset in $requiredAssets) {
    Assert-True (Test-Path -LiteralPath (Join-Path $assets $asset)) "missing collection asset: $asset"
}

foreach ($path in @($itemPath, $autoPath, $pinPath, $menuPath, $newButtonPath)) {
    $source = [System.IO.File]::ReadAllText($path, $utf8)
    $result = $source | & node --check - 2>&1
    Assert-True ($LASTEXITCODE -eq 0) ("Node syntax check failed for " + $path + [Environment]::NewLine + $result)
}

if (-not $SourceOnly) {
    & (Join-Path $PSScriptRoot 'verify_collection_ui_assets.ps1')
    Assert-True ($LASTEXITCODE -eq 0) 'BMP asset verification failed'
}

Write-Host 'Item Collection UI source verification passed.'
