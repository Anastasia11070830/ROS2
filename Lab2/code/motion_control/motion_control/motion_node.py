import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class MotionNode(Node):

    def __init__(self):
        super().__init__('motion_node')
        # Межі швидкості задані параметрами — їх можна змінити без зміни коду
        self.declare_parameter('max_linear_speed', 1.0)
        self.declare_parameter('max_angular_speed', 1.5)
        self.declare_parameter('output_topic', '/turtle1/cmd_vel')
        self.max_linear = self.get_parameter('max_linear_speed').value
        self.max_angular = self.get_parameter('max_angular_speed').value
        output_topic = self.get_parameter('output_topic').value

        self.subscription = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.publisher_ = self.create_publisher(Twist, output_topic, 10)

        self.get_logger().info(
            f'Motion Node started: max_linear={self.max_linear} m/s, '
            f'max_angular={self.max_angular} rad/s, output={output_topic}')

    def limit(self, name, value, max_value):
        if abs(value) <= max_value:
            return value
        # Обрізаємо до порогу, зберігаючи напрямок руху
        limited = math.copysign(max_value, value)
        self.get_logger().warn(
            f'{name}={value:.2f} exceeds limit +/-{max_value:.2f}, '
            f'limited to {limited:.2f}')
        return limited

    def cmd_vel_callback(self, msg):
        self.get_logger().info(
            f'Received: linear.x={msg.linear.x:.2f}, angular.z={msg.angular.z:.2f}')

        cmd = Twist()
        cmd.linear.x = self.limit('linear.x', msg.linear.x, self.max_linear)
        cmd.angular.z = self.limit('angular.z', msg.angular.z, self.max_angular)
        self.publisher_.publish(cmd)

        self.get_logger().info(
            f'Sent: linear.x={cmd.linear.x:.2f}, angular.z={cmd.angular.z:.2f}')


def main(args=None):
    rclpy.init(args=args)
    node = MotionNode()
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
