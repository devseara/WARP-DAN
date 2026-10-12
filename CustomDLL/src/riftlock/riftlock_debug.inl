#ifndef RIFTLOCK_DEBUG_INL
#define RIFTLOCK_DEBUG_INL

#include <windows.h>
#include <tlhelp32.h>
#include <intrin.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace riftlock_debug {

enum DebuggerFlags : std::uint16_t {
	kDebuggerApi = 0x0001,
	kRemoteDebuggerApi = 0x0002,
	kPebBeingDebugged = 0x0004,
	kProcessDebugPort = 0x0008,
	kProcessDebugObject = 0x0010,
	kProcessDebugFlags = 0x0020,
};

enum ScanFlags : std::uint16_t {
	kProcessScanComplete = 0x0001,
	kThreadScanComplete = 0x0002,
	kHandleScanComplete = 0x0004,
	kRequiredScans = kProcessScanComplete | kThreadScanComplete | kHandleScanComplete,
};

struct Snapshot {
	std::uint8_t digest[32];
	std::uint16_t debugger_flags;
	std::uint16_t hardware_breakpoint_count;
	std::uint16_t threads_checked;
	std::uint16_t suspicious_handle_count;
	std::uint16_t external_handle_count;
	std::uint16_t scan_flags;
	std::uint32_t first_hardware_thread_id;
	std::uint32_t first_hardware_dr7;
	std::uint32_t first_handle_owner_pid;
	std::uint32_t first_handle_access;
};

struct ThreadSkipDiagnostic {
	std::uint32_t thread_id;
	std::uint32_t error;
	std::uint8_t stage;
	riftlock_modules::ThreadAddressDiagnostic address;
	char description[128];
};

typedef struct _RiftlockSystemHandleEntryEx {
	PVOID Object;
	ULONG_PTR UniqueProcessId;
	ULONG_PTR HandleValue;
	ULONG GrantedAccess;
	USHORT CreatorBackTraceIndex;
	USHORT ObjectTypeIndex;
	ULONG HandleAttributes;
	ULONG Reserved;
} RiftlockSystemHandleEntryEx;

typedef struct _RiftlockSystemHandleInformationEx {
	ULONG_PTR NumberOfHandles;
	ULONG_PTR Reserved;
	RiftlockSystemHandleEntryEx Handles[1];
} RiftlockSystemHandleInformationEx;

using NtQueryInformationProcessFn = LONG (NTAPI *)(HANDLE, ULONG, PVOID, ULONG, PULONG);
using NtQuerySystemInformationFn = LONG (NTAPI *)(ULONG, PVOID, ULONG, PULONG);

static const LONG kStatusInfoLengthMismatch = static_cast<LONG>(0xC0000004u);
static const LONG kStatusPortNotSet = static_cast<LONG>(0xC0000353u);
static const ULONG kSystemExtendedHandleInformation = 64;
static const ULONG kProcessDebugPortClass = 7;
static const ULONG kProcessDebugObjectHandleClass = 30;
static const ULONG kProcessDebugFlagsClass = 31;
static const DWORD kDangerousProcessAccess = PROCESS_TERMINATE | PROCESS_CREATE_THREAD |
	PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_DUP_HANDLE |
	PROCESS_SET_INFORMATION | PROCESS_SUSPEND_RESUME;

static SRWLOCK g_snapshot_lock = SRWLOCK_INIT;
static SRWLOCK g_diagnostic_lock = SRWLOCK_INIT;
static LONG g_worker_queued = 0;
static riftlock_assets::Sha256Fn g_sha256 = nullptr;
static Snapshot g_snapshot = {};
static ThreadSkipDiagnostic g_thread_skip = {};

void trace(const char* message) {
#if defined(RIFTLOCK_DEBUG_TRACE)
	fprintf(stderr, "debug-trace: %s\n", message);
#else
	(void)message;
#endif
}

