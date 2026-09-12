// Runs the real server YamlDatabase loader with allocator/logging boundaries.
#include <algorithm>
#include <cassert>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <common/database.hpp>
#include <common/showmsg.hpp>
#include <common/malloc.hpp>
void* _mmalloc(size_t n,const char*,int32,const char*){auto p=std::malloc(n);if(!p)throw std::bad_alloc();return p;}
void _mfree(void* p,const char*,int32,const char*){std::free(p);}
int32 _vShowMessage(msg_type,const char*,va_list){return 0;}
void ShowMessage(const char*,...){} void ShowStatus(const char*,...){}
void ShowError(const char*,...){} void ShowWarning(const char*,...){}
extern void do_init_database();
char db_path[12]=".";
struct TestMobDb{std::shared_ptr<int> find(uint32_t id){return id==1002?std::make_shared<int>(1):nullptr;}} mob_db;
#include "bestiary_lore_under_test.inc"
struct Entry{uint32_t id,value;};
class Candidate final:public TypesafeYamlDatabase<uint32_t,Entry>{
public:
	Candidate(bool strict=true):TypesafeYamlDatabase("BESTIARY_TEST",1){strictLoading=strict;}
	const std::string getDefaultLocation()override{return "root.yml";}
	uint64 parseBodyNode(const ryml::NodeRef& n)override{
		uint32_t id,value;if(!asUInt32(n,"Id",id)||!asUInt32(n,"Value",value))return 0;
		if(value>100){invalidWarning(n,"Value exceeds test domain.\n");return 0;}
		put(id,std::make_shared<Entry>(Entry{id,value}));return 1;
	}
};
const std::string header="Header:\n  Type: BESTIARY_TEST\n  Version: 1\n";
void write(const char* path,const std::string& text){std::ofstream(path)<<text;}
int main(int argc,char** argv){
	assert(argc==2);std::filesystem::current_path(argv[1]);do_init_database();
	write("root.yml",header+"Body:\n  - Id: 1\n    Value: 12\nFooter:\n  Imports:\n    - Path: import.yml\n");
	write("import.yml",header+"Body:\n  - Id: 2\n    Value: 34\n");
	auto active=std::make_unique<Candidate>();assert(active->load()&&active->size()==2);
	unsigned rejected=0;
	for(const auto& invalid:std::vector<std::string>{
		"Header: [broken\n", "Header:\n  Type: WRONG\n  Version: 1\n",
		"Header:\n  Type: BESTIARY_TEST\n  Version: 99\n",
		header+"Body:\n  - Id: 2\n    Value: 101\n",
		header+"Body:\n  - Id: 2\n",
		header+"Footer:\n  Imports:\n    - Path: missing.yml\n",
		header+"Footer:\n  Imports:\n    - Path: root.yml\n"}){
		write("import.yml",invalid);auto candidate=std::make_unique<Candidate>();
		if(candidate->load())active=std::move(candidate);else ++rejected;
		assert(active->size()==2&&active->find(2)->value==34);
	}
	assert(rejected==7);
	// The opt-in must not change legacy loaders' historical import behavior.
	write("import.yml","Header: [broken\n");Candidate legacy(false);assert(legacy.load()&&legacy.size()==1);
	// Failed candidate state must not poison the next complete load.
	write("import.yml",header+"Body:\n  - Id: 2\n    Value: 50\n");
	auto candidate=std::make_unique<Candidate>();assert(candidate->load());active=std::move(candidate);assert(active->find(2)->value==50);
	const std::string loreHeader="Header:\n  Type: BESTIARY_LORE_DB\n  Version: 1\n";
	const std::string goodLore=loreHeader+"Body:\n  - Id: 1002\n    Text: A field note.\n    Source: Editorial\n";
	write("bestiary_lore.yml",goodLore);auto lore=std::make_unique<LoreDatabase>();assert(lore->load()&&lore->find(1002)->text=="A field note.");
	for(const auto& invalid:std::vector<std::string>{
		loreHeader+"Body: invalid\n",
		loreHeader+"Body:\n  - Id: 9999\n    Text: No such monster.\n    Source: Editorial\n",
		loreHeader+"Body:\n  - Id: 1002\n    Text: "+std::string(16385,'A')+"\n    Source: Editorial\n",
		loreHeader+"Body:\n  - Id: 1002\n    Text: Text\n    Source: "+std::string(64,'A')+"\n",
		loreHeader+"Body:\n  - Id: 1002\n    Text: \"a\\0b\"\n    Source: Editorial\n"}){
		write("bestiary_lore.yml",invalid);auto next=std::make_unique<LoreDatabase>();assert(!next->load()&&!next->valid);assert(lore->find(1002)->text=="A field note.");
	}
	std::cout<<"Passed: real lore parser rejects malformed Body, unknown MobId, oversized prose/source and embedded NUL.\n";
	std::cout<<"Passed: strict imports, invalid entries, missing imports, cycles, retained snapshot, legacy compatibility and recovery.\n";
}
