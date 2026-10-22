import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Lab1Publisher(Node):

    def __init__(self):
        super().__init__('lab1_publisher')
        self.publisher_ = self.create_publisher(String, 'lab1_topic', 10)
        # Таймер з періодом 1 с — публікація 1 раз на секунду
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.count = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Hello from Lab1! Message #{self.count}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = Lab1Publisher()
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
