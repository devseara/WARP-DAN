// NPC name overlay for 2025-07-16 Ragexe.
//
// The overlay reuses the client's native actor-name balloon setup and mirrors
// its above-head placement when /font is enabled. /shownpcname only controls
// whether the additional NPC balloons exist.
//
// Gepard-safe model: WARP patches the EXE on disk so the known frame caller
// invokes NpcNameOverlayFrame after the original game function returns. This
// DLL never patches EXE code, IAT entries, vtables, or system DLL exports at
// runtime.

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
static constexpr uint16_t kExtNamePacketId = 0x0BB7;
static constexpr uint16_t kExtNamePacketLenLegacyV1 = 233;
static constexpr uint16_t kExtNamePacketLenLegacy = 237;
static constexpr uint16_t kExtNamePacketLenV1 = 773;
static constexpr uint16_t kExtNamePacketLen = 777;
static constexpr uint16_t kExtNamePacketTypeOffsetLegacy = 232;
static constexpr uint16_t kExtNamePacketTypeOffset = 772;
static constexpr uint16_t kExtNameShortFieldLen = 24;
static constexpr uint16_t kExtNameLegacyTextFieldLen = 31;
static constexpr uint16_t kExtNameTextFieldLen = 128;
static constexpr uint32_t kExtNameMagic = 0x4558544E; // 'EXTN'
static constexpr uint32_t kExtNameRingMagic = 0x474E4952; // 'RING'
static constexpr uint32_t kExtNameRingCapacity = 128;
static constexpr uint32_t kExtNameRingHeaderSize = 16;
static constexpr uint32_t kExtNameRingSlotSize = 1024;
static constexpr uint32_t kExtNameRingPayloadSize =
	kExtNameRingSlotSize - sizeof(uint32_t);
static constexpr DWORD kPacketDispatchTable = 0x00CAA2E0;
static constexpr uint16_t kPacketDispatchFirstId = 0x0073;
static constexpr DWORD kClippedRetryMs = 250;
// Native balloon setup also updates screen position. Throttling it during
// movement makes names visibly jitter, so throttling is opt-in for profiling.
static constexpr DWORD kDefaultFrameIntervalMs = 0;
static constexpr DWORD kMaxFrameIntervalMs = 250;

enum : DWORD
{
	O_WM = 0x0CC,
	O_BA = 0x2AC,
	O_HG = 0x2D8,
};

using FnFact = void (__stdcall*)(void**);
using FnSetup = void (__thiscall*)(void*, void*);
using FnGetAct = void* (__thiscall*)(void*, DWORD);
using FnDestroy = void (__thiscall*)(void*, void*);
using FnGetOption = bool (__cdecl*)(DWORD);
using FnSetOption = bool (__cdecl*)(DWORD, int);
using FnSetPosition = void (__thiscall*)(void*, int, int);

static DWORD g_base;
static volatile LONG g_enabled;
static volatile bool g_down;
static BYTE* g_extnBlock;
static bool g_extnProbeComplete;
static DWORD g_extnNextProbeTick;
static uint32_t g_extnReadSequence;
static bool g_optionSynced;

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
static std::unordered_map<uint32_t, DWORD> g_clippedUntil;
static void* g_lastGameMode;
static DWORD g_lastWorldManager;
static DWORD g_suppressUntil;
static volatile LONG g_renderIntervalLoaded;
static DWORD g_renderIntervalMs = kDefaultFrameIntervalMs;
static DWORD g_nextRenderTick;

static bool TickBefore(DWORD now, DWORD future);

static DWORD Rebase(DWORD address)
{
	return g_base + (address - kBase);
}

static bool EnsureBase()
{
	if (!g_base)
		g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));
	return g_base != 0;
}

