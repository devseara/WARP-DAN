#include "riftlock.h"

#include "riftlock_protocol.h"
#include "riftlock_public_key.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <intrin.h>
#include <string>
#include <vector>

#include "riftlock_assets.inl"
#include "riftlock_modules.inl"
#include "riftlock_text.inl"
#include "riftlock_debug.inl"
#include "riftlock_hooks.inl"

namespace {

typedef void (__thiscall *QueueInsertFn)(void*, DWORD, const void*);
typedef bool (__thiscall *ConnectFn)(void*, void*);

enum class SessionState : std::uint8_t {
	kDisconnected,
	kWaitingHello,
	kWaitingReady,
	kActive,
	kFailed,
};

struct SodiumApi {
	HMODULE module;
	int (__cdecl *init)();
	void (__cdecl *random_bytes)(void*, std::size_t);
	int (__cdecl *x25519_base)(unsigned char*, const unsigned char*);
	int (__cdecl *x25519)(unsigned char*, const unsigned char*, const unsigned char*);
	int (__cdecl *verify_ed25519)(const unsigned char*, const unsigned char*, unsigned long long, const unsigned char*);
	int (__cdecl *hmac_sha256)(unsigned char*, const unsigned char*, unsigned long long, const unsigned char*);
	int (__cdecl *sha256)(unsigned char*, const unsigned char*, unsigned long long);
	void (__cdecl *memzero)(void*, std::size_t);
	int (__cdecl *memcmp_constant)(const void*, const void*, std::size_t);
};

struct PendingPacket {
	void* queue;
	QueueInsertFn insert;
	std::vector<std::uint8_t> bytes;
};

struct Session {
	SessionState state;
	void* control_queue;
	QueueInsertFn control_insert;
	std::uint32_t sequence;
	std::uint32_t last_challenge_sequence;
	std::uint32_t server_build_id;
	std::uint16_t server_type;
	std::uint8_t client_to_server[riftlock::kKeySize];
	std::uint8_t server_to_client[riftlock::kKeySize];
	std::vector<PendingPacket> pending;
	std::vector<std::uint8_t> inbound_control;
	std::size_t pending_bytes;
};

static const std::size_t kMaximumPendingPackets = 256;
static const std::size_t kMaximumPendingBytes = 1024 * 1024;
static const std::size_t kMaximumInnerPacket = 0xFFFFu -
	sizeof(riftlock::EnvelopePrefix) - riftlock::kMacSize;

INIT_ONCE g_initialize_once = INIT_ONCE_STATIC_INIT;
SRWLOCK g_session_lock = SRWLOCK_INIT;
SodiumApi g_sodium = {};
Session g_session = {};
bool g_initialized = false;
HMODULE g_module_instance = nullptr;
std::uint8_t g_device_digest[riftlock::kDigestSize] = {};
std::uint8_t g_integrity_digest[riftlock::kDigestSize] = {};
std::uint8_t g_asset_manifest_digest[riftlock::kDigestSize] = {};
std::vector<riftlock_assets::AllowedModule> g_allowed_modules;
riftlock_modules::Snapshot g_module_snapshot = {};
riftlock_debug::Snapshot g_debug_snapshot = {};
riftlock_hooks::Evidence g_hook_snapshot = {};
std::uint64_t g_last_thread_skip_signature = 0;

void handle_server_packet(const BYTE* packet, DWORD length);

void secure_zero(void* data, std::size_t length) {
	if (g_sodium.memzero != nullptr)
		g_sodium.memzero(data, length);
	else
		SecureZeroMemory(data, length);
}

std::wstring executable_directory() {
	wchar_t path[MAX_PATH] = {};
	const DWORD length = GetModuleFileNameW(nullptr, path, MAX_PATH);
	if (length == 0 || length >= MAX_PATH)
		return std::wstring();
	wchar_t* slash = wcsrchr(path, L'\\');
	if (slash == nullptr)
		return std::wstring();
	*slash = L'\0';
	return std::wstring(path);
}

void write_log(const char* message) {
	if (message == nullptr)
		return;
	char debug_line[512] = {};
	_snprintf_s(debug_line, sizeof(debug_line), _TRUNCATE, "Riftlock: %s\n", message);
	OutputDebugStringA(debug_line);

	const std::wstring directory = executable_directory();
	if (directory.empty())
		return;
	const std::wstring path = directory + L"\\riftlock.log";
	HANDLE file = CreateFileW(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
		nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (file == INVALID_HANDLE_VALUE)
		return;
	DWORD written = 0;
	WriteFile(file, debug_line, static_cast<DWORD>(strlen(debug_line)), &written, nullptr);
	CloseHandle(file);
}

void log_debug_scan_diagnostic(const riftlock_debug::Snapshot& snapshot) {
	if ((snapshot.scan_flags & riftlock_debug::kThreadScanComplete) != 0)
		return;
	riftlock_debug::ThreadSkipDiagnostic diagnostic = {};
	if (!riftlock_debug::thread_skip_diagnostic(diagnostic))
		return;
	const std::uint64_t signature = (static_cast<std::uint64_t>(diagnostic.stage) << 56) |
		(static_cast<std::uint64_t>(diagnostic.error) << 24) | diagnostic.thread_id;
	if (signature == g_last_thread_skip_signature)
		return;
	g_last_thread_skip_signature = signature;
	char message[512] = {};
	_snprintf_s(message, sizeof(message), _TRUNCATE,
		"thread debug scan incomplete stage=%u thread=%u error=%u checked=%u scan_flags=0x%04x start=0x%08x region_type=0x%08x trusted_module=%u module='%s' mapped='%s' description='%s'",
		diagnostic.stage, diagnostic.thread_id, diagnostic.error,
		snapshot.threads_checked, snapshot.scan_flags,
		static_cast<std::uint32_t>(diagnostic.address.start_address),
		diagnostic.address.region_type, diagnostic.address.trusted_module,
		diagnostic.address.module_name, diagnostic.address.mapped_path,
		diagnostic.description);
	write_log(message);
}

template <typename T>
bool load_symbol(T& output, const char* name) {
	output = reinterpret_cast<T>(GetProcAddress(g_sodium.module, name));
	return output != nullptr;
}

bool load_sodium() {
	const std::wstring directory = executable_directory();
	const wchar_t* names[] = {L"libsodium.dll", L"sodium.dll"};
	for (std::size_t index = 0; index < sizeof(names) / sizeof(names[0]); ++index) {
		const std::wstring path = directory.empty() ? std::wstring(names[index]) :
			directory + L"\\" + names[index];
		g_sodium.module = LoadLibraryW(path.c_str());
		if (g_sodium.module != nullptr)
			break;
	}
	if (g_sodium.module == nullptr) {
		write_log("libsodium.dll was not found beside the client executable");
		return false;
	}

	if (!load_symbol(g_sodium.init, "sodium_init") ||
		!load_symbol(g_sodium.random_bytes, "randombytes_buf") ||
		!load_symbol(g_sodium.x25519_base, "crypto_scalarmult_curve25519_base") ||
		!load_symbol(g_sodium.x25519, "crypto_scalarmult_curve25519") ||
		!load_symbol(g_sodium.verify_ed25519, "crypto_sign_verify_detached") ||
		!load_symbol(g_sodium.hmac_sha256, "crypto_auth_hmacsha256") ||
		!load_symbol(g_sodium.sha256, "crypto_hash_sha256") ||
		!load_symbol(g_sodium.memzero, "sodium_memzero") ||
		!load_symbol(g_sodium.memcmp_constant, "sodium_memcmp")) {
		write_log("libsodium.dll is missing one or more required exports");
		return false;
	}
	if (g_sodium.init() < 0) {
		write_log("sodium_init failed");
		return false;
	}
	return true;
}

void append_bytes(std::vector<std::uint8_t>& output, const void* data, std::size_t length) {
	const std::uint8_t* first = static_cast<const std::uint8_t*>(data);
	output.insert(output.end(), first, first + length);
}

void append_u16(std::vector<std::uint8_t>& output, std::uint16_t value) {
	output.push_back(static_cast<std::uint8_t>(value & 0xFF));
	output.push_back(static_cast<std::uint8_t>((value >> 8) & 0xFF));
}

void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
	for (unsigned int shift = 0; shift < 32; shift += 8)
		output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xFF));
}

