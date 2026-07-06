#!/usr/bin/env python3
import argparse
import json
import os
import signal
import sys
import time


def read_netdev():
    rx_bytes = 0
    tx_bytes = 0
    interfaces = {}

    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        for line in f.readlines()[2:]:
            if ":" not in line:
                continue
            name, data = line.split(":", 1)
            name = name.strip()
            if name == "lo":
                continue
            fields = data.split()
            if len(fields) < 16:
                continue
            iface_rx = int(fields[0])
            iface_tx = int(fields[8])
            interfaces[name] = {"rx_bytes": iface_rx, "tx_bytes": iface_tx}
            rx_bytes += iface_rx
            tx_bytes += iface_tx

    return {
        "rx_bytes_total": rx_bytes,
        "tx_bytes_total": tx_bytes,
        "interfaces": interfaces,
    }


def atomic_write_json(path, data):
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def absolute_path(path):
    return os.path.abspath(path)


def build_record(start, current, started_at, pid=None, running=False):
    elapsed = max(0.0, time.time() - started_at)
    iface_tx_delta = {
        name: max(0, current["interfaces"].get(name, {}).get("tx_bytes", 0)
                  - start["interfaces"].get(name, {}).get("tx_bytes", 0))
        for name in current["interfaces"]
    }
    return {
        "pid": pid,
        "running": running,
        "started_at": started_at,
        "updated_at": time.time(),
        "elapsed_seconds": elapsed,
        "start_rx_bytes": start["rx_bytes_total"],
        "start_tx_bytes": start["tx_bytes_total"],
        "current_rx_bytes": current["rx_bytes_total"],
        "current_tx_bytes": current["tx_bytes_total"],
        "recv_bytes": max(0, current["rx_bytes_total"] - start["rx_bytes_total"]),
        "sent_bytes": max(0, current["tx_bytes_total"] - start["tx_bytes_total"]),
        "interfaces": current["interfaces"],
        "iface_tx_delta": iface_tx_delta,
    }


def daemonize():
    pid = os.fork()
    if pid > 0:
        return pid

    os.setsid()
    second_pid = os.fork()
    if second_pid > 0:
        os._exit(0)

    os.chdir("/")
    os.umask(0)
    with open(os.devnull, "rb", 0) as devnull_in:
        os.dup2(devnull_in.fileno(), sys.stdin.fileno())
    with open(os.devnull, "ab", 0) as devnull_out:
        os.dup2(devnull_out.fileno(), sys.stdout.fileno())
        os.dup2(devnull_out.fileno(), sys.stderr.fileno())
    return 0


def monitor(output_path, interval):
    started_at = time.time()
    start = read_netdev()
    stop = {"requested": False}

    def handle_stop(_signum, _frame):
        stop["requested"] = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    while not stop["requested"]:
        current = read_netdev()
        record = build_record(start, current, started_at, pid=os.getpid(), running=True)
        atomic_write_json(output_path, record)
        time.sleep(interval)

    current = read_netdev()
    record = build_record(start, current, started_at, pid=os.getpid(), running=False)
    atomic_write_json(output_path, record)


def start_monitor(output_path, interval):
    parent_child_pid = daemonize()
    if parent_child_pid > 0:
        return 0

    monitor(output_path, interval)
    return 0


def stop_monitor(input_path, output_path):
    data = load_json(input_path)
    pid = data.get("pid")

    if isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        time.sleep(0.2)

    final_data = load_json(input_path)
    if final_data:
        final_data["running"] = False
        final_data["ended_at"] = time.time()
        final_data["updated_at"] = final_data["ended_at"]
        atomic_write_json(output_path, final_data)
    else:
        current = read_netdev()
        now = time.time()
        record = build_record(current, current, now, pid=None, running=False)
        record["ended_at"] = now
        atomic_write_json(output_path, record)
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Record namespace interface byte counters.")
    parser.add_argument("-s", "--start", action="store_true", help="start a background counter monitor")
    parser.add_argument("-e", "--end", action="store_true", help="stop a background counter monitor")
    parser.add_argument("-i", "--input", help="input JSON path for --end")
    parser.add_argument("-o", "--output", required=True, help="output JSON path")
    parser.add_argument("--interval", type=float, default=1.0, help="sampling interval in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.start == args.end:
        print("Use exactly one of --start or --end.", file=sys.stderr)
        return 2
    if args.end and not args.input:
        print("--end requires --input.", file=sys.stderr)
        return 2
    if args.interval <= 0:
        print("--interval must be positive.", file=sys.stderr)
        return 2

    output_path = absolute_path(args.output)
    input_path = absolute_path(args.input) if args.input else None

    if args.start:
        return start_monitor(output_path, args.interval)
    return stop_monitor(input_path, output_path)


if __name__ == "__main__":
    raise SystemExit(main())
