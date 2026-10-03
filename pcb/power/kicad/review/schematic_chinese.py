"""Chinese descriptions only; electrical net names and power values stay ASCII."""
from kicad_tools import parse, Node, children, child
import json,re

LEGACY_NETS={
 'GND':'地','VBAT_SYS':'电池保护后母线','VLOGIC_IN':'降压电源输入','VREF_2V495':'基准电压_2.495V',
 'BUCK_ENABLE':'降压使能','MOTOR_POWER_OK':'电机供电正常','VM_SWITCHED':'电机总开关输出',
 '+3V3_RAW':'板载3.3V_稳压输出','+3V3_ONBOARD':'板载3.3V_保护输出','+3V3':'本板3.3V',
 '+3V3_SENS':'传感器3.3V','3V3_FPGA_IN':'逻辑板3.3V_输入','3V3_ONBOARD_OK':'板载3.3V_电压正常',
 '+5V_FPGA':'逻辑板5V_稳压输出','+5V_FPGA_PROT':'逻辑板5V_保护输出','+5V_FPGA_OK':'逻辑板5V_电压正常',
 '+5V_AI':'计算板5V_稳压输出','+5V_AI_PROT':'计算板5V_保护输出','+5V_AI_OK':'计算板5V_电压正常',
 'MOTOR_ARM':'电机解锁脉冲','MOTOR_PERMIT':'电机运行许可','MOTOR_ARMED':'电机已解锁',
 'ESTOP_OK':'急停回路闭合','EXT_KILL_N':'外部故障_低有效','POR_OK':'上电复位完成',
 'BAT_WARN_N':'电池欠压告警_低有效','BAT_ADC':'电池电压采样','CURRENT_REF_1V217':'过流基准_1.217V',
 'USB1_VBUS':'供电口1_总线电源','USB2_VBUS':'供电口2_总线电源',
 'USB1_FAULT_PULSE_N':'供电口1_故障脉冲_低有效','USB2_FAULT_PULSE_N':'供电口2_故障脉冲_低有效',
}
for side,name in [('L','左'),('R','右')]:
 LEGACY_NETS.update({f'VM_{side}':name+'电机_动力电源',f'VM_{side}_IMON':name+'电机_母线电流采样',
  f'VREF_{side}':name+'电机_限流参考',f'{side}_PWM_FWD_RAW':name+'电机_原始正转脉宽',
  f'{side}_PWM_REV_RAW':name+'电机_原始反转脉宽',
  **{f'ENC_{side}_{ch}':name+'编码器_'+ch for ch in ['A','B']},
  **{f'ENC_{side}_{ch}_FPGA':name+'编码器_'+ch+'_逻辑板输入' for ch in ['A','B']}})

# Kept for functional audits. Network identifiers are excluded from translation.
NETS={name:name for name in LEGACY_NETS}