void append_registry_value(std::vector<std::uint8_t>& output) {
	HKEY key = nullptr;
	if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Microsoft\\Cryptography", 0,
		KEY_QUERY_VALUE | KEY_WOW64_64KEY, &key) != ERROR_SUCCESS)
		return;
	wchar_t value[256] = {};
	DWORD type = 0;
	DWORD bytes = sizeof(value);
	if (RegQueryValueExW(key, L"MachineGuid", nullptr, &type,
		reinterpret_cast<BYTE*>(value), &bytes) == ERROR_SUCCESS &&
		(type == REG_SZ || type == REG_EXPAND_SZ)) {
		static const char label[] = "machine-guid";
		append_bytes(output, label, sizeof(label));
		append_bytes(output, value, std::min<std::size_t>(bytes, sizeof(value)));
	}
	RegCloseKey(key);
}

void append_volume_serial(std::vector<std::uint8_t>& output) {
	wchar_t windows_directory[MAX_PATH] = {};
	if (GetWindowsDirectoryW(windows_directory, MAX_PATH) == 0)
		return;
	wchar_t root[] = L"C:\\";
	root[0] = windows_directory[0];
	DWORD serial = 0;
	if (GetVolumeInformationW(root, nullptr, 0, &serial, nullptr, nullptr, nullptr, 0)) {
		static const char label[] = "system-volume";
		append_bytes(output, label, sizeof(label));
		append_bytes(output, &serial, sizeof(serial));
	}
}

void append_cpu_identity(std::vector<std::uint8_t>& output) {
	int registers[4] = {};
	__cpuid(registers, 0);
	static const char label[] = "cpu";
	append_bytes(output, label, sizeof(label));
	append_bytes(output, registers, sizeof(registers));
	__cpuid(registers, 1);
	append_bytes(output, registers, sizeof(registers));
}

bool compute_device_digest() {
	std::vector<std::uint8_t> identity;
	static const char domain[] = "riftlock/device/v1";
	append_bytes(identity, domain, sizeof(domain));
	append_registry_value(identity);
	append_volume_serial(identity);
	append_cpu_identity(identity);
	if (identity.size() <= sizeof(domain))
		return false;
	return g_sodium.sha256(g_device_digest, identity.data(), identity.size()) == 0;
}

bool hash_file(const wchar_t* path, std::uint8_t output[riftlock::kDigestSize]) {
	HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
		FILE_ATTRIBUTE_NORMAL, nullptr);
	if (file == INVALID_HANDLE_VALUE)
		return false;
	LARGE_INTEGER size = {};
	bool ok = GetFileSizeEx(file, &size) != FALSE && size.QuadPart > 0 &&
		size.QuadPart <= 256ll * 1024ll * 1024ll;
	HANDLE mapping = nullptr;
	const std::uint8_t* view = nullptr;
	if (ok) {
		mapping = CreateFileMappingW(file, nullptr, PAGE_READONLY, 0, 0, nullptr);
		ok = mapping != nullptr;
	}
	if (ok) {
		view = static_cast<const std::uint8_t*>(MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0));
		ok = view != nullptr;
	}
	if (ok)
		ok = g_sodium.sha256(output, view,
			static_cast<unsigned long long>(size.QuadPart)) == 0;
	if (view != nullptr)
		UnmapViewOfFile(view);
	if (mapping != nullptr)
		CloseHandle(mapping);
	CloseHandle(file);
	return ok;
}

