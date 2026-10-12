// Exercise real research definitions and WAL. Only allocator/log boundaries are substituted.
#include <common/bestiary_definitions.hpp>
#include <map/bestiary_journal.hpp>
#include <map/bestiary_research.hpp>
#include <atomic>
#include <cstring>
#include <common/showmsg.hpp>
#include <cassert>
#include <fstream>
#include <iostream>
#include <thread>
#include <cstdarg>
#include <memory>
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

namespace title_fixture {
struct s_title_bonus_db { int32 icon=1; };
struct map_session_data {
 int fd=1;uint32 account=1;
 struct {int32 title_id=0;char name[24]="Researcher";} status;
 struct {int32 mvp_ranking_title_display=0;} state;
 std::vector<uint16> titles;
};
struct User {std::vector<AccountRow> rows;};
std::map<uint32,User> accounts;
std::map<uint16,std::shared_ptr<s_title_bonus_db>> titles;
bool enabled=true;
User& user(map_session_data* sd){return accounts[sd->account];}
std::shared_ptr<s_title_bonus_db> title_get_entry(uint16 id){auto it=titles.find(id);return it==titles.end()?nullptr:it->second;}
std::vector<std::pair<int32,int32>> acknowledgements;
void clif_change_title_ack(map_session_data*,int32 result,int32 id){acknowledgements.emplace_back(result,id);}
enum efst_type {EFST_BLANK=0};
constexpr int SCO_FORCE=1,SCO_NONE=0,INFINITE_TICK=-1;
void clif_status_change(map_session_data*,efst_type,int,int,int,int,int){}
void mvp_ranking_on_title_changed(map_session_data* sd){sd->state.mvp_ranking_title_display=0;}
void mvp_ranking_reapply_ladder_status(map_session_data*){}
void status_calc_pc(map_session_data*,int){}
void clif_name_area(map_session_data*){}
#define nullpo_retv(ptr) if(!(ptr))return
#include "title-projection-under-test.inc"
#include "title-equip-under-test.inc"
#undef nullpo_retv
void test(){
 for(uint16 id:{1000,1002,1003,1004,1025,1035})titles[id]=std::make_shared<s_title_bonus_db>();
 for(uint32 id:{1002,1003,1004,1025,1035})accounts[1].rows.push_back({4,id,2});
 accounts[1].rows.push_back({4,1002,2});accounts[1].rows.push_back({4,60000,2});accounts[1].rows.push_back({4,1000,1});
 map_session_data first,second,foreign;first.titles={1000};foreign.account=2;
 project_titles(&first);project_titles(&first);project_titles(&second);project_titles(&foreign);
 assert(first.titles.size()==6 && second.titles.size()==5 && foreign.titles.empty());
 clif_change_title(&first,1004);assert(first.status.title_id==1004 && acknowledgements.back().first==0);
 clif_change_title(&foreign,1004);assert(foreign.status.title_id==0 && acknowledgements.back().first==1);
 clif_change_title(&first,70000);assert(first.status.title_id==1004 && acknowledgements.back().first==1);
 clif_change_title(&first,0);assert(first.status.title_id==0 && acknowledgements.back().first==0);
 first.titles.clear();project_titles(&first);clif_change_title(&first,1002);assert(first.status.title_id==1002);
 second.fd=0;second.titles.clear();project_titles(&second);assert(second.titles.empty());
}
}

