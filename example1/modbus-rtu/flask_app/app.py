import time
import threading
import logging
import struct
import platform
from pymodbus.client import ModbusSerialClient
from pymodbus.transaction import ModbusRtuFramer
from flask import Flask, jsonify, request, render_template

# ===================== 基础配置 =====================
# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 串口配置（主设备）
MODBUS_CONFIG = {
    'port': 'COM1',  # 设置为COM1
    'baudrate': 9600,
    'parity': 'N',
    'stopbits': 1,
    'bytesize': 8,
    'timeout': 1
}

# 双枪初始状态
INITIAL_STATUS = {
    'gun1': {
        'voltage': 220.0,    # 0.1V分辨率
        'current': 0.0,      # 0.01A分辨率
        'power': 0.0,        # 0.001kW分辨率
        'soc': 50,           # 1%分辨率
        'status': 0,         # 0-空闲,1-已连接,2-启动充电,3-充电中,4-完成,5-故障
        'mode': 0,           # 0-充电模式
        'temperature': 30.0, # 设备温度
        'alarm': 0,          # 32位告警码
        'fault': 0,          # 32位故障码
        'meter_reading': 0.0, # 电表读数（0.001kWh）
        'charge_energy': 0.0, # 充电电量（0.001kWh）
        'charge_time': 0,     # 充电时长（s）
        'charge_amount': 0.0  # 充电金额（0.01元）
    },
    'gun2': {
        'voltage': 220.0,
        'current': 0.0,
        'power': 0.0,
        'soc': 60,
        'status': 0,
        'mode': 0,
        'temperature': 29.0,
        'alarm': 0,
        'fault': 0,
        'meter_reading': 0.0,
        'charge_energy': 0.0,
        'charge_time': 0,
        'charge_amount': 0.0
    }
}

# ===================== 全局变量 =====================
# 充电桩状态（全局可读写）
charger_status = INITIAL_STATUS.copy()
# 运行标记
running = True
# Modbus客户端（全局）
modbus_client = None

# Flask App
app = Flask(__name__, template_folder='templates')

# ===================== 核心工具函数 =====================
def int_to_4byte_regs(value):
    """将4字节数据转换为2个16位寄存器（先低16位，后高16位）"""
    bytes_data = struct.pack('<i', int(value))
    reg1 = (bytes_data[1] << 8) | bytes_data[0]
    reg2 = (bytes_data[3] << 8) | bytes_data[2]
    return [reg1, reg2]

def regs_to_int(regs):
    """将2个16位寄存器转换为4字节整数"""
    if len(regs) < 2:
        return 0
    bytes_data = bytearray()
    bytes_data.append(regs[0] & 0xFF)
    bytes_data.append((regs[0] >> 8) & 0xFF)
    bytes_data.append(regs[1] & 0xFF)
    bytes_data.append((regs[1] >> 8) & 0xFF)
    return struct.unpack('<i', bytes_data)[0]

def init_modbus_client():
    """初始化Modbus RTU客户端"""
    global modbus_client
    try:
        logger.info(f"初始化Modbus RTU客户端，端口：{MODBUS_CONFIG['port']}")
        modbus_client = ModbusSerialClient(
            port=MODBUS_CONFIG['port'],
            framer=ModbusRtuFramer,
            baudrate=MODBUS_CONFIG['baudrate'],
            parity=MODBUS_CONFIG['parity'],
            stopbits=MODBUS_CONFIG['stopbits'],
            bytesize=MODBUS_CONFIG['bytesize'],
            timeout=MODBUS_CONFIG['timeout']
        )
        
        # 连接到从设备
        if modbus_client.connect():
            logger.info("Modbus RTU客户端连接成功")
            return True
        else:
            logger.error("Modbus RTU客户端连接失败")
            return False
    except Exception as e:
        logger.error(f"初始化Modbus客户端异常: {e}")
        return False

