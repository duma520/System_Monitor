import sys
import os
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import OrderedDict

# PyQt5 imports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QProgressBar, QPushButton, QCheckBox, QComboBox,
                             QSpinBox, QDoubleSpinBox, QMessageBox, QSystemTrayIcon,
                             QAction, QMenu, QStyle, QTabWidget, QScrollArea)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, pyqtSlot, QTimer, 
                          QSettings, QSize, QPoint, QRect)
from PyQt5.QtGui import (QIcon, QFont, QColor, QPalette, QLinearGradient, 
                         QPainter, QBrush, QPen, QCloseEvent)

# OpenHardwareMonitor通过WMI访问
try:
    import pythoncom
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False
    print("警告: wmi模块未安装，将使用模拟数据")
    print("请安装: pip install wmi")


# ==================== 硬件监控线程类 ====================
class HardwareMonitorThread(QThread):
    """硬件监控线程，负责定期获取硬件信息"""
    
    # 信号：用于向GUI线程发送硬件数据
    hardware_data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, update_interval=2.0):
        super().__init__()
        self.update_interval = update_interval  # 更新间隔（秒）
        self.running = False
        self.wmi_conn = None
        self.hardware_data = {
            'cpu': {'temperature': 0.0, 'fan_speeds': [], 'load': 0.0},
            'gpu': {'temperature': 0.0, 'fan_speeds': [], 'load': 0.0},
            'fans': [],  # 其他风扇
            'last_update': None
        }
        
    def init_wmi(self):
        """初始化WMI连接"""
        try:
            if not WMI_AVAILABLE:
                return False
                
            pythoncom.CoInitialize()
            self.wmi_conn = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            return True
        except Exception as e:
            self.error_occurred.emit(f"WMI初始化失败: {str(e)}")
            return False
    
    def get_hardware_data(self):
        """通过WMI获取硬件数据"""
        try:
            if not self.wmi_conn:
                if not self.init_wmi():
                    return self.get_mock_data()
            
            sensors = self.wmi_conn.Sensor()
            
            # 重置数据
            cpu_temp = 0.0
            cpu_fans = []
            cpu_load = 0.0
            gpu_temp = 0.0
            gpu_fans = []
            gpu_load = 0.0
            other_fans = []
            
            # 解析传感器数据
            for sensor in sensors:
                sensor_type = sensor.SensorType
                sensor_name = sensor.Name
                sensor_value = sensor.Value
                parent_name = getattr(sensor, 'Parent', '')
                
                if sensor_type == 'Temperature':
                    if 'cpu' in parent_name.lower() or 'cpu' in sensor_name.lower():
                        try:
                            cpu_temp = max(cpu_temp, float(sensor_value or 0))
                        except:
                            pass
                    elif 'gpu' in parent_name.lower() or 'gpu' in sensor_name.lower() or 'graphics' in parent_name.lower():
                        try:
                            gpu_temp = max(gpu_temp, float(sensor_value or 0))
                        except:
                            pass
                
                elif sensor_type == 'Fan':
                    try:
                        fan_speed = float(sensor_value or 0)
                        if 'cpu' in parent_name.lower() or 'cpu' in sensor_name.lower():
                            cpu_fans.append(fan_speed)
                        elif 'gpu' in parent_name.lower() or 'gpu' in sensor_name.lower():
                            gpu_fans.append(fan_speed)
                        else:
                            other_fans.append({'name': sensor_name, 'speed': fan_speed})
                    except:
                        pass
                
                elif sensor_type == 'Load':
                    try:
                        load_value = float(sensor_value or 0)
                        if 'cpu' in parent_name.lower() or 'cpu' in sensor_name.lower():
                            cpu_load = max(cpu_load, load_value)
                        elif 'gpu' in parent_name.lower() or 'gpu' in sensor_name.lower():
                            gpu_load = max(gpu_load, load_value)
                    except:
                        pass
            
            # 更新数据字典
            self.hardware_data = {
                'cpu': {
                    'temperature': cpu_temp,
                    'fan_speeds': cpu_fans,
                    'load': cpu_load
                },
                'gpu': {
                    'temperature': gpu_temp,
                    'fan_speeds': gpu_fans,
                    'load': gpu_load
                },
                'fans': other_fans,
                'last_update': datetime.now().strftime("%H:%M:%S")
            }
            
            return self.hardware_data
            
        except Exception as e:
            self.error_occurred.emit(f"获取硬件数据失败: {str(e)}")
            return self.get_mock_data()
    
    def get_mock_data(self):
        """生成模拟数据用于测试（当OpenHardwareMonitor不可用时）"""
        import random
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 模拟CPU数据
        cpu_temp = 40 + random.randint(0, 30) + random.random()
        cpu_fans = [800 + random.randint(0, 800) for _ in range(2)]
        cpu_load = 10 + random.randint(0, 60) + random.random()
        
        # 模拟GPU数据
        gpu_temp = 45 + random.randint(0, 35) + random.random()
        gpu_fans = [1000 + random.randint(0, 1000)]
        gpu_load = 15 + random.randint(0, 50) + random.random()
        
        # 模拟其他风扇
        other_fans = [
            {'name': '机箱风扇1', 'speed': 600 + random.randint(0, 400)},
            {'name': '机箱风扇2', 'speed': 700 + random.randint(0, 300)},
            {'name': '水泵', 'speed': 2000 + random.randint(0, 1000)}
        ]
        
        self.hardware_data = {
            'cpu': {
                'temperature': cpu_temp,
                'fan_speeds': cpu_fans,
                'load': cpu_load
            },
            'gpu': {
                'temperature': gpu_temp,
                'fan_speeds': gpu_fans,
                'load': gpu_load
            },
            'fans': other_fans,
            'last_update': current_time
        }
        
        return self.hardware_data
    
    def run(self):
        """线程主循环"""
        self.running = True
        
        # 初始化WMI
        if WMI_AVAILABLE:
            self.init_wmi()
        
        while self.running:
            try:
                data = self.get_hardware_data()
                if data:
                    self.hardware_data_ready.emit(data)
                time.sleep(self.update_interval)
            except Exception as e:
                self.error_occurred.emit(f"监控线程错误: {str(e)}")
                time.sleep(self.update_interval)
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.wait()