TEXT={
 'EdgeMind Robot power / 2x5V + independent 3V3':'机器人电源板 / 两路5V与独立3.3V',
 '3S input and voltage protection':'三串电池输入与电压保护',
 'Two MP2236 / 6P USB-C sources':'两路5V降压与六针供电口',
 'Independent 3V3 and source selector':'独立3.3V与电源选择',
 'E-stop and explicit arm latch':'急停与显式解锁锁存',
 'Left AT8236 and current monitor':'左电机驱动与电流监测',
 'Right AT8236 and current monitor':'右电机驱动与电流监测',
 'Regeneration dump':'电机回生能量泄放',
 'Low-cost output OV disconnect':'低成本输出过压关断',
 'FPGA control and monitor interfaces':'逻辑板控制与电源监测接口',
 '3S protected battery -> fuse / reverse protection -> VBAT_SYS\nLogic switch -> VLOGIC_IN -> two 5V bucks + independent 3V3 buck\nMotor arm switch -> branch fuses / shunts -> VM_L / VM_R\nJP1: 1-2 ONBOARD (default); 2-3 FPGA IN (optional, confirm current headroom)':
 '三串受保护电池 → 保险丝与防反接 → 电池保护后母线\n逻辑电源开关 → 两路5V降压与独立3.3V降压\n动力解锁开关 → 分支保险丝与采样电阻 → 左右电机电源\nJP1：1-2为板载供电（默认）；2-3为逻辑板输入（需确认电流余量）',
 'Schematic R2 / PCB intentionally unchanged. Bench validation required before fabrication.\nExternal 3S cell protection required. Stepper drivers and FPGA RTL are separate system work.':
 '第二版原理图；本次未修改电路板。投板前须完成台架验证。\n系统需要外部三串电芯保护；步进驱动和逻辑板程序另行设计。',
 'INPUT / 3S pack + external BMS / fuse + reverse polarity':'输入：三串电池与外部电芯保护 / 保险丝与防反接',
 'Q1: D=BAT input / S=VBAT_SYS\nTVS handles transients, not a 17V clamp.\nFuse rating must match copper and harness.':
 'Q1：漏极接电池输入，源极接保护后母线\n瞬态抑制二极管不能把电压固定在17V以下。\n保险丝额定值须匹配铜箔与线束承载能力。',
 'RAW-BUS reference / logic input switch':'电池母线基准与降压输入开关',
 'UV / OV WINDOW: logic 9.0-14.1V, motor 9.65-14.1V':'欠压与过压窗口：逻辑约9.0-14.1V；动力约9.65-14.1V',
 'OC outputs wired-AND. Motor faults clear the arm latch; voltage recovery does not re-arm.\nTotal voltage monitoring does not replace cell protection. Validate threshold/overshoot on bench.':
 '开集电极故障输出共同拉低使能。电机故障清除解锁锁存；电压恢复后不自动解锁。\n总电压监测不能替代单体电芯保护。阈值、响应和过冲须实测。',
 'DEFAULT: independent 3.3V buck / initial load budget 0.5A':'默认独立3.3V降压 / 初始负载预算0.5A',
 '2A IC capacity does not define connector/load budget.\nFeedback senses the buck output before protection.\n4.7uH matches the allowed 2.2-10uH range.':
 '芯片标称2A能力不能代替接口与散热验收。\n反馈取自保护开关前的稳压输出。\n4.7µH位于手册允许的2.2-10µH范围内。',
 'JP1: one shunt only / source selection':'JP1电源选择：只安装一个跳帽',
 'Default shunt 1-2: onboard 3V3.\n2-3 only after verifying FPGA headroom.\nNever fit two shunts. No hard paralleling.\nOnboard buck remains populated by default.':
 '默认短接1-2：板载3.3V供电。\n确认逻辑板电流余量后，才能改为2-3。\n只能装一个跳帽，不能并联两个电源。\n默认安装板载降压电路。',
 'FILTERED SENSOR POWER / finished 3.3V-compatible modules only':'传感器电源滤波 / 仅接已确认支持3.3V的成品模块',
 'Default +3V3 powers encoders, current monitors and safety logic. Sensor signals connect to FPGA.\nBare sensor chips and finished modules may need different supply levels; confirm actual modules.':
 '本板3.3V供给编码器、电流监测和安全逻辑；传感器信号接逻辑板。\n裸芯片与成品模块的供电要求可能不同，须核对实际模块。',
 'MOTOR HARDWARE LATCH: power-on OFF / NC E-stop / explicit ARM rising edge':'动力硬件锁存：上电关闭 / 常闭急停 / 解锁需要上升沿',
 'Open E-stop / low PERMIT / external KILL / undervoltage / overcurrent clears immediately.\nRestore conditions then pulse ARM: no automatic restart. FPGA must drop PERMIT on watchdog/stall.\nHC08/HC74 are CMOS parts running at 3.3V. Do not substitute 74LS parts.':
 '急停断开、运行许可撤销、外部故障、欠压或过流均立即清除解锁。\n条件恢复后还须发出解锁脉冲；逻辑板须在看门狗超时或堵转时撤销运行许可。\n使用支持3.3V的74HC08与74HC74，不可换成74LS系列。',
 'MOTOR POWER SWITCH / not a small slider in the motor path':'动力总开关 / 急停触点只承载控制电流',
 'REGEN DUMP / external chassis resistors':'回生能量泄放 / 外接底盘散热电阻',
 'Dump turns ON ~15.39V; verify OFF threshold and worst-case overshoot.\nUse two 3.3ohm >=100W chassis resistors if the supply/BMS cannot absorb regen.\nCircuit operates from raw bus even when local 3V3 is absent. MOSFET cooling required.':
 '约15.39V开始泄放；关闭阈值和最坏过冲须实测。\n若电源或电池保护板不能吸收回生，外接两只3.3Ω、至少100W的底盘散热电阻。\n电路由电池母线供电，本板3.3V消失时仍可工作；功率管需要散热。',
 '3V3 onboard OV cutoff ~3.451V':'板载3.3V过压关断 / 标称约3.451V',
 'MOTOR overcurrent / filtered bus current / common latch clear':'动力过流检测 / 滤波后母线电流 / 共用锁存清除',
 'Discrete OV disconnects are cost-oriented. Verify fault-step overshoot and thermal behavior.\nNo claim of true reverse-current blocking: use supply selection/isolation on attached boards.\nMotor bus current threshold ~3.04A plus tolerance; fuse is harness protection, not winding limit.':
 '分立过压关断方案用于控制成本；故障阶跃过冲和温升须实测。\n本方案不保证所有状态下阻断反灌，接入板卡仍须核对电源选择与隔离。\n母线过流阈值标称约3.04A；保险丝保护线束，不能代替绕组限流。',
 'CONTROL / power direction / explicit source selection':'控制接口 / 电源方向 / 互斥电源选择',
 'BAT_ADC: 12.6V -> 2.71V; requires external ADC.\nJ1.6 and J2.3 = same FPGA 3V3 INPUT,\nnot local 3V3 OUTPUT. JP1 isolates by default.\nOnly connect one FPGA supply domain.\nPERMIT low during reset / watchdog timeout.\nARM rising edge after safety checks.\nKILL_N accepts external open-drain fault.\nLichee Pi GPIO needs appropriate level translation.':
 '电池采样：12.6V对应约2.71V，需要外部模数转换器。\nJ1第6脚与J2第3脚均为逻辑板3.3V输入，\n默认与本板输出隔离，只接同一个电源域。\n复位或看门狗超时时，运行许可必须为低。\n安全检查后，以解锁脉冲的上升沿解锁。\n外部故障脚接受开漏低电平。\n荔枝派普通输入输出需要合适的电平转换。',
 'Do not fabricate the existing PCB using this schematic. Synchronization/layout is separate work.\nAT8236 Rsense / encoder variant / ACG720 Type-C supply path remain hardware verification items.':
 'PCB封装与网络已同步，布局布线待完成。\n仍须核对模块采样电阻、编码器版本与逻辑板供电接口。',
 'CC attach detection + integrated VBUS switch\nISET 150k: 3.6A typ / Rp advertises 3A\nNo external Rp, USB data or PD voltage negotiation':
 '连接检测与总线电源开关由控制器完成\n限流电阻150kΩ：典型限流3.6A，宣告供电能力3A\n无需外部上拉电阻；仅固定5V供电',
 'OPTIONAL FPGA 3V3 IN':'可选逻辑板3.3V输入','1-2 ONBOARD / 2-3 FPGA':'1-2板载 / 2-3逻辑板',
 'IMU PWR':'惯性传感器电源','TOF1 PWR':'测距传感器1电源','TOF2 PWR':'测距传感器2电源','TOF3 PWR':'测距传感器3电源',
 '3V3 AUX OUT':'3.3V辅助输出','ESTOP NC LOOP':'急停常闭回路','AT8236 dual module':'AT8236双路模块',
 'MG513 / verify harness':'MG513电机 / 核对线序','LEFT CTRL':'左轮控制','RIGHT CTRL':'右轮控制',
 'POWER MONITOR / external ADC':'电源监测 / 外部模数转换','XT60PW-M / 3S':'XT60PW-M / 三串电池',
 'TYPE-C-31-M-17 / 6P':'TYPE-C-31-M-17 / 六针供电','220R@100MHz 1A':'220Ω@100MHz / 1A',
}

