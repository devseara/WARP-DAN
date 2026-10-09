#ifndef RIFTLOCK_MODULES_INL
#define RIFTLOCK_MODULES_INL

#include <windows.h>
#include <tlhelp32.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace riftlock_modules {

struct Snapshot {
	std::uint8_t digest[32];
	std::uint8_t first_unknown_text_digest[32];
	std::uint8_t memory_digest[32];
	std::uint16_t module_count;
	std::uint16_t unknown_count;
	std::uint16_t private_exec_region_count;
	std::uint16_t unlinked_exec_region_count;
	std::uint16_t suspicious_thread_count;
	std::uint16_t runtime_reserved;
	std::uint32_t first_unknown_size;
	std::uint32_t first_private_region_size;
	std::uint32_t first_private_region_protect;
	std::uint32_t first_suspicious_thread_id;
	std::uint32_t first_suspicious_region_type;
	char first_unknown_name[64];
};

struct ModuleRecord {
	std::string key;
	std::uint32_t image_size;
	std::uintptr_t base_address;
	std::uint8_t text_digest[32];
	bool unknown;
	std::string display_name;
};

struct RuntimeRegionDiagnostic {
	std::uintptr_t region_base;
	std::uintptr_t allocation_base;
	std::uint64_t region_size;
	std::uint32_t protect;
	std::uint32_t type;
	std::uint32_t pe_image_size;
	std::uint32_t pe_timestamp;
	std::uint8_t pe_valid;
	std::uint8_t trusted_system_image;
	std::uint8_t header_digest[32];
	char mapped_path[260];
};

struct ThreadAddressDiagnostic {
	std::uintptr_t start_address;
	std::uint32_t region_type;
	std::uint8_t trusted_module;
	char module_name[64];
	char mapped_path[260];
};

typedef struct _RiftlockUnicodeString {
	USHORT Length;
	USHORT MaximumLength;
	PWSTR Buffer;
} RiftlockUnicodeString;

typedef struct _RiftlockLdrDllLoadedNotificationData {
	ULONG Flags;
	const RiftlockUnicodeString* FullDllName;
	const RiftlockUnicodeString* BaseDllName;
	PVOID DllBase;
	ULONG SizeOfImage;
} RiftlockLdrDllLoadedNotificationData;

typedef union _RiftlockLdrDllNotificationData {
	RiftlockLdrDllLoadedNotificationData Loaded;
	RiftlockLdrDllLoadedNotificationData Unloaded;
} RiftlockLdrDllNotificationData;

using LdrDllNotificationFunction = VOID (CALLBACK *)(
	ULONG, const RiftlockLdrDllNotificationData*, PVOID);
using LdrRegisterDllNotificationFn = LONG (NTAPI *)(
	ULONG, LdrDllNotificationFunction, PVOID, PVOID*);

static LONG g_dirty = 1;
static LONG g_worker_queued = 0;
static PVOID g_notification_cookie = nullptr;
static SRWLOCK g_snapshot_lock = SRWLOCK_INIT;
static std::wstring g_directory;
static std::wstring g_client_path;
static std::wstring g_windows_directory;
// Kernel device forms ("\Device\HarddiskVolumeN\...") of the directories whose
// unlinked image mappings are trusted, as returned by GetMappedFileName.
static std::string g_system32_device_directory;
static std::string g_syswow64_device_directory;
static std::string g_client_device_directory;
static std::vector<riftlock_assets::AllowedModule> g_allowed_modules;
static riftlock_assets::Sha256Fn g_sha256 = nullptr;
static Snapshot g_snapshot = {};
static std::vector<ModuleRecord> g_module_records;
static std::vector<RuntimeRegionDiagnostic> g_runtime_diagnostics;

VOID CALLBACK loader_notification(ULONG, const RiftlockLdrDllNotificationData*, PVOID) {
	InterlockedExchange(&g_dirty, 1);
}

std::wstring lowercase(std::wstring value) {
	for (wchar_t& character : value)
		character = static_cast<wchar_t>(std::towlower(character));
	return value;
}

