import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String


class MonitorNode(Node):

    def __init__(self):
        super().__init__('monitor_node')
        self.declare_parameter('heartbeat_timeout', 2.5)  # с без heartbeat = нода не відповідає
        self.declare_parameter('data_timeout', 2.5)       # с без даних = дані не приходять
        self.declare_parameter('expected_rate', 10.0)     # Гц, очікувана частота /sensor_data
        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self.data_timeout = self.get_parameter('data_timeout').value
        self.expected_rate = self.get_parameter('expected_rate').value

        now = self.now()
        self.last_heartbeat = now
        self.last_data = now
        self.last_check = now
        self.data_count = 0
        self.state = None

        self.create_subscription(String, '/heartbeat', self.heartbeat_callback, 10)
        self.create_subscription(Float32, '/sensor_data', self.data_callback, 10)
        self.status_pub = self.create_publisher(String, '/system_status', 10)
        # Раз на секунду оцінюємо стан системи
        self.timer = self.create_timer(1.0, self.check)

        self.get_logger().info(
            f'Monitor Node started: heartbeat_timeout={self.heartbeat_timeout} s, '
            f'data_timeout={self.data_timeout} s, expected_rate={self.expected_rate} Hz')

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def heartbeat_callback(self, msg):
        self.last_heartbeat = self.now()
        self.get_logger().debug(f'Heartbeat received: {msg.data}')

    def data_callback(self, msg):
        self.last_data = self.now()
        self.data_count += 1

    def check(self):
        now = self.now()
        heartbeat_age = now - self.last_heartbeat
        data_age = now - self.last_data
        rate = self.data_count / (now - self.last_check)
        self.data_count = 0
        self.last_check = now

        if heartbeat_age > self.heartbeat_timeout:
            level = 'ERROR'
            text = f'Heartbeat lost: no signal for {heartbeat_age:.1f} s, node is not responding'
        elif data_age > self.data_timeout:
            level = 'ERROR'
            text = f'No data on /sensor_data for {data_age:.1f} s, but heartbeat is alive'
        elif rate < 0.75 * self.expected_rate:
            level = 'WARN'
            text = f'Data unstable: rate {rate:.1f} Hz (expected {self.expected_rate:.1f} Hz)'
        else:
            level = 'OK'
            text = f'System stable: heartbeat ok, data rate {rate:.1f} Hz'

        if level == 'ERROR':
            self.get_logger().error(text)
        elif level == 'WARN':
            self.get_logger().warn(text)
        else:
            self.get_logger().info(text)
        if level != self.state:
            if self.state is not None:
                self.get_logger().info(f'Status changed: {self.state} -> {level}')
            self.state = level

        status = String()
        status.data = f'{level}: {text}'
        self.status_pub.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = MonitorNode()
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
