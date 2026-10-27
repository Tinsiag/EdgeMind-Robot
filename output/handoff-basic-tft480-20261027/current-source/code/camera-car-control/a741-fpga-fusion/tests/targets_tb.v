`timescale 1ns/1ps
module targets_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst=0,enable=1,tick=0,cancel=0,rotating=0,braking=0,hold_heading=0,positive=1,tof_valid=1;
    reg signed [10:0] dl=0,dr=0;
    reg signed [15:0] yaw=0,origin=0,gz=0,bias=0;
    reg signed [31:0] turn=16384,acc=0,sl=0,sr=0;
    reg [8:0] cap=200,turn_cap=100;
    reg [5:0] step=5;
    reg [31:0] range_mm=1000;
    wire valid,out_braking;
    wire signed [31:0] tl,tr;
    a741_targets dut(.clk(clk),.rst_n(rst),.enable(enable),.tick(tick),.cancel(cancel),
        .rotating(rotating),.turn_braking(braking),.heading_hold(hold_heading),.heading_positive(positive),
        .desired_l(dl),.desired_r(dr),.yaw(yaw),.heading_origin(origin),.gz(gz),.gyro_bias(bias),
        .turn_target(turn),.accumulated_yaw(acc),.left_speed(sl),.right_speed(sr),
        .max_speed(cap),.turn_speed(turn_cap),.speed_step(step),.tof_valid(tof_valid),.clearance(range_mm),
        .valid(valid),.braking(out_braking),.target_l(tl),.target_r(tr));
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
            if(rotating) begin
                e=turn-acc;mag=e<0 ? -e:e;rate=gz-bias;if(rate<0) rate=-rate;
                sp=sl<0 ? -sl:sl;p=sr<0 ? -sr:sr;if(p>sp) sp=p;if(sp>400) sp=400;
                threshold=364+rate*(sp/(step==0 ? 1:step)+8)/18;if(threshold>4096) threshold=4096;
                if(braking || (turn>0 && e<=threshold) || (turn<0 && e>=-threshold)) begin
                    l=0;r=0;expected_braking=1;
                end else begin
                    tc=mag/32;if(tc>turn_cap) tc=turn_cap;if(tc<40) tc=40;
                    if(e<0) tc=-tc;l=-tc;r=tc;
                end
            end else begin
                p=l<0 ? -l:l;k=r<0 ? -r:r;if(k>p) p=k;
                if(p>limit_value) begin l=l*limit_value/p;r=r*limit_value/p;end
                delta=yaw-origin;c=delta;if(!positive) c=-c;c=hold_heading ? c/64:0;
                if(c>20) c=20;if(c < -20) c=-20;
                l=l+c;r=r-c;p=l<0 ? -l:l;k=r<0 ? -r:r;if(k>p) p=k;
                if(p>limit_value) begin l=l*limit_value/p;r=r*limit_value/p;end
                if(l+r>0) begin
                    if(!tof_valid || range_mm<=250) begin l=0;r=0;end
                    else if(range_mm<500) begin l=l*range_factor/250;r=r*range_factor/250;end
                end
            end
            previous_l=tl;previous_r=tr;start_job;k=0;
            while(!valid && k<250) begin
                if(tl!==previous_l || tr!==previous_r) $fatal(1,"wheel targets changed before atomic publish");
                @(negedge clk);k=k+1;
            end
            if(!valid || tl!==l || tr!==r || out_braking!==expected_braking)
                $fatal(1,"case %0d mode %b expected %0d %0d brake%b got %0d %0d brake%b in %0d cycles",n,rotating,l,r,expected_braking,tl,tr,out_braking,k);
            @(negedge clk);
        end
    endtask
    initial begin
        #50;rst=1;
        // Wrap at 16 bits, then negate in a wider type for the half-turn boundary.
        dl=100;dr=100;hold_heading=1;origin=0;yaw=-32768;
        positive=1;n=-2;run_case();positive=0;n=-1;run_case();
        for(n=0;n<120;n=n+1) begin
            dl=($random & 32'h7fffffff)%801-400;dr=($random & 32'h7fffffff)%801-400;
            cap=40+($random & 32'h7fffffff)%361;
            hold_heading=n%2;positive=n%3!=0;yaw=$random;origin=$random;
            range_mm=251+($random & 32'h7fffffff)%300;tof_valid=n%5!=0;
            run_case();
        end
        rotating=1;
        for(n=0;n<80;n=n+1) begin
            turn=n%2 ? 16384:-16384;acc=($random & 32'h7fffffff)%40001-20000;
            gz=$random;bias=$random;step=1+n%50;sl=n*7-200;sr=300-n*7;braking=n%7==0;
            run_case();
        end
        // Abort each division phase and prove it cannot publish a stale target.
        rotating=0;hold_heading=1;dl=400;dr=300;cap=100;range_mm=375;tof_valid=1;
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
        dl=-80;dr=-40;hold_heading=0;range_mm=1000;n=999;run_case;
        $display("PASS multi-cycle targets: 203 reference cases, half-turn signs, atomic wheels, ToF, braking, commit/divider cancellation and lost enable");$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
