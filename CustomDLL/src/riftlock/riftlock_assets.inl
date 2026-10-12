#ifndef RIFTLOCK_ASSETS_INL
#define RIFTLOCK_ASSETS_INL

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cwctype>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace riftlock_assets {

using Sha256Fn = int (__cdecl *)(unsigned char*, const unsigned char*, unsigned long long);

static const wchar_t kManifestName[] = L"riftlock-assets-v1.txt";
static const std::uint64_t kMaximumRangeSize = 256ull * 1024ull * 1024ull;

struct LooseRecord {
	char kind;
	std::string path;
	std::uint64_t size;
};

struct AllowedModule {
	std::wstring name;
	std::uint64_t size;
	std::uint8_t digest[32];
};

struct ChallengeRecord {
	std::uint8_t kind;
	std::wstring path;
	std::uint64_t offset;
	std::uint64_t length;
	std::uint8_t expected_digest[32];
	bool whole_file;
};

struct ChallengeEvidence {
	std::uint8_t digest[32];
	std::uint16_t mismatch_count;
	std::uint16_t module_sample_count;
	std::uint16_t grf_sample_count;
	std::uint16_t loose_sample_count;
	std::uint32_t checked_bytes;
	std::uint32_t first_mismatch_index;
	std::uint8_t first_mismatch_kind;
	std::uint8_t reserved[3];
};

static const std::size_t kModuleChallengeSamples = 2;
static const std::size_t kGrfChallengeSamples = 4;
static const std::size_t kLooseChallengeSamples = 4;
static std::vector<ChallengeRecord> g_module_challenge_records;
static std::vector<ChallengeRecord> g_grf_challenge_records;
static std::vector<ChallengeRecord> g_loose_challenge_records;

void set_error(std::string& error, const char* message) {
	error = message != nullptr ? message : "asset verification failed";
}

std::uint32_t read_u32(const std::uint8_t* bytes) {
	std::uint32_t value = 0;
	memcpy(&value, bytes, sizeof(value));
	return value;
}

void append_u64(std::vector<std::uint8_t>& output, std::uint64_t value) {
	for (unsigned int shift = 0; shift < 64; shift += 8)
		output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xff));
}

void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
	for (unsigned int shift = 0; shift < 32; shift += 8)
		output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xff));
}

bool parse_u64(const std::string& text, std::uint64_t& value) {
	if (text.empty())
		return false;
	char* end = nullptr;
	const unsigned long long parsed = _strtoui64(text.c_str(), &end, 10);
	if (end == text.c_str() || end == nullptr || *end != '\0')
		return false;
	value = static_cast<std::uint64_t>(parsed);
	return true;
}

bool parse_hex_digest(const std::string& text, std::uint8_t output[32]) {
	if (text.size() != 64)
		return false;
	for (std::size_t index = 0; index < 32; ++index) {
		unsigned int value = 0;
		if (sscanf_s(text.substr(index * 2, 2).c_str(), "%2x", &value) != 1)
			return false;
		output[index] = static_cast<std::uint8_t>(value);
	}
	return true;
}

bool parse_hex_bytes(const std::string& text, std::string& output) {
	if ((text.size() & 1u) != 0)
		return false;
	output.clear();
	output.reserve(text.size() / 2);
	for (std::size_t index = 0; index < text.size(); index += 2) {
		unsigned int value = 0;
		if (sscanf_s(text.substr(index, 2).c_str(), "%2x", &value) != 1)
			return false;
		output.push_back(static_cast<char>(value));
	}
	return true;
}

std::vector<std::string> split(const std::string& input, char delimiter) {
	std::vector<std::string> fields;
	std::size_t start = 0;
	for (;;) {
		const std::size_t position = input.find(delimiter, start);
		fields.push_back(input.substr(start, position == std::string::npos ? position : position - start));
		if (position == std::string::npos)
			break;
		start = position + 1;
	}
	return fields;
}

bool utf8_to_wide(const std::string& input, std::wstring& output) {
	if (input.empty())
		return false;
	const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
		input.data(), static_cast<int>(input.size()), nullptr, 0);
	if (length <= 0)
		return false;
	output.resize(static_cast<std::size_t>(length));
	return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
		input.data(), static_cast<int>(input.size()), &output[0], length) == length;
}

bool wide_to_utf8(const std::wstring& input, std::string& output) {
	if (input.empty()) {
		output.clear();
		return true;
	}
	const int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
		input.data(), static_cast<int>(input.size()), nullptr, 0, nullptr, nullptr);
	if (length <= 0)
		return false;
	output.resize(static_cast<std::size_t>(length));
	return WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
		input.data(), static_cast<int>(input.size()), &output[0], length, nullptr, nullptr) == length;
}

