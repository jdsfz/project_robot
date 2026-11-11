"""Raspberry Pi adapter: turn common wheel speeds into Raspbot commands."""


class PiOutput:
    def __init__(self):
        from Raspbot_Lib import Raspbot
        self.bot = Raspbot()

    def set_wheels(self, left: int, right: int) -> None:
        # IDs follow the user's manual.py example.
        for motor_id, speed in ((1, left), (3, left), (2, right), (4, right)):
            self.bot.Ctrl_Muto(motor_id, speed)

    def close(self) -> None:
        self.set_wheels(0, 0)
