// NPC name overlay for 2025-07-16 Ragexe.
//
// The overlay reuses the client's native actor-name balloon setup and mirrors
// its above-head placement when /font is enabled. /shownpcname only controls
// whether the additional NPC balloons exist.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "boh_features.h"

static constexpr DWORD kBase = 0x00400000;
static constexpr DWORD kHook = 0x00C77820;
static constexpr DWORD kFact = 0x00C714B0;
static constexpr DWORD kSetup = 0x00C6D1D0;
static constexpr DWORD kGetAct = 0x00A69EB0;
static constexpr DWORD kGetAct2 = 0x00A69FA0;
static constexpr DWORD kDestroy = 0x00A447D0;
static constexpr DWORD kGetOption = 0x0068EA70;
static constexpr DWORD kSetOption = 0x0068FD50;
static constexpr DWORD kViewport = 0x012515F8;
static constexpr DWORD kUiMgr = 0x0131F4E8;
static constexpr DWORD kVtab = 0x010904B8;
static constexpr DWORD kStaleNpcMs = 10000;
static constexpr DWORD kNameAboveHeadOption = 0x5C;
static constexpr DWORD kShowNpcNameOption = 10001;

enum : DWORD
{
	O_WM = 0x0CC,
	O_BA = 0x2AC,
	O_HG = 0x2D8,
};

using FnOrig = void (__thiscall*)(void*);
using FnFact = void (__stdcall*)(void**);
using FnSetup = void (__thiscall*)(void*, void*);
using FnGetAct = void* (__thiscall*)(void*, DWORD);
using FnDestroy = void (__thiscall*)(void*, void*);
using FnGetOption = bool (__cdecl*)(DWORD);
using FnSetOption = bool (__cdecl*)(DWORD, int);
using FnSetPosition = void (__thiscall*)(void*, int, int);

static DWORD g_base;
static BYTE g_stolen[5];
static void* g_trampoline;
static volatile LONG g_hookInstalled;
static volatile LONG g_enabled;
static volatile bool g_down;
static HANDLE g_thread;

// Value is the last EXTN refresh tick. Names are rendered from the actor's
// interned 0x0ADF string, so retaining another copy here is unnecessary.
static std::unordered_map<uint32_t, DWORD> g_knownNpcs;
static std::vector<std::pair<uint32_t, DWORD>> g_knownSnapshot;
static std::mutex g_knownMutex;
static volatile LONG g_knownDirty = 1;

struct NpcBalloon
{
	void* ptr;
};

static std::unordered_map<uint32_t, NpcBalloon> g_balloons;
static std::unordered_map<uint32_t, DWORD> g_missingSince;

static DWORD Rebase(DWORD address)
{
	return g_base + (address - kBase);
}

static bool PatchJump(
	DWORD address,
	void* target,
	BYTE* stolen,
	SIZE_T stolenLength,
	void** trampoline)
{
	BYTE* source = reinterpret_cast<BYTE*>(Rebase(address));
	CopyMemory(stolen, source, stolenLength);

	BYTE* gateway = reinterpret_cast<BYTE*>(VirtualAlloc(
		nullptr,
		stolenLength + 5,
		MEM_COMMIT | MEM_RESERVE,
		PAGE_EXECUTE_READWRITE));
	if (!gateway)
		return false;

	CopyMemory(gateway, stolen, stolenLength);
	gateway[stolenLength] = 0xE9;
	*reinterpret_cast<int32_t*>(gateway + stolenLength + 1) =
		static_cast<int32_t>(
			(source + stolenLength) - (gateway + stolenLength + 5));

	DWORD oldProtect = 0;
	if (!VirtualProtect(
			source,
			stolenLength,
			PAGE_EXECUTE_READWRITE,
			&oldProtect))
	{
		VirtualFree(gateway, 0, MEM_RELEASE);
		return false;
	}

	source[0] = 0xE9;
	*reinterpret_cast<int32_t*>(source + 1) =
		static_cast<int32_t>(reinterpret_cast<BYTE*>(target) - (source + 5));
	for (SIZE_T i = 5; i < stolenLength; ++i)
		source[i] = 0x90;

	FlushInstructionCache(GetCurrentProcess(), source, stolenLength);
	VirtualProtect(source, stolenLength, oldProtect, &oldProtect);
	*trampoline = gateway;
	return true;
}

static void RestorePatchedBytes(DWORD address, BYTE* stolen, SIZE_T stolenLength)
{
	if (!g_base || !stolen || stolenLength < 5)
		return;

	BYTE* source = reinterpret_cast<BYTE*>(Rebase(address));
	DWORD oldProtect = 0;
	if (!VirtualProtect(
			source,
			stolenLength,
			PAGE_EXECUTE_READWRITE,
			&oldProtect))
	{
		return;
	}

	CopyMemory(source, stolen, stolenLength);
	FlushInstructionCache(GetCurrentProcess(), source, stolenLength);
	VirtualProtect(source, stolenLength, oldProtect, &oldProtect);
}