namespace reward_view_fixture {
using namespace bestiary_research;
using t_tick=int64_t;
struct map_session_data {struct {uint32_t title_id=0;} status;};
struct Item {std::string name,ename;};
struct ItemDatabase {std::map<uint32_t,std::shared_ptr<Item>> rows;std::shared_ptr<Item> find(uint32_t id){auto it=rows.find(id);return it==rows.end()?nullptr:it->second;}} item_db;
struct Title {std::string name;};
std::map<uint16_t,std::shared_ptr<Title>> title_rows;
std::shared_ptr<Title> title_get_entry(uint16_t id){auto it=title_rows.find(id);return it==title_rows.end()?nullptr:it->second;}
struct Mob {std::string display_name,jname;struct {uint32_t look[1]{};} vd;};
struct MobDatabase {std::shared_ptr<Mob> find(uint32_t){return nullptr;}} mob_db;
constexpr int LOOK_BASE=0,SELF=0;
struct JournalStub {std::string error(){return {};}size_t pending(){return 0;}} journal;
Definitions* definitions=nullptr;bool enabled=true;std::atomic<uint64_t> rejected{0};
bool link(){return true;}
std::map<std::pair<uint32_t,uint32_t>,const Reward*> entitlement_labels;
std::vector<uint8_t> output;
void clif_send(const void* p,size_t n,map_session_data*,int){const auto* b=static_cast<const uint8_t*>(p);output.assign(b,b+n);}
void safestrncpy(char* to,const char* from,size_t n){if(n){std::strncpy(to,from,n-1);to[n-1]=0;}}
#include "reward-view-under-test.inc"
void test(Definitions& database){
 definitions=&database;
 item_db.rows[504]=std::make_shared<Item>(Item{"White_Potion","White Potion"});
 item_db.rows[505]=std::make_shared<Item>(Item{"Blue_Potion","Blue Potion"});
 title_rows[1004]=std::make_shared<Title>(Title{"Grand Master"});
 assert(search_fold("  WhItE PoTiOn  ")=="white potion");
 assert(reward_matches(database.rewards.at(6),"504") && reward_matches(database.rewards.at(6),"white potion"));
 assert(!reward_matches(database.rewards.at(7),"white potion"));
 assert(!reward_matches(database.rewards.at(6),"0") && !reward_matches(database.rewards.at(6),"999999999999999999999999999"));
 map_session_data player;User u;u.ui=true;u.ready=true;u.dirty=false;u.query.base.tab=2;u.query.filter_flags=reward_preview_flag;
 u.rows.push_back({2,1002,1,5,10000,0});index(u);
 auto send=[&](const char* query,uint16_t view){std::memset(u.query.base.query,0,28);std::strncpy(u.query.base.query,query,27);u.query.race=view;u.query.base.page=0;transmit(&player,u);PersonalSnapshotV2 result{};std::memcpy(&result,output.data(),output.size());return result;};
 auto packet=send(" WhItE PoTiOn ",0);assert(output.size()==2440 && packet.base.message==10 && packet.base.count==2 && packet.base.pages==1);
 assert(packet.base.rows[0].id==6 && packet.base.rows[1].id==10 && packet.previews[0].count==5);
 assert(packet.previews[0].items[0].item_id==504 && packet.previews[0].items[0].quantity==20);
 for(size_t i=2;i<6;++i)assert(packet.previews[i].count==0);
 packet=send("504",0);assert(packet.base.count==2);
 packet=send("not-a-reward",0);assert(packet.base.count==0 && packet.base.pages==0 && packet.base.page==0);
 u.rows.push_back({3,6,1});index(u);packet=send("white potion",1);assert(packet.base.count==1 && packet.base.rows[0].id==10);
 packet=send("white potion",2);assert(packet.base.count==1 && packet.base.rows[0].id==6);
 packet=send("grand master",0);assert(packet.base.count==1 && packet.base.rows[0].id==14 && packet.previews[0].count==0);
 u.rows.push_back({4,1004,2});index(u);packet=send("Grand",3);assert(packet.base.count==1 && packet.base.rows[0].id==1004 && packet.base.rows[0].flags==8);
 u.query.filter_flags=0;packet=send("white potion",0);assert(output.size()==2176 && packet.base.message==9);
}
}

