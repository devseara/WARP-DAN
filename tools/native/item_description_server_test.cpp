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
#include <crtdbg.h>
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
    struct { bool active = true; int storage_flag = 0; } state;
    struct { int guild_id = 0; } status;
    uint32 item_description_request_id[2]{}, item_description_item_id[2]{};
    int item_description_index[2]{-1,-1};
    uint64 item_description_fingerprint[2]{};
    int64 item_description_next_request[2]{};
    struct { struct { item items_inventory[MAX_INVENTORY]{}; } u; } inventory;
    struct { struct { item items_cart[MAX_CART]{}; } u; } cart;
    s_storage storage{}, premiumStorage{};
};
s_storage test_guild_storage{};
s_storage* guild2storage2(int guild) { return guild == 7 ? &test_guild_storage : nullptr; }
std::vector<w::Snapshot> invalidations;
void initialize(w::Snapshot& s,const w::Request& r) { w::zero(s);s.request_id=r.request_id;s.item_id=r.item_id;s.client_index=r.client_index;s.scope=r.scope; }
void send(map_session_data*,const w::Snapshot& s) { invalidations.push_back(s); }
std::vector<map_session_data*> sessions;
void map_foreachpc(int32 (*callback)(map_session_data*, va_list)) {
    for (auto* session : sessions) { va_list unused{}; callback(session, unused); }
}
namespace item_description {
void invalidate(map_session_data*, int, bool);
#include "item_description_watch_under_test.inc"
}
int64 test_tick=1000;
int64 gettick() { return test_tick; }
#define DIFF_TICK(a,b) ((a)-(b))
struct BuildCapture { item value{}; bool actual=false, comparison=false; int index=-99, calls=0; } captured;
void build(Builder& b,map_session_data*,const int&,const item& value,bool actual,bool comparison,int index) {
    captured.value=value;captured.actual=actual;captured.comparison=comparison;captured.index=index;++captured.calls;
    b.s.refine=value.refine;b.s.grade=value.enchantgrade;b.s.fingerprint=fingerprint(value);
}
namespace item_description {
#include "item_description_request_under_test.inc"
}
using item_description::invalidate;
static void write(const std::string& text){std::ofstream("item_description_db.yml",std::ios::binary)<<text;}
int main(int argc,char**argv){
    _CrtSetReportMode(_CRT_ASSERT,_CRTDBG_MODE_FILE);_CrtSetReportFile(_CRT_ASSERT,_CRTDBG_FILE_STDERR);
    _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
    assert(argc==3);std::filesystem::current_path(argv[1]);do_init_database();
    static_assert(offsetof(w::Request,options)==48 && offsetof(w::Request,known_fingerprint)==76,"request offsets");
    static_assert(offsetof(w::Snapshot,rows)==128 && offsetof(w::Row,text)==64,"snapshot offsets");
    item actual{};actual.nameid=1201;actual.amount=1;actual.identify=1;actual.refine=7;actual.enchantgrade=2;
    actual.card[0]=4001;actual.option[0]={1,7,0};actual.unique_id=123456;
    w::Request r{};r.packet_type=w::request_packet;r.packet_length=sizeof(r);r.magic=w::magic;r.version=w::version;r.message=w::inspect;
    r.request_id=1;r.item_id=1201;r.client_index=7;r.scope=w::inventory;r.refine=7;r.grade=2;r.identified=1;r.cards[0]=4001;r.options[0]={1,7,0};r.option_count=5;
    assert(w::request_valid(r)&&matches(actual,r));
    // Execute the production container resolver and encoded watch ownership.
    auto owner=std::make_unique<map_session_data>();
    owner->inventory.u.items_inventory[5]=actual;owner->cart.u.items_cart[5]=actual;
    owner->storage.u.items_storage[5]=actual;owner->premiumStorage.u.items_storage[5]=actual;
    test_guild_storage.u.items_guild[5]=actual;
    assert(item_description::inspection_item(owner.get(),w::inventory,5)==&owner->inventory.u.items_inventory[5]);
    assert(item_description::inspection_item(owner.get(),w::cart,5)==&owner->cart.u.items_cart[5]);
    assert(!item_description::inspection_item(owner.get(),w::storage,5));
    for(int mode : {1,3,2}) {
        owner->state.storage_flag=mode;owner->status.guild_id=7;test_guild_storage.status=true;
        const auto* expected=mode==1?&owner->storage.u.items_storage[5]:mode==3?&owner->premiumStorage.u.items_storage[5]:&test_guild_storage.u.items_guild[5];
        assert(item_description::inspection_item(owner.get(),w::storage,5)==expected);
    }
    test_guild_storage.lock=true;assert(!item_description::inspection_item(owner.get(),w::storage,5));test_guild_storage.lock=false;
    owner->status.guild_id=8;assert(!item_description::inspection_item(owner.get(),w::storage,5));
    for(auto scope : {w::inventory,w::cart,w::storage}) {
        auto request=r;request.scope=scope;assert(w::request_valid(request));
        request.message=w::compare;assert(w::request_valid(request)==(scope==w::inventory));
        assert(!item_description::inspection_item(owner.get(),scope,-1));
        assert(!item_description::inspection_item(owner.get(),scope,65535));
        assert(item_description::watch_scope(item_description::watch_index(scope,5))==scope);
    }
    auto unknown_scope=r;unknown_scope.scope=4;assert(!w::request_valid(unknown_scope));
    owner->item_description_request_id[0]=21;owner->item_description_item_id[0]=actual.nameid;
    owner->item_description_index[0]=item_description::watch_index(w::cart,5);
    owner->item_description_fingerprint[0]=fingerprint(actual);
    invalidate(owner.get(),5,false);assert(invalidations.empty());
    ++owner->cart.u.items_cart[5].refine;invalidate(owner.get(),3,false);
    assert(invalidations.size()==1&&invalidations[0].scope==w::cart&&invalidations[0].client_index==7);
    invalidations.clear();
    owner->cart.u.items_cart[5]=actual;
    // Exercise the production request dispatcher with only final row building
    // mocked. Container selection, exact matching, watch ownership and throttling
    // are all real server code; metadata row generation is tested below.
    auto dispatch=[&](w::Request request) {
        test_tick+=200;invalidations.clear();captured={};
        item_description::process_request(owner.get(),request);
    };
    for(auto scope : {w::inventory,w::cart,w::storage}) {
        auto request=r;request.scope=scope;request.client_index=5+w::index_base(scope);owner->state.storage_flag=1;
        dispatch(request);assert(captured.calls==1&&captured.actual);
        assert(captured.index==(scope==w::inventory?5:-1));
        assert(captured.value.unique_id==actual.unique_id&&captured.value.refine==7&&captured.value.card[0]==4001);
        assert(invalidations.size()==1&&invalidations[0].result==w::ok);
        assert(owner->item_description_index[0]==item_description::watch_index(scope,5));
        request.refine=8;dispatch(request);assert(!captured.calls&&invalidations[0].result==w::stale);
        request.refine=7;request.known_fingerprint=fingerprint(actual)+1;
        dispatch(request);assert(!captured.calls&&invalidations[0].result==w::stale);
    }
    auto closed=r;closed.scope=w::storage;owner->state.storage_flag=0;
    dispatch(closed);assert(!captured.calls&&invalidations[0].result==w::stale);
    for(auto scope : {w::inventory,w::cart,w::storage}) {
        const int count=scope==w::inventory?MAX_INVENTORY:scope==w::cart?MAX_CART:MAX_STORAGE;
        owner->state.storage_flag=1;
        for(int index : {0,count-1}) {
            auto* value=const_cast<item*>(item_description::inspection_item(owner.get(),scope,index));*value=actual;
            auto request=r;request.scope=scope;request.client_index=index+w::index_base(scope);
            dispatch(request);assert(captured.calls==1&&invalidations[0].client_index==request.client_index);
            invalidations.clear();++value->refine;invalidate(owner.get(),-1,false);
            assert(invalidations.size()==1&&invalidations[0].client_index==request.client_index&&invalidations[0].scope==scope);
        }
        auto request=r;request.scope=scope;request.client_index=count+w::index_base(scope);
        dispatch(request);assert(!captured.calls&&invalidations[0].result==w::stale);
    }
    auto catalog=r;catalog.scope=w::catalog;catalog.client_index=catalog.refine=catalog.grade=0;
    catalog.option_count=0;for(auto& c:catalog.cards)c=0;for(auto& o:catalog.options)w::zero(o);
    dispatch(catalog);assert(captured.calls==1&&!captured.actual&&captured.index==-1&&!owner->item_description_request_id[0]);
    auto compare=r;compare.request_id|=0x80000000u;compare.message=w::compare;
    dispatch(compare);assert(captured.calls==1&&captured.comparison&&owner->item_description_request_id[1]==compare.request_id);
    invalidations.clear();captured={};item_description::process_request(owner.get(),compare);
    assert(!captured.calls&&invalidations.empty());
    std::cout<<"PASS: exact inventory/cart/personal/premium/guild storage resolution; closed/locked/foreign storage and invalid indices rejected; container watch scopes retained.\n";
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
        case 2:invalid.scope=4;break;case 3:invalid.client_index=1;break;case 4:invalid.reserved0=1;break;case 5:invalid.message=99;break;
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
    // Execute the production reload path: a setting change must be atomic and
    // invalidate both watched panes; malformed settings retain the active data.
    item_description::reload();assert(descriptions&&!show_grade());
    static map_session_data watcher;sessions.push_back(&watcher);
    watcher.item_description_request_id[0]=11;watcher.item_description_request_id[1]=0x8000000b;
    write(good+"Settings:\n  ShowGrade: true\n");item_description::reload();
    assert(show_grade()&&invalidations.size()==2);
    assert(invalidations[0].request_id==11&&invalidations[1].request_id==0x8000000b);
    const auto accepted_revision=revision;const auto* accepted=descriptions.get();
    watcher.item_description_request_id[0]=12;
    for (const auto& settings : std::vector<std::string>{
        "Settings: false\n", "Settings: []\n", "Settings:\n  ShowGrade: typo\n",
        "Settings:\n  ShowGrade: []\n", "Settings:\n  ShowGrade: {}\n", "Settings:\n  ShowGrade:\n"}) {
        write(good+settings);item_description::reload();
        assert(descriptions.get()==accepted&&revision==accepted_revision&&show_grade());
        assert(watcher.item_description_request_id[0]==12&&invalidations.size()==2);
    }
    write(good+"Settings:\n  ShowGrade: false\n");item_description::reload();
    assert(!show_grade()&&revision!=accepted_revision&&invalidations.size()==3);
    // Last explicit setting wins; an import without Settings retains the root.
    std::ofstream("grade-import.yml")<<header+"Settings:\n  ShowGrade: true\nBody: []\n";
    const auto imported=good+"Settings:\n  ShowGrade: false\nFooter:\n  Imports:\n    - Path: grade-import.yml\n";
    write(imported);item_description::reload();assert(show_grade());
    std::ofstream("grade-import.yml")<<header+"Body: []\n";
    item_description::reload();assert(!show_grade());
    std::ofstream("grade-import.yml")<<header+"Settings:\n  ShowGrade: invalid\nBody: []\n";
    const auto before_bad_import=revision;item_description::reload();assert(!show_grade()&&revision==before_bad_import);
    sessions.clear();invalidations.clear();
    std::cout<<"PASS: ShowGrade defaults off; live reload toggles and invalidates both panes; invalid scalars/containers/imports roll back; explicit import precedence.\n";
    write(good);item_description::reload();assert(!show_item_collection());
    write(good+"Settings:\n  ShowGrade: false\n  ShowItemCollection: true\n");item_description::reload();
    assert(show_item_collection()&&!show_grade());
    const auto collection_revision=revision;const auto* collection_accepted=descriptions.get();
    for(const auto& value:std::vector<std::string>{"typo","[]","{}",""}) {
        write(good+"Settings:\n  ShowItemCollection: "+value+"\n");item_description::reload();
        assert(show_item_collection()&&revision==collection_revision&&descriptions.get()==collection_accepted);
    }
    write(good+"Settings:\n  ShowGrade: true\n  ShowItemCollection: false\n");item_description::reload();
    assert(!show_item_collection()&&show_grade());
    write(good);item_description::reload();
    std::cout<<"PASS: Item Collection defaults off; independent runtime toggle; invalid settings roll back.\n";
    w::Snapshot hidden{};Builder hidden_builder{hidden};
    hidden_builder.row(w::grade,"Current grade","Epic");
    hidden_builder.long_effect(w::grade,"Epic",std::string(2048,'g'),w::active);
    assert(!hidden.row_count&&!hidden.flags);
    Descriptor mixed;Effect base;base.text="Base ATK +10";mixed.effects.push_back(base);
    Effect grade;grade.section=w::grade;grade.text="Grade preview";mixed.effects.push_back(grade);
    Effect conditional;conditional.min_grade=1;conditional.text="Grade conditional";mixed.effects.push_back(conditional);
    conditional.min_grade=0;conditional.max_grade=2;mixed.effects.push_back(conditional);
    Effect refined;refined.min_refine=1;refined.text="Refine bonus";mixed.effects.push_back(refined);
    for (auto section : {static_cast<w::Section>(0), w::cards, w::random_options}) {
        w::zero(hidden);Builder hb{hidden};append_effects(hb,mixed,actual,true,section);
        assert(hidden.row_count==2&&std::string(hidden.rows[0].text)=="Base ATK +10");
        assert(std::string(hidden.rows[1].text).find("Refine bonus")!=std::string::npos);
    }
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
    assert(!show_grade());
    // Every descriptor must omit grade rows and grade predicates while hidden.
    for (uint32 item_id : item_db.ids) if (auto d=generated.find(item_id)) {
        w::zero(hidden);Builder hb{hidden};append_effects(hb,*d,actual,true);
        for (unsigned n=0;n<hidden.row_count;++n) assert(hidden.rows[n].section!=w::grade);
    }
    descriptions->show_grade=true;
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
    static map_session_data session;
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
