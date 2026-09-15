#!/usr/bin/env python3
"""Static regression gate for the QJS item/enchant-grade color renderer.

The source gate is intentionally structural.  It checks the generated-code
builder, native grade-title boundary gates, and companion patches rather than
accepting documentation strings as proof of behavior.

Final PE cases use this label grammar:

    VERSION/MODE/LABELS[/ORDER]=PATH

VERSION is 2025 or 2026, MODE is item or grade, LABELS is stock or custom,
and ORDER is optional outside --strict-matrix.  ORDER uses the short patch
names item, grade, and labels joined in selection order, for example:

    --case 2026/grade/custom/labels-grade-item=C:\builds\2026-lgi.exe

The strict matrix requires the eleven meaningful patch-order configurations
for each target client.  It is a static/disassembly gate; the live screenshot
matrix in docs/item-grade-color-renderer-contract.md remains mandatory.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

ITEM_SOURCE = Path("Scripts/Patches/CustomColoredItemName.qjs")
GRADE_SOURCE = Path("Scripts/Patches/CustomColoredEnchantGradeName.qjs")
LABEL_SOURCE = Path("Scripts/Patches/CustomEnchantGradeLabels.qjs")
EXTNAME_SOURCE = Path("Scripts/Patches/ExtNameTextStatic.qjs")
ENTITY_TEXT_SOURCE = Path("Scripts/Patches/EntityTextStatic.qjs")
EMOJI_SOURCE = Path("Scripts/Patches/FluentEmoji.qjs")

IMAGE_FILE_MACHINE_I386 = 0x014C
PE32_MAGIC = 0x010B


@dataclass(frozen=True)
class Profile:
    key: str
    aliases: frozenset[str]
    text_out_direct: int
    text_out_thunk: int
    extent_iat: int
    set_text_color_iat: int
    wide_to_multi_iat: int
    item_tooltip_stock: int
    item_id_getter: int
    inventory_caller_item_offset: int
    equipment_caller_item_offset: int
    item_label_sites: tuple[int, ...]
    ground_tooltip_stock: int
    ground_sites: tuple[int, ...]
    balloon_plain_stock: int
    balloon_plain_sites: tuple[int, ...]
    balloon_styled_stock: int
    balloon_styled_sites: tuple[int, ...]
    grade_title_formatter: int
    item_title_formatter: int
    item_title_formatter_prologue: bytes
    grade_title_formatter_sites: tuple[int, int]
    grade_title_guard_bytes: tuple[bytes, bytes]
    grade_boundary_append_site: int
    grade_boundary_append_stock: int
    grade_boundary_append_prefix: bytes
    grade_boundary_append_suffix: bytes
    grade_inline_site: int
    grade_inline_replay: int
    grade_inline_resume: int
    grade_inline_displaced: bytes


PROFILES = {
    "2025": Profile(
        key="2025",
        aliases=frozenset({"2025", "20250716", "2025-07-16"}),
        text_out_direct=0x005476C7,
        text_out_thunk=0x00DBA690,
        extent_iat=0x00FC112C,
        set_text_color_iat=0x00FC10E0,
        wide_to_multi_iat=0x00FC1204,
        item_tooltip_stock=0x00A753D0,
        item_id_getter=0x005D98A0,
        inventory_caller_item_offset=0x138,
        equipment_caller_item_offset=0x230,
        item_label_sites=(
            0x0094D594,
            0x0094D639,
            0x008B9EC6,
            0x008B9F48,
            0x008BA00E,
            0x008BA0B1,
        ),
        ground_tooltip_stock=0x00C72CE0,
        ground_sites=(0x00C7147C,),
        balloon_plain_stock=0x00A27C20,
        balloon_plain_sites=(0x00826529,),
        balloon_styled_stock=0x00A26540,
        balloon_styled_sites=(0x00826503,),
        grade_title_formatter=0x006A2AC0,
        item_title_formatter=0x008A0570,
        item_title_formatter_prologue=bytes.fromhex(
            "55 8B EC 51 53 56 57"
        ),
        grade_title_formatter_sites=(0x008A0620, 0x008A0822),
        grade_title_guard_bytes=(
            bytes.fromhex(
                "33 C9 66 3B 88 88 00 00 00 7D 19 "
                "6A 01 53 FF 36 8B C8"
            ),
            bytes.fromhex(
                "33 C9 66 3B 88 88 00 00 00 7D 2E "
                "6A 01 53 FF 36 8B C8"
            ),
        ),
        grade_boundary_append_site=0x008A062A,
        grade_boundary_append_stock=0x008D2450,
        grade_boundary_append_prefix=bytes.fromhex("8B CF 56"),
        grade_boundary_append_suffix=bytes.fromhex("8B 45 08"),
        grade_inline_site=0x008A082D,
        grade_inline_replay=0x008A0833,
        grade_inline_resume=0x008A0846,
        grade_inline_displaced=bytes.fromhex("8B 47 04 3B 47 08"),
    ),
    "2026": Profile(
        key="2026",
        aliases=frozenset({"2026", "20260219", "2026-02-19"}),
        text_out_direct=0x00550747,
        text_out_thunk=0x00E60C50,
        extent_iat=0x010C70E0,
        set_text_color_iat=0x010C7130,
        wide_to_multi_iat=0x010C7244,
        item_tooltip_stock=0x00AD6510,
        item_id_getter=0x005FCCF0,
        inventory_caller_item_offset=0x138,
        equipment_caller_item_offset=0x230,
        item_label_sites=(
            0x00987744,
            0x009877E9,
            0x008F3F76,
            0x008F3FF8,
            0x008F40BE,
            0x008F4161,
        ),
        ground_tooltip_stock=0x00CDD350,
        ground_sites=(0x00CDBADC,),
        balloon_plain_stock=0x00A86510,
        balloon_plain_sites=(0x0085E209,),
        balloon_styled_stock=0x00A84E30,
        balloon_styled_sites=(0x0085E1E3,),
        grade_title_formatter=0x006D5780,
        item_title_formatter=0x008DA690,
        item_title_formatter_prologue=bytes.fromhex(
            "55 8B EC 51 53 56 57"
        ),
        grade_title_formatter_sites=(0x008DA740, 0x008DA942),
        grade_title_guard_bytes=(
            bytes.fromhex(
                "33 C9 66 3B 88 88 00 00 00 7D 19 "
                "6A 01 53 FF 36 8B C8"
            ),
            bytes.fromhex(
                "33 C9 66 3B 88 88 00 00 00 7D 2E "
                "6A 01 53 FF 36 8B C8"
            ),
        ),
        grade_boundary_append_site=0x008DA74A,
        grade_boundary_append_stock=0x0090C4C0,
        grade_boundary_append_prefix=bytes.fromhex("8B CF 56"),
        grade_boundary_append_suffix=bytes.fromhex("8B 45 08"),
        grade_inline_site=0x008DA94D,
        grade_inline_replay=0x008DA953,
        grade_inline_resume=0x008DA966,
        grade_inline_displaced=bytes.fromhex("8B 47 04 3B 47 08"),
    ),
}

PROFILE_BY_ALIAS = {
    alias: profile
    for profile in PROFILES.values()
    for alias in profile.aliases
}

VALID_MODES = frozenset({"item", "grade"})
VALID_LABEL_SETS = frozenset({"stock", "custom"})
VALID_ORDER_PARTS = frozenset({"item", "grade", "labels"})

STRICT_ORDERS = {
    ("item", "stock"): frozenset({"item"}),
    ("item", "custom"): frozenset({"item-labels", "labels-item"}),
    ("grade", "stock"): frozenset({"item-grade", "grade-item"}),
    ("grade", "custom"): frozenset(
        {
            "item-grade-labels",
            "item-labels-grade",
            "grade-item-labels",
            "grade-labels-item",
            "labels-item-grade",
            "labels-grade-item",
        }
    ),
}

KNOWN_ITEM_COLOR_DLLS = frozenset(
    {
        "boh.dll",
        "boh_text.dll",
        "boh_item_color.dll",
        "boh_itemcolor.dll",
        "item_color.dll",
        "itemcolor.dll",
        "grade_color.dll",
        "gradecolor.dll",
        "enchant_grade.dll",
    }
)

FORBIDDEN_BRIDGE_APIS = frozenset(
    {
        "gettextextentpoint32a",
        "gettextextentpoint32w",
        "gettextalign",
        "settextalign",
        "gettickcount",
        "gettickcount64",
        "queryperformancecounter",
        "timegettime",
    }
)


@dataclass(frozen=True)
class CaseSpec:
    raw_label: str
    profile: Profile
    mode: str
    labels: str
    order: str | None
    path: Path


@dataclass(frozen=True)
class GradeConfig:
    address: int
    mode: int
    label_count: int
    label_table: int
    labels: tuple[tuple[int, str | None], ...]


class ContractFailure(RuntimeError):
    """A user-actionable verification failure."""


class SourceChecks:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.count = 0

    def require(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            raise ContractFailure(f"source: {message}")

    def read_qjs(self, relative: Path) -> str:
        path = self.root / relative
        self.require(path.is_file(), f"missing {relative.as_posix()}")
        raw = path.read_bytes()
        self.require(
            not raw.startswith(b"\xef\xbb\xbf"),
            f"{relative.as_posix()} has a UTF-8 BOM",
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractFailure(
                f"source: {relative.as_posix()} is not valid UTF-8: {exc}"
            ) from exc
        self.require(
            text.count("\n") == text.count("\r\n"),
            f"{relative.as_posix()} contains LF-only lines; QJS requires CRLF",
        )
        self.require(
            raw.startswith(b"/*"),
            f"{relative.as_posix()} must begin with the patch header",
        )
        return text

    def run(self) -> int:
        item = self.read_qjs(ITEM_SOURCE)
        grade = self.read_qjs(GRADE_SOURCE)
        labels = self.read_qjs(LABEL_SOURCE)
        extname = self.read_qjs(EXTNAME_SOURCE)
        if (self.root / ENTITY_TEXT_SOURCE).exists():
            extname += self.read_qjs(ENTITY_TEXT_SOURCE)
        emoji = self.read_qjs(EMOJI_SOURCE)

        self.require(
            "ExtNameTextStatic.isPatchSelected" in extname
            and "ExtNameTextStatic.isStateLive" in extname
            and "ExtNameTextStatic.isPatchSelected(state.ownerPatch)"
            in extname,
            "shared text state is not gated by current patch ownership",
        )
        self.require(
            "lookupVir: missing.virAddr" in extname
            and "findWideVir: missing.virAddr" not in extname,
            "minimal emoji-only text state does not publish the lookup callback consumed by buildFindWide",
        )
        self.require(
            "refusing stale text-bridge state" in extname
            and "ExtNameTextStatic.isStateLive(current)" in extname,
            "text-surface patching or static refresh can reuse stale shared callbacks",
        )
        self.require(
            "ExtNameTextStatic.isPatchSelected(emoji.ownerPatch)" in extname,
            "deselected FluentEmoji callbacks can be embedded into the shared text bridge",
        )
        self.require(
            extname.count(
                "ExtNameTextStatic.isPatchSelected(itemState.ownerPatch)"
            )
            == 2,
            "an ExtName reapply path can invoke deselected cached ItemColor code",
        )
        self.require(
            "ownerPatch: _" in emoji
            and "ExtNameTextStatic.isPatchSelected(state.ownerPatch)" in emoji,
            "FluentEmoji renderer cache is not scoped to its selected owner patch",
        )
        self.require(
            "ownerPatch: _" in item
            and "ExtNameTextStatic.isPatchSelected(state.ownerPatch)" in item
            and "ItemColorStatic.GradeConfigOwner" in item,
            "item-color or grade-config cache is not scoped to current patch ownership",
        )

        for relative, source in (
            (ITEM_SOURCE, item),
            (GRADE_SOURCE, grade),
            (LABEL_SOURCE, labels),
        ):
            code = strip_js_comments(source)
            forbidden_dll_tokens = (
                "CustomDLL.",
                "CustomDLL.applySpec",
                "addVisualDll(",
            )
            self.require(
                not any(token in code for token in forbidden_dll_tokens),
                f"{relative.as_posix()} reintroduces a custom-DLL dependency",
            )

        text_out = extract_js_function(item, "ItemColorStatic.buildTextOut")
        lookup = extract_js_function(item, "ItemColorStatic.buildLookup")
        lookup_id = extract_js_function(item, "ItemColorStatic.buildLookupId")
        lookup_grade = extract_js_function(
            item, "ItemColorStatic.buildLookupGrade"
        )
        producer_color_match = extract_js_function(
            item, "ItemColorStatic.buildProducerColorMatch"
        )
        register_rendered_name = extract_js_function(
            item, "ItemColorStatic.buildRegisterRenderedName"
        )
        item_title_formatter = extract_js_function(
            item, "ItemColorStatic.buildItemTitleFormatter"
        )
        item_title_trampoline = extract_js_function(
            item, "ItemColorStatic.buildItemTitleFormatterTrampoline"
        )
        item_tooltip = extract_js_function(
            item, "ItemColorStatic.buildItemTooltip"
        )
        ground_tooltip = extract_js_function(
            item, "ItemColorStatic.buildGroundTooltip"
        )
        drain = extract_js_function(item, "ItemColorStatic.buildDrain")
        create_config = extract_js_function(
            item, "ItemColorStatic.createGradeConfig"
        )
        write_registry = extract_js_function(
            item, "ItemColorStatic.writeGradeLabelRegistry"
        )
        append_gate = extract_js_function(
            item, "ItemColorStatic.buildGradeTitleBoundaryAppendGate"
        )
        inline_gate = extract_js_function(
            item, "ItemColorStatic.buildGradeTitleInlineGate"
        )
        patch_boundaries = extract_js_function(
            item, "ItemColorStatic.patchGradeTitleBoundaries"
        )
        patch_item_title = extract_js_function(
            item, "ItemColorStatic.patchItemTitleFormatter"
        )
        text_out_code = strip_js_comments(text_out)
        lookup_code = strip_js_comments(lookup)
        lookup_id_code = strip_js_comments(lookup_id)
        lookup_grade_code = strip_js_comments(lookup_grade)
        producer_color_match_code = strip_js_comments(producer_color_match)
        register_rendered_name_code = strip_js_comments(
            register_rendered_name
        )
        item_title_formatter_code = strip_js_comments(item_title_formatter)
        item_title_trampoline_code = strip_js_comments(item_title_trampoline)
        item_tooltip_code = strip_js_comments(item_tooltip)
        ground_tooltip_code = strip_js_comments(ground_tooltip)
        append_gate_code = strip_js_comments(append_gate)
        inline_gate_code = strip_js_comments(inline_gate)
        patch_boundaries_code = strip_js_comments(patch_boundaries)
        patch_item_title_code = strip_js_comments(patch_item_title)

        forbidden_renderer_tokens = (
            "GetTextExtentPoint32",
            "GetTextAlign",
            "SetTextAlign",
            "apis.extent",
            "StateContinuation",
            "ContinuationMs",
            "splitWidth",
            "splitDraw",
        )
        self.require(
            not any(
                token in text_out_code for token in forbidden_renderer_tokens
            ),
            "TextOutW bridge contains split/extent/alignment/continuation logic",
        )
        item_code = strip_js_comments(item)
        renderer_code = "\n".join(
            (
                item_code,
                strip_js_comments(grade),
                strip_js_comments(labels),
            )
        )
        self.require(
            "StateContinuation" not in item_code
            and "ContinuationMs" not in item_code
            and "GradeContinuation" not in item_code,
            "cross-call grade continuation state is present",
        )
        forbidden_global_heuristics = (
            "GetTickCount",
            "getTickCount",
            "GetTickCount64",
            "QueryPerformanceCounter",
            "timeGetTime",
            "Date.now",
            "System.LocalTime",
            "GetTextExtentPoint32",
            "GetTextAlign",
            "SetTextAlign",
        )
        self.require(
            not any(
                token in renderer_code
                for token in forbidden_global_heuristics
            ),
            "renderer reintroduces timer/extent/alignment heuristics",
        )
        self.require(
            re.search(
                r"\b(?:coord(?:inate)?s?|last[XY]|"
                r"state(?:last|draw|text|continuation)?[XY]|"
                r"continuation[XY]|"
                r"(?:state|continuation)\w*(?:tick|time|hdc|coord)\w*)\b",
                renderer_code,
                re.IGNORECASE,
            )
            is None,
            "renderer reintroduces coordinate/timer/global continuation state",
        )

        item_lookup_at = text_out.find('a.label("item_lookup")')
        grade_mode_at = text_out.find(
            "gradeConfigVir + ItemColorStatic.GradeConfigColorMode"
        )
        grade_lookup_at = text_out.find("a.call(lookupVir)", grade_mode_at)
        fallback_lookup_at = text_out.find("a.call(lookupVir)", item_lookup_at)
        self.require(
            min(item_lookup_at, grade_mode_at, grade_lookup_at) >= 0
            and grade_mode_at < grade_lookup_at < item_lookup_at,
            "grade lookup does not precede item-database lookup",
        )
        self.require(
            fallback_lookup_at > item_lookup_at,
            "normal item lookup is not a grade-miss fallback",
        )

        downstream_calls = [
            match.start()
            for match in re.finditer(
                r"a\.call\s*\(\s*previousTextOutVir\s*\)", text_out
            )
        ]
        native_foreground_at = text_out.find('a.label("foreground_policy")')
        foreground_at = text_out.find('a.label("draw_foreground")')
        stock_at = text_out.find('a.label("draw_stock")')
        return_at = text_out.find('a.label("return")')
        self.require(
            len(downstream_calls) == 4,
            "TextOutW bridge must have exactly one native balloon shadow, "
            "one producer-owned balloon foreground, one custom foreground, "
            "and one stock downstream call site",
        )
        self.require(
            native_foreground_at >= 0
            and foreground_at > native_foreground_at
            and stock_at > foreground_at
            and downstream_calls[0] < native_foreground_at
            and downstream_calls[1] > native_foreground_at
            and downstream_calls[1] < foreground_at
            and downstream_calls[2] > foreground_at
            and downstream_calls[2] < stock_at
            and downstream_calls[3] > stock_at,
            "TextOutW balloon-shadow/producer/custom/stock branches are not "
            "mutually exclusive single-span draws",
        )
        foreground = text_out[foreground_at:stock_at]
        self.require(
            "0xFF, 0x75, 0xF0" in foreground
            and "0xFF, 0x75, 0x14" in foreground,
            "foreground draw does not use the original UTF-16 pointer and "
            "bounded render count",
        )
        self.require(
            foreground.find("a.call(previousTextOutVir)")
            < foreground.find("ItemColorStatic.callIat(a, apis.setTextColor)")
            < foreground.find('a.jmp("return")'),
            "foreground path does not restore the original HDC color",
        )

        quantity_at = text_out.find('a.label("quantity_digits_back")')
        quantity_commit_at = text_out.find('a.label("quantity_commit")')
        self.require(
            grade_lookup_at < quantity_at < quantity_commit_at < item_lookup_at,
            "quantity-tail shortening is not confined to a grade match",
        )
        for token, description in (
            ("0xF8, 0x20", "leading space in exact ' ea.' tail"),
            ("0xFA, 0x65", "'e' in exact quantity tail"),
            ("0xFC, 0x61", "'a' in exact quantity tail"),
            ("0xFE, 0x2E", "period in exact quantity tail"),
            ("0x30", "lower digit bound"),
            ("0x39", "upper digit bound"),
            ("0xFE, 0x3A", "optional colon delimiter"),
            ("0x89, 0x55, 0xF0", "render-count commit"),
        ):
            self.require(
                token in text_out[grade_lookup_at:item_lookup_at],
                f"grade quantity parser is missing {description}",
            )

        apply_color_at = text_out.find('a.label("apply_color")')
        shadow_end = native_foreground_at
        shadow = text_out[apply_color_at:shadow_end]
        suppress_dark_at = shadow.find('a.label("suppress_dark_pass")')
        self.require(
            apply_color_at > item_lookup_at and shadow_end > apply_color_at,
            "matched color/shadow path is missing",
        )
        self.require(
            shadow.count("0x20") >= 3
            and "ItemColorStatic.callIat(a, apis.setTextColor)" in shadow,
            "dark-pass RGB threshold or HDC restoration is missing",
        )
        self.require(
            "stateVir + ItemColorStatic.StateBalloonScope" in shadow
            and suppress_dark_at >= 0
            and shadow.find("a.call(previousTextOutVir)")
            < suppress_dark_at,
            "semantic item-balloon dark pass does not restore and draw its "
            "native outline before the non-balloon suppression branch",
        )
        self.require(
            re.search(
                r"a\.emit\s*\(\s*0xB8\s*\)\s*;\s*a\.dword\s*\(\s*1\s*\)"
                r"\s*;\s*a\.jmp\s*\(\s*\"return\"\s*\)",
                shadow[suppress_dark_at:],
            )
            is not None,
            "Inventory/Alt+Q/Item Description dark pass is not suppressed "
            "after the balloon-only outline branch",
        )

        self.require(
            'a.label("normal_compare")' in lookup
            and 'a.label("normal_suffix")' in lookup
            and 'a.label("slot_suffix")' in lookup,
            "exact base-item and canonical suffix matching are missing",
        )
        self.require(
            "ItemColorStatic.EntryDynamicTitle" in lookup_code
            and 'a.label("dynamic_fragment")' in lookup_code
            and 'a.label("dynamic_prefix_compare")' in lookup_code
            and 'a.label("dynamic_suffix_compare")' in lookup_code
            and "0x83, 0xF8, 0x03" in lookup_code
            and "0x83, 0xF9, 0x03" in lookup_code,
            "producer-derived wrapped Alt+Q prefix/suffix matching is missing "
            "or is not restricted to dynamic title records",
        )
        self.require(
            "a.emit(0x6A, 0x03" in text_out_code
            and text_out_code.find("a.emit(0x6A, 0x03")
            > text_out_code.find('a.label("item_lookup")')
            and "stateVir + ItemColorStatic.StateBalloonScope"
            in text_out_code[
                text_out_code.find('a.label("item_lookup")'):
                text_out_code.find('a.label("apply_color")')
            ],
            "TextOutW does not use the current-span-only dynamic fragment "
            "fallback for non-balloon wrapped titles",
        )
        suffix_at = lookup_code.find('a.label("normal_suffix")')
        space_at = lookup_code.find('a.label("space_suffix")', suffix_at)
        colon_at = lookup_code.find('a.label("colon_quantity")', suffix_at)
        next_entry_at = lookup_code.find('a.label("next_entry")', suffix_at)
        suffix_grammar = lookup_code[suffix_at:next_entry_at]
        self.require(
            0 <= suffix_at < space_at < colon_at < next_entry_at,
            "item suffix grammar does not contain ordered space, slot, and "
            "slotless-colon paths",
        )
        self.require(
            re.search(
                r"a\.emit\s*\(\s*0x80\s*,\s*0x3E\s*,\s*0x3A\s*\)"
                r"\s*;\s*a\.jcc\s*\(\s*0x84\s*,\s*"
                r"\"colon_quantity\"\s*\)",
                suffix_grammar,
            )
            is not None,
            "exact slotless 'Name: <digits> ea.' entry path is missing",
        )
        self.require(
            "a.emit(0x66, 0x81, 0x3E, 0x3A, 0x20)" in suffix_grammar
            and 'a.jmp("quantity_digits")' in suffix_grammar
            and "a.dword(0x2E616520)" in suffix_grammar,
            "slotless/slotted colon quantity grammar does not require exact "
            "': <digits> ea.' syntax",
        )
        self.require(
            "strstr" not in lookup_code.lower()
            and "substring" not in lookup_code.lower(),
            "lookup uses substring matching",
        )
        self.require(
            'a.label("grade_number_scan")' in drain
            and "gradeConfigVir + ItemColorStatic.GradeConfigLabelCount"
            in drain
            and "gradeConfigVir + ItemColorStatic.GradeConfigLabelTable"
            in drain,
            "_GRADE_ records are not parsed by numeric grade through the "
            "active client label registry",
        )
        self.require(
            "server-label" in drain and "without trusting server text" in drain,
            "numeric grade parser no longer explicitly rejects server-label "
            "authority",
        )
        self.require(
            "PacketV2Magic: 0x324C4349" in item
            and "PacketV2Version: 2" in item
            and "PacketV2RecordSize: 12" in item
            and "PacketV2KindItem: 0" in item
            and "PacketV2KindGrade: 1" in item,
            "ICL2 typed trailer constants are missing",
        )
        v2_parse_at = drain.find('a.label("parse_v2")')
        v2_item_at = drain.find('a.label("v2_item")')
        v2_grade_at = drain.find('a.label("v2_grade")')
        publish_at = drain.find('a.label("publish")')
        self.require(
            0 <= v2_parse_at < v2_item_at < v2_grade_at < publish_at
            and "ItemColorStatic.PacketV2Magic" in drain[v2_parse_at:publish_at]
            and "ItemColorStatic.PacketV2RecordSize" in drain[v2_parse_at:publish_at]
            and "stateVir + ItemColorStatic.StateItemIdCount" in drain,
            "drain does not parse the backward-compatible ICL2 trailer after "
            "legacy names",
        )
        self.require(
            "itemIdTableVir" in drain[v2_item_at:v2_grade_at]
            and "ItemColorStatic.ItemIdEntryItemId" in drain[v2_item_at:v2_grade_at]
            and "ItemColorStatic.ItemIdEntrySize" in drain[v2_item_at:v2_grade_at],
            "ICL2 item records are not stored in the bounded item-id table",
        )
        self.require(
            'a.label("v2_grade_registry_loop")' in drain
            and 'a.label("v2_grade_label_scan")' in drain
            and "ItemColorStatic.EntryGrade" in drain[v2_grade_at:publish_at],
            "ICL2 grade records are not resolved numerically through the "
            "active label registry",
        )
        self.require(
            "stateVir + ItemColorStatic.StateItemIdCount" in lookup_id_code
            and "ItemColorStatic.ItemIdEntryItemId" in lookup_id_code
            and "ItemColorStatic.ItemIdEntrySize" in lookup_id_code
            and "strstr" not in lookup_id_code.lower()
            and "substring" not in lookup_id_code.lower(),
            "item-id lookup table is missing or uses text matching",
        )
        self.require(
            "stateVir + ItemColorStatic.StateCount" in lookup_grade_code
            and "ItemColorStatic.EntryGrade" in lookup_grade_code
            and "a.emit(0xC1, 0xE8, 0x08, 0x3B, 0xC6)"
            in lookup_grade_code
            and "strstr" not in lookup_grade_code.lower(),
            "numeric grade lookup is missing or falls back to grade text",
        )
        self.require(
            "ItemColorStatic.TablePacketCapacity" in drain
            and "stateVir + ItemColorStatic.StateDynamicNext" in drain
            and drain.count("a.emit(0x83, 0xC8, ItemColorStatic.EntryGrade)")
            >= 2,
            "packet grade records do not retain numeric grade identity or "
            "reserve the bounded native-title cache",
        )
        self.require(
            "ItemColorStatic.ItemIdGetter" in item_title_formatter_code
            and "a.call(lookupGradeVir)" in item_title_formatter_code
            and "a.call(lookupIdVir)" in item_title_formatter_code
            and item_title_formatter_code.find("a.call(lookupGradeVir)")
            < item_title_formatter_code.find("a.call(lookupIdVir)")
            and "a.call(registerNameVir)" in item_title_formatter_code
            and "a.emit(0x89, 0x02)" in item_title_formatter_code
            and "0xC2, 0x20, 0x00" in item_title_formatter_code,
            "native CItem title formatter does not apply grade then ItemId "
            "and canonicalize the exact rendered title",
        )
        self.require(
            "ItemColorStatic.NameCapacity - 1"
            in register_rendered_name_code
            and "ItemColorStatic.TableCapacity"
            in register_rendered_name_code
            and "ItemColorStatic.TableDynamicCapacity"
            in register_rendered_name_code
            and "ItemColorStatic.EntryDynamic"
            in register_rendered_name_code
            and 'a.label("dedupe_loop")' in register_rendered_name_code
            and 'a.label("ring_index")' in register_rendered_name_code,
            "native rendered-title recognition cache is not bounded, "
            "deduplicated, ring-replaced, and recognition-only",
        )
        self.require(
            "stateVir + ItemColorStatic.StateItemIdCount"
            in producer_color_match_code
            and "ItemColorStatic.ItemIdEntrySize"
            in producer_color_match_code
            and "ItemColorStatic.EntryGrade"
            in producer_color_match_code,
            "foreground ownership does not recognize native ItemId/grade "
            "COLORREF values",
        )
        self.require(
            "a.emit(0x55, 0x8B, 0xEC, 0x51, 0x53, 0x56, 0x57)"
            in item_title_trampoline_code
            and "ItemColorStatic.ItemTitleFormatter + 7"
            in item_title_trampoline_code
            and "Exe.SetJMP(entryPhy, state.itemTitleFormatterVir, 0)"
            in patch_item_title_code
            and "Exe.SetNOPs(entryPhy + 5, 2)" in patch_item_title_code
            and "ItemTitleFormatterPrologue" in patch_item_title_code,
            "native item-title formatter trampoline/prologue gate is missing",
        )

        for function_name, function_code in (
            ("ItemTooltip", item_tooltip_code),
            ("GroundTooltip", ground_tooltip_code),
        ):
            grade_probe_at = function_code.find("a.call(lookupVir)")
            id_lookup_at = function_code.find('a.label("id_lookup")')
            id_call_at = function_code.find("a.call(lookupIdVir)")
            legacy_label_at = function_code.find('a.label("legacy_lookup")')
            legacy_call_at = function_code.find(
                "a.call(lookupVir)", legacy_label_at
            )
            self.require(
                0
                <= grade_probe_at
                < id_lookup_at
                < id_call_at
                < legacy_label_at
                < legacy_call_at,
                f"{function_name} does not give grade ownership first, then "
                "ItemId, then legacy ItemName fallback",
            )
            self.require(
                "ItemColorStatic.ItemIdGetter" in function_code
                and "lookupIdVir" in function_code
                and "a.call(registerNameVir)" in function_code,
                f"{function_name} does not use the native CItem item-id "
                "accessor and register its exact producer title",
            )

        self.require(
            "0x53, 0x56, 0x57, 0x51" in item_tooltip_code
            and "0x59, 0x5F, 0x5E, 0x5B" in item_tooltip_code
            and "a.jmp(ItemColorStatic.ItemTooltipShow)"
            in item_tooltip_code,
            "ItemTooltip bridge must preserve incoming thiscall ECX across "
            "all drain/lookups and restore it before the stock tail jump",
        )
        self.require(
            'a.label("foreground_policy")' in text_out_code
            and "stateVir + ItemColorStatic.StateBalloonScope"
            in text_out_code
            and "a.call(producerColorMatchVir)" in text_out_code
            and "ItemColorStatic.EntryDynamic" in text_out_code
            and text_out_code.count(
                'a.jcc(0x84, "draw_foreground")'
            )
            >= 2
            and text_out_code.count(
                'a.jcc(0x85, "draw_producer_foreground")'
            )
            >= 1
            and "a.emit(0xC7, 0x45, 0xE8)" in text_out_code
            and text_out_code.find('a.label("foreground_policy")')
            < text_out_code.find('a.label("draw_foreground")'),
            "dynamic CItem titles do not own final TextOut foreground while "
            "semantic balloon draws preserve their producer ItemId color",
        )
        self.require(
            "InventoryCallerItemOffset" in item_tooltip
            and "EquipmentCallerItemOffset" in item_tooltip
            and "callVir + 5" in item_tooltip,
            "inventory/equipment ItemId bridge is not tied to profiled "
            "producer callsites",
        )
        inventory_this_at = item_tooltip_code.find(
            'a.label("caller_inventory")'
        )
        equipment_this_at = item_tooltip_code.find(
            'a.label("caller_equipment")'
        )
        have_item_at = item_tooltip_code.find(
            'a.label("caller_have_item")'
        )
        inventory_this = item_tooltip_code[
            inventory_this_at:equipment_this_at
        ]
        equipment_this = item_tooltip_code[equipment_this_at:have_item_at]
        self.require(
            0 <= inventory_this_at < equipment_this_at < have_item_at
            and "a.emit(0x8D, 0x88)" in inventory_this
            and "a.emit(0x8D, 0x88)" in equipment_this
            and "a.emit(0x8B, 0x88)" not in inventory_this
            and "a.emit(0x8B, 0x88)" not in equipment_this,
            "inventory/equipment ItemId bridge must LEA the profiled inline "
            "CItem locals; MOV dereferences the first field as an invalid "
            "ItemIdGetter this pointer and crashes on hover",
        )

        self.require(
            "const stockLabels = [0x44, 0x43, 0x42, 0x41]" in create_config,
            "stock disabled-label fallback is not D/C/B/A",
        )
        self.require(
            'ItemColorStatic.isPatchActive("CustomColoredEnchantGradeName")'
            in create_config,
            "late/early companion selection is not reflected in grade mode",
        )
        self.require(
            "GradeConfigDefaultTable" in write_registry
            and "Exe.SetUint32(countPhy, 4)" in write_registry,
            "disabled CustomEnchantGradeLabels does not restore stock labels",
        )
        self.require(
            "ItemColorStatic.enableGradeColors()" in grade
            and "ItemColorStatic.disableGradeColors()" in grade,
            "grade companion does not own the runtime grade-color mode",
        )
        self.require(
            "ItemColorStatic.installGradeLabelRegistry(labels)" in labels
            and "ItemColorStatic.resetGradeLabelRegistry()" in labels,
            "custom-label patch does not publish and clean up its exact map",
        )
        self.require(
            "const grade = entry.Grade" in labels
            and "labels.sort((a, b) => a.grade - b.grade)" in labels,
            "custom labels are not keyed and ordered by numeric grade",
        )

        for profile in PROFILES.values():
            block = extract_profile_block(
                item,
                "20250716" if profile.key == "2025" else "20260219",
            )
            self.require(
                profile_source_contract_matches(block, profile),
                f"{profile.key} native grade-boundary profile no longer "
                "matches the verifier contract",
            )

        append_mode = append_gate_code.find(
            "gradeConfigVir + ItemColorStatic.GradeConfigColorMode"
        )
        append_enabled = append_gate_code.find(
            'a.jcc(0x85, "skip_endpoint")', append_mode
        )
        append_stock = append_gate_code.find(
            "a.jmp(stockAppendVir)", append_enabled
        )
        append_skip = append_gate_code.find(
            'a.label("skip_endpoint")', append_stock
        )
        append_return = append_gate_code.find(
            "a.emit(0xC2, 0x04, 0x00)", append_skip
        )
        self.require(
            0
            <= append_mode
            < append_enabled
            < append_stock
            < append_skip
            < append_return,
            "helper endpoint gate is not conditional, stock-tail-jumping, "
            "and enabled-mode RET 4",
        )
        self.require(
            "a.call(stockAppendVir)" not in append_gate_code,
            "helper endpoint stock branch calls instead of tail-jumping",
        )

        inline_mode = inline_gate_code.find(
            "gradeConfigVir + ItemColorStatic.GradeConfigColorMode"
        )
        inline_enabled = inline_gate_code.find(
            'a.jcc(0x85, "skip_endpoint")', inline_mode
        )
        inline_mov = inline_gate_code.find(
            "a.emit(0x8B, 0x47, 0x04)", inline_enabled
        )
        inline_cmp = inline_gate_code.find(
            "a.emit(0x3B, 0x47, 0x08)", inline_mov
        )
        inline_replay = inline_gate_code.find(
            "a.jmp(ItemColorStatic.GradeTitleInlineReplay)", inline_cmp
        )
        inline_skip = inline_gate_code.find(
            'a.label("skip_endpoint")', inline_replay
        )
        inline_resume = inline_gate_code.find(
            "a.jmp(ItemColorStatic.GradeTitleInlineResume)", inline_skip
        )
        self.require(
            0
            <= inline_mode
            < inline_enabled
            < inline_mov
            < inline_cmp
            < inline_replay
            < inline_skip
            < inline_resume,
            "inline endpoint gate does not replay stock compare or skip only "
            "the guarded post-grade boundary",
        )

        self.require(
            "ItemColorStatic.GradeTitleFormatterCallSites" in patch_boundaries
            and "ItemColorStatic.GradeTitleGuardHex" in patch_boundaries
            and "ItemColorStatic.GradeTitleBoundaryAppendShape"
            in patch_boundaries,
            "native endpoint patch no longer validates formatter guards and "
            "stock append shape",
        )
        self.require(
            re.search(
                r"ItemColorStatic\.GradeTitleInlineReplay\s*!==\s*"
                r"ItemColorStatic\.GradeTitleInlinePatch\s*\+\s*6",
                patch_boundaries_code,
            )
            is not None
            and re.search(
                r"ItemColorStatic\.GradeTitleInlineResume\s*<=\s*"
                r"ItemColorStatic\.GradeTitleInlineReplay",
                patch_boundaries_code,
            )
            is not None,
            "inline endpoint patch no longer validates replay/resume bounds",
        )
        self.require(
            "Exe.SetCALL(" in patch_boundaries_code
            and "state.gradeTitleBoundaryAppendGateVir"
            in patch_boundaries_code
            and "Exe.SetJMP(" in patch_boundaries_code
            and "state.gradeTitleInlineGateVir" in patch_boundaries_code
            and "Exe.SetNOPs(inlinePhy + 5, 1)" in patch_boundaries_code,
            "native endpoint CALL/JMP installation is incomplete",
        )
        self.require(
            "ItemColorStatic.buildGradeTitleBoundaryAppendGate(" in item_code
            and "ItemColorStatic.buildGradeTitleInlineGate(" in item_code
            and "ItemColorStatic.patchGradeTitleBoundaries(state)" in item_code
            and "ItemColorStatic.patchGradeTitleBoundaries(current)"
            in item_code,
            "native boundary gates are not allocated and refreshed",
        )

        return self.count


def strip_js_comments(source: str) -> str:
    """Remove JS comments while preserving strings and line positions."""

    output: list[str] = []
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if line_comment:
            if char in "\r\n":
                line_comment = False
                output.append(char)
            else:
                output.append(" ")
            index += 1
            continue
        if block_comment:
            if char == "*" and following == "/":
                output.extend((" ", " "))
                block_comment = False
                index += 2
            else:
                output.append(char if char in "\r\n" else " ")
                index += 1
            continue
        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and following == "/":
            output.extend((" ", " "))
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            output.extend((" ", " "))
            block_comment = True
            index += 2
            continue
        output.append(char)
        if char in {"'", '"', "`"}:
            quote = char
        index += 1

    return "".join(output)


def extract_profile_block(source: str, build: str) -> str:
    pattern = re.compile(
        rf"^\t\t{re.escape(build)}:\s*\{{(?P<body>.*?)^\t\t\}}",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    if match is None:
        raise ContractFailure(f"source: missing ItemColorStatic profile {build}")
    return match.group("body")


def relative_branch_bytes(site: int, target: int, opcode: int) -> bytes:
    displacement = target - (site + 5)
    return bytes((opcode,)) + struct.pack("<i", displacement)


def profile_source_contract_matches(block: str, profile: Profile) -> bool:
    def hex_field(name: str, value: int) -> bool:
        return (
            re.search(
                rf"\b{re.escape(name)}\s*:\s*0x0*{value:X}\b",
                block,
                re.IGNORECASE,
            )
            is not None
        )

    def address_array(name: str, values: Sequence[int]) -> bool:
        rendered = r"\s*,\s*".join(
            rf"0x{value:08X}" for value in values
        )
        return (
            re.search(
                rf"\b{re.escape(name)}\s*:\s*\[\s*{rendered}\s*\]",
                block,
            )
            is not None
        )

    append_shape = (
        profile.grade_boundary_append_prefix
        + relative_branch_bytes(
            profile.grade_boundary_append_site,
            profile.grade_boundary_append_stock,
            0xE8,
        )
        + profile.grade_boundary_append_suffix
    )
    expected_hex_strings = (
        *(guard.hex(" ").upper() for guard in profile.grade_title_guard_bytes),
        append_shape.hex(" ").upper(),
        profile.grade_inline_displaced.hex(" ").upper(),
    )

    return (
        hex_field("GradeTitleFormatter", profile.grade_title_formatter)
        and hex_field("ItemTitleFormatter", profile.item_title_formatter)
        and (
            profile.item_title_formatter_prologue.hex(" ").upper()
            in block
        )
        and hex_field("ItemIdGetter", profile.item_id_getter)
        and hex_field(
            "InventoryCallerItemOffset",
            profile.inventory_caller_item_offset,
        )
        and hex_field(
            "EquipmentCallerItemOffset",
            profile.equipment_caller_item_offset,
        )
        and address_array(
            "GradeTitleFormatterCallSites",
            profile.grade_title_formatter_sites,
        )
        and all(value in block for value in expected_hex_strings)
        and hex_field(
            "GradeTitleBoundaryAppendCall",
            profile.grade_boundary_append_site,
        )
        and hex_field(
            "GradeTitleBoundaryAppendStock",
            profile.grade_boundary_append_stock,
        )
        and hex_field("GradeTitleInlinePatch", profile.grade_inline_site)
        and hex_field("GradeTitleInlineReplay", profile.grade_inline_replay)
        and hex_field("GradeTitleInlineResume", profile.grade_inline_resume)
    )


def extract_js_function(source: str, name: str) -> str:
    """Return one assignment-style JS function, respecting strings/comments."""

    marker = f"{name} = function"
    start = source.find(marker)
    if start < 0:
        raise ContractFailure(f"source: missing {name}")
    brace = source.find("{", start + len(marker))
    if brace < 0:
        raise ContractFailure(f"source: malformed {name}")

    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = brace
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if line_comment:
            if char in "\r\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
        index += 1

    raise ContractFailure(f"source: unterminated {name}")


def parse_case(value: str) -> CaseSpec:
    label, separator, raw_path = value.partition("=")
    if not separator or not label.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError(
            "case must be VERSION/MODE/LABELS[/ORDER]=PATH"
        )

    fields = [part.strip().lower() for part in re.split(r"[/:]", label)]
    if len(fields) not in {3, 4} or any(not part for part in fields):
        raise argparse.ArgumentTypeError(
            "case label must be VERSION/MODE/LABELS[/ORDER]"
        )

    version, mode, labels = fields[:3]
    profile = PROFILE_BY_ALIAS.get(version)
    if profile is None:
        raise argparse.ArgumentTypeError(
            f"unsupported client version {version!r}; use 2025 or 2026"
        )

    mode_aliases = {
        "item": "item",
        "item-only": "item",
        "grade": "grade",
        "item-grade": "grade",
    }
    mode = mode_aliases.get(mode, mode)
    if mode not in VALID_MODES:
        raise argparse.ArgumentTypeError("MODE must be item or grade")
    if labels not in VALID_LABEL_SETS:
        raise argparse.ArgumentTypeError("LABELS must be stock or custom")

    order = fields[3] if len(fields) == 4 else None
    if order is not None:
        parts = order.split("-")
        if (
            any(part not in VALID_ORDER_PARTS for part in parts)
            or len(parts) != len(set(parts))
        ):
            raise argparse.ArgumentTypeError(
                "ORDER must contain unique item, grade, and/or labels names"
            )
        expected_parts = {"item"}
        if mode == "grade":
            expected_parts.add("grade")
        if labels == "custom":
            expected_parts.add("labels")
        if set(parts) != expected_parts:
            raise argparse.ArgumentTypeError(
                f"ORDER {order!r} does not match MODE={mode}, LABELS={labels}"
            )

    return CaseSpec(
        raw_label=label,
        profile=profile,
        mode=mode,
        labels=labels,
        order=order,
        path=Path(raw_path.strip()),
    )


class PEImage:
    def __init__(self, path: Path) -> None:
        try:
            import pefile  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ContractFailure(
                "PE checks require pefile; run with .venv\\Scripts\\python.exe"
            ) from exc

        self.path = path
        if not path.is_file():
            raise ContractFailure(f"PE artifact does not exist: {path}")
        try:
            self.data = path.read_bytes()
            self.pe = pefile.PE(data=self.data, fast_load=False)
            self.pe.parse_data_directories()
        except (OSError, pefile.PEFormatError) as exc:
            raise ContractFailure(f"cannot parse PE {path}: {exc}") from exc

        if self.pe.FILE_HEADER.Machine != IMAGE_FILE_MACHINE_I386:
            raise ContractFailure(
                f"{path.name}: machine is 0x{self.pe.FILE_HEADER.Machine:04X}, "
                "expected x86 IMAGE_FILE_MACHINE_I386"
            )
        if self.pe.OPTIONAL_HEADER.Magic != PE32_MAGIC:
            raise ContractFailure(
                f"{path.name}: optional-header magic is "
                f"0x{self.pe.OPTIONAL_HEADER.Magic:04X}, expected PE32"
            )
        self.image_base = int(self.pe.OPTIONAL_HEADER.ImageBase)
        self.imports = self._read_imports()

    def _read_imports(self) -> dict[int, tuple[str, str]]:
        result: dict[int, tuple[str, str]] = {}
        for descriptor in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", ()):
            dll = decode_ascii(descriptor.dll).lower()
            for imported in descriptor.imports:
                name = (
                    decode_ascii(imported.name).lower()
                    if imported.name is not None
                    else f"ordinal_{imported.ordinal}"
                )
                result[int(imported.address)] = (dll, name)
        return result

    @property
    def imported_dlls(self) -> frozenset[str]:
        return frozenset(dll for dll, _ in self.imports.values())

    def offset(self, va: int, size: int = 1) -> int:
        rva = va - self.image_base
        if rva < 0:
            raise ContractFailure(f"{self.path.name}: VA 0x{va:08X} is unmapped")
        try:
            offset = int(self.pe.get_offset_from_rva(rva))
        except Exception as exc:  # pefile uses several exception types here
            raise ContractFailure(
                f"{self.path.name}: VA 0x{va:08X} is unmapped"
            ) from exc
        if offset < 0 or offset + size > len(self.data):
            raise ContractFailure(
                f"{self.path.name}: VA 0x{va:08X} extends outside the file"
            )
        return offset

    def is_mapped(self, va: int, size: int = 1) -> bool:
        try:
            self.offset(va, size)
        except ContractFailure:
            return False
        return True

    def is_executable(self, va: int) -> bool:
        rva = va - self.image_base
        for section in self.pe.sections:
            start = int(section.VirtualAddress)
            size = max(int(section.Misc_VirtualSize), int(section.SizeOfRawData))
            if start <= rva < start + size:
                return bool(int(section.Characteristics) & 0x20000000)
        return False

    def read(self, va: int, size: int) -> bytes:
        offset = self.offset(va, size)
        return self.data[offset : offset + size]

    def read_up_to(self, va: int, maximum: int) -> bytes:
        """Read through the containing section's raw tail, capped at maximum."""

        offset = self.offset(va)
        available = len(self.data) - offset
        for section in self.pe.sections:
            raw_start = int(section.PointerToRawData)
            raw_end = raw_start + int(section.SizeOfRawData)
            if raw_start <= offset < raw_end:
                available = min(available, raw_end - offset)
                break
        size = min(maximum, available)
        if size <= 0:
            raise ContractFailure(
                f"{self.path.name}: no raw bytes available at VA 0x{va:08X}"
            )
        return self.data[offset : offset + size]

    def u16(self, va: int) -> int:
        return struct.unpack("<H", self.read(va, 2))[0]

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]

    def c_string(self, va: int, limit: int = 128) -> str:
        raw = bytearray()
        for index in range(limit):
            byte = self.read(va + index, 1)[0]
            if byte == 0:
                if not raw:
                    raise ContractFailure(
                        f"{self.path.name}: empty label at 0x{va:08X}"
                    )
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ContractFailure(
                        f"{self.path.name}: invalid UTF-8 label at "
                        f"0x{va:08X}"
                    ) from exc
            raw.append(byte)
        raise ContractFailure(
            f"{self.path.name}: unterminated label at 0x{va:08X}"
        )


