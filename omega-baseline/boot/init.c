/* Own freestanding Linux x86_64 boot probe. No libc or external runtime linked. */
#ifndef ROKO_BUILD_ID
#define ROKO_BUILD_ID "unconfigured"
#endif
static long call(long n,long a,long b,long c,long d,long e,long f) {
 register long r10 __asm__("r10")=d;
 register long r8 __asm__("r8")=e;
 register long r9 __asm__("r9")=f;
 long result;
 __asm__ volatile("syscall":"=a"(result):"a"(n),"D"(a),"S"(b),"d"(c),"r"(r10),"r"(r8),"r"(r9):"rcx","r11","memory");
 return result;
}
static long length(const char *s) {long n=0;while(s[n])n++;return n;}
static void write_text(long fd,const char *s) {call(1,fd,(long)s,length(s),0,0,0);}
static void text(const char *s) {write_text(1,s);}
static long mount_fs(const char *type,const char *path) {
 return call(165,(long)type,(long)path,(long)type,0,0,0);
}
static int same(const char *a,const char *b) {long i=0;while(a[i]&&b[i]&&a[i]==b[i])i++;return a[i]==b[i];}
static void rescue(void) {
 text("ROKO_RESCUE_READY\nCommands: help, status, poweroff\n");
 for(;;) {
  char line[128];long n=0;char c;int overflow=0;
  text("roko> ");
  for(;;) {
   if(call(0,0,(long)&c,1,0,0,0)<=0)continue;
   if(c=='\n'||c=='\r')break;
   if(n<127)line[n++]=c;else overflow=1;
  }
  line[n]=0;
  if(overflow) {text("ROKO_COMMAND_REJECTED too long\n");continue;}
  if(same(line,"help"))text("ROKO_HELP help status poweroff; no arbitrary shell execution\n");
  else if(same(line,"status"))text("ROKO_STATUS serial-rescue; profile=no-network,no-host-disks; cosmic=not-started; cognition=not-started\n");
  else if(same(line,"poweroff")) {
   text("ROKO_GUEST_POWER_OFF\n");
   call(169,0xfee1dead,0x28121969,0x4321fedc,0,0,0);
   text("ROKO_COMMAND_FAILED poweroff\n");
  } else if(n)text("ROKO_COMMAND_REJECTED unknown command\n");
 }
}
__attribute__((noreturn)) void _start(void) {
 if (call(39,0,0,0,0,0,0)!=1) {
  write_text(2,"Roko init refuses to run outside guest PID 1.\n");
  call(60,77,0,0,0,0,0);for(;;){}
 }
 text("ROKO_INIT_ENTERED\n");
 if (mount_fs("proc","/proc")<0 || mount_fs("sysfs","/sys")<0) {
  text("ROKO_INIT_FAILED mounts\n");for(;;)call(34,0,0,0,0,0,0);
 }
 if (mount_fs("devtmpfs","/dev")<0)text("ROKO_INIT_NOTE devtmpfs unavailable\n");
 char host[390];
 if (call(63,(long)host,0,0,0,0,0)==0) {
  text("ROKO_KERNEL ");text(host+130);text(" ");text(host+260);text("\n");
 }
 text("ROKO_INIT_READY " ROKO_BUILD_ID "\n");
 text("Roko serial rescue: no COSMIC, model, network or autonomous agent started.\n");
 if (call(21,(long)"/bin/busybox",1,0,0,0,0)==0) {
  text("ROKO_BUSYBOX_PRESENT\n");
  long child=call(57,0,0,0,0,0,0);
  if (child==0) {
   char *args[]={"/bin/busybox","sh",0};
   call(59,(long)args[0],(long)args,0,0,0,0);
   call(60,127,0,0,0,0,0);for(;;){}
  }
 } else rescue();
 for(;;) {int status;if(call(61,-1,(long)&status,0,0,0,0)<0)call(34,0,0,0,0,0,0);}
}
