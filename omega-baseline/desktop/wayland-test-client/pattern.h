#ifndef ROKO_PATTERN_H
#define ROKO_PATTERN_H
#include <stdint.h>
enum { WIDTH = 320, HEIGHT = 240, STRIDE = WIDTH * 4, BYTES = STRIDE * HEIGHT };
/* Native-endian XRGB8888 words, origin at top left; alpha byte opaque. */
static uint32_t pixel(unsigned x, unsigned y, unsigned state) {
    if (x < 4 || y < 4 || x >= WIDTH - 4 || y >= HEIGHT - 4) return 0xff000000u;
    if (x >= 144 && x < 176 && y >= 104 && y < 136) return 0xffffffffu;
    static const uint32_t colors[2][4] = {
        {0xffff0000u, 0xff00ff00u, 0xff0000ffu, 0xffffff00u},
        {0xff00ffffu, 0xffff00ffu, 0xffff8000u, 0xff8040ffu}
    };
    return colors[state & 1][(y >= HEIGHT / 2) * 2 + (x >= WIDTH / 2)];
}
#endif
