#!/usr/bin/python
import os
import time
import logging
from systemd.journal import JournalHandler

# Set debug mode based on the environment variable "DEBUG"
# The DEBUG variable can be set to "true", "True", or "1" (case-insensitive)
DEBUG = os.environ.get("DEBUG", "1").lower() in ["1", "true", "on"]

if DEBUG:
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            JournalHandler(
                SYSLOG_IDENTIFIER="fan_control"
            ),  # Send logs to systemd journal
            #       logging.FileHandler('/var/log/fan_controller.log'),  # Optional: Log to a file as well
        ],
    )


logger = logging.getLogger(__name__)

# Configuration variables
SLEEP_TIME = 5 if DEBUG else 15

MIN_STATE = 1  # if you set it to 0, the fan will switch off when temperature falls below LOWER_TEMP_THRESHOLD
LOWER_TEMP_THRESHOLD = 45.0
UPPER_TEMP_THRESHOLD = 65.0
MIN_DELTA = 0.01  # Minimum temperature change to trigger speed change

THERMAL_DIR = "/sys/class/thermal"
DEVICE_TYPE_PWM_FAN = "pwm-fan"
THERMAL_ZONE_NAME = "thermal_zone"
DEVICE_NAME_COOLING = "cooling_device"
FILE_NAME_CUR_STATE = "cur_state"


def format_temp(value):
    res = f"{value:.2f}°C"
    return res


def get_fan_device():
    for device in os.listdir(THERMAL_DIR):
        if device.startswith(DEVICE_NAME_COOLING):
            dev_path = os.path.join(THERMAL_DIR, device)
            type_file = os.path.join(dev_path, "type")
            try:
                with open(type_file, "r") as f:
                    if DEVICE_TYPE_PWM_FAN in f.read().strip():
                        return dev_path
            except Exception as e:
                logger.error(f"Error while getting fan device: {e}")
    return None


def get_fan_speed(device):
    try:
        cur_state_file = os.path.join(device, FILE_NAME_CUR_STATE)
        with open(cur_state_file, "r") as f:
            res = int(f.read().strip())
            return res
    except Exception as e:
        logger.error(f"Error getting fan speed: {e}")
    return 0


def set_fan_speed(device, speed):
    try:
        logger.debug(f"setting fan speed to {speed}")
        cur_state_file = os.path.join(device, FILE_NAME_CUR_STATE)
        with open(cur_state_file, "w") as f:
            f.write(str(speed))
        return True
    except Exception as e:
        logger.error(f"Error setting fan speed: {e}")
    return False


def get_temperature_slots():
    """
    Creates predefined temperature thresholds and corresponding fan states.

    Returns:
        list of tuples: Each tuple contains (fan_state, temperature_threshold)
    """
    res = None
    max_state = 0
    fan_device = get_fan_device()
    try:
        int(open(f"{fan_device}/max_state", "r").read().strip())
        with open(f"{fan_device}/max_state", "r") as f:
            max_state = int(f.read().strip())
    except Exception as e:
        logger.error(f"Error while getting temperature slots: {e}")
        max_state = 0
        pass

    if max_state <= 0:
        logger.error(f"max_state could not be determined for {fan_device}")
    else:
        temperature_range = UPPER_TEMP_THRESHOLD - LOWER_TEMP_THRESHOLD
        slots = max_state
        step = temperature_range / (slots - 1)
        res = [(x + MIN_STATE, x * step + LOWER_TEMP_THRESHOLD) for x in range(slots)]
    return res


def adjust_speed_based_on_temperature(current_temp):
    """
    Adjusts the fan speed based on the current temperature.

    Args:
        current_temp (float): The current CPU temperature.

    Returns:
        None
    """
    temperature_slots = get_temperature_slots()
    desired_slot = [
        (state, temp) for state, temp in temperature_slots if current_temp >= temp
    ]
    if desired_slot:
        desired_slot = desired_slot[-1]
    elif current_temp <= LOWER_TEMP_THRESHOLD:
        desired_slot = temperature_slots[0]
    else:
        desired_slot = temperature_slots[-1]

    logger.debug(
        f"desired_slot (current_temp: {current_temp}): {desired_slot} (out of {temperature_slots})"
    )

    desired_state, _ = desired_slot

    # Update fan speed only if needed
    fan_device = get_fan_device()
    if get_fan_speed(fan_device) != desired_state:
        logger.info(
            f"fan speed needs to be changed to: {desired_state} (current_temp: {format_temp(current_temp)} | slot: {desired_slot})"
        )
        set_fan_speed(fan_device, desired_state)


def get_current_temp():
    """
    Reads the CPU temperature from system files.

    Returns:
        float: The maximum CPU temperature (in degrees Celsius) or 0 if no valid readings are found.

    Raises:
        Exception: If an error occurs while reading temperature data.
    """
    temps = []
    try:
        for zone in os.listdir(THERMAL_DIR):
            if zone.startswith(THERMAL_ZONE_NAME):
                temp_file = os.path.join(THERMAL_DIR, zone, "temp")
                if os.path.exists(temp_file):
                    with open(temp_file, "r") as f:
                        temp = float(f.read().strip()) / 1000.0
                        temps.append(temp)
    except Exception as e:
        logger.error(f"Error while getting current temperature: {e}")
    return max(temps) if temps else 0.0


def adjust_fan():
    current_temp = get_current_temp()
    adjust_speed_based_on_temperature(current_temp)


def main():
    """Main function to control fan speed."""

    logger.info("PWM Fan control service")

    fan_device = get_fan_device()
    if not fan_device:
        logger.error("No PWM fan device found")
        return

    logger.info(f"Fan device: {fan_device}")
    logger.info("Temperature slots:")
    logger.info(
        "    * when temperature reaches the threshold of a slot, the fan state is set to the corresponding fan_state value)"
    )
    logger.info(f'    * when temperature falls below LOWER_TEMP_THRESHOLD (i.e. {format_temp(LOWER_TEMP_THRESHOLD)}), state is set to MIN_STATE (i.e. {MIN_STATE})')
    for fan_state, temperature_threshold in get_temperature_slots():
        logger.info(f"    {format_temp(temperature_threshold):4}: {fan_state}")

    while True:
        adjust_fan()
        logger.debug(f"sleeping for {SLEEP_TIME} seconds")
        time.sleep(SLEEP_TIME)  # Check temperature after a delay


def test():
    for x in range(30):
        current_temp = LOWER_TEMP_THRESHOLD - 5 + (x * 1.0)
        adjust_speed_based_on_temperature(current_temp)


if __name__ == "__main__":
    logger.info("Starting fan controller service")
    try:
        # test()
        main()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
