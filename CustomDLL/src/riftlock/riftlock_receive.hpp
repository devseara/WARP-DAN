#pragma once
#include <cstdint>
#include "riftlock_protocol.h"

namespace riftlock_receive {

inline std::uint16_t control_size(std::uint16_t opcode) {
	switch (opcode) {
		case riftlock::kServerHello: return sizeof(riftlock::ServerHello);
		case riftlock::kServerReady: return sizeof(riftlock::ServerReady);
		case riftlock::kServerChallenge: return sizeof(riftlock::ServerChallenge);
		default: return 0;
	}
}

/// Inspect only the head of the native queue. Ordinary packets are consumed
/// exclusively by the original reader, including its custom-length adapters.
/// Peek/read must leave partial packets queued and preserve the stock ABI.
template <typename Peek, typename Read, typename Control, typename Native, typename Fail>
bool read_packet(Peek&& peek, Read&& read, Control&& control, Native&& native, Fail&& fail) {
	for (;;) {
		std::uint16_t opcode = 0;
		if (!peek(sizeof(opcode), &opcode)) return false;
		const std::uint16_t expected = control_size(opcode);
		if (expected == 0) return native();
		std::uint16_t header[2] = {};
		if (!peek(sizeof(header), header)) return false;
		if (header[1] != expected) {
			fail();
			return false;
		}
		std::uint8_t packet[sizeof(riftlock::ServerHello)] = {};
		if (!read(expected, packet)) return false;
		if (!control(packet, expected)) return false;
	}
}

/// Character authentication reads a raw four-byte account-ID prelude before
/// entering the framed packet loop. Drain only handshake controls here and
/// stop immediately at ACTIVE: the opaque account ID may look like a control ID.
template <typename Peek, typename Read, typename Control, typename Active, typename Fail>
bool finish_handshake(Peek&& peek, Read&& read, Control&& control, Active&& active, Fail&& fail) {
	while (!active()) {
		std::uint16_t header[2] = {};
		if (!peek(sizeof(header), header)) return false;
		const std::uint16_t expected = control_size(header[0]);
		if (expected == 0 || header[1] != expected) { fail(); return false; }
		std::uint8_t packet[sizeof(riftlock::ServerHello)] = {};
		if (!read(expected, packet)) return false;
		if (!control(packet, expected)) return false;
	}
	return true;
}

} // namespace riftlock_receive
