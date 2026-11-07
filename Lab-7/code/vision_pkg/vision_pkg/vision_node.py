import os
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


class VisionNode(Node):

    def __init__(self):
        super().__init__('vision_node')
        self.declare_parameter('blur_kernel', 7)         # непарне число
        self.declare_parameter('threshold', 140)         # поріг бінаризації 0..255
        self.declare_parameter('canny_low', 60)
        self.declare_parameter('canny_high', 160)
        self.declare_parameter('motion_threshold', 20)   # мінімальна зміна яскравості
        self.declare_parameter('motion_min_area', 400)   # мінімальна площа області руху
        self.declare_parameter('show', True)             # показувати вікно OpenCV
        self.declare_parameter('results_dir', '~/ros2_ws/results')

        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            Image, '/camera/image', self.image_callback, 10)
        self.processed_pub = self.create_publisher(Image, '/camera/image_processed', 10)

        self.prev_blur = None
        self.show = self.get_parameter('show').value
        self.results_dir = os.path.expanduser(self.get_parameter('results_dir').value)
        self.save_count = 0
        self.last = None
        self.quit = False
        self.frames = 0
        self.fps_start = time.time()

        self.get_logger().info(
            'Vision Node started: waiting for images on /camera/image '
            "(keys in the window: 's' = save, 'q' = quit)")

    def param(self, name):
        return self.get_parameter(name).value

    def process(self, frame):
        # 1. Перетворення в градації сірого
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 2. Розмиття за Гауссом (ядро має бути непарним)
        kernel = int(self.param('blur_kernel')) | 1
        blur = cv2.GaussianBlur(gray, (kernel, kernel), 0)

        # 3. Порогова обробка: яскравіше за поріг стає білим, інше чорним
        _, binary = cv2.threshold(blur, int(self.param('threshold')), 255, cv2.THRESH_BINARY)

        # 4. Детекція країв (Canny)
        edges = cv2.Canny(blur, int(self.param('canny_low')), int(self.param('canny_high')))

        # 5. Детекція руху: різниця поточного й попереднього кадрів
        if self.prev_blur is None:
            mask = np.zeros_like(gray)
        else:
            diff = cv2.absdiff(self.prev_blur, blur)
            _, mask = cv2.threshold(diff, int(self.param('motion_threshold')), 255,
                                    cv2.THRESH_BINARY)
            mask = cv2.dilate(mask, None, iterations=2)
        self.prev_blur = blur

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = self.param('motion_min_area')
        boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > min_area]
        motion = frame.copy()
        for x, y, w, h in boxes:
            cv2.rectangle(motion, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return gray, blur, binary, edges, motion, boxes

    def make_mosaic(self, frame, gray, blur, binary, edges, motion):
        def tile(image, label):
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            image = cv2.resize(image, (320, 240))
            cv2.putText(image, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            return image

        top = np.hstack([tile(frame, 'Original'), tile(gray, 'Grayscale'),
                         tile(blur, 'Gaussian blur')])
        bottom = np.hstack([tile(binary, 'Threshold'), tile(edges, 'Edges (Canny)'),
                            tile(motion, 'Motion')])
        return np.vstack([top, bottom])

    def image_callback(self, msg):
        start = time.time()
        # cv_bridge: ROS Image -> масив OpenCV (BGR)
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        gray, blur, binary, edges, motion, boxes = self.process(frame)
        self.last = (frame, gray, blur, binary, edges, motion)

        # Оброблене зображення також публікується в топік для rqt_image_view
        out = self.bridge.cv2_to_imgmsg(binary, encoding='mono8')
        out.header = msg.header
        self.processed_pub.publish(out)

        if boxes:
            self.get_logger().info(
                f'Motion detected: {len(boxes)} region(s)', throttle_duration_sec=1.0)

        self.frames += 1
        elapsed = time.time() - self.fps_start
        if elapsed >= 2.0:
            self.get_logger().info(
                f'Frames: {self.frames}, input {self.frames / elapsed:.1f} fps, '
                f'processing {(time.time() - start) * 1000:.1f} ms/frame, '
                f'frame {frame.shape[1]}x{frame.shape[0]}')
            self.frames = 0
            self.fps_start = time.time()

        if self.show:
            self.display()

    def display(self):
        mosaic = self.make_mosaic(*self.last)
        try:
            cv2.imshow('Vision', mosaic)
            key = cv2.waitKey(1) & 0xFF
        except cv2.error as err:
            self.get_logger().error(f'Cannot show window ({err}); continuing without display')
            self.show = False
            return
        if key == ord('s'):
            self.save(mosaic)
        elif key == ord('q'):
            self.quit = True

    def save(self, mosaic):
        os.makedirs(self.results_dir, exist_ok=True)
        self.save_count += 1
        names = ['original', 'gray', 'blur', 'threshold', 'edges', 'motion']
        for name, image in zip(names, self.last):
            cv2.imwrite(os.path.join(self.results_dir, f'{self.save_count:02d}_{name}.png'), image)
        cv2.imwrite(os.path.join(self.results_dir, f'{self.save_count:02d}_mosaic.png'), mosaic)
        self.get_logger().info(f'Saved snapshot #{self.save_count} to {self.results_dir}')


def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    try:
        while rclpy.ok() and not node.quit:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
