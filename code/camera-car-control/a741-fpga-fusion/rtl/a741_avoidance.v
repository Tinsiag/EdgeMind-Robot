`timescale 1ns/1ps
`default_nettype none
// Avoidance-only personality. Retain the command/snapshot shape without
// instantiating map, pose, scan matching, planning or path tracking hardware.
module a741_avoidance #(parameter GEOMETRY_VERIFIED=0,CONFIG_CRC=0,SEQUENCE_TEST=0,BUTTON_AUTONOMOUS=0)(
    input wire clk,rst_n,ms_tick,tick,armed,link_alive,imu_valid,tilt_valid,
    input wire [15:0] motor_faults,input wire signed [31:0] manual_left,manual_right,
    input wire signed [15:0] yaw,roll,pitch,input wire lidar_valid,
    input wire [15:0] lidar_front,lidar_left,lidar_right,
    input wire manual_stop,manual_scan_valid,input wire [9:0] manual_limit,
    input wire supervisor_alive,supervisor_fault,input wire [31:0] supervisor_uptime,
    input wire command,input wire [7:0] kind,input wire [255:0] payload,input wire button_start,
    output reg reply_done,output reg [255:0] reply,
    output wire drive_enabled,force_stop,output wire signed [31:0] drive_left,drive_right,
    output wire sensor_stop,output wire [9:0] sensor_limit,
    output wire [7:0] state,fault,output wire [15:0] front_distance
);
    reg avoid_running,avoid_turning,avoid_turn_left;
    reg sequence_running,button_pending;
    reg [2:0] sequence_phase;
    reg [8:0] phase_ticks;
    reg [3:0] transition_ticks;
    reg [10:0] start_wait_ticks;
    reg [7:0] turn_ticks;
    reg escape_reverse,escape_search;
    reg [9:0] escape_ticks;
    wire valid_scan=lidar_valid && lidar_front!=16'hffff &&
        lidar_left!=16'hffff && lidar_right!=16'hffff;
    wire left_open=valid_scan && lidar_left>=500;
    wire right_open=valid_scan && lidar_right>=500;
    wire blocked=!valid_scan || (avoid_turning ?
        (avoid_turn_left ? !left_open:!right_open):
        (!escape_reverse && !escape_search && lidar_front<=450 && !left_open && !right_open));
    // Both personalities stop on an invalid scan.  This is a hard safety
    // boundary: a lost LD06 stream cannot silently turn into a blind drive.
    // A close front return also stops the deterministic sequence; the
    // autonomous personality may turn only after a valid side opening exists.
    wire sequence_blocked=!valid_scan || lidar_front<=450;
    wire run_enabled=SEQUENCE_TEST!=0 ? sequence_running:avoid_running;
    wire live=run_enabled && armed && link_alive && motor_faults==0 && supervisor_alive && !supervisor_fault;
    wire signed [31:0] forward_speed=lidar_front<=450 ? 32'sd0:
        lidar_front<=900 ? 32'sd60:32'sd120;
    wire signed [31:0] sequence_left = sequence_phase==0 ? 32'sd120 :
        sequence_phase==1 ? -32'sd100 : sequence_phase==2 ? -32'sd80 : 32'sd80;
    wire signed [31:0] sequence_right = sequence_phase==0 ? 32'sd120 :
        sequence_phase==1 ? -32'sd100 : sequence_phase==2 ? 32'sd80 : -32'sd80;
    assign sensor_stop=run_enabled ? (SEQUENCE_TEST!=0 ? sequence_blocked:blocked):manual_stop;
    assign sensor_limit=run_enabled ? (SEQUENCE_TEST!=0 ? (sequence_blocked ? 10'd0:10'd400) :
        (blocked ? 10'd0:avoid_turning ? 10'd80:(forward_speed<=0 ? 10'd0 : forward_speed[9:0]))) : manual_limit;
    assign drive_enabled=run_enabled;
    assign drive_left=!live || (SEQUENCE_TEST!=0 ? sequence_blocked:(blocked)) ? 32'sd0:
        SEQUENCE_TEST!=0 ? (transition_ticks!=0 ? 32'sd0:sequence_left):
        escape_reverse ? -32'sd60 : escape_search ? (avoid_turn_left ? -32'sd80:32'sd80):
        (avoid_turning ? (avoid_turn_left ? -32'sd80:32'sd80):forward_speed);
    assign drive_right=!live || (SEQUENCE_TEST!=0 ? sequence_blocked:(blocked)) ? 32'sd0:
        SEQUENCE_TEST!=0 ? (transition_ticks!=0 ? 32'sd0:sequence_right):
        escape_reverse ? -32'sd60 : escape_search ? (avoid_turn_left ? 32'sd80:-32'sd80):
        (avoid_turning ? (avoid_turn_left ? 32'sd80:-32'sd80):forward_speed);
    // Invalid radar data and a closed corridor are latched by the motion
    // supervisor.  This prevents a transient sensor return from silently
    // restarting a stopped S1 session.
    wire autonomous_hard_stop=!valid_scan || (escape_search && escape_ticks>=10'd800);
    assign force_stop=run_enabled && (!armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault ||
        (SEQUENCE_TEST!=0 ? sequence_blocked:autonomous_hard_stop));
    assign state=SEQUENCE_TEST!=0 ? (!sequence_running ? 8'd0:sequence_blocked ? 8'd6:
        transition_ticks!=0 ? 8'd5:(8'd10+sequence_phase)):
        (!avoid_running ? 8'd0:!valid_scan ? 8'd5:escape_reverse ? 8'd7:escape_search ? 8'd8:blocked ? 8'd4:
        avoid_turning ? (avoid_turn_left ? 8'd2:8'd3):8'd1);
    assign fault=SEQUENCE_TEST!=0 ? (!sequence_running ? 8'd0:sequence_blocked ? 8'd3:8'd0):
        (!avoid_running ? 8'd0:!valid_scan ? 8'd1:blocked ? 8'd2:8'd0);
    assign front_distance=lidar_front;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin
            avoid_running<=0;avoid_turning<=0;avoid_turn_left<=0;sequence_running<=0;
            sequence_phase<=0;phase_ticks<=0;transition_ticks<=0;button_pending<=0;start_wait_ticks<=0;turn_ticks<=0;escape_reverse<=0;escape_search<=0;escape_ticks<=0;reply_done<=0;reply<=0;
        end else begin
            reply_done<=0;
            if(BUTTON_AUTONOMOUS!=0 && button_start) begin
                if(run_enabled) begin
                    avoid_running<=0;sequence_running<=0;avoid_turning<=0;avoid_turn_left<=0;turn_ticks<=0;escape_reverse<=0;escape_search<=0;escape_ticks<=0;
                    button_pending<=0;phase_ticks<=0;transition_ticks<=0;
                end else begin button_pending<=1;start_wait_ticks<=0;end
            end
            if(button_pending && ms_tick) begin
                if(start_wait_ticks==11'd999) begin button_pending<=0;start_wait_ticks<=0;end
                else start_wait_ticks<=start_wait_ticks+1'b1;
            end
            if(button_pending && armed && motor_faults==0 && supervisor_alive && !supervisor_fault) begin
                if(valid_scan && (SEQUENCE_TEST!=0 || manual_scan_valid)) begin
                if(SEQUENCE_TEST!=0) begin
                    sequence_running<=1;sequence_phase<=0;phase_ticks<=0;transition_ticks<=4'd10;
                end else begin
                    avoid_running<=1;avoid_turning<=0;avoid_turn_left<=0;turn_ticks<=0;escape_reverse<=0;escape_search<=0;escape_ticks<=0;
                end
                button_pending<=0;
                start_wait_ticks<=0;
                end
            end
            if(SEQUENCE_TEST!=0 && tick && sequence_running) begin
                if(phase_ticks==9'd499) begin
                    phase_ticks<=0;sequence_phase<=sequence_phase==3 ? 0:sequence_phase+1'b1;
                    transition_ticks<=4'd10;
                end else begin
                    phase_ticks<=phase_ticks+1'b1;
                    if(transition_ticks!=0) transition_ticks<=transition_ticks-1'b1;
                end
            end
            if(ms_tick && live && valid_scan) begin
                if(escape_reverse) begin
                    if(left_open || right_open) begin
                        escape_reverse<=0;avoid_turning<=1;avoid_turn_left<=left_open && (!right_open || lidar_left>=lidar_right);turn_ticks<=0;escape_ticks<=0;
                    end else if(escape_ticks!=0) escape_ticks<=escape_ticks-1'b1;
                    else begin escape_reverse<=0;escape_search<=1;escape_ticks<=0;end
                end else if(escape_search) begin
                    if(left_open || right_open) begin
                        escape_search<=0;avoid_turning<=1;avoid_turn_left<=left_open && (!right_open || lidar_left>=lidar_right);turn_ticks<=0;escape_ticks<=0;
                    end else if(escape_ticks==10'd800) begin
                        // Bounded search: leave the vehicle stopped until a
                        // fresh S1 press rather than spinning forever.
                        escape_search<=0;escape_ticks<=0;avoid_running<=0;
                    end else escape_ticks<=escape_ticks+1'b1;
                end else if(!avoid_turning && lidar_front<=450 && !left_open && !right_open) begin
                    if(escape_ticks>=10'd200) begin escape_reverse<=1;escape_ticks<=10'd300;end
                    else escape_ticks<=escape_ticks+1'b1;
                end else if(avoid_turning) begin
                    if(lidar_front>=600) begin avoid_turning<=0;turn_ticks<=0;end
                    else if(turn_ticks!=8'hff) turn_ticks<=turn_ticks+1'b1;
                    // If the chosen side closes while the opposite side is
                    // open, change side after a bounded 200 ms search.
                    if(turn_ticks>=8'd19 && !((avoid_turn_left && left_open) || (!avoid_turn_left && right_open)) &&
                        (avoid_turn_left ? right_open:left_open)) begin
                        avoid_turn_left<=!avoid_turn_left;turn_ticks<=0;
                    end
                end else if(!escape_reverse && !escape_search && lidar_front<=450 && (left_open || right_open)) begin
                    avoid_turning<=1;
                    avoid_turn_left<=left_open && (!right_open || lidar_left>=lidar_right);
                    turn_ticks<=0;
                end
            end
            if(command && kind>=8'h50 && kind<=8'h59 || (SEQUENCE_TEST!=0 && command && kind==8'h58)) begin
                reply_done<=1;reply<=0;
                case(kind)
                    8'h58: begin
                        if(SEQUENCE_TEST==0 || payload[7:0]>1) reply[7:0]<=2;
                        else if(payload[7:0]==0) begin sequence_running<=0;phase_ticks<=0;transition_ticks<=0;end
                        else if(sequence_running || !armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault || manual_left!=0 || manual_right!=0) reply[7:0]<=1;
                        else begin sequence_running<=1;sequence_phase<=0;phase_ticks<=0;transition_ticks<=4'd10;end
                    end
                    8'h59:if(payload[7:0]>1 || (payload[7:0]==1 &&
                        (avoid_running || GEOMETRY_VERIFIED==0 || !armed || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault ||
                         manual_left!=0 || manual_right!=0))) reply[7:0]<=1;
                        else begin avoid_running<=payload[7:0]==1;avoid_turning<=0;avoid_turn_left<=0;end
                    8'h56:begin avoid_running<=0;avoid_turning<=0;turn_ticks<=0;escape_reverse<=0;escape_search<=0;escape_ticks<=0;end
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
            if((!armed && !(BUTTON_AUTONOMOUS!=0 && button_pending)) || !link_alive || motor_faults!=0 || !supervisor_alive || supervisor_fault ||
                (command && (kind==3 || kind==4 || kind==8'h56 ||
                 (kind==8'h59 && payload[7:0]==0) || (kind==8'h58 && payload[7:0]==0)))) begin
                avoid_running<=0;avoid_turning<=0;turn_ticks<=0;escape_reverse<=0;escape_search<=0;escape_ticks<=0;
                sequence_running<=0;phase_ticks<=0;transition_ticks<=0;button_pending<=0;start_wait_ticks<=0;
            end
        end
endmodule
`default_nettype wire
