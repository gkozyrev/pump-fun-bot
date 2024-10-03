from solders.pubkey import Pubkey

# System & pump.fun addresses
PUMP_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
PUMP_GLOBAL = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
PUMP_EVENT_AUTHORITY = Pubkey.from_string("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1")
PUMP_FEE = Pubkey.from_string("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
SYSTEM_TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
SOL = Pubkey.from_string("So11111111111111111111111111111111111111112")
LAMPORTS_PER_SOL = 1_000_000_000

# Trading parameters
BUY_AMOUNT = 0.0001  # Amount of SOL to spend when buying
BUY_SLIPPAGE = 0.05  # 5% slippage tolerance for buying
SELL_SLIPPAGE = 0.05  # 5% slippage tolerance for selling

# Your nodes
# You can also get a trader node https://docs.chainstack.com/docs/warp-transactions
RPC_ENDPOINT = "https://solana-mainnet.core.chainstack.com/12a947cc52af1fecbb9981620fe19b5e"
WSS_ENDPOINT = "wss://solana-mainnet.core.chainstack.com/12a947cc52af1fecbb9981620fe19b5e"

# Helius API
RPC_ENDPOINT_HELIUS = "https://mainnet.helius-rpc.com/?api-key=6f4f0ef0-5ac1-4320-b03a-4d1ef3269de7"
WSS_ENDPOINT_HELIUS = "wss://mainnet.helius-rpc.com/?api-key=6f4f0ef0-5ac1-4320-b03a-4d1ef3269de7"
API_KEY_HELIUS = "6f4f0ef0-5ac1-4320-b03a-4d1ef3269de7"

#Private key
PRIVATE_KEY = "SOLANA_PRIVATE_KEY"