std::wstring parent_directory(const std::wstring& path) {
	const std::size_t slash = path.find_last_of(L"\\/");
	return slash == std::wstring::npos ? std::wstring() : path.substr(0, slash);
}

bool path_is_under(const std::wstring& path, const std::wstring& root) {
	if (root.empty() || path.size() < root.size() || _wcsnicmp(path.c_str(), root.c_str(), root.size()) != 0)
		return false;
	return path.size() == root.size() || path[root.size()] == L'\\' || path[root.size()] == L'/';
}

const riftlock_assets::AllowedModule* find_allowed(const std::wstring& name) {
	for (const riftlock_assets::AllowedModule& module : g_allowed_modules) {
		if (module.name == name)
			return &module;
	}
	return nullptr;
}

bool hash_pe_text(const std::wstring& path, std::uint8_t output[32]) {
	std::vector<std::uint8_t> header;
	if (!riftlock_assets::read_range(path, 0, 4096, header) || header.size() < 64 ||
		header[0] != 'M' || header[1] != 'Z')
		return false;
	const std::uint32_t nt_offset = riftlock_assets::read_u32(header.data() + 0x3c);
	if (nt_offset > header.size() - 24 || memcmp(header.data() + nt_offset, "PE\0\0", 4) != 0)
		return false;
	std::uint16_t section_count = 0, optional_size = 0;
	memcpy(&section_count, header.data() + nt_offset + 6, sizeof(section_count));
	memcpy(&optional_size, header.data() + nt_offset + 20, sizeof(optional_size));
	if (section_count == 0 || section_count > 96)
		return false;
	const std::uint64_t section_offset = static_cast<std::uint64_t>(nt_offset) + 24 + optional_size;
	const std::uint64_t section_bytes = static_cast<std::uint64_t>(section_count) * 40;
	std::vector<std::uint8_t> sections;
	if (!riftlock_assets::read_range(path, section_offset, section_bytes, sections))
		return false;
	for (std::uint16_t index = 0; index < section_count; ++index) {
		const std::uint8_t* section = sections.data() + static_cast<std::size_t>(index) * 40;
		if (memcmp(section, ".text", 5) != 0)
			continue;
		const std::uint32_t raw_size = riftlock_assets::read_u32(section + 16);
		const std::uint32_t raw_offset = riftlock_assets::read_u32(section + 20);
		return raw_size != 0 && riftlock_assets::hash_range(path, raw_offset, raw_size, g_sha256, output);
	}
	return false;
}

bool hash_full_file(const std::wstring& path, std::uint8_t output[32], std::uint64_t& size) {
	return riftlock_assets::file_size(path, size) &&
		riftlock_assets::hash_range(path, 0, size, g_sha256, output);
}

void append_record(std::vector<std::uint8_t>& material, const ModuleRecord& record) {
	material.insert(material.end(), record.key.begin(), record.key.end());
	material.push_back(0);
	for (unsigned int shift = 0; shift < 32; shift += 8)
		material.push_back(static_cast<std::uint8_t>((record.image_size >> shift) & 0xff));
	material.insert(material.end(), record.text_digest, record.text_digest + 32);
}

bool executable_protection(DWORD protection) {
	if ((protection & (PAGE_GUARD | PAGE_NOACCESS)) != 0)
		return false;
	const DWORD base = protection & 0xff;
	return base == PAGE_EXECUTE || base == PAGE_EXECUTE_READ ||
		base == PAGE_EXECUTE_READWRITE || base == PAGE_EXECUTE_WRITECOPY;
}

const ModuleRecord* module_for_address(const std::vector<ModuleRecord>& records,
	std::uintptr_t address) {
	for (const ModuleRecord& record : records) {
		if (address >= record.base_address &&
			address - record.base_address < record.image_size)
			return &record;
	}
	return nullptr;
}

