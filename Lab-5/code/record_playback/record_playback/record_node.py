import os

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class RecordNode(Node):

    def __init__(self):
        super().__init__('record_node')
        self.declare_parameter('file', '~/ros2_ws/data/route.csv')
        path = os.path.expanduser(self.get_parameter('file').value)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Файл відкривається на запис: попередній сценарій перезаписується
        self.file = open(path, 'w', encoding='utf-8')
        self.file.write('time, linear_x, angular_z\n')
        self.start = None
        self.count = 0

        self.subscription = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.get_logger().info(f'Recording /cmd_vel to {path}. Press Ctrl+C to finish.')

    def cmd_vel_callback(self, msg):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.start is None:
            # Час відраховується від першої отриманої команди
            self.start = now
        elapsed = now - self.start

        self.file.write(f'{elapsed:.3f}, {msg.linear.x:.3f}, {msg.angular.z:.3f}\n')
        # flush: дані потрапляють у файл одразу, навіть якщо ноду буде перервано
        self.file.flush()
        self.count += 1
        self.get_logger().info(
            f'#{self.count} t={elapsed:.3f} s, '
            f'linear.x={msg.linear.x:.3f}, angular.z={msg.angular.z:.3f}')

    def close(self):
        self.file.close()
        self.get_logger().info(f'Recording finished: {self.count} commands saved')


def main(args=None):
    rclpy.init(args=args)
    node = RecordNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
