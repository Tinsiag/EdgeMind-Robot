`timescale 1ns/1ps
module mpu_heading_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,sample_update=0,sample_valid=1,calibrated=0;
    reg signed [15:0] raw_gz=0,ax=0,ay=0,az=16384,gyro_bias=0;
    reg [31:0] sample_time=0;
    wire signed [15:0] yaw,gz;wire angle_update,gyro_update,valid,stationary;
    mpu6050_heading dut(.*);integer n,cycles;
    reg reference_previous=0,expected_angle,expected_valid;
    reg signed [63:0] reference_rate,reference_increment;
    reg signed [47:0] reference_phase=0;
    task set_calibration(input value);begin
        @(negedge clk);calibrated=value;reference_phase=0;repeat(3) @(negedge clk);
    end endtask
    task sample(input signed [15:0] rate,input [31:0] dt);begin
        reference_rate=($signed(rate)*64'sd1024)/1025;
        expected_valid=!reference_previous || (dt>0 && dt<=30);
        expected_angle=!calibrated || (reference_previous && dt>0 && dt<=30);
        if(!calibrated) reference_phase=0;
        else if(expected_angle) begin
            reference_increment=((reference_rate-$signed(gyro_bias))*64'sd65536*$signed({1'b0,dt}))/90;
            reference_phase=reference_phase+reference_increment;
        end
        reference_previous=1;
        @(negedge clk);raw_gz=rate;sample_time=sample_time+dt;sample_update=1;
        @(negedge clk);sample_update=0;cycles=0;
        while(!gyro_update && cycles<250) begin @(negedge clk);cycles=cycles+1;end
        if(cycles>=250) $fatal(1,"sample processing exceeded 5 us");
        if(gz!==reference_rate[15:0]) $fatal(1,"gyro conversion got %d expected %d",gz,reference_rate);
        if(angle_update!==expected_angle) $fatal(1,"angle/gyro updates do not describe the same sample");
        if(yaw!==reference_phase[31:16]) $fatal(1,"fractional integration got %d expected %d",yaw,$signed(reference_phase[31:16]));
        if(valid!==expected_valid) $fatal(1,"interval validity mismatch for %d ms",dt);
        repeat(2) @(negedge clk);
        if(gyro_update || angle_update) $fatal(1,"update pulse wider than one clock");
    end endtask
    task invalidate;begin
        @(negedge clk);sample_valid=0;reference_previous=0;reference_phase=0;
        repeat(3) @(negedge clk);
        if(valid || yaw!=0) $fatal(1,"stale heading");
        sample_valid=1;
    end endtask
    initial begin
        #50;rst_n=1;sample(0,10);set_calibration(1);
        for(n=0;n<100;n=n+1) sample(1476,10);
        if(yaw<16370 || yaw>16390) $fatal(1,"90 degree integration %d",yaw);
        for(n=0;n<120;n=n+1) sample(1476,10);
        if(yaw> -29470 || yaw< -29520) $fatal(1,"180 degree wrap %d",yaw);
        sample(1476,100);if(valid) $fatal(1,"gap accepted");
        set_calibration(0);invalidate;
        gyro_bias=1638;sample(1640,10);set_calibration(1);
        for(n=0;n<100;n=n+1) sample(1640,10);
        if(yaw!=0) $fatal(1,"bias not removed");

        set_calibration(0);gyro_bias=0;sample(0,10);set_calibration(1);
        for(n=0;n<100;n=n+1) sample(-1476,10);
        if(yaw> -16370 || yaw< -16390) $fatal(1,"negative 90 degree integration %d",yaw);
        sample(1,1);sample(-1,1);sample(1024,29);sample(-1024,30);
        sample(1025,0);sample(-1025,31);sample(0,10);
        gyro_bias=32767;sample(-32768,30);
        gyro_bias=-32768;sample(32767,30);

        // Millisecond timestamp rollover must preserve unsigned interval subtraction.
        invalidate;sample_time=32'hfffffff8;gyro_bias=0;sample(0,0);sample(1476,10);

        // Invalid data or recalibration cancels both divisions and their eventual update pulses.
        @(negedge clk);raw_gz=1476;sample_time=sample_time+10;sample_update=1;
        @(negedge clk);sample_update=0;repeat(8) @(negedge clk);invalidate;
        repeat(120) begin @(negedge clk);if(gyro_update || angle_update) $fatal(1,"stale computation committed");end
        sample(0,10);
        @(negedge clk);raw_gz=1476;sample_time=sample_time+10;sample_update=1;
        @(negedge clk);sample_update=0;repeat(45) @(negedge clk);set_calibration(0);
        repeat(120) begin @(negedge clk);if(gyro_update || angle_update) $fatal(1,"old calibration committed");end
        set_calibration(1);sample(-1025,10);

        // Unexpected input overrun is invalidated rather than committing an older yaw.
        @(negedge clk);sample_time=sample_time+10;sample_update=1;
        @(negedge clk);sample_update=0;repeat(4) @(negedge clk);
        sample_time=sample_time+10;sample_update=1;
        @(negedge clk);sample_update=0;reference_previous=0;reference_phase=0;
        repeat(120) begin @(negedge clk);if(gyro_update || angle_update) $fatal(1,"overrun computation committed");end
        if(valid || yaw!=0) $fatal(1,"overrun not invalidated");
        sample(0,10);sample(-1025,10);
        ax=9000;#10;if(stationary) $fatal(1,"tilted module accepted as flat");
        $display("PASS MPU6050 exact pipelined conversion/integration, signed extremes, wrap, bias, cancellation, gaps and flat-install check");$finish;
    end
    initial begin #5000000;$fatal(1,"heading test timeout");end
endmodule
