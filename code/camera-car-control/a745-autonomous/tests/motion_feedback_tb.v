`timescale 1ns/1ps
module motion_feedback_tb;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,tick=0,enable=1,imu_valid=1;
    reg signed [31:0] target_l=120,target_r=120,left_speed=0,right_speed=0;
    reg signed [15:0] yaw=100;
    wire signed [31:0] corrected_l,corrected_r;
    wire heading_active; wire signed [15:0] heading_error,speed_error;
    a741_motion_feedback dut(.clk(clk),.rst_n(rst_n),.tick(tick),.enable(enable),.imu_valid(imu_valid),
        .target_l(target_l),.target_r(target_r),.left_speed(left_speed),.right_speed(right_speed),.yaw(yaw),
        .corrected_l(corrected_l),.corrected_r(corrected_r),.heading_active(heading_active),
        .heading_error(heading_error),.speed_error(speed_error));
    task control_tick;
        begin @(negedge clk);tick=1;@(negedge clk);tick=0;end
    endtask
    initial begin
        #20;rst_n=1;
        // First sample establishes the heading origin without a kick.
        control_tick;
        if(corrected_l!==120 || corrected_r!==120 || !heading_active)
            $fatal(1,"straight entry changed target l=%0d r=%0d active=%0d",corrected_l,corrected_r,heading_active);
        // Positive yaw drift and a faster left wheel require left reduction
        // and right increase in the final wheel targets.
        yaw=740;left_speed=130;right_speed=110;control_tick;
        if(corrected_l!==129 || corrected_r!==111 || heading_error!==640 || speed_error!==20)
            $fatal(1,"outer correction mismatch l=%0d r=%0d yaw=%0d speed=%0d",corrected_l,corrected_r,heading_error,speed_error);
        // Reverse motion reverses the yaw correction sign, while preserving
        // the signed speed synchronizer.
        target_l=-100;target_r=-100;yaw=100;left_speed=-120;right_speed=-100;control_tick;
        yaw=740;control_tick;
        if(corrected_l!==-108 || corrected_r!==-92)
            $fatal(1,"reverse correction mismatch l=%0d r=%0d",corrected_l,corrected_r);
        // Opposite-sign commands are in-place turns and must pass through.
        target_l=-80;target_r=80;left_speed=-70;right_speed=70;yaw=2000;control_tick;
        if(corrected_l!==-80 || corrected_r!==80 || heading_active)
            $fatal(1,"turn command was modified l=%0d r=%0d active=%0d",corrected_l,corrected_r,heading_active);
        // A new straight segment must lock the post-turn heading, including
        // small drift across the signed +/-180-degree representation boundary.
        target_l=100;target_r=100;left_speed=100;right_speed=100;yaw=32700;control_tick;
        if(corrected_l!==100 || corrected_r!==100 || heading_error!==0)
            $fatal(1,"post-turn heading was not reacquired");
        yaw=-32700;control_tick;
        if(heading_error!==136 || corrected_l!==102 || corrected_r!==98)
            $fatal(1,"heading wrap created a large false correction");
        // Safety disable clears the outer target immediately.
        enable=0;@(negedge clk);
        if(corrected_l!==0 || corrected_r!==0 || heading_active)
            $fatal(1,"disable did not clear feedback output");
        $display("PASS heading hold and wheel synchronization outer feedback");$finish;
    end
    initial begin #10000;$fatal(1,"motion feedback watchdog");end
endmodule