def decode_ascii(value: bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("ascii", errors="replace")


def relative_target(image: PEImage, site: int, opcode: int, kind: str) -> int:
    encoded = image.read(site, 5)
    if encoded[0] != opcode:
        raise ContractFailure(
            f"{image.path.name}: {kind} at 0x{site:08X} is "
            f"0x{encoded[0]:02X}, expected 0x{opcode:02X}"
        )
    displacement = struct.unpack("<i", encoded[1:])[0]
    return (site + 5 + displacement) & 0xFFFFFFFF


def disassemble_bridge(image: PEImage, bridge: int) -> tuple[list[object], bytes]:
    try:
        from capstone import (  # type: ignore[import-not-found]
            CS_ARCH_X86,
            CS_MODE_32,
            Cs,
        )
    except ImportError as exc:
        raise ContractFailure(
            "PE checks require capstone; run with .venv\\Scripts\\python.exe"
        ) from exc

    raw = image.read_up_to(bridge, 0x1000)
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    engine.detail = True
    instructions: list[object] = []
    end = 0
    for instruction in engine.disasm(raw, bridge):
        instructions.append(instruction)
        end = int(instruction.address + instruction.size - bridge)
        if instruction.mnemonic == "ret" and instruction.op_str.lower() in {
            "0x14",
            "20",
        }:
            break
    else:
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge at 0x{bridge:08X} has no "
            "RET 14h within 4096 bytes"
        )
    return instructions, raw[:end]


