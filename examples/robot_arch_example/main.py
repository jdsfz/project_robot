"""Entry point: select the hardware/simulator output here."""

MODE = "gazebo"  # Change to "pi" on the Raspberry Pi.

from controller import run

if MODE == "pi":
    from pi_output import PiOutput
    output = PiOutput()
elif MODE == "gazebo":
    from gazebo_output import GazeboOutput
    output = GazeboOutput()
else:
    raise ValueError('MODE must be "pi" or "gazebo"')

try:
    run(output)
finally:
    output.close()
