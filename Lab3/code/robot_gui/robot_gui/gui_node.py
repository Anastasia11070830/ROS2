import signal
import sys

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from PyQt5.QtCore import Qt, QTime, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
)

# Стилізація інтерфейсу (Modern Dark Theme)
MODERN_STYLE = """
QWidget {
    background-color: #1e1e24;
    color: #f0f0f5;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #3e4251;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
    color: #61afef;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QDoubleSpinBox {
    background-color: #2b2d3a;
    border: 1px solid #4f5368;
    border-radius: 5px;
    padding: 4px 8px;
    color: #ffffff;
    font-weight: bold;
}

QDoubleSpinBox:focus {
    border: 1px solid #61afef;
}

QPushButton {
    background-color: #2e3440;
    color: #eceff4;
    border: 1px solid #4c566a;
    border-radius: 6px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #3b4252;
    border-color: #88c0d0;
}

QPushButton:pressed {
    background-color: #434c5e;
}

/* Спеціальний стиль для кнопки СТОП */
QPushButton#stop_btn {
    background-color: #e06c75;
    color: #ffffff;
    border: 1px solid #be5046;
}

QPushButton#stop_btn:hover {
    background-color: #be5046;
}

QPushButton#stop_btn:pressed {
    background-color: #983830;
}

/* Вікно терміналу / логів */
QPlainTextEdit {
    background-color: #14161d;
    border: 1px solid #282c34;
    border-radius: 6px;
    color: #98c379;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px;
}

QLabel#cmd_badge {
    background-color: #2b2d3a;
    border: 1px solid #3e4251;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e5c07b;
    font-weight: bold;
}
"""


class RobotGuiNode(Node):

    def __init__(self, on_status):
        super().__init__('robot_gui')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.subscription = self.create_subscription(
            String, '/motion_status', lambda msg: on_status(msg.data), 10)

    def send_command(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.publisher_.publish(msg)
        self.get_logger().info(
            f'Published /cmd_vel: linear.x={linear_x:.2f}, angular.z={angular_z:.2f}')


class ControlWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.node = RobotGuiNode(self.show_status)
        self.setWindowTitle('Керування роботом (ROS2 / Qt GUI)')
        self.setMinimumWidth(460)
        self.setStyleSheet(MODERN_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # --- 1. Блок налаштування швидкості ---
        speed_group = QGroupBox('Параметри швидкості')
        speed_form = QFormLayout(speed_group)
        speed_form.setContentsMargins(15, 15, 15, 15)

        self.linear_speed = self.make_spinbox(0.5)
        self.angular_speed = self.make_spinbox(1.0)
        speed_form.addRow('Лінійна швидкість (м/с):', self.linear_speed)
        speed_form.addRow('Кутова швидкість (рад/с):', self.angular_speed)
        main_layout.addWidget(speed_group)

        # --- 2. Блок кнопок керування ---
        control_group = QGroupBox('Пульт керування (або W, A, S, D / Стрілки)')
        control_layout = QVBoxLayout(control_group)

        buttons_grid = QGridLayout()
        buttons_grid.setSpacing(8)

        self.add_button(buttons_grid, '▲\nВперед', 0, 1, 1, 0)
        self.add_button(buttons_grid, '◀\nЛіворуч', 1, 0, 0, 1)
        self.add_button(buttons_grid, '⏹\nСТОП', 1, 1, 0, 0, is_stop=True)
        self.add_button(buttons_grid, '▶\nПраворуч', 1, 2, 0, -1)
        self.add_button(buttons_grid, '▼\nНазад', 2, 1, -1, 0)
        control_layout.addLayout(buttons_grid)

        self.command_label = QLabel('Остання команда: Очікування дій')
        self.command_label.setObjectName('cmd_badge')
        control_layout.addWidget(self.command_label)
        main_layout.addWidget(control_group)

        # --- 3. Блок журналу та статусу ---
        status_group = QGroupBox('Статус системи (/motion_status)')
        status_layout = QVBoxLayout(status_group)

        self.status_box = QPlainTextEdit()
        self.status_box.setReadOnly(True)
        self.status_box.setMaximumBlockCount(150)
        status_layout.addWidget(self.status_box)

        # Кнопка очищення логу
        clear_btn = QPushButton('Очистити журнал')
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self.status_box.clear)
        status_layout.addWidget(clear_btn)

        main_layout.addWidget(status_group)

        # Таймер для спину ROS2 (кожні 40 мс = 25 Гц)
        self.ros_timer = QTimer(self)
        self.ros_timer.timeout.connect(
            lambda: rclpy.spin_once(self.node, timeout_sec=0))
        self.ros_timer.start(40)

        self.show_status('GUI запущено, топіки підключено.')

    def make_spinbox(self, value):
        box = QDoubleSpinBox()
        box.setRange(0.0, 5.0)
        box.setSingleStep(0.1)
        box.setValue(value)
        box.setFixedHeight(28)
        return box

    def add_button(self, grid, text, row, col, linear_dir, angular_dir, is_stop=False):
        button = QPushButton(text)
        button.setMinimumSize(100, 55)
        button.setAutoRepeat(bool(linear_dir or angular_dir))
        button.setAutoRepeatDelay(250)
        button.setAutoRepeatInterval(100)

        if is_stop:
            button.setObjectName('stop_btn')

        button.clicked.connect(
            lambda: self.on_button(text.replace('\n', ' '), linear_dir, angular_dir))
        grid.addWidget(button, row, col)

    def on_button(self, name, linear_dir, angular_dir):
        linear_x = linear_dir * self.linear_speed.value()
        angular_z = angular_dir * self.angular_speed.value()
        self.node.send_command(linear_x, angular_z)
        self.command_label.setText(
            f'Остання команда: {name} (lin={linear_x:.2f}, ang={angular_z:.2f})')

    def show_status(self, text):
        time = QTime.currentTime().toString('HH:mm:ss')
        self.status_box.appendPlainText(f'[{time}] {text}')

    # Підтримка гарячих клавіш з клавіатури
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_W):
            self.on_button('Вперед', 1, 0)
        elif key in (Qt.Key_Down, Qt.Key_S):
            self.on_button('Назад', -1, 0)
        elif key in (Qt.Key_Left, Qt.Key_A):
            self.on_button('Ліворуч', 0, 1)
        elif key in (Qt.Key_Right, Qt.Key_D):
            self.on_button('Праворуч', 0, -1)
        elif key in (Qt.Key_Space, Qt.Key_Escape):
            self.on_button('СТОП', 0, 0)
        else:
            super().keyPressEvent(event)


def main(args=None):
    rclpy.init(args=args)
    app = QApplication(sys.argv)
    window = ControlWindow()
    window.show()

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    app.exec_()

    window.node.send_command(0.0, 0.0)
    window.node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()