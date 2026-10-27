/* Bare-metal health supervisor: no maps, destinations or waypoint tasks. */
typedef unsigned int u32;
static volatile u32 *const io = (volatile u32 *)0x10000000;
int main(void)
{
    for (;;) {
        io[9] = 0x0741c0de;
        io[10] = io[1];
    }
}
