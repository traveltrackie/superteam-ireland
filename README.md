# LocalLoop - Solana-Powered Scavenger Hunt Game

LocalLoop is an interactive web-based scavenger hunt game built with Python, Dash, and Plotly. Players explore real-world locations, solve puzzles, and earn SPL tokens on the Solana devnet as rewards. This project demonstrates how to integrate Solana blockchain interactions (token creation, transfers) into a Python web application.

## Features

*   Interactive scavenger hunt game UI using Dash and Dash Bootstrap Components.
*   Location-based puzzles and audio guides.
*   SPL token rewards on Solana devnet for game achievements (arriving at locations, solving puzzles).
*   Token minting and transfer logic using the `solana-py` SDK.
*   Dynamic UI updates based on game state.
*   Selfie uploads for game completion.
*   (Optional) AI-powered answer checking using Anthropic Claude.

## Repository Structure

```
.
├── app.py                  # Main Dash application, game logic, Solana interactions
├── mint_tokens.py          # Script to create and mint SPL tokens
├── setup_account.py        # Script to generate Solana keypairs
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment variable file
├── audio/                    # Directory for audio guide files (referenced in app.py)
└── README.md               # This file
```
*(The `data/` directory for game states and selfies will be created automatically by `app.py` when it runs.)*

## Prerequisites

*   Python 3.8 or higher
*   pip (Python package installer)
*   A Solana devnet RPC URL (e.g., from Helius)
*   (Optional) An Anthropic API key for AI-enhanced puzzle answer checking.

## Setup Instructions

Follow these steps to set up and run the LocalLoop application on your local environment.

### 1. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### 2. Set Up Python Virtual Environment

It's recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 4. Create `.env` File

Create a `.env` file in the root of the project directory by copying `.env.example` (if provided) or creating a new one. This file will store your sensitive configuration and API keys.

```bash
touch .env
```

You will populate this file in the following steps.

### 5. Solana Account Setup

This application requires a "sender" account (to pay for transactions and mint tokens) and a "receiver" account (to receive token rewards from the game).

*   **Generate Keypairs**:
    Run the `setup_account.py` script to generate new Solana keypairs for the sender and receiver:

    ```bash
    python setup_account.py
    ```

    The script will output:
    *   `Sender Private Key (64-byte array)`: e.g., `[10, 20, ..., 30]`
    *   `Sender Public Key`: e.g., `EhDv821AFuFipAkV7oLcTERSWLXHLxrHRpm5qeidGXYZ`
    *   `Receiver Private Key (64-byte array)` (Keep this safe if you want to access the receiver wallet, though `app.py` only needs its public key).
    *   `Receiver Public Key`: e.g., `BkCQxTbDgffpv1iZe6r6g8wneHugqT7z1BiHwWbH2ABC`

    **IMPORTANT**:
    *   Securely save the **Sender Private Key array**. You will add this to your `.env` file.
    *   Note down the **Sender Public Key**. You'll need this to fund the account.
    *   Note down the **Receiver Public Key**. This will be the wallet address rewards are sent to.

