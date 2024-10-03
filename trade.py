import asyncio
import json
import base64
import struct
import base58
import hashlib
import websockets
import os
import argparse
from datetime import datetime

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction

from spl.token.instructions import get_associated_token_address
import spl.token.instructions as spl_token

from config import *

# Import functions from buy.py
from buy import get_pump_curve_state, calculate_pump_curve_price, buy_token, listen_for_create_transaction

# Import functions from sell.py
from sell import sell_token

from analytics import HolderCountAnalyzer

import builtins
import time

# Save the original print function
original_print = builtins.print

# Define a new print function with timestamps
def print(*args, **kwargs):
    original_print(time.strftime("%Y-%m-%d %H:%M:%S"), *args, **kwargs)


def log_trade(action, token_data, price, tx_hash):
    os.makedirs("trades", exist_ok=True)
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "token_address": token_data['mint'],
        "price": price,
        "tx_hash": tx_hash
    }
    with open("trades/trades.log", 'a') as log_file:
        json.dump(log_entry, log_file)
        log_file.write("\n")

async def trade(websocket=None, match_string=None, bro_address=None, marry_mode=False, yolo_mode=False):
    if websocket is None:
        async with websockets.connect(WSS_ENDPOINT) as websocket:
            await _trade(websocket, match_string, bro_address, marry_mode, yolo_mode)
    else:
        await _trade(websocket, match_string, bro_address, marry_mode, yolo_mode)

async def _trade(websocket, match_string=None, bro_address=None, marry_mode=False, yolo_mode=False):
    while True:
        print("Waiting for a new token creation...")
        token_data = await listen_for_create_transaction(websocket)
        print("New token created:")
        print(json.dumps(token_data, indent=2))

        if match_string and not (match_string.lower() in token_data['name'].lower() or match_string.lower() in token_data['symbol'].lower()):
            print(f"Token does not match the criteria '{match_string}'. Skipping...")
            if not yolo_mode:
                break
            continue

        if bro_address and token_data['user'] != bro_address:
            print(f"Token not created by the specified user '{bro_address}'. Skipping...")
            if not yolo_mode:
                break
            continue

        # Save token information to a .txt file in the "trades" directory
        mint_address = token_data['mint']
        os.makedirs("trades", exist_ok=True)
        file_name = os.path.join("trades", f"{mint_address}.txt")
        with open(file_name, 'w') as file:
            file.write(json.dumps(token_data, indent=2))
        print(f"Token information saved to {file_name}")

        print("Waiting for 15 seconds for things to stabilize...")
        await asyncio.sleep(15)

        mint = Pubkey.from_string(token_data['mint'])
        bonding_curve = Pubkey.from_string(token_data['bondingCurve'])
        associated_bonding_curve = Pubkey.from_string(token_data['associatedBondingCurve'])

        # Fetch the token price
        async with AsyncClient(RPC_ENDPOINT) as client:
            curve_state = await get_pump_curve_state(client, bonding_curve)
            token_price_sol = calculate_pump_curve_price(curve_state)

        print(f"Bonding curve address: {bonding_curve}")
        print(f"Token price: {token_price_sol:.10f} SOL")
        print(f"Buying {BUY_AMOUNT:.6f} SOL worth of the new token with {BUY_SLIPPAGE*100:.1f}% slippage tolerance...")
        buy_tx_hash = await buy_token(mint, bonding_curve, associated_bonding_curve, BUY_AMOUNT, BUY_SLIPPAGE)
        if buy_tx_hash:
            log_trade("buy", token_data, token_price_sol, str(buy_tx_hash))
        else:
            print("Buy transaction failed.")

        if not marry_mode:
            print("Waiting for 20 seconds before selling...")
            await asyncio.sleep(20)

            print(f"Selling tokens with {SELL_SLIPPAGE*100:.1f}% slippage tolerance...")
            sell_tx_hash = await sell_token(mint, bonding_curve, associated_bonding_curve, SELL_SLIPPAGE)
            if sell_tx_hash:
                log_trade("sell", token_data, token_price_sol, str(sell_tx_hash))
            else:
                print("Sell transaction failed or no tokens to sell.")
        else:
            print("Marry mode enabled. Skipping sell operation.")

        if not yolo_mode:
            break
        
