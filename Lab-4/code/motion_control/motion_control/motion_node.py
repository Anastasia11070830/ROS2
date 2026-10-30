import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String


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

        self.sensor_alarm = False
        self.subscription = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.alarm_subscription = self.create_subscription(
            Bool, '/sensor_alarm', self.alarm_callback, 10)
        self.publisher_ = self.create_publisher(Twist, output_topic, 10)
        self.status_publisher = self.create_publisher(String, '/motion_status', 10)

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

    def alarm_callback(self, msg):
        if msg.data != self.sensor_alarm:
            self.sensor_alarm = msg.data
            if self.sensor_alarm:
                self.get_logger().warn('Sensor alarm ON: forward motion is blocked')
            else:
                self.get_logger().info('Sensor alarm OFF: motion allowed')

    def cmd_vel_callback(self, msg):
        self.get_logger().info(
            f'Received: linear.x={msg.linear.x:.2f}, angular.z={msg.angular.z:.2f}')

        cmd = Twist()
        cmd.linear.x = self.limit('linear.x', msg.linear.x, self.max_linear)
        cmd.angular.z = self.limit('angular.z', msg.angular.z, self.max_angular)
        limited = (cmd.linear.x, cmd.angular.z) != (msg.linear.x, msg.angular.z)

        # Тривога сенсора забороняє лише рух вперед; назад і поворот дозволені
        blocked = self.sensor_alarm and cmd.linear.x > 0.0
        if blocked:
            cmd.linear.x = 0.0
            self.get_logger().warn(
                'Forward motion blocked by sensor alarm', throttle_duration_sec=1.0)

        self.publisher_.publish(cmd)

        self.get_logger().info(
            f'Sent: linear.x={cmd.linear.x:.2f}, angular.z={cmd.angular.z:.2f}')

        # Статус для GUI: OK, LIMITED (швидкість обмежено) або BLOCKED (рух заблоковано)
        label = 'BLOCKED' if blocked else ('LIMITED' if limited else 'OK')
        status = String()
        status.data = (f'{label}: '
                       f'linear.x={cmd.linear.x:.2f}, angular.z={cmd.angular.z:.2f}')
        self.status_publisher.publish(status)


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
