  //TFT5.0 800x480(pixel clock 33MHz)，行、场扫描时序参数表
  //Horizontal timing (line)
  parameter H_Visible_Area = 800;
  parameter H_Right_Border = 0;
  parameter H_Front_Porch  = 40;
  parameter H_Sync_Pulse   = 128;
  parameter H_Back_Porch   = 88;
  parameter H_Left_Border  = 0;
  parameter H_Whole_Line   = 1056;

  //Vertical timing (frame)
  parameter V_Visible_Area = 480;
  parameter V_Bottom_Border= 0;
  parameter V_Front_Porch  = 10;
  parameter V_Sync_Pulse   = 2;
  parameter V_Back_Porch   = 33;
  parameter V_Top_Border   = 0;
  parameter V_Whole_Frame  = 525;

/*
  //TFT4.3 480x272(pixel clock 9MHz)，行、场扫描时序参数表
  //Horizontal timing (line)
  parameter H_Visible_Area = 480;
  parameter H_Right_Border = 0;
  parameter H_Front_Porch  = 2;
  parameter H_Sync_Pulse   = 41;
  parameter H_Back_Porch   = 2;
  parameter H_Left_Border  = 0;
  parameter H_Whole_Line   = 525;

  //Vertical timing (frame)
  parameter V_Visible_Area = 272;
  parameter V_Bottom_Border= 0;
  parameter V_Front_Porch  = 2;
  parameter V_Sync_Pulse   = 10;
  parameter V_Back_Porch   = 2;
  parameter V_Top_Border   = 0;
  parameter V_Whole_Frame  = 286;
*/


