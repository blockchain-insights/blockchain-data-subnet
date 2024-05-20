import os
import subprocess
import time
import argparse
import traceback
import bittensor as bt
import requests

from neurons.miners.blacklist_registry import BlacklistRegistryManager

SLEEP_TIME = 60

def get_external_ip():
    try:
        response = requests.get('https://api.ipify.org')
        return response.text
    except requests.RequestException:
        bt.logging.error("Failed to get external IP address.")
        return None

def main():
    bt.logging.info(f"Running ip blocker")

    my_ip = get_external_ip()

    while True:
        try:
            needs_refresh = False
            blacklist_registry = BlacklistRegistryManager().get_blacklist()
            for entry in blacklist_registry:
                if entry.ip_address == my_ip:
                    bt.logging.warning("⚠️ Skipping blocking of own IP address", ip_address = entry.ip_address)
                    continue

                # add to iptables, but only missing entries
                result = subprocess.run(["iptables", "-L", "INPUT", "-v", "-n"], capture_output=True, text=True)
                if entry.ip_address not in result.stdout:
                    subprocess.run(["iptables", "-I", "DOCKER", "1", "-s", entry.ip_address, "-j", "DROP"], check=True)
                    bt.logging.info("🚫💻 Blocked IP address", ip_address = entry.ip_address, hotkey = entry.hot_key)
                    needs_refresh = True
                else:
                    bt.logging.info("ℹ️ IP address already blocked", ip_address = entry.ip_address)

            if needs_refresh:
                subprocess.run(["iptables-save"], check=True)
                bt.logging.success(f"Refreshed ip tables")
            else:
                bt.logging.info(f"✅ No new blacklisted ips found")

            bt.logging.info(f"Sleeping", sleep_time_in_seconds = SLEEP_TIME)
            time.sleep(SLEEP_TIME)

        except KeyboardInterrupt:
            bt.logging.info("Ip blocker killed by keyboard interrupt.")
            break
        except Exception as e:
            bt.logging.error(error = traceback.format_exc())
            continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=15, help="The chain subnet uid.")
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)
    config = bt.config(parser)

    config.wallet.name = "miner"
    config.wallet.hotkey = "default"

    config.full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}/ip_blocker".format(
            config.logging.logging_dir,
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            "miner",
        )
    )
    if not os.path.exists(config.full_path):
        os.makedirs(config.full_path, exist_ok=True)

    bt.logging(config=config, logging_dir = config.full_path)

    main()