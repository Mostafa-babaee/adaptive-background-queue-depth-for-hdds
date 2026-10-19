#ifndef MILESTONE1_PATTERN_H
#define MILESTONE1_PATTERN_H

#include <stdint.h>

/* Must match tools/create_fixture.py. The expected byte uses absolute offset. */
static inline unsigned char expected_byte(uint64_t position)
{
    uint64_t within = position & UINT64_C(4095);
    return (unsigned char)(((position >> 12) * UINT64_C(37) +
                            within * UINT64_C(17) + (within >> 8) +
                            (position >> 20) * UINT64_C(53)) & UINT64_C(255));
}

#endif
