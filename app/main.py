import argparse

from managers.get_schedules import ScheduleManager
from managers.set_heaters import HeaterManager

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="Manage your heaters")
    parser.add_argument("--configs", required=False, default="configs/main.yaml", help="Set heaters config file")
    parser.add_argument("--dry-run", default=False, action='store_true', help="Run as dry run")
    parser.add_argument("--mode", default="all", choices=["all", "set_heaters", "get_schedules"], help="Run specific mode")
    args = parser.parse_args()

    if args.mode == "all" or args.mode == "get_schedules":
        schedule_manager = ScheduleManager(args.configs)
        schedule_manager.run()

    if args.mode == "all" or args.mode == "set_heaters":
        heater_manager = HeaterManager(args.configs)
        heater_manager.dry_run = args.dry_run
        heater_manager.run()
