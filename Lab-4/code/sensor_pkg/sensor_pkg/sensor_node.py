import math
import random
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32


class SensorNode(Node):

    def __init__(self):
        super().__init__('sensor_node')
        self.declare_parameter('publish_rate', 10.0)      # Гц
        self.declare_parameter('window_size', 7)          # розмір вікна усереднення
        self.declare_parameter('threshold', 0.6)          # м, нижче — критично
        self.declare_parameter('noise_std', 0.04)         # м, шум сенсора
        self.declare_parameter('spike_probability', 0.02) # імовірність викиду
        self.declare_parameter('period', 24.0)            # с, період зміни відстані

        self.rate = self.get_parameter('publish_rate').value
        self.window = deque(maxlen=self.get_parameter('window_size').value)
        self.noise_std = self.get_parameter('noise_std').value
        self.spike_probability = self.get_parameter('spike_probability').value
        self.period = self.get_parameter('period').value

        self.raw_pub = self.create_publisher(Float32, '/sensor_data', 10)
        self.filtered_pub = self.create_publisher(Float32, '/sensor_data_filtered', 10)
        self.alarm_pub = self.create_publisher(Bool, '/sensor_alarm', 10)

        self.step = 0
        self.alarm = False
        # Таймер задає періодичність публікації (10 Гц = кожні 0.1 с)
        self.timer = self.create_timer(1.0 / self.rate, self.timer_callback)

        self.get_logger().info(
            f'Sensor Node started: rate={self.rate} Hz, '
            f'window={self.window.maxlen}, threshold={self.get_parameter("threshold").value} m')

    def read_sensor(self):
        # Імітація дальноміра: плавна зміна відстані + шум + рідкісні викиди
        t = self.step / self.rate
        value = 1.4 + 1.0 * math.sin(2.0 * math.pi * t / self.period)
        value += random.gauss(0.0, self.noise_std)
        if random.random() < self.spike_probability:
            value = random.uniform(0.08, 0.2)
        return max(value, 0.02)

    def timer_callback(self):
        raw = self.read_sensor()
        self.step += 1

        # Усереднення: середнє арифметичне останніх N вимірювань
        self.window.append(raw)
        filtered = sum(self.window) / len(self.window)

        self.raw_pub.publish(Float32(data=raw))
        self.filtered_pub.publish(Float32(data=filtered))

        # Поріг читається щоразу, тож його можна змінювати командою ros2 param set
        threshold = self.get_parameter('threshold').value
        critical = filtered < threshold
        if critical:
            self.get_logger().warn(
                f'CRITICAL: filtered={filtered:.2f} m is below threshold {threshold:.2f} m',
                throttle_duration_sec=1.0)
        elif self.alarm:
            self.get_logger().info(f'Value back to normal: filtered={filtered:.2f} m')
        self.alarm = critical
        self.alarm_pub.publish(Bool(data=self.alarm))

        self.get_logger().info(
            f'raw={raw:.2f} m, filtered={filtered:.2f} m', throttle_duration_sec=1.0)


def main(args=None):
    rclpy.init(args=args)
    node = SensorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