void append_runtime_record(std::vector<std::uint8_t>& material, char kind,
	std::uintptr_t address, std::uint64_t size, std::uint32_t detail) {
	material.push_back(static_cast<std::uint8_t>(kind));
	for (unsigned int shift = 0; shift < sizeof(address) * 8; shift += 8)
		material.push_back(static_cast<std::uint8_t>((address >> shift) & 0xff));
	for (unsigned int shift = 0; shift < 64; shift += 8)
		material.push_back(static_cast<std::uint8_t>((size >> shift) & 0xff));
	for (unsigned int shift = 0; shift < 32; shift += 8)
		material.push_back(static_cast<std::uint8_t>((detail >> shift) & 0xff));
}

void describe_runtime_region(const MEMORY_BASIC_INFORMATION& memory,
	RuntimeRegionDiagnostic& output) {
	output = {};
	output.region_base = reinterpret_cast<std::uintptr_t>(memory.BaseAddress);
	output.allocation_base = reinterpret_cast<std::uintptr_t>(memory.AllocationBase);
	output.region_size = memory.RegionSize;
	output.protect = memory.Protect;
	output.type = memory.Type;

	using GetMappedFileNameFn = DWORD (WINAPI *)(HANDLE, LPVOID, LPWSTR, DWORD);
	HMODULE kernel = GetModuleHandleW(L"kernel32.dll");
	auto get_mapped_file_name = kernel == nullptr ? nullptr :
		reinterpret_cast<GetMappedFileNameFn>(GetProcAddress(kernel, "K32GetMappedFileNameW"));
	if (get_mapped_file_name != nullptr) {
		wchar_t mapped_path[1024] = {};
		const DWORD length = get_mapped_file_name(GetCurrentProcess(), memory.AllocationBase,
			mapped_path, static_cast<DWORD>(sizeof(mapped_path) / sizeof(mapped_path[0])));
		if (length > 0 && length < sizeof(mapped_path) / sizeof(mapped_path[0])) {
			std::string utf8;
			if (riftlock_assets::wide_to_utf8(std::wstring(mapped_path, length), utf8))
				strncpy_s(output.mapped_path, sizeof(output.mapped_path), utf8.c_str(), _TRUNCATE);
		}
	}

	SIZE_T bytes_read = 0;
	IMAGE_DOS_HEADER dos = {};
	if (memory.AllocationBase != nullptr &&
		ReadProcessMemory(GetCurrentProcess(), memory.AllocationBase, &dos,
			sizeof(dos), &bytes_read) && bytes_read == sizeof(dos) &&
		dos.e_magic == IMAGE_DOS_SIGNATURE && dos.e_lfanew > 0 && dos.e_lfanew < 4096) {
		IMAGE_NT_HEADERS32 nt = {};
		const std::uint8_t* base = static_cast<const std::uint8_t*>(memory.AllocationBase);
		if (ReadProcessMemory(GetCurrentProcess(), base + dos.e_lfanew, &nt,
			sizeof(nt), &bytes_read) && bytes_read == sizeof(nt) &&
			nt.Signature == IMAGE_NT_SIGNATURE) {
			output.pe_valid = 1;
			output.pe_image_size = nt.OptionalHeader.SizeOfImage;
			output.pe_timestamp = nt.FileHeader.TimeDateStamp;
		}
	}

	std::uint8_t header[4096] = {};
	if (memory.AllocationBase != nullptr &&
		ReadProcessMemory(GetCurrentProcess(), memory.AllocationBase, header,
			sizeof(header), &bytes_read) && bytes_read != 0)
		g_sha256(output.header_digest, header, static_cast<unsigned long long>(bytes_read));
}

// Converts "C:\dir" into the kernel device form used by GetMappedFileName.
bool device_form(const std::wstring& dos_path, std::string& output) {
	output.clear();
	if (dos_path.size() < 3 || dos_path[1] != L':')
		return false;
	wchar_t drive[3] = {dos_path[0], L':', L'\0'};
	wchar_t device_path[1024] = {};
	if (QueryDosDeviceW(drive, device_path,
		static_cast<DWORD>(sizeof(device_path) / sizeof(device_path[0]))) == 0)
		return false;
	return riftlock_assets::wide_to_utf8(std::wstring(device_path) + dos_path.substr(2), output);
}

