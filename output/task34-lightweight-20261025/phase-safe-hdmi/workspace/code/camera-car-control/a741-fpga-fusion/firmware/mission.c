/* Bare-metal RV32I task sequencer. Planning and motor safety stay in RTL. */
typedef unsigned int u32;
#define REG(n) (*(volatile u32 *)(0x10000000u + (n)))
#define STATUS REG(0)
#define CLOCK REG(4)
#define HOST REG(8)
#define ARG REG(12)
#define ACK REG(16)
#define COMMAND REG(20)
#define COMMAND_ARG REG(24)
#define COMMAND_RESULT REG(28)
#define ACTIVE REG(32)
#define HEARTBEAT REG(36)
#define PROGRESS REG(40)

void main(void) {
    u32 route[16], count=0, index=0, phase=0, deadline=0, error=0, started=0;
    ACTIVE=0;
    for (;;) {
        u32 status=STATUS, now=CLOCK, host=HOST;
        HEARTBEAT=0x741c0deu;
        PROGRESS=index | (count<<8) | (phase<<16) | (error<<24);
        /* Hardware STOP, CPU trap and sensor/motor faults never auto-resume. */
        if ((status & 4u) || (phase && !(status & 1u))) {
            ACTIVE=0; phase=0; error=6;
        }
        if (host & 0x100u) {
            u32 op=host&255u, result=0;
            if (op==0) {
                if (phase) result=2; else {count=0; index=0; error=0;}
            } else if (op==1) {
                if (phase || count==16 || (ARG&0x8080u)) result=2;
                else route[count++]=ARG;
            } else if (op==2) {
                if (phase || !count || !(status&1u) || !(status&2u) || (status&4u)) result=1;
                else {index=0; error=0; ACTIVE=1; phase=1; deadline=now;}
            } else if (op==3) {
                ACTIVE=0; phase=0; error=0;
            } else if (op!=4) result=3;
            ACK=result;
        }
        if (!phase) continue;
        /* Bounded failure: a leg cannot keep driving indefinitely without arriving. */
        if (now-deadline>120000u) {ACTIVE=0; phase=0; error=7; continue;}
        if (phase==1 && !(COMMAND_RESULT&0x100u)) {
            COMMAND_ARG=route[index]; COMMAND=0x54; phase=2;
        } else if (phase==2 && !(COMMAND_RESULT&0x100u)) {
            if (COMMAND_RESULT&255u) {ACTIVE=0; phase=0; error=2;}
            else {COMMAND=0x55; phase=3;}
        } else if (phase==3 && !(COMMAND_RESULT&0x100u)) {
            if (COMMAND_RESULT&255u) {ACTIVE=0; phase=0; error=3;}
            else {started=now; phase=4;}
        } else if (phase==4) {
            if (status&8u) {ACTIVE=0; phase=0; error=4;}
            else if (status&16u) {
                index++;
                if (index==count) {ACTIVE=0; phase=0; error=0;}
                else {deadline=now; phase=5; started=now;}
            } else if (now-started>1000u && !(status&32u)) {
                ACTIVE=0; phase=0; error=5;
            }
        } else if (phase==5 && now-started>=300u) phase=1;
    }
}
