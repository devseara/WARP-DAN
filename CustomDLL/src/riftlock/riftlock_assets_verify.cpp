#include "riftlock_assets.inl"
#include "riftlock_modules.inl"
#include "riftlock_text.inl"
#include "riftlock_debug.inl"
#include "riftlock_hooks.inl"

#include <windows.h>

#include <cstdio>
#include <string>

DWORD WINAPI riftlock_hardware_probe_thread(LPVOID event_handle) {
	WaitForSingleObject(event_handle, INFINITE);
	return 0;
}

// Overwrites bytes in a read-only image page of this process and restores the
// original protection. The probes only touch Winsock exports the verifier never
// calls, so no thread can execute the temporary bytes.
bool riftlock_probe_write(void* address, const void* bytes, std::size_t length,
	void* saved) {
	DWORD protect = 0;
	if (!VirtualProtect(address, length, PAGE_EXECUTE_READWRITE, &protect))
		return false;
	if (saved != nullptr)
		memcpy(saved, address, length);
	memcpy(address, bytes, length);
	DWORD ignored = 0;
	VirtualProtect(address, length, protect, &ignored);
	FlushInstructionCache(GetCurrentProcess(), address, length);
	return true;
}

// Locates the in-memory export address table slot of a named export.
std::uint32_t* riftlock_probe_eat_slot(HMODULE module, const char* name) {
	const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(module);
	const IMAGE_DOS_HEADER* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
	const IMAGE_NT_HEADERS32* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
		base + dos->e_lfanew);
	const IMAGE_DATA_DIRECTORY& entry =
		nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
	if (entry.VirtualAddress == 0)
		return nullptr;
	const IMAGE_EXPORT_DIRECTORY* directory =
		reinterpret_cast<const IMAGE_EXPORT_DIRECTORY*>(base + entry.VirtualAddress);
	const std::uint32_t* names = reinterpret_cast<const std::uint32_t*>(
		base + directory->AddressOfNames);
	const std::uint16_t* ordinals = reinterpret_cast<const std::uint16_t*>(
		base + directory->AddressOfNameOrdinals);
	std::uint32_t* functions = reinterpret_cast<std::uint32_t*>(
		base + directory->AddressOfFunctions);
	for (DWORD index = 0; index < directory->NumberOfNames; ++index) {
		if (strcmp(reinterpret_cast<const char*>(base + names[index]), name) == 0)
			return ordinals[index] < directory->NumberOfFunctions ?
				&functions[ordinals[index]] : nullptr;
	}
	return nullptr;
}

// Applies one synthetic hook, rescans, and restores the original bytes.
bool riftlock_hook_probe(const char* label, void* address, const void* bytes,
	std::size_t length, std::uint16_t expected_target) {
	std::uint8_t saved[8] = {};
	if (length > sizeof(saved) || !riftlock_probe_write(address, bytes, length, saved)) {
		fprintf(stderr, "%s probe could not patch its target\n", label);
		return false;
	}
	riftlock_hooks::Evidence evidence = {};
	std::string error;
	const bool scanned = riftlock_hooks::scan(evidence, error);
	if (!riftlock_probe_write(address, saved, length, nullptr)) {
		fprintf(stderr, "%s probe could not restore its target\n", label);
		return false;
	}
	if (!scanned || evidence.mismatch_count != 1 ||
		evidence.first_mismatch_target != expected_target) {
		fprintf(stderr, "%s probe was not detected: mismatches=%u first_target=%u error=%s\n",
			label, evidence.mismatch_count, evidence.first_mismatch_target, error.c_str());
		return false;
	}
	printf("%s_probe_detected mismatches=%u checked=%u unresolved=%u first_target=%u\n",
		label, evidence.mismatch_count, evidence.checked_count,
		evidence.unresolved_count, evidence.first_mismatch_target);
	return true;
}