def disassemble_to_ret(
    image: PEImage,
    address: int,
    accepted_operands: frozenset[str],
    maximum: int = 0x1000,
) -> tuple[list[object], bytes]:
    try:
        from capstone import (  # type: ignore[import-not-found]
            CS_ARCH_X86,
            CS_MODE_32,
            Cs,
        )
    except ImportError as exc:
        raise ContractFailure(
            "PE checks require capstone; run with .venv\\Scripts\\python.exe"
        ) from exc

    raw = image.read_up_to(address, maximum)
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    engine.detail = True
    instructions: list[object] = []
    end = 0
    for instruction in engine.disasm(raw, address):
        instructions.append(instruction)
        end = int(instruction.address + instruction.size - address)
        if (
            instruction.mnemonic == "ret"
            and instruction.op_str.lower() in accepted_operands
        ):
            return instructions, raw[:end]
    rendered = ", ".join(sorted(accepted_operands))
    raise ContractFailure(
        f"{image.path.name}: function at 0x{address:08X} has no accepted "
        f"RET ({rendered}) within {maximum} bytes"
    )


def disassemble_prefix(
    image: PEImage,
    address: int,
    count: int,
    maximum: int = 96,
) -> list[object]:
    try:
        from capstone import (  # type: ignore[import-not-found]
            CS_ARCH_X86,
            CS_MODE_32,
            Cs,
        )
    except ImportError as exc:
        raise ContractFailure(
            "PE checks require capstone; run with .venv\\Scripts\\python.exe"
        ) from exc

    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    engine.detail = True
    instructions = list(
        engine.disasm(image.read_up_to(address, maximum), address, count)
    )
    if len(instructions) != count:
        raise ContractFailure(
            f"{image.path.name}: expected {count} instructions at "
            f"0x{address:08X}, decoded {len(instructions)}"
        )
    return instructions