void append_u16(std::vector<std::uint8_t>& output, std::uint16_t value) {
	output.push_back(static_cast<std::uint8_t>(value & 0xff));
	output.push_back(static_cast<std::uint8_t>((value >> 8) & 0xff));
}

void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
	for (unsigned int shift = 0; shift < 32; shift += 8)
		output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xff));
}

void inspect_debug_registers(const CONTEXT& context, DWORD thread_id, Snapshot& output) {
	const DWORD_PTR registers[4] = {context.Dr0, context.Dr1, context.Dr2, context.Dr3};
	std::uint16_t active = 0;
	for (unsigned int index = 0; index < 4; ++index) {
		const DWORD_PTR enable = (context.Dr7 >> (index * 2)) & 0x3;
		if (enable != 0 && registers[index] != 0)
			++active;
	}
	if (active != 0 && output.hardware_breakpoint_count == 0) {
		output.first_hardware_thread_id = thread_id;
		output.first_hardware_dr7 = static_cast<std::uint32_t>(context.Dr7);
	}
	const std::uint32_t total = static_cast<std::uint32_t>(
		output.hardware_breakpoint_count) + active;
	output.hardware_breakpoint_count = total > UINT16_MAX ? UINT16_MAX :
		static_cast<std::uint16_t>(total);
}

void capture_thread_skip_identity(HANDLE thread, DWORD thread_id,
	ThreadSkipDiagnostic& output) {
	output.thread_id = thread_id;
	if (thread == nullptr)
		return;
	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	using NtQueryInformationThreadFn = LONG (NTAPI *)(HANDLE, ULONG, PVOID, ULONG, PULONG);
	auto query_thread = ntdll == nullptr ? nullptr :
		reinterpret_cast<NtQueryInformationThreadFn>(
			GetProcAddress(ntdll, "NtQueryInformationThread"));
	PVOID start_address = nullptr;
	if (query_thread != nullptr && query_thread(thread, 9, &start_address,
		sizeof(start_address), nullptr) >= 0)
		riftlock_modules::describe_thread_address(
			reinterpret_cast<std::uintptr_t>(start_address), output.address);

	using GetThreadDescriptionFn = HRESULT (WINAPI *)(HANDLE, PWSTR*);
	HMODULE kernel = GetModuleHandleW(L"kernel32.dll");
	auto get_description = kernel == nullptr ? nullptr :
		reinterpret_cast<GetThreadDescriptionFn>(
			GetProcAddress(kernel, "GetThreadDescription"));
	PWSTR description = nullptr;
	if (get_description != nullptr && SUCCEEDED(get_description(thread, &description)) &&
		description != nullptr) {
		std::string utf8;
		if (riftlock_assets::wide_to_utf8(description, utf8))
			strncpy_s(output.description, sizeof(output.description), utf8.c_str(), _TRUNCATE);
		LocalFree(description);
	}
}

