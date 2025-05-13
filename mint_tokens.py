from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.rpc.api import Client
from solana.keypair import Keypair
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    transfer_checked,
)
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from solana.system_program import SYS_PROGRAM_ID
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.client import Token
from spl.token.instructions import get_associated_token_address
from solana.rpc.commitment import Confirmed
from spl.token.instructions import initialize_mint, InitializeMintParams
from solana.system_program import CreateAccountParams, create_account
import base58
import os


# Initialize the Solana client
client = Client(os.getenv("SOLANA_RPC_URL"))

# Generate a new keypair for the mint account
mint_account = Keypair.generate()

# Generate a keypair for the mint authority (who can mint new tokens)
mint_authority = sender_public_key

# Define the number of decimals for the token (e.g., 6 for USDC)
decimals = 6

# Calculate the minimum balance required for rent exemption
mint_account_space = 82  # Size of the Mint account
rent_exemption = client.get_minimum_balance_for_rent_exemption(mint_account_space)


# Create the mint account
create_mint_account_ix = create_account(
    CreateAccountParams(
        from_pubkey=PublicKey(sender_public_key),  # Convert sender_public_key to PublicKey
        new_account_pubkey=mint_account.public_key,
        lamports=1461600,
        space=mint_account_space,
        program_id=TOKEN_PROGRAM_ID,
    )
)

# Initialize the mint account
initialize_mint_ix = initialize_mint(
    InitializeMintParams(
        decimals=decimals,
        program_id=TOKEN_PROGRAM_ID,
        mint=mint_account.public_key,
        mint_authority=PublicKey(mint_authority), # Convert mint_authority to PublicKey
        freeze_authority=None,  # Optional: set if you want to be able to freeze token accounts
    )
)

# Create and send the transaction
transaction = Transaction()
transaction.add(create_mint_account_ix)
transaction.add(initialize_mint_ix)

# Output the mint address and transaction signature
print("Mint Address:", mint_account.public_key)

# Replace with your token mint address
TOKEN_MINT_ADDRESS = os.getenv("TOKEN_MINT_ADDRESS")
mint_pubkey = PublicKey(TOKEN_MINT_ADDRESS)


# Use the 'sender' Keypair as the payer instead of mint_authority
payer = sender  # sender is a Keypair object

# Create a new token mint
# The mint_authority should be the payer's public key for minting
token = Token.create_mint(
    conn=client,
    payer=payer,
    mint_authority=payer.public_key, # Changed to payer.public_key
    decimals=6,  # you can choose 0-9 typically
    program_id=TOKEN_PROGRAM_ID,
)

recipient_token_account = token.create_associated_token_account(PublicKey(sender_public_key))

# Mint tokens to the recipient’s token account
# The mint_authority in mint_to should be the payer
token.mint_to(
    dest=recipient_token_account,
    mint_authority=payer, # Changed to payer instead of payer.public_key
    amount=10_000_000,  # amount = 1.0 token if decimals=6
    opts=TxOpts(skip_confirmation=False),
)

print("Tokens minted successfully!")