bool safe_relative_path(const std::wstring& path) {
	if (path.empty() || path[0] == L'\\' || path[0] == L'/' || path.find(L':') != std::wstring::npos)
		return false;
	std::size_t start = 0;
	while (start <= path.size()) {
		const std::size_t end = path.find_first_of(L"\\/", start);
		const std::wstring component = path.substr(start,
			end == std::wstring::npos ? std::wstring::npos : end - start);
		if (component.empty() || component == L"." || component == L"..")
			return false;
		if (end == std::wstring::npos)
			break;
		start = end + 1;
	}
	return true;
}

std::wstring join_path(const std::wstring& base, const std::wstring& relative) {
	if (base.empty())
		return relative;
	return base + L"\\" + relative;
}

bool file_size(const std::wstring& path, std::uint64_t& output) {
	WIN32_FILE_ATTRIBUTE_DATA attributes = {};
	if (!GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &attributes) ||
		(attributes.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0)
		return false;
	output = (static_cast<std::uint64_t>(attributes.nFileSizeHigh) << 32) |
		attributes.nFileSizeLow;
	return true;
}

bool read_range(const std::wstring& path, std::uint64_t offset, std::uint64_t length,
	std::vector<std::uint8_t>& output) {
	if (length > kMaximumRangeSize || length > static_cast<std::uint64_t>(SIZE_MAX))
		return false;
	HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ,
		nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
	if (file == INVALID_HANDLE_VALUE)
		return false;
	LARGE_INTEGER size = {};
	bool ok = GetFileSizeEx(file, &size) != FALSE && offset <= static_cast<std::uint64_t>(size.QuadPart) &&
		length <= static_cast<std::uint64_t>(size.QuadPart) - offset;
	LARGE_INTEGER position = {};
	position.QuadPart = static_cast<LONGLONG>(offset);
	if (ok)
		ok = SetFilePointerEx(file, position, nullptr, FILE_BEGIN) != FALSE;
	output.resize(ok ? static_cast<std::size_t>(length) : 0);
	std::size_t consumed = 0;
	while (ok && consumed < output.size()) {
		const DWORD request = static_cast<DWORD>(std::min<std::size_t>(output.size() - consumed, 1024 * 1024));
		DWORD read = 0;
		ok = ReadFile(file, output.data() + consumed, request, &read, nullptr) != FALSE && read == request;
		consumed += read;
	}
	CloseHandle(file);
	return ok;
}

bool hash_range(const std::wstring& path, std::uint64_t offset, std::uint64_t length,
	Sha256Fn sha256, std::uint8_t output[32]) {
	std::vector<std::uint8_t> bytes;
	if (!read_range(path, offset, length, bytes))
		return false;
	const std::uint8_t empty = 0;
	const std::uint8_t* data = bytes.empty() ? &empty : bytes.data();
	return sha256(output, data, static_cast<unsigned long long>(bytes.size())) == 0;
}

bool equal_digest(const std::uint8_t left[32], const std::uint8_t right[32]) {
	std::uint8_t difference = 0;
	for (std::size_t index = 0; index < 32; ++index)
		difference |= left[index] ^ right[index];
	return difference == 0;
}

bool verify_hash(const std::wstring& path, std::uint64_t offset, std::uint64_t length,
	const std::string& expected_hex, Sha256Fn sha256) {
	std::uint8_t expected[32] = {};
	std::uint8_t actual[32] = {};
	return parse_hex_digest(expected_hex, expected) &&
		hash_range(path, offset, length, sha256, actual) && equal_digest(expected, actual);
}

bool verify_file(const std::wstring& path, std::uint64_t expected_size,
	const std::string& expected_hex, Sha256Fn sha256) {
	std::uint64_t actual_size = 0;
	return file_size(path, actual_size) && actual_size == expected_size &&
		verify_hash(path, 0, actual_size, expected_hex, sha256);
}