// Returns the file name when path is a direct child of directory, else nullptr.
const char* direct_child_name(const char* path, const std::string& directory) {
	const std::size_t length = directory.size();
	if (length == 0 || _strnicmp(path, directory.c_str(), length) != 0 || path[length] != '\\')
		return nullptr;
	const char* name = path + length + 1;
	return *name != '\0' && strchr(name, '\\') == nullptr ? name : nullptr;
}

// Unlinked executable images are trusted when they are valid PE mappings of
// a file directly in System32 or SysWOW64, or of an app-local DLL whose on-disk
// content still matches the signed module allowlist.
bool trusted_unlinked_image(const RuntimeRegionDiagnostic& region) {
	if (region.type != MEM_IMAGE || region.pe_valid == 0 || region.pe_image_size == 0)
		return false;
	if (direct_child_name(region.mapped_path, g_system32_device_directory) != nullptr ||
		direct_child_name(region.mapped_path, g_syswow64_device_directory) != nullptr)
		return true;
	const char* name = direct_child_name(region.mapped_path, g_client_device_directory);
	if (name == nullptr)
		return false;
	const int wide_length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, nullptr, 0);
	if (wide_length <= 1)
		return false;
	std::wstring wide_name(static_cast<std::size_t>(wide_length - 1), L'\0');
	if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, &wide_name[0], wide_length) != wide_length)
		return false;
	wide_name = lowercase(wide_name);
	const riftlock_assets::AllowedModule* allowed = find_allowed(wide_name);
	std::uint8_t digest[32] = {};
	std::uint64_t size = 0;
	return allowed != nullptr && hash_full_file(g_directory + L"\\" + wide_name, digest, size) &&
		size == allowed->size && riftlock_assets::equal_digest(digest, allowed->digest);
}

bool trusted_runtime_address(const std::vector<RuntimeRegionDiagnostic>& regions,
	std::uintptr_t address) {
	for (const RuntimeRegionDiagnostic& region : regions) {
		if (region.trusted_system_image != 0 &&
			address >= region.allocation_base &&
			address - region.allocation_base < region.pe_image_size)
			return true;
	}
	return false;
}

