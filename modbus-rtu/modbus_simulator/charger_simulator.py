import time
import threading
import logging
from pymodbus.server import StartSerialServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.transaction import ModbusRtuFramer

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 兼容处理：若原项目有config.py，保留；无则直接定义配置（二选一即可）
try:
    from config import MODBUS_CONFIG, INITIAL_STATUS
except ImportError:
    # 方案2：跨平台默认配置
    import platform
    if platform.system() == 'Windows':
        DEFAULT_PORT = 'COM2'
    else:
        DEFAULT_PORT = '/dev/ttyUSB1'
    
    MODBUS_CONFIG = {
        'port': DEFAULT_PORT,
        'baudrate': 9600,
        'parity': 'N',
        'stopbits': 1,
        'bytesize': 8,
        'timeout': 1
    }
    INITIAL_STATUS = {
        'voltage': 220.0,
        'current': 0.0,
        'power': 0.0,
        'soc': 50.0,
        'status': 0,
        'temperature': 30.0  # 改为浮点数，统一精度
    }

class ChargerSimulator:
    def __init__(self):
        self.charger_status = INITIAL_STATUS.copy()
        self._init_registers()
        self.running = True
        self.status_thread = threading.Thread(target=self._update_status)
        self.status_thread.daemon = True
        self.status_thread.start()
        logger.info("Charger simulator initialized")

    def _init_registers(self):
        """初始化寄存器，包含整桩/枪扩展地址"""
        regs_num = 0x3000
        self.holding_registers = ModbusSequentialDataBlock(0, [0] * regs_num)
        self.input_registers = ModbusSequentialDataBlock(0, [0] * regs_num)
        
        # 初始化基础寄存器
        self._update_base_registers()
        # 初始化扩展寄存器（整桩/枪信息）
        self._update_extend_registers()

        self.slave_context = ModbusSlaveContext(
            hr=self.holding_registers,
            ir=self.input_registers,
            di=None, co=None
        )
        self.context = ModbusServerContext(slaves=self.slave_context, single=True)

        self.identity = ModbusDeviceIdentification()
        self.identity.VendorName = 'Charger Simulator'
        self.identity.ProductCode = 'MODBUS-RTU'
        self.identity.VendorUrl = 'http://example.com'
        self.identity.ProductName = 'EV Charger'
        self.identity.ModelName = 'Simulator V1.0'
        self.identity.MajorMinorRevision = '1.0'

    def _update_base_registers(self):
        """更新基础寄存器（0-5地址）"""
        # 保留1位小数，转int存储
        self.holding_registers.setValues(0, [int(self.charger_status['voltage'] * 10)])
        self.holding_registers.setValues(1, [int(self.charger_status['current'] * 10)])
        self.holding_registers.setValues(2, [int(self.charger_status['power'] * 10)])
        self.holding_registers.setValues(3, [int(self.charger_status['soc'])])  # SOC为整数
        self.holding_registers.setValues(4, [int(self.charger_status['status'])])
        self.holding_registers.setValues(5, [int(self.charger_status['temperature'] * 10)])  # 温度保留1位小数

        # 输入寄存器镜像基础寄存器
        self.input_registers.setValues(0, [int(self.charger_status['voltage'] * 10)])
        self.input_registers.setValues(1, [int(self.charger_status['current'] * 10)])
        self.input_registers.setValues(2, [int(self.charger_status['power'] * 10)])
        self.input_registers.setValues(3, [int(self.charger_status['soc'])])
        self.input_registers.setValues(4, [int(self.charger_status['status'])])
        self.input_registers.setValues(5, [int(self.charger_status['temperature'] * 10)])

    def _update_extend_registers(self):
        """更新扩展寄存器（整桩/枪信息）"""
        # 整桩信息（输入寄存器0x1000=4096）
        self.input_registers.setValues(4096, [1])        # 整桩枪个数
        self.input_registers.setValues(4097, [2200])     # 整桩最大输出功率（220.0kW，*10存储）
        # 1号枪状态（输入寄存器0x2000=8192）
        self.input_registers.setValues(8192, [int(self.charger_status['status'])])  # 枪工作状态
        self.input_registers.setValues(8193, [0])        # 枪工作模式：0-充电

    def _update_status(self):
        """修复：循环内更新所有寄存器，优化状态逻辑"""
        while self.running:
            try:
                # 充电状态逻辑
                if self.charger_status['status'] == 1:
                    self.charger_status['current'] = 10.0
                    self.charger_status['power'] = self.charger_status['voltage'] * self.charger_status['current']
                    
                    # SOC上限100，满电后恢复空闲
                    if self.charger_status['soc'] < 100:
                        self.charger_status['soc'] += 0.5
                    else:
                        self.charger_status['status'] = 0
                        self.charger_status['current'] = 0.0
                        self.charger_status['power'] = 0.0
                else:
                    self.charger_status['current'] = 0.0
                    self.charger_status['power'] = 0.0

                # 温度逻辑（充电升温，空闲降温）
                if self.charger_status['status'] == 1:
                    if self.charger_status['temperature'] < 45.0:
                        self.charger_status['temperature'] += 0.2
                else:
                    if self.charger_status['temperature'] > 30.0:
                        self.charger_status['temperature'] -= 0.1

                # 更新所有寄存器（基础+扩展）
                self._update_base_registers()
                self._update_extend_registers()
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in status update loop: {e}")
                time.sleep(1)  # 出错后延迟，避免死循环刷屏

    def start_server(self):
        """启动Modbus RTU服务器，增强异常处理"""
        try:
            logger.info(f"Starting Modbus RTU server on {MODBUS_CONFIG['port']}")
            logger.info(f"Config: baud={MODBUS_CONFIG['baudrate']}, parity={MODBUS_CONFIG['parity']}, stopbits={MODBUS_CONFIG['stopbits']}")
            
            StartSerialServer(
                context=self.context,
                identity=self.identity,
                framer=ModbusRtuFramer,
                port=MODBUS_CONFIG['port'],
                baudrate=MODBUS_CONFIG['baudrate'],
                parity=MODBUS_CONFIG['parity'],
                stopbits=MODBUS_CONFIG['stopbits'],
                bytesize=MODBUS_CONFIG['bytesize'],
                timeout=MODBUS_CONFIG['timeout'],
                strict=True  # 严格模式，提升协议兼容性
            )
        except Exception as e:
            logger.error(f"Failed to start server: {e}", exc_info=True)
            raise

    def stop(self):
        """优雅停止模拟器"""
        logger.info("Stopping charger simulator...")
        self.running = False
        if self.status_thread.is_alive():
            self.status_thread.join(timeout=3)
        logger.info("Charger simulator stopped")

if __name__ == '__main__':
    simulator = ChargerSimulator()
    try:
        simulator.start_server()
    except KeyboardInterrupt:
        simulator.stop()
        logger.info("Server stopped by user (Ctrl+C)")
    except Exception as e:
        simulator.stop()
        logger.error(f"Server crashed: {e}", exc_info=True)