bool select_challenge_index(const std::uint8_t seed[32], std::uint8_t kind,
	std::uint8_t ordinal, std::size_t record_count, const std::vector<std::size_t>& used,
	Sha256Fn sha256, std::size_t& output) {
	if (record_count == 0 || record_count > UINT32_MAX)
		return false;
	std::uint8_t selector_input[34] = {};
	std::uint8_t selector_digest[32] = {};
	memcpy(selector_input, seed, 32);
	selector_input[32] = kind;
	selector_input[33] = ordinal;
	if (sha256(selector_digest, selector_input, sizeof(selector_input)) != 0)
		return false;
	std::uint32_t selector = 0;
	memcpy(&selector, selector_digest, sizeof(selector));
	output = selector % record_count;
	while (std::find(used.begin(), used.end(), output) != used.end())
		output = (output + 1) % record_count;
	return true;
}

bool sample_challenge_group(const std::uint8_t seed[32], std::uint8_t kind,
	const std::vector<ChallengeRecord>& records, std::size_t requested, Sha256Fn sha256,
	ChallengeEvidence& result, std::vector<std::uint8_t>& material, std::string& error) {
	const std::size_t count = (std::min)(requested, records.size());
	std::vector<std::size_t> used;
	used.reserve(count);
	for (std::size_t ordinal = 0; ordinal < count; ++ordinal) {
		std::size_t index = 0;
		if (!select_challenge_index(seed, kind, static_cast<std::uint8_t>(ordinal),
			records.size(), used, sha256, index)) {
			set_error(error, "could not select asset challenge records");
			return false;
		}
		used.push_back(index);
		const ChallengeRecord& record = records[index];
		std::uint64_t actual_size = 0;
		std::uint8_t actual_digest[32] = {};
		const bool size_valid = file_size(record.path, actual_size) &&
			(record.whole_file ? actual_size == record.length :
				record.offset <= actual_size && record.length <= actual_size - record.offset);
		const bool read_valid = size_valid && hash_range(record.path, record.offset,
			record.length, sha256, actual_digest);
		const bool mismatch = !read_valid ||
			!equal_digest(record.expected_digest, actual_digest);
		material.push_back(kind);
		append_u32(material, static_cast<std::uint32_t>(index));
		append_u64(material, record.length);
		material.push_back(read_valid ? 1 : 0);
		material.insert(material.end(), actual_digest, actual_digest + sizeof(actual_digest));
		if (mismatch) {
			if (result.mismatch_count == 0) {
				result.first_mismatch_kind = kind;
				result.first_mismatch_index = static_cast<std::uint32_t>(index);
			}
			if (result.mismatch_count != UINT16_MAX)
				++result.mismatch_count;
		}
		if (read_valid) {
			const std::uint64_t total = static_cast<std::uint64_t>(result.checked_bytes) +
				record.length;
			result.checked_bytes = total > UINT32_MAX ? UINT32_MAX :
				static_cast<std::uint32_t>(total);
		}
		if (kind == 1 && result.module_sample_count != UINT16_MAX)
			++result.module_sample_count;
		else if (kind == 2 && result.grf_sample_count != UINT16_MAX)
			++result.grf_sample_count;
		else if (kind == 3 && result.loose_sample_count != UINT16_MAX)
			++result.loose_sample_count;
	}
	return true;
}

bool sample_challenge(const std::uint8_t seed[32], Sha256Fn sha256,
	ChallengeEvidence& output, std::string& error) {
	if (seed == nullptr || sha256 == nullptr) {
		set_error(error, "asset challenge sampling is not initialized");
		return false;
	}
	ChallengeEvidence result = {};
	std::vector<std::uint8_t> material;
	if (!sample_challenge_group(seed, 1, g_module_challenge_records,
		kModuleChallengeSamples, sha256, result, material, error) ||
		!sample_challenge_group(seed, 2, g_grf_challenge_records,
			kGrfChallengeSamples, sha256, result, material, error) ||
		!sample_challenge_group(seed, 3, g_loose_challenge_records,
			kLooseChallengeSamples, sha256, result, material, error))
		return false;
	const std::uint8_t empty = 0;
	const std::uint8_t* bytes = material.empty() ? &empty : material.data();
	if (sha256(result.digest, bytes, static_cast<unsigned long long>(material.size())) != 0) {
		set_error(error, "could not hash asset challenge samples");
		return false;
	}
	output = result;
	return true;
}