bool scan_runtime(Snapshot& output, const std::vector<ModuleRecord>& module_records,
	std::string& error) {
	output.private_exec_region_count = 0;
	output.unlinked_exec_region_count = 0;
	output.suspicious_thread_count = 0;
	output.runtime_reserved = 0;
	output.first_private_region_size = 0;
	output.first_private_region_protect = 0;
	output.first_suspicious_thread_id = 0;
	output.first_suspicious_region_type = 0;
	memset(output.memory_digest, 0, sizeof(output.memory_digest));
	std::vector<std::uint8_t> material;
	std::vector<RuntimeRegionDiagnostic> diagnostics;
	SYSTEM_INFO system_info = {};
	GetSystemInfo(&system_info);
	std::uintptr_t address = 0;
	const std::uintptr_t maximum = reinterpret_cast<std::uintptr_t>(
		system_info.lpMaximumApplicationAddress);
	while (address < maximum) {
		MEMORY_BASIC_INFORMATION memory = {};
		if (VirtualQuery(reinterpret_cast<LPCVOID>(address), &memory, sizeof(memory)) == 0) {
			error = "virtual memory enumeration failed";
			return false;
		}
		const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(memory.BaseAddress);
		const std::uintptr_t next = base + memory.RegionSize;
		if (next <= address)
			break;
		if (memory.State == MEM_COMMIT && executable_protection(memory.Protect)) {
			const ModuleRecord* module = module_for_address(module_records, base);
			const bool private_exec = memory.Type == MEM_PRIVATE;
			const bool unlinked_candidate =
				(memory.Type == MEM_PRIVATE || memory.Type == MEM_IMAGE) && module == nullptr;
			RuntimeRegionDiagnostic diagnostic = {};
			if (unlinked_candidate) {
				describe_runtime_region(memory, diagnostic);
				diagnostic.trusted_system_image =
					trusted_unlinked_image(diagnostic) ? 1 : 0;
				diagnostics.push_back(diagnostic);
			}
			const bool unlinked_exec = unlinked_candidate &&
				diagnostic.trusted_system_image == 0;
			if (private_exec) {
				if (output.private_exec_region_count == 0) {
					output.first_private_region_size = static_cast<std::uint32_t>(
						std::min<SIZE_T>(memory.RegionSize, UINT32_MAX));
					output.first_private_region_protect = memory.Protect;
				}
				if (output.private_exec_region_count != UINT16_MAX)
					++output.private_exec_region_count;
			}
			if (unlinked_exec && output.unlinked_exec_region_count != UINT16_MAX)
				++output.unlinked_exec_region_count;
			if (private_exec || unlinked_exec)
				append_runtime_record(material, private_exec ? 'P' : 'I', base,
					memory.RegionSize, memory.Protect);
		}
		address = next;
	}

	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	using NtQueryInformationThreadFn = LONG (NTAPI *)(HANDLE, ULONG, PVOID, ULONG, PULONG);
	auto query_thread = ntdll == nullptr ? nullptr :
		reinterpret_cast<NtQueryInformationThreadFn>(
			GetProcAddress(ntdll, "NtQueryInformationThread"));
	if (query_thread == nullptr) {
		error = "thread start-address query is unavailable";
		return false;
	}
	HANDLE thread_snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
	if (thread_snapshot == INVALID_HANDLE_VALUE) {
		error = "could not create the thread inventory snapshot";
		return false;
	}
	THREADENTRY32 thread = {};
	thread.dwSize = sizeof(thread);
	BOOL has_thread = Thread32First(thread_snapshot, &thread);
	while (has_thread) {
		if (thread.th32OwnerProcessID == GetCurrentProcessId()) {
			HANDLE handle = OpenThread(THREAD_QUERY_INFORMATION, FALSE, thread.th32ThreadID);
			if (handle != nullptr) {
				PVOID start_address = nullptr;
				if (query_thread(handle, 9, &start_address, sizeof(start_address), nullptr) >= 0) {
					const std::uintptr_t start = reinterpret_cast<std::uintptr_t>(start_address);
					const ModuleRecord* module = module_for_address(module_records, start);
					if ((module == nullptr && !trusted_runtime_address(diagnostics, start)) ||
						(module != nullptr && module->unknown)) {
						MEMORY_BASIC_INFORMATION start_memory = {};
						VirtualQuery(start_address, &start_memory, sizeof(start_memory));
						if (output.suspicious_thread_count == 0) {
							output.first_suspicious_thread_id = thread.th32ThreadID;
							output.first_suspicious_region_type = start_memory.Type;
						}
						if (output.suspicious_thread_count != UINT16_MAX)
							++output.suspicious_thread_count;
						append_runtime_record(material, 'T', start, thread.th32ThreadID,
							start_memory.Type);
					}
				}
				CloseHandle(handle);
			}
		}
		has_thread = Thread32Next(thread_snapshot, &thread);
	}
	const DWORD thread_error = GetLastError();
	CloseHandle(thread_snapshot);
	if (thread_error != ERROR_NO_MORE_FILES) {
		error = "thread inventory enumeration failed";
		return false;
	}
	const std::uint8_t empty = 0;
	const std::uint8_t* bytes = material.empty() ? &empty : material.data();
	if (g_sha256(output.memory_digest, bytes,
		static_cast<unsigned long long>(material.size())) != 0) {
		error = "could not hash runtime memory evidence";
		return false;
	}
	AcquireSRWLockExclusive(&g_snapshot_lock);
	g_runtime_diagnostics.swap(diagnostics);
	ReleaseSRWLockExclusive(&g_snapshot_lock);
	return true;
}

void runtime_diagnostics(std::vector<RuntimeRegionDiagnostic>& output) {
	AcquireSRWLockShared(&g_snapshot_lock);
	output = g_runtime_diagnostics;
	ReleaseSRWLockShared(&g_snapshot_lock);
}