bool scan_thread_contexts_once(Snapshot& output) {
	trace("thread-scan-start");
	HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
	if (snapshot == INVALID_HANDLE_VALUE)
		return false;
	trace("thread-snapshot-created");
	const DWORD process_id = GetCurrentProcessId();
	const DWORD current_thread = GetCurrentThreadId();
	bool complete = true;
	std::uint32_t matching_threads = 0;
	ThreadSkipDiagnostic first_skip = {};
	auto record_skip = [&](DWORD thread_id, DWORD error, std::uint8_t stage,
		HANDLE thread) {
		if (first_skip.stage == 0) {
			first_skip.error = error;
			first_skip.stage = stage;
			capture_thread_skip_identity(thread, thread_id, first_skip);
		}
		complete = false;
	};
	THREADENTRY32 entry = {};
	entry.dwSize = sizeof(entry);
	BOOL available = Thread32First(snapshot, &entry);
	while (available) {
		if (entry.th32OwnerProcessID == process_id) {
			++matching_threads;
			if (matching_threads > 128) {
				complete = false;
				break;
			}
			CONTEXT context = {};
			bool captured = false;
			if (entry.th32ThreadID == current_thread) {
				// The scan runs on a dedicated, short-lived worker that does not
				// execute game code. Inspecting its own context is both irrelevant
				// and unsafe under x86 LTCG, so only persistent peer threads count.
				trace("current-scan-worker-skipped");
			} else {
				trace("other-thread-capture-start");
				HANDLE thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT |
					THREAD_QUERY_INFORMATION, FALSE, entry.th32ThreadID);
				if (thread != nullptr) {
					const DWORD previous_suspend = SuspendThread(thread);
					if (previous_suspend != static_cast<DWORD>(-1)) {
						context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
						captured = GetThreadContext(thread, &context) != FALSE;
						const DWORD context_error = captured ? ERROR_SUCCESS : GetLastError();
						const DWORD resume_result = ResumeThread(thread);
						const DWORD resume_error = resume_result == static_cast<DWORD>(-1) ?
							GetLastError() : ERROR_SUCCESS;
						if (!captured)
							record_skip(entry.th32ThreadID, context_error, 3, thread);
						if (resume_result == static_cast<DWORD>(-1))
							record_skip(entry.th32ThreadID, resume_error, 4, nullptr);
					} else if (GetLastError() != ERROR_INVALID_PARAMETER) {
						record_skip(entry.th32ThreadID, GetLastError(), 2, thread);
					} else {
						record_skip(entry.th32ThreadID, ERROR_INVALID_PARAMETER, 2, thread);
					}
					CloseHandle(thread);
				} else {
					record_skip(entry.th32ThreadID, GetLastError(), 1, nullptr);
				}
			}
			trace("thread-entry-capture-complete");
			if (entry.th32ThreadID == current_thread) {
				// Intentionally excluded from completeness accounting.
			} else if (captured) {
				if (output.threads_checked != UINT16_MAX)
					++output.threads_checked;
				inspect_debug_registers(context, entry.th32ThreadID, output);
			} else {
				if (first_skip.stage == 0)
					record_skip(entry.th32ThreadID, ERROR_GEN_FAILURE, 3, nullptr);
			}
		}
		available = Thread32Next(snapshot, &entry);
	}
	const DWORD final_error = GetLastError();
	CloseHandle(snapshot);
	const bool result = complete && output.threads_checked != 0 &&
		(final_error == ERROR_NO_MORE_FILES || final_error == ERROR_SUCCESS);
	AcquireSRWLockExclusive(&g_diagnostic_lock);
	g_thread_skip = result ? ThreadSkipDiagnostic{} : first_skip;
	ReleaseSRWLockExclusive(&g_diagnostic_lock);
	return result;
}

bool thread_skip_diagnostic(ThreadSkipDiagnostic& output) {
	AcquireSRWLockShared(&g_diagnostic_lock);
	output = g_thread_skip;
	ReleaseSRWLockShared(&g_diagnostic_lock);
	return output.stage != 0;
}

bool scan_thread_contexts(Snapshot& output) {
	Snapshot latest = {};
	for (unsigned int attempt = 0; attempt < 2; ++attempt) {
		Snapshot candidate = {};
		const bool complete = scan_thread_contexts_once(candidate);
		latest = candidate;
		if (complete) {
			output.hardware_breakpoint_count = candidate.hardware_breakpoint_count;
			output.threads_checked = candidate.threads_checked;
			output.first_hardware_thread_id = candidate.first_hardware_thread_id;
			output.first_hardware_dr7 = candidate.first_hardware_dr7;
			return true;
		}
		if (attempt == 0)
			Sleep(1);
	}
	output.hardware_breakpoint_count = latest.hardware_breakpoint_count;
	output.threads_checked = latest.threads_checked;
	output.first_hardware_thread_id = latest.first_hardware_thread_id;
	output.first_hardware_dr7 = latest.first_hardware_dr7;
	return false;
}

