// Select exactly one complete frame from the official DVP_Capture outputs.
// DataVs is active high outside sensor VSYNC; DataHs follows delayed HREF.
module camera_frame_gate #(
    parameter FRAME_WIDTH = 800,
    parameter FRAME_HEIGHT = 480
)(
    input clk, input reset_n, input ready,
    input frame_active, input line_active, input pixel_valid,
    output source_valid,
    output reg frame_done, output reg frame_good, output reg geometry_error,
    output reg [18:0] frame_pixels,
    output reg [11:0] line_pixels,
    output reg [10:0] frame_lines
);
    reg previous_frame, previous_line;
    reg capturing, saw_blank;
    wire start_frame = ready && saw_blank && !previous_frame && frame_active
                     && !capturing && !frame_done && !geometry_error;
    assign source_valid = ready && capturing && frame_active && pixel_valid
                        && !frame_done && !geometry_error;
    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            previous_frame <= 0; previous_line <= 0;
            capturing <= 0; saw_blank <= 0;
            frame_done <= 0; frame_good <= 0; geometry_error <= 0;
            frame_pixels <= 0; line_pixels <= 0; frame_lines <= 0;
        end else begin
            previous_frame <= frame_active;
            previous_line <= line_active;
            if (ready && !frame_active) saw_blank <= 1;
            if (start_frame) begin
                capturing <= 1;
                frame_pixels <= 0; line_pixels <= 0; frame_lines <= 0;
                // The official sensor timing has blanking before first HREF.
                if (pixel_valid || line_active) geometry_error <= 1;
            end else if (capturing && !frame_done) begin
                if (pixel_valid && frame_active) begin
                    frame_pixels <= frame_pixels + 1'b1;
                    line_pixels <= line_pixels + 1'b1;
                    if (!line_active || line_pixels >= FRAME_WIDTH ||
                        frame_pixels >= FRAME_WIDTH * FRAME_HEIGHT)
                        geometry_error <= 1;
                end
                if (previous_line && !line_active) begin
                    frame_lines <= frame_lines + 1'b1;
                    line_pixels <= 0;
                    if (line_pixels != FRAME_WIDTH || frame_lines >= FRAME_HEIGHT)
                        geometry_error <= 1;
                end
                if (previous_frame && !frame_active) begin
                    capturing <= 0; frame_done <= 1;
                    if (frame_pixels == FRAME_WIDTH * FRAME_HEIGHT &&
                        frame_lines == FRAME_HEIGHT && line_pixels == 0 &&
                        !geometry_error && !previous_line && !pixel_valid)
                        frame_good <= 1;
                    else geometry_error <= 1;
                end
            end
        end
    end
endmodule
