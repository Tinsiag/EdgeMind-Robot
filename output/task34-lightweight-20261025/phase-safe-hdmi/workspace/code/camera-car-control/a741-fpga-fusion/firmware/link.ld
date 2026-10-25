ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0, LENGTH = 8K }
SECTIONS {
  .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } > ram
  .data : { *(.data*) *(.sdata*) } > ram
  .bss : { *(.bss*) *(.sbss*) *(COMMON) } > ram
  /DISCARD/ : { *(.comment) *(.eh_frame*) }
  ASSERT(. < 7168, "Mission firmware leaves less than 1 KiB stack")
}