bool query_process_path(DWORD process_id, std::wstring& output) {
	HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, process_id);
	if (process == nullptr)
		return false;
	wchar_t path[1024] = {};
	DWORD length = static_cast<DWORD>(sizeof(path) / sizeof(path[0]));
	const bool ok = QueryFullProcessImageNameW(process, 0, path, &length) != FALSE &&
		length != 0 && length < sizeof(path) / sizeof(path[0]);
	CloseHandle(process);
	if (ok)
		output.assign(path, length);
	return ok;
}

bool trusted_handle_owner(ULONG_PTR process_id) {
	if (process_id == 0 || process_id == 4)
		return true;
	if (process_id > UINT32_MAX)
		return false;
	std::wstring path;
	if (!query_process_path(static_cast<DWORD>(process_id), path))
		return false;
	wchar_t windows_path[MAX_PATH] = {};
	const UINT length = GetWindowsDirectoryW(windows_path, MAX_PATH);
	return length != 0 && length < MAX_PATH &&
		riftlock_modules::path_is_under(riftlock_modules::lowercase(path),
			riftlock_modules::lowercase(windows_path));
}

void record_external_handle(const RiftlockSystemHandleEntryEx& entry,
	Snapshot& output) {
	if (output.external_handle_count != UINT16_MAX)
		++output.external_handle_count;
	const bool dangerous = (entry.GrantedAccess & kDangerousProcessAccess) != 0 &&
		!trusted_handle_owner(entry.UniqueProcessId);
	if (!dangerous)
		return;
	if (output.suspicious_handle_count == 0) {
		output.first_handle_owner_pid = entry.UniqueProcessId > UINT32_MAX ? 0 :
			static_cast<std::uint32_t>(entry.UniqueProcessId);
		output.first_handle_access = entry.GrantedAccess;
	}
	if (output.suspicious_handle_count != UINT16_MAX)
		++output.suspicious_handle_count;
}

