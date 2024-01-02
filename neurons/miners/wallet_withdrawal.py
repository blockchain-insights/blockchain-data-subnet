import subprocess
import pexpect
import time
from dotenv import load_dotenv
import os

load_dotenv()
password = os.getenv('WALLET_PASSWORD')

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        return None

def parse_wallets(output):
    lines = output.split("\n")
    wallets = []
    current_wallet = None
    for line in lines:
        # Check for wallet lines
        if any(keyword in line for keyword in ['owner', 'miner', 'validator']):
            # Extract wallet name
            current_wallet = line.split('(')[1].split(')')[0].strip()
        # Check for hotkey lines and make sure we have a current wallet
        elif '└──' in line and current_wallet is not None:
            # Extract hotkey
            hotkey_parts = line.strip().split('(')
            if len(hotkey_parts) > 1:
                hotkey = hotkey_parts[1].split(')')[0].strip()
                wallets.append((current_wallet, hotkey))
    return wallets


def parse_metagraph_output(output):
    lines = output.split("\n")
    miners = []
    for line in lines[7:]:
        if line.strip() == '':
            break
        data = line.split()
        if '.' in data[12]:
            miners.append({"HOTKEY": data[13], "ACTIVE": data[11]})
    return miners

def register_miner(wallet_name, hotkey):
    command = f"btcli subnet register --netuid 15 --subtensor.network finney --wallet.name {wallet_name} --wallet.hotkey {hotkey}"
    child = pexpect.spawn(command, encoding='utf-8')
    child.expect("Do you want to continue? \[y/n\] \(n\):")
    child.sendline('y')
    child.expect("Enter password to unlock key:")
    child.sendline(password)
    child.expect(" to register on subnet:15? \[y/n\]:")
    child.sendline('y')
    output = child.read()
    print(output)
    return 'TooManyRegistrationsThisInterval' not in output

def main():
    #while True:
        # Retrieve wallet list and parse it
        wallet_list_command = "btcli w list --subtensor.network finney"
        wallet_list_output = execute_command(wallet_list_command)
        wallets = parse_wallets(wallet_list_output)
        print("Parsing part done..")
        # Retrieve metagraph data and parse it
        #metagraph_command = "btcli subnet metagraph --netuid 15 --subtensor.network finney"
        #metagraph_output = execute_command(metagraph_command)
        #miners = parse_metagraph_output(metagraph_output)

        # Create a set of active hotkeys
        #active_hotkeys = set(miner['HOTKEY'] for miner in miners if miner['ACTIVE'] == '1')

        # Attempt to register inactive hotkeys
        for wallet_name, hotkey in wallets:
            print(f"Wallet {wallet_name} has the following hotkey: {hotkey}")
            #if hotkey not in active_hotkeys:
            #    print(f"Trying to register hotkey {hotkey} of wallet {wallet_name}...")
           #     if register_miner(wallet_name, hotkey):
           #         print(f"Successfully registered {hotkey}.")
           #     else:
           ##         print(f"Failed to register {hotkey}. Waiting for 3 minutes before next attempt.")
           #         time.sleep(180)

        #print("Completed a cycle. Waiting for 10 minutes before next cycle.")
        #time.sleep(600)  # Sleep for 10 minutes

if __name__ == "__main__":
    main()