def translated(v):
 if v in TEXT:return TEXT[v]
 if v in NETS:return NETS[v]
 if v.endswith(' / 5.10V / USB-C 3A target'):return ('逻辑板降压输出' if v.split(' /')[0]=='+5V_FPGA' else '计算板降压输出')+' / 5.10V / 供电目标3A'
 if ' / 6P power-only / fixed 5V' in v:return v.split(' /')[0]+' / 六针供电口 / 固定5V'
 if v.startswith('Gain 20 / shunt'):return '增益20，采样电阻20mΩ：约0.4V/A\n输出滤波约1ms；母线电流不同于绕组电流\n标称母线过流阈值约3.04A，须实测设定'
 if ' MOTOR / branch fuse / bus current monitor / local bulk' in v:return ('左' if v[0]=='L' else '右')+'电机：分支保险、电流监测与本地储能'
 if ' AT8236 / A channel / VREF adjustable / female sockets' in v:return ('左' if v[0]=='L' else '右')+'电机驱动：使用A通道 / 可调限流参考 / 双排排母'
 if ' DUMP / external 3R3' in v:return ('左' if v[0]=='L' else '右')+'回生泄放 / 外接3.3Ω'
 if v.startswith('ROW='):
  row=re.search(r'ROW=([\d.]+)',v).group(1)
  return f'排间距{row}毫米，沿用原电路板；对排引脚编号已纠正。\n限流电流=参考电压/(10×采样电阻)；安装电机前先测阻值并校准。\n10正转、01反转、00滑行、11制动；B通道未用。编码器线序须与实物一致。'
 if v.startswith('5V OV cutoff ~5.364V / '):return ('逻辑板供电过压关断' if v.split(' / ')[-1]=='+5V_FPGA_PROT' else '计算板供电过压关断')+' / 标称约5.364V'
 return v