bool scan_external_handles(NtQuerySystemInformationFn query_system, Snapshot& output,
	bool force_duplicate_fallback = false) {
	if (query_system == nullptr)
		return false;
	HANDLE self = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, GetCurrentProcessId());
	if (self == nullptr)
		return false;
	std::vector<std::uint8_t> buffer(1024 * 1024);
	LONG status = kStatusInfoLengthMismatch;
	ULONG needed = 0;
	for (unsigned int attempt = 0; attempt < 8; ++attempt) {
		status = query_system(kSystemExtendedHandleInformation, buffer.data(),
			static_cast<ULONG>(buffer.size()), &needed);
		if (status != kStatusInfoLengthMismatch)
			break;
		std::size_t next_size = needed > buffer.size() ? needed : buffer.size() * 2;
		if (next_size > 64u * 1024u * 1024u) {
			CloseHandle(self);
			return false;
		}
		buffer.resize(next_size);
	}
	if (status < 0 || buffer.size() < sizeof(RiftlockSystemHandleInformationEx)) {
		CloseHandle(self);
		return false;
	}
	const auto* information = reinterpret_cast<const RiftlockSystemHandleInformationEx*>(
		buffer.data());
	const std::size_t header_size = offsetof(RiftlockSystemHandleInformationEx, Handles);
	const std::size_t maximum_entries = (buffer.size() - header_size) /
		sizeof(RiftlockSystemHandleEntryEx);
	if (information->NumberOfHandles > maximum_entries) {
		CloseHandle(self);
		return false;
	}
	const ULONG_PTR current_pid = GetCurrentProcessId();
	const ULONG_PTR self_handle = reinterpret_cast<ULONG_PTR>(self);
	PVOID process_object = nullptr;
	USHORT process_type_index = 0;
	for (ULONG_PTR index = 0; index < information->NumberOfHandles; ++index) {
		const RiftlockSystemHandleEntryEx& entry = information->Handles[index];
		if (entry.UniqueProcessId == current_pid && entry.HandleValue == self_handle) {
			process_object = entry.Object;
			process_type_index = entry.ObjectTypeIndex;
			break;
		}
	}
	if (process_type_index == 0) {
		CloseHandle(self);
		return false;
	}
	if (process_object != nullptr && !force_duplicate_fallback) {
		for (ULONG_PTR index = 0; index < information->NumberOfHandles; ++index) {
			const RiftlockSystemHandleEntryEx& entry = information->Handles[index];
			if (entry.Object == process_object && entry.UniqueProcessId != current_pid)
				record_external_handle(entry, output);
		}
		CloseHandle(self);
		return true;
	}

	// Non-elevated Windows processes receive masked kernel object pointers.
	// Fall back to same-user duplication of process-type handles that already
	// carry injection-capable access. Protected/higher-integrity owners cannot be
	// duplicated and remain outside this user-mode detector's trust boundary.
	for (ULONG_PTR index = 0; index < information->NumberOfHandles; ++index) {
		const RiftlockSystemHandleEntryEx& entry = information->Handles[index];
		if (entry.UniqueProcessId == current_pid ||
			entry.ObjectTypeIndex != process_type_index ||
			(entry.GrantedAccess & kDangerousProcessAccess) == 0 ||
			entry.UniqueProcessId == 0 || entry.UniqueProcessId > UINT32_MAX)
			continue;
		HANDLE owner = OpenProcess(PROCESS_DUP_HANDLE, FALSE,
			static_cast<DWORD>(entry.UniqueProcessId));
		if (owner == nullptr)
			continue;
		HANDLE duplicate = nullptr;
		const BOOL duplicated = DuplicateHandle(owner,
			reinterpret_cast<HANDLE>(entry.HandleValue), GetCurrentProcess(),
			&duplicate, 0, FALSE, DUPLICATE_SAME_ACCESS);
		CloseHandle(owner);
		if (!duplicated || duplicate == nullptr)
			continue;
		const DWORD target_pid = GetProcessId(duplicate);
		CloseHandle(duplicate);
		if (target_pid == GetCurrentProcessId())
			record_external_handle(entry, output);
	}
	CloseHandle(self);
	return true;
}

bool test_duplicate_handle_fallback(Snapshot& output) {
	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	auto query_system = ntdll == nullptr ? nullptr :
		reinterpret_cast<NtQuerySystemInformationFn>(
			GetProcAddress(ntdll, "NtQuerySystemInformation"));
	return scan_external_handles(query_system, output, true);
}

