#ifndef RIFTLOCK_HOOKS_INL
#define RIFTLOCK_HOOKS_INL

#include <windows.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace riftlock_hooks {

static const std::size_t kPrologueSize = 32;
// A HIGHLOW relocation that starts in the last three prologue bytes extends
// past the compared window; read enough live bytes to undo it completely.
static const std::size_t kPrologueReadSize = kPrologueSize + 3;
static const std::size_t kFingerprintSize = 16;

enum ScanFlags : std::uint16_t {
	kHookScanComplete = 0x0001,
};

struct Evidence {
	std::uint8_t digest[32];
	std::uint16_t mismatch_count;
	std::uint16_t checked_count;
	std::uint16_t unresolved_count;
	std::uint16_t scan_flags;
	std::uint16_t first_mismatch_target;
	std::uint16_t reserved;
	std::uint8_t first_live[kFingerprintSize];
	std::uint8_t first_disk[kFingerprintSize];
};

struct Target {
	std::uint16_t id;
	const wchar_t* module;
	const char* export_name;
};

static const Target kTargets[] = {
	{1, L"ws2_32.dll", "send"},
	{2, L"ws2_32.dll", "recv"},
	{3, L"ws2_32.dll", "WSASend"},
	{4, L"ws2_32.dll", "WSARecv"},
	{5, L"ws2_32.dll", "connect"},
	{6, L"ws2_32.dll", "closesocket"},
	{7, L"kernel32.dll", "QueryPerformanceCounter"},
	{8, L"kernel32.dll", "GetTickCount"},
	{9, L"kernel32.dll", "GetTickCount64"},
	{10, L"kernel32.dll", "Sleep"},
	{11, L"winmm.dll", "timeGetTime"},
	{12, L"ntdll.dll", "NtQueryPerformanceCounter"},
	{13, L"ntdll.dll", "NtDelayExecution"},
};

struct PeImage {
	std::vector<std::uint8_t> bytes;
	std::vector<IMAGE_SECTION_HEADER> sections;
	std::uint32_t image_base;
	std::uint32_t export_rva;
	std::uint32_t export_size;
	std::uint32_t relocation_rva;
	std::uint32_t relocation_size;
};

struct LoadedImage {
	std::wstring name;
	std::wstring path;
	HMODULE module;
	PeImage disk;
	bool valid;
};

static SRWLOCK g_snapshot_lock = SRWLOCK_INIT;
static LONG g_worker_queued = 0;
static riftlock_assets::Sha256Fn g_sha256 = nullptr;
static Evidence g_snapshot = {};

void append_u16(std::vector<std::uint8_t>& output, std::uint16_t value) {
	output.push_back(static_cast<std::uint8_t>(value & 0xff));
	output.push_back(static_cast<std::uint8_t>((value >> 8) & 0xff));
}

bool range_valid(std::size_t offset, std::size_t length, std::size_t total) {
	return offset <= total && length <= total - offset;
}

template <typename T>
bool read_object(const std::vector<std::uint8_t>& bytes, std::size_t offset, T& output) {
	if (!range_valid(offset, sizeof(T), bytes.size()))
		return false;
	memcpy(&output, bytes.data() + offset, sizeof(T));
	return true;
}

bool rva_to_offset(const PeImage& image, std::uint32_t rva, std::size_t length,
	std::size_t& output) {
	for (const IMAGE_SECTION_HEADER& section : image.sections) {
		const std::uint32_t virtual_size = (std::max)(section.Misc.VirtualSize,
			section.SizeOfRawData);
		if (rva < section.VirtualAddress || rva - section.VirtualAddress >= virtual_size)
			continue;
		const std::uint64_t raw = static_cast<std::uint64_t>(section.PointerToRawData) +
			(rva - section.VirtualAddress);
		if (raw > SIZE_MAX || !range_valid(static_cast<std::size_t>(raw), length,
			image.bytes.size()))
			return false;
		output = static_cast<std::size_t>(raw);
		return true;
	}
	return false;
}

bool load_pe(const std::wstring& path, PeImage& output) {
	std::uint64_t size = 0;
	if (!riftlock_assets::file_size(path, size) || size < sizeof(IMAGE_DOS_HEADER) ||
		size > 64ull * 1024ull * 1024ull ||
		!riftlock_assets::read_range(path, 0, size, output.bytes))
		return false;
	IMAGE_DOS_HEADER dos = {};
	if (!read_object(output.bytes, 0, dos) || dos.e_magic != IMAGE_DOS_SIGNATURE ||
		dos.e_lfanew <= 0)
		return false;
	IMAGE_NT_HEADERS32 nt = {};
	if (!read_object(output.bytes, static_cast<std::size_t>(dos.e_lfanew), nt) ||
		nt.Signature != IMAGE_NT_SIGNATURE || nt.OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
		nt.FileHeader.NumberOfSections == 0 || nt.FileHeader.NumberOfSections > 96)
		return false;
	const std::size_t section_offset = static_cast<std::size_t>(dos.e_lfanew) +
		offsetof(IMAGE_NT_HEADERS32, OptionalHeader) + nt.FileHeader.SizeOfOptionalHeader;
	const std::size_t section_bytes = static_cast<std::size_t>(
		nt.FileHeader.NumberOfSections) * sizeof(IMAGE_SECTION_HEADER);
	if (!range_valid(section_offset, section_bytes, output.bytes.size()))
		return false;
	output.sections.resize(nt.FileHeader.NumberOfSections);
	memcpy(output.sections.data(), output.bytes.data() + section_offset, section_bytes);
	output.image_base = nt.OptionalHeader.ImageBase;
	output.export_rva = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
	output.export_size = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].Size;
	output.relocation_rva = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].VirtualAddress;
	output.relocation_size = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].Size;
	return output.export_rva != 0 && output.export_size >= sizeof(IMAGE_EXPORT_DIRECTORY);
}