bool compute_integrity_digest() {
	wchar_t executable_path[MAX_PATH] = {};
	wchar_t module_path[MAX_PATH] = {};
	wchar_t sodium_path[MAX_PATH] = {};
	if (GetModuleFileNameW(nullptr, executable_path, MAX_PATH) == 0 ||
		g_module_instance == nullptr ||
		GetModuleFileNameW(g_module_instance, module_path, MAX_PATH) == 0 ||
		g_sodium.module == nullptr ||
		GetModuleFileNameW(g_sodium.module, sodium_path, MAX_PATH) == 0)
		return false;

	std::uint8_t executable_digest[riftlock::kDigestSize] = {};
	std::uint8_t module_digest[riftlock::kDigestSize] = {};
	std::uint8_t sodium_digest[riftlock::kDigestSize] = {};
	bool ok = hash_file(executable_path, executable_digest) &&
		hash_file(module_path, module_digest) &&
		hash_file(sodium_path, sodium_digest);
	if (ok) {
		std::vector<std::uint8_t> release_identity;
		static const char domain[] = "riftlock/integrity/v2";
		append_bytes(release_identity, domain, strlen(domain));
		append_bytes(release_identity, executable_digest, sizeof(executable_digest));
		append_bytes(release_identity, module_digest, sizeof(module_digest));
		append_bytes(release_identity, sodium_digest, sizeof(sodium_digest));
		append_bytes(release_identity, g_asset_manifest_digest, sizeof(g_asset_manifest_digest));
		ok = g_sodium.sha256(g_integrity_digest, release_identity.data(),
			release_identity.size()) == 0;
	}
	secure_zero(executable_digest, sizeof(executable_digest));
	secure_zero(module_digest, sizeof(module_digest));
	secure_zero(sodium_digest, sizeof(sodium_digest));
	return ok;
}

BOOL CALLBACK initialize_once(PINIT_ONCE, PVOID, PVOID*) {
	const ULONGLONG started_at = GetTickCount64();
	bool public_key_nonzero = false;
	for (std::size_t index = 0; index < sizeof(kRiftlockServerPublicKey); ++index)
		public_key_nonzero = public_key_nonzero || kRiftlockServerPublicKey[index] != 0;
	if (RIFTLOCK_PUBLIC_KEY_CONFIGURED != 1 || !public_key_nonzero) {
		write_log("server public key is not configured; refusing native traffic");
		return TRUE;
	}
	if (!load_sodium())
		return TRUE;
	wchar_t executable_path[MAX_PATH] = {};
	if (GetModuleFileNameW(nullptr, executable_path, MAX_PATH) == 0) {
		write_log("could not resolve the patched client path");
		return TRUE;
	}
	std::string asset_error;
	if (!riftlock_assets::verify(executable_directory(), executable_path, g_sodium.sha256,
		g_asset_manifest_digest, g_allowed_modules, asset_error)) {
		write_log(asset_error.c_str());
		return TRUE;
	}
	std::string module_error;
	if (!riftlock_modules::initialize(executable_directory(), executable_path,
		g_allowed_modules, g_sodium.sha256, g_module_snapshot, module_error)) {
		write_log(module_error.c_str());
		return TRUE;
	}
	if (g_module_snapshot.unlinked_exec_region_count != 0) {
		std::vector<riftlock_modules::RuntimeRegionDiagnostic> diagnostics;
		riftlock_modules::runtime_diagnostics(diagnostics);
		for (const riftlock_modules::RuntimeRegionDiagnostic& region : diagnostics) {
			if (region.trusted_system_image != 0)
				continue;
			char message[512] = {};
			_snprintf_s(message, sizeof(message), _TRUNCATE,
				"unlinked image path='%s' type=0x%08x protect=0x%08x pe=%u image_size=%u",
				region.mapped_path, region.type, region.protect, region.pe_valid,
				region.pe_image_size);
			write_log(message);
		}
	}
	std::string text_error;
	if (!riftlock_text::initialize(GetModuleHandleW(nullptr), g_module_instance, text_error)) {
		write_log(text_error.c_str());
		return TRUE;
	}
	std::string debug_error;
	if (!riftlock_debug::initialize(g_sodium.sha256, g_debug_snapshot, debug_error)) {
		write_log(debug_error.c_str());
		return TRUE;
	}
	log_debug_scan_diagnostic(g_debug_snapshot);
	std::string hook_error;
	if (!riftlock_hooks::initialize(g_sodium.sha256, g_hook_snapshot, hook_error)) {
		write_log(hook_error.c_str());
		return TRUE;
	}
	if (!compute_device_digest()) {
		write_log("could not compute the device identity digest");
		return TRUE;
	}
	if (!compute_integrity_digest()) {
		write_log("could not hash the client release files");
		return TRUE;
	}
	secure_zero(g_asset_manifest_digest, sizeof(g_asset_manifest_digest));
	g_initialized = true;
	char message[128] = {};
	_snprintf_s(message, sizeof(message), _TRUNCATE,
		"transport initialized in %llu ms", GetTickCount64() - started_at);
	write_log(message);
	return TRUE;
}

bool ensure_initialized() {
	InitOnceExecuteOnce(&g_initialize_once, initialize_once, nullptr, nullptr);
	return g_initialized;
}