bool scan(Snapshot& output, std::string& error) {
	trace("scan-start");
	if (g_sha256 == nullptr) {
		error = "debug evidence hashing is not initialized";
		return false;
	}
	Snapshot result = {};
	if (IsDebuggerPresent())
		result.debugger_flags |= kDebuggerApi;
	BOOL remote_debugger = FALSE;
	const bool remote_complete = CheckRemoteDebuggerPresent(GetCurrentProcess(),
		&remote_debugger) != FALSE;
	if (remote_complete && remote_debugger)
		result.debugger_flags |= kRemoteDebuggerApi;
	trace("debugger-apis-complete");
#if defined(_M_IX86)
	const std::uint8_t* peb = reinterpret_cast<const std::uint8_t*>(__readfsdword(0x30));
	if (peb != nullptr && peb[2] != 0)
		result.debugger_flags |= kPebBeingDebugged;
#endif

	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	auto query_process = ntdll == nullptr ? nullptr :
		reinterpret_cast<NtQueryInformationProcessFn>(
			GetProcAddress(ntdll, "NtQueryInformationProcess"));
	auto query_system = ntdll == nullptr ? nullptr :
		reinterpret_cast<NtQuerySystemInformationFn>(
			GetProcAddress(ntdll, "NtQuerySystemInformation"));
	bool process_complete = remote_complete && query_process != nullptr;
	if (query_process != nullptr) {
		ULONG_PTR debug_port = 0;
		HANDLE debug_object = nullptr;
		ULONG debug_flags = 1;
		const LONG port_status = query_process(GetCurrentProcess(), kProcessDebugPortClass,
			&debug_port, sizeof(debug_port), nullptr);
		const LONG object_status = query_process(GetCurrentProcess(),
			kProcessDebugObjectHandleClass, &debug_object, sizeof(debug_object), nullptr);
		const LONG flags_status = query_process(GetCurrentProcess(), kProcessDebugFlagsClass,
			&debug_flags, sizeof(debug_flags), nullptr);
		process_complete = process_complete && port_status >= 0 && flags_status >= 0 &&
			(object_status >= 0 || object_status == kStatusPortNotSet);
		if (port_status >= 0 && debug_port != 0)
			result.debugger_flags |= kProcessDebugPort;
		if (object_status >= 0 && debug_object != nullptr)
			result.debugger_flags |= kProcessDebugObject;
		if (flags_status >= 0 && debug_flags == 0)
			result.debugger_flags |= kProcessDebugFlags;
	}
	if (process_complete)
		result.scan_flags |= kProcessScanComplete;
	trace("process-queries-complete");
	if (scan_thread_contexts(result))
		result.scan_flags |= kThreadScanComplete;
	trace("thread-contexts-complete");
	if (scan_external_handles(query_system, result))
		result.scan_flags |= kHandleScanComplete;
	trace("external-handles-complete");

	std::vector<std::uint8_t> material;
	append_u16(material, result.debugger_flags);
	append_u16(material, result.hardware_breakpoint_count);
	append_u16(material, result.threads_checked);
	append_u16(material, result.suspicious_handle_count);
	append_u16(material, result.external_handle_count);
	append_u16(material, result.scan_flags);
	append_u32(material, result.first_hardware_thread_id);
	append_u32(material, result.first_hardware_dr7);
	append_u32(material, result.first_handle_owner_pid);
	append_u32(material, result.first_handle_access);
	if (g_sha256(result.digest, material.data(),
		static_cast<unsigned long long>(material.size())) != 0) {
		error = "could not hash debug evidence";
		return false;
	}
	output = result;
	trace("scan-complete");
	return true;
}

DWORD WINAPI refresh_worker(LPVOID) {
	Snapshot result = {};
	std::string error;
	if (scan(result, error)) {
		AcquireSRWLockExclusive(&g_snapshot_lock);
		g_snapshot = result;
		ReleaseSRWLockExclusive(&g_snapshot_lock);
	}
	InterlockedExchange(&g_worker_queued, 0);
	return 0;
}

void schedule_refresh() {
	if (InterlockedCompareExchange(&g_worker_queued, 1, 0) != 0)
		return;
	if (!QueueUserWorkItem(refresh_worker, nullptr, WT_EXECUTEDEFAULT))
		InterlockedExchange(&g_worker_queued, 0);
}

bool initialize(riftlock_assets::Sha256Fn sha256, Snapshot& output, std::string& error) {
	g_sha256 = sha256;
	if (!scan(output, error))
		return false;
	AcquireSRWLockExclusive(&g_snapshot_lock);
	g_snapshot = output;
	ReleaseSRWLockExclusive(&g_snapshot_lock);
	schedule_refresh();
	return true;
}

bool refresh(Snapshot& output, std::string& error) {
	AcquireSRWLockShared(&g_snapshot_lock);
	output = g_snapshot;
	ReleaseSRWLockShared(&g_snapshot_lock);
	if (output.threads_checked == 0) {
		error = "debug evidence is not initialized";
		return false;
	}
	schedule_refresh();
	return true;
}

} // namespace riftlock_debug

#endif // RIFTLOCK_DEBUG_INL