def instruction_immediate(instruction: object, index: int = 0) -> int | None:
    try:
        from capstone.x86_const import X86_OP_IMM  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ContractFailure("capstone x86 constants are unavailable") from exc

    if index >= len(instruction.operands):
        return None
    operand = instruction.operands[index]
    if operand.type != X86_OP_IMM:
        return None
    return int(operand.imm) & 0xFFFFFFFF


def instruction_absolute_memory(
    instruction: object, index: int = 0
) -> int | None:
    try:
        from capstone.x86_const import (  # type: ignore[import-not-found]
            X86_OP_MEM,
            X86_REG_INVALID,
        )
    except ImportError as exc:
        raise ContractFailure("capstone x86 constants are unavailable") from exc

    if index >= len(instruction.operands):
        return None
    operand = instruction.operands[index]
    if (
        operand.type != X86_OP_MEM
        or operand.mem.base != X86_REG_INVALID
        or operand.mem.index != X86_REG_INVALID
    ):
        return None
    return int(operand.mem.disp) & 0xFFFFFFFF


def validate_mode_compare(instruction: object, grade_config: int) -> bool:
    return (
        instruction.mnemonic == "cmp"
        and instruction_absolute_memory(instruction, 0) == grade_config
        and instruction_immediate(instruction, 1) == 0
    )


