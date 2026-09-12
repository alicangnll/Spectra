/* Eval fixture: unsigned underflow defeating a length check (logic bug).
 * Expected finding: hdr_len - 4 wraps to a huge size_t when hdr_len < 4,
 * so the bounds check passes and the token comparison reads out of bounds;
 * more importantly the "authenticated" path is reachable with a truncated
 * header. Directive 5 (assumption inversion) + directive 6 (extreme values).
 */
#include <string.h>

int check_session_token(const unsigned char *buf, unsigned int hdr_len)
{
    const unsigned char secret[8] = {0xde, 0xad, 0xbe, 0xef, 0x01, 0x02, 0x03, 0x04};
    unsigned char token[8];

    /* intended: body must fit. actual: hdr_len < 4 wraps the subtraction,
     * the comparison succeeds, and memcpy reads/writes far past buf. */
    size_t body_len = hdr_len - 4;
    if (body_len > 64)
        return 0;

    memcpy(token, buf + 4, body_len);

    if (memcmp(token, secret, 8) == 0)
        return 1;   /* authenticated */

    return 0;
}
