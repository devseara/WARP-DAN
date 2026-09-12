// Actual char service + SQL driver + extracted transaction-free mail insertion.
// Socket buffers/logging/timers are the only substituted boundaries.
#include <common/bestiary_definitions.hpp>
#include <common/malloc.hpp>
#include <common/showmsg.hpp>
#include <common/socket.hpp>
#include <common/sql.hpp>
#include <common/timer.hpp>
#include <common/strlib.hpp>
#include <char/char.hpp>
#include <char/int_mail.hpp>
#include <cassert>
#include <iostream>
#include <cstring>
#include <cstdlib>
#include <vector>
void* _mmalloc(size_t n,const char*,int32,const char*){auto p=std::malloc(n);if(!p)throw std::bad_alloc();return p;}
void* _mcalloc(size_t n,size_t size,const char*,int32,const char*){auto p=std::calloc(n,size);if(!p)throw std::bad_alloc();return p;}
void* _mrealloc(void* p,size_t n,const char*,int32,const char*){auto q=std::realloc(p,n);if(!q)throw std::bad_alloc();return q;}
void _mfree(void* p,const char*,int32,const char*){std::free(p);}
int32 _vShowMessage(msg_type,const char*,va_list){return 0;}
void ShowMessage(const char*,...){} void ShowStatus(const char*,...){}
void ShowError(const char*,...){} void ShowWarning(const char* format,...){va_list ap;va_start(ap,format);vfprintf(stderr,format,ap);va_end(ap);} void ShowInfo(const char*,...){} void ShowDebug(const char*,...){} void ShowSQL(const char* format,...){va_list ap;va_start(ap,format);vfprintf(stderr,format,ap);va_end(ap);}
void ShowFatalError(const char*,...){}
const char* INTER_CONF_NAME="unused-in-sql-test";
t_tick gettick(){return 0;}
int32 add_timer_interval(t_tick,TimerFunc,int32,intptr_t,int32){return 1;}
int32 delete_timer(int32,TimerFunc){return 0;}
char db_path[12]="db";
Schema_Config schema_config{};
Sql* sql_handle=nullptr;
socket_data* session[MAXCONN]{};
std::vector<std::vector<uint8_t>> output;
int32 _realloc_writefifo(int32,size_t,const char*,int32,const char*){assert(false);return 0;}
int32 WFIFOSET(int32 fd,size_t length){output.emplace_back(session[fd]->wdata,session[fd]->wdata+length);return 1;}
int32 RFIFOSKIP(int32 fd,size_t length){session[fd]->rdata_pos+=length;return 0;}
void set_eof(int32){assert(false);}
#ifdef ASYNC_NETWORK_QUEUE
void socket_outbound_drain_before_direct(int32){}
#endif
extern void do_init_database();
#include "bestiary_mail_under_test.inc"
#include <char/int_bestiary.cpp>

