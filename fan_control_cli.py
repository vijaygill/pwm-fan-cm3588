#!/usr/bin/python

import argparse
import os

from fan_control_service import get_fan_device, get_fan_speed, set_fan_speed, logger

def main():
    parser = argparse.ArgumentParser(description="Thermal Cooling Device Control")
    parser.add_argument("desired_state", nargs='?', default=None, help="Desired cooling device state")
    args = parser.parse_args()

    fan_device = get_fan_device()
    if not fan_device:
        logger.error("No PWM fan device found")
        return

    logger.info(f"Fan device: {fan_device}")

    try:
        max_state_file = os.path.join(fan_device, "max_state")
        cur_state_file = os.path.join(fan_device, "cur_state")
        trans_table_file = os.path.join(fan_device, "stats/trans_table")
        time_in_state_ms_file = os.path.join(fan_device, "stats/time_in_state_ms")

        max_state = int(open(max_state_file).read().strip())
        cur_state = int(open(cur_state_file).read().strip())

        logger.info(f"Maximum state allowed: {max_state}")

        desired_state = int(args.desired_state) if args.desired_state else None
        if desired_state:
            if desired_state > max_state:
                logger.error(f"Error: Desired state {desired_state} exceeds the maximum allowed state {max_state}.")
                return
            set_fan_speed(fan_device, args.desired_state)
            logger.info(f"Desired state set to: {args.desired_state}")
        else:
            current_state = get_fan_speed(fan_device)
            logger.info(f"Current state is set to: {current_state}")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()
