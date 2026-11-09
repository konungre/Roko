#define _GNU_SOURCE
#include <cpuid.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

/* Compile for baseline x86-64. Never execute AVX instructions in this probe. */
int main(void) {
    cpu_set_t allowed, one;
    if (sched_getaffinity(0, sizeof(allowed), &allowed)) return 2;
    bool avx=true, avx2=true, fma=true, f16c=true, bmi2=true, sse42=true, state=true;
    unsigned tested=0;
    for (int cpu=0; cpu<CPU_SETSIZE; ++cpu) {
        if (!CPU_ISSET(cpu, &allowed)) continue;
        CPU_ZERO(&one); CPU_SET(cpu, &one);
        if (sched_setaffinity(0, sizeof(one), &one)) return 2;
        unsigned a=0,b=0,c=0,d=0;
        unsigned maximum=__get_cpuid_max(0, NULL);
        if (maximum<1 || !__get_cpuid(1,&a,&b,&c,&d)) return 2;
        avx &= (c & (1u<<28)) != 0;
        fma &= (c & (1u<<12)) != 0;
        f16c &= (c & (1u<<29)) != 0;
        sse42 &= (c & (1u<<20)) != 0;
        bool enabled=(c & (1u<<26)) && (c & (1u<<27));
        if (enabled) {
            uint32_t lo,hi;
            __asm__ volatile ("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
            enabled=(lo & 6u)==6u;
        }
        state &= enabled;
        a=b=c=d=0;
        if (maximum>=7) __cpuid_count(7,0,a,b,c,d);
        avx2 &= (b & (1u<<5)) != 0;
        bmi2 &= (b & (1u<<8)) != 0;
        ++tested;
    }
    if (sched_setaffinity(0,sizeof(allowed),&allowed) || !tested) return 2;
    printf("{\"architecture\":\"x86_64\",\"all_allowed_cpus\":true,\"tested_cpus\":%u,"
           "\"avx\":%s,\"avx2\":%s,\"fma\":%s,\"f16c\":%s,\"bmi2\":%s,"
           "\"sse4_2\":%s,\"os_avx_state\":%s}\n",tested,
           avx?"true":"false",avx2?"true":"false",fma?"true":"false",f16c?"true":"false",
           bmi2?"true":"false",sse42?"true":"false",state?"true":"false");
    return 0;
}