def bridge_memory_references(instructions: Sequence[object]) -> Counter[int]:
    try:
        from capstone.x86_const import (  # type: ignore[import-not-found]
            X86_OP_MEM,
            X86_REG_INVALID,
        )
    except ImportError as exc:
        raise ContractFailure("capstone x86 constants are unavailable") from exc

    references: Counter[int] = Counter()
    for instruction in instructions:
        for operand in instruction.operands:
            if (
                operand.type == X86_OP_MEM
                and operand.mem.base == X86_REG_INVALID
                and operand.mem.index == X86_REG_INVALID
            ):
                references[int(operand.mem.disp) & 0xFFFFFFFF] += 1
    return references


def validate_default_grade_config(image: PEImage, address: int) -> bool:
    try:
        mode = image.u32(address)
        count = image.u32(address + 4)
        table = image.u32(address + 8)
        if mode not in {0, 1} or count == 0 or count > 256:
            return False
        expected_labels = "DCBA"
        for index, expected in enumerate(expected_labels):
            record = address + 12 + index * 8
            if image.u16(record) != index + 1:
                return False
            pointer = image.u32(record + 4)
            if pointer != address + 44 + index * 2:
                return False
            if image.u16(pointer) != ord(expected):
                return False
        return image.is_mapped(table, min(count, 256) * 8)
    except ContractFailure:
        return False