# ==================== 硬件监控小组件 ====================
class HardwareMonitorWidget(QWidget):
    """单个硬件监控小组件"""
    
    def __init__(self, title, temperature=0.0, fan_speeds=None, load=0.0, max_temp=100, max_fan=3000, parent=None):
        super().__init__(parent)
        self.title = title
        self.temperature = temperature
        self.fan_speeds = fan_speeds or []
        self.load = load
        self.max_temp = max_temp
        self.max_fan = max_fan
        
        self.init_ui()
        self.update_display()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)
        
        # 温度显示
        temp_layout = QHBoxLayout()
        temp_label = QLabel("温度:")
        temp_label.setMinimumWidth(40)
        self.temp_value_label = QLabel("0.0°C")
        self.temp_value_label.setAlignment(Qt.AlignRight)
        temp_font = QFont()
        temp_font.setPointSize(12)
        temp_font.setBold(True)
        self.temp_value_label.setFont(temp_font)
        
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_value_label)
        layout.addLayout(temp_layout)
        
        # 温度进度条
        self.temp_progress = QProgressBar()
        self.temp_progress.setTextVisible(True)
        self.temp_progress.setFormat("%v°C")
        self.temp_progress.setMaximum(100)
        layout.addWidget(self.temp_progress)
        
        # 负载显示
        load_layout = QHBoxLayout()
        load_label = QLabel("负载:")
        load_label.setMinimumWidth(40)
        self.load_value_label = QLabel("0.0%")
        self.load_value_label.setAlignment(Qt.AlignRight)
        
        load_layout.addWidget(load_label)
        load_layout.addWidget(self.load_value_label)
        layout.addLayout(load_layout)
        
        # 负载进度条
        self.load_progress = QProgressBar()
        self.load_progress.setTextVisible(True)
        self.load_progress.setFormat("%v%")
        self.load_progress.setMaximum(100)
        layout.addWidget(self.load_progress)
        
        # 风扇显示区域
        self.fan_widgets = []
        for i in range(len(self.fan_speeds)):
            fan_layout = QHBoxLayout()
            fan_label = QLabel(f"风扇{i+1}:")
            fan_label.setMinimumWidth(40)
            fan_value_label = QLabel("0 RPM")
            fan_value_label.setAlignment(Qt.AlignRight)
            
            fan_layout.addWidget(fan_label)
            fan_layout.addWidget(fan_value_label)
            layout.addLayout(fan_layout)
            
            fan_progress = QProgressBar()
            fan_progress.setTextVisible(True)
            fan_progress.setFormat("%v RPM")
            fan_progress.setMaximum(100)
            layout.addWidget(fan_progress)
            
            self.fan_widgets.append((fan_value_label, fan_progress))
        
        # 如果没有风扇数据，显示提示
        if not self.fan_speeds:
            no_fan_label = QLabel("无风扇数据")
            no_fan_label.setAlignment(Qt.AlignCenter)
            no_fan_label.setStyleSheet("color: gray;")
            layout.addWidget(no_fan_label)
    
    def update_data(self, temperature, fan_speeds, load):
        """更新数据并刷新显示"""
        self.temperature = temperature
        self.fan_speeds = fan_speeds
        self.load = load
        self.update_display()
    
    def update_display(self):
        """更新显示内容"""
        # 温度
        self.temp_value_label.setText(f"{self.temperature:.1f}°C")
        temp_percent = int((self.temperature / self.max_temp) * 100) if self.max_temp > 0 else 0
        self.temp_progress.setValue(min(temp_percent, 100))
        
        # 根据温度设置颜色
        if self.temperature > 80:
            self.temp_progress.setStyleSheet("QProgressBar::chunk { background-color: #FF0000; }")
        elif self.temperature > 70:
            self.temp_progress.setStyleSheet("QProgressBar::chunk { background-color: #FF6600; }")
        elif self.temperature > 60:
            self.temp_progress.setStyleSheet("QProgressBar::chunk { background-color: #FFCC00; }")
        else:
            self.temp_progress.setStyleSheet("QProgressBar::chunk { background-color: #00CC00; }")
        
        # 负载
        self.load_value_label.setText(f"{self.load:.1f}%")
        self.load_progress.setValue(int(self.load))
        
        # 根据负载设置颜色
        if self.load > 90:
            self.load_progress.setStyleSheet("QProgressBar::chunk { background-color: #FF0000; }")
        elif self.load > 70:
            self.load_progress.setStyleSheet("QProgressBar::chunk { background-color: #FF6600; }")
        elif self.load > 50:
            self.load_progress.setStyleSheet("QProgressBar::chunk { background-color: #FFCC00; }")
        else:
            self.load_progress.setStyleSheet("QProgressBar::chunk { background-color: #00CC00; }")
        
        # 风扇
        for i, (fan_speed, (label, progress)) in enumerate(zip(self.fan_speeds, self.fan_widgets)):
            label.setText(f"{fan_speed:.0f} RPM")
            fan_percent = int((fan_speed / self.max_fan) * 100) if self.max_fan > 0 else 0
            progress.setValue(min(fan_percent, 100))
            
            # 根据风扇速度设置颜色
            if fan_speed > self.max_fan * 0.8:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #FF0000; }")
            elif fan_speed > self.max_fan * 0.6:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #FF6600; }")
            elif fan_speed > self.max_fan * 0.4:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #FFCC00; }")
            else:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #00CC00; }")
        
        # 如果风扇数量变化，需要重新创建UI
        if len(self.fan_speeds) != len(self.fan_widgets):
            self.recreate_fan_widgets()
    
    def recreate_fan_widgets(self):
        """重新创建风扇显示组件"""
        # 移除所有风扇相关组件
        for label, progress in self.fan_widgets:
            label.setParent(None)
            progress.setParent(None)
        
        self.fan_widgets = []
        
        # 重新添加风扇组件
        layout = self.layout()
        # 移除除前4个元素外的所有元素（标题、温度标签、温度值、温度进度条、负载标签、负载值、负载进度条）
        # 这里简单实现：移除所有然后重新添加
        while layout.count() > 7:  # 保留前7个元素
            item = layout.takeAt(7)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新的风扇显示
        for i in range(len(self.fan_speeds)):
            fan_layout = QHBoxLayout()
            fan_label = QLabel(f"风扇{i+1}:")
            fan_label.setMinimumWidth(40)
            fan_value_label = QLabel("0 RPM")
            fan_value_label.setAlignment(Qt.AlignRight)
            
            fan_layout.addWidget(fan_label)
            fan_layout.addWidget(fan_value_label)
            layout.addLayout(fan_layout)
            
            fan_progress = QProgressBar()
            fan_progress.setTextVisible(True)
            fan_progress.setFormat("%v RPM")
            fan_progress.setMaximum(100)
            layout.addWidget(fan_progress)
            
            self.fan_widgets.append((fan_value_label, fan_progress))
        
        # 如果没有风扇数据，显示提示
        if not self.fan_speeds and layout.count() == 7:
            no_fans_label = QLabel("无风扇数据")
            no_fans_label.setAlignment(Qt.AlignCenter)
            no_fans_label.setStyleSheet("color: gray;")
            layout.addWidget(no_fans_label)
            self.fan_widgets.append((no_fans_label, None))