def localize(file):
 text=file.read_text(encoding='utf-8');root=parse(text);edits=[]
 def put(atom,value):
  if str(atom)!=value:edits.append((atom.start,atom.end,json.dumps(value,ensure_ascii=False)))
 for n in root[1:]:
  if not isinstance(n,Node):continue
  if n[0] in ('label','global_label','hierarchical_label'):
   assert str(n[1]).isascii(),'Electrical labels must not be translated'
  elif n[0]=='text':put(n[1],translated(str(n[1])))
  elif n[0]=='symbol':
   for p in children(n,'property'):
    if p[1]=='Value':
     lib_id=child(n,'lib_id')
     if lib_id and str(lib_id[1]).startswith('power:'):
      assert str(p[2]).isascii(),'Power names must not be translated'
     else:put(p[2],translated(str(p[2])))
  elif n[0]=='sheet':
   for pin in children(n,'pin'):assert str(pin[1]).isascii(),'Hierarchy ports must not be translated'
   for p in children(n,'property'):
    if p[1]=='Sheetname':put(p[2],translated(str(p[2])))
  elif n[0]=='title_block':
   for x in n[1:]:
    if isinstance(x,Node):
     if x[0]=='title':put(x[1],translated(str(x[1])))
     elif x[0]=='rev':put(x[1],'第二版原理图')
     elif x[0]=='company':put(x[1],'EdgeMind机器人')
     elif x[0]=='comment':put(x[2],'PCB封装与网络已同步，布局布线待完成')
 for a,b,v in sorted(edits,reverse=True):text=text[:a]+v+text[b:]
 assert '(face ' not in text,'Unexpected non-default font'
 file.write_text(text,encoding='utf-8')