def discover_grade_config(
    image: PEImage,
    bridge_bytes: bytes,
    *,
    allow_opaque_labels: bool,
) -> GradeConfig:
    candidates: list[int] = []
    cursor = 0
    while True:
        cursor = bridge_bytes.find(b"\x83\x3d", cursor)
        if cursor < 0:
            break
        if cursor + 7 <= len(bridge_bytes) and bridge_bytes[cursor + 6] == 0:
            address = struct.unpack_from("<I", bridge_bytes, cursor + 2)[0]
            if validate_default_grade_config(image, address):
                candidates.append(address)
        cursor += 1

    candidates = sorted(set(candidates))
    if len(candidates) != 1:
        rendered = ", ".join(f"0x{value:08X}" for value in candidates) or "none"
        raise ContractFailure(
            f"{image.path.name}: expected one grade-config signature in the "
            f"TextOutW bridge, found {rendered}"
        )

    address = candidates[0]
    mode = image.u32(address)
    count = image.u32(address + 4)
    table = image.u32(address + 8)
    labels: list[tuple[int, str | None]] = []
    seen: set[int] = set()
    seen_pointers: set[int] = set()
    for index in range(count):
        record = table + index * 8
        grade = image.u16(record)
        pointer = image.u32(record + 4)
        if grade == 0 or grade in seen:
            raise ContractFailure(
                f"{image.path.name}: invalid/duplicate numeric grade {grade} "
                f"in config at 0x{address:08X}"
            )
        if pointer == 0 or pointer in seen_pointers or not image.is_mapped(pointer):
            raise ContractFailure(
                f"{image.path.name}: invalid/duplicate label pointer "
                f"0x{pointer:08X} for numeric grade {grade}"
            )
        seen.add(grade)
        seen_pointers.add(pointer)
        try:
            label: str | None = image.c_string(pointer)
        except ContractFailure:
            if not allow_opaque_labels:
                raise
            # The protected 2026 client encrypts original AddText storage on
            # disk and restores it at runtime.  The EXE-resident numeric table
            # and its mapped pointers remain statically verifiable.
            label = None
        labels.append((grade, label))

    return GradeConfig(
        address=address,
        mode=mode,
        label_count=count,
        label_table=table,
        labels=tuple(labels),
    )


