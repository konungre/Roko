#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static void fail(const char *s) { perror(s); exit(1); }
static void check(int ok, const char *s) { if (!ok) { errno=EINVAL; fail(s); } }
static void metadata(int fd, mode_t mode, int dir) {
    struct stat s; if(fstat(fd,&s)) fail("fstat");
    check((s.st_mode & 07777)==mode && s.st_uid==0 && s.st_gid==0 &&
          (dir ? S_ISDIR(s.st_mode) : S_ISREG(s.st_mode) && s.st_nlink==1),"metadata");
}
int main(int argc,char **argv) {
    check(argc==2 && (!strcmp(argv[1],"write") || !strcmp(argv[1],"read")),"phase");
    int writing=!strcmp(argv[1],"write");
    umask(077);
    int root=open("/data",O_RDONLY|O_DIRECTORY|O_NOFOLLOW); if(root<0) fail("data");
    if(writing && mkdirat(root,"probe",0700)) fail("exclusive probe mkdir");
    int dir=openat(root,"probe",O_RDONLY|O_DIRECTORY|O_NOFOLLOW); if(dir<0) fail("probe");
    metadata(dir,0700,1);
    unsigned char expected[4097],got[4098];
    for(size_t i=0;i<sizeof expected;i++) expected[i]=(unsigned char)((i*31+7)%251);
    const char *names[]={"notes.txt","binary.dat"};
    const char note[]="Roko private ext4 fixture\nExplicit clean two-boot check only.\n";
    for(int i=0;i<2;i++) {
        const void *data=i ? (const void *)expected : (const void *)note;
        size_t size=i ? sizeof expected : sizeof note-1;
        if(writing) {
            int fd=openat(dir,"pending",O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600); if(fd<0) fail("create");
            check(write(fd,data,size)==(ssize_t)size,"write");
            if(fsync(fd)) fail("file fsync");
            metadata(fd,0600,0);
            if(close(fd)) fail("close");
            if(renameat(dir,"pending",dir,names[i]) || fsync(dir)) fail("rename directory fsync");
        }
        int fd=openat(dir,names[i],O_RDONLY|O_NOFOLLOW); if(fd<0) fail("read open");
        metadata(fd,0600,0); check(read(fd,got,sizeof got)==(ssize_t)size && !memcmp(got,data,size),"fixture equality"); close(fd);
    }
    if(writing && fsync(root)) fail("root fsync");
    pid_t child=fork(); if(child<0) fail("fork");
    if(!child) {
        if(setgid(1000) || setuid(1000)) _exit(2);
        errno=0; int fd=openat(dir,"notes.txt",O_RDONLY|O_NOFOLLOW);
        if(fd>=0 || errno!=EACCES) _exit(3);
        errno=0; fd=open("/data/probe",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
        _exit(fd<0 && errno==EACCES ? 0 : 4);
    }
    int status; check(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,"unprivileged denial");
    close(dir); close(root);
    printf("ROKO_FILES_%s_PASSED fsync=files,directories fixtures=2 permissions=0700,0600 denial=uid1000\n",writing?"WRITE":"READ");
    return 0;
}
