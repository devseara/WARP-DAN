#pragma once

#include <cstddef>
#include <cstdint>

namespace riftlock {

static const std::uint16_t kProtocolVersion = 7;
static const std::uint32_t kProbeMagic = 0x54464952u;
static const std::size_t kNonceSize = 32;
static const std::size_t kKeySize = 32;
static const std::size_t kDigestSize = 32;
static const std::size_t kSignatureSize = 64;
static const std::size_t kMacSize = 16;
static const std::size_t kModuleNameSize = 64;

enum ClientFlags : std::uint16_t {
	kModuleInventoryPresent = 0x0001,
};

enum PacketId : std::uint16_t {
	kClientProbe = 0x0CEF,
	kServerHello = 0x0CF0,
	kClientHello = 0x0CF1,
	kServerChallenge = 0x0CF2,
	kClientChallenge = 0x0CF3,
	kClientEnvelope = 0x0CF4,
	kServerReady = 0x0CF5,
};

enum ChallengeType : std::uint16_t {
	kSessionHmac = 1,
};

enum AssetSampleKind : std::uint8_t {
	kAssetSampleNone = 0,
	kAssetSampleModule = 1,
	kAssetSampleGrfEntry = 2,
	kAssetSampleLooseFile = 3,
};

enum DebugEvidenceFlags : std::uint16_t {
	kDebugEvidenceApi = 0x0001,
	kDebugEvidenceRemoteApi = 0x0002,
	kDebugEvidencePeb = 0x0004,
	kDebugEvidencePort = 0x0008,
	kDebugEvidenceObject = 0x0010,
	kDebugEvidenceFlags = 0x0020,
	kDebugEvidenceAll = 0x003f,
};

enum DebugScanFlags : std::uint16_t {
	kDebugScanProcess = 0x0001,
	kDebugScanThreads = 0x0002,
	kDebugScanHandles = 0x0004,
	kDebugScanRequired = 0x0007,
};

enum HookScanFlags : std::uint16_t {
	kHookScanComplete = 0x0001,
};

static const std::uint16_t kHookTargetMax = 13;

#pragma pack(push, 1)

struct ClientProbe {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint32_t magic;
};

struct ServerHello {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint16_t protocol_version;
	std::uint16_t server_type;
	std::uint32_t build_id;
	std::uint8_t server_nonce[kNonceSize];
	std::uint8_t server_ephemeral_public[kKeySize];
	std::uint8_t signature[kSignatureSize];
};

struct ClientHello {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint16_t protocol_version;
	std::uint16_t flags;
	std::uint32_t build_id;
	std::uint8_t client_nonce[kNonceSize];
	std::uint8_t client_ephemeral_public[kKeySize];
	std::uint8_t device_digest[kDigestSize];
	std::uint8_t integrity_digest[kDigestSize];
	std::uint8_t module_digest[kDigestSize];
	std::uint16_t module_count;
	std::uint16_t unknown_module_count;
	std::uint32_t unknown_module_size;
	char unknown_module_name[kModuleNameSize];
	std::uint8_t unknown_module_text_digest[kDigestSize];
	std::uint8_t memory_digest[kDigestSize];
	std::uint16_t private_exec_region_count;
	std::uint16_t unlinked_exec_region_count;
	std::uint16_t suspicious_thread_count;
	std::uint16_t runtime_reserved;
	std::uint32_t first_private_region_size;
	std::uint32_t first_private_region_protect;
	std::uint32_t first_suspicious_thread_id;
	std::uint32_t first_suspicious_region_type;
	std::uint8_t text_sample_digest[kDigestSize];
	std::uint16_t text_mismatch_count;
	std::uint16_t text_slice_count;
	std::uint32_t text_checked_bytes;
	std::uint32_t first_text_mismatch_offset;
	std::uint8_t first_text_mismatch_module;
	std::uint8_t text_reserved[3];
	std::uint8_t debug_digest[kDigestSize];
	std::uint16_t debugger_flags;
	std::uint16_t hardware_breakpoint_count;
	std::uint16_t debug_threads_checked;
	std::uint16_t suspicious_handle_count;
	std::uint16_t external_handle_count;
	std::uint16_t debug_scan_flags;
	std::uint32_t first_hardware_thread_id;
	std::uint32_t first_hardware_dr7;
	std::uint32_t first_handle_owner_pid;
	std::uint32_t first_handle_access;
	std::uint8_t hook_digest[kDigestSize];
	std::uint16_t hook_mismatch_count;
	std::uint16_t hook_checked_count;
	std::uint16_t hook_unresolved_count;
	std::uint16_t hook_scan_flags;
	std::uint16_t first_hook_target;
	std::uint16_t hook_reserved;
	std::uint8_t first_hook_live[16];
	std::uint8_t first_hook_disk[16];
	std::uint8_t tag[kMacSize];
};

struct ServerReady {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint32_t build_id;
	std::uint64_t session_id;
	std::uint8_t tag[kMacSize];
};

struct ServerChallenge {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint32_t sequence;
	std::uint16_t type;
	std::uint16_t reserved;
	std::uint8_t nonce[kNonceSize];
	std::uint8_t tag[kMacSize];
};

struct ClientChallenge {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint32_t sequence;
	std::uint8_t nonce[kNonceSize];
	std::uint8_t module_digest[kDigestSize];
	std::uint16_t module_count;
	std::uint16_t unknown_module_count;
	std::uint32_t unknown_module_size;
	char unknown_module_name[kModuleNameSize];
	std::uint8_t unknown_module_text_digest[kDigestSize];
	std::uint8_t memory_digest[kDigestSize];
	std::uint16_t private_exec_region_count;
	std::uint16_t unlinked_exec_region_count;
	std::uint16_t suspicious_thread_count;
	std::uint16_t runtime_reserved;
	std::uint32_t first_private_region_size;
	std::uint32_t first_private_region_protect;
	std::uint32_t first_suspicious_thread_id;
	std::uint32_t first_suspicious_region_type;
	std::uint8_t text_sample_digest[kDigestSize];
	std::uint16_t text_mismatch_count;
	std::uint16_t text_slice_count;
	std::uint32_t text_checked_bytes;
	std::uint32_t first_text_mismatch_offset;
	std::uint8_t first_text_mismatch_module;
	std::uint8_t text_reserved[3];
	std::uint8_t asset_sample_digest[kDigestSize];
	std::uint16_t asset_mismatch_count;
	std::uint16_t asset_module_sample_count;
	std::uint16_t asset_grf_sample_count;
	std::uint16_t asset_loose_sample_count;
	std::uint32_t asset_checked_bytes;
	std::uint32_t first_asset_mismatch_index;
	std::uint8_t first_asset_mismatch_kind;
	std::uint8_t asset_reserved[3];
	std::uint8_t debug_digest[kDigestSize];
	std::uint16_t debugger_flags;
	std::uint16_t hardware_breakpoint_count;
	std::uint16_t debug_threads_checked;
	std::uint16_t suspicious_handle_count;
	std::uint16_t external_handle_count;
	std::uint16_t debug_scan_flags;
	std::uint32_t first_hardware_thread_id;
	std::uint32_t first_hardware_dr7;
	std::uint32_t first_handle_owner_pid;
	std::uint32_t first_handle_access;
	std::uint8_t hook_digest[kDigestSize];
	std::uint16_t hook_mismatch_count;
	std::uint16_t hook_checked_count;
	std::uint16_t hook_unresolved_count;
	std::uint16_t hook_scan_flags;
	std::uint16_t first_hook_target;
	std::uint16_t hook_reserved;
	std::uint8_t first_hook_live[16];
	std::uint8_t first_hook_disk[16];
	std::uint8_t tag[kMacSize];
};

struct EnvelopePrefix {
	std::uint16_t packet_id;
	std::uint16_t packet_length;
	std::uint32_t sequence;
	std::uint16_t inner_length;
	std::uint16_t reserved;
};

#pragma pack(pop)

static_assert(sizeof(ClientProbe) == 8, "Riftlock ClientProbe ABI mismatch");
static_assert(sizeof(ServerHello) == 140, "Riftlock ServerHello ABI mismatch");
static_assert(sizeof(ClientHello) == 532, "Riftlock ClientHello ABI mismatch");
static_assert(sizeof(ServerReady) == 32, "Riftlock ServerReady ABI mismatch");
static_assert(sizeof(ServerChallenge) == 60, "Riftlock ServerChallenge ABI mismatch");
static_assert(sizeof(ClientChallenge) == 484, "Riftlock ClientChallenge ABI mismatch");
static_assert(sizeof(EnvelopePrefix) == 12, "Riftlock EnvelopePrefix ABI mismatch");

} // namespace riftlock
