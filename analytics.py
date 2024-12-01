import asyncio
import struct
import requests
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from typing import Dict, List, Optional
from config import *
from solana.rpc.types import MemcmpOpts

import builtins
import time

# Save the original print function
original_print = builtins.print

# Define a new print function with timestamps
def print(*args, **kwargs):
    original_print(time.strftime("%Y-%m-%d %H:%M:%S"), *args, **kwargs)

# Constants
LAMPORTS_PER_SOL = 1_000_000_000
TOKEN_DECIMALS = 6
SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"  # SPL Token Program ID
CONVERT_TO_OWNER_WALLET_ADDRESSES = True # TODO: BUG WHEN SET TO FALSE: Set to False to convert token account addresses to owner wallet addresses, if needed to save API calls, and faster processing

class HolderCountAnalyzer:
    def __init__(self, client: AsyncClient, dev_wallet: Optional[str] = None, bonding_curve: Optional[str] = None):
        self.client = client
        self.dev_wallet_pubkey = Pubkey.from_string(dev_wallet) if dev_wallet else None
        self.bonding_curve_pubkey = Pubkey.from_string(bonding_curve) if bonding_curve else None

    async def get_holder_count(self, mint: Pubkey) -> int:
        """
        Fetches the number of unique holders for the given mint address.

        Args:
            mint (Pubkey): The mint address of the token.

        Returns:
            int: Number of unique holders.
        """
        url = f"https://mainnet.helius-rpc.com/?api-key={API_KEY_HELIUS}"
        page = 1
        all_owners = set()

        while True:
            response = requests.post(url, headers={"Content-Type": "application/json"}, json={
                "jsonrpc": "2.0",
                "method": "getTokenAccounts",
                "id": "helius-test",
                "params": {
                    "page": page,
                    "limit": 1000,
                    "displayOptions": {},
                    "mint": str(mint)
                }
            })

            data = response.json()

            # Pagination logic
            if 'result' not in data or len(data['result']['token_accounts']) == 0:
                print(f"No more results. Total pages: {page - 1}")
                break

            print(f"Processing results from page {page}")
            for account in data['result']['token_accounts']:
                all_owners.add(account['owner'])

            page += 1

        # Output the list of unique owners
        # print("Unique Token Holders:")
        # for owner in all_owners:
        #     print(owner)
            
        return len(all_owners)
        
    async def get_token_supply(self, mint: Pubkey) -> int:
        """
        Retrieves the total supply of the token.

        Args:
            mint (Pubkey): The mint address of the token.

        Returns:
            int: Total token supply. Returns 0 if unable to fetch.
        """
        try:
            response = await self.client.get_token_supply(mint)
            if response.value is None:
                print("Failed to fetch token supply: No value in response.")
                return 0
            supply = int(response.value.amount)
            print(f"Total token supply: {supply}")
            return supply
        except Exception as e:
            print(f"Exception in get_token_supply: {e}")
            return 0

    async def get_owner_wallet(self, token_account: Pubkey) -> Optional[str]:
        """
        Retrieves the owner wallet address for a given token account.

        Args:
            token_account (Pubkey): The token account address.

        Returns:
            Optional[str]: Owner wallet address if successful, else None.
        """
        try:
            response = await self.client.get_account_info(token_account)
            if response.value is None:
                print(f"Failed to fetch account info for {str(token_account)}: No data found.")
                return None

            # Verify that the account is owned by the SPL Token program
            if str(response.value.owner) != SPL_TOKEN_PROGRAM_ID:
                print(f"Account {str(token_account)} is not owned by the SPL Token program.")
                return None

            account_data = response.value.data

            if not isinstance(account_data, bytes):
                print(f"Invalid account data format for {str(token_account)}.")
                return None

            if len(account_data) < 64:
                print(f"Account data too short for {str(token_account)}.")
                return None

            # SPL Token Account Layout:
            # Bytes 0-31: Mint (Pubkey)
            # Bytes 32-63: Owner (Pubkey)
            # Bytes 64-71: Amount (u64)
            # ... (other fields are ignored for this purpose)

            # Extract owner (bytes 32 to 64)
            owner_bytes = account_data[32:64]
            owner_pubkey = Pubkey(owner_bytes)
            return str(owner_pubkey)
        except Exception as e:
            print(f"Exception in get_owner_wallet for {str(token_account)}: {e}")
            return None

    async def get_top_holders(self, mint: Pubkey, top_n: int = 20) -> List[Dict]:
        """
        Retrieves the top N token holders based on token balance.

        Args:
            mint (Pubkey): The mint address of the token.
            top_n (int, optional): Number of top holders to retrieve. Defaults to 20.

        Returns:
            List[Dict]: A list of dictionaries containing holder wallet addresses, token amounts, and holding percentages.
        """
        try:
            # Fetch the largest token accounts
            response = await self.client.get_token_largest_accounts(mint)
            
            if response.value is None:
                print("Failed to fetch largest accounts: No value in response.")
                return []
            
            largest_accounts = response.value
            top_holders = []
            
            # Fetch total supply to calculate percentages
            # total_supply = await self.get_token_supply(mint)
            total_supply = 1000000000000000 # This is constant for all PUMPFUN tokens
            if total_supply == 0:
                print("Total supply is zero. Cannot calculate percentages.")
                return []
            
            print(f"\nFetching top {top_n} holders for mint {str(mint)}\n")
            
            # Limit to top_n
            accounts_to_process = largest_accounts[:top_n]
            
            if CONVERT_TO_OWNER_WALLET_ADDRESSES:
                tasks = []
                for account in accounts_to_process:
                    token_account_pubkey = account.address
                    tasks.append(self.get_owner_wallet(token_account_pubkey))
                
                # Gather all owner wallet addresses
                owner_wallets = await asyncio.gather(*tasks)
                
                # Compile holder information
                for idx, (account, owner_wallet) in enumerate(zip(accounts_to_process, owner_wallets), start=1):
                    if owner_wallet is None:
                        print(f"Skipping account {str(account.address)} due to missing owner wallet.")
                        continue
                    holder_info = {
                        "rank": idx,
                        "address": owner_wallet,
                        "amount": int(account.amount.amount),
                        "percentage": (int(account.amount.amount) / total_supply) * 100 if total_supply > 0 else 0,
                        "is_dev": False  # Default value
                    }
                    # Tag the dev wallet if it matches
                    if self.dev_wallet_pubkey and owner_wallet == str(self.dev_wallet_pubkey):
                        holder_info["is_dev"] = True
                    top_holders.append(holder_info)
            else:
                for idx, account in enumerate(accounts_to_process, start=1):
                    holder_info = {
                        "rank": idx,
                        "address": str(account.address),
                        "amount": int(account.amount.amount),
                        "percentage": (int(account.amount.amount) / total_supply) * 100 if total_supply > 0 else 0,
                        "is_dev": False  # Default value
                    }
                    # Tag the dev wallet if it matches
                    if self.dev_wallet_pubkey and str(account.address) == str(self.dev_wallet_pubkey):
                        holder_info["is_dev"] = True
                    top_holders.append(holder_info)
            
            return top_holders
        except Exception as e:
            print(f"Exception in get_top_holders: {e}")
            return []

    async def display_top_holders(self, mint_address: Pubkey, top_n: int = 20, top_holders: List[Dict] = None):
        """
        Fetches and displays the top N token holders with their wallet addresses, balances, and holding percentages.

        Args:
            mint_address (str): The mint address of the token.
            top_n (int, optional): Number of top holders to retrieve. Defaults to 20.
        """  
        if not top_holders:
            print("No top holders found or an error occurred.")
            return
        
        print("Total number of unique holders:", str(await self.get_holder_count(mint_address)))
        
        print(f"\nTop {top_n} Token Holders for Mint {mint_address}:")
        print("-" * 120)
        print(f"{'Rank':<5} {'Owner Wallet Address':<50} {'Amount':<25} {'% of Total Supply':<20} {'Dev Wallet'}")
        print("-" * 120)
        for holder in top_holders:
            rank = holder['rank']
            address = holder['address']
            amount = holder['amount']
            percentage = holder['percentage']
            dev_tag = "✅" if holder.get('is_dev') else ""
            print(f"{rank:<5} {address:<50} {amount:<25} {percentage:<20.2f} {dev_tag}")
        print("-" * 120)
        
    # Check if holder count exceeds the threshold
    async def check_holder_count(self, mint_address: Pubkey, threshold: int = 35):
        currentThreshold = await self.get_holder_count(mint_address)
        if (currentThreshold >= threshold):
            print(f"Unique holder count exceeds the threshold of {threshold}.")
            return True
        print(f"Unique holder count is below the threshold of {threshold}.")
        return False
        
    # Check if dev wallet is sold
    async def check_dev_wallet_sold(self, mint_address: Pubkey, threshold: int = 1, top_holders: List[Dict] = None):
        if not top_holders:
            print("No top holders found or an error occurred.")
            return False
        
        for holder in top_holders:
            if holder['address'] == str(self.dev_wallet_pubkey) and holder['percentage'] >= threshold:
                print(f"Dev wallet still holds tokens and exceeds the threshold of {threshold}%.")
                return False
        print("Dev wallet has sold all tokens.")
        return True
    
    # Check if LP liquidity threshold (BondingCurve) is met
    async def check_lp_liquidity(self, mint_address: Pubkey, thresholdLower: int = 70, thresholdUpper: int = 80, top_holders: List[Dict] = None):
        if not top_holders:
            print("No top holders found or an error occurred.")
            return False
        
        for holder in top_holders:
            if holder['address'] == str(self.bonding_curve_pubkey) and holder['percentage'] <= thresholdUpper and holder['percentage'] > thresholdLower:
                print(f"LP liquidity meets the threshold of {thresholdLower}% to {thresholdUpper}%.")
                return True
        print(f"LP liquidity does not meet the threshold of {thresholdLower}% to {thresholdUpper}%.")
        return False
    
    # Check if within the time limit
    async def check_time_limit(self, startEpochTime: int = 0, timeLimit: int = 100):
        if int(time.time()) - startEpochTime <= timeLimit:
            print(f"Within the time limit of {timeLimit} seconds.")
            return True
        print(f"Time limit exceeded ({timeLimit} seconds).")
        return False
        
    # Decision maker for HolderCountAnalyzer
    # Check if the number of unique holders exceeds the threshold
    # Check if the dev wallet has sold all tokens
    # Check if LP liquidity (BondingCurve) meets the threshold
    # Check if within the time limit
    async def make_decision(self, mint_address: Pubkey, holder_threshold: int = 35, dev_threshold: int = 1, lp_threshold_lower: int = 70, lp_threshold_upper: int = 80, startEpochTime: int = 0, timeLimit: int = 100): 
        try:
            print("At second since epoch: ", int(time.time()) - startEpochTime)
            top_holders = await self.get_top_holders(mint_address, top_n=20)
            if not top_holders:
                print("No top holders found or an error occurred. Skipping further analysis.")
                return True
            await self.display_top_holders(mint_address, top_n=20, top_holders=top_holders)
            time_met = await self.check_time_limit(startEpochTime, timeLimit)
            holder_count_met = await self.check_holder_count(mint_address, holder_threshold)
            dev_wallet_sold = await self.check_dev_wallet_sold(mint_address, dev_threshold, top_holders)
            lp_liquidity_met = await self.check_lp_liquidity(mint_address, lp_threshold_lower, lp_threshold_upper, top_holders)
            
            if holder_count_met and dev_wallet_sold and lp_liquidity_met and time_met:
                print("All conditions met. Proceed with the next step.")
                return False
            # TODO: Hardcoded conditions for now  
            # 60 holders, dev holding, liquidity 60 - 80, 6 minutes
            elif await self.check_holder_count(mint_address, 60) and await self.check_lp_liquidity(mint_address, 60, 80, top_holders) and time_met and not dev_wallet_sold:
                print("Special conditions met. Proceed with the next step.")
                print("Conditions: 60 holders, LP liquidity 60 - 80, dev wallet still holding, within 100 seconds.")
                return False
            else:
                print("Conditions not met. Waiting for further analysis.")
            
            # No longer needed to track if the dev wallet has no more holders
            for holder in top_holders:
                if holder['address'] == str(self.bonding_curve_pubkey):
                    if holder['percentage'] >= 99:
                        print("No holders left in the bonding curve. Exiting...")
                        return False
            
            # No longer needed to track if time limit is exceeded
            if not time_met:
                print("Time limit exceeded. Exiting...")
                return False
            
            return True
        except Exception as e:
            print(f"Exception in make_decision: {e}")