using namespace bestiary_research;
static uint32_t request_id=0;
Header call(Message type,uint32_t target=0,std::vector<Record> records={},uint32_t account=2000000,uint32_t character=2000000,uint64_t sequence=0){
	Header h;h.message=static_cast<uint16_t>(type);h.request=++request_id;h.definitions=definitions->fingerprint();h.account=account;h.character=character;h.cursor=target;h.sequence=sequence;h.stream[0]=42;
	h.count=static_cast<uint16_t>(records.size());h.length=static_cast<uint16_t>(sizeof(h)+records.size()*sizeof(Record));
	memcpy(session[1]->rdata,&h,sizeof(h));if(!records.empty())memcpy(session[1]->rdata+sizeof(h),records.data(),records.size()*sizeof(Record));session[1]->rdata_pos=0;session[1]->rdata_size=h.length;
	output.clear();assert(inter_bestiary_parse(1)==1 && !output.empty());Header response;memcpy(&response,output.back().data(),sizeof(response));return response;
}
uint64_t scalar(const char* sql){query("%s",sql);assert(Sql_NextRow(sql_handle)==SQL_SUCCESS);auto value=column(0);Sql_FreeResult(sql_handle);return value;}
int main(int argc,char** argv){
	assert(argc==2);do_init_database();safestrncpy(schema_config.char_db,"char",DB_NAME_LEN);safestrncpy(schema_config.mail_db,"mail",DB_NAME_LEN);safestrncpy(schema_config.mail_attachment_db,"mail_attachments",DB_NAME_LEN);
	sql_handle=Sql_Malloc();assert(Sql_Connect(sql_handle,getenv("BESTIARY_TEST_USER"),getenv("BESTIARY_TEST_PASSWORD"),getenv("BESTIARY_TEST_HOST"),static_cast<uint16_t>(atoi(getenv("BESTIARY_TEST_PORT"))),getenv("BESTIARY_TEST_DB"))==SQL_SUCCESS);
	static socket_data socket{};static uint8_t input[16384],out[16384];socket.rdata=input;socket.wdata=out;socket.max_rdata=sizeof(input);socket.max_wdata=sizeof(out);session[1]=&socket;
	inter_bestiary_init();assert(ready && mail_ready);
	const std::string mode=argv[1];
	if(mode=="concurrent"){const auto response=call(Message::Claim,4);assert(response.result==0);Sql_Free(sql_handle);return 0;}
	if(mode=="claim_all"){
		uint32_t cursor=0;size_t calls=0;
		do{auto response=call(Message::ClaimAll,cursor);assert(response.result==0);cursor=response.cursor;assert(++calls<16);}while(cursor);
		assert(scalar("SELECT COUNT(*) FROM bestiary_claims WHERE account_id=2000000")>30);
		const auto count=scalar("SELECT COUNT(*) FROM bestiary_claims");call(Message::ClaimAll);assert(scalar("SELECT COUNT(*) FROM bestiary_claims")==count);
		std::cout<<"Passed: bounded Claim All and replay preserve one claim per account/reward/version.\n";Sql_Free(sql_handle);return 0;
	}
	assert(call(Message::Hello).result==0);
	std::vector<Record> records;for(uint64_t i=1;i<=25;++i){Record r;r.sequence=i;r.account=2000000;r.mob=1002;r.occurred=1800000000;records.push_back(r);}
	assert(call(Message::Commit,0,records).sequence==25);assert(call(Message::Commit,0,records).sequence==25);
	assert(scalar("SELECT kills FROM bestiary_progress WHERE account_id=2000000 AND mob_id=1002")==25);
	Record gap=records.back();gap.sequence=27;assert(call(Message::Commit,0,{gap}).result==static_cast<uint16_t>(Result::Gap));
	assert(scalar("SELECT sequence FROM bestiary_streams")==25);
	assert(call(Message::Claim,1).sequence==0);assert(scalar("SELECT COUNT(*) FROM bestiary_claims")==0);
	assert(call(Message::Load).result==0);size_t loaded=0;for(const auto& packet:output){Header h;memcpy(&h,packet.data(),sizeof(h));assert(h.cursor==loaded);loaded+=h.count;}assert(loaded>=2);
	assert(call(Message::Preference,1002,{},2000000,2000001,3).result==0);
	assert(scalar("SELECT favorite+tracked FROM bestiary_preferences WHERE account_id=2000000 AND mob_id=1002")==2);
	assert(call(Message::Claim,1,{},2000000,2000002).result==static_cast<uint16_t>(Result::Invalid));
	// Seed committed hunt totals only inside this disposable test database.
	{Transaction transaction;account_lock(2000000);size_t count=0;for(const auto& m:definitions->monsters){query("INSERT INTO bestiary_progress(account_id,mob_id,kills,first_seen,last_seen) VALUES(2000000,%u,1500,1800000000,1800000000) ON DUPLICATE KEY UPDATE kills=1500",m.first);if(++count==40)break;}milestones(2000000,1800000000);transaction.commit();}
	const auto points_before=scalar("SELECT SUM(points) FROM bestiary_milestones WHERE account_id=2000000");milestones(2000000,1800000000);assert(scalar("SELECT SUM(points) FROM bestiary_milestones WHERE account_id=2000000")==points_before);
	assert(call(Message::Claim,1,{},2000000,2000001).sequence==1);assert(call(Message::Claim,1).sequence==0);
	assert(scalar("SELECT COUNT(*) FROM bestiary_claims WHERE reward_id=1")==1 && scalar("SELECT COUNT(*) FROM mail")==1);
	assert(scalar("SELECT amount FROM mail_attachments LIMIT 1")==5 && scalar("SELECT bound FROM mail_attachments LIMIT 1")==BOUND_ACCOUNT);
	query("CREATE TRIGGER bestiary_fail_mail BEFORE INSERT ON mail_attachments FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='injected attachment failure'");
	assert(call(Message::Claim,2).result==static_cast<uint16_t>(Result::Unavailable));
	assert(scalar("SELECT COUNT(*) FROM bestiary_claims WHERE reward_id=2")==0 && scalar("SELECT COUNT(*) FROM mail")==1);
	query("DROP TRIGGER bestiary_fail_mail");assert(call(Message::Claim,2).sequence==1);
	assert(call(Message::Claim,3).sequence==1 && scalar("SELECT COUNT(*) FROM bestiary_entitlements WHERE account_id=2000000 AND kind=2 AND entitlement_id=1000")==1);
	assert(call(Message::Load,0,{},2000000,2000001).result==0);
	std::cout<<"Passed: real SQL event replay/gaps, account sharing, committed eligibility, immutable points, recipient validation, atomic mail+claim rollback/retry and title entitlement.\n";
	Sql_Free(sql_handle);
}