bool constant_equal(const void* left, const void* right, std::size_t length) {
	return g_sodium.memcmp_constant(left, right, length) == 0;
}

bool hmac_tag(std::uint8_t output[riftlock::kMacSize],
	const std::uint8_t key[riftlock::kKeySize], const void* message, std::size_t length) {
	std::uint8_t full[riftlock::kKeySize] = {};
	const int result = g_sodium.hmac_sha256(full,
		static_cast<const unsigned char*>(message), length, key);
	if (result == 0)
		memcpy(output, full, riftlock::kMacSize);
	secure_zero(full, sizeof(full));
	return result == 0;
}

void reset_session_locked() {
	secure_zero(g_session.client_to_server, sizeof(g_session.client_to_server));
	secure_zero(g_session.server_to_client, sizeof(g_session.server_to_client));
	g_session.control_queue = nullptr;
	g_session.control_insert = nullptr;
	g_session.sequence = 0;
	g_session.last_challenge_sequence = 0;
	g_session.server_build_id = 0;
	g_session.server_type = 0;
	g_session.pending.clear();
	g_session.inbound_control.clear();
	g_session.pending_bytes = 0;
	g_session.state = g_initialized ? SessionState::kDisconnected : SessionState::kFailed;
}

void fail_session_locked(const char* reason) {
	secure_zero(g_session.client_to_server, sizeof(g_session.client_to_server));
	secure_zero(g_session.server_to_client, sizeof(g_session.server_to_client));
	g_session.pending.clear();
	g_session.pending_bytes = 0;
	g_session.state = SessionState::kFailed;
	write_log(reason);
}

bool queue_raw_locked(void* queue, QueueInsertFn insert,
	const void* packet, std::size_t length) {
	if (queue == nullptr || insert == nullptr || packet == nullptr ||
		length == 0 || length > 0xFFFFFFFFu)
		return false;
	insert(queue, static_cast<DWORD>(length), packet);
	return true;
}

bool queue_control_locked(const void* packet, std::size_t length) {
	return queue_raw_locked(g_session.control_queue, g_session.control_insert, packet, length);
}

bool queue_probe_locked() {
	riftlock::ClientProbe probe = {};
	probe.packet_id = riftlock::kClientProbe;
	probe.packet_length = sizeof(probe);
	probe.magic = riftlock::kProbeMagic;
	if (!queue_control_locked(&probe, sizeof(probe)))
		return false;
	g_session.state = SessionState::kWaitingHello;
	return true;
}

bool buffer_native_locked(void* queue, QueueInsertFn insert,
	const std::uint8_t* packet, std::size_t length) {
	if (queue == nullptr || insert == nullptr || packet == nullptr ||
		length < sizeof(std::uint16_t) || length > kMaximumInnerPacket ||
		g_session.pending.size() >= kMaximumPendingPackets ||
		g_session.pending_bytes + length > kMaximumPendingBytes)
		return false;
	PendingPacket pending = {};
	pending.queue = queue;
	pending.insert = insert;
	pending.bytes.assign(packet, packet + length);
	g_session.pending.push_back(pending);
	g_session.pending_bytes += length;
	return true;
}

bool queue_envelope_locked(void* queue, QueueInsertFn insert,
	const std::uint8_t* packet, std::size_t length) {
	if (queue == nullptr || insert == nullptr || packet == nullptr ||
		length < sizeof(std::uint16_t) || length > kMaximumInnerPacket ||
		g_session.sequence == 0xFFFFFFFFu)
		return false;
	const std::size_t total = sizeof(riftlock::EnvelopePrefix) + length + riftlock::kMacSize;
	std::vector<std::uint8_t> envelope(total, 0);
	riftlock::EnvelopePrefix* prefix =
		reinterpret_cast<riftlock::EnvelopePrefix*>(envelope.data());
	prefix->packet_id = riftlock::kClientEnvelope;
	prefix->packet_length = static_cast<std::uint16_t>(total);
	prefix->sequence = ++g_session.sequence;
	prefix->inner_length = static_cast<std::uint16_t>(length);
	memcpy(envelope.data() + sizeof(*prefix), packet, length);
	if (!hmac_tag(envelope.data() + total - riftlock::kMacSize,
		g_session.client_to_server, envelope.data(), total - riftlock::kMacSize))
		return false;
	return queue_raw_locked(queue, insert, envelope.data(), envelope.size());
}

bool derive_session_keys(const riftlock::ServerHello& server,
	const std::uint8_t client_nonce[riftlock::kNonceSize],
	const std::uint8_t shared[riftlock::kKeySize]) {
	std::uint8_t prk[riftlock::kKeySize] = {};
	if (g_sodium.hmac_sha256(prk, shared, riftlock::kKeySize, server.server_nonce) != 0)
		return false;

	auto expand = [&](const char* label, std::uint8_t output[riftlock::kKeySize]) -> bool {
		std::vector<std::uint8_t> info;
		append_bytes(info, label, strlen(label));
		append_bytes(info, client_nonce, riftlock::kNonceSize);
		append_u32(info, RIFTLOCK_BUILD_ID);
		append_u16(info, server.server_type);
		info.push_back(1);
		return g_sodium.hmac_sha256(output, info.data(), info.size(), prk) == 0;
	};

	const bool result = expand("riftlock/c2s/v1", g_session.client_to_server) &&
		expand("riftlock/s2c/v1", g_session.server_to_client);
	secure_zero(prk, sizeof(prk));
	return result;
}