static void DestroyAllBalloons(FnDestroy destroy, void* uiManager)
{
	for (const auto& entry : g_balloons)
	{
		if (entry.second.ptr)
			destroy(uiManager, entry.second.ptr);
	}
	g_balloons.clear();
	g_missingSince.clear();
}

// type: 0=PC, 1=MOB, 2=NPC, 3=portal NPC.
extern "C" __declspec(dllexport) void NpcOverlay_OnExtName(
	uint32_t gid,
	uint8_t type,
	const char* name)
{
	if (g_down || type != 2 || !name || !name[0])
		return;

	std::lock_guard<std::mutex> lock(g_knownMutex);
	const DWORD now = GetTickCount();
	g_knownNpcs[gid] = now;
	if (g_knownNpcs.size() > 5000)
	{
		g_knownNpcs.clear();
		g_knownNpcs[gid] = now;
	}
	InterlockedExchange(&g_knownDirty, 1);
}

extern "C" __declspec(dllexport) void ToggleNpcNameOverlay()
{
	const LONG current = InterlockedCompareExchange(&g_enabled, 0, 0);
	const LONG enabled = current ? 0 : 1;
	InterlockedExchange(&g_enabled, enabled);

	if (g_base)
	{
		auto setOption = reinterpret_cast<FnSetOption>(Rebase(kSetOption));
		setOption(kShowNpcNameOption, enabled != 0);
	}
}

// Called by the WARP Game Settings bridge. Only the custom NPC option is
// written here. Native options such as /font must remain owned by the client:
// pre-writing them prevents the client's registered TALKTYPE handler from
// observing a state change and running its normal update path.
extern "C" __declspec(dllexport) void SetNpcNameOverlayOption(
	uint32_t optionId,
	int enabled)
{
	const LONG value = enabled ? 1 : 0;
	if (optionId == kShowNpcNameOption)
	{
		InterlockedExchange(&g_enabled, value);
		if (g_base)
		{
			auto setOption =
				reinterpret_cast<FnSetOption>(Rebase(kSetOption));
			setOption(optionId, value != 0);
		}
	}
}

