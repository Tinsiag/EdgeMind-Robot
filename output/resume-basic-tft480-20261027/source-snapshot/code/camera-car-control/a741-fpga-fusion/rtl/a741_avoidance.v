`timescale 1ns/1ps
`default_nettype none
// Avoidance-only personality. Retain the command/snapshot shape without
// instantiating map, pose, scan matching, planning or path tracking hardware.
module a741_avoidance #(parameter GEOMETRY_VERIFIED=0,CONFIG_CRC=0)(
    input wire clk,rst_n,ms_tick,armed,link_alive,imu_valid,tilt_valid,
    input wire [15:0] motor_faults,input wire signed [31:0] manual_left,manual_right,
    input wire signed [15:0] yaw,roll,pitch,input wire lidar_valid,
    input wire [15:0] lidar_front,lidar_left,lidar_right,
    input wire manual_stop,manual_scan_valid,input wire [9:0] manual_limit,
    input wire supervisor_alive,supervisor_fault,input wire [31:0] supervisor_uptime,
    input wire command,input wire [7:0] kind,input wire [255:0] payload,
    output reg reply_done,output reg [255:0] reply,
    output wire drive_enabled,force_stop,output wire signed [31:0] drive_left,drive_right,
    output wire sensor_stop,output wire [9:0] sensor_limit,
    output wire [7:0] state,fault,output wire [15:0] front_distance
);
    reg avoid_running,avoid_turning,avoid_turn_left;
    wire valid_scan=lidar_valid && lidar_front!=16'hffff &&
        lidar_left!=16'hffff && lidar_right!=16'hffff;
    wire left_open=valid_scan && lidar_left>=500;
    wire right_open=valid_scan && lidar_right>=500;
    wire blocked=!valid_scan || (avoid_turning ?
        (avoid_turn_left ? !left_open:!right_open):
        (lidar_front<=450 && !left_open && !right_open));
    wire live=avoid_running && armed && link_alive && motor_faults==0 && supervisor_alive && !supervisor_fault;
    wire signed [31:0] forward_speed=lidar_front<=450 ? 32'sd0:
        lidar_front<=900 ? 32'sd60:32'sd120;
    assign sensor_stop=avoid_running ? blocked:manual_stop;
    assign sensor_limit=avoid_running ? (blocked ? 10'd0:avoid_turning ? 10'd80:10'(forward_speed)):manual_limit;
    assign drive_enabled=avoid_running;
    assign drive_left=!live || blocked ? 32'sd0:avoid_turning ?
        (avoid_turn_left ? -32'sd80:32'sd80):forward_speed;
    assign drive_right=!live || blocked ? 32'sd0:avoid_turning ?
        (avoid_turn_left ? 32'sd80:-32'sd80):forward_speed;
    assign force_stop=avoid_running && (!armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault);
    assign state=!avoid_running ? 8'd0:!valid_scan ? 8'd5:blocked ? 8'd4:
        avoid_turning ? (avoid_turn_left ? 8'd2:8'd3):8'd1;
    assign fault=!avoid_running ? 8'd0:!valid_scan ? 8'd1:blocked ? 8'd2:8'd0;
    assign front_distance=lidar_front;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            avoid_running<=0;avoid_turning<=0;avoid_turn_left<=0;reply_done<=0;reply<=0;
        end else begin
            reply_done<=0;
            if(ms_tick && live && valid_scan) begin
                if(avoid_turning) begin
                    if(lidar_front>=600) avoid_turning<=0;
                end else if(lidar_front<=450 && (left_open || right_open)) begin
                    avoid_turning<=1;
                    avoid_turn_left<=left_open && (!right_open || lidar_left>=lidar_right);
                end
            end
            if(command && kind>=8'h50 && kind<=8'h59) begin
                reply_done<=1;reply<=0;
                case(kind)
                    8'h59:if(payload[7:0]>1 || (payload[7:0]==1 &&
                        (avoid_running || GEOMETRY_VERIFIED==0 || !armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault ||
                         manual_left!=0 || manual_right!=0))) reply[7:0]<=1;
                        else begin avoid_running<=payload[7:0]==1;avoid_turning<=0;avoid_turn_left<=0;end
                    8'h56:begin avoid_running<=0;avoid_turning<=0;end
                    8'h57:begin
                        reply[15:8]<=state;reply[23:16]<=fault;
                        reply[31:24]<={GEOMETRY_VERIFIED!=0,imu_valid,tilt_valid,2'd0,manual_scan_valid,valid_scan,avoid_running};
                        reply[47:32]<=roll;reply[63:48]<=pitch;
                        reply[111:96]<=yaw;reply[127:112]<=front_distance;
                        reply[159:128]<={lidar_right,lidar_left};
                        reply[167:160]<={6'd0,supervisor_fault,supervisor_alive};
                        reply[207:176]<=supervisor_uptime;
                        reply[239:208]<=CONFIG_CRC;reply[247:240]<=8'd1;reply[255:248]<=8'd1;
                    end
                    default:reply[7:0]<=2; // Map/goal commands are not present.
                endcase
            end
            // Shutdown wins over every simultaneous start or turn update.
            if(!armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault ||
                (command && (kind==3 || kind==4 || kind==8'h56 ||
                 (kind==8'h59 && payload[7:0]==0)))) begin
                avoid_running<=0;avoid_turning<=0;
            end
        end
endmodule
`default_nettype wire