*   **Fund Sender Account**:
    The sender account needs SOL on the devnet to pay for transaction fees (like minting tokens).
    1.  Go to a Solana devnet faucet: [https://faucet.solana.com/](https://faucet.solana.com/)
    2.  Enter the **Sender Public Key** you noted down.
    3.  Select "Devnet" as the network.
    4.  Request an airdrop of SOL (e.g., 1 or 2 SOL is usually sufficient for dev purposes).

### 6. Helius RPC Setup

You need a Solana RPC URL to communicate with the blockchain. Helius provides reliable RPC endpoints.

1.  Go to [https://www.helius.dev/](https://www.helius.dev/) and sign up for an account.
2.  Create a new project.
3.  Navigate to the "Endpoints" section of your Helius project dashboard.
4.  Copy the **Devnet RPC URL**. It will look something like `https://devnet.helius-rpc.com/?api-key=YOUR_API_KEY`.

### 7. Configure Environment Variables (Part 1)

Open your `.env` file and add the following, replacing the placeholder values with your actual keys and URLs:

```env
# Sender's account details (from setup_account.py)
SENDER_PRIVATE_KEY="[...paste the 64-byte array for sender private key here, e.g., [10,20,...,30]...]"
# SENDER_PUBLIC_KEY="your_sender_public_key_string" # For reference or if mint_tokens.py uses it directly

# Receiver's wallet address (from setup_account.py)
RECEIVER_WALLET_ADDRESS="your_receiver_public_key_string"

# Solana RPC URL (from Helius)
SOLANA_RPC_URL="your_helius_devnet_rpc_url"

# (Optional) Anthropic API Key for AI puzzle checking
# ANTHROPIC_API_KEY="your_anthropic_api_key"
```
**Note on `SENDER_PRIVATE_KEY`**: Ensure it is the full string representation of the list, including the square brackets `[]`.

### 8. Prepare and Run Token Minting Script

The `mint_tokens.py` script will create a new SPL Token on the devnet and mint an initial supply to the sender's account. This token will then be used for rewards in the game.

*   **Modify `mint_tokens.py`**:
    The provided `mint_tokens.py` script needs to be updated to load the sender's credentials from the `.env` file.
    Make the following changes at the beginning of `mint_tokens.py`:

    ```python
    from dotenv import load_dotenv # Add this import
    import os # Add this import
    # from solana.keypair import Keypair # Already there, ensure it is
    # from solana.publickey import PublicKey # Already there, ensure it is
    # from solana.rpc.api import Client # Already there, ensure it is
    # from spl.token.client import Token # Already there, ensure it is
    # from spl.token.constants import TOKEN_PROGRAM_ID # Already there, ensure it is
    # from solana.rpc.types import TxOpts # Already there, ensure it is
    import logging # Optional: for better output

    logging.basicConfig(level=logging.INFO) # Optional
    logger = logging.getLogger(__name__) # Optional

    load_dotenv() # Add this line

    # Initialize Solana Client (uses SOLANA_RPC_URL from .env)
    # The script already has: client = Client(os.getenv("SOLANA_RPC_URL"))
    # Ensure SOLANA_RPC_URL is correctly set in .env

    # Reconstruct Sender Keypair from SENDER_PRIVATE_KEY in .env
    sender_private_key_str = os.getenv("SENDER_PRIVATE_KEY")
    if not sender_private_key_str:
        raise ValueError("SENDER_PRIVATE_KEY not found in .env file. Please set it.")
    try:
        sender_secret_key_list = eval(sender_private_key_str) # Safely parse the string list
        sender_secret_key_bytes = bytes(sender_secret_key_list)
        sender = Keypair.from_secret_key(sender_secret_key_bytes) # This is the 'sender' Keypair object
        logger.info(f"Using sender account: {sender.public_key}") # Optional
    except Exception as e:
        raise ValueError(f"Error parsing SENDER_PRIVATE_KEY: {e}. Ensure it's a string like '[1, 2, ...]'")

    # The script uses a 'sender_public_key' variable as a string later on.
    # Let's define it from our reconstructed 'sender' Keypair for consistency if needed.
    # However, it's better to use sender.public_key (PublicKey object) where possible.
    # sender_public_key = str(sender.public_key) # If 'sender_public_key' (string) is explicitly needed

    # The script has two sections for creating a mint. The `Token.create_mint` method is more straightforward.
    # We will rely on the part of the script that uses `Token.create_mint`.
    # Ensure `payer = sender` line correctly uses the reconstructed `sender` Keypair object.
    # Ensure `mint_authority = payer.public_key` uses the public key from the reconstructed `sender` Keypair.

    # The script should print the new token mint address.
    # After `token = Token.create_mint(...)`, add:
    # print(f"Newly created Token Mint Address: {token.pubkey}")
    # This is the address you'll use for TOKEN_MINT_ADDRESS in .env for app.py.
    ```
    Specifically, ensure the latter part of `mint_tokens.py` (starting with `payer = sender` and `token = Token.create_mint(...)`) uses the `sender` `Keypair` object you just reconstructed. The script should output the public key of the token created by `Token.create_mint`.

*   **Run the script**:
    ```bash
    python mint_tokens.py
    ```
    The script should output "Tokens minted successfully!" and, if you added the print statement, the **Token Mint Address**. Note this address down. It will be a long base58 string (e.g., `7pvFhTvjetnAG7YiakCQFnvpjwTdp7LhLqgFfPq1ZG7G`).

### 9. Update Environment Variables (Part 2)

Go back to your `.env` file and add/update the `TOKEN_MINT_ADDRESS`:

```env
# ... (other variables from Part 1) ...

# Token Mint Address (from output of mint_tokens.py)
TOKEN_MINT_ADDRESS="your_newly_created_token_mint_address"
```

Your `.env` file should now look something like this:
```env
SENDER_PRIVATE_KEY="[...]"
RECEIVER_WALLET_ADDRESS="receiver_public_key_string"
SOLANA_RPC_URL="helius_devnet_rpc_url"
TOKEN_MINT_ADDRESS="token_mint_public_key_string"
ANTHROPIC_API_KEY="your_anthropic_api_key" # Optional
```

## Running the Application

Once all setup steps are complete, you can run the Dash application:

```bash
python app.py
```

Alternatively, for a more production-like setup, you can use Gunicorn:
```bash
gunicorn app:server --bind 0.0.0.0:8050
```

The application will be accessible at `http://127.0.0.1:8050` (or `http://localhost:8050`) in your web browser.

## Using the Application

1.  **Access the UI**: Open `http://127.0.0.1:8050` in your browser.
2.  **Start the Game**:
    *   The game starts with an initial message. Click the "ARRIVED" button (map marker icon) to begin the hunt at the first location.
3.  **Gameplay**:
    *   **Navigation**: The app will tell you the name of the next location. Use the provided Google Maps link to navigate there.
    *   **Arrival**: Once you arrive, click the "ARRIVED" button again.
    *   **Puzzles**: You'll receive a puzzle related to the location. You can listen to an audio fact for clues.
    *   **Hints**: If stuck, use the "HINT" button (lightbulb icon). Using a hint incurs a small token penalty.
    *   **Answering**: Type your puzzle answer into the chat box and press Enter or click the send button.
    *   **Token Rewards**: Correct answers and arrivals reward you with SPL tokens. These are automatically sent to the `RECEIVER_WALLET_ADDRESS` you configured.
    *   **Progress**: Your progress and token balance are displayed. You can click the token balance to see recent transactions.
    *   **Help**: Use the "HELP" button (question mark icon) for context-specific assistance.
4.  **Completion**: After visiting all locations and solving puzzles, you'll be asked to upload a selfie to complete the hunt and receive a (mock) certificate.
5.  **Checking Token Transfers (Optional)**:
    You can verify token transfers on a Solana explorer like [Solscan (Devnet)](https://solscan.io/?cluster=devnet).
    *   Search for your `RECEIVER_WALLET_ADDRESS`.
    *   Look under the "Token Accounts" or "Portfolio" section to see the tokens you've earned. You might need to find the token account associated with the `TOKEN_MINT_ADDRESS` for your receiver wallet.

## Resources

The original instructions included these helpful resources:

*   [QuickNode: How to Transfer SPL Tokens on Solana](https://www.quicknode.com/guides/solana-development/spl-tokens/how-to-transfer-spl-tokens-on-solana)
*   [Solana Faucet](https://faucet.solana.com/)
*   [Solscan Explorer](https://solscan.io/)
*   [Helius Docs: Quickstart](https://www.helius.dev/docs/quickstart)
*   [Solana Developers Cookbook](https://solana.com/developers/cookbook)
*   [MichaelHly: Solana-Py SPL Intro](https://michaelhly.com/solana-py/spl/intro/)
*   [Solana Medium: Sealevel Parallel Processing](https://medium.com/solana-labs/sealevel-parallel-processing-thousands-of-smart-contracts-d814b378192)
*   [Solana YouTube Playlist](https://www.youtube.com/watch?v=amAq-WHAFs8&list=PLilwLeBwGuK7HN8ZnXpGAD9q6i4syhnVc)
*   [Solana Docs: Python Client](https://solana.com/docs/clients/python)

## Disclaimer

This project is for educational and demonstration purposes, utilizing the Solana **devnet**. Tokens earned have no real-world value. Always handle private keys with extreme care and never share them. Do not use devnet private keys for mainnet accounts.