static bool SafeReadDword(const void* ptr, DWORD* out)
{
	if (!ptr || !out)
		return false;

	__try
	{
		*out = *reinterpret_cast<const DWORD*>(ptr);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeReadPtr(const void* ptr, void** out)
{
	if (!ptr || !out)
		return false;

	__try
	{
		*out = *reinterpret_cast<void* const*>(ptr);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeReadFloat(const void* ptr, float* out)
{
	if (!ptr || !out)
		return false;

	__try
	{
		*out = *reinterpret_cast<const float*>(ptr);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeWriteDword(void* ptr, DWORD value)
{
	if (!ptr)
		return false;

	__try
	{
		*reinterpret_cast<DWORD*>(ptr) = value;
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeWritePtr(void* ptr, void* value)
{
	if (!ptr)
		return false;

	__try
	{
		*reinterpret_cast<void**>(ptr) = value;
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeGetOption(FnGetOption getOption, DWORD option, bool* out)
{
	if (!getOption || !out)
		return false;

	__try
	{
		*out = getOption(option);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeSetOption(FnSetOption setOption, DWORD option, int value)
{
	if (!setOption)
		return false;

	__try
	{
		return setOption(option, value) != false;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeGetActor(
	FnGetAct getActor,
	void* worldManager,
	DWORD gid,
	void** out)
{
	if (!getActor || !worldManager || !out)
		return false;

	__try
	{
		*out = getActor(worldManager, gid);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		*out = nullptr;
		return false;
	}
}

static bool SafeFactory(FnFact factory, void** slot)
{
	if (!factory || !slot)
		return false;

	__try
	{
		factory(slot);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeDestroy(FnDestroy destroy, void* uiManager, void* balloon)
{
	if (!destroy || !uiManager || !balloon)
		return false;

	__try
	{
		destroy(uiManager, balloon);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeSetup(FnSetup setup, void* gameMode, void* actor)
{
	if (!setup || !gameMode || !actor)
		return false;

	__try
	{
		setup(gameMode, actor);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SafeSetPosition(
	FnSetPosition setPosition,
	void* balloon,
	int x,
	int y)
{
	if (!setPosition || !balloon)
		return false;

	__try
	{
		setPosition(balloon, x, y);
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool SyncEnabledFromClientOption()
{
	if (g_optionSynced || !EnsureBase())
		return g_optionSynced;

	__try
	{
		auto getOption = reinterpret_cast<FnGetOption>(Rebase(kGetOption));
		auto setOption = reinterpret_cast<FnSetOption>(Rebase(kSetOption));
		bool enabled = false;
		if (!SafeGetOption(getOption, kShowNpcNameOption, &enabled))
			return false;
		if (!SafeSetOption(setOption, kShowNpcNameOption, enabled ? 1 : 0))
			return false;

		InterlockedExchange(&g_enabled, enabled ? 1 : 0);
		g_nextRenderTick = 0;
		g_optionSynced = true;
		return true;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return false;
	}
}

static bool IsValidExtnSharedBlock(BYTE* candidate)
{
	if (!candidate)
		return false;

	uint32_t magic = *reinterpret_cast<uint32_t*>(candidate);
	if (magic != kExtNameMagic)
		return false;

	uint32_t readyOrSequence =
		*reinterpret_cast<uint32_t*>(candidate + 4);
	uint32_t lengthOrFormat =
		*reinterpret_cast<uint32_t*>(candidate + 8);
	uint32_t capacity =
		*reinterpret_cast<uint32_t*>(candidate + 12);
	if (lengthOrFormat == kExtNameRingMagic &&
		capacity == kExtNameRingCapacity)
		return true;

	return (readyOrSequence == 0 || readyOrSequence == 1) &&
		lengthOrFormat <= 4092;
}

static BYTE* NormalizeExeVa(BYTE* exe, uintptr_t value)
{
	const uintptr_t exeBase = reinterpret_cast<uintptr_t>(exe);
	const uintptr_t scanEnd = exeBase + 64 * 1024 * 1024;
	if (value >= exeBase && value < scanEnd)
		return reinterpret_cast<BYTE*>(value);
	if (value >= kBase && value < kBase + 64 * 1024 * 1024)
		return exe + (value - kBase);
	return nullptr;
}

static BYTE* FindActiveExtnDispatcherBlock()
{
	HMODULE exeModule = GetModuleHandleW(nullptr);
	if (!exeModule)
		return nullptr;

	BYTE* exe = reinterpret_cast<BYTE*>(exeModule);
	__try
	{
		const uintptr_t entryOffset =
			kPacketDispatchTable - kBase +
			(kExtNamePacketId - kPacketDispatchFirstId) * sizeof(uint32_t);
		DWORD handlerVa = *reinterpret_cast<DWORD*>(exe + entryOffset);
		BYTE* handler = NormalizeExeVa(exe, handlerVa);
		if (!handler)
			return nullptr;

		if (handler[0] != 0x9C || handler[1] != 0x60 ||
			handler[2] != 0xBE)
			return nullptr;
		if (*reinterpret_cast<uint16_t*>(handler + 10) != kExtNamePacketId)
			return nullptr;

		DWORD blockVa = *reinterpret_cast<DWORD*>(handler + 35);
		BYTE* block = NormalizeExeVa(exe, blockVa);
		return IsValidExtnSharedBlock(block) ? block : nullptr;
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
		return nullptr;
	}
}

static BYTE* FindExtnSharedBlock()
{
	BYTE* active = FindActiveExtnDispatcherBlock();
	if (active)
		return active;

	HMODULE exe = GetModuleHandleW(nullptr);
	if (!exe)
		return nullptr;

	BYTE* start = reinterpret_cast<BYTE*>(exe);
	const size_t scanSize = 64 * 1024 * 1024;
	__try
	{
		for (size_t offset = 0; offset < scanSize - 16; offset += 4)
		{
			BYTE* candidate = start + offset;
			if (*reinterpret_cast<uint32_t*>(candidate) != kExtNameMagic)
				continue;

			if (IsValidExtnSharedBlock(candidate))
				return candidate;
		}
	}
	__except (EXCEPTION_EXECUTE_HANDLER)
	{
	}
	return nullptr;
}

static BYTE* ProbeExtnSharedBlock()
{
	if (g_extnBlock)
		return g_extnBlock;

	const DWORD now = GetTickCount();
	if (g_extnProbeComplete && g_extnNextProbeTick &&
		TickBefore(now, g_extnNextProbeTick))
		return nullptr;

	g_extnBlock = FindExtnSharedBlock();
	if (g_extnBlock)
	{
		g_extnProbeComplete = true;
		g_extnNextProbeTick = 0;
	}
	else
	{
		// Startup import order can make the dispatcher table look absent during
		// DLL attach. Retry misses instead of disabling EXTN-backed NPC names for
		// the lifetime of the process.
		g_extnProbeComplete = true;
		g_extnNextProbeTick = now + 500;
	}
	return g_extnBlock;
}

static void DestroyAllBalloons(FnDestroy destroy, void* uiManager)
{
	for (const auto& entry : g_balloons)
	{
		if (entry.second.ptr)
			SafeDestroy(destroy, uiManager, entry.second.ptr);
	}
	g_balloons.clear();
	g_missingSince.clear();
	g_clippedUntil.clear();
}

static void ClearKnownNpcs()
{
	std::lock_guard<std::mutex> lock(g_knownMutex);
	g_knownNpcs.clear();
	g_knownSnapshot.clear();
	InterlockedExchange(&g_knownDirty, 1);
}

static void ResetOverlayState(bool clearKnown)
{
	g_nextRenderTick = 0;

	if (EnsureBase())
	{
		auto destroy = reinterpret_cast<FnDestroy>(Rebase(kDestroy));
		void* uiManager = reinterpret_cast<void*>(Rebase(kUiMgr));
		DestroyAllBalloons(destroy, uiManager);
	}
	else
	{
		g_balloons.clear();
		g_missingSince.clear();
		g_clippedUntil.clear();
	}

	if (clearKnown)
		ClearKnownNpcs();
}

static bool TickBefore(DWORD now, DWORD future)
{
	return static_cast<LONG>(now - future) < 0;
}

static DWORD ReadNpcFrameIntervalMs()
{
	char value[32] = {};
	const DWORD length = GetEnvironmentVariableA(
		"BOH_NPC_NAME_FRAME_MS",
		value,
		sizeof(value));
	if (length == 0 || length >= sizeof(value))
		return kDefaultFrameIntervalMs;

	DWORD parsed = 0;
	for (DWORD i = 0; i < length; ++i)
	{
		if (value[i] < '0' || value[i] > '9')
			return kDefaultFrameIntervalMs;
		parsed = parsed * 10 + static_cast<DWORD>(value[i] - '0');
		if (parsed > kMaxFrameIntervalMs)
			return kMaxFrameIntervalMs;
	}
	return parsed;
}

static DWORD NpcFrameIntervalMs()
{
	if (InterlockedCompareExchange(&g_renderIntervalLoaded, 1, 0) == 0)
		g_renderIntervalMs = ReadNpcFrameIntervalMs();
	return g_renderIntervalMs;
}

static bool ShouldRenderNpcOverlayNow()
{
	const DWORD interval = NpcFrameIntervalMs();
	if (interval == 0)
		return true;

	const DWORD now = GetTickCount();
	if (g_nextRenderTick && TickBefore(now, g_nextRenderTick))
		return false;

	g_nextRenderTick = now + interval;
	return true;
}

static bool BeginNpcFrame(void* gameMode, DWORD* worldManagerOut)
{
	if (g_down || !gameMode || !worldManagerOut || !EnsureBase())
		return false;

	const DWORD now = GetTickCount();
	if (g_suppressUntil && TickBefore(now, g_suppressUntil))
		return false;
	g_suppressUntil = 0;

	BYTE* gm = reinterpret_cast<BYTE*>(gameMode);
	DWORD vtable = 0;
	if (!SafeReadDword(gm, &vtable) || vtable != Rebase(kVtab))
	{
		if (g_lastGameMode || g_lastWorldManager)
		{
			ResetOverlayState(true);
			g_lastGameMode = nullptr;
			g_lastWorldManager = 0;
		}
		return false;
	}

	DWORD worldManager = 0;
	if (!SafeReadDword(gm + O_WM, &worldManager) || !worldManager)
	{
		if (g_lastGameMode || g_lastWorldManager)
		{
			ResetOverlayState(true);
			g_lastGameMode = nullptr;
			g_lastWorldManager = 0;
		}
		return false;
	}

	if (g_lastGameMode != gameMode || g_lastWorldManager != worldManager)
	{
		ResetOverlayState(true);
		g_lastGameMode = gameMode;
		g_lastWorldManager = worldManager;
	}

	*worldManagerOut = worldManager;
	return true;
}

static bool IsBalloonViewportClamped(
	void* ptr,
	int viewportWidth,
	int viewportHeight)
{
	if (!ptr || viewportWidth <= 0 || viewportHeight <= 0)
		return false;

	BYTE* balloon = reinterpret_cast<BYTE*>(ptr);
	DWORD rawWidth = 0;
	DWORD rawHeight = 0;
	DWORD rawX = 0;
	DWORD rawY = 0;
	if (!SafeReadDword(balloon + 0x14, &rawWidth) ||
	    !SafeReadDword(balloon + 0x18, &rawHeight) ||
	    !SafeReadDword(balloon + 0x1C, &rawX) ||
	    !SafeReadDword(balloon + 0x20, &rawY))
		return true;

	const int width = static_cast<int>(rawWidth);
	const int height = static_cast<int>(rawHeight);
	const int x = static_cast<int>(rawX);
	const int y = static_cast<int>(rawY);
	if (width <= 0 || height <= 0 ||
	    width > viewportWidth + 512 ||
	    height > viewportHeight + 512)
		return false;

	const int minClamp = -3;
	const int maxX = viewportWidth - width + 3;
	const int maxY = viewportHeight - height + 3;
	return x <= minClamp || y <= minClamp || x >= maxX || y >= maxY;
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

static void ParseExtnNpcPacket(BYTE* data, uint32_t length)
{
	bool hasHeader = false;
	bool hasWideLayout = false;
	uint16_t packetLength = 0;
	uint32_t offset = 2;
	if (length >= kExtNamePacketLenLegacyV1)
	{
		packetLength = *reinterpret_cast<uint16_t*>(data + 2);
		uint32_t magic = *reinterpret_cast<uint32_t*>(data + 4);
		hasWideLayout =
			packetLength == kExtNamePacketLenV1 ||
			packetLength == kExtNamePacketLen;
		hasHeader =
			packetLength == length &&
			(hasWideLayout ||
			 packetLength == kExtNamePacketLenLegacyV1 ||
			 packetLength == kExtNamePacketLenLegacy) &&
			magic == kExtNameMagic;
	}

	if (hasHeader)
		offset = 8;
	else if (length < 226)
		return;

	if (*reinterpret_cast<uint16_t*>(data) != kExtNamePacketId)
		return;
	const uint16_t textLen =
		hasWideLayout ? kExtNameTextFieldLen : kExtNameLegacyTextFieldLen;
	if (length < offset + 4 + kExtNameShortFieldLen + textLen)
		return;

	uint32_t gid = *reinterpret_cast<uint32_t*>(data + offset);
	char* shortName = reinterpret_cast<char*>(data + offset + 4);
	char* extName =
		reinterpret_cast<char*>(data + offset + 4 + kExtNameShortFieldLen);
	shortName[kExtNameShortFieldLen - 1] = '\0';
	extName[textLen - 1] = '\0';

	uint8_t type = 0;
	if (hasHeader)
		type = *reinterpret_cast<uint8_t*>(
			data + (hasWideLayout ?
				kExtNamePacketTypeOffset :
				kExtNamePacketTypeOffsetLegacy));
	else if (length >= 227)
		type = *reinterpret_cast<uint8_t*>(data + 226);

	NpcOverlay_OnExtName(gid, type, extName[0] ? extName : shortName);
}

static void DrainExtnRing(BYTE* base)
{
	volatile uint32_t* writeSequence =
		reinterpret_cast<volatile uint32_t*>(base + 4);
	for (;;)
	{
		uint32_t published = *writeSequence;
		MemoryBarrier();
		uint32_t pending = published - g_extnReadSequence;
		if (pending == 0)
			break;
		if (pending > kExtNameRingCapacity)
			g_extnReadSequence = published - kExtNameRingCapacity;

		uint32_t slotIndex =
			g_extnReadSequence & (kExtNameRingCapacity - 1);
		BYTE* slot =
			base + kExtNameRingHeaderSize +
			slotIndex * kExtNameRingSlotSize;
		uint32_t length = *reinterpret_cast<volatile uint32_t*>(slot);
		MemoryBarrier();

		if (length > 0 && length <= kExtNameRingPayloadSize)
		{
			BYTE packet[kExtNameRingPayloadSize];
			CopyMemory(packet, slot + sizeof(uint32_t), length);
			ParseExtnNpcPacket(packet, length);
		}
		++g_extnReadSequence;
	}
}

static void PollExtnSharedBlock()
{
	BYTE* base = ProbeExtnSharedBlock();
	if (!base)
		return;

	uint32_t format = *reinterpret_cast<uint32_t*>(base + 8);
	uint32_t capacity = *reinterpret_cast<uint32_t*>(base + 12);
	if (format == kExtNameRingMagic &&
		capacity == kExtNameRingCapacity)
	{
		DrainExtnRing(base);
		return;
	}

	volatile uint32_t* ready =
		reinterpret_cast<volatile uint32_t*>(base + 4);
	if (*ready != 1)
		return;

	uint32_t length = *reinterpret_cast<uint32_t*>(base + 8);
	if (length > 0 && length <= 4092)
		ParseExtnNpcPacket(base + 12, length);
	*ready = 0;
}

extern "C" __declspec(dllexport) void ToggleNpcNameOverlay()
{
	if (!BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
		return;

	const LONG current = InterlockedCompareExchange(&g_enabled, 0, 0);
	const LONG enabled = current ? 0 : 1;
	InterlockedExchange(&g_enabled, enabled);
	g_nextRenderTick = 0;

	if (EnsureBase())
	{
		auto setOption = reinterpret_cast<FnSetOption>(Rebase(kSetOption));
		SafeSetOption(setOption, kShowNpcNameOption, enabled != 0);
	}
	g_optionSynced = true;
}

// Called by the WARP Game Settings bridge. Only the custom NPC option is
// written here. Native options such as /font must remain owned by the client:
// pre-writing them prevents the client's registered TALKTYPE handler from
// observing a state change and running its normal update path.
extern "C" __declspec(dllexport) void SetNpcNameOverlayOption(
	uint32_t optionId,
	int enabled)
{
	if (!BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
		return;

	const LONG value = enabled ? 1 : 0;
	if (optionId == kShowNpcNameOption)
	{
		InterlockedExchange(&g_enabled, value);
		g_nextRenderTick = 0;
		if (EnsureBase())
		{
			auto setOption =
				reinterpret_cast<FnSetOption>(Rebase(kSetOption));
			SafeSetOption(setOption, optionId, value != 0);
		}
		g_optionSynced = true;
	}
}

static void RenderNpcBalloons(void* gameMode, DWORD worldManager)
{
	if (g_down || !gameMode || !EnsureBase())
		return;

	BYTE* gm = reinterpret_cast<BYTE*>(gameMode);
	DWORD savedHoverGid = 0;
	if (!SafeReadDword(gm + O_HG, &savedHoverGid))
		return;

	auto destroy = reinterpret_cast<FnDestroy>(Rebase(kDestroy));
	void* uiManager = reinterpret_cast<void*>(Rebase(kUiMgr));
	if (InterlockedCompareExchange(&g_enabled, 0, 0) == 0)
	{
		g_nextRenderTick = 0;
		if (!g_balloons.empty())
			DestroyAllBalloons(destroy, uiManager);
		return;
	}

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
				SafeDestroy(destroy, uiManager, it->second.ptr);
			g_missingSince.erase(it->first);
			g_clippedUntil.erase(it->first);
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
	void* savedMain = nullptr;
	if (!SafeReadPtr(mainSlot, &savedMain))
		return;

	bool nameAboveHead = false;
	SafeGetOption(getOption, kNameAboveHeadOption, &nameAboveHead);

	BYTE* viewport = nullptr;
	void* rawViewport = nullptr;
	SafeReadPtr(reinterpret_cast<void*>(Rebase(kViewport)), &rawViewport);
	viewport = reinterpret_cast<BYTE*>(rawViewport);
	const int viewportWidth = viewport
		? [] (BYTE* view) -> int
		{
			DWORD value = 0;
			return SafeReadDword(view + 0x28, &value)
				? static_cast<int>(value)
				: 0;
		}(viewport)
		: 0;
	const int viewportHeight = viewport
		? [] (BYTE* view) -> int
		{
			DWORD value = 0;
			return SafeReadDword(view + 0x2C, &value)
				? static_cast<int>(value)
				: 0;
		}(viewport)
		: 0;
	const DWORD now = GetTickCount();
	std::vector<std::pair<uint32_t, DWORD>> stale;

	for (const auto& entry : g_knownSnapshot)
	{
		const uint32_t gid = entry.first;
		if (g_balloons.find(gid) == g_balloons.end())
		{
			auto clipped = g_clippedUntil.find(gid);
			if (clipped != g_clippedUntil.end() &&
			    TickBefore(now, clipped->second))
				continue;
		}

		void* actor = nullptr;
		SafeGetActor(
			getActor,
			reinterpret_cast<void*>(worldManager),
			gid,
			&actor);
		if (!actor)
			SafeGetActor(
				getActorFallback,
				reinterpret_cast<void*>(worldManager),
				gid,
				&actor);

		auto balloon = g_balloons.find(gid);
		if (!actor)
		{
			if (balloon != g_balloons.end())
			{
				if (balloon->second.ptr)
					SafeDestroy(destroy, uiManager, balloon->second.ptr);
				g_balloons.erase(balloon);
			}

			auto missing = g_missingSince.find(gid);
			if (missing == g_missingSince.end())
				g_missingSince[gid] = now;
			else if (now - missing->second >= kStaleNpcMs)
				stale.push_back(entry);
			g_clippedUntil.erase(gid);
			continue;
		}

		g_missingSince.erase(gid);
		void* internedName = nullptr;
		if (!SafeReadPtr(
			reinterpret_cast<BYTE*>(actor) + 0x110,
			&internedName))
		{
			g_suppressUntil = now + kClippedRetryMs;
			continue;
		}
		if (!internedName)
			continue;

		if (balloon == g_balloons.end() || !balloon->second.ptr)
		{
			void* slot = nullptr;
			if (!SafeFactory(factory, &slot))
			{
				g_suppressUntil = now + kClippedRetryMs;
				continue;
			}
			if (!slot)
				continue;
			g_balloons[gid] = NpcBalloon{slot};
			balloon = g_balloons.find(gid);
		}

		if (!SafeWritePtr(mainSlot, balloon->second.ptr))
			return;
		if (!SafeSetup(setup, gameMode, actor))
		{
			SafeWritePtr(mainSlot, savedMain);
			SafeWriteDword(gm + O_HG, savedHoverGid);
			ResetOverlayState(true);
			g_suppressUntil = now + kClippedRetryMs;
			return;
		}

		if (IsBalloonViewportClamped(
			balloon->second.ptr,
			viewportWidth,
			viewportHeight))
		{
			SafeWritePtr(mainSlot, savedMain);
			if (balloon->second.ptr)
				SafeDestroy(destroy, uiManager, balloon->second.ptr);
			g_balloons.erase(gid);
			g_clippedUntil[gid] = now + kClippedRetryMs;
			continue;
		}

		g_clippedUntil.erase(gid);

		// Hover-style NPC balloons normally use the below-character branch in
		// UpdateBalloonPos because NPC actors have no +0xA8 name anchor. Match
		// the client's above-head branch when /font (option 0x5C) is enabled.
		if (nameAboveHead && viewportHeight > 0)
		{
			BYTE* balloonObject =
				reinterpret_cast<BYTE*>(balloon->second.ptr);
			float actorScale = 0.0f;
			if (!SafeReadFloat(
				reinterpret_cast<BYTE*>(actor) + 0x5C,
				&actorScale))
				actorScale = 0.0f;
			if (actorScale > 0.0f && actorScale < 10.0f)
			{
				const int belowBase = viewportHeight / 24;
				const int aboveBase = -(viewportHeight * 5) / 24;
				const int belowOffset =
					static_cast<int>(belowBase * actorScale);
				const int aboveOffset =
					static_cast<int>(aboveBase * actorScale);
				DWORD rawX = 0;
				DWORD rawY = 0;
				void* rawVtable = nullptr;
				if (SafeReadDword(balloonObject + 0x1C, &rawX) &&
				    SafeReadDword(balloonObject + 0x20, &rawY) &&
				    SafeReadPtr(balloonObject, &rawVtable))
				{
					void* rawSetPosition = nullptr;
					SafeReadPtr(
						reinterpret_cast<BYTE*>(rawVtable) +
							sizeof(void*) * 4,
						&rawSetPosition);
					auto setPosition =
						reinterpret_cast<FnSetPosition>(
							rawSetPosition);
					SafeSetPosition(
						setPosition,
						balloonObject,
						static_cast<int>(rawX),
						static_cast<int>(rawY) +
							aboveOffset - belowOffset);
				}
			}
		}
		SafeWritePtr(mainSlot, savedMain);
	}

	SafeWritePtr(mainSlot, savedMain);
	SafeWriteDword(gm + O_HG, savedHoverGid);

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
			g_clippedUntil.erase(entry.first);
		}
		if (erased)
			InterlockedExchange(&g_knownDirty, 1);
	}
}

extern "C" __declspec(dllexport) void NpcNameOverlayFrame(void* gameMode)
{
	if (!BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
		return;

	DWORD worldManager = 0;
	if (!BeginNpcFrame(gameMode, &worldManager))
		return;

	SyncEnabledFromClientOption();
	PollExtnSharedBlock();
	if (InterlockedCompareExchange(&g_enabled, 0, 0) != 0 &&
	    !ShouldRenderNpcOverlayNow())
		return;
	RenderNpcBalloons(gameMode, worldManager);
}

BOOL APIENTRY NpcNameOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
	if (reason == DLL_PROCESS_DETACH && reserved != nullptr)
		return TRUE;

	switch (reason)
	{
	case DLL_PROCESS_ATTACH:
		if (!BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
			break;
		DisableThreadLibraryCalls(module);
		g_down = false;
		g_enabled = 0;
		g_renderIntervalLoaded = 0;
		g_renderIntervalMs = kDefaultFrameIntervalMs;
		g_nextRenderTick = 0;
		EnsureBase();
		break;

	case DLL_PROCESS_DETACH:
		g_down = true;
		// Drain C++ containers while CRT heap is intact — see
		// ItemColorExtNameCleanup for the full explanation.
		// NO LOCK: all other threads are dead during DETACH.
		g_knownNpcs.clear();
		g_knownSnapshot.clear();
		g_balloons.clear();
		g_missingSince.clear();
		g_clippedUntil.clear();
		g_lastGameMode = nullptr;
		g_lastWorldManager = 0;
		g_suppressUntil = 0;
		g_extnBlock = nullptr;
		g_extnProbeComplete = false;
		g_extnNextProbeTick = 0;
		g_extnReadSequence = 0;
		g_optionSynced = false;
		g_renderIntervalLoaded = 0;
		g_renderIntervalMs = kDefaultFrameIntervalMs;
		g_nextRenderTick = 0;
		break;
	}
	return TRUE;
}

extern "C" __declspec(dllexport) void NpcNameOverlayInit()
{
}