bool handle_server_hello_locked(const std::uint8_t* packet, std::size_t length) {
	if (g_session.state != SessionState::kWaitingHello ||
		length != sizeof(riftlock::ServerHello))
		return false;
	riftlock::ServerHello server = {};
	memcpy(&server, packet, sizeof(server));
	if (server.packet_id != riftlock::kServerHello ||
		server.packet_length != sizeof(server) ||
		server.protocol_version != riftlock::kProtocolVersion ||
		server.server_type < 1 || server.server_type > 3 ||
		server.build_id != RIFTLOCK_BUILD_ID)
		return false;
	if (g_sodium.verify_ed25519(server.signature, packet,
		offsetof(riftlock::ServerHello, signature), kRiftlockServerPublicKey) != 0)
		return false;
	std::string module_error;
	if (!riftlock_modules::refresh(g_module_snapshot, false, module_error)) {
		write_log(module_error.c_str());
		return false;
	}
	std::string debug_error;
	if (!riftlock_debug::refresh(g_debug_snapshot, debug_error)) {
		write_log(debug_error.c_str());
		return false;
	}
	log_debug_scan_diagnostic(g_debug_snapshot);
	std::string hook_error;
	if (!riftlock_hooks::refresh(g_hook_snapshot, hook_error)) {
		write_log(hook_error.c_str());
		return false;
	}

	std::uint8_t client_secret[riftlock::kKeySize] = {};
	std::uint8_t client_public[riftlock::kKeySize] = {};
	std::uint8_t shared[riftlock::kKeySize] = {};
	std::uint8_t client_nonce[riftlock::kNonceSize] = {};
	g_sodium.random_bytes(client_secret, sizeof(client_secret));
	g_sodium.random_bytes(client_nonce, sizeof(client_nonce));
	bool ok = g_sodium.x25519_base(client_public, client_secret) == 0 &&
		g_sodium.x25519(shared, client_secret, server.server_ephemeral_public) == 0 &&
		derive_session_keys(server, client_nonce, shared);
	secure_zero(client_secret, sizeof(client_secret));
	secure_zero(shared, sizeof(shared));
	if (!ok)
		return false;

	riftlock::ClientHello client = {};
	riftlock_text::Evidence text_evidence = {};
	std::string text_error;
	if (!riftlock_text::sample(server.server_nonce, g_sodium.sha256, text_evidence, text_error)) {
		write_log(text_error.c_str());
		return false;
	}
	client.packet_id = riftlock::kClientHello;
	client.packet_length = sizeof(client);
	client.protocol_version = riftlock::kProtocolVersion;
	client.flags = riftlock::kModuleInventoryPresent;
	client.build_id = RIFTLOCK_BUILD_ID;
	memcpy(client.client_nonce, client_nonce, sizeof(client.client_nonce));
	memcpy(client.client_ephemeral_public, client_public, sizeof(client.client_ephemeral_public));
	memcpy(client.device_digest, g_device_digest, sizeof(client.device_digest));
	memcpy(client.integrity_digest, g_integrity_digest, sizeof(client.integrity_digest));
	memcpy(client.module_digest, g_module_snapshot.digest, sizeof(client.module_digest));
	client.module_count = g_module_snapshot.module_count;
	client.unknown_module_count = g_module_snapshot.unknown_count;
	client.unknown_module_size = g_module_snapshot.first_unknown_size;
	memcpy(client.unknown_module_name, g_module_snapshot.first_unknown_name,
		sizeof(client.unknown_module_name));
	memcpy(client.unknown_module_text_digest, g_module_snapshot.first_unknown_text_digest,
		sizeof(client.unknown_module_text_digest));
	memcpy(client.memory_digest, g_module_snapshot.memory_digest, sizeof(client.memory_digest));
	client.private_exec_region_count = g_module_snapshot.private_exec_region_count;
	client.unlinked_exec_region_count = g_module_snapshot.unlinked_exec_region_count;
	client.suspicious_thread_count = g_module_snapshot.suspicious_thread_count;
	client.first_private_region_size = g_module_snapshot.first_private_region_size;
	client.first_private_region_protect = g_module_snapshot.first_private_region_protect;
	client.first_suspicious_thread_id = g_module_snapshot.first_suspicious_thread_id;
	client.first_suspicious_region_type = g_module_snapshot.first_suspicious_region_type;
	memcpy(client.text_sample_digest, text_evidence.digest, sizeof(client.text_sample_digest));
	client.text_mismatch_count = text_evidence.mismatch_count;
	client.text_slice_count = text_evidence.slice_count;
	client.text_checked_bytes = text_evidence.checked_bytes;
	client.first_text_mismatch_offset = text_evidence.first_mismatch_offset;
	client.first_text_mismatch_module = text_evidence.first_mismatch_module;
	memcpy(client.debug_digest, g_debug_snapshot.digest, sizeof(client.debug_digest));
	client.debugger_flags = g_debug_snapshot.debugger_flags;
	client.hardware_breakpoint_count = g_debug_snapshot.hardware_breakpoint_count;
	client.debug_threads_checked = g_debug_snapshot.threads_checked;
	client.suspicious_handle_count = g_debug_snapshot.suspicious_handle_count;
	client.external_handle_count = g_debug_snapshot.external_handle_count;
	client.debug_scan_flags = g_debug_snapshot.scan_flags;
	client.first_hardware_thread_id = g_debug_snapshot.first_hardware_thread_id;
	client.first_hardware_dr7 = g_debug_snapshot.first_hardware_dr7;
	client.first_handle_owner_pid = g_debug_snapshot.first_handle_owner_pid;
	client.first_handle_access = g_debug_snapshot.first_handle_access;
	memcpy(client.hook_digest, g_hook_snapshot.digest, sizeof(client.hook_digest));
	client.hook_mismatch_count = g_hook_snapshot.mismatch_count;
	client.hook_checked_count = g_hook_snapshot.checked_count;
	client.hook_unresolved_count = g_hook_snapshot.unresolved_count;
	client.hook_scan_flags = g_hook_snapshot.scan_flags;
	client.first_hook_target = g_hook_snapshot.first_mismatch_target;
	memcpy(client.first_hook_live, g_hook_snapshot.first_live,
		sizeof(client.first_hook_live));
	memcpy(client.first_hook_disk, g_hook_snapshot.first_disk,
		sizeof(client.first_hook_disk));
	secure_zero(client_nonce, sizeof(client_nonce));
	if (!hmac_tag(client.tag, g_session.client_to_server, &client,
		offsetof(riftlock::ClientHello, tag)) || !queue_control_locked(&client, sizeof(client)))
		return false;
	g_session.server_build_id = server.build_id;
	g_session.server_type = server.server_type;
	g_session.state = SessionState::kWaitingReady;
	return true;
}

