# Personal UI extensions on upstream WARP

Integrated on 2026-09-22 over upstream commit
`39c90df4b9df55f72aff980681e11f81981eb590`. The seven QJS modules and their
artwork/runtime payloads were recovered from the existing personal WARP working
copy, not from an older release tag. These patches target **2025-07-16 Ragexe**.

## Patch picker

| Patch title | Internal name | ID | Category |
| --- | --- | --- | --- |
| Inline Chat Item Icons | ChatItemIcons | 10004 | UI CUSTOMIZATION |
| Native VIP UI | VipUI | 10008 | UI CUSTOMIZATION |
| Original Announcements with Item Icons | NoticeMarquee | 10007 | UI CUSTOMIZATION |
| Battle Pass | BattlepassUI | 10003 | SPECIAL CUSTOMIZATIONS |
| Renewal NPC Dialog UI | ModernNpcDialog | 10005 | UI CUSTOMIZATION |
| Supplied Renewal Chat UI | ModernChatUI | 10001 | UI CUSTOMIZATION |
| Zeny Gacha UI With Pity | GachaUI | 10006 | UI CUSTOMIZATION |

Open `win32/WARP.exe` from this repository. A WARP process opened from another
folder continues to use that other installation. Select the patches and apply
them to a clean compatible source EXE. This integration does not change saved
personal profiles, patch the installed game EXE, or deploy server files.

VIP, Battle Pass and Gacha require their matching server implementations.
Gacha retains the latest v22 banners, wallet/ticket controls and reveal behavior.
Its UI artwork goes into `gachaui`; rewards and ticket icons are resolved from
item IDs, not bundled `item_*` pictures. The asset installers preserve existing
custom artwork and repair missing files beside the chosen output EXE.

## Upstream coexistence

The upstream ItemDescriptionUI and all existing upstream patch registrations
remain available. AutoCombatUI keeps the upstream RTTI-aware frame-vtable
cloning fix. Its only personal additions are the exported native helpers and
the independently routed shared `0x0BF6` BPUI/GCHA receiver. Using those helpers
does not require selecting AutoCombatUI.

Keep these extensions in local commits on `main`, tracking `origin/main`.
Use merge-based pulls (`pull.rebase=false`, `pull.ff=true`) to combine upstream
updates with the personal commits. Pulls may still need conflict resolution
when upstream edits the same code. Review conflicts and repeat the checks;
never replace the whole shared helper with an older personal version or reset
the repository to discard personal changes. A local commit is not a GitHub push.

## Verification

`tools/build_chat_item_icons.py` accepts a private profile with the desired
patches and a **new** output directory. It copies an isolated WARP fixture and
rewrites the output EXE path; it does not replace the installed game client.
For this integration, the test profile selects exactly the seven patches above.

```powershell
uv run python tools/build_chat_item_icons.py --profile path/to/test-profile.yml --output Outputs/personal-ui/combined --with-vip --with-notice
uv run python tools/build_vip_matrix.py Outputs/personal-ui/combined --output Outputs/personal-ui/order-matrix
uv run python tools/verify_vip_payload.py
uv run python tools/verify_item_grade_color_contract.py --source-only
uv run --with pillow --with pefile --with capstone --with unicorn python tools/run_vip_redesign_checks.py Outputs/personal-ui/combined/Ragnarok-chat-test.exe --output Outputs/personal-ui/vip-checks
```

Also run the native Battle Pass/Gacha, chat, NPC dialog and stock-announcement
suites, the packet router tests against combined/reversed/standalone builds,
and the six JS asset/font-input checks. Python native tests use `pillow`,
`pefile`, `capstone` and `unicorn`; the JS checks run with Node.js. Native tests
are offline emulation with explicit client boundaries, not live gameplay
acceptance. No live purchase, claim, mail or player reset is part of this test.

The historical `stable-battlepass-gacha.json` remains unchanged. Its check
correctly reports newer GachaUI and AutoCombatUI source changes relative to the
September 15 baseline. Do not refresh that baseline merely to clear the check.
Review those changes, run the current tests and obtain in-game acceptance
before deploying a newly patched game client.

### Integration results (2026-09-22)

- All seven features built together without skipped patches; reversed selection
  order and BP-only, Gacha-only and VIP-only variants also built successfully.
- All 20 VIP suites and 19 combined-client behavior/inventory suites passed.
- Packet dispatch passed combined, reversed, BP-only and Gacha-only cases.
  Standalone BP names, Gacha item capture, VIP lifecycle, reversed VIP window
  ordering and actual item-resource lookup checks also passed.
- Six JS installer/font checks, both runtime source/payload integrity checks,
  unique patch registration checks and the 100-check upstream item/grade source
  contract passed. The historical source-manifest differences noted above are
  expected and were not hidden by refreshing its hashes.
- The imported native QJS modules remain byte-identical to the recovered
  personal copies. Existing upstream item-renderer and ItemDescriptionUI source
  was not changed. The installed client and the previous WARP folder were not
  modified; live gameplay acceptance has not been performed for this build.
