/* Self-authored software-device/pbuffer test. Not compositor or scanout proof. */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <string.h>
static int extension(const char *list, const char *name) {
    size_t n = strlen(name);
    if (!list) return 0;
    for (const char *p = list; (p = strstr(p, name)); p += n)
        if ((p == list || p[-1] == ' ') && (p[n] == ' ' || p[n] == '\0')) return 1;
    return 0;
}
int main(void) {
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLContext context = EGL_NO_CONTEXT;
    EGLSurface surface = EGL_NO_SURFACE;
    int result = 1;
    PFNEGLQUERYDEVICESEXTPROC query_devices = (PFNEGLQUERYDEVICESEXTPROC)eglGetProcAddress("eglQueryDevicesEXT");
    PFNEGLQUERYDEVICESTRINGEXTPROC query_string = (PFNEGLQUERYDEVICESTRINGEXTPROC)eglGetProcAddress("eglQueryDeviceStringEXT");
    PFNEGLGETPLATFORMDISPLAYEXTPROC platform_display = (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDeviceEXT devices[16]; EGLint count = 0;
    if (!query_devices || !query_string || !platform_display || !query_devices(16, devices, &count)) goto done;
    for (EGLint i = 0; i < count; i++) {
        const char *ext = query_string(devices[i], EGL_EXTENSIONS);
        if (extension(ext, "EGL_MESA_device_software")) {
            display = platform_display(EGL_PLATFORM_DEVICE_EXT, devices[i], NULL);
            printf("ROKO_EGL_SOFTWARE_DEVICE index=%d\n", i);
            break;
        }
    }
    EGLint major, minor;
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor)) goto done;
    printf("ROKO_EGL_VERSION %d.%d\n", major, minor);
    const EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE};
    EGLConfig config; EGLint configs = 0;
    if (!eglChooseConfig(display, attributes, &config, 1, &configs) || configs < 1 || !eglBindAPI(EGL_OPENGL_ES_API)) goto done;
    const EGLint ctxattrs[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    context = eglCreateContext(display, config, EGL_NO_CONTEXT, ctxattrs);
    const EGLint pbattrs[] = {EGL_WIDTH, 8, EGL_HEIGHT, 8, EGL_NONE};
    surface = eglCreatePbufferSurface(display, config, pbattrs);
    if (context == EGL_NO_CONTEXT || surface == EGL_NO_SURFACE || !eglMakeCurrent(display, surface, surface, context)) goto done;
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    if (!renderer) goto done;
    printf("ROKO_EGL_RENDERER %s\n", renderer);
    if (!strstr(renderer, "llvmpipe")) goto done;
    glDisable(GL_DITHER);
    glViewport(0, 0, 8, 8);
    glClearColor(17.0f / 255, 34.0f / 255, 51.0f / 255, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    unsigned char pixels[8 * 8 * 4];
    memset(pixels, 0, sizeof pixels);
    glReadPixels(0, 0, 8, 8, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    if (glGetError() != GL_NO_ERROR) goto done;
    for (unsigned i = 0; i < sizeof pixels; i += 4)
        if (pixels[i] != 17 || pixels[i+1] != 34 || pixels[i+2] != 51 || pixels[i+3] != 255) {
            printf("ROKO_EGL_PIXEL_MISMATCH index=%u rgba=%u,%u,%u,%u\n", i/4, pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]);
            goto done;
        }
    puts("ROKO_EGL_PIXELS_PASSED pixels=64 rgba=17,34,51,255");
    result = 0;
done:
    if (result) printf("ROKO_EGL_FAILED error=0x%x\n", eglGetError());
    if (display != EGL_NO_DISPLAY) {
        eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
        if (context != EGL_NO_CONTEXT) eglDestroyContext(display, context);
        eglTerminate(display);
    }
    eglReleaseThread();
    puts("ROKO_EGL_CLEANUP_DONE");
    return result;
}