bool handle_server_ready_locked(const std::uint8_t* packet, std::size_t length) {
	if (g_session.state != SessionState::kWaitingReady ||
		length != sizeof(riftlock::ServerReady))
		return false;
	riftlock::ServerReady ready = {};
	memcpy(&ready, packet, sizeof(ready));
	std::uint8_t expected[riftlock::kMacSize] = {};
	if (ready.packet_id != riftlock::kServerReady ||
		ready.packet_length != sizeof(ready) ||
		ready.build_id != g_session.server_build_id ||
		!hmac_tag(expected, g_session.server_to_client, packet,
			offsetof(riftlock::ServerReady, tag)) ||
		!constant_equal(expected, ready.tag, sizeof(expected)))
		return false;

	g_session.state = SessionState::kActive;
	for (std::size_t index = 0; index < g_session.pending.size(); ++index) {
		const PendingPacket& pending = g_session.pending[index];
		if (!queue_envelope_locked(pending.queue, pending.insert,
			pending.bytes.data(), pending.bytes.size()))
			return false;
	}
	g_session.pending.clear();
	g_session.pending_bytes = 0;
	return true;
}

bool handle_server_challenge_locked(const std::uint8_t* packet, std::size_t length) {
	if (g_session.state != SessionState::kActive ||
		length != sizeof(riftlock::ServerChallenge))
		return false;
	riftlock::ServerChallenge challenge = {};
	memcpy(&challenge, packet, sizeof(challenge));
	std::uint8_t expected[riftlock::kMacSize] = {};
	if (challenge.packet_id != riftlock::kServerChallenge ||
		challenge.packet_length != sizeof(challenge) ||
		challenge.type != riftlock::kSessionHmac || challenge.reserved != 0 ||
		challenge.sequence <= g_session.last_challenge_sequence ||
		!hmac_tag(expected, g_session.server_to_client, packet,
			offsetof(riftlock::ServerChallenge, tag)) ||
		!constant_equal(expected, challenge.tag, sizeof(expected)))
		return false;

	riftlock::ClientChallenge response = {};
	std::string module_error;
	if (!riftlock_modules::refresh(g_module_snapshot, false, module_error)) {
		write_log(module_error.c_str());
		return false;
	}
	std::string debug_error;
	if (!riftlock_debug::refresh(g_debug_snapshot, debug_error)) {
		write_log(debug_error.c_str());
		return false;
	}
	log_debug_scan_diagnostic(g_debug_snapshot);
	std::string hook_error;
	if (!riftlock_hooks::refresh(g_hook_snapshot, hook_error)) {
		write_log(hook_error.c_str());
		return false;
	}
	riftlock_text::Evidence text_evidence = {};
	std::string text_error;
	if (!riftlock_text::sample(challenge.nonce, g_sodium.sha256, text_evidence, text_error)) {
		write_log(text_error.c_str());
		return false;
	}
	riftlock_assets::ChallengeEvidence asset_evidence = {};
	std::string asset_error;
	const ULONGLONG asset_started_at = GetTickCount64();
	if (!riftlock_assets::sample_challenge(challenge.nonce, g_sodium.sha256,
		asset_evidence, asset_error)) {
		write_log(asset_error.c_str());
		return false;
	}
	const ULONGLONG asset_elapsed = GetTickCount64() - asset_started_at;
	if (asset_elapsed >= 100) {
		char message[160] = {};
		_snprintf_s(message, sizeof(message), _TRUNCATE,
			"asset challenge sampled %u files and %u bytes in %llu ms",
			static_cast<unsigned>(asset_evidence.module_sample_count +
				asset_evidence.grf_sample_count + asset_evidence.loose_sample_count),
			asset_evidence.checked_bytes, asset_elapsed);
		write_log(message);
	}
	response.packet_id = riftlock::kClientChallenge;
	response.packet_length = sizeof(response);
	response.sequence = challenge.sequence;
	memcpy(response.nonce, challenge.nonce, sizeof(response.nonce));
	memcpy(response.module_digest, g_module_snapshot.digest, sizeof(response.module_digest));
	response.module_count = g_module_snapshot.module_count;
	response.unknown_module_count = g_module_snapshot.unknown_count;
	response.unknown_module_size = g_module_snapshot.first_unknown_size;
	memcpy(response.unknown_module_name, g_module_snapshot.first_unknown_name,
		sizeof(response.unknown_module_name));
	memcpy(response.unknown_module_text_digest, g_module_snapshot.first_unknown_text_digest,
		sizeof(response.unknown_module_text_digest));
	memcpy(response.memory_digest, g_module_snapshot.memory_digest, sizeof(response.memory_digest));
	response.private_exec_region_count = g_module_snapshot.private_exec_region_count;
	response.unlinked_exec_region_count = g_module_snapshot.unlinked_exec_region_count;
	response.suspicious_thread_count = g_module_snapshot.suspicious_thread_count;
	response.first_private_region_size = g_module_snapshot.first_private_region_size;
	response.first_private_region_protect = g_module_snapshot.first_private_region_protect;
	response.first_suspicious_thread_id = g_module_snapshot.first_suspicious_thread_id;
	response.first_suspicious_region_type = g_module_snapshot.first_suspicious_region_type;
	memcpy(response.text_sample_digest, text_evidence.digest, sizeof(response.text_sample_digest));
	response.text_mismatch_count = text_evidence.mismatch_count;
	response.text_slice_count = text_evidence.slice_count;
	response.text_checked_bytes = text_evidence.checked_bytes;
	response.first_text_mismatch_offset = text_evidence.first_mismatch_offset;
	response.first_text_mismatch_module = text_evidence.first_mismatch_module;
	memcpy(response.asset_sample_digest, asset_evidence.digest,
		sizeof(response.asset_sample_digest));
	response.asset_mismatch_count = asset_evidence.mismatch_count;
	response.asset_module_sample_count = asset_evidence.module_sample_count;
	response.asset_grf_sample_count = asset_evidence.grf_sample_count;
	response.asset_loose_sample_count = asset_evidence.loose_sample_count;
	response.asset_checked_bytes = asset_evidence.checked_bytes;
	response.first_asset_mismatch_index = asset_evidence.first_mismatch_index;
	response.first_asset_mismatch_kind = asset_evidence.first_mismatch_kind;
	memcpy(response.debug_digest, g_debug_snapshot.digest,
		sizeof(response.debug_digest));
	response.debugger_flags = g_debug_snapshot.debugger_flags;
	response.hardware_breakpoint_count = g_debug_snapshot.hardware_breakpoint_count;
	response.debug_threads_checked = g_debug_snapshot.threads_checked;
	response.suspicious_handle_count = g_debug_snapshot.suspicious_handle_count;
	response.external_handle_count = g_debug_snapshot.external_handle_count;
	response.debug_scan_flags = g_debug_snapshot.scan_flags;
	response.first_hardware_thread_id = g_debug_snapshot.first_hardware_thread_id;
	response.first_hardware_dr7 = g_debug_snapshot.first_hardware_dr7;
	response.first_handle_owner_pid = g_debug_snapshot.first_handle_owner_pid;
	response.first_handle_access = g_debug_snapshot.first_handle_access;
	memcpy(response.hook_digest, g_hook_snapshot.digest,
		sizeof(response.hook_digest));
	response.hook_mismatch_count = g_hook_snapshot.mismatch_count;
	response.hook_checked_count = g_hook_snapshot.checked_count;
	response.hook_unresolved_count = g_hook_snapshot.unresolved_count;
	response.hook_scan_flags = g_hook_snapshot.scan_flags;
	response.first_hook_target = g_hook_snapshot.first_mismatch_target;
	memcpy(response.first_hook_live, g_hook_snapshot.first_live,
		sizeof(response.first_hook_live));
	memcpy(response.first_hook_disk, g_hook_snapshot.first_disk,
		sizeof(response.first_hook_disk));
	if (!hmac_tag(response.tag, g_session.client_to_server, &response,
		offsetof(riftlock::ClientChallenge, tag)) ||
		!queue_control_locked(&response, sizeof(response)))
		return false;
	g_session.last_challenge_sequence = challenge.sequence;
	return true;
}

