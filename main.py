import pylontech
import time

#bat1 = pylontech.Pylontech(serial_port="/home/mrx/bat1")
bat2 = pylontech.Pylontech(serial_port="/home/usr/bat2")

bat2.scan_for_batteries(30)

# print(bat2.get_module_serial_number(34))
# print(bat2.get_module_serial_number(35))
# print(bat2.get_module_serial_number(36))
# print(bat2.get_module_serial_number(37))
# print(bat2.get_module_serial_number(38))


# print(bat1.get_module_serial_number(18))
# print(bat1.get_module_serial_number(19))
# print(bat1.get_module_serial_number(20))
# print(bat1.get_module_serial_number(21))
# print(bat1.get_module_serial_number(22))