def read_modbus_registers():
    """从Modbus从设备读取寄存器数据"""
    global modbus_client, charger_status
    
    if not modbus_client or not modbus_client.is_socket_open():
        logger.warning("Modbus客户端未连接")
        return False
    
    try:
        # 读取1号枪状态（输入寄存器，功能码0x04）
        result = modbus_client.read_input_registers(8192, 38, slave=1)
        if result.isError():
            logger.error(f"读取1号枪状态失败: {result}")
        else:
            gun1 = charger_status['gun1']
            gun1['status'] = result.registers[0]
            gun1['mode'] = result.registers[1]
            gun1['alarm'] = regs_to_int(result.registers[2:4])
            gun1['fault'] = regs_to_int(result.registers[4:6])
            gun1['meter_reading'] = regs_to_int(result.registers[17:19]) / 1000
            gun1['charge_amount'] = regs_to_int(result.registers[21:23]) / 100
            gun1['charge_energy'] = regs_to_int(result.registers[25:27]) / 1000
            gun1['charge_time'] = regs_to_int(result.registers[29:31])
            gun1['power'] = regs_to_int(result.registers[33:35]) / 1000
            gun1['voltage'] = result.registers[35] / 10
            gun1['current'] = result.registers[36] / 100
            gun1['soc'] = result.registers[37]
        
        # 读取2号枪状态（输入寄存器，功能码0x04）
        result = modbus_client.read_input_registers(8448, 38, slave=1)
        if result.isError():
            logger.error(f"读取2号枪状态失败: {result}")
        else:
            gun2 = charger_status['gun2']
            gun2['status'] = result.registers[0]
            gun2['mode'] = result.registers[1]
            gun2['alarm'] = regs_to_int(result.registers[2:4])
            gun2['fault'] = regs_to_int(result.registers[4:6])
            gun2['meter_reading'] = regs_to_int(result.registers[17:19]) / 1000
            gun2['charge_amount'] = regs_to_int(result.registers[21:23]) / 100
            gun2['charge_energy'] = regs_to_int(result.registers[25:27]) / 1000
            gun2['charge_time'] = regs_to_int(result.registers[29:31])
            gun2['power'] = regs_to_int(result.registers[33:35]) / 1000
            gun2['voltage'] = result.registers[35] / 10
            gun2['current'] = result.registers[36] / 100
            gun2['soc'] = result.registers[37]
        
        return True
    except Exception as e:
        logger.error(f"读取Modbus寄存器异常: {e}")
        return False

def write_modbus_register(address, value, slave=1):
    """向Modbus从设备写入单个寄存器"""
    global modbus_client
    
    if not modbus_client or not modbus_client.is_socket_open():
        logger.warning("Modbus客户端未连接")
        return False
    
    try:
        result = modbus_client.write_register(address, value, slave=slave)
        if result.isError():
            logger.error(f"写入寄存器失败: {result}")
            return False
        else:
            logger.info(f"成功写入寄存器 {address} = {value}")
            return True
    except Exception as e:
        logger.error(f"写入Modbus寄存器异常: {e}")
        return False

# ===================== 状态更新逻辑 =====================
def update_charger_status():
    """从Modbus从设备读取状态并更新"""
    global charger_status, running

    while running:
        try:
            # 从Modbus从设备读取状态
            read_modbus_registers()
            
            # 处理充电完成和故障状态的自动复位
            for gun_id in ['gun1', 'gun2']:
                gun = charger_status[gun_id]
                
                # 空闲/已连接状态逻辑
                if gun['status'] not in [3]:  # 非充电中状态
                    gun['current'] = 0.0
                    gun['power'] = 0.0

            time.sleep(1)

        except Exception as e:
            logger.error(f"状态更新异常: {e}")
            time.sleep(1)

def set_gun_status(gun_id, status):
    """通过Modbus设置充电桩枪状态"""
    global charger_status
    if gun_id not in ['gun1', 'gun2']:
        return False, "无效枪号"
    if status not in [0,1,2,3,4,5]:
        return False, "无效状态码"
    
    # 确定寄存器地址
    if gun_id == 'gun1':
        register_address = 8192  # 1号枪状态寄存器
    else:
        register_address = 8448  # 2号枪状态寄存器
    
    # 通过Modbus写入状态
    success = write_modbus_register(register_address, status)
    if success:
        # 同时更新本地状态
        charger_status[gun_id]['status'] = status
        return True, "设置成功"
    else:
        return False, "设置失败，请检查Modbus连接"


# ===================== Flask接口 =====================
@app.route('/')
def index():
    """前端页面"""
    return render_template('index.html')

@app.route('/api/charger/status', methods=['GET'])
def get_status():
    """获取实时状态"""
    return jsonify({
        'code': 200,
        'data': charger_status,
        'msg': 'success'
    })

@app.route('/api/charger/set_status', methods=['POST'])
def set_status():
    """设置枪状态"""
    data = request.json
    gun_id = data.get('gun_id')
    status = data.get('status')
    
    if not gun_id or status is None:
        return jsonify({'code': 400, 'msg': '参数缺失'})
    
    success, msg = set_gun_status(gun_id, status)
    return jsonify({
        'code': 200 if success else 400,
        'msg': msg
    })

# ===================== 服务启动 =====================
def start_flask_server():
    """启动Flask服务"""
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

if __name__ == '__main__':
    # 1. 初始化Modbus客户端
    success = init_modbus_client()
    if not success:
        logger.warning("Modbus客户端初始化失败，将使用模拟数据")
    else:
        logger.info("Modbus RTU客户端初始化完成")

    # 2. 启动状态更新线程
    status_thread = threading.Thread(target=update_charger_status)
    status_thread.daemon = True
    status_thread.start()
    logger.info("状态更新线程启动")

    # 3. 启动Flask服务（主线程）
    try:
        start_flask_server()
    except KeyboardInterrupt:
        running = False
        # 关闭Modbus客户端连接
        if modbus_client:
            modbus_client.close()
        logger.info("用户终止服务（Ctrl+C）")
    except Exception as e:
        running = False
        # 关闭Modbus客户端连接
        if modbus_client:
            modbus_client.close()
        logger.error(f"服务崩溃: {e}", exc_info=True)