bool verify_loader_marker(const std::wstring& client_path, const std::string& expected) {
	static const char prefix[] = "RIFTLOCK_GRFS_V1|";
	std::uint64_t size = 0;
	std::vector<std::uint8_t> image;
	if (expected.compare(0, sizeof(prefix) - 1, prefix) != 0 || expected.size() > 4096 ||
		!file_size(client_path, size) || size == 0 || size > 128ull * 1024ull * 1024ull ||
		!read_range(client_path, 0, size, image))
		return false;
	std::size_t matches = 0;
	std::string actual;
	for (std::size_t index = 0; index + sizeof(prefix) - 1 <= image.size(); ++index) {
		if (memcmp(image.data() + index, prefix, sizeof(prefix) - 1) != 0)
			continue;
		++matches;
		std::size_t end = index;
		while (end < image.size() && image[end] != 0 && end - index <= 4096)
			++end;
		if (end >= image.size() || end - index > 4096)
			return false;
		actual.assign(reinterpret_cast<const char*>(image.data() + index), end - index);
	}
	return matches == 1 && actual == expected;
}

bool verify_grf(const std::wstring& path, const std::vector<std::string>& fields,
	Sha256Fn sha256) {
	std::uint64_t expected_size = 0, expected_version = 0, expected_table_offset = 0;
	std::uint64_t expected_compressed = 0, expected_uncompressed = 0, actual_size = 0;
	if (fields.size() != 7 || !parse_u64(fields[1], expected_size) ||
		!parse_u64(fields[2], expected_version) || !parse_u64(fields[3], expected_table_offset) ||
		!parse_u64(fields[4], expected_compressed) || !parse_u64(fields[5], expected_uncompressed) ||
		!file_size(path, actual_size) || actual_size != expected_size)
		return false;
	std::vector<std::uint8_t> header;
	if (!read_range(path, 0, 46, header) || header.size() != 46)
		return false;
	const bool known_magic = memcmp(header.data(), "Master of Magic", 15) == 0 ||
		memcmp(header.data(), "Event Horizon", 13) == 0;
	const std::uint32_t version = read_u32(header.data() + 42);
	const std::uint64_t table_offset = 46ull + read_u32(header.data() + 30);
	if (!known_magic || version != expected_version || table_offset != expected_table_offset ||
		(version != 0x200 && version != 0x300))
		return false;
	const std::uint64_t table_header_size = version == 0x300 ? 12 : 8;
	std::vector<std::uint8_t> table_header;
	if (!read_range(path, table_offset, table_header_size, table_header))
		return false;
	const std::size_t size_offset = version == 0x300 ? 4 : 0;
	if (version == 0x300 && read_u32(table_header.data()) != 0)
		return false;
	const std::uint32_t compressed = read_u32(table_header.data() + size_offset);
	const std::uint32_t uncompressed = read_u32(table_header.data() + size_offset + 4);
	return compressed == expected_compressed && uncompressed == expected_uncompressed &&
		verify_hash(path, table_offset + table_header_size, compressed, fields[6], sha256);
}

