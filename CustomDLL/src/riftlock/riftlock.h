#pragma once

#include <windows.h>

// Riftlock v1 client transport for the profiled 2025-07-16 Ragexe build.
// The DLL is passive: WARP installs every call site at patch time. The DLL
// never rewrites executable code, IAT entries, vtables, or Winsock exports.

#define RIFTLOCK_VERSION 0x00010000u
#define RIFTLOCK_BUILD_ID 0x00000001u

extern "C" __declspec(dllexport) DWORD __cdecl RiftlockInit(void);

// Static bridge for CConnection::Connect. WARP inserts the stock trampoline
// as the first stack argument while preserving ECX as the native receiver.
extern "C" __declspec(dllexport) BOOL __fastcall RiftlockConnectionResetBridge(
	void* connection,
	void* edx,
	DWORD original,
	void* target
);

// Static bridge for the two CPacketQueue::InsertBackData calls made after
// CRagConnection::SendPacket has applied native packet obfuscation.
extern "C" __declspec(dllexport) void __fastcall RiftlockQueuePacketBridge(
	void* queue,
	void* edx,
	DWORD original,
	DWORD length,
	const BYTE* packet
);

extern "C" __declspec(dllexport) void __fastcall RiftlockQueueDeferredPacketBridge(
	void* queue,
	void* edx,
	DWORD original,
	DWORD length,
	const BYTE* packet
);

// Static bridge at CConnection's receive-queue insertion. It forwards receive
// bytes unchanged. RiftlockReadPacketBridge strips controls at packet boundaries.
extern "C" __declspec(dllexport) void __fastcall RiftlockReceiveBytesBridge(
	void* queue,
	void* edx,
	DWORD original,
	DWORD length,
	const BYTE* bytes
);

// Static bridge for the profiled CConnection::ReadPacket. The native reader
// remains responsible for ordinary/custom packet lengths and payload copying.
extern "C" __declspec(dllexport) BOOL __fastcall RiftlockReadPacketBridge(
	void* connection, void* edx, DWORD original, void* packet, unsigned short* length
);

// Character-login raw four-byte account-ID bootstrap, before framed packets.
extern "C" __declspec(dllexport) DWORD __fastcall RiftlockReadRawBridge(
	void* connection, void* edx, DWORD original, void* buffer, DWORD length, bool exact
);