void describe_thread_address(std::uintptr_t address, ThreadAddressDiagnostic& output) {
	output = {};
	output.start_address = address;
	AcquireSRWLockShared(&g_snapshot_lock);
	const ModuleRecord* module = module_for_address(g_module_records, address);
	if (module != nullptr) {
		output.trusted_module = module->unknown ? 0 : 1;
		strncpy_s(output.module_name, sizeof(output.module_name),
			module->display_name.c_str(), _TRUNCATE);
	}
	ReleaseSRWLockShared(&g_snapshot_lock);
	MEMORY_BASIC_INFORMATION memory = {};
	if (VirtualQuery(reinterpret_cast<LPCVOID>(address), &memory, sizeof(memory)) == 0)
		return;
	output.region_type = memory.Type;
	if (module != nullptr)
		return;
	using GetMappedFileNameFn = DWORD (WINAPI *)(HANDLE, LPVOID, LPWSTR, DWORD);
	HMODULE kernel = GetModuleHandleW(L"kernel32.dll");
	auto get_mapped_file_name = kernel == nullptr ? nullptr :
		reinterpret_cast<GetMappedFileNameFn>(GetProcAddress(kernel, "K32GetMappedFileNameW"));
	if (get_mapped_file_name == nullptr)
		return;
	wchar_t path[1024] = {};
	const DWORD length = get_mapped_file_name(GetCurrentProcess(), memory.AllocationBase,
		path, static_cast<DWORD>(sizeof(path) / sizeof(path[0])));
	if (length == 0 || length >= sizeof(path) / sizeof(path[0]))
		return;
	std::string utf8;
	if (riftlock_assets::wide_to_utf8(std::wstring(path, length), utf8))
		strncpy_s(output.mapped_path, sizeof(output.mapped_path), utf8.c_str(), _TRUNCATE);
}

bool scan(Snapshot& output, std::string& error) {
	InterlockedExchange(&g_dirty, 0);
	HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
		GetCurrentProcessId());
	if (snapshot == INVALID_HANDLE_VALUE) {
		error = "could not create the module inventory snapshot";
		return false;
	}
	MODULEENTRY32W entry = {};
	entry.dwSize = sizeof(entry);
	std::vector<ModuleRecord> records;
	bool ok = Module32FirstW(snapshot, &entry) != FALSE;
	while (ok) {
		const std::wstring path = entry.szExePath;
		const std::wstring name = lowercase(entry.szModule);
		std::string name_utf8;
		ModuleRecord record = {};
		record.image_size = entry.modBaseSize;
		record.base_address = reinterpret_cast<std::uintptr_t>(entry.modBaseAddr);
		record.unknown = false;
		if (!riftlock_assets::wide_to_utf8(name, name_utf8) ||
			!hash_pe_text(path, record.text_digest)) {
			CloseHandle(snapshot);
			error = "could not hash a loaded module";
			return false;
		}
		const bool client_executable = _wcsicmp(path.c_str(), g_client_path.c_str()) == 0;
		const bool app_local = _wcsicmp(parent_directory(path).c_str(), g_directory.c_str()) == 0;
		const bool system_module = path_is_under(path, g_windows_directory);
		char origin = 'U';
		if (client_executable) {
			origin = 'E';
		} else if (app_local) {
			origin = 'A';
			const riftlock_assets::AllowedModule* allowed = find_allowed(name);
			std::uint8_t file_digest[32] = {};
			std::uint64_t file_length = 0;
			if (allowed == nullptr || !hash_full_file(path, file_digest, file_length) ||
				file_length != allowed->size ||
				!riftlock_assets::equal_digest(file_digest, allowed->digest))
				record.unknown = true;
		} else if (system_module) {
			origin = 'S';
		} else {
			record.unknown = true;
		}
		record.key.assign(1, origin);
		record.key.push_back('|');
		record.key += name_utf8;
		record.display_name = name_utf8;
		records.push_back(record);
		ok = Module32NextW(snapshot, &entry) != FALSE;
	}
	const DWORD final_error = GetLastError();
	CloseHandle(snapshot);
	if (final_error != ERROR_NO_MORE_FILES) {
		error = "module inventory enumeration failed";
		return false;
	}
	std::sort(records.begin(), records.end(), [](const ModuleRecord& left, const ModuleRecord& right) {
		return left.key < right.key;
	});
	std::vector<std::uint8_t> material;
	Snapshot result = {};
	for (const ModuleRecord& record : records) {
		append_record(material, record);
		if (record.unknown) {
			if (result.unknown_count == 0) {
				strncpy_s(result.first_unknown_name, sizeof(result.first_unknown_name),
					record.display_name.c_str(), _TRUNCATE);
				result.first_unknown_size = record.image_size;
				memcpy(result.first_unknown_text_digest, record.text_digest,
					sizeof(result.first_unknown_text_digest));
			}
			if (result.unknown_count != UINT16_MAX)
				++result.unknown_count;
		}
		if (result.module_count != UINT16_MAX)
			++result.module_count;
	}
	const std::uint8_t empty = 0;
	const std::uint8_t* bytes = material.empty() ? &empty : material.data();
	if (g_sha256(result.digest, bytes, static_cast<unsigned long long>(material.size())) != 0) {
		error = "could not hash the module inventory";
		return false;
	}
	if (!scan_runtime(result, records, error))
		return false;
	AcquireSRWLockExclusive(&g_snapshot_lock);
	g_module_records = records;
	g_snapshot = result;
	ReleaseSRWLockExclusive(&g_snapshot_lock);
	output = result;
	return true;
}

