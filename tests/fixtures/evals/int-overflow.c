/* Eval fixture: integer overflow in an allocation size calculation.
 * Expected finding: count * 8 computed in 32-bit int wraps when count is
 * large (e.g. 0x20000000), malloc allocates a small buffer, loop writes
 * count entries → heap overflow. Directive 6 (extreme-value data flow).
 */
#include <stdlib.h>

typedef struct {
    unsigned long id;
    void *next;
} entry_t;   /* 16 bytes on x86-64, but size is computed as count * 8 */

int load_entries(const unsigned int *counts, unsigned int n_counts)
{
    unsigned int count = counts[0];
    int total_size = count * 8;          /* wraps for count >= 0x20000000 */
    entry_t *table = malloc(total_size); /* tiny allocation */

    if (!table)
        return -1;

    for (unsigned int i = 0; i < count; i++) {
        table[i].id = i;                 /* writes past the allocation */
        table[i].next = NULL;
    }

    return publish_table(table, count);
}
