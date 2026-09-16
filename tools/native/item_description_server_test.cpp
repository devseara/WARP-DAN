// Executes the real descriptor parser, shared wire validation and identity logic.
#include <algorithm>
#include <cassert>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <common/database.hpp>
#include <common/showmsg.hpp>
#include <common/malloc.hpp>
#include <common/mmo.hpp>
#include <common/item_description_wire.hpp>
namespace w = item_description_wire;
void* _mmalloc(size_t n,const char*,int32,const char*){auto p=std::malloc(n);if(!p)throw std::bad_alloc();return p;}
void _mfree(void* p,const char*,int32,const char*){std::free(p);}
int32 _vShowMessage(msg_type,const char*,va_list){return 0;}
void ShowMessage(const char*,...){} void ShowStatus(const char*,...){}
void ShowError(const char*,...){} void ShowWarning(const char*,...){}
extern void do_init_database();
char db_path[12]=".";
struct Lookup { std::set<uint32> ids; std::shared_ptr<int> find(uint32 id) { return ids.count(id)?std::make_shared<int>(1):nullptr; } };
Lookup item_db{{1201,1202,4001,4140}},random_option_db{{1,2}};
#include "item_description_under_test.inc"
struct map_session_data {
    struct { bool active = true; } state;
    uint32 item_description_request_id[2]{}, item_description_item_id[2]{};
    int item_description_index[2]{-1,-1};
    uint64 item_description_fingerprint[2]{};
    struct { struct { item items_inventory[MAX_INVENTORY]{}; } u; } inventory;
};
std::vector<w::Snapshot> invalidations;
void initialize(w::Snapshot& s,const w::Request& r) { w::zero(s);s.request_id=r.request_id;s.item_id=r.item_id;s.client_index=r.client_index;s.scope=r.scope; }
void send(map_session_data*,const w::Snapshot& s) { invalidations.push_back(s); }
#include "item_description_watch_under_test.inc"
static void write(const std::string& text){std::ofstream("item_description_db.yml",std::ios::binary)<<text;}
int main(int argc,char**argv){
    assert(argc==3);std::filesystem::current_path(argv[1]);do_init_database();
    static_assert(offsetof(w::Request,options)==48 && offsetof(w::Request,known_fingerprint)==76,"request offsets");
    static_assert(offsetof(w::Snapshot,rows)==128 && offsetof(w::Row,text)==64,"snapshot offsets");
    item actual{};actual.nameid=1201;actual.amount=1;actual.identify=1;actual.refine=7;actual.enchantgrade=2;
    actual.card[0]=4001;actual.option[0]={1,7,0};actual.unique_id=123456;
    w::Request r{};r.packet_type=w::request_packet;r.packet_length=sizeof(r);r.magic=w::magic;r.version=w::version;r.message=w::inspect;
    r.request_id=1;r.item_id=1201;r.client_index=7;r.scope=w::inventory;r.refine=7;r.grade=2;r.identified=1;r.cards[0]=4001;r.options[0]={1,7,0};r.option_count=5;
    assert(w::request_valid(r)&&matches(actual,r));
    for(int field=0;field<9;++field){auto changed=actual;switch(field){
        case 0:changed.nameid=1202;break;case 1:changed.refine=8;break;case 2:changed.enchantgrade=3;break;
        case 3:changed.card[0]=4140;break;case 4:changed.option[0].value=8;break;case 5:changed.option[0].id=2;break;
        case 6:changed.option[0].param=1;break;case 7:changed.identify=0;break;case 8:changed.amount=0;break;}
        assert(!matches(changed,r));}
    const auto hash=fingerprint(actual);r.known_fingerprint=hash;assert(matches(actual,r));
    auto changed=actual;changed.unique_id++;assert(!matches(changed,r));changed=actual;changed.bound=1;assert(fingerprint(changed)!=hash);
    changed=actual;changed.equip=2;assert(fingerprint(changed)!=hash);changed=actual;changed.amount=2;assert(fingerprint(changed)!=hash);
    r.known_fingerprint=0;
    for(int field=0;field<8;++field){auto invalid=r;switch(field){case 0:invalid.version=9;break;case 1:invalid.option_count=6;break;
        case 2:invalid.scope=2;break;case 3:invalid.client_index=1;break;case 4:invalid.reserved0=1;break;case 5:invalid.message=99;break;
        case 6:invalid.packet_length--;break;case 7:invalid.request_id=0;break;}assert(!w::request_valid(invalid));}
    Effect set;set.required_cards={4001,4001};assert(!predicate(set,actual));actual.card[1]=4001;assert(predicate(set,actual));set.min_refine=8;assert(!predicate(set,actual));
    const std::string header="Header:\n  Type: ITEM_DESCRIPTION_DB\n  Version: 1\n";
    const auto good=header+"Body:\n  - Id: 1201\n    Rarity: Rare\n    Effects:\n      - Section: NativeEffects\n        MinRefine: 7\n        RequiredCards: [4001]\n        Text: Accurate configured effect\n  - Id: 1\n    Kind: RandomOption\n    Label: Attack\n    Effects:\n      - Text: ATK +{value}%\n";
    write(good);auto current=std::make_unique<DescriptionDatabase>();assert(current->load()&&current->valid&&current->size()==2);
    assert(current->find(1201)->effects[0].min_refine==7&&current->find(option_key|1)->label=="Attack");
    unsigned rejected=0;
    for(const auto& bad:std::vector<std::string>{
        "Header: [broken\n",header+"Body: invalid\n",header+"Body:\n  - Id: 9999\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Text: \"a\\0b\"\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Section: Fake\n        Text: bad\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Text: bad\n        RequiredCards: [9999]\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Text: bad\n        RequiredCards: [-1]\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Text: bad\n        RequiredCards: [42949672960]\n",
        header+"Body:\n  - Id: 1201\n    Effects:\n      - Text: "+std::string(2049,'x')+"\n",
        header+"Footer:\n  Imports:\n    - Path: missing.yml\n"}){
        write(bad);auto candidate=std::make_unique<DescriptionDatabase>();if(!candidate->load()||!candidate->valid)++rejected;else assert(false&&"invalid descriptor accepted");
        assert(current->find(1201)->effects[0].text=="Accurate configured effect");}
    assert(rejected==10);write(good);auto recovery=std::make_unique<DescriptionDatabase>();assert(recovery->load());
    w::Snapshot snapshot{};Builder builder{snapshot};Descriptor descriptor;Effect effect;effect.text=std::string(2048,'x');descriptor.effects.assign(64,effect);
    append_effects(builder,descriptor,actual,true);assert(snapshot.row_count<=44&&(snapshot.flags&w::truncated));
    builder.row(w::restrictions,"Storage","No");assert(snapshot.rows[snapshot.row_count-1].section==w::restrictions);
    w::zero(snapshot);Builder b{snapshot};append_effects(b,*current->find(option_key|1),actual,true,w::random_options,7);
    assert(std::string(snapshot.rows[0].text)=="ATK +7%");
    std::filesystem::current_path(argv[2]);
    std::ifstream ids("ids.txt");std::string line;std::getline(ids,line);std::istringstream item_ids(line);uint32 id;
    while(item_ids>>id)item_db.ids.insert(id);
    std::getline(ids,line);std::istringstream option_ids(line);while(option_ids>>id)random_option_db.ids.insert(id);
    DescriptionDatabase generated;assert(generated.load()&&generated.valid&&generated.size()>2000);
    auto knife=generated.find(1201);assert(knife&&knife->effects.size()==4&&!knife->legacy);
    auto armor=generated.find(2315);assert(armor&&armor->effects.size()==4);
    for (int grade=0;grade<=5;++grade) {
        actual.enchantgrade=grade;w::zero(snapshot);Builder gb{snapshot};append_effects(gb,*knife,actual,true);
        unsigned active=0;for(unsigned i=0;i<snapshot.row_count;++i) {
            const auto& row=snapshot.rows[i];assert(row.section==w::grade);
            if(row.flags&w::active){++active;assert(std::string(row.text)==std::string("ATK +")+(grade==1?"1%":grade==2?"2%":grade==3?"3%":"5%"));}
        }
        assert(active==(grade?1:0));
    }
    for (auto sample : std::vector<std::pair<int,std::string>>{{4,"AGI +4"},{170,"Cast time -4%"},{257,"Weight capacity +0.4"},{259,"Stun resistance +0.04%"}}) {
        auto option=generated.find(option_key|sample.first);assert(option);w::zero(snapshot);Builder ob{snapshot};append_effects(ob,*option,actual,true,w::random_options,4);
        assert(std::string(snapshot.rows[0].text).find(sample.second)!=std::string::npos);
    }
    auto option=generated.find(option_key|4);w::zero(snapshot);Builder negative{snapshot};append_effects(negative,*option,actual,true,w::random_options,-4);
    assert(std::string(snapshot.rows[0].text)=="AGI -4");
    auto apple=generated.find(2285);assert(apple&&!apple->legacy&&apple->effects.size()==6);
    for(int grade=0;grade<=5;++grade) {
        actual.enchantgrade=grade;w::zero(snapshot);Builder ab{snapshot};append_effects(ab,*apple,actual,true);
        assert(std::string(snapshot.rows[0].text)=="DEX +3");unsigned active=0;
        for(unsigned n=1;n<snapshot.row_count;++n) if(snapshot.rows[n].flags&w::active) {
            ++active;assert(std::string(snapshot.rows[n].text)=="Ranged physical damage +"+std::to_string(grade)+"%");
        }
        assert(active==(grade?1:0));
    }
    auto angra=generated.find(1599);assert(angra&&!angra->legacy&&angra->effects.size()==16);
    actual.nameid=1599;actual.enchantgrade=0;w::zero(snapshot);Builder angra_rows{snapshot};
    append_effects(angra_rows,*angra,actual,true);
    unsigned native_rows=0,grade_rows=0;bool hp=false,sp=false;unsigned grants=0;
    for(unsigned i=0;i<snapshot.row_count;++i) {
        const auto& row=snapshot.rows[i];std::string text=row.text;
        if(row.section==w::native_effects) {++native_rows;assert(!(row.flags&w::unknown));}
        if(row.section==w::grade){++grade_rows;assert(row.flags&w::unmet);}
        if(text=="100% chance to drain HP equal to 100% of damage dealt when attacking")hp=true;
        if(text=="100% chance to drain SP equal to 20% of damage dealt when attacking")sp=true;
        if(text.find("Enables ")==0)++grants;
    }
    assert(native_rows==12&&grade_rows==4&&hp&&sp&&grants==4&&!(snapshot.flags&w::truncated));
    std::cout<<"PASS: Angra Manyu emits all 12 base-script effects and four grade previews without fallback or truncation.\n";
    auto invalid_option=generated.find(option_key|260);assert(invalid_option&&invalid_option->effects[0].unknown);
    assert(generated.find(4001));
    write(header+"Body:\n  - Id: 1201\n    Effects:\n      - Section: Grade\n        MinGrade: 3\n        MaxGrade: 2\n        Text: invalid range\n");
    DescriptionDatabase invalid_range;assert(!invalid_range.load()||!invalid_range.valid);
    map_session_data session;
    for(unsigned view=0;view<2;++view) {
        session.item_description_request_id[view]=7|(view<<31);session.item_description_item_id[view]=actual.nameid;
        session.item_description_index[view]=view+5;session.inventory.u.items_inventory[view+5]=actual;
        session.item_description_fingerprint[view]=fingerprint(actual);
    }
    invalidate(&session,-1,false);assert(invalidations.empty());
    ++session.inventory.u.items_inventory[6].refine;invalidate(&session,6,false);
    assert(invalidations.size()==1&&invalidations[0].request_id==0x80000007&&invalidations[0].client_index==8);
    assert(session.item_description_request_id[0]==7&&!session.item_description_request_id[1]);
    session.item_description_request_id[1]=0x80000008;invalidate(&session,-1,true);
    assert(invalidations.size()==3&&invalidations[1].request_id==7&&invalidations[2].request_id==0x80000008);
    std::cout<<"PASS: actual two-view invalidation targets only the changed item and reload invalidates both snapshots.\n";
    std::cout<<"PASS: complete generated metadata through real YAML loader; exclusive grade tiers 0..5; signed, negated and fractional option values; invalid option definitions stay unknown; invalid grade ranges rejected.\n";
    std::cout<<"PASS: shared wire offsets, malformed requests, duplicate item identity, unique/bound/equip fingerprint, duplicate card predicates, real strict YAML parser, transactional reload recovery, bounded rows and option substitution.\n";
}