DWORD WINAPI refresh_worker(LPVOID) {
	std::string error;
	if (InterlockedCompareExchange(&g_dirty, 0, 0) != 0) {
		Snapshot ignored = {};
		if (!scan(ignored, error))
			InterlockedExchange(&g_dirty, 1);
	} else {
		Snapshot result = {};
		std::vector<ModuleRecord> records;
		AcquireSRWLockShared(&g_snapshot_lock);
		result = g_snapshot;
		records = g_module_records;
		ReleaseSRWLockShared(&g_snapshot_lock);
		if (scan_runtime(result, records, error)) {
			AcquireSRWLockExclusive(&g_snapshot_lock);
			g_snapshot = result;
			ReleaseSRWLockExclusive(&g_snapshot_lock);
		}
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

bool refresh(Snapshot& output, bool, std::string& error) {
	AcquireSRWLockShared(&g_snapshot_lock);
	output = g_snapshot;
	ReleaseSRWLockShared(&g_snapshot_lock);
	if (output.module_count == 0) {
		error = "module inventory is not initialized";
		return false;
	}
	schedule_refresh();
	return true;
}

bool initialize(const std::wstring& directory, const std::wstring& client_path,
	const std::vector<riftlock_assets::AllowedModule>& allowed_modules,
	riftlock_assets::Sha256Fn sha256, Snapshot& output, std::string& error) {
	g_directory = lowercase(directory);
	g_client_path = lowercase(client_path);
	g_allowed_modules = allowed_modules;
	g_sha256 = sha256;
	wchar_t windows_path[MAX_PATH] = {};
	const UINT windows_length = GetWindowsDirectoryW(windows_path, MAX_PATH);
	if (windows_length == 0 || windows_length >= MAX_PATH) {
		error = "could not resolve the Windows module directory";
		return false;
	}
	g_windows_directory = lowercase(windows_path);
	const std::wstring windows_directory(windows_path, windows_length);
	device_form(windows_directory + L"\\System32", g_system32_device_directory);
	device_form(windows_directory + L"\\SysWOW64", g_syswow64_device_directory);
	device_form(directory, g_client_device_directory);
	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	auto register_notification = ntdll == nullptr ? nullptr :
		reinterpret_cast<LdrRegisterDllNotificationFn>(
			GetProcAddress(ntdll, "LdrRegisterDllNotification"));
	if (register_notification == nullptr ||
		register_notification(0, loader_notification, nullptr, &g_notification_cookie) < 0) {
		error = "could not register DLL load notifications";
		return false;
	}
	InterlockedExchange(&g_dirty, 1);
	return scan(output, error);
}

} // namespace riftlock_modules

#endif // RIFTLOCK_MODULES_INL