bool enumerate_loose(const std::wstring& current, const std::wstring& relative,
	std::vector<LooseRecord>& records,
	std::uint64_t& file_count, std::uint64_t& reparse_count) {
	const std::wstring search = join_path(current, L"*");
	WIN32_FIND_DATAW data = {};
	HANDLE handle = FindFirstFileW(search.c_str(), &data);
	if (handle == INVALID_HANDLE_VALUE)
		return GetLastError() == ERROR_FILE_NOT_FOUND;
	bool ok = true;
	do {
		if (wcscmp(data.cFileName, L".") == 0 || wcscmp(data.cFileName, L"..") == 0)
			continue;
		const std::wstring child_relative = relative.empty() ? data.cFileName : relative + L"/" + data.cFileName;
		const std::wstring child_path = join_path(current, data.cFileName);
		if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
			if ((data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
				std::string utf8;
				if (!wide_to_utf8(child_relative, utf8)) {
					ok = false;
					break;
				}
				records.push_back({'R', utf8, 0});
				++reparse_count;
			} else if (!enumerate_loose(child_path, child_relative, records, file_count, reparse_count)) {
				ok = false;
				break;
			}
		} else if ((data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0) {
			std::string utf8;
			if (!wide_to_utf8(child_relative, utf8)) {
				ok = false;
				break;
			}
			const std::uint64_t size = (static_cast<std::uint64_t>(data.nFileSizeHigh) << 32) |
				data.nFileSizeLow;
			records.push_back({'F', utf8, size});
			++file_count;
		}
	} while (FindNextFileW(handle, &data) != FALSE);
	const DWORD final_error = GetLastError();
	FindClose(handle);
	return ok && (final_error == ERROR_NO_MORE_FILES || final_error == ERROR_SUCCESS);
}

bool verify_loose_tree(const std::wstring& directory, std::uint64_t expected_files,
	std::uint64_t expected_reparse, const std::string& expected_hex, Sha256Fn sha256) {
	const std::wstring data_root = join_path(directory, L"data");
	std::vector<LooseRecord> records;
	std::uint64_t files = 0, reparse = 0;
	const DWORD attributes = GetFileAttributesW(data_root.c_str());
	if (attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
		if (!enumerate_loose(data_root, L"", records, files, reparse))
			return false;
	}
	if (files != expected_files || reparse != expected_reparse)
		return false;
	std::sort(records.begin(), records.end(), [](const LooseRecord& left, const LooseRecord& right) {
		if (left.kind != right.kind)
			return left.kind < right.kind;
		return left.path < right.path;
	});
	std::vector<std::uint8_t> material;
	for (const LooseRecord& record : records) {
		material.push_back(static_cast<std::uint8_t>(record.kind));
		material.insert(material.end(), record.path.begin(), record.path.end());
		material.push_back(0);
		if (record.kind == 'F')
			append_u64(material, record.size);
	}
	std::uint8_t expected[32] = {};
	std::uint8_t actual[32] = {};
	const std::uint8_t empty = 0;
	const std::uint8_t* bytes = material.empty() ? &empty : material.data();
	return parse_hex_digest(expected_hex, expected) &&
		sha256(actual, bytes, static_cast<unsigned long long>(material.size())) == 0 &&
		equal_digest(expected, actual);
}

bool verify(const std::wstring& directory, const std::wstring& client_path, Sha256Fn sha256,
	std::uint8_t manifest_digest[32], std::vector<AllowedModule>& allowed_modules,
	std::string& error) {
	if (directory.empty() || client_path.empty() || sha256 == nullptr) {
		set_error(error, "asset verifier is missing its runtime dependencies");
		return false;
	}
	const std::wstring manifest_path = join_path(directory, kManifestName);
	std::uint64_t manifest_size = 0;
	if (!file_size(manifest_path, manifest_size) || manifest_size == 0 || manifest_size > 16 * 1024 * 1024 ||
		!hash_range(manifest_path, 0, manifest_size, sha256, manifest_digest)) {
		set_error(error, "riftlock-assets-v1.txt is missing or unreadable");
		return false;
	}
	std::vector<std::uint8_t> manifest_bytes;
	if (!read_range(manifest_path, 0, manifest_size, manifest_bytes)) {
		set_error(error, "could not read the asset manifest");
		return false;
	}
	const std::string manifest(reinterpret_cast<const char*>(manifest_bytes.data()), manifest_bytes.size());
	allowed_modules.clear();
	std::vector<ChallengeRecord> module_challenge_records;
	std::vector<ChallengeRecord> grf_challenge_records;
	std::vector<ChallengeRecord> loose_challenge_records;
	bool format_seen = false, loader_seen = false, module_seen = false;
	bool grf_seen = false, loose_tree_seen = false;
	std::size_t start = 0;
	while (start < manifest.size()) {
		const std::size_t end = manifest.find('\n', start);
		std::string line = manifest.substr(start, end == std::string::npos ? end : end - start);
		if (!line.empty() && line.back() == '\r')
			line.pop_back();
		start = end == std::string::npos ? manifest.size() : end + 1;
		if (line.empty())
			continue;
		if (line == "format=riftlock-assets-v1") {
			if (format_seen) {
				set_error(error, "duplicate asset manifest format");
				return false;
			}
			format_seen = true;
			continue;
		}
		const std::size_t equals = line.find('=');
		if (equals == std::string::npos) {
			set_error(error, "malformed asset manifest line");
			return false;
		}
		const std::string type = line.substr(0, equals);
		const std::vector<std::string> fields = split(line.substr(equals + 1), '|');
		if (type == "loader") {
			std::string marker;
			if (fields.size() != 1 || !parse_hex_bytes(fields[0], marker) ||
				!verify_loader_marker(client_path, marker)) {
				set_error(error, "client GRF loader marker mismatch");
				return false;
			}
			loader_seen = true;
		} else if (type == "module") {
			std::string name_utf8;
			std::wstring name;
			std::uint64_t size = 0;
			AllowedModule module = {};
			if (fields.size() != 3 || !parse_hex_bytes(fields[0], name_utf8) ||
				!utf8_to_wide(name_utf8, name) || !safe_relative_path(name) ||
				name.find_first_of(L"\\/") != std::wstring::npos || !parse_u64(fields[1], size) ||
				!parse_hex_digest(fields[2], module.digest) ||
				!verify_file(join_path(directory, name), size, fields[2], sha256)) {
				set_error(error, "allowed module mismatch");
				return false;
			}
			for (wchar_t& character : name)
				character = static_cast<wchar_t>(std::towlower(character));
			module.name = name;
			module.size = size;
			allowed_modules.push_back(module);
			ChallengeRecord challenge_record = {};
			challenge_record.kind = 1;
			challenge_record.path = join_path(directory, name);
			challenge_record.length = size;
			challenge_record.whole_file = true;
			memcpy(challenge_record.expected_digest, module.digest,
				sizeof(challenge_record.expected_digest));
			module_challenge_records.push_back(challenge_record);
			module_seen = true;
		} else if (type == "loose_sample") {
			if (fields.size() != 3) {
				set_error(error, "malformed loose challenge record");
				return false;
			}
			std::string path_utf8;
			std::wstring relative;
			std::uint64_t size = 0;
			ChallengeRecord challenge_record = {};
			if (!parse_hex_bytes(fields[0], path_utf8) ||
				!utf8_to_wide(path_utf8, relative) || !safe_relative_path(relative) ||
				!parse_u64(fields[1], size) ||
				!parse_hex_digest(fields[2], challenge_record.expected_digest)) {
				set_error(error, "invalid loose challenge record");
				return false;
			}
			challenge_record.kind = 3;
			challenge_record.path = join_path(join_path(directory, L"data"), relative);
			challenge_record.length = size;
			challenge_record.whole_file = true;
			loose_challenge_records.push_back(challenge_record);
		} else if (type == "file" || type == "loose") {
			if (fields.size() != 3) {
				set_error(error, "malformed asset file record");
				return false;
			}
			std::string path_utf8;
			std::wstring relative;
			std::uint64_t size = 0;
			if (!parse_hex_bytes(fields[0], path_utf8) || !utf8_to_wide(path_utf8, relative) ||
				!safe_relative_path(relative) || !parse_u64(fields[1], size)) {
				set_error(error, "invalid asset file path");
				return false;
			}
			const std::wstring base = type == "loose" ? join_path(directory, L"data") : directory;
			if (!verify_file(join_path(base, relative), size, fields[2], sha256)) {
				set_error(error, type == "loose" ? "critical loose-data file mismatch" : "critical client file mismatch");
				return false;
			}
		} else if (type == "grf") {
			if (fields.size() != 7) {
				set_error(error, "malformed GRF record");
				return false;
			}
			std::wstring relative;
			if (!utf8_to_wide(fields[0], relative) || !safe_relative_path(relative) ||
				!verify_grf(join_path(directory, relative), fields, sha256)) {
				error = "GRF table mismatch: " + fields[0];
				return false;
			}
			grf_seen = true;
		} else if (type == "entry") {
			if (fields.size() != 5) {
				set_error(error, "malformed GRF entry record");
				return false;
			}
			std::wstring relative;
			std::uint64_t offset = 0, length = 0;
			ChallengeRecord challenge_record = {};
			if (!utf8_to_wide(fields[0], relative) || !safe_relative_path(relative) ||
				!parse_u64(fields[1], offset) || !parse_u64(fields[2], length) ||
				!parse_hex_digest(fields[3], challenge_record.expected_digest) ||
				!verify_hash(join_path(directory, relative), offset, length, fields[3], sha256)) {
				error = "critical GRF entry mismatch: " + fields[0];
				return false;
			}
			challenge_record.kind = 2;
			challenge_record.path = join_path(directory, relative);
			challenge_record.offset = offset;
			challenge_record.length = length;
			challenge_record.whole_file = false;
			grf_challenge_records.push_back(challenge_record);
		} else if (type == "loose_tree") {
			std::uint64_t files = 0, reparse = 0;
			if (fields.size() != 3 || !parse_u64(fields[0], files) || !parse_u64(fields[1], reparse) ||
				!verify_loose_tree(directory, files, reparse, fields[2], sha256)) {
				set_error(error, "loose-data tree mismatch");
				return false;
			}
			loose_tree_seen = true;
		} else {
			set_error(error, "unknown asset manifest record");
			return false;
		}
	}
	if (!format_seen || !loader_seen || !module_seen || !grf_seen || !loose_tree_seen) {
		set_error(error, "asset manifest is incomplete");
		return false;
	}
	g_module_challenge_records.swap(module_challenge_records);
	g_grf_challenge_records.swap(grf_challenge_records);
	g_loose_challenge_records.swap(loose_challenge_records);
	return true;
}

} // namespace riftlock_assets

#endif // RIFTLOCK_ASSETS_INL
