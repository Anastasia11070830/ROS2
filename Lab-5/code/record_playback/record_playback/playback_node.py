import csv
import os

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class PlaybackNode(Node):

    def __init__(self):
        super().__init__('playback_node')
        self.declare_parameter('file', '~/ros2_ws/data/route.csv')
        self.declare_parameter('speed', 1.0)        # 2.0 = відтворення вдвічі швидше
        self.declare_parameter('start_delay', 3.0)  # с до початку відтворення
        self.declare_parameter('end_hold', 1.0)     # с утримання останньої команди
        path = os.path.expanduser(self.get_parameter('file').value)
        self.speed = self.get_parameter('speed').value
        self.end_hold = self.get_parameter('end_hold').value
        start_delay = self.get_parameter('start_delay').value

        try:
            self.rows = self.load(path)
        except (OSError, KeyError, ValueError) as err:
            self.get_logger().error(f'Cannot read scenario {path}: {err}')
            raise SystemExit(1)
        if not self.rows:
            self.get_logger().error(f'Scenario {path} is empty')
            raise SystemExit(1)

        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.index = 0
        self.errors = []
        self.done = False
        self.start = self.now() + start_delay
        # Таймер 100 Гц перевіряє, чи настав час наступної команди
        self.timer = self.create_timer(0.01, self.tick)

        duration = self.rows[-1][0] / self.speed
        self.get_logger().info(
            f'Loaded {len(self.rows)} commands from {path}, duration {duration:.2f} s, '
            f'speed x{self.speed}. Starting in {start_delay} s')

    def now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def load(self, path):
        with open(path, newline='', encoding='utf-8') as f:
            return [(float(r['time']), float(r['linear_x']), float(r['angular_z']))
                    for r in csv.DictReader(f, skipinitialspace=True)]

    def send(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self.publisher_.publish(msg)

    def tick(self):
        elapsed = self.now() - self.start
        # Відправляємо всі команди, час яких уже настав, у порядку запису
        while self.index < len(self.rows):
            t, linear_x, angular_z = self.rows[self.index]
            planned = t / self.speed
            if elapsed < planned:
                return
            self.send(linear_x, angular_z)
            self.errors.append(elapsed - planned)
            self.index += 1
            self.get_logger().info(
                f'#{self.index}/{len(self.rows)} planned={planned:.3f} s, '
                f'actual={elapsed:.3f} s, linear.x={linear_x:.3f}, angular.z={angular_z:.3f}')

        # Усі команди відправлено: після утримання останньої надсилаємо Стоп
        if elapsed >= self.rows[-1][0] / self.speed + self.end_hold:
            self.send(0.0, 0.0)
            self.timer.cancel()
            self.done = True
            worst = max(abs(e) for e in self.errors) * 1000.0
            mean = sum(abs(e) for e in self.errors) / len(self.errors) * 1000.0
            self.get_logger().info(
                f'Playback finished: {len(self.errors)} commands sent, '
                f'timing error mean={mean:.1f} ms, max={worst:.1f} ms. Stop command sent')


def main(args=None):
    rclpy.init(args=args)
    node = PlaybackNode()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
