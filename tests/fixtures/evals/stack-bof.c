/* Eval fixture: network-facing header parser with a planted stack overflow.
 * Expected finding: strcpy into fixed 32-byte stack buffer in parse_header
 * (attacker-controlled name_len, no bounds check) → CRITICAL.
 */
#include <string.h>

typedef struct {
    unsigned char magic[2];
    unsigned char name_len;
    char payload[64];
} packet_hdr_t;

int process_packet(const char *buf, unsigned int len)
{
    packet_hdr_t hdr;
    char name[32];

    if (len < sizeof(packet_hdr_t))
        return -1;
    memcpy(&hdr, buf, sizeof(hdr));
    if (hdr.magic[0] != 'S' || hdr.magic[1] != 'P')
        return -1;

    /* name_len is attacker-controlled (0-255) and never checked against
     * sizeof(name) — classic stack buffer overflow via strcpy. */
    strcpy(name, hdr.payload);

    return register_client(name);
}