# ==================== 主窗口类 ====================
class HardwareMonitorWindow(QMainWindow):
    """硬件监控主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 应用设置
        self.settings = QSettings("HardwareMonitor", "AppConfig")
        self.update_interval = 2.0
        self.max_cpu_temp = 100
        self.max_gpu_temp = 100
        self.max_fan_speed = 3000
        self.start_minimized = False
        self.always_on_top = False
        self.show_system_tray = True
        
        # 硬件监控线程
        self.monitor_thread = None
        
        # 初始化UI
        self.init_ui()
        
        # 加载设置
        self.load_settings()
        
        # 设置窗口图标
        self.set_window_icon()
        
        # 初始化系统托盘
        if self.show_system_tray:
            self.init_system_tray()
        
        # 启动硬件监控
        self.start_hardware_monitor()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("硬件监控系统 - OpenHardwareMonitor")
        self.setMinimumSize(800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_label = QLabel("正在初始化硬件监控...")
        self.status_bar.addWidget(self.status_label)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 监控选项卡
        self.monitor_tab = QWidget()
        self.tab_widget.addTab(self.monitor_tab, "硬件监控")
        
        # 设置选项卡
        self.settings_tab = QWidget()
        self.tab_widget.addTab(self.settings_tab, "设置")
        
        # 初始化监控选项卡
        self.init_monitor_tab()
        
        # 初始化设置选项卡
        self.init_settings_tab()
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("立即刷新")
        self.refresh_button.clicked.connect(self.force_refresh)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        
        self.minimize_button = QPushButton("最小化到托盘")
        self.minimize_button.clicked.connect(self.minimize_to_tray)
        button_layout.addWidget(self.minimize_button)
        
        self.quit_button = QPushButton("退出")
        self.quit_button.clicked.connect(self.close)
        button_layout.addWidget(self.quit_button)
        
        main_layout.addLayout(button_layout)
    
    def init_monitor_tab(self):
        """初始化监控选项卡"""
        layout = QGridLayout(self.monitor_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # CPU监控组
        cpu_group = QGroupBox("CPU 监控")
        cpu_layout = QVBoxLayout()
        self.cpu_widget = HardwareMonitorWidget(
            "中央处理器", 
            max_temp=self.max_cpu_temp, 
            max_fan=self.max_fan_speed
        )
        cpu_layout.addWidget(self.cpu_widget)
        cpu_group.setLayout(cpu_layout)
        layout.addWidget(cpu_group, 0, 0)
        
        # GPU监控组
        gpu_group = QGroupBox("GPU 监控")
        gpu_layout = QVBoxLayout()
        self.gpu_widget = HardwareMonitorWidget(
            "图形处理器", 
            max_temp=self.max_gpu_temp, 
            max_fan=self.max_fan_speed
        )
        gpu_layout.addWidget(self.gpu_widget)
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group, 0, 1)
        
        # 其他风扇监控组
        self.fans_group = QGroupBox("其他风扇监控")
        fans_layout = QVBoxLayout()
        self.fans_scroll_widget = QWidget()
        self.fans_scroll_layout = QVBoxLayout(self.fans_scroll_widget)
        
        # 初始风扇组件
        self.fan_widgets = []
        for i in range(3):
            fan_widget = self.create_fan_widget(i)
            self.fans_scroll_layout.addWidget(fan_widget)
            self.fan_widgets.append(fan_widget)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.fans_scroll_widget)
        scroll_area.setMaximumHeight(200)
        
        fans_layout.addWidget(scroll_area)
        self.fans_group.setLayout(fans_layout)
        layout.addWidget(self.fans_group, 1, 0, 1, 2)
        
        # 系统信息组
        sys_group = QGroupBox("系统信息")
        sys_layout = QVBoxLayout()
        
        self.update_time_label = QLabel("最后更新: 未更新")
        self.update_time_label.setAlignment(Qt.AlignCenter)
        sys_layout.addWidget(self.update_time_label)
        
        self.system_info_label = QLabel("正在获取系统信息...")
        self.system_info_label.setAlignment(Qt.AlignCenter)
        sys_layout.addWidget(self.system_info_label)
        
        # 硬件检测进度条
        self.hardware_detect_progress = QProgressBar()
        self.hardware_detect_progress.setTextVisible(True)
        self.hardware_detect_progress.setFormat("硬件检测: %p%")
        self.hardware_detect_progress.setValue(0)
        sys_layout.addWidget(self.hardware_detect_progress)
        
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group, 2, 0, 1, 2)
        
        # 设置列和行的拉伸比例
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 2)
        layout.setRowStretch(1, 1)
        layout.setRowStretch(2, 0)
    
    def create_fan_widget(self, index, name=None, speed=0):
        """创建单个风扇显示组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        if name is None:
            name = f"风扇 {index+1}"
        
        name_label = QLabel(f"{name}:")
        name_label.setMinimumWidth(80)
        
        # 确保speed是数值类型
        try:
            speed_float = float(speed)
        except:
            speed_float = 0.0
            
        speed_label = QLabel(f"{speed_float:.0f} RPM")
        speed_label.setAlignment(Qt.AlignRight)
        speed_label.setMinimumWidth(80)
        
        progress = QProgressBar()
        progress.setTextVisible(True)
        progress.setFormat("%v RPM")
        progress.setMaximum(self.max_fan_speed)
        
        # 修复: 确保传入整数
        progress.setValue(min(int(speed_float), self.max_fan_speed))
        
        layout.addWidget(name_label)
        layout.addWidget(speed_label)
        layout.addWidget(progress)
        
        # 根据速度设置颜色
        speed_int = int(speed_float)
        if speed_int > self.max_fan_speed * 0.8:
            progress.setStyleSheet("QProgressBar::chunk { background-color: #FF0000; }")
        elif speed_int > self.max_fan_speed * 0.6:
            progress.setStyleSheet("QProgressBar::chunk { background-color: #FF6600; }")
        elif speed_int > self.max_fan_speed * 0.4:
            progress.setStyleSheet("QProgressBar::chunk { background-color: #FFCC00; }")
        else:
            progress.setStyleSheet("QProgressBar::chunk { background-color: #00CC00; }")
        
        return widget
    
    def init_settings_tab(self):
        """初始化设置选项卡"""
        layout = QVBoxLayout(self.settings_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 监控设置组
        monitor_group = QGroupBox("监控设置")
        monitor_layout = QGridLayout()
        
        monitor_layout.addWidget(QLabel("更新间隔(秒):"), 0, 0)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 60.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(self.update_interval)
        self.interval_spin.valueChanged.connect(self.update_interval_changed)
        monitor_layout.addWidget(self.interval_spin, 0, 1)
        
        monitor_layout.addWidget(QLabel("CPU最大温度(°C):"), 1, 0)
        self.cpu_temp_spin = QSpinBox()
        self.cpu_temp_spin.setRange(60, 120)
        self.cpu_temp_spin.setValue(self.max_cpu_temp)
        self.cpu_temp_spin.valueChanged.connect(self.cpu_temp_changed)
        monitor_layout.addWidget(self.cpu_temp_spin, 1, 1)
        
        monitor_layout.addWidget(QLabel("GPU最大温度(°C):"), 2, 0)
        self.gpu_temp_spin = QSpinBox()
        self.gpu_temp_spin.setRange(60, 120)
        self.gpu_temp_spin.setValue(self.max_gpu_temp)
        self.gpu_temp_spin.valueChanged.connect(self.gpu_temp_changed)
        monitor_layout.addWidget(self.gpu_temp_spin, 2, 1)
        
        monitor_layout.addWidget(QLabel("风扇最大转速(RPM):"), 3, 0)
        self.fan_speed_spin = QSpinBox()
        self.fan_speed_spin.setRange(1000, 10000)
        self.fan_speed_spin.setSingleStep(500)
        self.fan_speed_spin.setValue(self.max_fan_speed)
        self.fan_speed_spin.valueChanged.connect(self.fan_speed_changed)
        monitor_layout.addWidget(self.fan_speed_spin, 3, 1)
        
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)
        
        # 窗口设置组
        window_group = QGroupBox("窗口设置")
        window_layout = QVBoxLayout()
        
        self.start_minimized_check = QCheckBox("启动时最小化")
        self.start_minimized_check.setChecked(self.start_minimized)
        self.start_minimized_check.stateChanged.connect(self.start_minimized_changed)
        window_layout.addWidget(self.start_minimized_check)
        
        self.always_on_top_check = QCheckBox("窗口始终置顶")
        self.always_on_top_check.setChecked(self.always_on_top)
        self.always_on_top_check.stateChanged.connect(self.always_on_top_changed)
        window_layout.addWidget(self.always_on_top_check)
        
        self.system_tray_check = QCheckBox("启用系统托盘图标")
        self.system_tray_check.setChecked(self.show_system_tray)
        self.system_tray_check.stateChanged.connect(self.system_tray_changed)
        window_layout.addWidget(self.system_tray_check)
        
        window_group.setLayout(window_layout)
        layout.addWidget(window_group)
        
        # 按钮组
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("恢复默认")
        self.reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_button)
        
        self.about_button = QPushButton("关于")
        self.about_button.clicked.connect(self.show_about)
        button_layout.addWidget(self.about_button)
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
    
    def init_system_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # 设置托盘图标
        if os.path.exists("icon.ico"):
            self.tray_icon.setIcon(QIcon("icon.ico"))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window_from_tray)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # 托盘图标点击事件
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # 显示托盘图标
        self.tray_icon.show()
        
        # 设置托盘提示
        self.tray_icon.setToolTip("硬件监控系统")
    
    def set_window_icon(self):
        """设置窗口图标"""
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))
    
    def start_hardware_monitor(self):
        """启动硬件监控线程"""
        self.monitor_thread = HardwareMonitorThread(self.update_interval)
        self.monitor_thread.hardware_data_ready.connect(self.update_hardware_data)
        self.monitor_thread.error_occurred.connect(self.show_error)
        self.monitor_thread.start()
        
        # 模拟硬件检测进度
        self.hardware_detect_progress.setValue(30)
        QTimer.singleShot(500, lambda: self.hardware_detect_progress.setValue(60))
        QTimer.singleShot(1000, lambda: self.hardware_detect_progress.setValue(90))
        QTimer.singleShot(1500, lambda: self.hardware_detect_progress.setValue(100))
    
    @pyqtSlot(dict)
    def update_hardware_data(self, data):
        """更新硬件数据显示"""
        try:
            # 更新CPU数据
            cpu_data = data['cpu']
            self.cpu_widget.update_data(
                cpu_data['temperature'],
                cpu_data['fan_speeds'],
                cpu_data['load']
            )
            
            # 更新GPU数据
            gpu_data = data['gpu']
            self.gpu_widget.update_data(
                gpu_data['temperature'],
                gpu_data['fan_speeds'],
                gpu_data['load']
            )
            
            # 更新其他风扇数据
            fans_data = data['fans']
            
            # 清除现有风扇组件
            for widget in self.fan_widgets:
                widget.setParent(None)
            self.fan_widgets.clear()
            
            # 清除滚动区域中的所有组件
            while self.fans_scroll_layout.count():
                item = self.fans_scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 添加新的风扇组件
            for i, fan_data in enumerate(fans_data):
                fan_widget = self.create_fan_widget(
                    i, 
                    fan_data.get('name', f'风扇{i+1}'), 
                    fan_data.get('speed', 0)
                )
                self.fans_scroll_layout.addWidget(fan_widget)
                self.fan_widgets.append(fan_widget)
            
            # 如果没有风扇数据，显示提示
            if not fans_data:
                no_fans_label = QLabel("未检测到其他风扇")
                no_fans_label.setAlignment(Qt.AlignCenter)
                no_fans_label.setStyleSheet("color: gray;")
                self.fans_scroll_layout.addWidget(no_fans_label)
            
            # 更新最后更新时间
            self.update_time_label.setText(f"最后更新: {data.get('last_update', '未知')}")
            
            # 更新状态栏
            cpu_temp = cpu_data['temperature']
            gpu_temp = gpu_data['temperature']
            self.status_label.setText(f"CPU: {cpu_temp:.1f}°C, GPU: {gpu_temp:.1f}°C | 更新于: {data.get('last_update', '未知')}")
            
            # 更新系统信息
            total_fans = len(cpu_data['fan_speeds']) + len(gpu_data['fan_speeds']) + len(fans_data)
            self.system_info_label.setText(f"检测到: {total_fans}个风扇 | CPU负载: {cpu_data['load']:.1f}% | GPU负载: {gpu_data['load']:.1f}%")
            
            # 更新托盘提示
            if hasattr(self, 'tray_icon'):
                self.tray_icon.setToolTip(f"CPU: {cpu_temp:.1f}°C\nGPU: {gpu_temp:.1f}°C")
                
        except Exception as e:
            print(f"更新硬件数据时出错: {e}")
    
    @pyqtSlot(str)
    def show_error(self, error_msg):
        """显示错误信息"""
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.warning(self, "硬件监控错误", error_msg)
    
    def force_refresh(self):
        """强制刷新硬件数据"""
        if self.monitor_thread and self.monitor_thread.isRunning():
            # 在线程中手动触发一次数据获取
            data = self.monitor_thread.get_hardware_data()
            if data:
                self.update_hardware_data(data)
    
    def minimize_to_tray(self):
        """最小化到系统托盘"""
        if hasattr(self, 'tray_icon'):
            self.hide()
            self.tray_icon.showMessage(
                "硬件监控", 
                "程序已最小化到系统托盘", 
                QSystemTrayIcon.Information, 
                2000
            )
    
    def show_window_from_tray(self):
        """从系统托盘显示窗口"""
        self.show()
        self.activateWindow()
        self.raise_()
    
    def tray_icon_activated(self, reason):
        """系统托盘图标被激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window_from_tray()
    
    # ==================== 设置相关方法 ====================
    def load_settings(self):
        """加载设置"""
        # 窗口位置和大小
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # 应用设置
        self.update_interval = float(self.settings.value("update_interval", 2.0))
        self.max_cpu_temp = int(self.settings.value("max_cpu_temp", 100))
        self.max_gpu_temp = int(self.settings.value("max_gpu_temp", 100))
        self.max_fan_speed = int(self.settings.value("max_fan_speed", 3000))
        self.start_minimized = self.settings.value("start_minimized", False, type=bool)
        self.always_on_top = self.settings.value("always_on_top", False, type=bool)
        self.show_system_tray = self.settings.value("show_system_tray", True, type=bool)
        
        # 更新UI控件
        if hasattr(self, 'interval_spin'):
            self.interval_spin.setValue(self.update_interval)
            self.cpu_temp_spin.setValue(self.max_cpu_temp)
            self.gpu_temp_spin.setValue(self.max_gpu_temp)
            self.fan_speed_spin.setValue(self.max_fan_speed)
            self.start_minimized_check.setChecked(self.start_minimized)
            self.always_on_top_check.setChecked(self.always_on_top)
            self.system_tray_check.setChecked(self.show_system_tray)
        
        # 应用窗口置顶设置
        if self.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
    
    def save_settings(self):
        """保存设置"""
        # 窗口位置和大小
        self.settings.setValue("window_geometry", self.saveGeometry())
        
        # 应用设置
        self.settings.setValue("update_interval", self.update_interval)
        self.settings.setValue("max_cpu_temp", self.max_cpu_temp)
        self.settings.setValue("max_gpu_temp", self.max_gpu_temp)
        self.settings.setValue("max_fan_speed", self.max_fan_speed)
        self.settings.setValue("start_minimized", self.start_minimized)
        self.settings.setValue("always_on_top", self.always_on_top)
        self.settings.setValue("show_system_tray", self.show_system_tray)
        
        # 应用窗口置顶设置
        if self.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        
        # 重新显示窗口以应用标志更改
        self.show()
        
        # 更新监控线程间隔
        if self.monitor_thread:
            self.monitor_thread.update_interval = self.update_interval
        
        # 更新硬件监控组件的最大值
        self.cpu_widget.max_temp = self.max_cpu_temp
        self.cpu_widget.max_fan = self.max_fan_speed
        self.gpu_widget.max_temp = self.max_gpu_temp
        self.gpu_widget.max_fan = self.max_fan_speed
        
        QMessageBox.information(self, "设置已保存", "设置已成功保存，部分设置需要重启应用才能生效。")
    
    def reset_settings(self):
        """恢复默认设置"""
        reply = QMessageBox.question(
            self, 
            "确认恢复默认", 
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 重置设置值
            self.update_interval = 2.0
            self.max_cpu_temp = 100
            self.max_gpu_temp = 100
            self.max_fan_speed = 3000
            self.start_minimized = False
            self.always_on_top = False
            self.show_system_tray = True
            
            # 更新UI控件
            self.interval_spin.setValue(self.update_interval)
            self.cpu_temp_spin.setValue(self.max_cpu_temp)
            self.gpu_temp_spin.setValue(self.max_gpu_temp)
            self.fan_speed_spin.setValue(self.max_fan_speed)
            self.start_minimized_check.setChecked(self.start_minimized)
            self.always_on_top_check.setChecked(self.always_on_top)
            self.system_tray_check.setChecked(self.show_system_tray)
            
            QMessageBox.information(self, "设置已重置", "所有设置已恢复为默认值。")
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>硬件监控系统</h2>
        <p>版本: 1.0.0</p>
        <p>基于OpenHardwareMonitor的硬件监控程序</p>
        <p>功能:</p>
        <ul>
            <li>实时监控CPU和GPU温度</li>
            <li>监控CPU、GPU和其他风扇转速</li>
            <li>显示CPU和GPU负载</li>
            <li>多线程处理，不影响界面响应</li>
            <li>自适应各种分辨率</li>
            <li>设置自动保存</li>
            <li>系统托盘支持</li>
        </ul>
        <p>注意: 需要安装OpenHardwareMonitor并运行</p>
        <p>GitHub: https://github.com/example/hardware-monitor</p>
        """
        QMessageBox.about(self, "关于硬件监控系统", about_text)
    
    # ==================== 设置变更槽函数 ====================
    def update_interval_changed(self, value):
        self.update_interval = value
    
    def cpu_temp_changed(self, value):
        self.max_cpu_temp = value
    
    def gpu_temp_changed(self, value):
        self.max_gpu_temp = value
    
    def fan_speed_changed(self, value):
        self.max_fan_speed = value
    
    def start_minimized_changed(self, state):
        self.start_minimized = (state == Qt.Checked)
    
    def always_on_top_changed(self, state):
        self.always_on_top = (state == Qt.Checked)
    
    def system_tray_changed(self, state):
        self.show_system_tray = (state == Qt.Checked)
    
    # ==================== 事件处理 ====================
    def closeEvent(self, event: QCloseEvent):
        """窗口关闭事件处理"""
        # 停止监控线程
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.stop()
            self.monitor_thread.wait()
        
        # 如果启用了系统托盘，最小化到托盘而不是退出
        if hasattr(self, 'tray_icon') and self.show_system_tray and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "硬件监控", 
                "程序仍在后台运行，双击托盘图标可恢复窗口", 
                QSystemTrayIcon.Information, 
                3000
            )
        else:
            # 保存窗口位置和大小
            self.settings.setValue("window_geometry", self.saveGeometry())
            event.accept()
    
    def showEvent(self, event):
        """窗口显示事件处理"""
        super().showEvent(event)
        # 如果设置启动时最小化，则最小化窗口
        if self.start_minimized and not self.isMinimized():
            self.showMinimized()


# ==================== 应用程序主函数 ====================
def main():
    """应用程序主函数"""
    # 创建应用实例
    app = QApplication(sys.argv)
    app.setApplicationName("硬件监控系统")
    app.setOrganizationName("HardwareMonitor")
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = HardwareMonitorWindow()
    
    # 根据设置决定是否显示窗口
    if not window.start_minimized:
        window.show()
    else:
        window.showMinimized()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()