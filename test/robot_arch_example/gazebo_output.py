"""Gazebo adapter: turn common wheel speeds into ROS 2 cmd_vel messages."""


class GazeboOutput:
    # Example conversion constants. Tune these for the robot model.
    METERS_PER_SPEED_POINT = 0.01
    RADIANS_PER_SPEED_DIFFERENCE = 0.02

    def __init__(self):
        import rclpy
        from geometry_msgs.msg import Twist
        from rclpy.node import Node

        self.rclpy = rclpy
        self.Twist = Twist
        rclpy.init()
        self.node = Node("robot_arch_example")
        self.publisher = self.node.create_publisher(Twist, "/cmd_vel", 10)

    def set_wheels(self, left: int, right: int) -> None:
        msg = self.Twist()
        msg.linear.x = (left + right) / 2 * self.METERS_PER_SPEED_POINT
        msg.angular.z = (right - left) / 100 * self.RADIANS_PER_SPEED_DIFFERENCE
        self.publisher.publish(msg)

    def close(self) -> None:
        self.set_wheels(0, 0)
        self.node.destroy_node()
        if self.rclpy.ok():
            self.rclpy.shutdown()
