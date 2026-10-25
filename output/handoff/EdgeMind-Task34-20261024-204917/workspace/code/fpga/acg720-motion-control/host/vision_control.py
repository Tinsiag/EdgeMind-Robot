"""Vision firmware CLI. No hardware access until main() explicitly runs."""
import argparse

from car_control import CarController
from protocol import CLEAR_FAULT
from serial_control import open_serial


def main():
    parser = argparse.ArgumentParser(description='ACG720 视觉循线与测距调试')
    parser.add_argument('--port', required=True)
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('sense', 'stop', 'start-line', 'manual', 'clear-fault'):
        commands.add_parser(name)
    param = commands.add_parser('set-line-param')
    param.add_argument('id', type=int)
    param.add_argument('value', type=int)
    args = parser.parse_args()
    with open_serial(args.port) as port:
        car = CarController(port)
        # STOP remains usable with both old and new firmware, even if capability
        # probing is unsupported or perception has failed.
        if args.action == 'stop':
            car.stop()
            return 0
        if car.detect_capabilities() is None:
            raise RuntimeError('当前固件没有 EVM1 视觉能力回复')
        if args.action == 'sense':
            print(car.sensing())
        elif args.action == 'start-line':
            try:
                print(car.start_line())
            except BaseException:
                car.stop()
                raise
            print('循线已启动；关闭本串口不停止自主任务，停止请发送 stop 或按 S0。')
        elif args.action == 'manual':
            car.set_mode(False)
            print(car.sensing())
        elif args.action == 'clear-fault':
            car.stop()
            car.request(CLEAR_FAULT)
            print(car.sensing())
        else:
            car.stop()
            car.line_param(args.id, args.value)
            print(car.sensing())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