void reset_for_connection() {
	const bool initialized = ensure_initialized();
	AcquireSRWLockExclusive(&g_session_lock);
	reset_session_locked();
	if (!initialized)
		g_session.state = SessionState::kFailed;
	ReleaseSRWLockExclusive(&g_session_lock);
}

void queue_native(void* queue, DWORD original, DWORD length, const BYTE* packet,
	bool deferred_queue) {
	if (!ensure_initialized())
		return;
	AcquireSRWLockExclusive(&g_session_lock);
	QueueInsertFn insert = reinterpret_cast<QueueInsertFn>(original);
	// CConnection owns the immediate queue at +0x24 and the deferred queue at
	// +0x54 in the profiled client. Control traffic must always use +0x24 so a
	// heartbeat cannot remain parked behind SetBlock.
	void* control_queue = deferred_queue && queue != nullptr
		? static_cast<void*>(static_cast<BYTE*>(queue) - 0x30)
		: queue;
	if (g_session.control_queue == nullptr || !deferred_queue) {
		g_session.control_queue = control_queue;
		g_session.control_insert = insert;
	}
	bool ok = true;
	if (g_session.state == SessionState::kDisconnected) {
		ok = queue_probe_locked();
		if (ok)
			ok = buffer_native_locked(queue, insert, packet, length);
	} else if (g_session.state == SessionState::kWaitingHello ||
		g_session.state == SessionState::kWaitingReady) {
		ok = buffer_native_locked(queue, insert, packet, length);
	} else if (g_session.state == SessionState::kActive) {
		ok = queue_envelope_locked(queue, insert, packet, length);
	} else {
		ok = false;
	}
	if (!ok && g_session.state != SessionState::kFailed)
		fail_session_locked("outgoing transport failed; native packet was dropped");
	ReleaseSRWLockExclusive(&g_session_lock);
}

bool is_server_control(std::uint16_t packet_id) {
	return packet_id == riftlock::kServerHello || packet_id == riftlock::kServerChallenge ||
		packet_id == riftlock::kServerReady;
}

