// Exercise real research definitions and WAL. Only allocator/log boundaries are substituted.
#include <common/bestiary_definitions.hpp>
#include <map/bestiary_journal.hpp>
#include <common/showmsg.hpp>
#include <cassert>
#include <fstream>
#include <iostream>
#include <thread>
#include <cstdarg>
void* _mmalloc(size_t n,const char*,int32,const char*){auto p=std::malloc(n);if(!p)throw std::bad_alloc();return p;}
void _mfree(void* p,const char*,int32,const char*){std::free(p);}
int32 _vShowMessage(msg_type,const char*,va_list){return 0;}
void ShowMessage(const char*,...){} void ShowStatus(const char*,...){}
void ShowError(const char*,...){} void ShowWarning(const char*,...){}
extern void do_init_database();
char db_path[12]="db";
using namespace bestiary_research;

namespace capture_fixture {
struct block_list { int m=1,x=0,y=0; };
struct map_session_data : block_list {
 struct {uint32_t account_id=2000000,party_id=0;} status;
 struct {bool active=true;} state;
 int fd=1;bool dead=false;
};
struct mob_data : block_list {
 Origin research_origin=Origin::Registered;
 void* spawn=this;uint32_t master_id=0,mob_id=1002;
 struct {int ai=0;} special_state;
 void* guardian_data=nullptr;
 struct Db {uint64_t base_exp=10,job_exp=1;} database;
 Db* db=&database;
};
struct Map {int instance_id=0;} map;
Map* map_getmapdata(int){return &map;}
bool pc_isdead(map_session_data* sd){return sd->dead;}
bool mob_is_clone(uint32_t id){return id==3999;}
constexpr int AREA_SIZE=14,BL_PC=1;
std::vector<map_session_data*> nearby;
Definitions* definitions=nullptr;bool enabled=true;
int invoke(int (*fn)(block_list*,va_list),block_list* bl,...){va_list ap;va_start(ap,bl);int result=fn(bl,ap);va_end(ap);return result;}
void map_foreachinallrange(int (*fn)(block_list*,va_list),mob_data* mob,int radius,int,uint32_t party,std::set<uint32_t>* accounts){
 for(auto* sd:nearby)if(sd->m==mob->m && std::abs(sd->x-mob->x)<=radius && std::abs(sd->y-mob->y)<=radius)invoke(fn,sd,party,accounts);
}
#include "capture-under-test.inc"
void test(Definitions& db){
 definitions=&db;mob_data mob;map_session_data solo,same_account,support,dead,distant,offline,other_party,other_map;
 auto credits=capture(&mob,{&solo},true);assert(credits.size()==1 && credits[0].account==solo.status.account_id && credits[0].kills==1);
 solo.status.party_id=7;same_account.status.party_id=7;support.status={2000001,7};dead.status={2000002,7};dead.dead=true;
 distant.status={2000003,7};distant.x=15;offline.status={2000004,7};offline.fd=0;other_party.status={2000005,8};other_map.status={2000006,7};other_map.m=2;
 nearby={&same_account,&support,&dead,&distant,&offline,&other_party,&other_map};
 credits=capture(&mob,{&solo,&same_account,&solo},true);assert(credits.size()==2 && credits[0].account==2000000 && credits[1].account==2000001);
 assert(capture(&mob,{},true).empty());assert(capture(&mob,{&solo},false).empty());assert(capture(nullptr,{&solo},true).empty());
 for(auto origin:{Origin::Unknown,Origin::Script,Origin::Player,Origin::Summoned,Origin::Clone}){mob.research_origin=origin;assert(capture(&mob,{&solo},true).empty());}mob.research_origin=Origin::Registered;
 mob.master_id=1;assert(capture(&mob,{&solo},true).empty());mob.master_id=0;
 mob.spawn=nullptr;assert(capture(&mob,{&solo},true).empty());mob.spawn=&mob;
 mob.guardian_data=&mob;assert(capture(&mob,{&solo},true).empty());mob.guardian_data=nullptr;
 mob.special_state.ai=1;assert(capture(&mob,{&solo},true).empty());mob.special_state.ai=0;
 map.instance_id=1;assert(capture(&mob,{&solo},true).empty());map.instance_id=0;
 mob.database.base_exp=mob.database.job_exp=0;assert(capture(&mob,{&solo},true).empty());mob.database.base_exp=1;
 mob.mob_id=3999;assert(capture(&mob,{&solo},true).empty());mob.mob_id=32766;assert(capture(&mob,{&solo},true).empty());mob.mob_id=1002;
 enabled=false;assert(capture(&mob,{&solo},true).empty());enabled=true;
 nearby.clear();assert(capture(&mob,{&dead,&offline,&other_map,nullptr},true).empty());
}
}
int main(int argc,char** argv){
	assert(argc==3);do_init_database();std::filesystem::current_path(argv[1]);
	Definitions definitions;assert(definitions.load()&&definitions.validate());assert(definitions.monsters.count(1002));
	capture_fixture::test(definitions);
	assert(definitions.monster_tier(1002,0)==0 && definitions.monster_tier(1002,1)==1 && definitions.monster_tier(1002,25)==2 && definitions.monster_tier(1002,1500)==5);
	const auto fingerprint=definitions.fingerprint();assert(fingerprint);definitions.curves.at(1).kills[1]++;assert(definitions.fingerprint()!=fingerprint);definitions.curves.at(1).kills[1]--;
	auto milestones=definitions.milestones({{1002,25},{1113,1},{1031,1}});bool group=false;for(auto e:milestones)if(e.source==2&&e.target==1&&e.tier==1)group=true;assert(group);
	assert(!valid_curve({1,1,2,3,4}));assert(origin_allowed(Origin::Registered,false,false,false));assert(!origin_allowed(Origin::Summoned,false,true,true));assert(!origin_allowed(Origin::Registered,true,false,false));
	const std::filesystem::path root=argv[2];std::filesystem::create_directories(root);
	Record r;r.account=2000000;r.mob=1002;r.occurred=1800000000;
	Journal first;assert(first.open(root/"replay"));Journal locked;assert(!locked.open(root/"replay"));
	std::vector<std::thread> producers;
	for(int i=0;i<4;++i)producers.emplace_back([&]{for(int j=0;j<64;++j)assert(first.enqueue({r}));});
	for(auto& thread:producers)thread.join();assert(first.flush());auto initial=first.batch();assert(initial.size()==256);const auto stream=first.stream();
	for(size_t i=0;i<initial.size();++i)assert(initial[i].sequence==i+1);
	assert(!first.acknowledge(257));first.close();
	Journal replay;assert(replay.open(root/"replay"));assert(replay.stream()==stream && replay.batch().size()==256);
	size_t begin=0;assert(new_records(replay.batch(),128,begin)==Result::Ok && begin==128);
	auto gap=replay.batch();gap.front().sequence=2;assert(new_records(gap,0,begin)==Result::Invalid);
	gap={initial.back()};assert(new_records(gap,0,begin)==Result::Gap);
	assert(replay.acknowledge(256));assert(replay.enqueue({r}));assert(replay.flush());auto next=replay.batch();assert(next.size()==1 && next[0].sequence==257);replay.close();
	// The same object can reopen after shutdown without retaining queue/error state.
	assert(replay.open(root/"replay"));assert(replay.batch().back().sequence==257);replay.close();
	{std::ofstream tail(root/"replay/research.wal",std::ios::binary|std::ios::app);tail.write("partial",7);}
	Journal torn;assert(torn.open(root/"replay"));assert(torn.batch().back().sequence==257);torn.close();
	{std::fstream corrupt(root/"replay/research.wal",std::ios::binary|std::ios::in|std::ios::out);corrupt.seekp(48);char c=0x7f;corrupt.write(&c,1);}
	Journal corrupt;assert(!corrupt.open(root/"replay"));assert(!corrupt.error().empty());
	Journal bounded;assert(bounded.open(root/"bounded"));size_t accepted=0;std::vector<Record> chunk(256,r);
	while(bounded.enqueue(chunk))accepted+=chunk.size();assert(accepted==max_backlog);assert(bounded.flush());assert(bounded.pending()==max_backlog);
	while(!bounded.batch().empty()){const auto batch=bounded.batch();assert(bounded.acknowledge(batch.back().sequence));}
	assert(bounded.enqueue({r})&&bounded.flush());bounded.close();
	Journal recovered;assert(recovered.open(root/"bounded"));assert(recovered.batch().back().sequence==max_backlog+1);recovered.close();
	std::cout<<"Passed: actual solo/support-party capture, account deduplication, death/spawn/instance/clone exclusions; roster/tier boundaries, fingerprint, group minimum, concurrent producers, file lock, durable replay, gap rejection, checkpoint/reopen, torn tail, corruption and bounded queue recovery.\n";
}
