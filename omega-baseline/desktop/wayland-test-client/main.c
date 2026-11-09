#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
#include "pattern.h"

struct app {
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct xdg_wm_base *wm;
    struct wl_seat *seat;
    struct wl_keyboard *keyboard;
    struct wl_pointer *pointer;
    struct wl_surface *surface;
    struct xdg_surface *xdg;
    struct xdg_toplevel *top;
    struct wl_buffer *buffers[2];
    struct wl_callback *frame;
    unsigned state, submitted, frames;
    bool configured, running;
    const char *reason;
};
static volatile sig_atomic_t stopped;
static void stop_signal(int sig) { stopped = sig; }
static void timeout_signal(int sig) {
    (void)sig;
    const char msg[] = "ROKO_WAYLAND_TIMEOUT\n";
    (void)write(STDERR_FILENO, msg, sizeof(msg)-1);
    _exit(124);
}
static void fail(const char *what) { fprintf(stderr, "ROKO_WAYLAND_ERROR %s\n", what); exit(1); }
static void submit(struct app *a);
static void frame_done(void *data, struct wl_callback *cb, uint32_t time) {
    struct app *a = data;
    wl_callback_destroy(cb); a->frame = NULL; a->frames++;
    printf("ROKO_WAYLAND_FRAME count=%u state=%u time=%u\n", a->frames, a->submitted, time);
    if (a->state != a->submitted) submit(a);
}
static const struct wl_callback_listener frame_listener = {.done = frame_done};
static void submit(struct app *a) {
    if (!a->configured || a->frame) return;
    wl_surface_attach(a->surface, a->buffers[a->state], 0, 0);
    wl_surface_damage(a->surface, 0, 0, WIDTH, HEIGHT);
    a->frame = wl_surface_frame(a->surface);
    wl_callback_add_listener(a->frame, &frame_listener, a);
    a->submitted = a->state;
    wl_surface_commit(a->surface);
    printf("ROKO_WAYLAND_SUBMIT state=%u\n", a->state);
}
static void toggle(struct app *a, const char *source) {
    if (!a->frames || a->frame) return; /* Each accepted input has its own frame. */
    a->state ^= 1;
    printf("ROKO_WAYLAND_INPUT source=%s state=%u\n", source, a->state);
    submit(a);
}
static void keymap(void *d, struct wl_keyboard *k, uint32_t f, int32_t fd, uint32_t size) {
    (void)d; (void)k; (void)f; (void)size; close(fd); /* Raw evdev codes, no layout interpretation. */
}
static void key_enter(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sf, struct wl_array *keys) {
    (void)d; (void)k; (void)s; (void)sf; (void)keys;
}
static void key_leave(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sf) {
    (void)d; (void)k; (void)s; (void)sf;
}
static void key(void *d, struct wl_keyboard *k, uint32_t serial, uint32_t time, uint32_t code, uint32_t state) {
    (void)k; (void)serial; (void)time; struct app *a = d;
    if (state != WL_KEYBOARD_KEY_STATE_PRESSED) return;
    if (code == 57) toggle(a, "space");
    if (code == 1 || code == 16) { a->running = false; a->reason = "key"; }
}
static void modifiers(void *d, struct wl_keyboard *k, uint32_t s, uint32_t dep, uint32_t lat, uint32_t lock, uint32_t group) {
    (void)d; (void)k; (void)s; (void)dep; (void)lat; (void)lock; (void)group;
}
static const struct wl_keyboard_listener keyboard_listener = {
    .keymap=keymap, .enter=key_enter, .leave=key_leave, .key=key, .modifiers=modifiers
};
static void ptr_enter(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf, wl_fixed_t x, wl_fixed_t y) {
    (void)d; (void)p; (void)s; (void)sf; (void)x; (void)y;
}
static void ptr_leave(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf) { (void)d; (void)p; (void)s; (void)sf; }
static void motion(void *d, struct wl_pointer *p, uint32_t t, wl_fixed_t x, wl_fixed_t y) { (void)d; (void)p; (void)t; (void)x; (void)y; }
static void button(void *d, struct wl_pointer *p, uint32_t s, uint32_t t, uint32_t b, uint32_t state) {
    (void)p; (void)s; (void)t;
    if (b == 272 && state == WL_POINTER_BUTTON_STATE_PRESSED) toggle(d, "left-click");
}
static void axis(void *d, struct wl_pointer *p, uint32_t t, uint32_t axis_id, wl_fixed_t value) { (void)d; (void)p; (void)t; (void)axis_id; (void)value; }
static const struct wl_pointer_listener pointer_listener = {.enter=ptr_enter,.leave=ptr_leave,.motion=motion,.button=button,.axis=axis};
static void capabilities(void *d, struct wl_seat *seat, uint32_t caps) {
    struct app *a = d;
    if ((caps & WL_SEAT_CAPABILITY_KEYBOARD) && !a->keyboard) {
        a->keyboard = wl_seat_get_keyboard(seat); wl_keyboard_add_listener(a->keyboard, &keyboard_listener, a);
    } else if (!(caps & WL_SEAT_CAPABILITY_KEYBOARD) && a->keyboard) { wl_keyboard_destroy(a->keyboard); a->keyboard=NULL; }
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !a->pointer) {
        a->pointer = wl_seat_get_pointer(seat); wl_pointer_add_listener(a->pointer, &pointer_listener, a);
    } else if (!(caps & WL_SEAT_CAPABILITY_POINTER) && a->pointer) { wl_pointer_destroy(a->pointer); a->pointer=NULL; }
    printf("ROKO_WAYLAND_SEAT capabilities=%u\n", caps);
}
static const struct wl_seat_listener seat_listener = {.capabilities=capabilities};
static void ping(void *d, struct xdg_wm_base *wm, uint32_t serial) { (void)d; xdg_wm_base_pong(wm, serial); }
static const struct xdg_wm_base_listener wm_listener = {.ping=ping};
static void global(void *d, struct wl_registry *r, uint32_t id, const char *name, uint32_t version) {
    struct app *a = d; (void)version;
    /* Bind version 1 so no newer event callbacks are required. */
    if (!strcmp(name,"wl_compositor") && !a->compositor) a->compositor=wl_registry_bind(r,id,&wl_compositor_interface,1);
    else if (!strcmp(name,"wl_shm") && !a->shm) a->shm=wl_registry_bind(r,id,&wl_shm_interface,1);
    else if (!strcmp(name,"xdg_wm_base") && !a->wm) {
        a->wm=wl_registry_bind(r,id,&xdg_wm_base_interface,1); xdg_wm_base_add_listener(a->wm,&wm_listener,a);
    } else if (!strcmp(name,"wl_seat") && !a->seat) {
        a->seat=wl_registry_bind(r,id,&wl_seat_interface,1); wl_seat_add_listener(a->seat,&seat_listener,a);
    }
}
static void global_remove(void *d, struct wl_registry *r, uint32_t id) { (void)d; (void)r; (void)id; }
static const struct wl_registry_listener registry_listener = {.global=global,.global_remove=global_remove};
static void configure(void *d, struct xdg_surface *surface, uint32_t serial) {
    struct app *a=d; xdg_surface_ack_configure(surface,serial); a->configured=true; submit(a);
}
static const struct xdg_surface_listener surface_listener = {.configure=configure};
static void top_configure(void *d, struct xdg_toplevel *top, int32_t w, int32_t h, struct wl_array *states) {
    (void)d; (void)top;
    uint32_t *state;
    bool fullscreen=false;
    wl_array_for_each(state, states) if (*state == XDG_TOPLEVEL_STATE_FULLSCREEN) fullscreen=true;
    printf("ROKO_WAYLAND_CONFIGURE width=%d height=%d fullscreen=%u\n", w, h, fullscreen ? 1u : 0u);
}
static void top_close(void *d, struct xdg_toplevel *top) { (void)top; struct app *a=d; a->running=false; a->reason="close"; }
static const struct xdg_toplevel_listener top_listener = {.configure=top_configure,.close=top_close};
static struct wl_buffer *make_buffer(struct app *a, unsigned state) {
    int fd=memfd_create("roko-test-pixels", MFD_CLOEXEC);
    if (fd<0 || ftruncate(fd,BYTES)<0) fail("shm allocation");
    uint32_t *pixels=mmap(NULL,BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if (pixels==MAP_FAILED) fail("mmap");
    for (unsigned y=0;y<HEIGHT;y++) for (unsigned x=0;x<WIDTH;x++) pixels[y*WIDTH+x]=pixel(x,y,state);
    struct wl_shm_pool *pool=wl_shm_create_pool(a->shm,fd,BYTES);
    struct wl_buffer *buffer=wl_shm_pool_create_buffer(pool,0,WIDTH,HEIGHT,STRIDE,WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool); munmap(pixels,BYTES); close(fd);
    return buffer; /* Immutable for lifetime: no writes while compositor uses it. */
}
int main(int argc, char **argv) {
    if (argc != 1) { fprintf(stderr,"Usage: %s (30 second hard deadline)\n",argv[0]); return 2; }
    /* Refuse inherited socket FDs and paths, permit only an explicit local basename. */
    const char *display=getenv("WAYLAND_DISPLAY"), *runtime=getenv("XDG_RUNTIME_DIR");
    if (getenv("WAYLAND_SOCKET") || !display || !*display || strchr(display,'/') || !runtime || runtime[0]!='/') fail("explicit local Wayland environment required");
    setvbuf(stdout,NULL,_IOLBF,0);
    signal(SIGALRM,timeout_signal); alarm(30);
    signal(SIGINT,stop_signal); signal(SIGTERM,stop_signal);
    struct app a={.running=true,.reason="unknown"};
    a.display=wl_display_connect(display); if (!a.display) fail("connect");
    a.registry=wl_display_get_registry(a.display); wl_registry_add_listener(a.registry,&registry_listener,&a);
    if (wl_display_roundtrip(a.display)<0) fail("registry roundtrip");
    if (!a.compositor || !a.shm || !a.wm) fail("missing compositor/shm/xdg-shell");
    a.buffers[0]=make_buffer(&a,0); a.buffers[1]=make_buffer(&a,1);
    a.surface=wl_compositor_create_surface(a.compositor);
    struct wl_region *opaque=wl_compositor_create_region(a.compositor);
    wl_region_add(opaque,0,0,WIDTH,HEIGHT); wl_surface_set_opaque_region(a.surface,opaque); wl_region_destroy(opaque);
    a.xdg=xdg_wm_base_get_xdg_surface(a.wm,a.surface); xdg_surface_add_listener(a.xdg,&surface_listener,&a);
    a.top=xdg_surface_get_toplevel(a.xdg); xdg_toplevel_add_listener(a.top,&top_listener,&a);
    xdg_toplevel_set_title(a.top,"Roko Wayland pixel test"); xdg_toplevel_set_app_id(a.top,"org.roko.WaylandPixelTest");
    xdg_toplevel_set_min_size(a.top,WIDTH,HEIGHT); xdg_toplevel_set_max_size(a.top,WIDTH,HEIGHT);
    /* xdg-shell explicitly permits smaller fullscreen surfaces with border fill.
     * Keep the exact pixel dimensions; fullscreen avoids compositor window chrome.
     */
    xdg_toplevel_set_fullscreen(a.top,NULL);
    xdg_surface_set_window_geometry(a.xdg,0,0,WIDTH,HEIGHT); wl_surface_commit(a.surface);
    while (a.running && !stopped) {
        while (wl_display_prepare_read(a.display)!=0) if (wl_display_dispatch_pending(a.display)<0) fail("dispatch pending");
        int flush=wl_display_flush(a.display);
        if (flush<0 && errno!=EAGAIN) { wl_display_cancel_read(a.display); fail("flush"); }
        struct pollfd p={.fd=wl_display_get_fd(a.display),.events=POLLIN | (flush<0 ? POLLOUT : 0)};
        int n=poll(&p,1,100);
        if (n<0 && errno!=EINTR) { wl_display_cancel_read(a.display); fail("poll"); }
        if (n>0 && (p.revents&POLLIN)) { if (wl_display_read_events(a.display)<0) fail("read events"); }
        else wl_display_cancel_read(a.display);
        if (n>0 && (p.revents&(POLLERR|POLLHUP|POLLNVAL))) fail("display disconnected");
        if (wl_display_dispatch_pending(a.display)<0) fail("dispatch");
    }
    if (stopped) a.reason="signal";
    if (a.frame) wl_callback_destroy(a.frame);
    xdg_toplevel_destroy(a.top); xdg_surface_destroy(a.xdg); wl_surface_destroy(a.surface);
    wl_buffer_destroy(a.buffers[0]); wl_buffer_destroy(a.buffers[1]);
    if (a.keyboard) wl_keyboard_destroy(a.keyboard);
    if (a.pointer) wl_pointer_destroy(a.pointer);
    if (a.seat) wl_seat_destroy(a.seat);
    xdg_wm_base_destroy(a.wm); wl_shm_destroy(a.shm); wl_compositor_destroy(a.compositor); wl_registry_destroy(a.registry);
    (void)wl_display_flush(a.display); wl_display_disconnect(a.display); alarm(0);
    printf("ROKO_WAYLAND_EXIT reason=%s frames=%u state=%u\n",a.reason,a.frames,a.state);
    return a.frames ? 0 : 1;
}
