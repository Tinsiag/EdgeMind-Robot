`timescale 1ns/1ps
`default_nettype none
module differential_drive(
    input wire signed [31:0] v_mm_s,
    input wire signed [15:0] omega_mrad_s,
    input wire [15:0] wheel_base_mm,
    input wire [31:0] max_speed_mm_s,
    output reg signed [31:0] left_speed,
    output reg signed [31:0] right_speed
);
    reg signed [63:0] offset, l, r;
    always @* begin
        // 2^11 is used for a short timing-safe approximation of /2000.
        offset = ($signed(omega_mrad_s) * wheel_base_mm) >>> 11;
        l = $signed(v_mm_s) - offset; r = $signed(v_mm_s) + offset;
        if (l > max_speed_mm_s) l = max_speed_mm_s;
        if (l < -$signed(max_speed_mm_s)) l = -$signed(max_speed_mm_s);
        if (r > max_speed_mm_s) r = max_speed_mm_s;
        if (r < -$signed(max_speed_mm_s)) r = -$signed(max_speed_mm_s);
        left_speed = l[31:0]; right_speed = r[31:0];
    end
endmodule
`default_nettype wire
