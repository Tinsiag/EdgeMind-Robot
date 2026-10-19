`timescale 1ns/1ps
`default_nettype none
// Ethernet AXI stream (without preamble/FCS) -> ARP/IPv4/UDP -> control/video.
// Use a frame FIFO MAC in front so bad-FCS frames never reach the control port.
module ethernet_udp_router #(
    parameter LOCAL_MAC=48'h020000000002,LOCAL_IP=32'hc0a80002,PEER_IP=32'hc0a80003,
    parameter CONTROL_PORT=5000,HOST_CONTROL_PORT=5001,VIDEO_PORT=6102
)(
    input wire clk,rst_n,
    input wire [7:0] eth_rx_data,input wire eth_rx_valid,eth_rx_last,eth_rx_bad,
    output wire eth_rx_ready,
    output wire [7:0] eth_tx_data,output wire eth_tx_valid,eth_tx_last,eth_tx_bad,
    input wire eth_tx_ready,
    output wire [7:0] control_rx_data,output wire control_rx_valid,control_rx_last,control_rx_bad,
    input wire control_rx_ready,
    input wire [7:0] control_tx_data,input wire control_tx_valid,control_tx_last,
    input wire [15:0] control_tx_length,output wire control_tx_ready,
    input wire [7:0] video_data,input wire video_valid,video_last,
    input wire [15:0] video_length,output wire video_ready
);
    wire rst=!rst_n;
    wire ehv,ehr,epv,epr,epl,epu,thv,thr,tpv,tpr,tpl,tpu;
    wire [47:0] edst,esrc,tdst,tsrc;
    wire [15:0] etype,ttype;
    wire [7:0] epd,tpd;
    eth_axis_rx ingress(.clk(clk),.rst(rst),.s_axis_tdata(eth_rx_data),.s_axis_tkeep(1'b1),
        .s_axis_tvalid(eth_rx_valid),.s_axis_tready(eth_rx_ready),.s_axis_tlast(eth_rx_last),.s_axis_tuser(eth_rx_bad),
        .m_eth_hdr_valid(ehv),.m_eth_hdr_ready(ehr),.m_eth_dest_mac(edst),.m_eth_src_mac(esrc),.m_eth_type(etype),
        .m_eth_payload_axis_tdata(epd),.m_eth_payload_axis_tvalid(epv),.m_eth_payload_axis_tready(epr),
        .m_eth_payload_axis_tlast(epl),.m_eth_payload_axis_tuser(epu));
    eth_axis_tx egress(.clk(clk),.rst(rst),.s_eth_hdr_valid(thv),.s_eth_hdr_ready(thr),
        .s_eth_dest_mac(tdst),.s_eth_src_mac(tsrc),.s_eth_type(ttype),
        .s_eth_payload_axis_tdata(tpd),.s_eth_payload_axis_tkeep(1'b1),.s_eth_payload_axis_tvalid(tpv),
        .s_eth_payload_axis_tready(tpr),.s_eth_payload_axis_tlast(tpl),.s_eth_payload_axis_tuser(tpu),
        .m_axis_tdata(eth_tx_data),.m_axis_tvalid(eth_tx_valid),.m_axis_tready(eth_tx_ready),
        .m_axis_tlast(eth_tx_last),.m_axis_tuser(eth_tx_bad));
    wire rhv,rhr,rpv,rpr,rpl,rpu,uhv,uhr,upv,upr,upl;
    wire [7:0] rpd,upd;
    wire [31:0] rsrc,rdst;
    wire [15:0] rsport,rdport,ulen;
    wire [2:0] rflags;
    wire [12:0] rfragment;
    reg rx_active,rx_match,tx_active,tx_control,tx_header;
    reg [15:0] tx_length;
    wire choose_control=tx_control;
    assign uhv=tx_header;
    assign upd=tx_control ? control_tx_data : video_data;
    assign upv=tx_active && (tx_control ? control_tx_valid : video_valid);
    assign upl=tx_control ? control_tx_last : video_last;
    assign ulen=tx_length+16'd8;
    assign control_tx_ready=tx_active && tx_control && upr;
    assign video_ready=tx_active && !tx_control && upr;
    assign rhr=!rx_active;
    assign rpr=rx_active && (!rx_match || control_rx_ready);
    assign control_rx_data=rpd;
    assign control_rx_valid=rx_active && rx_match && rpv;
    assign control_rx_last=rpl;
    assign control_rx_bad=rpu;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) begin rx_active<=0;rx_match<=0;tx_active<=0;tx_control<=0;tx_header<=0;tx_length<=0;end
        else begin
            if(rhv && rhr) begin
                rx_active<=1;
                rx_match<=rsrc==PEER_IP && rdst==LOCAL_IP && rsport==HOST_CONTROL_PORT &&
                    rdport==CONTROL_PORT && rfragment==0 && !rflags[0];
            end
            if(rpv && rpr && rpl) rx_active<=0;
            if(!tx_active && !tx_header && (control_tx_valid || video_valid)) begin
                tx_header<=1;tx_control<=control_tx_valid;
                tx_length<=control_tx_valid ? control_tx_length : video_length;
            end
            if(uhv && uhr) begin tx_active<=1;tx_header<=0;end
            if(upv && upr && upl) tx_active<=0;
        end
    udp_complete #(.ARP_CACHE_ADDR_WIDTH(4),.UDP_CHECKSUM_GEN_ENABLE(1),
        .UDP_CHECKSUM_PAYLOAD_FIFO_DEPTH(2048)) stack(
        .clk(clk),.rst(rst),
        .s_eth_hdr_valid(ehv),.s_eth_hdr_ready(ehr),.s_eth_dest_mac(edst),.s_eth_src_mac(esrc),.s_eth_type(etype),
        .s_eth_payload_axis_tdata(epd),.s_eth_payload_axis_tvalid(epv),.s_eth_payload_axis_tready(epr),
        .s_eth_payload_axis_tlast(epl),.s_eth_payload_axis_tuser(epu),
        .m_eth_hdr_valid(thv),.m_eth_hdr_ready(thr),.m_eth_dest_mac(tdst),.m_eth_src_mac(tsrc),.m_eth_type(ttype),
        .m_eth_payload_axis_tdata(tpd),.m_eth_payload_axis_tvalid(tpv),.m_eth_payload_axis_tready(tpr),
        .m_eth_payload_axis_tlast(tpl),.m_eth_payload_axis_tuser(tpu),
        .s_ip_hdr_valid(1'b0),.s_ip_dscp(6'd0),.s_ip_ecn(2'd0),.s_ip_length(16'd0),
        .s_ip_ttl(8'd0),.s_ip_protocol(8'd0),.s_ip_source_ip(32'd0),.s_ip_dest_ip(32'd0),
        .s_ip_payload_axis_tdata(8'd0),.s_ip_payload_axis_tvalid(1'b0),.s_ip_payload_axis_tlast(1'b0),
        .s_ip_payload_axis_tuser(1'b0),.m_ip_hdr_ready(1'b1),.m_ip_payload_axis_tready(1'b1),
        .s_udp_hdr_valid(uhv),.s_udp_hdr_ready(uhr),.s_udp_ip_dscp(6'd0),.s_udp_ip_ecn(2'd0),
        .s_udp_ip_ttl(8'd64),.s_udp_ip_source_ip(LOCAL_IP),.s_udp_ip_dest_ip(PEER_IP),
        .s_udp_source_port(choose_control ? CONTROL_PORT : VIDEO_PORT),
        .s_udp_dest_port(choose_control ? HOST_CONTROL_PORT : VIDEO_PORT),
        .s_udp_length(ulen),.s_udp_checksum(16'd0),
        .s_udp_payload_axis_tdata(upd),.s_udp_payload_axis_tvalid(upv),.s_udp_payload_axis_tready(upr),
        .s_udp_payload_axis_tlast(upl),.s_udp_payload_axis_tuser(1'b0),
        .m_udp_hdr_valid(rhv),.m_udp_hdr_ready(rhr),.m_udp_ip_source_ip(rsrc),.m_udp_ip_dest_ip(rdst),
        .m_udp_ip_flags(rflags),.m_udp_ip_fragment_offset(rfragment),
        .m_udp_source_port(rsport),.m_udp_dest_port(rdport),
        .m_udp_payload_axis_tdata(rpd),.m_udp_payload_axis_tvalid(rpv),.m_udp_payload_axis_tready(rpr),
        .m_udp_payload_axis_tlast(rpl),.m_udp_payload_axis_tuser(rpu),
        .local_mac(LOCAL_MAC),.local_ip(LOCAL_IP),.gateway_ip(LOCAL_IP),.subnet_mask(32'hffffff00),.clear_arp_cache(1'b0));
endmodule
`default_nettype wire