extern "C" void __fastcall BalloonHook(void* gameMode)
{
	auto original = reinterpret_cast<FnOrig>(g_trampoline);
	if (!original)
		return;

	if (g_down)
	{
		original(gameMode);
		return;
	}

	BYTE* gm = reinterpret_cast<BYTE*>(gameMode);
	if (*reinterpret_cast<DWORD*>(gm) != Rebase(kVtab))
	{
		original(gameMode);
		return;
	}

	const DWORD savedHoverGid = *reinterpret_cast<DWORD*>(gm + O_HG);
	original(gameMode);

	auto destroy = reinterpret_cast<FnDestroy>(Rebase(kDestroy));
	void* uiManager = reinterpret_cast<void*>(Rebase(kUiMgr));
	if (InterlockedCompareExchange(&g_enabled, 0, 0) == 0)
	{
		if (!g_balloons.empty())
			DestroyAllBalloons(destroy, uiManager);
		return;
	}

	const DWORD worldManager = *reinterpret_cast<DWORD*>(gm + O_WM);
	if (!worldManager)
		return;

	const bool refreshKnown =
		InterlockedExchange(&g_knownDirty, 0) != 0;
	if (refreshKnown)
	{
		std::lock_guard<std::mutex> lock(g_knownMutex);
		g_knownSnapshot.clear();
		g_knownSnapshot.reserve(g_knownNpcs.size());
		for (const auto& entry : g_knownNpcs)
			g_knownSnapshot.push_back(entry);
	}

	if (refreshKnown)
	{
		std::unordered_set<uint32_t> knownIds;
		knownIds.reserve(g_knownSnapshot.size());
		for (const auto& entry : g_knownSnapshot)
			knownIds.insert(entry.first);

		for (auto it = g_balloons.begin(); it != g_balloons.end();)
		{
			if (knownIds.find(it->first) != knownIds.end())
			{
				++it;
				continue;
			}
			if (it->second.ptr)
				destroy(uiManager, it->second.ptr);
			g_missingSince.erase(it->first);
			it = g_balloons.erase(it);
		}
	}

	auto factory = reinterpret_cast<FnFact>(Rebase(kFact));
	auto setup = reinterpret_cast<FnSetup>(Rebase(kSetup));
	auto getActor = reinterpret_cast<FnGetAct>(Rebase(kGetAct));
	auto getActorFallback = reinterpret_cast<FnGetAct>(Rebase(kGetAct2));
	auto getOption =
		reinterpret_cast<FnGetOption>(Rebase(kGetOption));
	void** mainSlot = reinterpret_cast<void**>(gm + O_BA);
	void* savedMain = *mainSlot;
	const bool nameAboveHead = getOption(kNameAboveHeadOption);
	BYTE* viewport = *reinterpret_cast<BYTE**>(Rebase(kViewport));
	const int viewportHeight = viewport
		? *reinterpret_cast<int*>(viewport + 0x2C)
		: 0;
	const DWORD now = GetTickCount();
	std::vector<std::pair<uint32_t, DWORD>> stale;

	for (const auto& entry : g_knownSnapshot)
	{
		const uint32_t gid = entry.first;
		void* actor = getActor(
			reinterpret_cast<void*>(worldManager),
			gid);
		if (!actor)
			actor = getActorFallback(
				reinterpret_cast<void*>(worldManager),
				gid);

		auto balloon = g_balloons.find(gid);
		if (!actor)
		{
			if (balloon != g_balloons.end())
			{
				if (balloon->second.ptr)
					destroy(uiManager, balloon->second.ptr);
				g_balloons.erase(balloon);
			}

			auto missing = g_missingSince.find(gid);
			if (missing == g_missingSince.end())
				g_missingSince[gid] = now;
			else if (now - missing->second >= kStaleNpcMs)
				stale.push_back(entry);
			continue;
		}

		g_missingSince.erase(gid);
		void* internedName = *reinterpret_cast<void**>(
			reinterpret_cast<BYTE*>(actor) + 0x110);
		if (!internedName)
			continue;

		if (balloon == g_balloons.end() || !balloon->second.ptr)
		{
			void* slot = nullptr;
			factory(&slot);
			if (!slot)
				continue;
			g_balloons[gid] = NpcBalloon{slot};
			balloon = g_balloons.find(gid);
		}

		*mainSlot = balloon->second.ptr;
		setup(gameMode, actor);

		// Hover-style NPC balloons normally use the below-character branch in
		// UpdateBalloonPos because NPC actors have no +0xA8 name anchor. Match
		// the client's above-head branch when /font (option 0x5C) is enabled.
		if (nameAboveHead && viewportHeight > 0)
		{
			BYTE* balloonObject =
				reinterpret_cast<BYTE*>(balloon->second.ptr);
			const float actorScale = *reinterpret_cast<float*>(
				reinterpret_cast<BYTE*>(actor) + 0x5C);
			if (actorScale > 0.0f && actorScale < 10.0f)
			{
				const int belowBase = viewportHeight / 24;
				const int aboveBase = -(viewportHeight * 5) / 24;
				const int belowOffset =
					static_cast<int>(belowBase * actorScale);
				const int aboveOffset =
					static_cast<int>(aboveBase * actorScale);
				const int x = *reinterpret_cast<int*>(
					balloonObject + 0x1C);
				const int y = *reinterpret_cast<int*>(
					balloonObject + 0x20);
				void** vtable = *reinterpret_cast<void***>(
					balloonObject);
				auto setPosition =
					reinterpret_cast<FnSetPosition>(vtable[4]);
				setPosition(
					balloonObject,
					x,
					y + aboveOffset - belowOffset);
			}
		}
		*mainSlot = savedMain;
	}

	*mainSlot = savedMain;
	*reinterpret_cast<DWORD*>(gm + O_HG) = savedHoverGid;

	if (!stale.empty())
	{
		std::lock_guard<std::mutex> lock(g_knownMutex);
		bool erased = false;
		for (const auto& entry : stale)
		{
			auto current = g_knownNpcs.find(entry.first);
			if (current != g_knownNpcs.end() &&
			    current->second == entry.second)
			{
				g_knownNpcs.erase(current);
				erased = true;
			}
			g_missingSince.erase(entry.first);
		}
		if (erased)
			InterlockedExchange(&g_knownDirty, 1);
	}
}

static DWORD WINAPI MainThread(LPVOID)
{
	Sleep(200);
	g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));
	if (PatchJump(
			kHook,
			reinterpret_cast<void*>(&BalloonHook),
			g_stolen,
			sizeof(g_stolen),
			&g_trampoline))
	{
		InterlockedExchange(&g_hookInstalled, 1);
	}
	return 0;
}

BOOL APIENTRY NpcNameOverlayDllMain(HMODULE module, DWORD reason, LPVOID)
{
	switch (reason)
	{
	case DLL_PROCESS_ATTACH:
		if (!BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
			break;
		DisableThreadLibraryCalls(module);
		g_down = false;
		g_hookInstalled = 0;
		g_enabled = 0;
		g_thread = CreateThread(nullptr, 0, MainThread, nullptr, 0, nullptr);
		break;

	case DLL_PROCESS_DETACH:
		g_down = true;
		if (g_thread)
		{
			WaitForSingleObject(g_thread, 3000);
			CloseHandle(g_thread);
			g_thread = nullptr;
		}
		if (InterlockedExchange(&g_hookInstalled, 0) != 0)
			RestorePatchedBytes(kHook, g_stolen, sizeof(g_stolen));
		break;
	}
	return TRUE;
}

extern "C" __declspec(dllexport) void NpcNameOverlayInit()
{
}
