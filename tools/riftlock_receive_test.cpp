#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include "../CustomDLL/src/riftlock/riftlock_receive.hpp"
using Bytes = std::vector<std::uint8_t>;
struct Reader {
	Bytes queue;
	std::vector<Bytes> native;
	std::vector<std::uint16_t> controls;
	bool failed = false;
	bool reject_control = false;
	bool peek(std::size_t count, void* out) {
		if (queue.size() < count) return false;
		memcpy(out, queue.data(), count); return true;
	}
	bool read(std::size_t count, void* out) {
		if (!peek(count, out)) return false;
		queue.erase(queue.begin(), queue.begin() + count); return true;
	}
	bool next() {
		if (failed) return false;
		return riftlock_receive::read_packet(
			[&](std::size_t n, void* out) { return peek(n, out); },
			[&](std::size_t n, void* out) { return read(n, out); },
			[&](const std::uint8_t* p, std::size_t) {
				if (reject_control) { failed = true; return false; }
				std::uint16_t id; memcpy(&id, p, 2); controls.push_back(id); return true;
			},
			[&]() {
				std::uint16_t id; assert(peek(2, &id));
				std::uint16_t size = 6;
				if (id == 0x0bb7) {
					std::uint16_t header[2]; if (!peek(4, header)) return false;
					size = header[1]; // Stands in for the stock custom-length reader.
				}
				Bytes packet(size); if (!read(size, packet.data())) return false;
				native.push_back(packet); return true;
			},
			[&]() { failed = true; });
	}
	void feed(const Bytes& bytes) {
		queue.insert(queue.end(), bytes.begin(), bytes.end());
		while (next()) {}
	}
};
Bytes control(std::uint16_t id) {
	Bytes p(riftlock_receive::control_size(id), 0);
	const auto len = static_cast<std::uint16_t>(p.size());
	memcpy(p.data(), &id, 2); memcpy(p.data()+2, &len, 2); return p;
}
Bytes concat(const std::vector<Bytes>& packets) {
	Bytes out; for (const auto& p : packets) out.insert(out.end(), p.begin(), p.end()); return out;
}
void test_raw_character_bootstrap() {
	const auto hello = control(riftlock::kServerHello), ready = control(riftlock::kServerReady);
	// An account ID whose low word is 0x0CF0 must remain opaque after READY.
	const Bytes aid = {0xf0,0x0c,0x34,0x12};
	const Bytes stream = concat({hello,ready,aid});
	for (std::size_t split = 0; split <= stream.size(); ++split) {
		Reader r; bool active = false; unsigned controls = 0; Bytes result;
		auto drain = [&]() {
			const bool complete = riftlock_receive::finish_handshake(
				[&](std::size_t n, void* out) { return r.peek(n,out); },
				[&](std::size_t n, void* out) { return r.read(n,out); },
				[&](const std::uint8_t* p, std::size_t) { ++controls; if (p[0]==0xf5) active=true; return true; },
				[&]() { return active; }, [&]() { r.failed=true; });
			if (complete && r.queue.size()>=4) { result.resize(4); assert(r.read(4,result.data())); }
		};
		r.queue.assign(stream.begin(),stream.begin()+split); drain();
		r.queue.insert(r.queue.end(),stream.begin()+split,stream.end()); drain();
		assert(!r.failed && controls==2 && result==aid && r.queue.empty());
	}
	Reader r; r.queue=hello; bool active=false;
	assert(!riftlock_receive::finish_handshake([&](std::size_t n,void* out){return r.peek(n,out);},
		[&](std::size_t n,void* out){return r.read(n,out);},[](const std::uint8_t*,std::size_t){return false;},
		[&](){return active;},[&](){r.failed=true;}));
	puts("PASS raw character bootstrap: all 177 split points, opaque control-looking account ID, rejected handshake");
}

int main() {
	test_raw_character_bootstrap();
	const Bytes fixed = {0x7f,0,1,2,3,4};
	// Control-looking payload bytes must never be scanned/intercepted.
	const Bytes variable = {0xb7,0x0b,12,0,0xf2,0x0c,60,0,0xf5,0x0c,32,0};
	const auto hello = control(riftlock::kServerHello);
	const auto ready = control(riftlock::kServerReady);
	const auto challenge = control(riftlock::kServerChallenge);
	assert(hello.size()==140 && ready.size()==32 && challenge.size()==60);
	unsigned split_cases = 0;
	for (const auto& packets : std::vector<std::vector<Bytes>>{
		{hello,ready}, {challenge,challenge}, {fixed,challenge}, {challenge,fixed},
		{variable,challenge,fixed,challenge}, {hello,ready,fixed,variable,challenge}}) {
		const Bytes stream = concat(packets);
		Reader expected; expected.feed(stream);
		assert(!expected.failed && expected.queue.empty());
		std::vector<Bytes> want_native; std::vector<std::uint16_t> want_controls;
		for (const auto& p : packets) {
			if (p==fixed || p==variable) want_native.push_back(p);
			else { std::uint16_t id; memcpy(&id,p.data(),2); want_controls.push_back(id); }
		}
		assert(expected.native==want_native && expected.controls==want_controls);
		for (std::size_t split = 0; split <= stream.size(); ++split) {
			Reader r; r.feed(Bytes(stream.begin(),stream.begin()+split));
			r.feed(Bytes(stream.begin()+split,stream.end()));
			assert(!r.failed && r.queue.empty());
			assert(r.controls == expected.controls && r.native == expected.native); ++split_cases;
		}
		Reader bytewise;
		for (const auto byte : stream) bytewise.feed(Bytes{byte});
		assert(bytewise.controls == expected.controls && bytewise.native == expected.native);
	}
	Reader embedded; embedded.feed(variable);
	assert(embedded.controls.empty() && embedded.native == std::vector<Bytes>{variable});
	for (const std::uint16_t bad : std::vector<std::uint16_t>{0,2,4,59,61,65535}) {
		Reader r; Bytes packet = challenge; memcpy(packet.data()+2,&bad,2); r.feed(packet);
		assert(r.failed && r.native.empty() && r.controls.empty());
	}
	Reader rejected; rejected.reject_control = true; rejected.feed(concat({challenge,fixed}));
	assert(rejected.failed && rejected.native.empty());
	// A partial control is retained unchanged; reset/reconnect discards the old queue.
	Reader partial; partial.feed(Bytes(challenge.begin(),challenge.begin()+1));
	assert(partial.queue.size()==1 && partial.native.empty() && partial.controls.empty());
	partial = Reader{}; partial.feed(concat({hello,ready,fixed}));
	assert(partial.controls.size()==2 && partial.native.size()==1);
	printf("PASS framing: %u two-chunk splits, 6 bytewise streams, payload IDs, malformed lengths, rejected control, reconnect\n",split_cases);
}
