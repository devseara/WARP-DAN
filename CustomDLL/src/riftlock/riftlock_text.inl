#ifndef RIFTLOCK_TEXT_INL
#define RIFTLOCK_TEXT_INL

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace riftlock_text {

static const std::size_t kSliceSize = 256;
static const std::size_t kSlicesPerModule = 8;

struct Baseline {
	HMODULE module;
	std::uint8_t kind;
	std::uint32_t text_rva;
	std::vector<std::uint8_t> text;
};

struct Evidence {
	std::uint8_t digest[32];
	std::uint16_t mismatch_count;
	std::uint16_t slice_count;
	std::uint32_t checked_bytes;
	std::uint32_t first_mismatch_offset;
	std::uint8_t first_mismatch_module;
	std::uint8_t reserved[3];
};

static std::vector<Baseline> g_baselines;

bool capture(HMODULE module, std::uint8_t kind, Baseline& output) {
	if (module == nullptr)
		return false;
	const std::uint8_t* base = reinterpret_cast<const std::uint8_t*>(module);
	SIZE_T bytes_read = 0;
	IMAGE_DOS_HEADER dos = {};
	if (!ReadProcessMemory(GetCurrentProcess(), base, &dos, sizeof(dos), &bytes_read) ||
		bytes_read != sizeof(dos) || dos.e_magic != IMAGE_DOS_SIGNATURE || dos.e_lfanew <= 0)
		return false;
	IMAGE_NT_HEADERS32 nt = {};
	if (!ReadProcessMemory(GetCurrentProcess(), base + dos.e_lfanew, &nt, sizeof(nt), &bytes_read) ||
		bytes_read != sizeof(nt) || nt.Signature != IMAGE_NT_SIGNATURE ||
		nt.FileHeader.NumberOfSections == 0 || nt.FileHeader.NumberOfSections > 96)
		return false;
	IMAGE_SECTION_HEADER sections[96] = {};
	const std::uintptr_t section_address = reinterpret_cast<std::uintptr_t>(base) +
		dos.e_lfanew + offsetof(IMAGE_NT_HEADERS32, OptionalHeader) + nt.FileHeader.SizeOfOptionalHeader;
	const SIZE_T section_bytes = static_cast<SIZE_T>(nt.FileHeader.NumberOfSections) *
		sizeof(IMAGE_SECTION_HEADER);
	if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(section_address),
		sections, section_bytes, &bytes_read) || bytes_read != section_bytes)
		return false;
	for (std::uint16_t index = 0; index < nt.FileHeader.NumberOfSections; ++index) {
			if (memcmp(sections[index].Name, ".text", 5) != 0)
				continue;
			const std::uint32_t virtual_size = sections[index].Misc.VirtualSize;
			const std::uint32_t virtual_address = sections[index].VirtualAddress;
			if (virtual_size == 0 || virtual_address >= nt.OptionalHeader.SizeOfImage ||
				virtual_size > nt.OptionalHeader.SizeOfImage - virtual_address)
				return false;
			Baseline baseline = {};
			baseline.module = module;
			baseline.kind = kind;
			baseline.text_rva = virtual_address;
			baseline.text.resize(virtual_size);
			if (!ReadProcessMemory(GetCurrentProcess(), base + virtual_address,
				baseline.text.data(), virtual_size, &bytes_read) || bytes_read != virtual_size)
				return false;
			output = std::move(baseline);
			return true;
	}
	return false;
}

bool initialize(HMODULE executable, HMODULE riftlock_module, std::string& error) {
	Baseline exe = {};
	Baseline dll = {};
	if (!capture(executable, 1, exe) || !capture(riftlock_module, 2, dll)) {
		error = "could not capture executable code baselines";
		return false;
	}
	g_baselines.clear();
	g_baselines.push_back(std::move(exe));
	g_baselines.push_back(std::move(dll));
	return true;
}

void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
	for (unsigned int shift = 0; shift < 32; shift += 8)
		output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xff));
}

bool sample(const std::uint8_t seed[32], riftlock_assets::Sha256Fn sha256,
	Evidence& output, std::string& error) {
	if (seed == nullptr || sha256 == nullptr || g_baselines.size() != 2) {
		error = "code baseline sampling is not initialized";
		return false;
	}
	Evidence result = {};
	std::vector<std::uint8_t> material;
	for (const Baseline& baseline : g_baselines) {
		if (baseline.text.empty())
			continue;
		const std::size_t slice_size = baseline.text.size() < kSliceSize ?
			baseline.text.size() : kSliceSize;
		for (std::size_t index = 0; index < kSlicesPerModule; ++index) {
			std::uint8_t selector_input[34] = {};
			std::uint8_t selector_digest[32] = {};
			memcpy(selector_input, seed, 32);
			selector_input[32] = baseline.kind;
			selector_input[33] = static_cast<std::uint8_t>(index);
			if (sha256(selector_digest, selector_input, sizeof(selector_input)) != 0) {
				error = "could not select code integrity slices";
				return false;
			}
			std::uint32_t selector = 0;
			memcpy(&selector, selector_digest, sizeof(selector));
			const std::size_t available = baseline.text.size() - slice_size;
			std::size_t offset = available == 0 ? 0 : selector % (available + 1);
			offset &= ~static_cast<std::size_t>(0x0f);
			std::vector<std::uint8_t> current(slice_size);
			SIZE_T bytes_read = 0;
			const std::uint8_t* current_address =
				reinterpret_cast<const std::uint8_t*>(baseline.module) + baseline.text_rva + offset;
			if (!ReadProcessMemory(GetCurrentProcess(), current_address, current.data(),
				slice_size, &bytes_read) || bytes_read != slice_size) {
				error = "could not read an in-memory code slice";
				return false;
			}
			const bool mismatch = memcmp(current.data(), baseline.text.data() + offset, slice_size) != 0;
			material.push_back(baseline.kind);
			append_u32(material, static_cast<std::uint32_t>(offset));
			material.insert(material.end(), current.begin(), current.end());
			if (mismatch) {
				if (result.mismatch_count == 0) {
					result.first_mismatch_module = baseline.kind;
					result.first_mismatch_offset = static_cast<std::uint32_t>(offset);
				}
				if (result.mismatch_count != UINT16_MAX)
					++result.mismatch_count;
			}
			if (result.slice_count != UINT16_MAX)
				++result.slice_count;
			result.checked_bytes += static_cast<std::uint32_t>(slice_size);
		}
	}
	const std::uint8_t empty = 0;
	const std::uint8_t* bytes = material.empty() ? &empty : material.data();
	if (sha256(result.digest, bytes, static_cast<unsigned long long>(material.size())) != 0) {
		error = "could not hash code integrity samples";
		return false;
	}
	output = result;
	return true;
}

} // namespace riftlock_text

#endif // RIFTLOCK_TEXT_INL