bool read_c_string(const PeImage& image, std::uint32_t rva, std::string& output) {
	std::size_t offset = 0;
	if (!rva_to_offset(image, rva, 1, offset))
		return false;
	const std::size_t maximum = (std::min)(image.bytes.size() - offset,
		static_cast<std::size_t>(256));
	const char* text = reinterpret_cast<const char*>(image.bytes.data() + offset);
	const std::size_t length = strnlen(text, maximum);
	if (length == maximum)
		return false;
	output.assign(text, length);
	return true;
}

bool find_export(const PeImage& image, const char* name, std::uint32_t& function_rva,
	bool& forwarded) {
	std::size_t export_offset = 0;
	IMAGE_EXPORT_DIRECTORY directory = {};
	if (!rva_to_offset(image, image.export_rva, sizeof(directory), export_offset) ||
		!read_object(image.bytes, export_offset, directory) ||
		directory.NumberOfNames > 65536 || directory.NumberOfFunctions > 65536)
		return false;
	std::size_t names_offset = 0, ordinals_offset = 0, functions_offset = 0;
	if (!rva_to_offset(image, directory.AddressOfNames,
		directory.NumberOfNames * sizeof(std::uint32_t), names_offset) ||
		!rva_to_offset(image, directory.AddressOfNameOrdinals,
			directory.NumberOfNames * sizeof(std::uint16_t), ordinals_offset) ||
		!rva_to_offset(image, directory.AddressOfFunctions,
			directory.NumberOfFunctions * sizeof(std::uint32_t), functions_offset))
		return false;
	for (std::uint32_t index = 0; index < directory.NumberOfNames; ++index) {
		std::uint32_t name_rva = 0;
		std::uint16_t ordinal = 0;
		memcpy(&name_rva, image.bytes.data() + names_offset + index * sizeof(name_rva),
			sizeof(name_rva));
		std::string current;
		if (!read_c_string(image, name_rva, current) || current != name)
			continue;
		memcpy(&ordinal, image.bytes.data() + ordinals_offset + index * sizeof(ordinal),
			sizeof(ordinal));
		if (ordinal >= directory.NumberOfFunctions)
			return false;
		memcpy(&function_rva,
			image.bytes.data() + functions_offset + ordinal * sizeof(function_rva),
			sizeof(function_rva));
		forwarded = function_rva >= image.export_rva &&
			function_rva - image.export_rva < image.export_size;
		return true;
	}
	return false;
}

bool normalize_relocations(const PeImage& image, std::uint32_t function_rva,
	std::uintptr_t loaded_base, std::uint8_t live[kPrologueReadSize]) {
	if (image.relocation_rva == 0 || image.relocation_size == 0)
		return true;
	const std::uint32_t delta = static_cast<std::uint32_t>(loaded_base - image.image_base);
	std::uint32_t consumed = 0;
	while (consumed < image.relocation_size) {
		std::size_t block_offset = 0;
		IMAGE_BASE_RELOCATION block = {};
		if (!rva_to_offset(image, image.relocation_rva + consumed, sizeof(block),
			block_offset) || !read_object(image.bytes, block_offset, block) ||
			block.SizeOfBlock < sizeof(block) || block.SizeOfBlock > image.relocation_size - consumed)
			return false;
		const std::size_t entry_count = (block.SizeOfBlock - sizeof(block)) /
			sizeof(std::uint16_t);
		if (!range_valid(block_offset + sizeof(block), entry_count * sizeof(std::uint16_t),
			image.bytes.size()))
			return false;
		for (std::size_t index = 0; index < entry_count; ++index) {
			std::uint16_t entry = 0;
			memcpy(&entry, image.bytes.data() + block_offset + sizeof(block) +
				index * sizeof(entry), sizeof(entry));
			const std::uint16_t type = entry >> 12;
			const std::uint32_t rva = block.VirtualAddress + (entry & 0x0fff);
			if (rva < function_rva || rva - function_rva >= kPrologueSize)
				continue;
			if (type == IMAGE_REL_BASED_ABSOLUTE)
				continue;
			if (type != IMAGE_REL_BASED_HIGHLOW)
				return false;
			std::uint32_t value = 0;
			const std::size_t offset = rva - function_rva;
			memcpy(&value, live + offset, sizeof(value));
			value -= delta;
			memcpy(live + offset, &value, sizeof(value));
		}
		consumed += block.SizeOfBlock;
	}
	return true;
}

