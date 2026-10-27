`timescale 1ns/1ps
module targets_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,enable=1,tick=0,cancel=0,tof_valid=1;
    reg signed [10:0] dl=0,dr=0;
    reg [8:0] cap=200;
    reg [31:0] range_mm=1000;
    wire valid;wire signed [31:0] tl,tr;
    a741_targets dut(.clk(clk),.rst_n(rst),.enable(enable),.tick(tick),.cancel(cancel),
        .desired_l(dl),.desired_r(dr),.max_speed(cap),.tof_valid(tof_valid),.clearance(range_mm),
        .valid(valid),.target_l(tl),.target_r(tr));
    integer n,k,l,r,p,c,e,mag,rate,sp,threshold,tc,limit_value,range_factor;
    reg expected_braking;
    reg signed [15:0] delta;
    reg signed [31:0] previous_l,previous_r;
    integer wait_cycles;
    task start_job;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;end
    endtask
    task await_state;
        input [3:0] wanted;
        begin
            wait_cycles=0;
            while(dut.state!=wanted && wait_cycles<250) begin @(negedge clk);wait_cycles=wait_cycles+1;end
            if(wait_cycles>=250) $fatal(1,"target state %0d not reached",wanted);
        end
    endtask
    task no_late_publish;
        begin
            repeat(260) begin @(negedge clk);if(valid) $fatal(1,"aborted boundary result published");end
        end
    endtask
    task run_case;
        begin
            l=dl;r=dr;expected_braking=0;limit_value=cap;range_factor=range_mm-250;
            p=l<0 ? -l:l;k=r<0 ? -r:r;if(k>p) p=k;
            if(p>limit_value) begin l=l*limit_value/p;r=r*limit_value/p;end
                if(l+r>0) begin
                    if(!tof_valid || range_mm<=250) begin l=0;r=0;end
                    else if(range_mm<500) begin l=l*range_factor/250;r=r*range_factor/250;end
                end
            previous_l=tl;previous_r=tr;start_job;k=0;
            while(!valid && k<250) begin
                if(tl!==previous_l || tr!==previous_r) $fatal(1,"wheel targets changed before atomic publish");
                @(negedge clk);k=k+1;
            end
            if(!valid || tl!==l || tr!==r)
                $fatal(1,"case %0d expected %0d %0d got %0d %0d in %0d cycles",n,l,r,tl,tr,k);
            @(negedge clk);
        end
    endtask
    initial begin
        #50;rst=1;
        for(n=0;n<120;n=n+1) begin
            dl=($random & 32'h7fffffff)%801-400;dr=($random & 32'h7fffffff)%801-400;
            cap=40+($random & 32'h7fffffff)%361;
            range_mm=251+($random & 32'h7fffffff)%300;tof_valid=n%5!=0;
            run_case();
        end
        // Abort each division phase and prove it cannot publish a stale target.
        dl=400;dr=300;cap=100;range_mm=375;tof_valid=1;
        for(n=1;n<180;n=n+17) begin
            @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(n) @(negedge clk);
            cancel=1;@(negedge clk);cancel=0;
            repeat(260) begin @(negedge clk);if(valid) $fatal(1,"cancelled result published");end
        end
        // Cancel on the final commit state, after every divider has finished.
        start_job;await_state(dut.DONE);cancel=1;
        @(negedge clk);cancel=0;no_late_publish;
        // A lost enable during the last divider also discards the computation.
        start_job;wait_cycles=0;
        while(!(dut.state==dut.RIGHT_WAIT && dut.after_scale==dut.DONE) && wait_cycles<250) begin
            @(negedge clk);wait_cycles=wait_cycles+1;
        end
        if(wait_cycles>=250) $fatal(1,"final division not reached");
        enable=0;@(negedge clk);enable=1;no_late_publish;
        // Cancel/disable at a valid pulse must prevent any later re-publication.
        start_job;wait_cycles=0;
        while(!valid && wait_cycles<250) begin @(negedge clk);wait_cycles=wait_cycles+1;end
        if(!valid) $fatal(1,"valid boundary not reached");
        cancel=1;@(negedge clk);cancel=0;no_late_publish;
        start_job;wait_cycles=0;
        while(!valid && wait_cycles<250) begin @(negedge clk);wait_cycles=wait_cycles+1;end
        if(!valid) $fatal(1,"enabled boundary not reached");
        enable=0;@(negedge clk);enable=1;no_late_publish;
        // A new tick is required after abort, and both wheels can run again.
        dl=-80;dr=-40;range_mm=1000;n=999;run_case;
        $display("PASS multi-cycle targets: 121 reference cases, atomic wheels, ToF, commit/divider cancellation and lost enable");$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