int wmain(int argc, wchar_t** argv) {
	setvbuf(stdout, nullptr, _IONBF, 0);
	setvbuf(stderr, nullptr, _IONBF, 0);
	if (argc != 3) {
		fwprintf(stderr, L"usage: riftlock_assets_verify.exe <game-directory> <client-exe>\n");
		return 2;
	}
	const std::wstring directory = argv[1];
	const std::wstring sodium_path = directory + L"\\libsodium.dll";
	HMODULE sodium = LoadLibraryW(sodium_path.c_str());
	if (sodium == nullptr) {
		fwprintf(stderr, L"could not load %ls\n", sodium_path.c_str());
		return 1;
	}
	auto sha256 = reinterpret_cast<riftlock_assets::Sha256Fn>(
		GetProcAddress(sodium, "crypto_hash_sha256"));
	wchar_t system_directory[MAX_PATH] = {};
	const UINT system_length = GetSystemDirectoryW(system_directory, MAX_PATH);
	if (system_length == 0 || system_length >= MAX_PATH) {
		fprintf(stderr, "could not resolve the 32-bit Windows system directory\n");
		FreeLibrary(sodium);
		return 1;
	}
	const std::wstring system_root(system_directory, system_length);
	HMODULE winsock = LoadLibraryW((system_root + L"\\ws2_32.dll").c_str());
	HMODULE winmm = LoadLibraryW((system_root + L"\\winmm.dll").c_str());
	if (winsock == nullptr || winmm == nullptr) {
		fprintf(stderr, "could not load system hook-baseline modules\n");
		if (winsock != nullptr)
			FreeLibrary(winsock);
		if (winmm != nullptr)
			FreeLibrary(winmm);
		FreeLibrary(sodium);
		return 1;
	}
	std::uint8_t digest[32] = {};
	std::vector<riftlock_assets::AllowedModule> allowed_modules;
	std::string error;
	const bool valid = riftlock_assets::verify(directory, argv[2], sha256, digest,
		allowed_modules, error);
	if (!valid) {
		fprintf(stderr, "asset verification failed: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	printf("asset_manifest_sha256=");
	for (std::uint8_t byte : digest)
		printf("%02x", byte);
	printf("\n");
	printf("allowed_modules=%zu\n", allowed_modules.size());
	wchar_t current_executable[MAX_PATH] = {};
	if (GetModuleFileNameW(nullptr, current_executable, MAX_PATH) == 0) {
		fprintf(stderr, "could not resolve verifier path\n");
		return 1;
	}
	riftlock_modules::Snapshot snapshot = {};
	if (!riftlock_modules::initialize(directory, current_executable, allowed_modules,
		sha256, snapshot, error)) {
		fprintf(stderr, "module inventory failed: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	printf("loaded_modules=%u unknown_modules=%u\n",
		snapshot.module_count, snapshot.unknown_count);
	printf("private_exec=%u unlinked_exec=%u suspicious_threads=%u\n",
		snapshot.private_exec_region_count, snapshot.unlinked_exec_region_count,
		snapshot.suspicious_thread_count);
	std::vector<riftlock_modules::RuntimeRegionDiagnostic> runtime_regions;
	riftlock_modules::runtime_diagnostics(runtime_regions);
	for (std::size_t index = 0; index < runtime_regions.size(); ++index) {
		const riftlock_modules::RuntimeRegionDiagnostic& region = runtime_regions[index];
		printf("runtime_image[%zu] trusted=%u region=%p allocation=%p size=%llu protect=0x%08x type=0x%08x pe=%u image_size=%u timestamp=0x%08x path=%s header_sha256=",
			index, region.trusted_system_image, reinterpret_cast<void*>(region.region_base),
			reinterpret_cast<void*>(region.allocation_base),
			static_cast<unsigned long long>(region.region_size), region.protect,
			region.type, region.pe_valid, region.pe_image_size, region.pe_timestamp,
			region.mapped_path);
		for (std::uint8_t byte : region.header_digest)
			printf("%02x", byte);
		printf("\n");
	}
	void* private_probe = VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE,
		PAGE_EXECUTE_READWRITE);
	if (private_probe == nullptr) {
		fprintf(stderr, "could not allocate runtime detection probe\n");
		FreeLibrary(sodium);
		return 1;
	}
	riftlock_modules::Snapshot probe_snapshot = {};
	if (!riftlock_modules::scan(probe_snapshot, error) ||
		probe_snapshot.private_exec_region_count == 0 ||
		probe_snapshot.unlinked_exec_region_count == 0) {
		fprintf(stderr, "runtime private-executable probe was not detected: %s\n", error.c_str());
		VirtualFree(private_probe, 0, MEM_RELEASE);
		FreeLibrary(sodium);
		return 1;
	}
	printf("runtime_private_probe_detected private_exec=%u unlinked_exec=%u\n",
		probe_snapshot.private_exec_region_count, probe_snapshot.unlinked_exec_region_count);
	VirtualFree(private_probe, 0, MEM_RELEASE);
	if (!riftlock_modules::scan(snapshot, error) || snapshot.private_exec_region_count != 0 ||
		snapshot.unlinked_exec_region_count != 0) {
		fprintf(stderr, "runtime baseline did not recover after probe: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	riftlock_debug::Snapshot debug_evidence = {};
	if (!riftlock_debug::initialize(sha256, debug_evidence, error)) {
		fprintf(stderr, "debug evidence scan failed: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	printf("debug_flags=0x%04x hardware_breakpoints=%u threads_checked=%u suspicious_handles=%u external_handles=%u scan_flags=0x%04x first_hw_thread=%u first_dr7=0x%08x first_handle_pid=%u first_handle_access=0x%08x\n",
		debug_evidence.debugger_flags, debug_evidence.hardware_breakpoint_count,
		debug_evidence.threads_checked, debug_evidence.suspicious_handle_count,
		debug_evidence.external_handle_count, debug_evidence.scan_flags,
		debug_evidence.first_hardware_thread_id, debug_evidence.first_hardware_dr7,
		debug_evidence.first_handle_owner_pid, debug_evidence.first_handle_access);
	if (debug_evidence.first_handle_owner_pid != 0) {
		std::wstring owner_path;
		if (riftlock_debug::query_process_path(debug_evidence.first_handle_owner_pid,
			owner_path))
			fwprintf(stdout, L"first_handle_owner_path=%ls\n", owner_path.c_str());
	}
	riftlock_debug::Snapshot fallback_handles = {};
	if (!riftlock_debug::test_duplicate_handle_fallback(fallback_handles) ||
		fallback_handles.suspicious_handle_count == 0) {
		fprintf(stderr, "duplicate-handle fallback did not confirm the test parent\n");
		FreeLibrary(sodium);
		return 1;
	}
	printf("handle_fallback_detected suspicious=%u external=%u first_pid=%u first_access=0x%08x\n",
		fallback_handles.suspicious_handle_count,
		fallback_handles.external_handle_count,
		fallback_handles.first_handle_owner_pid,
		fallback_handles.first_handle_access);
	HANDLE hardware_event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
	HANDLE hardware_thread = hardware_event == nullptr ? nullptr :
		CreateThread(nullptr, 0, riftlock_hardware_probe_thread, hardware_event,
			CREATE_SUSPENDED, nullptr);
	if (hardware_thread == nullptr) {
		fprintf(stderr, "could not create hardware-breakpoint probe thread\n");
		if (hardware_event != nullptr)
			CloseHandle(hardware_event);
		FreeLibrary(sodium);
		return 1;
	}
	CONTEXT hardware_context = {};
	hardware_context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
	if (!GetThreadContext(hardware_thread, &hardware_context)) {
		fprintf(stderr, "could not read hardware-breakpoint probe context\n");
		TerminateThread(hardware_thread, 1);
		CloseHandle(hardware_thread);
		CloseHandle(hardware_event);
		FreeLibrary(sodium);
		return 1;
	}
	hardware_context.Dr0 = reinterpret_cast<DWORD_PTR>(&debug_evidence);
	hardware_context.Dr7 = 1;
	if (!SetThreadContext(hardware_thread, &hardware_context) ||
		ResumeThread(hardware_thread) == static_cast<DWORD>(-1)) {
		fprintf(stderr, "could not activate hardware-breakpoint probe\n");
		TerminateThread(hardware_thread, 1);
		CloseHandle(hardware_thread);
		CloseHandle(hardware_event);
		FreeLibrary(sodium);
		return 1;
	}
	Sleep(10);
	riftlock_debug::Snapshot hardware_probe = {};
	if (!riftlock_debug::scan(hardware_probe, error) ||
		hardware_probe.hardware_breakpoint_count == 0) {
		fprintf(stderr, "hardware-breakpoint probe was not detected: %s\n", error.c_str());
		SetEvent(hardware_event);
		WaitForSingleObject(hardware_thread, 1000);
		CloseHandle(hardware_thread);
		CloseHandle(hardware_event);
		FreeLibrary(sodium);
		return 1;
	}
	printf("hardware_probe_detected count=%u first_thread=%u first_dr7=0x%08x\n",
		hardware_probe.hardware_breakpoint_count,
		hardware_probe.first_hardware_thread_id, hardware_probe.first_hardware_dr7);
	if (SuspendThread(hardware_thread) != static_cast<DWORD>(-1)) {
		hardware_context = {};
		hardware_context.ContextFlags = CONTEXT_DEBUG_REGISTERS;
		if (GetThreadContext(hardware_thread, &hardware_context)) {
			hardware_context.Dr0 = 0;
			hardware_context.Dr1 = 0;
			hardware_context.Dr2 = 0;
			hardware_context.Dr3 = 0;
			hardware_context.Dr7 = 0;
			SetThreadContext(hardware_thread, &hardware_context);
		}
		ResumeThread(hardware_thread);
	}
	SetEvent(hardware_event);
	WaitForSingleObject(hardware_thread, 1000);
	CloseHandle(hardware_thread);
	CloseHandle(hardware_event);
	riftlock_text::Evidence text_evidence = {};
	std::uint8_t seed[32] = {};
	if (!riftlock_text::initialize(GetModuleHandleW(nullptr), sodium, error) ||
		!riftlock_text::sample(seed, sha256, text_evidence, error)) {
		fprintf(stderr, "text integrity sampling failed: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	printf("text_slices=%u checked_bytes=%u mismatches=%u\n",
		text_evidence.slice_count, text_evidence.checked_bytes,
		text_evidence.mismatch_count);
	riftlock_assets::ChallengeEvidence asset_evidence = {};
	if (!riftlock_assets::sample_challenge(seed, sha256, asset_evidence, error)) {
		fprintf(stderr, "asset challenge sampling failed: %s\n", error.c_str());
		FreeLibrary(sodium);
		return 1;
	}
	printf("asset_modules=%u grf_entries=%u loose_files=%u checked_bytes=%u mismatches=%u\n",
		asset_evidence.module_sample_count, asset_evidence.grf_sample_count,
		asset_evidence.loose_sample_count, asset_evidence.checked_bytes,
		asset_evidence.mismatch_count);
	riftlock_hooks::Evidence hook_evidence = {};
	if (!riftlock_hooks::initialize(sha256, hook_evidence, error)) {
		fprintf(stderr, "hook integrity sampling failed: %s\n", error.c_str());
		FreeLibrary(winmm);
		FreeLibrary(winsock);
		FreeLibrary(sodium);
		return 1;
	}
	printf("hook_checked=%u unresolved=%u mismatches=%u scan_flags=0x%04x first_target=%u\n",
		hook_evidence.checked_count, hook_evidence.unresolved_count,
		hook_evidence.mismatch_count, hook_evidence.scan_flags,
		hook_evidence.first_mismatch_target);

	// Positive controls: an inline jmp over WSARecv (target 4) and an EAT
	// redirect of closesocket (target 6) must each produce exactly one mismatch.
	void* wsarecv = reinterpret_cast<void*>(GetProcAddress(winsock, "WSARecv"));
	std::uint32_t* closesocket_slot = riftlock_probe_eat_slot(winsock, "closesocket");
	const std::uint8_t inline_jmp[5] = {0xe9, 0x00, 0x00, 0x00, 0x00};
	std::uint32_t redirected_rva = closesocket_slot != nullptr ? *closesocket_slot + 0x10 : 0;
	const bool probes_passed = wsarecv != nullptr && closesocket_slot != nullptr &&
		riftlock_hook_probe("hook_prologue", wsarecv, inline_jmp, sizeof(inline_jmp), 4) &&
		riftlock_hook_probe("hook_eat", closesocket_slot, &redirected_rva,
			sizeof(redirected_rva), 6);
	riftlock_hooks::Evidence restored = {};
	if (!probes_passed || !riftlock_hooks::scan(restored, error) ||
		restored.mismatch_count != 0 || restored.unresolved_count != 0) {
		fprintf(stderr, "hook probes failed or did not restore a clean baseline\n");
		FreeLibrary(winmm);
		FreeLibrary(winsock);
		FreeLibrary(sodium);
		return 1;
	}
	printf("hook_probe_restored checked=%u unresolved=%u mismatches=%u\n",
		restored.checked_count, restored.unresolved_count, restored.mismatch_count);
	return 0;
}
