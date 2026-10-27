.section .text.start,"ax",@progbits
.global _start
_start:
    lui sp, 2
    call main
1:  j 1b