void bundle_definitions_test(const std::filesystem::path& root){
 const std::string base="Header:\n  Type: BESTIARY_RESEARCH_DB\n  Version: 1\nBody:\n"
 "- Kind: Curve\n  Id: 1\n  Tiers: [{Kills: 1, Points: 1}, {Kills: 2, Points: 1}, {Kills: 3, Points: 1}, {Kills: 4, Points: 1}, {Kills: 5, Points: 1}]\n"
 "- Kind: Monster\n  Id: 1002\n  Name: Poring\n  Curve: 1\n"
 "- Kind: Reward\n  Id: 1\n  Version: 1\n  Name: Bundle\n  Description: Supplies\n  Scope: Points\n  Target: 0\n  Required: 1\n";
 auto load=[&](const std::string& reward){const auto file=root/"bundle.yml";{std::ofstream f(file);f<<base<<reward;}Definitions db(file.string());return db.load()&&db.validate();};
 assert(load("  Items: [{Item: 501, Quantity: 1}, {Item: 601, Quantity: 100}]\n"));
 assert(load("  Item: 501\n  Quantity: 1\n"));
 for(const auto& value:{
 "  Items: []\n", "  Items: {Item: 501, Quantity: 1}\n",
 "  Items: [{Item: 501, Quantity: 0}]\n", "  Items: [{Item: 501, Quantity: 101}]\n",
 "  Items: [{Item: 0, Quantity: 1}]\n", "  Items: [{Item: 501, Quantity: 1}, {Item: 501, Quantity: 2}]\n",
 "  Item: 0\n  Items: [{Item: 501, Quantity: 1}]\n",
 "  Quantity: 0\n  Items: [{Item: 501, Quantity: 1}]\n",
 "  Items: [{Item: 501, Quantity: 1}, {Item: 502, Quantity: 1}, {Item: 503, Quantity: 1}, {Item: 504, Quantity: 1}, {Item: 505, Quantity: 1}, {Item: 506, Quantity: 1}]\n"
 })assert(!load(value));
}

int main(int argc,char** argv){
	assert(argc==3);do_init_database();std::filesystem::current_path(argv[1]);
	Definitions definitions;assert(definitions.load()&&definitions.validate());assert(definitions.monsters.count(1002));
	capture_fixture::test(definitions);title_fixture::test();reward_view_fixture::test(definitions);
	assert(definitions.rewards.at(1).items.size()==1 && definitions.rewards.at(1).items[0].id==601);
	assert(definitions.rewards.at(6).items.size()==5 && definitions.groups.size()>=12);
	const auto bundle_hash=definitions.fingerprint();definitions.rewards.at(6).items[0].quantity++;assert(definitions.fingerprint()!=bundle_hash);definitions.rewards.at(6).items[0].quantity--;
	assert(definitions.monster_tier(1002,0)==0 && definitions.monster_tier(1002,1)==1 && definitions.monster_tier(1002,25)==2 && definitions.monster_tier(1002,1500)==5);
	const auto fingerprint=definitions.fingerprint();assert(fingerprint);definitions.curves.at(1).kills[1]++;assert(definitions.fingerprint()!=fingerprint);definitions.curves.at(1).kills[1]--;
	auto milestones=definitions.milestones({{1002,25},{1113,1},{1031,1}});bool group=false;for(auto e:milestones)if(e.source==2&&e.target==1&&e.tier==1)group=true;assert(group);
	assert(!valid_curve({1,1,2,3,4}));assert(origin_allowed(Origin::Registered,false,false,false));assert(!origin_allowed(Origin::Summoned,false,true,true));assert(!origin_allowed(Origin::Registered,true,false,false));
	const std::filesystem::path root=argv[2];std::filesystem::create_directories(root);bundle_definitions_test(root);
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
	std::cout<<"Passed: real reward search/paging/preview serialization and legacy fallback; bundle bounds/duplicates/legacy compatibility, native title projection/equip/ownership; actual solo/support-party capture, account deduplication, death/spawn/instance/clone exclusions; roster/tier boundaries, fingerprint, group minimum, concurrent producers, file lock, durable replay, gap rejection, checkpoint/reopen, torn tail, corruption and bounded queue recovery.\n";
}
