#!/usr/bin/env python3
"""Static contract gate for the WARP/Banquet AutoSupport UI integration."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from PIL import Image
from render_autohunt_controller_frames import load_str

ROOT = Path(__file__).resolve().parents[1]
ROUTER_FILES = (
    "Scripts/Patches/AutoCombatUI.qjs",
    "Scripts/Patches/AutoSupportUI.qjs",
    "Scripts/Patches/ItemCollectionUI.qjs",
    "Scripts/Patches/InGamePincodeUI.qjs",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def read_qjs(relative: str) -> str:
    path = ROOT / relative
    data = path.read_bytes()
    require(data.startswith(b"/*"), f"{relative} must be UTF-8 without BOM")
    require(data.count(b"\n") == data.count(b"\r\n"), f"{relative} must use CRLF only")
    return data.decode("utf-8")


def bright_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        bright = [
            (x, y) for y in range(rgba.height) for x in range(rgba.width)
            if rgba.getpixel((x, y))[3] > 20 and
            max(rgba.getpixel((x, y))[:3]) > 80
        ]
    require(bool(bright), f"{path.name} is visually empty")
    return (
        max(x for x, _ in bright) - min(x for x, _ in bright) + 1,
        max(y for _, y in bright) - min(y for _, y in bright) + 1,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--banquet",
        type=Path,
        default=ROOT.parent / "BanquetOfHeroes",
        help="BanquetOfHeroes repository root",
    )
    args = parser.parse_args()
    banquet = args.banquet.resolve()

    autocombat = read_qjs("Scripts/Patches/AutoCombatUI.qjs")
    support = read_qjs("Scripts/Patches/AutoSupportUI.qjs")
    item_collection = read_qjs("Scripts/Patches/ItemCollectionUI.qjs")
    menu = read_qjs("Scripts/Patches/ROGlobalZeroMenu.qjs")
    button_visibility = read_qjs("Scripts/Patches/NewButtonVisibility.qjs")
    for relative in ROUTER_FILES:
        text = read_qjs(relative)
        require("SharedPacket0BEF.Router.v4" in text, f"{relative} is not on router v4")
        require("asuiHandlerCellPhy" in text, f"{relative} lacks the ASUI handler cell")

    require("PacketMagic: 0x49555341" in support, "AutoSupportUI magic is not ASUI")
    require('["Basic", "Player", "Skill", "Potion", "Looting", "Move", "Item"]' in support,
            "AutoSupportUI tab contract changed")
    require("dynamic_all" not in support, "Player tab still exposes All Monsters")
    require('"autosupport\\\\setting_player\\\\bg_player_autosupport.bmp"' in support,
            "Player background does not use the dedicated namespace")
    require('"autohunt\\\\' not in support, "AutoSupportUI still loads the autohunt namespace")
    require('command: "/autosupport"' in support, "missing /autosupport fallback")
    require("SettingAutoSupportEnabled: 45" in support, "missing ASUI start/stop setting")
    require("SettingAggressive" not in support and
            "Aggressively target nearby hostile monsters." not in support,
            "AutoSupport still exposes autonomous monster targeting")
    require("Only the selected player's current monster target is attacked." in support and
            "Lex uses only the master's current target." in support,
            "Skill pages do not document strict master-target assistance")
    require(
        "Support First - support the selected player before picking up items." in support,
        "AutoSupport priority copy still describes Fight First",
    )
    require("SettingStatusRecoveryItemRegister: 66" in support and
            "SnapshotStatusItemRowSize: 3840" in support and
            "FeatureStatusItemRow: 1 << 16" in support,
            "Status Recovery item client contract is incomplete")
    require("paths.lootDropdown.vir" in support and
            "setting_looting\\\\bg_dropdown.bmp" in support,
            "Looting selectors do not use the native dropdown frame")
    require('CACHE.get("AutoCombatUI.LifecycleHooks.v1")' in support,
            "AutoSupportUI does not bind the AutoCombat controller state")
    require(
        "ControllerBootstrapHook: 0x00C74FCC" in support and
        'ControllerBootstrapHookBytes: "E8 EF 4C DD FF"' in support and
        "ControllerBootstrapOriginal: 0x00A49CC0" in support,
        "AutoSupport does not own its dedicated pre-AutoCombat bootstrap hook",
    )
    require(
        "peerSuppressControllerVir" in support and
        "a.dword(peerSuppressControllerVir); a.dword(1)" in support and
        "verified.peerSuppressControllerVir" in support,
        "AutoSupport bootstrap does not suppress the peer controller at runtime",
    )
    require(
        "controllerVtableVir, mergedControllerWindowId" in autocombat and
        "a.dword(mergedControllerWindowId)" in autocombat and
        "controllerVtable.vir, 0x3F7" in autocombat,
        "AutoCombat dirty bridge does not recognize the merged controller window ID",
    )
    require("ControllerGroupWidth: 216" in support,
            "AutoSupport controller is not the merged three-tile width")
    require("autohunt-left-autosupport-center-autopotion-right" in support,
            "merged controller tile ordering changed")
    require("peerStateVir" in support and "peerScalarSenderVir" in support and
            "peerSuppressControllerVir" in support,
            "merged controller does not route AutoHunt/AutoPotion through peer state")
    require('"autosupport_controller", paths.autoBattle.blueIcon' in support,
            "AutoSupport baked tile still depends on loading its custom TGA at runtime")
    require("StateRejectResult" in support and "MutationResultStartRejected: 4" in support,
            "AutoSupport start failures do not have dedicated client feedback")
    require("AutoSupportUI must run first" in menu and
            "buildOptionalButtonMouseUp(autoSupportRoute.requestCellVir)" in menu,
            "AutoSupport menu button is not a required menu child")
    require("0x3F6" in support and "0x3F7" in support,
            "AutoSupport window/controller IDs are not isolated")

    require("AutoSupportButtonWindowId: 0x3F5" in menu,
            "menu AutoSupport child ID is missing")
    require("ROGlobalZeroMenu.AutoSupportRoute.v1" in menu,
            "menu AutoSupport optional route is missing")
    require(
        "priorVisibleVirs" in menu and
        "customVisibleVirs" in menu and
        "[autoHuntRoute.visibleVir, itemCollectionRoute.vir + 4]" in menu and
        "reservedControlRow: false" in menu and
        "reservedMenuSlot: true" in menu,
        "custom menu buttons do not fill available native-grid slots",
    )
    require("buildButtonHover(autoSupportHover.vir, 0, -20)" in menu and
            "buildButtonHover(autoHuntHover.vir, 0, -20)" in menu,
            "Auto UI tooltips are not anchored immediately above their native buttons")
    require("buildButtonHover = function(textVir, localX = null, localY = null)" in menu,
            "menu hover bridge does not support an explicit native local anchor")
    require(
        'NewButtonVis.CustomVisibilityKey = "NewButtonVisibility.CustomVisibility.v1"' in
        button_visibility and
        '{label: "Auto Hunt", bridgeKey: "AutoCombatUI.MenuButton.v1"}' in
        button_visibility and
        '{label: "AutoSupport", bridgeKey: "AutoSupportUI.MenuButton.v1"}' in
        button_visibility and
        '{label: "Item Collection", bridgeKey: "ItemCollectionUI.MenuButton.v1"}' in
        button_visibility and
        "this.applyCustomVisibility(key, index)" in button_visibility,
        "Show/Hide Buttons does not expose all custom menu choices order-independently",
    )
    require(
        'NewButtonVis.publishCustomButton("Auto Hunt", {' in autocombat and
        'NewButtonVis.publishCustomButton("AutoSupport", {' in support and
        'NewButtonVis.publishCustomButton("Item Collection", {' in item_collection and
        "Exe.SetUint32(route.visiblePhy, this.getCustomVisibility(label, 1))" in button_visibility,
        "custom menu bridges do not consume pending Show/Hide visibility",
    )
    require(
        'a.label("hover_status_item")' in support and
        "FeatureStatusItemRow" in support and
        '134, "hover_status_item"' in support and
        "AutoSupportUIStatic.ItemRowFlagsOffset + 2" in support,
        "Status Recovery item slot has no native hover tooltip",
    )
    for name in (
        "bt_autosupport_normal.bmp",
        "bt_autosupport_mouseon.bmp",
        "bt_autosupport_pressed.bmp",
        "bt_autosupport_old_normal.bmp",
        "bt_autosupport_old_mouseon.bmp",
        "bt_autosupport_old_pressed.bmp",
    ):
        require(name in menu, f"menu does not reference {name}")

    asset_root = ROOT / "Assets/AutoSupportUI/autosupport"
    require(asset_root.is_dir(), "dedicated AutoSupport asset root is missing")
    files = [path for path in asset_root.rglob("*") if path.is_file()]
    require(len(files) >= 100, f"expected full AutoSupport asset pack, found {len(files)} files")
    icon_root = asset_root / "menuicon"
    dimensions = {
        "bt_autosupport_normal.bmp": (45, 41),
        "bt_autosupport_mouseon.bmp": (45, 41),
        "bt_autosupport_pressed.bmp": (45, 41),
        "bt_autosupport_old_normal.bmp": (32, 34),
        "bt_autosupport_old_mouseon.bmp": (32, 34),
        "bt_autosupport_old_pressed.bmp": (32, 34),
    }
    for name, expected in dimensions.items():
        path = icon_root / name
        require(path.is_file(), f"missing icon {name}")
        with Image.open(path) as image:
            require(image.size == expected, f"{name} is {image.size}, expected {expected}")
            if "_old_" in name:
                rgb = image.convert("RGB")
                require(rgb.getpixel((4, 1)) != (255, 0, 255) and
                        rgb.getpixel((0, 17)) != (255, 0, 255),
                        f"{name} does not retain the native Classic frame")
    require((ROOT / "tools/build_autosupport_classic_menu_icons.py").is_file(),
            "reproducible Classic AutoSupport icon builder is missing")

    controller_root = ROOT / "Assets/AutoSupportUI/autosupport_controller"
    controller_frames = sorted(controller_root.glob("*.tga"))
    require(len(controller_frames) == 31,
            f"expected 30 active frames plus one inactive frame, found {len(controller_frames)}")
    for path in controller_frames:
        with Image.open(path) as image:
            require(image.size == (72, 72), f"{path.name} is not 72x72")
    support_size = bright_size(controller_root / "inactive.tga")
    hunt_size = bright_size(ROOT / "Assets/AutoSupportUI/autobattle/inactive.tga")
    require(all(abs(a - b) <= 2 for a, b in zip(support_size, hunt_size)),
            f"AutoSupport/Hunt visual sizes differ ({support_size} vs {hunt_size})")
    active_hashes = {
        hashlib.sha256(path.read_bytes()).digest()
        for path in controller_root.glob("active_*.tga")
    }
    require(len(active_hashes) == 30,
            f"native blue loop did not produce 30 distinct frames ({len(active_hashes)})")
    builder = (ROOT / "tools/build_autosupport_icon_assets.py").read_text(encoding="utf-8")
    require("render_autohunt_controller_frames import bake" in builder and
            "math.sin" not in builder,
            "AutoSupport controller still uses synthetic scale pulsing")

    effect_root = asset_root / "effect/roz_autosupport"
    expected_strs = {
        "autosupport_red/autosupport_red.str": b"auto_support_red.tga",
        "autosupport_blue_start/autosupport_blue_start.str": b"auto_support_blue.tga",
        "autosupport_blue_loop/autosupport_blue_loop.str": b"auto_support_blue.tga",
    }
    for relative, texture in expected_strs.items():
        path = effect_root / relative
        require(path.is_file(), f"missing native effect {relative}")
        data = path.read_bytes()
        require(data.startswith(b"STRM"), f"{relative} is not a Ragnarok STR file")
        require(texture in data, f"{relative} does not reference {texture.decode()}")
        if "blue_loop" in relative:
            require(int.from_bytes(data[16:20], "little") == 17,
                    "AutoSupport blue loop does not retain all 17 native layers")
            require(b"auto_particle.tga" in data and
                    b"auto_particleline_00.tga" in data,
                    "AutoSupport blue loop lost native orbit-particle textures")

    glyph_centers = {}
    for relative in (
        "autosupport_red/auto_support_red.tga",
        "autosupport_blue_loop/auto_support_blue.tga",
    ):
        with Image.open(effect_root / relative) as image:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            weighted = []
            for y in range(rgba.height):
                for x in range(rgba.width):
                    red, green, blue, opacity = rgba.getpixel((x, y))
                    gold = red > blue + 35 and green > blue + 10 and red > 150
                    if opacity > 12 and not gold:
                        weighted.append((x, opacity))
            total = sum(opacity for _, opacity in weighted)
            require(total > 0, f"{relative} has no non-sparkle glyph pixels")
            glyph_centers[relative] = sum(x * opacity for x, opacity in weighted) / total
            corners = (
                (0, 0, 16, 16), (112, 0, 128, 16),
                (0, 112, 16, 128), (112, 112, 128, 128),
            )
            require(all(alpha.crop(box).getextrema()[1] == 0 for box in corners),
                    f"{relative} contains a second square/frame")
    center_delta = abs(glyph_centers["autosupport_red/auto_support_red.tga"] -
        glyph_centers["autosupport_blue_loop/auto_support_blue.tga"])
    require(center_delta <= 0.5,
            f"red/blue AutoSupport glyph centers differ by {center_delta:.2f}px")
    with (
        Image.open(effect_root / "autosupport_red/auto_support_red.tga") as red_image,
        Image.open(effect_root /
            "autosupport_blue_loop/auto_support_blue.tga") as blue_image,
    ):
        red_alpha = red_image.convert("RGBA").getchannel("A")
        blue_alpha = blue_image.convert("RGBA").getchannel("A")
        require(red_alpha.tobytes() == blue_alpha.tobytes(),
                "red/blue AutoSupport glyph alpha masks are not pixel-identical")

    loop_effect = load_str(effect_root /
        "autosupport_blue_loop/autosupport_blue_loop.str")
    red_effect = load_str(effect_root / "autosupport_red/autosupport_red.str")
    red_glyph_layers = [layer for layer in red_effect.layers
                        if "auto_support_red.tga" in layer.textures]
    glyph_layers = [layer for layer in loop_effect.layers
                    if "auto_support_blue.tga" in layer.textures]
    require(len(glyph_layers) == 2,
            "AutoSupport blue loop does not contain both native glyph passes")
    for layer in glyph_layers:
        sizes = {
            (round(max(key.xy[:4]) - min(key.xy[:4]), 4),
             round(max(key.xy[4:]) - min(key.xy[4:]), 4))
            for key in layer.keys
        }
        require(len(sizes) == 1,
                f"AutoSupport glyph geometry changes across frames: {sizes}")
    red_sizes = {(round(max(key.xy[:4]) - min(key.xy[:4]), 4),
                  round(max(key.xy[4:]) - min(key.xy[4:]), 4))
                 for layer in red_glyph_layers for key in layer.keys}
    blue_sizes = {(round(max(key.xy[:4]) - min(key.xy[:4]), 4),
                   round(max(key.xy[4:]) - min(key.xy[4:]), 4))
                  for layer in glyph_layers for key in layer.keys}
    require(red_sizes == blue_sizes,
            f"red/blue STR glyph quads differ: {red_sizes} vs {blue_sizes}")

    main_profile = (ROOT / "profiles/2025-07-16 PROFILE MAIN.yml").read_text(encoding="utf-8")
    require("- AutoSupportUI" in main_profile and
            main_profile.index("- AutoCombatUI") < main_profile.index("- AutoSupportUI") <
            main_profile.index("- ROGlobalZeroUITheme"),
            "main EXE profile does not apply AutoSupport before menu dependencies")

    clif = (banquet / "src/map/clif.cpp").read_text(encoding="utf-8")
    state = (banquet / "src/map/autosupport_core.hpp").read_text(encoding="utf-8")
    ai = (banquet / "src/map/autosupport/ai/support_ai.cpp").read_text(encoding="utf-8")
    core = (banquet / "src/map/autosupport_core.cpp").read_text(encoding="utf-8")
    commands = (banquet / "src/map/autosupport/runtime/support_commands.cpp").read_text(
        encoding="utf-8"
    )
    command_header = (
        banquet / "src/map/autosupport/runtime/support_commands.hpp"
    ).read_text(encoding="utf-8")
    helpers = (
        banquet / "src/map/autosupport/runtime/support_helpers.cpp"
    ).read_text(encoding="utf-8")
    support_types = (
        banquet / "src/map/autosupport/core/support_types.cpp"
    ).read_text(encoding="utf-8")
    packets = (banquet / "src/map/packets.hpp").read_text(encoding="utf-8")
    sql = (banquet / "sql-files/autosupport/support_assistant.sql").read_text(encoding="utf-8")
    require("AUTOSUPPORT_UI_MAGIC = 0x49555341" in clif, "Banquet ASUI magic missing")
    require("clif_parse_autosupport_ui(fd, sd)" in clif, "Banquet ASUI dispatch missing")
    require("AUTOSUPPORT_UI_SETTING_MASTER = 19" in clif, "Player mutation missing")
    require("as_start_session(" in clif and "ASStartMode::AutoSupport" in clif,
            "ASUI bypasses the AutoSupport start gate")
    require("autosupport_follow_char_id" in state, "stable master state missing")
    require("autosupport_follow_char_id" in sql, "stable master SQL migration missing")
    require("trying party fallback" not in ai.lower(),
            "AutoSupport still silently substitutes a party master")
    require("map_charid2sd(sd->as.autosupport_follow_char_id)" in helpers,
            "master resolver does not prefer stable character ID")
    require("autohunt_ui_resolve_inventory_item(sd, requested_client_index" in clif,
            "ASUI item registration does not resolve client inventory indices")
    require("autosupport_ui_apply_recovery_skill_slot" in clif and
            "MAX_AUTOHUNT_UI_SKILL_ROWS + requested_slot" in clif,
            "status-recovery rows do not use isolated storage slots")
    require("autosupport_ui_apply_potion_action" in clif and
            "autosupport_ui_apply_buff_item_action" in clif,
            "potion/item registration handlers are missing")
    require("AUTOSUPPORT_UI_SETTING_STATUS_RECOVERY_ITEM = 66" in clif and
            "autosupport_ui_apply_status_recovery_item_action" in clif,
            "Status Recovery item registration handler is missing")
    require("status_recovery_item_id" in state and
            "preference_type`,`item_id`) VALUES (%d, 3" in core,
            "Status Recovery item state is not persisted")
    require("PACKET_ZC_AUTOSUPPORT_UI_SNAPSHOT" in packets and
            "statusRecoveryItemRow" in packets and
            "sizeof(PACKET_ZC_AUTOSUPPORT_UI_SNAPSHOT) == 3840" in packets,
            "ASUI status-item snapshot extension is missing")
    require("SupportAction::USE_STATUS_ITEM" in ai and
            "as_status_recovery_item_needed" in commands,
            "Status Recovery item runtime consumption is incomplete")
    require(
        "SettingStopMelee: 7" in support and
        "SettingBasicInput: 64" in support and
        "uint8 stopmelee = 0" in state and
        "uint8 normal_attack_sp_threshold = 10" in state and
        "if (setting_id == 7)" in clif and
        "setting_id == AUTOHUNT_UI_SETTING_BASIC_INPUT" in clif and
        "sd->as.normal_attack_sp_threshold = static_cast<uint8>(value)" in clif and
        "p.stopMelee = autohunt_ui_u16_clamp(sd->as.stopmelee)" in clif and
        "sd->as.normal_attack_sp_threshold, 100" in clif and
        "VALUES (%d, 47, %u, %u, %u)" in core and
        "case 47:" in core,
        "AutoSupport Basic settings 7/64 lack state, input, snapshot, or persistence wiring",
    )
    require(
        "if (setting_id == 59)" in clif and
        "value2 > 100" in clif and
        "std::min<uint32>(value2, 99)" in clif and
        "(v >= 99) ? 99 : v" in core,
        "Potion threshold setting 59 must accept 0..100 and persist at the 99 cap",
    )
    require(
        "as_support_select_potion" in ai and
        "decision.action = SupportAction::USE_POTION" in ai and
        "as_autopotion_needed(sd, *it)" in commands,
        "Potion rows register but are not wired to live AutoSupport decisions",
    )
    require(
        "as_support_select_buff_item" in ai and
        "decision.action = SupportAction::USE_BUFF_ITEM" in ai and
        "category_ == ASItemCategory::BUFF_ITEM" in commands,
        "Buff Item rows register but are not wired to live AutoSupport decisions",
    )
    assist_selector = ai[
        ai.index("static bool as_support_select_assist_attack"):
        ai.index("AutoSupportDecision as_analyze_support")
    ]
    lex_selector = ai[
        ai.index("bool as_support_select_lex_aeterna"):
        ai.index("bool as_support_teleport_to_master")
    ]
    require(
        "as_resolve_master_attack_target(sd, master)" in assist_selector and
        "detection_result" not in assist_selector and
        "aggressive_behavior" not in assist_selector,
        "Attack skills or normal attacks can still acquire a non-master target",
    )
    require(
        "as_resolve_master_attack_target(sd, master)" in lex_selector and
        "unit_skilluse_id" not in lex_selector and
        "skill_get_range2" in lex_selector,
        "Lex Aeterna is not a single queued master-target decision",
    )
    require(
        "master->ud.skilltarget" in helpers and
        "as_select_active_normal_attack_target_id" in helpers and
        "as_authorize_assist_target(input)" in helpers and
        "as_should_stop_stale_assist_attack" in helpers,
        "master attack/cast intent is not enforced by the live target resolver",
    )
    require(
        ai.index("as_stop_stale_assist_attack(sd);") <
        ai.index("if (sd->as.autosupport_follow_target[0]"),
        "stale continuous attack is not stopped before no-master early returns",
    )
    require(
        "config_kind_ == ASSkillConfigKind::Attack ||" in commands and
        "skill_id_ == PR_LEXAETERNA" in commands and
        commands.count(
            "as_is_current_master_attack_target(sd, target_id_)"
        ) >= 2 and
        "sd->as.last_lex_cast = now;" in commands and
        "sd->as.assist_normal_attack_active = true;" in commands,
        "queued Attack, normal attack, or Lex lacks execution-time ownership validation",
    )
    require(
        "as_stop_assist_attack(sd);" in core and
        "assist_normal_attack_active" in state and
        "buff_config.skill_id == PR_LEXAETERNA" in ai,
        "assist attack lifecycle or Lex generic-path exclusion is incomplete",
    )
    require(
        "as_support_select_assist_attack" in ai and
        "decision.action = SupportAction::ATTACK" in ai and
        "ASSkillConfigKind::Attack" in core and
        "ASNormalAttackCommand" in core and
        "class ASNormalAttackCommand" in command_header and
        "unit_attack(" in commands,
        "Attack-skill and normal-attack settings are not wired to live execution",
    )
    require(
        "as_support_select_loot" in ai and
        "effective_prio_item_config == 1" in ai and
        '"loot-first"' in ai and '"support-first"' in ai and
        "as_handle_loot_weight_limit" in support_types and
        "as_select_loot_return_resource" in support_types and
        "pc_useitem(sd, choice.inventory_index)" in support_types and
        "status_change_end(sd, SC_AUTOSUPPORT" in support_types,
        "Support First/Loot First or loot-limit actions are not live runtime behavior",
    )
    require(
        "autosupport_ui_apply_move_item_action" in clif and
        "autosupport_ui_apply_move_skill_action" in clif and
        "move_teleport_item_id" in helpers and
        "move_teleport_skill_id" in helpers and
        "as_find_flywing_inventory_index" in helpers and
        "pc_randomwarp(sd, CLR_TELEPORT)" in helpers and
        "move_return_item_id" in support_types and
        "move_return_skill_id == AL_TELEPORT" in support_types,
        "Move-tab registrations are not consumed by live teleport/return behavior",
    )
    require(
        "skill_id == AL_TELEPORT && skill_level >= 2" in clif and
        "move_return_skill_level >= 2" in support_types and
        "skill_consume_requirement(sd, AL_TELEPORT, 2, 1)" in support_types and
        "pc_setpos(sd, choice.destination_mapindex" in support_types and
        "(skill_id == AL_WARP && skill_level >= 1)" not in clif,
        "Move Return must accept and execute only learned Teleport level 2",
    )
    require("loot_category_bits" in state and "move_teleport_item_id" in state,
            "AutoSupport loot/move state is missing")
    require("VALUES (%d, 46" in core,
            "AutoSupport loot policy is not persisted")
    require("SupportAction::PICKUP" in ai and "as_support_select_loot" in ai,
            "AutoSupport AI does not schedule server-authoritative looting")
    require("ASPickupCommand::execute" in commands and "pc_takeitem" in commands,
            "AutoSupport pickup execution is missing")
    require("ui_delay_input_slot" in state and
            "autosupport_ui_try_handle_delay_amount" in clif and
            "autosupport_ui_apply_delay_slot" in clif,
            "AutoSupport setting 47 delay-dialog flow is incomplete")
    require("AUTOSUPPORT_UI_RESULT_START_REJECTED = 4" in clif,
            "AutoSupport start-policy rejection result is missing")
    require("autosupport players don't loot" not in ai,
            "legacy AutoSupport loot suppression is still present")

    print(f"PASS: AutoSupport UI contract ({len(files)} assets, router v4, ASUI server)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
