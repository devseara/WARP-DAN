# WARP0716

## Development Status — Active Again

**WARP0716 development has resumed.** After a pause, the project is back open — I'll keep working on patches as time allows.

**What's been built so far:**
- 40 recommended patches for the 2025-07-16 kRO Ragexe client
- Custom Jobs system (Reforged)
- EnableCustomFonts — fully rewritten to load .ttf fonts natively
- Multi-connection clientinfo support
- Cancel-to-exit on the service select screen
- Allow65kHairs with full CustomJobs compatibility
- …and plenty more improvements across the board

**Running a newer client?** [WARP2026](https://github.com/zVictorHG/WARP2026-Project) by zVictorHG targets the **2026-01-07 Ragexe** ([rAthena thread](https://rathena.org/board/topic/149414-2026-01-07-ragexe-clientinfo-warp/)). Some patches — like CustomJobs — will be ported over there as time allows.

Thanks to everyone who's tested, reported issues, and helped shape WARP0716. Your bug reports and feedback are what keep this project moving.

---

WARP patches for the 2025-07-16 client build. This build of WARP **only accepts the 2025-07-16 client EXE** — it will reject any other version.

20+ patches fixed, dead/incompatible patches removed, and all patch descriptions rewritten for the 07-16 client. If you find something off, please [open an issue](https://github.com/CrazyBebop/WARP0716/issues).

## Setup

1. Launch `win32/WARP.exe`
2. Load your unpacked exe
3. Select your patches and apply

## Recommended Patches

Click **"Recommended"** in the WARP GUI to select all recommended patches at once. A YAML profile is also included at `profiles/community_recommended.yml` for reference.

## What's New

### ⚠️ New Client EXE Required (Mar 30, 2026) ⚠️

All features below require the updated base EXE. **Download it here:**

[2025-07-16_Ragexe_175220998_clientinfo.zip](https://mirror2.romirrors.com/downloads/2025-07-16_Ragexe_175220998_clientinfo.zip)

**Character Select X Button Fix** — Fixed a bug where pressing the X button on the character select screen would show a "Are you sure you want to quit?" dialog instead of returning to the login screen. The previous cancel-exit patch was too broad and affected shared event guards. Now uses a targeted hook that only activates on the server selection screen.

**Cancel-Exit on Service Select** — The server select screen is now fully functional. Previously the cancel button did nothing — now it shows a "Are you sure you want to quit?" dialog and exits the client. The cancel button also automatically changes to say "exit" when on this screen. No extra files needed — the exit button graphics already exist in the GRF.

**Multi-Connection clientinfo.xml** — Servers with multiple entries in `clientinfo.xml` now work correctly. Previously all connections went to the first entry's IP regardless of which server the player selected. Now each server entry's address and port are stored separately, and the client connects to the right one based on the player's selection. Works with any standard `clientinfo.xml` layout — no special formatting needed.

Combined with the cancel-exit fix above, you can now list multiple servers and players will see the server select screen, pick their server, and connect to the correct one.

See [CHANGELOG.md](CHANGELOG.md) for full details on every patch and recent updates.

**Custom Jobs Guide:** [HTML](docs/CustomJobs/CUSTOM_JOBS_GUIDE.html) | [Online](https://legacygamers.net/docs/public/customjobs-reforged/)

### Known Conflict
**NoPassEncr** requires **UseOldLogin**. Do not enable both **UseSSOLogin** and **NoPassEncr** — the WARP GUI handles this automatically, but YAML profiles need manual care.

## Downloads

You need these to set up a working client:

1. **Client + Data GRF:** [Client+Data.grf](https://drive.google.com/file/d/1ugolNYp6vQE0Hzmwuj359LbgcwraiZgu/view?usp=drive_link) (December 4th, 2025) — Provided by Skylove
2. **Translation Project:** [llchrisll/ROenglishRE](https://github.com/llchrisll/ROenglishRE/) — Use the ClientGenerator, last option **[24] 2025-01-22**
3. **Client EXE:** [2025-07-16_Ragexe_175220998_clientinfo.zip](https://mirror2.romirrors.com/downloads/2025-07-16_Ragexe_175220998_clientinfo.zip) — Unpacked EXE, ready for WARP patching
4. **WARP** — Apply **Recommended** or use `profiles/community_recommended.yml` + your own patches

Then create a `data/` folder or GRF with your server's custom content (JobInfo Lua files, job sprites, Prontera map files, etc.) and add it to `DATA.INI`. Enable the **DataFolderFirst** patch if using loose files in `data/`, or pack into a GRF.

**Note:** The Prontera map files (`prontera.gat`, `prontera.gnd`, `prontera.rsw`) are **required** regardless of setup. They can be extracted from the GRF in step 1, or use your own if you already have them.

## Issues & Suggestions

Found a bug or have a suggestion? Post it in the [Issues](https://github.com/CrazyBebop/WARP0716/issues) section or join the [Discord](https://discord.com/invite/7CpRVcmjeB).

## Donate

It is never required, but if you feel the need to contribute to the project financially, you can do so by clicking the button below.

<a href="https://www.buymeacoffee.com/crazybebop"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" height="60" width="217" alt="Buy Me A Coffee"></a>

**PayPal:** <a href="https://www.paypal.com/donate/?hosted_button_id=WW9FD6SLEZ5BN"><img src="https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif" alt="Donate via PayPal"></a>

Special thanks to everyone who has donated — your support keeps this project going.

## Credits

Built on [WARP](https://github.com/Neo-Mind/WARP) by Neo-Mind and [Warp2025](https://github.com/hiphop9/Warp2025) by hiphop9.