def validate_surface_group(
    image: PEImage,
    sites: Iterable[int],
    stock_target: int,
    description: str,
    require_same: bool,
) -> tuple[int, ...]:
    targets = tuple(
        relative_target(image, site, 0xE8, f"{description} CALL")
        for site in sites
    )
    if any(target == stock_target for target in targets):
        raise ContractFailure(
            f"{image.path.name}: {description} still targets stock "
            f"0x{stock_target:08X}"
        )
    if require_same and len(set(targets)) != 1:
        rendered = ", ".join(f"0x{target:08X}" for target in targets)
        raise ContractFailure(
            f"{image.path.name}: {description} sites disagree: {rendered}"
        )
    if any(not image.is_executable(target) for target in targets):
        raise ContractFailure(
            f"{image.path.name}: {description} target is not executable"
        )
    return targets


def validate_native_grade_boundary(
    image: PEImage,
    profile: Profile,
    grade_config: GradeConfig,
) -> tuple[int, int]:
    for index, (site, guard) in enumerate(
        zip(
            profile.grade_title_formatter_sites,
            profile.grade_title_guard_bytes,
            strict=True,
        ),
        start=1,
    ):
        actual_guard = image.read(site - len(guard), len(guard))
        if actual_guard != guard:
            raise ContractFailure(
                f"{image.path.name}: native grade formatter guard {index} "
                f"at 0x{site - len(guard):08X} changed"
            )
        target = relative_target(
            image,
            site,
            0xE8,
            f"native grade formatter {index}",
        )
        if target != profile.grade_title_formatter:
            raise ContractFailure(
                f"{image.path.name}: native grade formatter {index} targets "
                f"0x{target:08X}, expected 0x{profile.grade_title_formatter:08X}"
            )

    append_site = profile.grade_boundary_append_site
    if (
        image.read(
            append_site - len(profile.grade_boundary_append_prefix),
            len(profile.grade_boundary_append_prefix),
        )
        != profile.grade_boundary_append_prefix
    ):
        raise ContractFailure(
            f"{image.path.name}: helper endpoint setup before "
            f"0x{append_site:08X} changed"
        )
    if (
        image.read(
            append_site + 5,
            len(profile.grade_boundary_append_suffix),
        )
        != profile.grade_boundary_append_suffix
    ):
        raise ContractFailure(
            f"{image.path.name}: helper endpoint continuation after "
            f"0x{append_site:08X} changed"
        )
    append_gate = relative_target(
        image,
        append_site,
        0xE8,
        "native grade helper endpoint gate",
    )
    if append_gate == profile.grade_boundary_append_stock:
        raise ContractFailure(
            f"{image.path.name}: native grade helper endpoint still targets "
            f"stock append 0x{append_gate:08X}; conditional boundary gate "
            "is missing"
        )
    if not image.is_executable(append_gate):
        raise ContractFailure(
            f"{image.path.name}: native grade helper gate "
            f"0x{append_gate:08X} is not executable"
        )
    if not image.is_executable(profile.grade_boundary_append_stock):
        raise ContractFailure(
            f"{image.path.name}: stock boundary append "
            f"0x{profile.grade_boundary_append_stock:08X} is not executable"
        )

    append_instructions = disassemble_prefix(image, append_gate, 4)
    append_cmp, append_enabled, append_stock, append_return = (
        append_instructions
    )
    if not validate_mode_compare(append_cmp, grade_config.address):
        raise ContractFailure(
            f"{image.path.name}: helper endpoint gate does not compare "
            "GradeConfigColorMode"
        )
    if (
        append_enabled.mnemonic not in {"jne", "jnz"}
        or instruction_immediate(append_enabled) != append_return.address
    ):
        raise ContractFailure(
            f"{image.path.name}: enabled helper endpoint branch does not "
            "skip exactly to its return"
        )
    if (
        append_stock.mnemonic != "jmp"
        or instruction_immediate(append_stock)
        != profile.grade_boundary_append_stock
    ):
        raise ContractFailure(
            f"{image.path.name}: disabled helper endpoint branch does not "
            "tail-jump the stock append"
        )
    if (
        append_return.mnemonic != "ret"
        or instruction_immediate(append_return) != 4
    ):
        raise ContractFailure(
            f"{image.path.name}: enabled helper endpoint does not RET 4 "
            "after skipping the guarded append"
        )

    inline_site = profile.grade_inline_site
    original_inline = image.read(
        inline_site,
        len(profile.grade_inline_displaced),
    )
    if original_inline == profile.grade_inline_displaced:
        raise ContractFailure(
            f"{image.path.name}: native inline grade boundary at "
            f"0x{inline_site:08X} is unpatched"
        )
    inline_gate = relative_target(
        image,
        inline_site,
        0xE9,
        "native inline grade boundary gate",
    )
    if image.read(inline_site + 5, 1) != b"\x90":
        raise ContractFailure(
            f"{image.path.name}: native inline grade boundary JMP lacks "
            "its trailing NOP"
        )
    if not image.is_executable(inline_gate):
        raise ContractFailure(
            f"{image.path.name}: native inline grade gate "
            f"0x{inline_gate:08X} is not executable"
        )
    if (
        profile.grade_inline_replay != inline_site + 6
        or profile.grade_inline_resume <= profile.grade_inline_replay
        or not image.is_executable(profile.grade_inline_replay)
        or not image.is_executable(profile.grade_inline_resume)
    ):
        raise ContractFailure(
            f"{image.path.name}: invalid native inline replay/resume profile"
        )

    inline_instructions = disassemble_prefix(image, inline_gate, 6)
    (
        inline_cmp,
        inline_enabled,
        inline_replay_mov,
        inline_replay_cmp,
        inline_stock,
        inline_skip,
    ) = inline_instructions
    if not validate_mode_compare(inline_cmp, grade_config.address):
        raise ContractFailure(
            f"{image.path.name}: inline endpoint gate does not compare "
            "GradeConfigColorMode"
        )
    if (
        inline_enabled.mnemonic not in {"jne", "jnz"}
        or instruction_immediate(inline_enabled) != inline_skip.address
    ):
        raise ContractFailure(
            f"{image.path.name}: enabled inline endpoint branch does not "
            "skip exactly to its resume jump"
        )
    replay_bytes = (
        bytes(inline_replay_mov.bytes) + bytes(inline_replay_cmp.bytes)
    )
    if replay_bytes != profile.grade_inline_displaced:
        raise ContractFailure(
            f"{image.path.name}: inline endpoint gate does not replay the "
            "exact displaced stock compare"
        )
    if (
        inline_stock.mnemonic != "jmp"
        or instruction_immediate(inline_stock) != profile.grade_inline_replay
    ):
        raise ContractFailure(
            f"{image.path.name}: disabled inline endpoint branch does not "
            "return to the stock append flow"
        )
    if (
        inline_skip.mnemonic != "jmp"
        or instruction_immediate(inline_skip) != profile.grade_inline_resume
    ):
        raise ContractFailure(
            f"{image.path.name}: enabled inline endpoint branch does not "
            "skip only the guarded post-grade boundary"
        )

    return append_gate, inline_gate


