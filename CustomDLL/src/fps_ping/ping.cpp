// ICMP ping for real network latency measurement.
// Compiled WITHOUT WIN32_LEAN_AND_MEAN to avoid icmpapi.h type conflicts.

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <iphlpapi.h>
#include <icmpapi.h>
#include <stdio.h>

#pragma comment(lib, "iphlpapi.lib")
#pragma comment(lib, "ws2_32.lib")

static HANDLE g_icmpHandle = nullptr;
static bool   g_icmpInit = false;
static bool   g_pingValid = false;    // true if we have a real ping measurement
static DWORD  g_pingResult = 0;       // last RTT in ms (0 on localhost is valid!)
static DWORD  g_lastPingTime = 0;
static DWORD  g_startupTick = 0;
static char   g_pingHost[256] = "45.139.226.188";

void PingSetHost(const char* host)
{
    if (host && host[0])
    {
        strncpy_s(g_pingHost, sizeof(g_pingHost), host, _TRUNCATE);
    }
}

DWORD PingGetResult()
{
    return g_pingResult;
}

bool PingIsValid()
{
    return g_pingValid;
}

void PingInit()
{
    if (g_icmpInit) return;
    g_icmpHandle = IcmpCreateFile();
    g_icmpInit = true;
}

void PingShutdown()
{
    if (g_icmpHandle && g_icmpHandle != INVALID_HANDLE_VALUE)
    {
        IcmpCloseHandle(g_icmpHandle);
        g_icmpHandle = nullptr;
    }
    g_icmpInit = false;
}

void PingUpdate()
{
    if (!g_icmpInit) PingInit();
    if (!g_icmpHandle || g_icmpHandle == INVALID_HANDLE_VALUE) return;

    DWORD now = GetTickCount();
    // Wait 5 seconds after startup before first ping (network stack init)
    if (!g_startupTick) g_startupTick = now;
    if (now - g_startupTick < 5000) return;

    // Ping at most once per second
    if (now - g_lastPingTime < 1000) return;
    g_lastPingTime = now;

    // Resolve hostname to IP
    DWORD ipAddr = inet_addr(g_pingHost);
    if (ipAddr == INADDR_NONE)
    {
        struct addrinfo hints = {}, *result = nullptr;
        hints.ai_family = AF_INET;
        if (getaddrinfo(g_pingHost, nullptr, &hints, &result) == 0 && result)
        {
            ipAddr = ((struct sockaddr_in*)result->ai_addr)->sin_addr.s_addr;
            freeaddrinfo(result);
        }
    }
    if (ipAddr == INADDR_NONE) return;

    char sendData[32] = "fps_overlay_ping";
    char replyBuf[sizeof(ICMP_ECHO_REPLY) + 64];

    DWORD ret = IcmpSendEcho(g_icmpHandle, ipAddr,
        sendData, sizeof(sendData), nullptr,
        replyBuf, sizeof(replyBuf), 1000);

    if (ret)
    {
        PICMP_ECHO_REPLY reply = (PICMP_ECHO_REPLY)replyBuf;
        g_pingResult = reply->RoundTripTime;
        g_pingValid = true;  // 0ms on localhost is valid
    }
    else
    {
        g_pingValid = false;
    }
}
