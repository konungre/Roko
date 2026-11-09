/* Guest-only x86-64 PID1 qualification probe. No libc, shell or model. */
#ifndef ROKO_BUILD_ID
#error ROKO_BUILD_ID required
#endif
static long sc(long n,long a,long b,long c,long d,long e,long f) {
 register long r10 __asm__("r10")=d, r8 __asm__("r8")=e, r9 __asm__("r9")=f;
 long result;
 __asm__ volatile("syscall":"=a"(result):"a"(n),"D"(a),"S"(b),"d"(c),"r"(r10),"r"(r8),"r"(r9):"rcx","r11","memory");
 return result;
}
static void say(long fd,const char *s) {
 long n=0;while(s[n])n++;
 while(n>0){long r=sc(1,fd,(long)s,n,0,0,0);if(r<=0)return;s+=r;n-=r;}
}
static void exit_child(long code){sc(60,code,0,0,0,0,0);for(;;){}}
static void stop(void){
 sc(169,0xfee1dead,0x28121969,0x4321fedc,0,0,0);
 for(;;)sc(34,0,0,0,0,0,0);
}
__attribute__((noreturn)) void _start(void) {
 if(sc(39,0,0,0,0,0,0)!=1){say(2,"ROKO_PROBE_REFUSED_NOT_PID1\n");exit_child(77);}
 say(1,"ROKO_FOUNDATION_ENTERED " ROKO_BUILD_ID "\n");
 if(sc(165,(long)"proc",(long)"/proc",(long)"proc",0,0,0)<0 ||
    sc(165,(long)"sysfs",(long)"/sys",(long)"sysfs",0,0,0)<0){
  say(1,"ROKO_FOUNDATION_FAILED mounts\n");stop();
 }
 long child=sc(57,0,0,0,0,0,0);
 if(child==0){
  /* Drop supplementary groups, all saved IDs, then prevent exec privilege gain. */
  if(sc(116,0,0,0,0,0,0)!=0 || sc(119,1000,1000,1000,0,0,0)!=0 ||
     sc(117,1000,1000,1000,0,0,0)!=0 || sc(157,38,1,0,0,0,0)!=0)exit_child(91);
  unsigned int u[3]={0},g[3]={0};
  if(sc(118,(long)&u[0],(long)&u[1],(long)&u[2],0,0,0)!=0 ||
     sc(120,(long)&g[0],(long)&g[1],(long)&g[2],0,0,0)!=0)exit_child(92);
  if(u[0]!=1000||u[1]!=1000||u[2]!=1000||g[0]!=1000||g[1]!=1000||g[2]!=1000 ||
     sc(115,0,0,0,0,0,0)!=0 || sc(157,39,0,0,0,0,0)!=1)exit_child(93);
  if(sc(117,0,0,0,0,0,0)!=-1)exit_child(94); /* must fail EPERM */
  say(1,"ROKO_FOUNDATION_NONROOT uid=1000 gid=1000 groups=0 no_new_privs=1 regain_root=denied\n");
  char *argv[]={"/opt/roko/python/bin/python3.12","/opt/roko/no-network.py","/opt/roko/swipl/bin/swipl","-q","-s","/opt/roko/probe.pl",0};
  char *env[]={"PATH=/opt/roko/python/bin:/usr/bin:/bin","PYTHONHOME=/opt/roko/python","PYTHONPATH=/opt/roko/site-packages:/opt/roko/omega/src","LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/opt/roko/python/lib:/opt/roko/swipl/lib/swipl/lib/x86_64-linux","PYTHONDONTWRITEBYTECODE=1","PYTHONNOUSERSITE=1","SWI_HOME_DIR=/opt/roko/swipl/lib/swipl","LANG=C.UTF-8","HOME=/home/roko",0};
  long error=-sc(59,(long)argv[0],(long)argv,(long)env,0,0,0);
  char detail[]={48+(error/10)%10,48+error%10,10,0};say(2,detail);
  say(2,"ROKO_SYMBOLIC_EXEC_FAILED\n");exit_child(95);
 }
 int status=-1;
 if(child<0 || sc(61,child,(long)&status,0,0,0,0)!=child || status!=0){
  say(1,"ROKO_FOUNDATION_FAILED child\n");stop();
 }
#ifdef ROKO_TRIAL_FAIL
 say(1,"ROKO_FOUNDATION_FAILED injected-trial-health\n");stop();
#endif
 say(1,"ROKO_FOUNDATION_COMPLETE " ROKO_BUILD_ID "\n");
 stop();
 for(;;){}
}