def verify_pe_case(case: CaseSpec) -> str:
    image = PEImage(case.path.resolve())
    profile = case.profile

    forbidden_dlls = sorted(
        dll
        for dll in image.imported_dlls
        if dll in KNOWN_ITEM_COLOR_DLLS
        or (
            dll.startswith("boh")
            and dll.endswith(".dll")
        )
    )
    if forbidden_dlls:
        raise ContractFailure(
            f"{image.path.name}: item/grade renderer imports custom DLL(s): "
            + ", ".join(forbidden_dlls)
        )

    bridge = relative_target(
        image, profile.text_out_direct, 0xE8, "TextOutW direct bridge"
    )
    thunk_bridge = relative_target(
        image, profile.text_out_thunk, 0xE9, "TextOutW thunk bridge"
    )
    if bridge != thunk_bridge:
        raise ContractFailure(
            f"{image.path.name}: TextOutW direct/thunk targets differ "
            f"(0x{bridge:08X} vs 0x{thunk_bridge:08X})"
        )
    if image.read(profile.text_out_direct + 5, 1) != b"\x90":
        raise ContractFailure(
            f"{image.path.name}: TextOutW direct bridge lacks trailing NOP"
        )
    if image.read(profile.text_out_thunk + 5, 1) != b"\x90":
        raise ContractFailure(
            f"{image.path.name}: TextOutW thunk bridge lacks trailing NOP"
        )
    if not image.is_executable(bridge):
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge 0x{bridge:08X} is not "
            "in an executable section"
        )

    instructions, bridge_bytes = disassemble_bridge(image, bridge)
    references = bridge_memory_references(instructions)
    referenced_imports = {
        address: image.imports[address]
        for address in references
        if address in image.imports
    }
    forbidden_refs = sorted(
        (address, dll, name)
        for address, (dll, name) in referenced_imports.items()
        if name in FORBIDDEN_BRIDGE_APIS
    )
    if profile.extent_iat in references:
        dll, name = image.imports.get(
            profile.extent_iat, ("profile", "GetTextExtentPoint32W")
        )
        forbidden_refs.append((profile.extent_iat, dll, name))
    if forbidden_refs:
        rendered = ", ".join(
            f"{dll}!{name}@0x{address:08X}"
            for address, dll, name in sorted(set(forbidden_refs))
        )
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge references forbidden "
            f"split/alignment API(s): {rendered}"
        )

    if references[profile.wide_to_multi_iat] < 1:
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge lacks bounded "
            "WideCharToMultiByte conversion"
        )
    if references[profile.set_text_color_iat] < 3:
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge has fewer than three "
            "SetTextColor sites (set, dark restore, foreground restore)"
        )

    direct_call_counts: Counter[int] = Counter(
        target
        for instruction in instructions
        if instruction.mnemonic == "call"
        and (target := instruction_immediate(instruction)) is not None
    )
    downstream_targets = [
        target for target, count in direct_call_counts.items() if count == 4
    ]
    if len(downstream_targets) != 1:
        raise ContractFailure(
            f"{image.path.name}: TextOutW bridge does not contain exactly four "
            "calls to one downstream renderer (balloon outline, producer "
            "foreground, custom foreground, stock)"
        )

    fragment_lookup = None
    for index, instruction in enumerate(instructions):
        if (
            instruction.mnemonic != "push"
            or instruction_immediate(instruction) != 3
        ):
            continue
        for candidate in instructions[index + 1:index + 6]:
            if candidate.mnemonic != "call":
                continue
            target = instruction_immediate(candidate)
            if target is None or not image.is_executable(target):
                continue
            try:
                _, candidate_bytes = disassemble_to_ret(
                    image,
                    target,
                    frozenset({""}),
                )
            except ContractFailure:
                continue
            if (
                bytes.fromhex("F7 47 08 04 00 00 00")
                in candidate_bytes
                and bytes.fromhex("83 F9 03") in candidate_bytes
                and bytes.fromhex("03 5F 04 2B D9") in candidate_bytes
            ):
                fragment_lookup = target
                break
        if fragment_lookup is not None:
            break
    if fragment_lookup is None:
        raise ContractFailure(
            f"{image.path.name}: final TextOutW bridge lacks the mode-3 "
            "dynamic-title-only anchored prefix/suffix lookup used by wrapped "
            "Alt+Q labels"
        )

    title_wrapper = relative_target(
        image,
        profile.item_title_formatter,
        0xE9,
        "native CItem title formatter bridge",
    )
    if image.read(profile.item_title_formatter + 5, 2) != b"\x90\x90":
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge lacks two "
            "trailing NOPs"
        )
    if not image.is_executable(title_wrapper):
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge "
            f"0x{title_wrapper:08X} is not executable"
        )
    title_instructions, title_bytes = disassemble_to_ret(
        image, title_wrapper, frozenset({"0x20", "32"})
    )
    title_calls = {
        target
        for instruction in title_instructions
        if instruction.mnemonic == "call"
        and (target := instruction_immediate(instruction)) is not None
    }
    if profile.item_id_getter not in title_calls:
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge does not call "
            f"ItemIdGetter 0x{profile.item_id_getter:08X}"
        )
    if bytes.fromhex("0F B7 86 88 00 00 00") not in title_bytes:
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge does not read "
            "the numeric enchant grade from CItem+88h"
        )
    if bytes.fromhex("6A 04 FF 75 F0 50 FF 75 F4 E8") not in title_bytes:
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge does not mark "
            "its exact generated text as a dynamic title record"
        )
    trampoline = None
    for target in title_calls:
        if (
            image.is_executable(target)
            and image.read(target, len(profile.item_title_formatter_prologue))
            == profile.item_title_formatter_prologue
            and image.read(
                target + len(profile.item_title_formatter_prologue), 1
            )
            == b"\xE9"
        ):
            resume = relative_target(
                image,
                target + len(profile.item_title_formatter_prologue),
                0xE9,
                "CItem title formatter trampoline resume",
            )
            if resume == (
                profile.item_title_formatter
                + len(profile.item_title_formatter_prologue)
            ):
                trampoline = target
                break
    if trampoline is None:
        raise ContractFailure(
            f"{image.path.name}: CItem title formatter bridge has no exact "
            "stock-prologue trampoline"
        )

    validate_surface_group(
        image,
        profile.item_label_sites,
        profile.item_tooltip_stock,
        "inventory/equipment item-label",
        require_same=True,
    )
    validate_surface_group(
        image,
        profile.ground_sites,
        profile.ground_tooltip_stock,
        "ground-item label",
        require_same=True,
    )
    validate_surface_group(
        image,
        profile.balloon_plain_sites,
        profile.balloon_plain_stock,
        "plain item-balloon",
        require_same=True,
    )
    validate_surface_group(
        image,
        profile.balloon_styled_sites,
        profile.balloon_styled_stock,
        "styled item-balloon",
        require_same=True,
    )

    grade_config = discover_grade_config(
        image,
        bridge_bytes,
        allow_opaque_labels=(
            case.profile.key == "2026" and case.labels == "custom"
        ),
    )
    expected_mode = 1 if case.mode == "grade" else 0
    if grade_config.mode != expected_mode:
        raise ContractFailure(
            f"{image.path.name}: grade mode is {grade_config.mode}, expected "
            f"{expected_mode} for case {case.raw_label}"
        )

    append_gate, inline_gate = validate_native_grade_boundary(
        image,
        profile,
        grade_config,
    )

    default_table = grade_config.address + 12
    if case.labels == "stock":
        expected = ((1, "D"), (2, "C"), (3, "B"), (4, "A"))
        if (
            grade_config.label_table != default_table
            or grade_config.label_count != 4
            or grade_config.labels != expected
        ):
            raise ContractFailure(
                f"{image.path.name}: stock label mode is not exact D/C/B/A"
            )
    else:
        grades = {grade for grade, _ in grade_config.labels}
        if grade_config.label_table == default_table:
            raise ContractFailure(
                f"{image.path.name}: custom-label case still points to the "
                "stock D/C/B/A table"
            )
        if not {1, 2, 3, 4}.issubset(grades):
            raise ContractFailure(
                f"{image.path.name}: custom-label table does not define "
                "numeric grades 1-4"
            )

    label_summary = ",".join(
        f"{grade}:{label if label is not None else '<protected>'}"
        for grade, label in grade_config.labels
    )
    return (
        f"bridge=0x{bridge:08X}, title=0x{title_wrapper:08X}, "
        f"grade_mode={grade_config.mode}, "
        f"labels=[{label_summary}], grade_gates="
        f"0x{append_gate:08X}/0x{inline_gate:08X}, "
        f"wrapped_lookup=0x{fragment_lookup:08X}, "
        f"instructions={len(instructions)}"
    )


def validate_strict_matrix(cases: Sequence[CaseSpec]) -> None:
    missing: list[str] = []
    for version in ("2025", "2026"):
        for (mode, labels), required_orders in STRICT_ORDERS.items():
            present = {
                case.order
                for case in cases
                if case.profile.key == version
                and case.mode == mode
                and case.labels == labels
            }
            for order in sorted(required_orders - present):
                missing.append(f"{version}/{mode}/{labels}/{order}")
    if missing:
        raise ContractFailure(
            "strict matrix is missing: " + ", ".join(missing)
        )

    resolved = [case.path.resolve() for case in cases]
    duplicates = sorted(
        str(path)
        for path, count in Counter(resolved).items()
        if count > 1
    )
    if duplicates:
        raise ContractFailure(
            "strict matrix reuses artifact path(s): " + ", ".join(duplicates)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the QJS item/enchant-grade renderer source contract and "
            "optionally inspect patched 32-bit Ragexe artifacts without "
            "executing them."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  .\\.venv\\Scripts\\python.exe "
            "tools\\verify_item_grade_color_contract.py --source-only\n\n"
            "  .\\.venv\\Scripts\\python.exe "
            "tools\\verify_item_grade_color_contract.py ^\n"
            "    --case "
            "2025/grade/stock/item-grade=C:\\builds\\2025-ig.exe ^\n"
            "    --case "
            "2026/grade/custom/labels-grade-item=C:\\builds\\2026-lgi.exe\n\n"
            "--strict-matrix requires, for each version: item/stock/item; "
            "both item/custom orders; both grade/stock orders; and all six "
            "grade/custom permutations (22 unique artifacts total)."
        ),
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="check the three QJS sources only; do not parse final PE files",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        type=parse_case,
        metavar="VERSION/MODE/LABELS[/ORDER]=PATH",
        help=(
            "labeled final-PE case; repeat as needed. VERSION accepts "
            "2025/20250716 or 2026/20260219"
        ),
    )
    parser.add_argument(
        "--strict-matrix",
        action="store_true",
        help=(
            "require all 22 target/config/selection-order cases before "
            "checking artifacts"
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repository root for source checks (default: script parent)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cases: list[CaseSpec] = args.case

    if args.source_only and cases:
        parser.error("--source-only cannot be combined with --case")
    if args.strict_matrix and args.source_only:
        parser.error("--strict-matrix requires final PE --case arguments")
    if args.strict_matrix and not cases:
        parser.error("--strict-matrix requires final PE --case arguments")
    if not args.source_only and not cases:
        parser.error("select --source-only or provide one or more --case values")

    failures: list[str] = []
    source_count = 0
    try:
        source_count = SourceChecks(args.repo_root.resolve()).run()
        print(f"PASS source ({source_count} checks)")
    except (ContractFailure, OSError) as exc:
        failures.append(str(exc))
        print(f"FAIL {exc}", file=sys.stderr)

    if args.strict_matrix:
        try:
            validate_strict_matrix(cases)
            print("PASS strict-matrix coverage (22 unique cases)")
        except ContractFailure as exc:
            failures.append(str(exc))
            print(f"FAIL {exc}", file=sys.stderr)

    for case in cases:
        try:
            details = verify_pe_case(case)
            print(f"PASS {case.raw_label} ({details})")
        except (ContractFailure, OSError, struct.error) as exc:
            message = f"{case.raw_label}: {exc}"
            failures.append(message)
            print(f"FAIL {message}", file=sys.stderr)

    if failures:
        print(
            f"FAIL item/grade renderer contract ({len(failures)} failure(s))",
            file=sys.stderr,
        )
        return 1

    print(
        "PASS item/grade renderer contract "
        f"({source_count} source checks, {len(cases)} PE case(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
