#!/usr/bin/python

import argparse
import os

from fan_control import get_fan_device, get_fan_speed, set_fan_speed, logger


def main():
    parser = argparse.ArgumentParser(description="Thermal Cooling Device Control")
    parser.add_argument(
        "--desired-state", nargs="?", default=None, help="Desired cooling device state"
    )
    args = parser.parse_args()

    fan_device = get_fan_device()
    if not fan_device:
        logger.error("No PWM fan device found")
        return

    logger.info(f"Fan device: {fan_device}")

    try:
        max_state_file = os.path.join(fan_device, "max_state")
        max_state = int(open(max_state_file).read().strip())

        logger.info(f"Maximum state allowed: {max_state}")

        desired_state = int(args.desired_state) if args.desired_state else None
        if desired_state is None:
            current_state = get_fan_speed(fan_device)
            logger.info(f"Current state is set to: {current_state}")
        else:
            if desired_state > max_state:
                logger.error(
                    f"Error: Desired state {desired_state} exceeds the maximum allowed state {max_state}."
                )
                return
            set_fan_speed(fan_device, desired_state)
            logger.info(f"Desired state set to: {desired_state}")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()
