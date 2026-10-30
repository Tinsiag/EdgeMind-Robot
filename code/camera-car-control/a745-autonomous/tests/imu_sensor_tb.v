`timescale 1ns/1ps
module imu_sensor_tb;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,ms_tick=0,calibrated=0,present=1;
    tri1 imu_sda,imu_scl,tof_sda,tof_scl,tof_xshut;
    reg slave_low=0;
    assign imu_sda=slave_low ? 1'b0:1'bz;
    wire iv,gv,au,gu,stationary;wire signed [15:0] yaw,gz;
    wire [31:0] diagnostic,seq,errors;
    a741_sensors #(.CLK_HZ(1000000),.AUX_ENABLED(0),.ALLOW_MPU6500(1)) dut(.clk(clk),.rst_n(rst_n),.ms_tick(ms_tick),
        .lidar_rx(1'b1),.imu_int(1'b0),.calibrated(calibrated),.gyro_bias(16'sd0),
        .imu_sda(imu_sda),.imu_scl(imu_scl),.tof_sda(tof_sda),.tof_scl(tof_scl),.tof_xshut(tof_xshut),
        .imu_valid(iv),.gyro_valid(gv),.angle_update(au),.gyro_update(gu),.imu_stationary(stationary),
        .yaw(yaw),.gz(gz),.imu_diagnostic(diagnostic),.imu_seq(seq),.imu_errors(errors));
    reg [7:0] registers[0:127];reg [111:0] response;
    integer i,cycles=0,seen=0;reg [7:0] header=0;
    // The wire slave responds only at 0x69; capture transmitted bytes at SCL edges.
    always @(posedge imu_scl) if(rst_n && dut.imu_bus.state==5) begin
        header={header[6:0],imu_sda};
        if(dut.imu_bus.bit_index==0) begin
            if(dut.imu_bus.header==0 && header!={dut.imu_bus.address_q,1'b0}) $fatal(1,"wire write address");
            if(dut.imu_bus.header==2 && header!=dut.imu_bus.reg_q) $fatal(1,"wire register");
            if(dut.imu_bus.header==3 && header!={dut.imu_bus.address_q,1'b1}) $fatal(1,"wire repeated START address");
            if(dut.imu_bus.header==4) registers[dut.imu_bus.reg_q]<=header;
        end
    end
    always @* begin
        case(dut.imu_bus.reg_q)
            8'h75:response=8'h70;
            8'h3a:response=1;
            8'h3b:response={16'd0,16'd0,16'd16384,16'd0,16'd0,16'd0,16'd164};
            default:response=registers[dut.imu_bus.reg_q[6:0]];
        endcase
        slave_low=0;
        if(present && dut.imu_bus.address_q==7'h69) begin
            if(dut.imu_bus.state>=7 && dut.imu_bus.state<=10) slave_low=1;
            if(dut.imu_bus.state>=14 && dut.imu_bus.state<=17)
                slave_low=!response[(dut.imu_bus.nbytes-1-dut.imu_bus.data_index)*8+dut.imu_bus.bit_index];
        end
    end
    always @(negedge clk) begin
        cycles=cycles+1;ms_tick=cycles%1000==0;
        if(gu) seen=seen+1;
        if(dut.imu_bus.sda_low && imu_sda!==1'b0) $fatal(1,"SDA must be open drain");
    end
    initial begin
        for(i=0;i<128;i=i+1) registers[i]=0;
        #50;rst_n=1;
        wait(seq>=4 && gu);@(negedge clk);
        if(!iv || !gv || !stationary || diagnostic[15:0]!=16'h7069 || !diagnostic[24] || diagnostic[23:16]!=0)
            $fatal(1,"sensor integration %h",diagnostic);
        if(errors!=1 || seen<3 || gz<160 || gz>164) $fatal(1,"address fallback or gyro conversion");
        if(registers[8'h1b]!=8'h18 || registers[8'h19]!=9 || registers[8'h1d]!=3) $fatal(1,"wire configuration");
        if(dut.tof_valid || dut.lidar_valid || tof_sda!==1'b1 || tof_scl!==1'b1)
            $fatal(1,"auxiliary sensors enabled");
        calibrated=1;wait(au);repeat(100) @(negedge clk);present=0;
        wait(!gv);repeat(100) @(negedge clk);if(iv) $fatal(1,"disconnected IMU remained valid");
        $display("PASS MPU6500 wire-level integration, 0x69 fallback/WHO, configured samples, heading and disconnected invalidation");$finish;
    end
    initial begin #20000000;$fatal(1,"watchdog");end
endmodule