void receive_bytes(void* queue, DWORD original, DWORD length, const BYTE* bytes) {
	QueueInsertFn insert = reinterpret_cast<QueueInsertFn>(original);
	if (!ensure_initialized() || queue == nullptr || insert == nullptr || bytes == nullptr || length == 0)
		return;

	std::vector<std::uint8_t> control;
	std::vector<std::uint8_t> remainder;
	bool intercept = false;
	AcquireSRWLockExclusive(&g_session_lock);
	if (!g_session.inbound_control.empty()) {
		intercept = true;
	} else if (length >= sizeof(std::uint16_t)) {
		std::uint16_t packet_id = 0;
		memcpy(&packet_id, bytes, sizeof(packet_id));
		intercept = is_server_control(packet_id);
	} else if (g_session.state == SessionState::kWaitingHello ||
		g_session.state == SessionState::kWaitingReady) {
		intercept = true;
	}

	if (intercept) {
		g_session.inbound_control.insert(g_session.inbound_control.end(), bytes, bytes + length);
		if (g_session.inbound_control.size() >= sizeof(std::uint16_t) * 2) {
			std::uint16_t packet_id = 0;
			std::uint16_t packet_length = 0;
			memcpy(&packet_id, g_session.inbound_control.data(), sizeof(packet_id));
			memcpy(&packet_length, g_session.inbound_control.data() + sizeof(packet_id),
				sizeof(packet_length));
			if (!is_server_control(packet_id) || packet_length < 4 || packet_length > 4096) {
				remainder.swap(g_session.inbound_control);
			} else if (g_session.inbound_control.size() >= packet_length) {
				control.assign(g_session.inbound_control.begin(),
					g_session.inbound_control.begin() + packet_length);
				remainder.assign(g_session.inbound_control.begin() + packet_length,
					g_session.inbound_control.end());
				g_session.inbound_control.clear();
			}
		}
	}
	ReleaseSRWLockExclusive(&g_session_lock);

	if (!intercept) {
		insert(queue, length, bytes);
		return;
	}
	if (!control.empty()) {
		handle_server_packet(control.data(), static_cast<DWORD>(control.size()));
	}
	if (!remainder.empty())
		insert(queue, static_cast<DWORD>(remainder.size()), remainder.data());
}

void handle_server_packet(const BYTE* packet, DWORD length) {
	if (!ensure_initialized() || packet == nullptr || length < sizeof(std::uint16_t))
		return;
	std::uint16_t packet_id = 0;
	memcpy(&packet_id, packet, sizeof(packet_id));
	AcquireSRWLockExclusive(&g_session_lock);
	bool ok = false;
	if (packet_id == riftlock::kServerHello)
		ok = handle_server_hello_locked(packet, length);
	else if (packet_id == riftlock::kServerReady)
		ok = handle_server_ready_locked(packet, length);
	else if (packet_id == riftlock::kServerChallenge)
		ok = handle_server_challenge_locked(packet, length);
	if (!ok)
		fail_session_locked("invalid or unexpected authenticated server control packet");
	ReleaseSRWLockExclusive(&g_session_lock);
}

} // namespace

#if defined(_M_IX86)
#pragma comment(linker, "/EXPORT:RiftlockConnectionResetBridge=@RiftlockConnectionResetBridge@16")
#pragma comment(linker, "/EXPORT:RiftlockQueuePacketBridge=@RiftlockQueuePacketBridge@20")
#pragma comment(linker, "/EXPORT:RiftlockQueueDeferredPacketBridge=@RiftlockQueueDeferredPacketBridge@20")
#pragma comment(linker, "/EXPORT:RiftlockReceiveBytesBridge=@RiftlockReceiveBytesBridge@20")
#endif

extern "C" __declspec(dllexport) DWORD __cdecl RiftlockInit(void) {
	return ensure_initialized() ? RIFTLOCK_VERSION : 0;
}

extern "C" __declspec(dllexport) BOOL __fastcall RiftlockConnectionResetBridge(
	void* connection, void*, DWORD original, void* target) {
	__try {
		reset_for_connection();
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		write_log("exception while resetting connection state");
	}
	ConnectFn connect = reinterpret_cast<ConnectFn>(original);
	return connect != nullptr && connect(connection, target) ? TRUE : FALSE;
}

extern "C" __declspec(dllexport) void __fastcall RiftlockQueuePacketBridge(
	void* queue, void*, DWORD original, DWORD length, const BYTE* packet) {
	__try {
		queue_native(queue, original, length, packet, false);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		write_log("exception while wrapping native packet; packet was dropped");
	}
}

extern "C" __declspec(dllexport) void __fastcall RiftlockQueueDeferredPacketBridge(
	void* queue, void*, DWORD original, DWORD length, const BYTE* packet) {
	__try {
		queue_native(queue, original, length, packet, true);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		write_log("exception while wrapping deferred native packet; packet was dropped");
	}
}

extern "C" __declspec(dllexport) void __fastcall RiftlockReceiveBytesBridge(
	void* queue, void*, DWORD original, DWORD length, const BYTE* bytes) {
	__try {
		receive_bytes(queue, original, length, bytes);
	} __except (EXCEPTION_EXECUTE_HANDLER) {
		write_log("exception while routing native receive bytes");
	}
}

DWORD WINAPI RiftlockInitializeWorker(LPVOID) {
	ensure_initialized();
	return 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
	if (reason == DLL_PROCESS_ATTACH) {
		g_module_instance = instance;
		DisableThreadLibraryCalls(instance);
		HANDLE worker = CreateThread(nullptr, 0, RiftlockInitializeWorker, nullptr, 0, nullptr);
		if (worker != nullptr)
			CloseHandle(worker);
	}
	return TRUE;
}
