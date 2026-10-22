`timescale 1ns/1ps
module control_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,tick=0,enable=0;
    reg signed [31:0] target=0,measured=0;
    reg [15:0] speed_step=5,pwm_step=8,limit=512;
    wire signed [31:0] applied,command;
    a741_pi pi(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(enable),.target(target),.measured(measured),
        .speed_step(speed_step),.pwm_step(pwm_step),.limit(limit),.applied(applied),.command(command));
    reg signed [63:0] ref_applied=0,ref_command=0,ref_integral=0;
    reg signed [63:0] rt,rm,ss,ps,cap,next_applied,error,next_i,desired;
    reg signed [31:0] old_applied,old_command;
    integer n,stage;
    reg signed [31:0] previous;
    task model;begin
        old_applied=applied;old_command=command;
        rt=$signed(target);rm=$signed(measured);
        ss=speed_step==0 ? 1:speed_step;ps=pwm_step==0 ? 1:pwm_step;cap=limit>512 ? 512:limit;
        if((ref_command>0 && rt<0)||(ref_command<0 && rt>0)||
            (ref_applied>0 && rt<0)||(ref_applied<0 && rt>0)||rt==0) begin
            if(ref_applied>ss) next_applied=ref_applied-ss;
            else if(ref_applied < -ss) next_applied=ref_applied+ss;
            else next_applied=0;
            if(ref_command>ps) desired=ref_command-ps;
            else if(ref_command < -ps) desired=ref_command+ps;
            else desired=0;
            ref_integral=0;
        end else begin
            if(rt-ref_applied>ss) next_applied=ref_applied+ss;
            else if(rt-ref_applied < -ss) next_applied=ref_applied-ss;
            else next_applied=rt;
            error=next_applied-rm;next_i=ref_integral+error/16;
            if(next_i>cap) next_i=cap;
            if(next_i < -cap) next_i=-cap;
            desired=error+next_i;
            if(!((desired>cap && error>0)||(desired < -cap && error<0))) ref_integral=next_i;
            if(desired>cap) desired=cap;
            if(desired < -cap) desired=-cap;
            if(next_applied>=0 && desired<0) desired=0;
            if(next_applied<=0 && desired>0) desired=0;
            if(desired-ref_command>ps) desired=ref_command+ps;
            if(desired-ref_command < -ps) desired=ref_command-ps;
        end
        if(desired>cap) desired=cap;
        if(desired < -cap) desired=-cap;
        ref_command=desired;ref_applied=next_applied;
    end endtask
    task pulse;begin @(negedge clk);tick=1;@(negedge clk);tick=0;end endtask
    task result;integer cycle;begin
        for(cycle=0;cycle<25;cycle=cycle+1) begin
            @(negedge clk);
            if((applied!==old_applied || command!==old_command) &&
                (applied!==ref_applied[31:0] || command!==ref_command[31:0]))
                $fatal(1,"non-atomic or incorrect PI update at cycle %0d: %0d/%0d expected %0d/%0d",cycle,applied,command,ref_applied,ref_command);
        end
        if(applied!==ref_applied[31:0] || command!==ref_command[31:0] || $signed(pi.integral)!==ref_integral || pi.state!=0)
            $fatal(1,"PI reference mismatch applied %0d/%0d command %0d/%0d integral %0d/%0d",applied,ref_applied,command,ref_command,$signed(pi.integral),ref_integral);
    end endtask
    task update;begin model; pulse; result;end endtask
    task drop_enable;begin
        @(negedge clk);enable=0;@(negedge clk);
        if(command!=0 || applied!=0 || pi.integral!=0) $fatal(1,"immediate fault disable");
        ref_applied=0;ref_command=0;ref_integral=0;enable=1;
    end endtask
    initial begin
        #50;rst_n=1;enable=1;target=100;
        for(n=0;n<20;n=n+1) update();
        if(applied!=100 || command<=0) $fatal(1,"PI acceleration");
        target=0;previous=command;
        repeat(100) @(negedge clk);
        if(command!=previous) $fatal(1,"zero target ramp ran at clock frequency");
        update();
        if(command<previous-8 || applied!=95) $fatal(1,"deceleration step");
        target=-100;
        for(n=0;n<50;n=n+1) begin
            previous=command;update();
            if(command-previous>8 || previous-command>8) $fatal(1,"reversal slew");
        end
        if(command>=0) $fatal(1,"reversal failed");
        drop_enable;target=100;measured=0;repeat(20) update();
        measured=120;repeat(80) update();
        if(command!=0 || applied!=100) $fatal(1,"overspeed test setup");
        target=-100;measured=0;
        for(n=0;n<50;n=n+1) begin
            update();if(command>0) $fatal(1,"reversal reasserted old direction after zero PWM");
        end
        // Negative errors below one integral quantum must truncate toward zero.
        drop_enable;target=5;measured=6;speed_step=50;pwm_step=128;repeat(20) update();
        if(pi.integral!=0) $fatal(1,"negative division rounded away from zero");
        target=-5;measured=-6;repeat(25) update();
        if(pi.integral!=0) $fatal(1,"positive division mismatch");

        drop_enable;target=400;measured=0;repeat(100) update();
        if(command!=512 || pi.integral>=512) $fatal(1,"positive anti-windup");
        measured=400;limit=32;update();
        if(pi.integral!=32 || command!=32) $fatal(1,"positive integral clamp");
        target=-400;measured=0;limit=512;repeat(120) update();
        if(command!=-512 || pi.integral<=-512) $fatal(1,"negative anti-windup");
        measured=-400;limit=32;update();
        if(pi.integral!=-32 || command!=-32) $fatal(1,"negative integral clamp");

        // Full encoder feedback range must never overflow into a small opposite error.
        drop_enable;target=400;measured=32'sh7fffffff;limit=512;speed_step=65535;pwm_step=65535;update();
        if(command!=0) $fatal(1,"large positive feedback reversed bridge");
        measured=-32'sh7fffffff;update();if(command!=512) $fatal(1,"large negative feedback wrapped");
        drop_enable;target=-400;measured=-32'sh7fffffff;update();
        if(command!=0) $fatal(1,"large negative feedback reversed bridge");
        measured=32'sh7fffffff;update();if(command!=-512) $fatal(1,"large positive feedback wrapped");
        drop_enable;target=32'sh7fffffff;measured=32'sh80000000;update();
        drop_enable;target=32'sh80000000;measured=32'sh7fffffff;update();

        // One update uses a snapshot even if live inputs change during the pipeline.
        drop_enable;target=100;measured=0;speed_step=5;pwm_step=8;limit=512;
        model;pulse;target=-400;measured=32'sh7fffffff;speed_step=50;pwm_step=128;limit=0;result;
        update;

        for(n=0;n<250;n=n+1) begin
            target=$signed($urandom_range(0,800))-400;measured=$signed($urandom_range(0,2000))-1000;
            speed_step=$urandom_range(0,50);pwm_step=$urandom_range(0,128);limit=$urandom_range(0,512);update();
        end

        // Withdraw enable at every pipeline stage, then ensure no old operation restarts.
        for(stage=0;stage<15;stage=stage+1) begin
            drop_enable;target=100;measured=0;speed_step=5;pwm_step=8;limit=512;update();
            pulse;repeat(stage) @(negedge clk);drop_enable;
            repeat(30) begin @(negedge clk);if(command!=0 || applied!=0 || pi.integral!=0) $fatal(1,"late commit after disable at stage %0d",stage);end
        end
        $display("PASS PI staged arithmetic/reference, 100Hz ramps, reversal, anti-windup, signed division, extreme feedback and in-flight disable");$finish;
    end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
