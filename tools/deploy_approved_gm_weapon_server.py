"""Activate the explicitly approved Admin-99 weapon-slot candidate safely.

Fixed paths and content hashes deliberately prevent reuse for arbitrary servers.
The only shutdown event is CTRL_C on a verified isolated map-server console.
There is no force-termination path. Run with an elevated Windows Python when
the map server is elevated. Progress is persisted even after console detachment.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Outputs/gm_all_weapons_20260905"
SERVER = Path(r"D:\Programs\Games\Ragnarok\01_github\BanquetOfHeroes")
TARGET = SERVER / "map-server.exe"
CANDIDATE = OUT / "map-server-gm-all-weapons.exe"
EXPECTED_OLD = "2ca1a116b6f913fc67da1ed474ef4cdefdfc9d9c17497d285f600e67636cf622"
EXPECTED_NEW = "21d80fc5186130ec1b65efc8cc37e347c8eb8f8dbfb161e177994224c74d479e"
EXPECTED_SOURCE = "eb9fc3b8a0cc8bc3efbd3dc2290b713fcde4c18103f66465a0bc8b042b0d4852"
REPORT = OUT / "deployment.json"
K = C.WinDLL("kernel32", use_last_error=True)


class ProcessEntry(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD),
                ("th32ProcessID", W.DWORD), ("th32DefaultHeapID", C.c_size_t),
                ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD),
                ("th32ParentProcessID", W.DWORD), ("pcPriClassBase", W.LONG),
                ("dwFlags", W.DWORD), ("szExeFile", W.WCHAR * 260)]


for name, args, result in [
    ("CreateToolhelp32Snapshot", [W.DWORD, W.DWORD], W.HANDLE),
    ("Process32FirstW", [W.HANDLE, C.POINTER(ProcessEntry)], W.BOOL),
    ("Process32NextW", [W.HANDLE, C.POINTER(ProcessEntry)], W.BOOL),
    ("OpenProcess", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
    ("QueryFullProcessImageNameW", [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL),
    ("CloseHandle", [W.HANDLE], W.BOOL),
    ("FreeConsole", [], W.BOOL),
    ("AttachConsole", [W.DWORD], W.BOOL),
    ("SetConsoleCtrlHandler", [C.c_void_p, W.BOOL], W.BOOL),
    ("GetConsoleProcessList", [C.POINTER(W.DWORD), W.DWORD], W.DWORD),
    ("GenerateConsoleCtrlEvent", [W.DWORD, W.DWORD], W.BOOL),
    ("WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD),
    ("GetExitCodeProcess", [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
]:
    f = getattr(K, name)
    f.argtypes = args
    f.restype = result


def check(ok, what):
    if not ok:
        raise OSError(C.get_last_error(), what)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def processes():
    h = K.CreateToolhelp32Snapshot(2, 0)
    check(h != C.c_void_p(-1).value, "Process snapshot")
    found = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = C.sizeof(entry)
        ok = K.Process32FirstW(h, C.byref(entry))
        while ok:
            found[entry.th32ProcessID] = {
                "pid": entry.th32ProcessID,
                "parent_pid": entry.th32ParentProcessID,
                "name": entry.szExeFile,
            }
            ok = K.Process32NextW(h, C.byref(entry))
    finally:
        K.CloseHandle(h)
    return found


def image_path(pid):
    h = K.OpenProcess(0x1000, False, pid)
    check(h, "Open process identity")
    try:
        buf = C.create_unicode_buffer(32768)
        length = W.DWORD(len(buf))
        check(K.QueryFullProcessImageNameW(h, 0, buf, C.byref(length)), "Process image path")
        return Path(buf.value)
    finally:
        K.CloseHandle(h)


state = {"authorization": "User explicitly approved patch deployment and map-server restart, then requested continuation.",
         "started_utc": datetime.now(timezone.utc).isoformat(),
         "scope": "Admin group 99 equipment override; approved pc.cpp guards and map-server executable only",
         "target": str(TARGET), "events": [], "completed": False}


def record(stage, **details):
    state["stage"] = stage
    state.update(details)
    state["events"].append({"stage": stage, "utc": datetime.now(timezone.utc).isoformat()})
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(REPORT)


def main():
    assert digest(CANDIDATE) == EXPECTED_NEW, "Candidate hash changed"
    assert digest(SERVER / "src/map/pc.cpp") == EXPECTED_SOURCE, "Approved source not installed"
    old_hash = digest(TARGET)
    assert old_hash in (EXPECTED_OLD, EXPECTED_NEW), "Unexpected installed executable; no overwrite"
    group_config = (SERVER / "conf/import/groups.yml").read_text(encoding="utf-8-sig")
    assert "- Id: 99" in group_config and "all_equipment: true" in group_config
    snapshot = processes()
    matching = [p for p in snapshot.values()
                if p["name"].lower() == "map-server.exe" and image_path(p["pid"]) == TARGET]
    assert len(matching) == 1, "Expected exactly one map server at the approved path"
    old = matching[0]
    peers = {pid: p for pid, p in snapshot.items()
             if p["name"].lower() in ("login-server.exe", "char-server.exe")}
    record("preflight", before_sha256=old_hash, candidate_sha256=EXPECTED_NEW,
           source_sha256=EXPECTED_SOURCE, old_process=old, peer_processes=list(peers.values()))
    if old_hash == EXPECTED_NEW:
        record("already_deployed", completed=True, new_pid=old["pid"], after_sha256=old_hash)
        return

    before_backup = OUT / "deployment-before-map-server.exe"
    if before_backup.exists():
        assert digest(before_backup) == EXPECTED_OLD, "Existing backup changed"
    else:
        shutil.copy2(TARGET, before_backup)
    process_handle = K.OpenProcess(0x101000, False, old["pid"])
    check(process_handle, "Open map server for identity and shutdown observation")
    try:
        K.FreeConsole()
        check(K.AttachConsole(old["pid"]), "Attach isolated map-server console")
        check(K.SetConsoleCtrlHandler(None, True), "Ignore Ctrl-C in helper")
        ids = (W.DWORD * 128)()
        n = K.GetConsoleProcessList(ids, len(ids))
        assert 0 < n <= len(ids), "Console inventory failed or truncated"
        members = set(ids[:n])
        assert old["pid"] in members and os.getpid() in members, "Map console identity mismatch"
        assert not members.intersection(peers), "Login/char server shares map console; no signal sent"
        others = members - {old["pid"], os.getpid()}
        assert all(pid == old["parent_pid"] and snapshot.get(pid, {}).get("name", "").lower() == "cmd.exe"
                   for pid in others), "Unexpected process shares map console; no signal sent"
        record("isolated_console_verified", console_members=[snapshot.get(pid, {"pid": pid, "name": "deployment helper"})
                                                              for pid in sorted(members)])
        check(K.GenerateConsoleCtrlEvent(0, 0), "Graceful map-server Ctrl-C")
        record("graceful_shutdown_requested")
        waited = K.WaitForSingleObject(process_handle, 45000)
        assert waited == 0, "Graceful shutdown did not finish within 45 seconds; no force termination or replacement"
        code = W.DWORD()
        check(K.GetExitCodeProcess(process_handle, C.byref(code)), "Read map-server exit code")
        assert code.value == 0, f"Nonzero graceful exit {code.value}; no replacement"
        record("graceful_shutdown_finished", old_exit_code=code.value)
    finally:
        K.FreeConsole()
        K.CloseHandle(process_handle)

    # Recheck all content immediately before the approved replacement.
    assert digest(TARGET) == EXPECTED_OLD and digest(CANDIDATE) == EXPECTED_NEW
    assert digest(SERVER / "src/map/pc.cpp") == EXPECTED_SOURCE
    alive = processes()
    assert all(pid in alive for pid in peers), "Login/char process disappeared; investigate before restart"
    shutil.copy2(CANDIDATE, TARGET)
    assert digest(TARGET) == EXPECTED_NEW
    record("binary_installed", after_sha256=EXPECTED_NEW)
    startup_log = OUT / "deployed-map-startup.log"
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    with startup_log.open("wb") as log:
        new = subprocess.Popen([str(TARGET)], cwd=SERVER, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NEW_CONSOLE,
                               startupinfo=si)
    record("map_server_started", new_pid=new.pid, startup_log=str(startup_log), hidden_window=True)
    # Readiness checks are performed by the caller so the helper does not keep
    # an elevated foreground process or conflate process creation with startup.
    time.sleep(2)
    assert new.poll() is None, "New map server exited during initial startup"
    record("awaiting_readiness_verification", new_pid=new.pid, after_sha256=digest(TARGET))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        record("failed", error=f"{type(exc).__name__}: {exc}")
        sys.exit(1)