LoadedImage* loaded_image(std::vector<LoadedImage>& images, const wchar_t* name) {
	for (LoadedImage& image : images) {
		if (_wcsicmp(image.name.c_str(), name) == 0)
			return &image;
	}
	LoadedImage image = {};
	image.name = name;
	image.module = GetModuleHandleW(name);
	if (image.module != nullptr) {
		wchar_t path[MAX_PATH] = {};
		const DWORD length = GetModuleFileNameW(image.module, path, MAX_PATH);
		wchar_t windows_path[MAX_PATH] = {};
		const UINT windows_length = GetWindowsDirectoryW(windows_path, MAX_PATH);
		if (length != 0 && length < MAX_PATH && windows_length != 0 &&
			windows_length < MAX_PATH && riftlock_modules::path_is_under(
				riftlock_modules::lowercase(path), riftlock_modules::lowercase(windows_path))) {
			image.path = path;
			image.valid = load_pe(image.path, image.disk);
		}
	}
	images.push_back(std::move(image));
	return &images.back();
}

bool scan(Evidence& output, std::string& error) {
	if (g_sha256 == nullptr) {
		error = "hook evidence hashing is not initialized";
		return false;
	}
	Evidence result = {};
	std::vector<LoadedImage> images;
	std::vector<std::uint8_t> material;
	for (const Target& target : kTargets) {
		LoadedImage* image = loaded_image(images, target.module);
		std::uint8_t live[kPrologueSize] = {};
		std::uint8_t disk[kPrologueSize] = {};
		std::uint8_t status = 0;
		bool mismatch = false;
		std::uint32_t function_rva = 0;
		bool forwarded = false;
		if (image == nullptr || !image->valid ||
			!find_export(image->disk, target.export_name, function_rva, forwarded) || forwarded) {
			status = 2;
		} else {
			std::size_t disk_offset = 0;
			const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(image->module);
			SIZE_T bytes_read = 0;
			std::uint8_t live_read[kPrologueReadSize] = {};
			if (!rva_to_offset(image->disk, function_rva, sizeof(disk), disk_offset) ||
				!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(base + function_rva),
					live_read, sizeof(live_read), &bytes_read) || bytes_read != sizeof(live_read)) {
				status = 2;
			} else {
				memcpy(live, live_read, sizeof(live));
				memcpy(disk, image->disk.bytes.data() + disk_offset, sizeof(disk));
				std::uint8_t normalized[kPrologueReadSize] = {};
				memcpy(normalized, live_read, sizeof(normalized));
				const FARPROC resolved = GetProcAddress(image->module, target.export_name);
				if (!normalize_relocations(image->disk, function_rva, base, normalized)) {
					status = 2;
				} else {
					status = 1;
					mismatch = memcmp(normalized, disk, sizeof(disk)) != 0 ||
						reinterpret_cast<std::uintptr_t>(resolved) != base + function_rva;
				}
			}
		}
		append_u16(material, target.id);
		material.push_back(status);
		material.push_back(mismatch ? 1 : 0);
		material.insert(material.end(), live, live + sizeof(live));
		material.insert(material.end(), disk, disk + sizeof(disk));
		if (status == 2) {
			if (result.unresolved_count != UINT16_MAX)
				++result.unresolved_count;
			continue;
		}
		if (result.checked_count != UINT16_MAX)
			++result.checked_count;
		if (!mismatch)
			continue;
		if (result.mismatch_count == 0) {
			result.first_mismatch_target = target.id;
			memcpy(result.first_live, live, sizeof(result.first_live));
			memcpy(result.first_disk, disk, sizeof(result.first_disk));
		}
		if (result.mismatch_count != UINT16_MAX)
			++result.mismatch_count;
	}
	result.scan_flags = kHookScanComplete;
	if (g_sha256(result.digest, material.data(),
		static_cast<unsigned long long>(material.size())) != 0) {
		error = "could not hash hook evidence";
		return false;
	}
	output = result;
	return true;
}

DWORD WINAPI refresh_worker(LPVOID) {
	Evidence result = {};
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

bool initialize(riftlock_assets::Sha256Fn sha256, Evidence& output, std::string& error) {
	g_sha256 = sha256;
	if (!scan(output, error))
		return false;
	AcquireSRWLockExclusive(&g_snapshot_lock);
	g_snapshot = output;
	ReleaseSRWLockExclusive(&g_snapshot_lock);
	schedule_refresh();
	return true;
}

bool refresh(Evidence& output, std::string& error) {
	AcquireSRWLockShared(&g_snapshot_lock);
	output = g_snapshot;
	ReleaseSRWLockShared(&g_snapshot_lock);
	if ((output.scan_flags & kHookScanComplete) == 0) {
		error = "hook evidence is not initialized";
		return false;
	}
	schedule_refresh();
	return true;
}

} // namespace riftlock_hooks

#endif // RIFTLOCK_HOOKS_INL