# Listen for new token creation
async def monitorTokenCreation():
        while True:
            async with websockets.connect(WSS_ENDPOINT) as websocket:
                print("Waiting for a new token creation...")
                token_data = await listen_for_create_transaction(websocket)
                print("New token created:")
                print(json.dumps(token_data, indent=2))
                
                # Get number of async tasks running
                tasks = asyncio.all_tasks()
                print(f"Number of tasks running: {len(tasks)}")
                
                # If the number of tasks is less than 200, start a new task to analyze the token
                if len(tasks) < 200:
                    # Create a background task to fetch holder count without blocking
                    print("Analyser started for mint address: ", token_data['mint'])
                    asyncio.create_task(analyser(token_data))
                else:
                    print("Too many tasks running. Skipping analyser...")
                
# Analyser function
async def analyser(token_data):
    try:
        async with AsyncClient(RPC_ENDPOINT) as client:
            # For HolderCountAnalyzer
            holder_count_analyzer = HolderCountAnalyzer(client, token_data['user'], token_data['bondingCurve'])
            print("Waiting for 5 seconds before fetching holder count...")
            # Look for the top holders of the new token
            currentEpochTime = int(time.time())
            for i in range(12 * 5): # 5 minutes
                iterationStartTime = time.time()
                proceed = await holder_count_analyzer.make_decision(Pubkey.from_string(token_data['mint']), holder_threshold=35, dev_threshold=1, lp_threshold_lower=60, lp_threshold_upper=80, startEpochTime=currentEpochTime)
                
                # Iteration time spent
                print(f"Iteration {i+1} for mint address {token_data['mint']} completed. Time spent: {time.time() - iterationStartTime}")
                if not proceed:
                    break
                await asyncio.sleep(5)
            
            # TODO: For Other Analyzers
            
    except Exception as e:
        print(f"Error fetching holder count: {e}")

async def main(yolo_mode=False, match_string=None, bro_address=None, marry_mode=False, monitor_mode=True):
    if monitor_mode:
        while True:
            try:
                await monitorTokenCreation()
            except Exception as e:
                print(f"An error occurred: {e}")
        
    if yolo_mode:
        while True:
            try:
                async with websockets.connect(WSS_ENDPOINT) as websocket:
                    while True:
                        try:
                            await trade(websocket, match_string, bro_address, marry_mode, yolo_mode)
                        except websockets.exceptions.ConnectionClosed:
                            print("WebSocket connection closed. Reconnecting...")
                            break
                        except Exception as e:
                            print(f"An error occurred: {e}")
                        print("Waiting for 5 seconds before looking for the next token...")
                        await asyncio.sleep(5)
            except Exception as e:
                print(f"Connection error: {e}")
                print("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    else:
        # For non-YOLO mode, create a websocket connection and close it after one trade
        async with websockets.connect(WSS_ENDPOINT) as websocket:
            await trade(websocket, match_string, bro_address, marry_mode, yolo_mode)

async def ping_websocket(websocket):
    while True:
        try:
            await websocket.ping()
            await asyncio.sleep(20) # Send a ping every 20 seconds
        except:
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade tokens on Solana.")
    parser.add_argument("--yolo", action="store_true", help="Run in YOLO mode (continuous trading)")
    parser.add_argument("--match", type=str, help="Only trade tokens with names or symbols matching this string")
    parser.add_argument("--bro", type=str, help="Only trade tokens created by this user address")
    parser.add_argument("--marry", action="store_true", help="Only buy tokens, skip selling")
    parser.add_argument("--monitor", action="store_true", help="Monitor token creation without trading")
    args = parser.parse_args()
    asyncio.run(main(yolo_mode=args.yolo, match_string=args.match, bro_address=args.bro, marry_mode=args.marry))