import dash
from dash import dcc, html, callback, Input, Output, State, ctx, ALL, MATCH, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px
import random
import time
import math
import os
import logging
import json
import anthropic
import uuid
import base64
import io
import re
import hashlib
from flask import Response
import pathlib

# Solana imports for token rewards
from solana.keypair import Keypair
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    transfer_checked,
    TransferCheckedParams
)
from solana.rpc.api import Client as SolanaClient
from solana.transaction import Transaction
from solana.publickey import PublicKey
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.client import Token
from solana.system_program import SYS_PROGRAM_ID

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Dash app
app = dash.Dash(
    __name__, 
    external_stylesheets=[
        dbc.themes.BOOTSTRAP, 
        'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.1/css/all.min.css'
    ],
    suppress_callback_exceptions=False,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1, maximum-scale=1"},
        {"name": "theme-color", "content": "#232333"}
    ]
)

# Then expose the server
server = app.server

# Configure local storage directories
DATA_DIR = os.path.join(os.getcwd(), "data")
GAME_STATES_DIR = os.path.join(DATA_DIR, "game_states")
SELFIES_DIR = os.path.join(DATA_DIR, "selfies")

# Create directories if they don't exist
for directory in [DATA_DIR, GAME_STATES_DIR, SELFIES_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

# Token reward constants
TOKEN_REWARD_ARRIVED = 10      # 10 tokens for arriving at a location
TOKEN_REWARD_CORRECT_ANSWER = 20  # 20 tokens for correctly answering a puzzle
TOKEN_PENALTY_HINT = 5         # Lose 5 tokens for using a hint
TOKEN_REWARD_FAILED_PUZZLE = 0  # 0 tokens for failing to answer a puzzle correctly

# Solana configuration constants
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")
TOKEN_MINT_ADDRESS = os.getenv("TOKEN_MINT_ADDRESS")
TOKEN_DECIMALS = 6

# Hardcoded wallet addresses as requested
SENDER_PRIVATE_KEY = os.getenv("SENDER_PRIVATE_KEY")
RECEIVER_WALLET_ADDRESS = os.getenv("RECEIVER_WALLET_ADDRESS")
# Initialize Solana client and sender keypair for token transfers
try:
    # Initialize Solana client
    solana_client = SolanaClient(SOLANA_RPC_URL)
    
    # Parse sender keypair from string representation
    sender_list = eval(SENDER_PRIVATE_KEY) if SENDER_PRIVATE_KEY else None
    sender_bytes = bytes(sender_list) if sender_list else None
    sender_keypair = Keypair.from_secret_key(sender_bytes) if sender_bytes else None
    sender_pubkey = sender_keypair.public_key if sender_keypair else None
    
    # Initialize token client
    if TOKEN_MINT_ADDRESS and sender_pubkey:
        token_client = Token(
            conn=solana_client,
            pubkey=PublicKey(TOKEN_MINT_ADDRESS),
            program_id=TOKEN_PROGRAM_ID,
            payer=sender_pubkey
        )
        logger.info("Solana token client initialized successfully")
        SOLANA_ENABLED = True
    else:
        logger.warning("Solana token client initialization skipped - missing configuration")
        SOLANA_ENABLED = False
except Exception as e:
    logger.error(f"Failed to initialize Solana client: {str(e)}")
    SOLANA_ENABLED = False

# Game data structure 
GAME_DATA = {
    "locations": [
        {
            "id": 1,
        "name": "Wolfe Tone Sculpture, St. Stephen's Green",
        "google_maps_link": "https://maps.app.goo.gl/7ppfqN3dd66KERkz5",
        "audio_fact": "audio/st_stephens_green.mp3",
        "lat": 53.3384, 
        "lon": -6.25619,
        "puzzle": {
        "question": "He stands alone, coat heavy, eyes forward. Behind him, stone rises like a wall. What shape do these stones form?",
        "answer": "a semicircle",
        "hint1": "The stones curve gently, not straight.",
        "hint2": "Think of half a circle.",
        "hint3": "The shape embraces the statue from behind."
            }
        },
        {
            "id": 2,
        "name": "Leinster House",
        "google_maps_link": "https://maps.app.goo.gl/ivY7RmngZ6quAds9A",
        "audio_fact": "audio/dail_eirrean.mp3",
        "lat": 53.34059, 
        "lon": -6.25398,
        "puzzle": {
        "question": "Before becoming the Irish Parliament, what group owned Leinster House?",
        "answer": "The Royal Dublin Society",
        "hint1": "This group is known for promoting agriculture and the arts.",
        "hint2": "They held their famous Dublin Horse Show on the grounds.",
        "hint3": "They bought the building in 1815."
            }
        },
        {
            "id": 3,
            "name": "Grafton Street",
        "google_maps_link": "https://maps.app.goo.gl/gg15UXuNLyNPjan7A",
        "audio_fact": "audio/grafton_street.mp3",
        "lat": 53.34242, 
        "lon": -6.25993,
        "puzzle": {
        "question": "Find the building with a white angel that promises 'PRAESCRIPTA MEDICORUM ACCURATE CONFECTA'. What business operates there now?",
        "answer": "Boots",
        "hint1": "Look for a white angel mounted on a beige wall.",
        "hint2": "The Latin phrase relates to medical prescriptions.",
        "hint3": "It's a well-known pharmacy chain with a blue storefront."
            }
        },
        {
            "id": 4,
        "name": "Trinity College Dublin",
        "google_maps_link": "https://maps.app.goo.gl/7bEcswZ7W1VUvYp78",
        "audio_fact": "audio/tcd.mp3",
        "lat": 53.34493, 
        "lon": -6.25779,
        "puzzle": {
        "question": "How many spiral shells appear on this ancient stone shield?",
        "answer": "3",
        "hint1": "Count the cone-shaped objects that look like seashells.",
        "hint2": "Look both above and below the horizontal line on the shield.",
        "hint3": "There are more spiral shapes on top than on bottom."
            }
        },
        {
            "id": 5,
        "name": "College Green",
        "google_maps_link": "https://maps.app.goo.gl/5gkATc4ak9RCBuhq6",
        "audio_fact": "audio/college_green.mp3",
        "lat": 53.34442, 
        "lon": -6.26085,
        "puzzle": {
        "question": "What do the four bronze figures on the Thomas Davis Memorial Fountain represent?",
        "answer": "Four provinces",
        "hint1": "These figures blow water through trumpets.",
        "hint2": "There are four main geographical divisions of the island.",
        "hint3": "Ulster, Munster, Leinster, and Connacht are their names."
            }
        },
        {
            "id": 6,
        "name": "Temple Bar",
        "google_maps_link": "https://maps.app.goo.gl/5K75ei1kcNNiuNB46",
        "audio_fact": "audio/templebar.mp3",
        "lat": 53.34499,
        "lon": -6.26534,
        "puzzle": {
        "question": "The yellow stars on \"The Diceman Corner\" sign: How many points do each star have?",
        "answer": "Five",
        "hint1": "Look closely at the golden shapes above the Irish words.",
        "hint2": "Count the sharp angles on one of the sun-like figures.",
        "hint3": "Think of a common shape often seen on flags or as celestial bodies."
            }
        },
        {
            "id": 7,
        "name": "Dublin Castle",
        "google_maps_link": "https://maps.app.goo.gl/wYaDtSRuacxXowAm9",
        "audio_fact": "audio/dublin_castle.mp3",
        "lat": 53.34288, 
        "lon": -6.26742,
        "puzzle": {
        "question": "What financial institution once stood where the extension of Bedford Tower is now?",
        "answer": "La Touche Bank",
        "hint1": "This former business dealt with money.",
        "hint2": "It shares a name with a prominent Irish family.",
        "hint3": "It was renamed as Castle Hall."
            }
        },
        {
            "id": 8,
        "name": "Chester Beatty Library",
        "google_maps_link": "https://maps.app.goo.gl/JfDwQ7AqR5pto4R4A",
        "audio_fact": "audio/chester_beatty.mp3",
        "lat": 53.34223, 
        "lon": -6.26727,
        "puzzle": {
        "question": "What unusual creature sits atop the Chester Beatty Library's clock tower, watching over Dublin Castle?",
        "answer": "A peacock-shaped weather vane.",
        "hint1": "It's a bird, but not one you'd expect on a roof.",
        "hint2": "This bird is known for its colorful feathers and royal strut.",
        "hint3": "It spins with the wind, yet never flies."
            }
        }        
    ]
}

# Constants
MAX_PUZZLE_ATTEMPTS = 3

def validate_game_state(game_state):
    """Validate and repair game state to ensure it has all required fields with correct types"""
    try:
        # If game_state is a string, parse it
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                logger.warning("Game state is a string and not valid JSON")
                return reset_game_state()
                
        if not isinstance(game_state, dict):
            return reset_game_state()
        
        # Create a fresh state with default values
        validated_state = {
            "game_started": bool(game_state.get("game_started", False)),
            "current_step": game_state.get("current_step", "not_started"),
            "current_location_index": 0,  # Will be validated below
            "completed_locations": [],
            "puzzle_attempts": 0,
            "hints_used": 0,
            "start_time": None,
            "messages": [],
            "tokens_earned": 0,
            "token_transactions": []
        }
        
        # Only copy valid current_location_index
        try:
            location_index = int(game_state.get("current_location_index", 0))
            if 0 <= location_index < len(GAME_DATA["locations"]):
                validated_state["current_location_index"] = location_index
        except (ValueError, TypeError):
            pass  # Keep default value
        
        # Copy other fields if they exist and are valid
        if "completed_locations" in game_state and isinstance(game_state["completed_locations"], list):
            validated_state["completed_locations"] = game_state["completed_locations"]
            
        if "puzzle_attempts" in game_state:
            try:
                validated_state["puzzle_attempts"] = int(game_state["puzzle_attempts"])
            except (ValueError, TypeError):
                pass  # Keep default
                
        if "hints_used" in game_state:
            try:
                validated_state["hints_used"] = int(game_state["hints_used"])
            except (ValueError, TypeError):
                pass  # Keep default
                
        if "start_time" in game_state:
            try:
                validated_state["start_time"] = float(game_state["start_time"])
            except (ValueError, TypeError):
                validated_state["start_time"] = time.time() if validated_state["game_started"] else None
                
        # Copy messages, but limit to MAX_MESSAGES
        MAX_MESSAGES = 5
        if "messages" in game_state and isinstance(game_state["messages"], list):
            messages = []
            for msg in game_state["messages"][-MAX_MESSAGES:]:  # Only keep most recent
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append(msg)
            validated_state["messages"] = messages
            
        # Copy token values
        if "tokens_earned" in game_state:
            try:
                validated_state["tokens_earned"] = int(game_state["tokens_earned"])
            except (ValueError, TypeError):
                pass  # Keep default
                
        if "token_transactions" in game_state and isinstance(game_state["token_transactions"], list):
            # Only keep most recent transactions
            validated_state["token_transactions"] = game_state["token_transactions"][-10:]
            
        return validated_state
    except Exception as e:
        logger.error(f"Error validating game state: {str(e)}")
        return reset_game_state()

# Add this new utility function to make objects JSON serializable
def sanitize_for_json(obj):
    """
    Recursively processes an object to make it JSON serializable.
    Enhanced to handle more edge cases.
    """
    try:
        # Try direct JSON serialization first (fast path)
        json.dumps(obj)
        return obj
    except (TypeError, OverflowError):
        # Handle more complex conversions
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, list):
            return [sanitize_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(key): sanitize_for_json(value) for key, value in obj.items()}
        elif hasattr(obj, '__dict__'):
            return sanitize_for_json(obj.__dict__)
        elif hasattr(obj, '__str__'):
            return str(obj)
        else:
            return str(obj)
    except Exception as e:
        logger.error(f"Error in sanitize_for_json: {str(e)}")
        return str(obj)

def generate_success_message(game_state, is_final_location):
    """Generate a success message when a puzzle is correctly answered"""
    try:
        if is_final_location:
            return "Correct! You've completed all locations! Please upload a selfie to finish the hunt."
        else:
            next_location = GAME_DATA["locations"][game_state["current_location_index"] + 1]
            return f"Correct! Next, head to {next_location['name']}. When you arrive, tap the 'ARRIVED' button."
    except Exception as e:
        logger.error(f"Error generating success message: {str(e)}")
        return "Correct! Continue to the next location."

def is_json_serializable(obj):
    """Check if an object can be serialized to JSON"""
    try:
        json.dumps(obj)
        return True
    except (TypeError, OverflowError, Exception):
        return False

# Function to transfer tokens via Solana - Simplified version using hardcoded wallet addresses
def transfer_tokens(amount):
    """
    Transfer tokens to the hardcoded receiver wallet address.
    
    Args:
        amount (int): Amount of tokens to transfer (positive for reward, negative for penalty)
    
    Returns:
        tuple: (success, transaction_signature_string or error_message)
    """
    if not SOLANA_ENABLED:
        return False, "Solana integration not enabled"
        
    try:
        # Convert amount from tokens to smallest units (e.g., lamports)
        amount_units = abs(amount) * (10 ** TOKEN_DECIMALS)
        
        # If amount is negative, it's a penalty - but we don't actually transfer
        # We just track it in the UI
        if amount <= 0:
            logger.info(f"Token penalty of {abs(amount)} applied - not transferred")
            return True, f"Applied penalty of {abs(amount)} tokens"
        
        # Convert receiver public key string to PublicKey object
        receiver_pubkey = PublicKey(RECEIVER_WALLET_ADDRESS)
        
        # Get associated token addresses
        token_mint_address = PublicKey(TOKEN_MINT_ADDRESS)
        sender_token_address = get_associated_token_address(sender_pubkey, token_mint_address)
        receiver_token_address = get_associated_token_address(receiver_pubkey, token_mint_address)
        
        # Get recent blockhash
        blockhash_resp = solana_client.get_latest_blockhash()
        recent_blockhash = str(blockhash_resp.value.blockhash)
        
        # Create transaction
        transaction = Transaction(recent_blockhash)
        
        # Check if receiver's token account exists
        receiver_account_info = solana_client.get_account_info(receiver_token_address)
        if receiver_account_info.value is None:
            # Create the receiver's token account if it doesn't exist
            create_receiver_account_ix = create_associated_token_account(
                payer=sender_pubkey,
                owner=receiver_pubkey,
                mint=token_mint_address
            )
            transaction.add(create_receiver_account_ix)
        
        # Create transfer instruction
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=sender_token_address,
                mint=token_mint_address,
                dest=receiver_token_address,
                owner=sender_pubkey,
                amount=amount_units,
                decimals=TOKEN_DECIMALS,
                signers=[]
            )
        )
        transaction.add(transfer_ix)
        
        # Send and sign transaction
        response = solana_client.send_transaction(transaction, sender_keypair)
        
        # Log and return success - Convert Signature object to string explicitly for safe serialization
        tx_signature = response.value
        # Force string conversion for the signature object
        tx_signature_str = str(tx_signature) if tx_signature else "transaction_completed"
        logger.info(f"Token transfer of {amount} tokens to {RECEIVER_WALLET_ADDRESS} successful: {tx_signature_str}")
        return True, tx_signature_str
    
    except Exception as e:
        error_msg = f"Error transferring tokens: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def get_session_id():
    """Get a unique session ID for the current user"""
    try:
        # Try to get the session ID from browser's localStorage
        session_id = None

        # Generate a random ID if JavaScript fails
        random_id = str(uuid.uuid4())
        session_id = f"session_{random_id}"

        logger.info(f"Created new session ID: {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Error generating session ID: {str(e)}")
        return f"session_{str(uuid.uuid4())}"

def save_game_state_locally(session_id, game_state):
    """Save the current game state to a local JSON file"""
    try:
        # Check if session_id is valid
        if not session_id or not isinstance(session_id, str):
            logger.error(f"Invalid session_id: {session_id}")
            return False
            
        # Handle case where game_state is a string
        if isinstance(game_state, str):
            try:
                game_state_dict = json.loads(game_state)
                game_state = game_state_dict
            except json.JSONDecodeError:
                logger.error("Game state is a string and not valid JSON")
                return False
                
        # Sanitize game_state to ensure it's JSON serializable
        try:
            # Deep copy the game state first to avoid modifying the original
            import copy
            game_state_copy = copy.deepcopy(game_state)
            sanitized_game_state = sanitize_for_json(game_state_copy)
            
            # Verify it's actually serializable
            json.dumps(sanitized_game_state)
        except Exception as e:
            logger.error(f"Error sanitizing game state: {str(e)}")
            # Create a minimal valid state that we know is serializable
            sanitized_game_state = {
                "game_started": game_state.get("game_started", False),
                "current_step": game_state.get("current_step", "not_started"),
                "current_location_index": game_state.get("current_location_index", 0),
                "tokens_earned": game_state.get("tokens_earned", 0),
                "messages": []
            }
        
        # Handle start_time carefully - FIXED: Proper handling of start_time value
        start_time_val = sanitized_game_state.get("start_time")
        if start_time_val is not None:
            try:
                # Convert to int or float if it's not already
                if not isinstance(start_time_val, (int, float)):
                    start_time_val = float(start_time_val)
                start_time = int(start_time_val)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert start_time to int: {start_time_val}")
                start_time = None
        else:
            start_time = None
            
        # Prepare message and token_transactions for safe serialization
        try:
            messages_json = json.dumps(sanitized_game_state.get("messages", []))
            token_tx_json = json.dumps(sanitized_game_state.get("token_transactions", []))
        except Exception as e:
            logger.error(f"Error converting messages or transactions to JSON: {str(e)}")
            messages_json = json.dumps([])
            token_tx_json = json.dumps([])

        # Create item to save
        item = {
            "session_id": session_id,
            "timestamp": int(time.time()),
            "game_active": sanitized_game_state.get("game_started", False),
            "current_location_index": sanitized_game_state.get("current_location_index", 0),
            "current_step": sanitized_game_state.get("current_step", "not_started"),
            "completed_locations": sanitized_game_state.get("completed_locations", []),
            "puzzle_attempts": sanitized_game_state.get("puzzle_attempts", 0),
            "hints_used": sanitized_game_state.get("hints_used", 0),
            "start_time": start_time,
            "messages": sanitized_game_state.get("messages", []),
            "tokens_earned": sanitized_game_state.get("tokens_earned", 0),
            "token_transactions": sanitized_game_state.get("token_transactions", []),
        }

        # Save to local file
        file_path = os.path.join(GAME_STATES_DIR, f"{session_id}.json")
        with open(file_path, 'w') as f:
            json.dump(item, f, indent=2)
            
        logger.info(f"Game state saved to local file: {file_path}")
        return True
    except Exception as e:
        error_msg = f"Error saving game state to local file: {str(e)}"
        logger.error(error_msg)
        return False

def test_local_storage():
    """Test if we can write to local storage directories"""
    try:
        # Test writing to game states directory
        test_file_path = os.path.join(GAME_STATES_DIR, "test_file.txt")
        with open(test_file_path, 'w') as f:
            f.write("Test content")
        
        # Remove test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            
        # Test writing to selfies directory
        test_file_path = os.path.join(SELFIES_DIR, "test_file.txt")
        with open(test_file_path, 'w') as f:
            f.write("Test content")
            
        # Remove test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            
        logger.info("Local storage test successful")
        return True
    except Exception as e:
        error_msg = f"Local storage test failed: {str(e)}"
        logger.error(error_msg)
        return False

def restore_game_state_locally(session_id):
    """Restore game state from local JSON file"""
    try:
        file_path = os.path.join(GAME_STATES_DIR, f"{session_id}.json")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.info(f"No saved game state found for session ID: {session_id}")
            return None
            
        # Read the JSON file
        with open(file_path, 'r') as f:
            item = json.load(f)

        # Check if item is expired (older than 24 hours)
        current_time = int(time.time())
        if "timestamp" in item and current_time - item["timestamp"] > 86400:
            logger.info(f"Saved game state has expired: {session_id}")
            # Remove expired file
            os.remove(file_path)
            return None

        # Check if game is active
        if "game_active" not in item or not item["game_active"]:
            logger.info(f"Saved game is not active: {session_id}")
            return None

        # Initialize game state
        game_state = {
            "game_started": item.get("game_active", False),
            "current_location_index": 0,  # Default safe value, will validate later
            "current_step": item.get("current_step", "not_started"),
            "completed_locations": item.get("completed_locations", []),
            "puzzle_attempts": item.get("puzzle_attempts", 0),
            "hints_used": item.get("hints_used", 0),
            # Add token tracking fields
            "tokens_earned": item.get("tokens_earned", 0),
            "token_transactions": item.get("token_transactions", []),
        }

        # Restore start time
        if "start_time" in item and item["start_time"]:
            try:
                game_state["start_time"] = float(item["start_time"])
            except (ValueError, TypeError):
                game_state["start_time"] = time.time()
        else:
            game_state["start_time"] = time.time()

        # Safely restore current_location_index with validation
        if "current_location_index" in item:
            try:
                location_index = int(item["current_location_index"])
                # Ensure it's within valid range
                if 0 <= location_index < len(GAME_DATA["locations"]):
                    game_state["current_location_index"] = location_index
                else:
                    logger.warning(f"Invalid current_location_index in saved state: {location_index}")
                    game_state["current_location_index"] = 0
            except (ValueError, TypeError):
                logger.warning(f"Non-integer current_location_index in saved state: {item['current_location_index']}")
                game_state["current_location_index"] = 0
        else:
            game_state["current_location_index"] = 0

        # Restore chat history
        if "messages" in item:
            game_state["messages"] = item.get("messages", [])
        else:
            game_state["messages"] = []

        # Add confirmation message to chat
        game_state["messages"].append({
            "role": "assistant",
            "content": "Game state restored! You can continue from where you left off.",
        })
        
        # Apply final validation to the restored state
        game_state = validate_game_state(game_state)

        logger.info(f"Game state restored from local file for session ID: {session_id}")
        return game_state
    except Exception as e:
        logger.error(f"Error restoring game state from local file: {str(e)}")
        return None

def start_hunt():
    """Initialize the game with token reward system"""
    try:
        # Create a new game state
        game_state = {
            "game_started": True,
            "current_location_index": 0,
            "current_step": "finding_location",
            "completed_locations": [],
            "puzzle_attempts": 0,
            "hints_used": 0,
            "start_time": time.time(),
            "messages": [],
            # Token reward system
            "tokens_earned": 0,
            "token_transactions": [],
        }

        # Return the first location information and game state
        first_location = GAME_DATA["locations"][0]
        message = (
            f"Welcome! First stop: {first_location['name']}. "
            f"Tap 'ARRIVED' button when you get there.\n\n"
            f"🪙 Token Reward System:\n"
            f"• Arriving at a location: +{TOKEN_REWARD_ARRIVED} tokens\n"
            f"• Correct puzzle answers: +{TOKEN_REWARD_CORRECT_ANSWER} tokens\n"
            f"• Using a hint: -{TOKEN_PENALTY_HINT} tokens\n\n"
            f"All tokens are automatically sent to the game's reward wallet."
        )
        
        # Do NOT add message to game state here
        
        return game_state, message
    except Exception as e:
        logger.error(f"Error starting hunt: {str(e)}")
        return (
            None,
            "Sorry, something went wrong. Tap the 'ARRIVED' button to try again.",
        )

def handle_location_arrival(game_state):
    """Handle user arrival at a location and award tokens"""
    try:
        # Validate game state first
        game_state = validate_game_state(game_state)
        
        # Ensure tokens_earned exists with a default value
        if "tokens_earned" not in game_state:
            game_state["tokens_earned"] = 0
            
        if game_state["current_step"] != "finding_location":
            return (
                game_state,
                "I'm not looking for a location confirmation right now. Tap 'HELP' for assistance.",
            )

        # Safely get current location index and validate
        current_location_index = game_state.get("current_location_index", 0)
        if not (0 <= current_location_index < len(GAME_DATA["locations"])):
            game_state["current_location_index"] = 0
            current_location_index = 0
            
        current_location = GAME_DATA["locations"][current_location_index]

        # Update state to indicate user has arrived
        game_state["current_step"] = "solving_puzzle"
        
        # Award tokens for arriving at location
        game_state["tokens_earned"] += TOKEN_REWARD_ARRIVED
        
        # Record token transaction
        transaction = {
            "type": "reward",
            "amount": TOKEN_REWARD_ARRIVED,
            "reason": f"Arrived at {current_location['name']}",
            "timestamp": time.time()
        }
        game_state.setdefault("token_transactions", []).append(transaction)
        
        # Transfer tokens using the hardcoded wallet address
        if SOLANA_ENABLED:
            success, tx_info = transfer_tokens(TOKEN_REWARD_ARRIVED)
            transaction["tx_info"] = tx_info
            transaction["success"] = success

        # Return a message that includes token information
        message = (
            f"Now, solve the puzzle at {current_location['name']}. Tap the 'HINT' button if you need assistance or listen to the audio for clues.\n\n"
            f"🪙 You earned {TOKEN_REWARD_ARRIVED} tokens for arriving! Current balance: {game_state['tokens_earned']} tokens."
        )

        return validate_game_state(game_state), message
    except Exception as e:
        logger.error(f"Error handling location arrival: {str(e)}")
        return (
            validate_game_state(game_state),
            "There was an error handling that. Try again, or if you need help, tap the 'HELP' button.",
        )

def generate_failure_message(current_location, remaining_attempts):
    """Generate a standard message for incorrect puzzle answers"""
    try:
        if remaining_attempts == 2:
            return f"Hmm, that's not it. Think it through, and try again. You have {remaining_attempts} attempts left."
        elif remaining_attempts == 1:
            return f"Almost there, but not quite. This is your last chance. If you need a hint, tap the 'HINT' button."
        elif remaining_attempts <= 0:
            # No attempts left - reveal answer and move on
            correct_answer = (
                current_location["puzzle"]["answer"]
                if isinstance(current_location["puzzle"]["answer"], str)
                else current_location["puzzle"]["answer"][0]
            )
            return f"The answer was {correct_answer}. Let's continue with the hunt."
        else:
            return f"That's not correct. Try again! You have {remaining_attempts} attempts left."
    except Exception as e:
        logger.error(f"Error generating failure message: {str(e)}")
        return "That's not correct. Please try again."

def handle_puzzle_answer(game_state, answer):
    """Handle a user's answer to a puzzle and award/deduct tokens accordingly"""
    try:
        # Validate game state first
        game_state = validate_game_state(game_state)
        
        # Ensure tokens_earned exists with a default value
        if "tokens_earned" not in game_state:
            game_state["tokens_earned"] = 0
            
        if game_state["current_step"] != "solving_puzzle":
            message = "I'm not expecting a puzzle answer right now. Tap 'HELP' for assistance."
            # Do NOT add message to game state - handle_user_input will handle that
            return game_state, message

        # Safely get location index and validate
        current_location_index = game_state.get("current_location_index", 0)
        if not (0 <= current_location_index < len(GAME_DATA["locations"])):
            game_state["current_location_index"] = 0
            current_location_index = 0
            
        current_location = GAME_DATA["locations"][current_location_index]
        puzzle = current_location["puzzle"]

        logger.info(f"Checking answer: {answer} against {puzzle['answer']}")

        if check_answer(answer, puzzle['answer'], game_state["current_location_index"]):
            # Correct answer - award tokens
            token_reward = TOKEN_REWARD_CORRECT_ANSWER
            
            # Use safe addition
            current_tokens = game_state.get("tokens_earned", 0)
            game_state["tokens_earned"] = current_tokens + token_reward
            
            # Record token transaction
            transaction = {
                "type": "reward",
                "amount": token_reward,
                "reason": f"Correct answer at {current_location['name']}",
                "timestamp": time.time()
            }
            game_state.setdefault("token_transactions", []).append(transaction)
            
            # Transfer tokens using hardcoded wallet addresses
            if SOLANA_ENABLED:
                success, tx_info = transfer_tokens(token_reward)
                transaction["tx_info"] = tx_info  # This is now a string, not a Signature object
                transaction["success"] = success
            
            # Add location to completed locations
            game_state["completed_locations"].append(current_location["id"])
            game_state["puzzle_attempts"] = 0
            # Reset hints counter when moving to a new puzzle
            game_state["hints_used"] = 0
            game_state["previous_hints"] = []
            
            # Check if this was the last location
            is_final_location = game_state["current_location_index"] == len(GAME_DATA["locations"]) - 1
            
            if is_final_location:
                # This was the final location
                game_state["current_step"] = "completed"
                base_message = "Correct! You've completed all locations! Please upload a selfie to finish the hunt."
            else:
                # Move to next location
                game_state["current_location_index"] += 1
                game_state["current_step"] = "finding_location"
                next_location = GAME_DATA["locations"][game_state["current_location_index"]]
                base_message = f"Correct! Next, head to {next_location['name']}. When you arrive, tap the 'ARRIVED' button."
                
            # Add token information to the message
            message = f"{base_message}\n\n🪙 You earned {token_reward} tokens for your correct answer! Current balance: {game_state['tokens_earned']} tokens."
                        
        else:
            # Incorrect answer
            logger.info(f"Incorrect answer for {current_location['id']}")
            game_state["puzzle_attempts"] += 1
            remaining_attempts = MAX_PUZZLE_ATTEMPTS - game_state["puzzle_attempts"]

            if game_state["puzzle_attempts"] >= MAX_PUZZLE_ATTEMPTS:
                # Too many attempts - reveal answer and move on, but no tokens awarded
                correct_answer = (
                    puzzle["answer"]
                    if isinstance(puzzle["answer"], str)
                    else puzzle["answer"][0]
                )

                # Record token transaction (0 tokens)
                transaction = {
                    "type": "no_reward",
                    "amount": TOKEN_REWARD_FAILED_PUZZLE,
                    "reason": f"Failed to solve puzzle at {current_location['name']}",
                    "timestamp": time.time()
                }
                game_state.setdefault("token_transactions", []).append(transaction)

                # Mark location as completed
                game_state["completed_locations"].append(current_location["id"])
                game_state["puzzle_attempts"] = 0
                # Reset hints counter when moving to a new puzzle
                game_state["hints_used"] = 0
                game_state["previous_hints"] = []
                
                # Check if this was the last location
                is_final_location = game_state["current_location_index"] == len(GAME_DATA["locations"]) - 1
                
                if is_final_location:
                    # This was the final location
                    game_state["current_step"] = "completed"
                    message = (
                        f"The answer was {correct_answer}. You've completed the Hunt! "
                        f"To finish up, please upload a selfie of yourself at this final location.\n\n"
                        f"No tokens were awarded for this puzzle as you exceeded the maximum number of attempts."
                    )
                else:
                    # Move to next location
                    game_state["current_location_index"] += 1
                    game_state["current_step"] = "finding_location"
                    next_location = GAME_DATA["locations"][game_state["current_location_index"]]
                    message = (
                        f"The answer was {correct_answer}. "
                        f"Next, head to {next_location['name']}. "
                        f"When you arrive, tap the 'ARRIVED' button.\n\n"
                        f"No tokens were awarded for this puzzle as you exceeded the maximum number of attempts."
                    )
            else:
                # Still has attempts left - generate standard failure message
                message = generate_failure_message(current_location, remaining_attempts)

        # Do NOT add message to game state - handle_user_input will handle that
        return validate_game_state(game_state), message
    except Exception as e:
        logger.error(f"Error handling puzzle answer: {str(e)}")
        error_message = "Sorry, there was an error processing your answer. Please try again or tap the 'HELP' button."
        # Do NOT add message to game state - handle_user_input will handle that
        return validate_game_state(game_state), error_message

def check_answer_with_llm(user_answer, correct_answers, question):
    try:
        # Convert correct_answers to a list if it's a string
        if isinstance(correct_answers, str):
            correct_answers = [correct_answers]

        # API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        # If still no API key, fall back to exact matching
        if not api_key:
            logger.warning("No Anthropic API key found. Falling back to exact matching.")
            # Try more flexible matching without LLM
            user_answer_clean = user_answer.lower().strip()
            for answer in correct_answers:
                answer_clean = answer.lower().strip()
                # Check for exact match or if answer is contained in user input
                if user_answer_clean == answer_clean or answer_clean in user_answer_clean:
                    return True
            return False

        # Initialize the Anthropic client with just the API key, no additional parameters
        client = anthropic.Anthropic(api_key=api_key)

        # Format the correct answers as a string
        formatted_correct_answers = ", ".join(correct_answers)

        # Create the prompt
        prompt = f"""Question: {question}
Accepted answers: {formatted_correct_answers}
User answer: {user_answer}

Is the user's answer semantically equivalent to any of the accepted answers? 
Consider spelling mistakes, synonyms, and different phrasings.
Only respond with 'YES' if it's essentially correct or 'NO' if it's incorrect."""

        # Call Claude API with a more reliable/available model (fallback to older model if needed)
        try:
            # Display loading feedback to user by adding a message to the game state
            # Note: This message will be shown only if added to game state in the calling function
            
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",  # Use a more stable model version
                max_tokens=50,
                temperature=0,
                system="You are a fair judge for a scavenger hunt game. Your job is to determine if a user's answer is semantically equivalent to the accepted answers.",
                messages=[{"role": "user", "content": prompt}],
            )
            
            result = response.content[0].text.strip().upper()
            logger.info(f"LLM answer check: Question: '{question}', User answer: '{user_answer}', Result: {result}")
            return result == "YES"
        except Exception as api_e:
            # Log specific API error and try a more flexible matching approach
            logger.error(f"Claude API error: {str(api_e)}, trying flexible matching")
            
            # Try more flexible matching without LLM
            user_answer_clean = user_answer.lower().strip()
            for answer in correct_answers:
                answer_clean = answer.lower().strip()
                # Check for exact match or if answer is contained in user input
                if user_answer_clean == answer_clean or answer_clean in user_answer_clean:
                    return True
            return False
            
    except Exception as e:
        logger.error(f"Error checking answer with LLM: {str(e)}")
        # Fall back to more flexible matching
        user_answer_clean = user_answer.lower().strip()
        for answer in correct_answers:
            answer_clean = answer.lower().strip()
            # Check for exact match or if answer is contained in user input
            if user_answer_clean == answer_clean or answer_clean in user_answer_clean:
                return True
        return False

def check_answer(user_answer, correct_answers, current_location_index):
    """Check if the user's answer matches any of the correct answers"""
    if not user_answer:
        return False
        
    user_answer = user_answer.lower().strip()

    # Convert correct_answers to a list if it's a string
    if isinstance(correct_answers, str):
        correct_answers = [correct_answers.lower().strip()]
    else:
        correct_answers = [answer.lower().strip() for answer in correct_answers]

    # First tier: Exact match (fastest)
    if any(answer == user_answer for answer in correct_answers):
        return True
        
    # Second tier: Contains match (still fast)
    for answer in correct_answers:
        if (answer in user_answer) or (user_answer in answer and len(user_answer) > 3):
            return True
    
    # Third tier: Fuzzy match (moderate speed)
    try:
        # Only import if needed
        from difflib import SequenceMatcher
        
        for answer in correct_answers:
            # If similarity > 0.85, consider it correct
            similarity = SequenceMatcher(None, user_answer, answer).ratio()
            if similarity > 0.85:
                return True
    except ImportError:
        pass
        
    # Final tier: LLM check (only if all else fails)
    current_location = GAME_DATA["locations"][current_location_index]
    question = current_location["puzzle"]["question"]
    return check_answer_with_llm(user_answer, correct_answers, question)

def generate_certificate_url(game_state, completion_time):
    """Generate a URL for the player's completion certificate"""
    try:
        # Create a timestamp for unique identification
        timestamp = int(time.time())
        
        # Get player identifier - use a session ID since we're not collecting wallets
        player_id = "player_" + str(timestamp)
        
        # In a real implementation, you might generate or store certificates and return actual URLs
        # For now, we'll just create a mock URL
        certificate_url = f"https://bit.ly/superteamIRL"
        
        return certificate_url
    except Exception as e:
        logger.error(f"Error generating certificate URL: {str(e)}")
        return "https://bit.ly/superteamIRL"

def save_image_locally(image_data, prefix="selfie"):
    """Save an image locally from base64 data"""
    try:
        if not image_data:
            logger.error("No image data provided")
            return False, None
            
        # Process the base64 data
        if "," in image_data:
            content_type, content_string = image_data.split(",")
        else:
            content_string = image_data
            
        try:
            decoded = base64.b64decode(content_string)
        except Exception as e:
            logger.error(f"Failed to decode base64 image data: {str(e)}")
            return False, None

        # Create a timestamp-based filename
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.jpg"
        file_path = os.path.join(SELFIES_DIR, filename)
        
        # Write the image file
        with open(file_path, 'wb') as f:
            f.write(decoded)
            
        logger.info(f"Saved image to {file_path}")
        return True, file_path
    except Exception as e:
        logger.error(f"Error saving image locally: {str(e)}")
        return False, None

def handle_completion_selfie(game_state, selfie_data):
    """Handle the final selfie submission and display total tokens earned"""
    try:
        if game_state["current_step"] != "completed":
            return (
                game_state,
                "I'm not expecting a completion selfie right now. Tap the 'HELP' button if you need assistance.",
            )

        # Calculate completion time
        elapsed_time = time.time() - game_state["start_time"]
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_display = (
            f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        )

        # Save the uploaded selfie if available
        if selfie_data:
            success, file_path = save_image_locally(selfie_data)
            if success:
                logger.info(f"Saved completion selfie to {file_path}")
            else:
                logger.error("Failed to save completion selfie")

        # Generate the certificate URL
        certificate_url = generate_certificate_url(game_state, time_display)

        # Store completion message with token information
        message = (
            f"🎉 Congratulations! Finish time: {time_display}!🎉 \n\n"
            f"You've successfully completed all the puzzles in the hunt!\n\n"
            f"🪙 Your final token balance: {game_state['tokens_earned']} tokens 🪙\n\n"
            f"🏆 [View and download your completion certificate]({certificate_url}) 🏆\n\n"
            f"Thank you for playing! We hope you had a great time!\n\n"
            f"Tap ARRIVED to play again.\n\n"
            f"We'd love your feedback! Fill out our form here: https://forms.gle/xdQYDReAz3KLow476"
        )

        # Reset game state
        new_game_state = {
            "game_started": False,
            "current_location_index": 0,
            "current_step": "not_started",
            "completed_locations": [],
            "puzzle_attempts": 0,
            "hints_used": 0,
            "start_time": None,
            "messages": [{"role": "assistant", "content": message}],
            # Preserve token records for the final display
            "final_tokens_earned": game_state["tokens_earned"],
            "final_token_transactions": game_state.get("token_transactions", []),
            "final_completion_time": time_display,
            # Reset current token tracking
            "tokens_earned": 0,
            "token_transactions": [],
        }

        return new_game_state, message
    except Exception as e:
        logger.error(f"Error handling completion selfie: {str(e)}")
        return (
            game_state,
            "Sorry, there was an error processing your completion. Please try again or tap the 'HELP' button.",
        )

def give_hint(game_state):
    """Give a hint for the current puzzle and deduct tokens"""
    try:
        # Ensure tokens_earned exists with a default value
        if "tokens_earned" not in game_state:
            game_state["tokens_earned"] = 0
            
        if game_state["current_step"] != "solving_puzzle":
            return (
                game_state,
                "Hints are only available when solving puzzles. Tap the 'HELP' button if you need assistance.",
            )

        current_location = GAME_DATA["locations"][game_state["current_location_index"]]
        current_question = current_location["puzzle"]["question"]
        
        # Initialize hints_used and previous_hints if not present
        if "hints_used" not in game_state:
            game_state["hints_used"] = 0
        if "previous_hints" not in game_state:
            game_state["previous_hints"] = []
            
        # Get the appropriate hint based on hints_used counter
        hints_used = game_state["hints_used"]
        hint_key = f"hint{hints_used + 1}"
        
        # Check if this hint exists
        if hint_key in current_location["puzzle"]:
            # Deduct tokens for using a hint
            token_penalty = TOKEN_PENALTY_HINT
            game_state["tokens_earned"] = max(0, game_state["tokens_earned"] - token_penalty)  # Ensure balance doesn't go negative
            
            # Record token transaction
            transaction = {
                "type": "penalty",
                "amount": -token_penalty,  # Negative to indicate deduction
                "reason": f"Used hint for {current_location['name']}",
                "timestamp": time.time()
            }
            game_state.setdefault("token_transactions", []).append(transaction)
            
            # Apply token penalty - penalties are only tracked in UI, not actually transferred
            if SOLANA_ENABLED:
                transaction["tx_info"] = "Penalty applied (not transferred)"
                transaction["success"] = True
            
            hint = current_location["puzzle"][hint_key]
            game_state["hints_used"] += 1
            
            # Add hint to previous_hints
            game_state["previous_hints"].append(hint)
            
            # Show how many hints are left
            hints_remaining = 3 - game_state["hints_used"]
            hint_status = f" ({hints_remaining} hint{'s' if hints_remaining != 1 else ''} remaining)"
            
            # Response with token information
            response = (
                f"Hint: {hint}{hint_status}\n\n"
                f"💸 You spent {token_penalty} tokens for this hint. Current balance: {game_state['tokens_earned']} tokens."
            )
            
            return game_state, response
        else:
            # If no specific hint exists, use the general hint
            if "hint" in current_location["puzzle"] and game_state["hints_used"] == 0:
                # Deduct tokens for using a hint
                token_penalty = TOKEN_PENALTY_HINT
                game_state["tokens_earned"] = max(0, game_state["tokens_earned"] - token_penalty)  # Ensure balance doesn't go negative
                
                # Record token transaction
                transaction = {
                    "type": "penalty",
                    "amount": -token_penalty,  # Negative to indicate deduction
                    "reason": f"Used hint for {current_location['name']}",
                    "timestamp": time.time()
                }
                game_state.setdefault("token_transactions", []).append(transaction)
                
                hint = current_location["puzzle"]["hint"]
                game_state["hints_used"] += 1
                game_state["previous_hints"].append(hint)
                
                # Show how many hints are left
                hints_remaining = 3 - game_state["hints_used"]
                hint_status = f" ({hints_remaining} hint{'s' if hints_remaining != 1 else ''} remaining)"
                
                # Response with token information
                response = (
                    f"Hint: {hint}{hint_status}\n\n"
                    f"💸 You spent {token_penalty} tokens for this hint. Current balance: {game_state['tokens_earned']} tokens."
                )
                
                return game_state, response
                
            # If all hints have been used
            elif game_state["previous_hints"]:
                last_hint = game_state["previous_hints"][-1]
                return (
                    game_state,
                    f"You've used all available hints. Last hint was: {last_hint}"
                )
            else:
                return (
                    game_state,
                    "No hints available for this puzzle. Try your best guess!"
                )
    except Exception as e:
        logger.error(f"Error giving hint: {str(e)}")
        return (
            game_state,
            "Sorry, there was an error providing a hint. Please try again or tap the 'HELP' button.",
        )

def handle_help_command(game_state):
    """Handle the help command"""
    try:
        # Ensure tokens_earned exists with a default value
        if "tokens_earned" not in game_state:
            game_state["tokens_earned"] = 0
            
        if not game_state["game_started"]:
            return (
                game_state,
                "Welcome to the Culture Date! Tap the 'ARRIVED' button to begin your adventure.",
            )

        if game_state["current_step"] == "finding_location":
            current_location = GAME_DATA["locations"][
                game_state["current_location_index"]
            ]
            message = (
                f"You're currently heading to {current_location['name']}. "
                f"When you arrive, tap the 'ARRIVED' button to confirm.\n\n"
                f"🪙 Current token balance: {game_state.get('tokens_earned', 0)} tokens"
            )

        elif game_state["current_step"] == "solving_puzzle":
            current_location = GAME_DATA["locations"][
                game_state["current_location_index"]
            ]
            remaining_attempts = MAX_PUZZLE_ATTEMPTS - game_state["puzzle_attempts"]
            message = (
                f"You're at {current_location['name']} solving a puzzle. "
                f"Tap the 'HINT' button for a hint (costs {TOKEN_PENALTY_HINT} tokens). You have {remaining_attempts} attempts left.\n\n"
                f"🪙 Current token balance: {game_state.get('tokens_earned', 0)} tokens"
            )

        elif game_state["current_step"] == "completed":
            message = (
                f"You've completed all locations! Please upload a selfie at the final location to receive your certificate.\n\n"
                f"🪙 Current token balance: {game_state.get('tokens_earned', 0)} tokens"
            )

        else:
            message = (
                f"Something went wrong. Tap the 'ARRIVED' button to begin again.\n\n"
                f"🪙 Current token balance: {game_state.get('tokens_earned', 0)} tokens"
            )

        return game_state, message
    except Exception as e:
        logger.error(f"Error handling help command: {str(e)}")
        return (
            game_state,
            "Welcome to the Culture Date! Tap the 'ARRIVED' button to begin your adventure.",
        )

def get_progress_summary(game_state):
    """Generate a summary of the user's current progress including token balance"""
    try:
        if not game_state["game_started"]:
            return (
                game_state,
                "You haven't started the game yet. Tap the 'ARRIVED' button to begin.",
            )

        total_locations = len(GAME_DATA["locations"])
        completed_locations = len(game_state["completed_locations"])
        current_index = game_state["current_location_index"]
        current_location = GAME_DATA["locations"][current_index]["name"]
        tokens_earned = game_state.get("tokens_earned", 0)

        message = (
            f"Progress Summary:\n"
            f"- Locations completed: {completed_locations}/{total_locations}\n"
            f"- Current Location: {current_location}\n"
            f"- 🪙 Token Balance: {tokens_earned} tokens\n"
            f"Tap the 'HELP' button for assistance with your current task."
        )

        return game_state, message
    except Exception as e:
        logger.error(f"Error getting progress summary: {str(e)}")
        return (
            game_state,
            "Sorry, there was an error retrieving your progress. Tap the 'HELP' button for assistance.",
        )

def convert_text_to_components(text):
    """Convert plain text to components, making URLs clickable."""
    # URL regex pattern
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^)\s]*)?'
    
    # Split the text by URLs
    parts = re.split(f'({url_pattern})', text)
    
    # Convert to components
    components = []
    for i, part in enumerate(parts):
        if i % 2 == 0:  # Text part
            if part:  # Only add if not empty
                components.append(part)
        else:  # URL part
            components.append(html.A(part, href=part, target="_blank", style={"color": "#03E1FF"}))
    
    return components

# Add this function to generate appropriate action buttons based on game state
@callback(
    Output("action-buttons-container", "children"),
    Input("game-state", "data"),
)
def update_action_buttons(game_state):
    try:
        # Parse game_state if needed
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                logger.error("Game state is a string and not valid JSON in update_action_buttons")
                game_state = {}
                
        # Initialize buttons list
        buttons = []
        
        # Style constants for Web3 buttons - Updated with Solana colors
        button_style = {
            "margin": "5px", 
            "padding": "12px",
            "fontSize": "18px",
            "borderRadius": "50%", # Make buttons circular for icons
            "width": "55px",
            "height": "55px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "border": "1px solid rgba(153, 69, 255, 0.3)",
            "backgroundColor": "rgba(35, 35, 51, 0.7)",
            "color": "white",
            "backdropFilter": "blur(5px)",
            "boxShadow": "0 4px 12px rgba(0, 0, 0, 0.15)",
            "transition": "all 0.3s ease",
        }
        
        # Different button colors based on action type
        arrived_style = {**button_style, "backgroundColor": "rgba(3, 225, 255, 0.2)", "borderColor": "#03E1FF"}
        hint_style = {**button_style, "backgroundColor": "rgba(20, 241, 149, 0.2)", "borderColor": "#14F195"}
        help_style = {**button_style, "backgroundColor": "rgba(153, 69, 255, 0.2)", "borderColor": "#9945FF"}
        
        # Game state dependent buttons
        if not game_state or not game_state.get("game_started", False):
            buttons.append(
                dbc.Button(
                    html.I(className="fas fa-map-marker-alt"), 
                    id={"type": "action-button", "action": "arrived"}, 
                    color=None, 
                    className="action-button arrived-button",
                    style=arrived_style,
                    title="Arrived"
                )
            )
            buttons.append(
                dbc.Button(
                    html.I(className="fas fa-question-circle"), 
                    id={"type": "action-button", "action": "help"}, 
                    color=None, 
                    className="action-button help-button",
                    style=help_style,
                    title="Help"
                )
            )
            return buttons
        
        # For active game, show buttons based on current step
        if game_state.get("current_step") == "finding_location":
            buttons.append(
                dbc.Button(
                    html.I(className="fas fa-map-marker-alt"), 
                    id={"type": "action-button", "action": "arrived"}, 
                    color=None, 
                    className="action-button arrived-button",
                    style=arrived_style,
                    title="Arrived"
                )
            )
        
        # Add HINT button when in solving_puzzle step
        elif game_state.get("current_step") == "solving_puzzle":
            hints_used = game_state.get("hints_used", 0)
            if hints_used < 3:
                buttons.append(
                    dbc.Button(
                        html.I(className="fas fa-lightbulb"), 
                        id={"type": "action-button", "action": "hint"}, 
                        color=None, 
                        className="action-button hint-button",
                        style=hint_style,
                        title="Hint"
                    )
                )
        
        # Always add HELP button for active game
        buttons.append(
            dbc.Button(
                html.I(className="fas fa-question-circle"), 
                id={"type": "action-button", "action": "help"}, 
                color=None, 
                className="action-button help-button",
                style=help_style,
                title="Help"
            )
        )
        
        return buttons
        
    except Exception as e:
        # Log the error
        logger.error(f"Error updating action buttons: {str(e)}")
        # Return minimal buttons in case of error
        return [
            dbc.Button(
                html.I(className="fas fa-question-circle"), 
                id={"type": "action-button", "action": "help"}, 
                color="secondary", 
                className="action-button",
                style=button_style
            )
        ]

def reset_game_state():
    """Reset all game-related state variables"""
    try:
        # Create a clean game state
        game_state = {
            "game_started": False,
            "start_time": None,
            "current_location_index": 0,
            "current_step": "not_started",
            "completed_locations": [],
            "puzzle_attempts": 0,
            "hints_used": 0,
            "messages": [],
            # Token reward tracking
            "tokens_earned": 0,
            "token_transactions": [],
        }

        return game_state
    except Exception as e:
        logger.error(f"Error resetting game state: {str(e)}")
        return {
            "game_started": False,
            "messages": [
                {
                    "role": "assistant",
                    "content": "Game reset due to an error. Please start again.",
                }
            ],
        }

def get_message_icon(role, content):
    """Return appropriate icon based on message content and role"""
    if role == 'user':
        return "👤"
    elif "arrived" in content.lower():
        return "📍"
    elif "correct" in content.lower():
        return "✅"
    elif "hint" in content.lower():
        return "💡"
    elif "token" in content.lower() and "earned" in content.lower():
        return "🪙"
    else:
        return "🤖"

def get_message_color(role, content):
    """Return appropriate color based on message content and role"""
    if role == 'user':
        return '#232333', '#848895'  # Dark background, gray avatar
    elif "hint" in content.lower():
        return 'rgba(3, 225, 255, 0.1)', '#03E1FF'  # Blue for hints
    elif "token" in content.lower() and "earned" in content.lower():
        return 'rgba(20, 241, 149, 0.1)', '#14F195'  # Green for token rewards
    else:
        return 'rgba(153, 69, 255, 0.1)', '#9945FF'  # Purple for default assistant colors

def is_action_locked(game_state, action_type):
    """Check if an action is currently locked (prevent rapid updates)"""
    now = time.time()
    
    # Handle case where game_state is a string
    if isinstance(game_state, str):
        try:
            # Try to parse it as JSON
            game_state = json.loads(game_state)
        except json.JSONDecodeError:
            # If it's not valid JSON, assume no locks
            return False
    
    # Create action_locks if it doesn't exist
    if not game_state or "action_locks" not in game_state:
        return False  # Don't lock if there's no state to check against
    
    action_locks = game_state.get("action_locks", {})
    
    # Get last action time
    last_action_time = action_locks.get(action_type, 0)
    
    # If action was performed less than 2 seconds ago, lock it
    if now - last_action_time < 2:
        return True
        
    # Don't modify game_state here - modifications should happen
    # in the callback where we return new state
    return False

def handle_user_input(game_state, user_input):
    """Process user input and return appropriate response and updated game state"""
    try:
        # Handle case where game_state is a string
        if isinstance(game_state, str):
            try:
                # Try to parse it as JSON
                game_state_parsed = json.loads(game_state)
                # If parsing succeeded, use the parsed dict instead
                game_state = game_state_parsed
            except json.JSONDecodeError:
                # If it's not valid JSON, create a default game state
                logger.error("Game state is a string and not valid JSON in handle_user_input")
                game_state = {"game_started": False, "messages": []}
    
        # Validate game state
        game_state = validate_game_state(game_state)

        # Return early if no input or game_state
        if not user_input or not game_state:
            return game_state, "Please provide input"

        user_input_lower = user_input.lower().strip()
        # Check for action lock to prevent duplicate processing
        if is_action_locked(game_state, user_input_lower):
            logger.info(f"Action '{user_input_lower}' is locked (processed too recently)")
            return game_state, "Processing previous command..."
            
        logger.info(f"Processing user input: '{user_input_lower}', game_started: {game_state.get('game_started', False)}")
        
        # Handle "arrived" differently based on game state
        if user_input_lower == "arrived":
            if not game_state.get("game_started", False):
                new_game_state, response = start_hunt()
            else:
                new_game_state, response = handle_location_arrival(game_state)

        # Help command
        elif user_input_lower in ["help", "assistance", "?"]:
            new_game_state, response = handle_help_command(game_state)

        # Hint command
        elif user_input_lower in ["hint", "clue", "help me"]:
            new_game_state, response = give_hint(game_state)

        # Restart command
        elif user_input_lower in ["restart", "reset", "new game"]:
            new_game_state, response = start_hunt()

        # Progress command
        elif user_input_lower in ["progress", "status", "where am i"]:
            new_game_state, response = get_progress_summary(game_state)
            
        # Token balance command
        elif user_input_lower in ["tokens", "balance", "my tokens", "token balance", "check tokens"]:
            token_balance = game_state.get("tokens_earned", 0)
            token_transactions = game_state.get("token_transactions", [])
            response = (
                f"💰 Your current token balance is: {token_balance} tokens\n\n"
                f"Recent token activity:\n"
            )
            
            # Show last 3 transactions if any
            if token_transactions:
                for i, tx in enumerate(token_transactions[-3:]):
                    tx_type = tx.get("type", "")
                    amount = tx.get("amount", 0)
                    reason = tx.get("reason", "")
                    response += f"• {'+' if amount > 0 else ''}{amount} tokens - {reason}\n"
            else:
                response += "No token activity yet."
                
            if not SOLANA_ENABLED:
                response += "\n\nNote: Solana integration is not currently enabled."
                
            new_game_state = game_state

        # Game start commands
        elif not game_state.get("game_started", False) and user_input_lower in [
            "hello", "travel trackie", "traveltrackie", "start hunt", 
            "start trail", "start", "begin", "play"
        ]:
            new_game_state, response = start_hunt()

        # Handle location arrival alternatives
        elif game_state.get("game_started", False) and user_input_lower in ["i'm here", "im here", "here", "made it"]:
            new_game_state, response = handle_location_arrival(game_state)

        # Handle puzzle answers when in solving_puzzle step
        elif game_state.get("current_step") == "solving_puzzle":
            new_game_state, response = handle_puzzle_answer(game_state, user_input)

        # New user or unrecognized command
        else:
            if not game_state.get("game_started", False):
                response = "Welcome to the Culture Date! Tap the 'ARRIVED' button to begin your adventure."
                new_game_state = game_state
            else:
                response = "I didn't understand that message. Tap the 'HELP' button for assistance with your current task."
                new_game_state = game_state

        # Update messages in game state
        if not new_game_state.get("messages"):
            new_game_state["messages"] = []
        
        MAX_MESSAGES = 5
        
        # Add user message to messages
        new_game_state["messages"].append({"role": "user", "content": user_input})
        
        # FIXED: Initialize already_added to False by default
        already_added = False
        
        # Check if response is already in messages before adding
        if new_game_state.get("messages"):
            last_message = new_game_state["messages"][-1] if new_game_state["messages"] else None
            if last_message and last_message.get("role") == "assistant" and last_message.get("content") == response:
                already_added = True
        
        # Only add assistant message if not already added
        if not already_added:
            # If adding this would exceed MAX_MESSAGES, remove oldest
            if len(new_game_state["messages"]) >= MAX_MESSAGES:
                new_game_state["messages"] = new_game_state["messages"][-MAX_MESSAGES+1:]
            new_game_state["messages"].append({"role": "assistant", "content": response})
        
        # Validate the updated game state before returning
        new_game_state = validate_game_state(new_game_state)

        # Ensure game state is JSON serializable before returning
        sanitized_state = sanitize_for_json(new_game_state)
        
        # Extra validation to ensure the sanitized state is actually JSON serializable
        if not is_json_serializable(sanitized_state):
            logger.error("Sanitized game state is still not JSON serializable!")
            # Create a simpler fallback state that we know is serializable
            sanitized_state = {
                "game_started": new_game_state.get("game_started", False),
                "current_step": new_game_state.get("current_step", "not_started"),
                "messages": [{"role": "assistant", "content": response}],
                "tokens_earned": new_game_state.get("tokens_earned", 0)
            }
            
        return sanitized_state, response
    except Exception as e:
        logger.error(f"Error handling user input: {str(e)}")
        # Create an error state we're sure is serializable
        error_state = {
            "game_started": False if not isinstance(game_state, dict) else game_state.get("game_started", False),
            "current_step": "not_started",
            "messages": [{"role": "assistant", "content": "Sorry, there was an error processing your message. Please try again."}],
            "tokens_earned": 0
        }
        return error_state, "Sorry, there was an error processing your message. Please try again."

# callback to handle button clicks
@callback(
    [Output("game-state", "data", allow_duplicate=True),
     Output("button-clicks-memory", "data")],
    [Input({"type": "action-button", "action": ALL}, "n_clicks")],
    [State("game-state", "data"), State("session-id", "data"), State("button-clicks-memory", "data")],
    prevent_initial_call=True,
)
def handle_action_buttons(button_clicks, game_state, session_id, button_memory):
    try:
        # Check if this is actually triggered by a real click
        ctx_triggered = dash.callback_context.triggered
        if not ctx_triggered or ctx_triggered[0]['value'] is None:
            # Don't log this as error since it's expected behavior
            return dash.no_update, dash.no_update  # Use no_update instead of raising PreventUpdate
            
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            return dash.no_update, dash.no_update
            
        # Handle case where game_state is None
        if game_state is None:
            game_state = {"game_started": False, "messages": []}
        
        # Handle case where game_state is a string
        if isinstance(game_state, str):
            try:
                # Try to parse it as JSON
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                # If it's not valid JSON, create a default game state
                logger.error("Game state is a string and not valid JSON in handle_action_buttons")
                game_state = {"game_started": False, "messages": []}
        
        # IMPORTANT: Validate the game state
        game_state = validate_game_state(game_state)
        
        action = triggered_id.get("action")
        if not action:
            return dash.no_update, dash.no_update
            
        # Handle case where button_memory is None or a string
        if button_memory is None:
            button_memory = {}
        elif isinstance(button_memory, str):
            try:
                button_memory = json.loads(button_memory)
            except json.JSONDecodeError:
                button_memory = {}
        
        now = time.time()
        last_click_time = button_memory.get(action, 0)
        if now - last_click_time < 2:
            # Rate limiting to prevent duplicate actions
            return dash.no_update, dash.no_update
            
        # Create a new dictionary instead of modifying in place
        new_button_memory = button_memory.copy() if isinstance(button_memory, dict) else {}
        new_button_memory[action] = now
        
        logger.info(f"Processing button action: {action}")
        updated_game_state, _ = handle_user_input(game_state, action)
        
        # Validate the updated game state
        updated_game_state = validate_game_state(updated_game_state)
        
        if session_id and (
            updated_game_state.get("current_step") != game_state.get("current_step") or
            updated_game_state.get("current_location_index") != game_state.get("current_location_index")
        ):
            save_game_state_locally(session_id, updated_game_state)
        
        return updated_game_state, new_button_memory
    except Exception as e:
        if not isinstance(e, dash.exceptions.PreventUpdate):
            # Only log real errors, not PreventUpdate exceptions
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Unhandled error in action button callback: {str(e)}\n{error_details}")
        # Return a safe fallback state
        return {"game_started": False, "messages": [{"role": "assistant", "content": "An error occurred. Please refresh the page."}]}, {}

# Update toggle_menu callback 
@callback(
    Output("side-menu", "style"),
    [Input("hamburger-icon", "n_clicks"), 
     Input("close-menu", "n_clicks"),
     Input("side-menu-overlay", "n_clicks")],  # Add overlay for closing
    State("side-menu", "style"),
    prevent_initial_call=True,
)
def toggle_menu(hamburger_clicks, close_clicks, overlay_clicks, current_style):
    # Initialize current_style if None
    if current_style is None:
        current_style = {"position": "fixed", "top": "0", "left": "-300px", "width": "300px", 
                        "height": "100%", "backgroundColor": "rgba(35, 35, 51, 0.9)", 
                        "backdropFilter": "blur(10px)", "boxShadow": "3px 0 15px rgba(153, 69, 255, 0.3)", 
                        "zIndex": "1000", "transition": "left 0.3s ease-in-out"}
    
    ctx_triggered = dash.callback_context.triggered
    if not ctx_triggered:
        return current_style
        
    trigger_id = ctx_triggered[0]["prop_id"].split(".")[0]
    
    if trigger_id == "hamburger-icon":
        current_style["left"] = "0px"
    elif trigger_id in ["close-menu", "side-menu-overlay"]:  
        current_style["left"] = "-300px"
    
    return current_style
    
# Add custom CSS with Solana colors
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
    :root {
        --solana-purple: #9945FF;
        --solana-teal: #14F195;
        --solana-blue: #03E1FF;
        --solana-dark: #232333;
        --solana-gray: #848895;
        --solana-gradient: linear-gradient(90deg, #9945FF 0%, #14F195 50%, #03E1FF 100%);
    }
    
    body {
        font-family: 'Roboto', sans-serif;
        background-color: #000000;
        color: white;
        line-height: 1.6;
    }
    
    /* Redesigned card style with glassmorphic effect */
    .card {
        background-color: rgba(35, 35, 51, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        margin-bottom: 12px;
        overflow: hidden;
        border: 1px solid rgba(153, 69, 255, 0.2);
    }
    
    .card-header {
        background-color: rgba(35, 35, 51, 0.8);
        padding: 15px 20px;
        border-bottom: 1px solid rgba(153, 69, 255, 0.3);
        font-weight: 500;
    }
    
    .card-body {
        padding: 20px;
        color: #e0e0e0;
    }
    
    /* Web3-styled chat container */
    .chat-container {
        height: 350px;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(153, 69, 255, 0.4);
        background: rgba(35, 35, 51, 0.8);
        backdrop-filter: blur(15px);
    }
    
    .chat-messages {
        padding: 15px 20px;
        overflow-y: auto;
        height: calc(100% - 60px);
        background-color: rgba(35, 35, 51, 0.7);
    }
    
    .chat-input-container {
        background-color: rgba(35, 35, 51, 0.9);
        padding: 15px;
        border-top: 1px solid rgba(153, 69, 255, 0.4);
    }

    /* Accordion styles with Web3 theme */
    .accordion-item {
        border-bottom: 1px solid rgba(153, 69, 255, 0.2);
        margin-bottom: 10px;
    }
    
    .accordion-button {
        cursor: pointer;
        padding: 12px 15px;
        background-color: rgba(35, 35, 51, 0.8);
        border-radius: 8px;
        position: relative;
        transition: all 0.3s ease;
        color: white;
        border: 1px solid rgba(153, 69, 255, 0.3);
    }
    
    .accordion-button::after {
        content: "+";
        position: absolute;
        right: 15px;
        color: var(--solana-purple);
    }
    
    .accordion-button.active::after {
        content: "-";
        color: var(--solana-teal);
    }
    
    .accordion-button:hover {
        background-color: rgba(153, 69, 255, 0.2);
        border-color: rgba(153, 69, 255, 0.5);
    }
    
    .accordion-content {
        padding: 0 15px 15px 15px;
        display: none;
        background-color: rgba(35, 35, 51, 0.4);
        border-radius: 0 0 8px 8px;
        animation: fadeIn 0.3s ease-in-out;
    }
    
    .accordion-content.active {
        display: block;
    }
    
    /* Animations for Web3 UI */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(153, 69, 255, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(153, 69, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(153, 69, 255, 0); }
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    @keyframes glow {
        0% { box-shadow: 0 0 5px rgba(153, 69, 255, 0.5); }
        50% { box-shadow: 0 0 15px rgba(153, 69, 255, 0.8); }
        100% { box-shadow: 0 0 5px rgba(153, 69, 255, 0.5); }
    }
    
    /* Enhanced action buttons - DIFFERENT COLORS */
    .action-button {
        margin: 5px;
        border-radius: 50%;
        font-weight: 500;
        transition: all 0.3s ease;
        background: rgba(35, 35, 51, 0.8);
        backdrop-filter: blur(5px);
        border: 1px solid rgba(153, 69, 255, 0.3);
        color: white;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
        width: 55px;
        height: 55px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .action-button::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: var(--solana-gradient);
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: -1;
        background-size: 200% 200%;
    }
    
    .action-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 15px rgba(153, 69, 255, 0.4);
        border: 1px solid rgba(153, 69, 255, 0.6);
    }
    
    .action-button:hover::before {
        opacity: 0.2;
        animation: gradientShift 3s ease infinite;
    }
    
    .action-button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 5px rgba(153, 69, 255, 0.4);
    }
    
    /* Button variations with DIFFERENT COLORS */
    .arrived-button {
        background: rgba(3, 225, 255, 0.2);
        border-color: var(--solana-blue);
    }
    
    .arrived-button:hover {
        background: rgba(3, 225, 255, 0.3);
        border-color: var(--solana-blue);
        box-shadow: 0 4px 15px rgba(3, 225, 255, 0.4);
    }
    
    .hint-button {
        background: rgba(20, 241, 149, 0.2);
        border-color: var(--solana-teal);
    }
    
    .hint-button:hover {
        background: rgba(20, 241, 149, 0.3);
        border-color: var(--solana-teal);
        box-shadow: 0 4px 15px rgba(20, 241, 149, 0.4);
    }
    
    .help-button {
        background: rgba(153, 69, 255, 0.2);
        border-color: var(--solana-purple);
    }
    
    .help-button:hover {
        background: rgba(153, 69, 255, 0.3);
        border-color: var(--solana-purple);
        box-shadow: 0 4px 15px rgba(153, 69, 255, 0.4);
    }
    
    /* Enhanced progress bar */
    .progress {
        height: 10px;
        border-radius: 5px;
        background-color: rgba(35, 35, 51, 0.5);
        overflow: hidden;
        margin-bottom: 15px;
        backdrop-filter: blur(5px);
        border: 1px solid rgba(153, 69, 255, 0.2);
    }
    
    .progress-bar {
        background: var(--solana-gradient);
        background-size: 200% 200%;
        animation: gradientShift 3s ease infinite;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(153, 69, 255, 0.5);
    }
    
    /* Better audio player */
    .audio-player {
        width: 100%;
        border-radius: 12px;
        overflow: hidden;
        background-color: rgba(35, 35, 51, 0.7);
        border: 1px solid rgba(153, 69, 255, 0.3);
        padding: 10px;
        margin-bottom: 15px;
    }
    
    .audio-player-header {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .audio-player-title {
        margin: 0;
        margin-left: 10px;
        font-size: 16px;
        font-weight: 500;
        color: var(--solana-purple);
    }
    
    .audio-controls {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .play-button {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: var(--solana-gradient);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 0 10px rgba(153, 69, 255, 0.5);
        margin-right: 10px;
    }
    
    .progress-bar-container {
        flex-grow: 1;
        height: 8px;
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        overflow: hidden;
        margin: 0 10px;
    }
    
    .time-display {
        font-size: 12px;
        color: var(--solana-gray);
        min-width: 45px;
        text-align: center;
    }
    
    /* Question styling */
    .question-box {
        background-color: rgba(3, 225, 255, 0.1);
        border-left: 4px solid var(--solana-blue);
        padding: 15px;
        margin: 15px 0;
        border-radius: 0 8px 8px 0;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    
    .hint-box {
        background-color: rgba(20, 241, 149, 0.1);
        border-left: 4px solid var(--solana-teal);
        padding: 12px 15px;
        margin: 10px 0;
        border-radius: 0 8px 8px 0;
        font-style: italic;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    
    /* Token display styling */
    .token-display {
        display: flex;
        align-items: center;
        background: linear-gradient(135deg, rgba(153, 69, 255, 0.15), rgba(3, 225, 255, 0.15));
        padding: 8px 15px;
        border-radius: 20px;
        font-weight: bold;
        color: white;
        margin-left: 10px;
        box-shadow: 0 0 10px rgba(153, 69, 255, 0.3);
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .token-display:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(153, 69, 255, 0.5);
    }
    
    .token-count {
        margin-left: 8px;
        background: var(--solana-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
    }
    
    /* Enhanced input field styling */
    .form-control {
        background-color: rgba(35, 35, 51, 0.85);
        border: 2px solid rgba(153, 69, 255, 0.5);
        color: white;
        border-radius: 20px;
        padding: 12px 15px;
        font-weight: 500;
        box-shadow: 0 0 10px rgba(153, 69, 255, 0.2);
    }
    
    .form-control::placeholder {
        color: rgba(255, 255, 255, 0.7);
    }
    
    .form-control:focus {
        background-color: rgba(35, 35, 51, 0.95);
        border-color: var(--solana-purple);
        color: white;
        box-shadow: 0 0 15px rgba(153, 69, 255, 0.4);
    }
    
    /* Links styling */
    a {
        color: var(--solana-blue);
        text-decoration: none;
        transition: all 0.2s ease;
    }
    
    a:hover {
        color: var(--solana-teal);
        text-decoration: none;
    }
    
    /* Button group styling */
    .btn-group {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* File upload styling */
    .upload-box {
        border: 2px dashed rgba(153, 69, 255, 0.5);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        background-color: rgba(35, 35, 51, 0.4);
        transition: all 0.3s ease;
    }
    
    .upload-box:hover {
        border-color: var(--solana-purple);
        background-color: rgba(153, 69, 255, 0.1);
    }
    
    /* More colorful token wallet */
    .token-wallet {
        background: linear-gradient(135deg, rgba(153, 69, 255, 0.2), rgba(3, 225, 255, 0.2));
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 0 20px rgba(153, 69, 255, 0.3);
        transition: all 0.3s ease;
    }
    
    .token-wallet:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(153, 69, 255, 0.5);
    }
    
    .token-wallet-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px;
        background: linear-gradient(90deg, rgba(35, 35, 51, 0.9), rgba(153, 69, 255, 0.2));
        border-bottom: 1px solid rgba(3, 225, 255, 0.4);
    }
    
    .wallet-title {
        display: flex;
        align-items: center;
    }
    
    .wallet-icon {
        font-size: 22px;
        margin-right: 12px;
        color: var(--solana-teal);
    }
    
    .wallet-balance {
        display: flex;
        align-items: baseline;
    }
    
    .balance-amount {
        font-size: 32px;
        font-weight: bold;
        background: var(--solana-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
    }
    
    .balance-currency {
        color: white;
        font-size: 18px;
        margin-left: 5px;
    }
    
    .transaction-history {
        padding: 10px;
    }
    
    .transaction-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px;
        border-bottom: 1px solid rgba(153, 69, 255, 0.2);
        border-left: 3px solid transparent;
    }
    
    .transaction-positive {
        border-left-color: var(--solana-teal);
    }
    
    .transaction-negative {
        border-left-color: #FF5757;
    }
    
    .transaction-info {
        display: flex;
        align-items: center;
    }
    
    .transaction-icon {
        margin-right: 10px;
        color: var(--solana-teal);
    }
    
    .transaction-icon.negative {
        color: #FF5757;
    }
    
    .transaction-amount {
        font-weight: bold;
    }
    
    .transaction-amount.positive {
        color: var(--solana-teal);
    }
    
    .transaction-amount.negative {
        color: #FF5757;
    }
    
    /* Send button with icon */
    #send-button {
        background: var(--solana-teal);
        color: var(--solana-dark);
        font-weight: bold;
        border: none;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        font-size: 20px;
    }
    
    #send-button:hover {
        background: linear-gradient(45deg, var(--solana-purple), var(--solana-teal));
        box-shadow: 0 0 15px rgba(20, 241, 149, 0.5);
        transform: translateY(-2px) rotate(15deg);
    }
    
    #send-button:active {
        transform: translateY(1px);
    }
    
    /* Journey progress card */
    .journey-progress {
        background-color: rgba(35, 35, 51, 0.8);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(153, 69, 255, 0.3);
        margin-bottom: 15px;
    }
    
    .journey-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    
    .journey-title {
        display: flex;
        align-items: center;
    }
    
    .journey-icon {
        color: var(--solana-blue);
        margin-right: 10px;
        font-size: 18px;
    }
    
    /* Game chat redesign */
    .game-chat {
        background-color: rgba(35, 35, 51, 0.8);
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(153, 69, 255, 0.3);
        margin-bottom: 15px;
    }
    
    .chat-header {
        display: flex;
        align-items: center;
        padding: 15px;
        background: linear-gradient(90deg, rgba(153, 69, 255, 0.2), rgba(3, 225, 255, 0.1));
        border-bottom: 1px solid rgba(153, 69, 255, 0.3);
    }
    
    .chat-icon {
        color: var(--solana-purple);
        margin-right: 10px;
        font-size: 18px;
    }
    
    /* Actions container */
    .actions-container {
        display: flex;
        justify-content: center;
        padding: 15px;
        background-color: rgba(35, 35, 51, 0.8);
        border-radius: 12px;
        border: 1px solid rgba(153, 69, 255, 0.3);
        margin-bottom: 15px;
    }
    
    /* Task container */
    .task-container {
        background-color: rgba(35, 35, 51, 0.8);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(153, 69, 255, 0.3);
        margin-bottom: 15px;
    }
    
    .task-header {
        display: flex;
        align-items: center;
        margin-bottom: 15px;
    }
    
    .task-icon {
        color: var(--solana-teal);
        margin-right: 10px;
        font-size: 18px;
    }
    
    /* Hamburger menu and sidebar */
    #hamburger-icon {
        position: absolute;
        top: 20px;
        left: 20px;
        font-size: 24px;
        color: var(--solana-purple);
        background: rgba(35, 35, 51, 0.8);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 1000;
        box-shadow: 0 0 10px rgba(153, 69, 255, 0.5);
        transition: all 0.3s ease;
    }
    
    #hamburger-icon:hover {
        transform: scale(1.1);
        color: var(--solana-blue);
        box-shadow: 0 0 15px rgba(3, 225, 255, 0.6);
    }
    
    #side-menu {
        position: fixed;
        top: 0;
        left: -300px;
        width: 300px;
        height: 100%;
        background-color: rgba(35, 35, 51, 0.9);
        backdrop-filter: blur(10px);
        box-shadow: 3px 0 15px rgba(153, 69, 255, 0.3);
        z-index: 1000;
        transition: left 0.3s ease-in-out;
        color: white;
        overflow-y: auto;
    }
    
    /* Improved mobile styling */
    @media (max-width: 768px) {
        .card {
            margin-bottom: 8px;
        }
        
        .chat-container {
            height: 350px;
        }
        
        /* Make sure all content divs take full width */
        .main-content > div {
            width: 100% !important;
            margin-bottom: 15px;
        }
        
        /* Ensure proper padding on mobile */
        .card-body {
            padding: 15px;
        }
        
        /* Make sure map is visible */
        iframe {
            width: 100% !important;
            height: 300px !important;
        }

        #side-menu {
            width: 85%;  /* Wider on mobile */
            max-width: 300px;
        }
        
        /* Adjust hamburger position on mobile */
        #hamburger-icon {
            top: 15px;
            left: 15px;
        }
        
        /* Make buttons more prominent on mobile */
        .action-button {
            width: 65px;
            height: 65px;
            font-size: 24px;
        }
        
        /* Better spacing for token display on mobile */
        .token-display {
            margin: 5px 0;
        }
        
        /* Adjust journey header for mobile */
        .journey-header {
            flex-direction: column;
            align-items: flex-start;
        }
        
        .token-display {
            margin-left: 0;
            margin-top: 10px;
        }
    }
    
    /* Client-side mouseleave detection for sidebar */
    #side-menu:hover::before {
        content: '';
        position: absolute;
        top: 0;
        right: -10px;
        width: 10px;
        height: 100%;
        background: transparent;
        z-index: -1;
    }
</style>
    </head>
    <body>
        {%app_entry%}
        
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        
        <script>
            // Define a function to initialize accordions that can be called multiple times
            function initAccordions() {
                document.querySelectorAll('.accordion-button').forEach((button, index) => {
                    // Remove existing listeners to prevent duplicates
                    button.removeEventListener('click', toggleAccordion);
                    // Add new listener
                    button.addEventListener('click', toggleAccordion);
                    
                    // Make the first accordion open by default
                    if (index === 0) {
                        button.classList.add('active');
                        let content = button.nextElementSibling;
                        if (content && content.classList.contains('accordion-content')) {
                            content.style.display = "block";
                        }
                    }
                });
            }
            
            // Separate function for the toggle logic
            function toggleAccordion() {
                this.classList.toggle('active');
                let content = this.nextElementSibling;
                if (content && content.classList.contains('accordion-content')) {
                    if (content.style.display === "block") {
                        content.style.display = "none";
                    } else {
                        content.style.display = "block";
                    }
                }
            }

            // Initialize on DOM load
            document.addEventListener('DOMContentLoaded', function() {
                initAccordions();
                
                // Add mouseleave event listener to side menu
                const sideMenu = document.getElementById('side-menu');
                if (sideMenu) {
                    sideMenu.addEventListener('mouseleave', function() {
                        sideMenu.style.left = "-300px";
                    });
                }
                
                // Initialize custom audio players
                initAudioPlayers();
            });
            
            // Function to initialize audio players
            function initAudioPlayers() {
                const audioElements = document.querySelectorAll('audio');
                
                audioElements.forEach(audio => {
                    // Create custom controls if they don't exist
                    if (!audio.parentNode.classList.contains('audio-player')) {
                        const audioPlayer = document.createElement('div');
                        audioPlayer.className = 'audio-player';
                        
                        const playerHeader = document.createElement('div');
                        playerHeader.className = 'audio-player-header';
                        
                        const playerTitle = document.createElement('h5');
                        playerTitle.className = 'audio-player-title';
                        playerTitle.textContent = 'Audio Guide';
                        
                        const playButton = document.createElement('div');
                        playButton.className = 'play-button';
                        playButton.innerHTML = '<i class="fas fa-play"></i>';
                        
                        playerHeader.appendChild(playButton);
                        playerHeader.appendChild(playerTitle);
                        
                        const controls = document.createElement('div');
                        controls.className = 'audio-controls';
                        
                        const currentTime = document.createElement('div');
                        currentTime.className = 'time-display';
                        currentTime.textContent = '0:00';
                        
                        const progressContainer = document.createElement('div');
                        progressContainer.className = 'progress-bar-container';
                        
                        const progressBar = document.createElement('div');
                        progressBar.className = 'progress-bar';
                        progressBar.style.width = '0%';
                        progressBar.style.height = '100%';
                        progressBar.style.background = 'var(--solana-gradient)';
                        
                        const duration = document.createElement('div');
                        duration.className = 'time-display';
                        duration.textContent = '0:00';
                        
                        progressContainer.appendChild(progressBar);
                        controls.appendChild(currentTime);
                        controls.appendChild(progressContainer);
                        controls.appendChild(duration);
                        
                        audioPlayer.appendChild(playerHeader);
                        audioPlayer.appendChild(controls);
                        
                        // Replace the audio element with our custom player
                        audio.parentNode.insertBefore(audioPlayer, audio);
                        audioPlayer.appendChild(audio);
                        audio.style.display = 'none';
                        
                        // Event listeners
                        playButton.addEventListener('click', function() {
                            if (audio.paused) {
                                audio.play();
                                playButton.innerHTML = '<i class="fas fa-pause"></i>';
                            } else {
                                audio.pause();
                                playButton.innerHTML = '<i class="fas fa-play"></i>';
                            }
                        });
                        
                        audio.addEventListener('timeupdate', function() {
                            const percent = (audio.currentTime / audio.duration) * 100;
                            progressBar.style.width = percent + '%';
                            
                            const mins = Math.floor(audio.currentTime / 60);
                            const secs = Math.floor(audio.currentTime % 60);
                            currentTime.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;
                        });
                        
                        audio.addEventListener('loadedmetadata', function() {
                            const mins = Math.floor(audio.duration / 60);
                            const secs = Math.floor(audio.duration % 60);
                            duration.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;
                        });
                        
                        audio.addEventListener('ended', function() {
                            playButton.innerHTML = '<i class="fas fa-play"></i>';
                        });
                        
                        progressContainer.addEventListener('click', function(e) {
                            const percent = e.offsetX / progressContainer.offsetWidth;
                            audio.currentTime = percent * audio.duration;
                        });
                    }
                });
            }
            
            // Re-initialize after Dash updates (if using clientside callbacks)
            if (window.dash_clientside) {
                window.dash_clientside.callback_context = window.dash_clientside.callback_context || {};
                window.dash_clientside.callback_context.rendered = function() {
                    setTimeout(function() {
                        initAccordions();
                        initAudioPlayers();
                    }, 100); // Small delay to ensure DOM is updated
                    return window.dash_clientside.no_update;
                };
            }
            
            // Additional attempt using MutationObserver to catch Dash updates
            const observer = new MutationObserver((mutations) => {
                // Check if any audio elements were added
                let shouldReinitAudio = false;
                let shouldReinitAccordions = false;
                
                mutations.forEach(mutation => {
                    if (mutation.addedNodes.length) {
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1) { // Element node
                                if (node.querySelector('audio')) {
                                    shouldReinitAudio = true;
                                }
                                if (node.classList?.contains('accordion-button') || node.querySelector?.('.accordion-button')) {
                                    shouldReinitAccordions = true;
                                }
                            }
                        });
                    }
                });
                
                if (shouldReinitAudio) {
                    initAudioPlayers();
                }
                
                if (shouldReinitAccordions) {
                    initAccordions();
                }
            });
            
            // Start observing once DOM is loaded
            document.addEventListener('DOMContentLoaded', function() {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            });

            // Handle sidebar mouseleave with JavaScript
            document.addEventListener('DOMContentLoaded', function() {
                const sideMenu = document.getElementById('side-menu');
                if (sideMenu) {
                    sideMenu.addEventListener('mouseleave', function() {
                        sideMenu.style.left = "-300px";
                    });
                }
            });

            // Add Web3 UI animation initialization
            document.addEventListener('DOMContentLoaded', function() {
                // Add hover animation to elements with .web3-hover class
                const hoverElements = document.querySelectorAll('.web3-hover');
                hoverElements.forEach(el => {
                    el.addEventListener('mouseenter', function() {
                        this.style.transform = 'translateY(-3px)';
                        this.style.boxShadow = '0 5px 15px rgba(153, 69, 255, 0.4)';
                    });
                    el.addEventListener('mouseleave', function() {
                        this.style.transform = 'translateY(0)';
                        this.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
                    });
                });
                
                // Wake Lock functionality to prevent screen sleep
                async function requestWakeLock() {
                    try {
                        if ('wakeLock' in navigator) {
                            window.wakeLockObj = await navigator.wakeLock.request('screen');
                            console.log('Wake Lock is active');
                        }
                    } catch (err) {
                        console.error(`Error requesting Wake Lock: ${err.name}, ${err.message}`);
                    }
                }
                requestWakeLock();
            });
        </script>
    </body>
</html>
'''

app.title = "LocalLoop"

# Define app layout
app.layout = html.Div(
    [
        # Store components
        dcc.Store(id="session-id", storage_type="local"),
        dcc.Store(id="game-state", storage_type="local"),
        dcc.Store(id="init-trigger", data=True),
        dcc.Store(id="button-clicks-memory", data={}),
        dcc.Store(id="timer-trigger", data={"last_save": 0, "success": None}, storage_type="local"),
        dcc.Interval(
            id="interval-component", interval=30 * 1000, n_intervals=0, disabled=True
        ),
        
        # Header with hamburger menu
        html.Div([
            # Hamburger menu icon
            html.Div([
                html.I(className="fas fa-bars", id="hamburger-icon")
            ]),
            
            # Site logo/header
            html.Div(
                html.H2("LocalLoop", 
                        style={
                            "textAlign": "center", 
                            "marginBottom": "20px", 
                            "background": "var(--solana-gradient)",
                            "WebkitBackgroundClip": "text",
                            "WebkitTextFillColor": "transparent",
                            "fontWeight": "bold"
                        }),
                style={"marginTop": "20px", "marginBottom": "20px"}
            ),
            
            # Side menu (initially hidden)
            html.Div([
                html.Div([
                    html.I(className="fas fa-times", id="close-menu", 
                        style={
                            "fontSize": "24px", 
                            "cursor": "pointer", 
                            "position": "absolute", 
                            "right": "15px", 
                            "top": "15px",
                            "color": "var(--solana-purple)",
                            "background": "rgba(255, 255, 255, 0.2)",
                            "borderRadius": "50%",
                            "padding": "8px",
                            "boxShadow": "0 0 10px rgba(153, 69, 255, 0.5)",
                            "zIndex": "1010"
                        }),
                    html.H3("Game Information", style={"marginBottom": "20px", "paddingTop": "20px", "textAlign": "center", "color": "var(--solana-blue)"}),
                    
                    # Game instructions tab
                    html.Div([
                        html.H4("How to Play", className="accordion-button",
                                style={
                                    "backgroundColor": "rgba(153, 69, 255, 0.2)",
                                    "color": "white",
                                    "borderRadius": "8px",
                                    "padding": "12px 15px",
                                    "marginBottom": "8px",
                                    "cursor": "pointer",
                                    "borderLeft": "4px solid var(--solana-purple)"
                                }),
                        html.Div([
                            html.P("""
                                Let the adventure begin. Head to the first marked spot and tap the 'ARRIVED' button once you get there.
                                You'll then receive your puzzle. Examine your surroundings or listen to the audio file to solve it.
                                Run into a roadblock? Tap the 'HINT' button for assistance.
                            """, style={"fontSize": "14px", "lineHeight": "1.5", "color": "#e0e0e0"})
                        ], className="accordion-content", style={"display": "block"})
                    ], className="accordion-item"),
                    html.Div([
                        html.P("""
                            Once you solve the puzzle, type your answer in the chat box. 
                            If you're correct, you'll be rewarded with tokens and a new location to explore.
                        """, style={"fontSize": "14px", "lineHeight": "1.5", "color": "#e0e0e0"})
                    ], className="accordion-content"),                    
                    
                    # Token reward system tab
                    html.Div([
                        html.H4("Token Rewards", className="accordion-button"),
                        html.Div([
                            html.P([
                                html.Span("• Arriving at locations: ", style={"fontWeight": "bold", "color": "var(--solana-blue)"}),
                                f"+{TOKEN_REWARD_ARRIVED} tokens"
                            ]),
                            html.P([
                                html.Span("• Answering puzzles correctly: ", style={"fontWeight": "bold", "color": "var(--solana-teal)"}),
                                f"+{TOKEN_REWARD_CORRECT_ANSWER} tokens"
                            ]),
                            html.P([
                                html.Span("• Using hints: ", style={"fontWeight": "bold", "color": "var(--solana-purple)"}),
                                f"-{TOKEN_PENALTY_HINT} tokens"
                            ])
                        ], className="accordion-content")
                    ], className="accordion-item"),
                    
                    # Data usage policy tab
                    html.Div([
                        html.H4("Data Usage", className="accordion-button"),
                        html.Div([
                            html.P("""
                                Data is kept only until the game is finished playing. 
                                As soon as the game is completed it refreshes and the data is deleted.
                            """, style={"fontSize": "14px", "lineHeight": "1.5"})
                        ], className="accordion-content")
                    ], className="accordion-item"),
                    
                ], style={"padding": "20px", "height": "100%", "overflowY": "auto"})
            ], id="side-menu"),
            # Add this to the layout, after the side-menu div
            html.Div(
                id="side-menu-overlay",
                style={
                    "position": "fixed",
                    "top": "0",
                    "left": "0",
                    "right": "0",
                    "bottom": "0",
                    "backgroundColor": "rgba(0, 0, 0, 0.5)",
                    "zIndex": "999",
                    "display": "none"
                }
            )
        ], style={"position": "relative"}),

        
        # Main content container
        html.Div(
            [
                # Journey Progress - redesigned
                html.Div(
                    [
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-route", style={"color": "var(--solana-blue)"}),
                                    html.H5("Journey Progress", style={"margin": "0 0 0 10px", "fontWeight": "600"})
                                ], className="journey-title"),
                                
                                # Token display next to progress bar - Clickable to open wallet
                                html.Div(
                                    [
                                        html.I(className="fas fa-coins", style={"color": "var(--solana-teal)"}),
                                        html.Span(id="token-count", className="token-count")
                                    ],
                                    id="token-display",
                                    className="token-display",
                                    **{"data-toggle": "modal", "data-target": "#token-wallet-modal"}
                                )
                            ], className="journey-header"),
                            
                            # Progress bar
                            html.Div(id="progress-bar-container"),
                            
                            # Current location info
                            html.Div(id="current-location-info")
                        ])
                    ],
                    id="journey-progress",
                    className="journey-progress",
                ),
                
                # Audio Guide - redesigned
                html.Div(
                    id="audio-guide-container",
                    className="task-container",
                    style={"display": "none"}
                ),
                
                # Task display - redesigned
                html.Div(
                    id="task-container",
                    className="task-container",
                    style={"display": "none"}
                ),
                
                # Selfie upload - standalone
                html.Div(
                    [
                        html.Div([
                            html.I(className="fas fa-camera", style={"color": "var(--solana-purple)", "marginRight": "10px"}),
                            html.H5("Upload Completion Selfie", style={"margin": "0", "fontWeight": "600"})
                        ], className="task-header"),
                        
                        dcc.Upload(
                            id="upload-selfie",
                            children=html.Div([
                                html.I(className="fas fa-cloud-upload-alt", style={"fontSize": "32px", "marginBottom": "10px", "color": "var(--solana-blue)"}),
                                html.Div("Drag and Drop or Click to Select")
                            ], style={"display": "flex", "flexDirection": "column", "alignItems": "center"}),
                            style={
                                "width": "100%",
                                "height": "120px",
                                "lineHeight": "120px",
                                "borderWidth": "2px",
                                "borderStyle": "dashed",
                                "borderRadius": "12px",
                                "textAlign": "center",
                                "margin": "15px 0",
                                "backgroundColor": "rgba(35, 35, 51, 0.5)",
                                "borderColor": "var(--solana-purple)",
                                "display": "flex",
                                "justifyContent": "center",
                                "alignItems": "center",
                                "cursor": "pointer"
                            },
                            multiple=False,
                        ),
                        dcc.Loading(
                            id="loading-selfie",
                            type="circle",
                            color="var(--solana-purple)",
                            children=[
                                html.Div(id="selfie-preview"),
                                dbc.Button(
                                    [html.I(className="fas fa-check", style={"marginRight": "8px"}), "Submit Selfie"],
                                    id="submit-selfie",
                                    color=None,
                                    style={
                                        "marginTop": "15px", 
                                        "display": "none",
                                        "backgroundColor": "var(--solana-teal)",
                                        "color": "var(--solana-dark)",
                                        "fontWeight": "bold",
                                        "border": "none",
                                        "padding": "12px 20px",
                                        "borderRadius": "10px"
                                    },
                                ),
                            ]
                        ),
                    ],
                    id="selfie-container",
                    className="task-container",
                    style={"display": "none"}
                ),
                
                # Game Chat - redesigned
                html.Div(
                    [
                        html.Div([
                            html.I(className="fas fa-comments", style={"color": "var(--solana-purple)"}),
                            html.H5("Game Chat", style={"margin": "0 0 0 10px", "fontWeight": "600"})
                        ], className="chat-header"),
                        
                        dcc.Loading(
                            id="loading-chat",
                            type="circle",
                            color="var(--solana-purple)",
                            children=html.Div(
                                id="chat-messages",
                                style={
                                    "height": "350px",
                                    "overflowY": "auto",
                                    "padding": "15px",
                                    "backgroundColor": "rgba(35, 35, 51, 0.5)",
                                }
                            )
                        ),
                        
                        html.Div([
                            dbc.InputGroup(
                                [
                                    dbc.Input(
                                        id="chat-input",
                                        type="text",
                                        placeholder="Type a message...",
                                        style={
                                            "backgroundColor": "rgba(35, 35, 51, 0.7)",
                                            "color": "white",
                                            "border": "1px solid var(--solana-purple)",
                                            "borderRadius": "25px 0 0 25px",
                                            "padding": "12px 20px",
                                        },
                                    ),
                                    dbc.Button(
                                        html.I(className="fas fa-paper-plane"),
                                        id="send-button",
                                        color=None,
                                        style={
                                            "borderRadius": "50%",
                                            "backgroundColor": "var(--solana-teal)",
                                            "width": "50px",
                                            "height": "50px",
                                            "display": "flex",
                                            "alignItems": "center",
                                            "justifyContent": "center",
                                            "marginLeft": "10px",
                                            "boxShadow": "0 0 10px rgba(20, 241, 149, 0.3)",
                                        }
                                    )
                                ], 
                                style={"marginTop": "15px"}
                            ),
                        ], style={"padding": "0 15px 15px 15px"}),
                    ],
                    className="game-chat",
                ),
                
                # Game Actions - redesigned
                html.Div(
                    [
                        html.Div(
                            id="action-buttons-container",
                            style={
                                "display": "flex",
                                "flexWrap": "wrap",
                                "justifyContent": "center",
                                "padding": "10px",
                                "gap": "15px"
                            },
                        ),
                    ],
                    className="actions-container",
                ),
                
                # Token info panel 
                html.Div(
                    [
                        # Pre-create the close-wallet button that can be referenced in callbacks
                        html.Div(className="token-wallet-content", id="token-wallet-content"),
                        html.Div([
                            dbc.Button(
                                html.I(className="fas fa-times"),
                                id="close-wallet",
                                color=None,
                                style={"display": "none"}  # Hide initially
                            )
                        ], id="close-wallet-container")
                    ],
                    id="token-info",
                    style={"display": "none"}
                )
            ],
            className="container",
            style={"maxWidth": "800px", "margin": "0 auto", "padding": "0 15px"}
        ),
    ]
)

@callback(
    Output("interval-component", "disabled"),
    Input({"type": "action-button", "action": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def enable_interval(clicks):
    return False  # Enable the interval after any button click

# Initialize session ID callback
@callback(
    Output("session-id", "data"),
    Input("interval-component", "n_intervals"),
    State("session-id", "data"),
)
def initialize_session_id(n_intervals, session_id):
    if session_id is None:
        new_session_id = get_session_id()
        return new_session_id
    return session_id

@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("init-trigger", "data"),
    prevent_initial_call=True
)
def initialize_default_game_state(trigger):
    """Initialize a default game state on page load"""
    if trigger:
        return {
            "game_started": False,
            "current_step": "not_started",
            "messages": [],
            "tokens_earned": 0,
            "token_transactions": []
        }
    raise PreventUpdate

@callback(
    Output("game-state", "data"),
    Input("session-id", "data"),
    State("game-state", "data"),
)
def initialize_game_state(session_id, current_game_state):
    if session_id is None:
        raise PreventUpdate

    try:
        # Handle case where current_game_state is a string
        if isinstance(current_game_state, str):
            try:
                # Try to parse it as JSON
                current_game_state = json.loads(current_game_state)
            except json.JSONDecodeError:
                # If it's not valid JSON, treat as None
                current_game_state = None

        # Check if current_game_state is already valid
        if (current_game_state is not None and 
            isinstance(current_game_state, dict) and 
            current_game_state.get("game_started", False)):
            
            # Just validate the existing state
            return validate_game_state(current_game_state)
                
        # Check if current_game_state is None or empty or if game hasn't started
        if (current_game_state is None or 
            not current_game_state or 
            not current_game_state.get("game_started", False)):
            
            # Try to restore from local file
            restored_state = restore_game_state_locally(session_id)

            if restored_state:
                # IMPORTANT: Validate the restored state
                validated_state = validate_game_state(restored_state)
                logger.info(f"Successfully restored and validated game state for session {session_id}")
                return validated_state

            # Initialize default state if restoration failed
            logger.info(f"Creating new game state for session {session_id}")
            return validate_game_state({
                "game_started": False,
                "start_time": None,
                "current_location_index": 0,
                "current_step": "not_started",
                "completed_locations": [],
                "puzzle_attempts": 0,
                "hints_used": 0,
                "messages": [],
                "tokens_earned": 0,
                "token_transactions": [],
            })

        # Validate the current state before returning it
        return validate_game_state(current_game_state)
    except Exception as e:
        logger.error(f"Error initializing game state: {str(e)}")
        # Return a minimally valid game state in case of errors
        return reset_game_state()

# Token Count Display
@callback(
    Output("token-count", "children"),
    Input("game-state", "data"),
    prevent_initial_call=True
)
def update_token_count(game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None:
            return "0"
        
        token_balance = game_state.get("tokens_earned", 0)
        return str(token_balance)
    except Exception as e:
        logger.error(f"Error updating token count: {str(e)}")
        return "0"

# Token Info Panel callback
@callback(
    Output("token-wallet-content", "children"),
    Input("token-display", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True
)
def show_token_wallet(n_clicks, game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None:
            return html.Div("Loading token information...")
        
        token_balance = game_state.get("tokens_earned", 0)
        transactions = game_state.get("token_transactions", [])[-5:]  # Get last 5 transactions
        
        # Create Web3-styled token wallet UI
        return html.Div([
            # Wallet header with gradient border
            html.Div([
                    html.Div([
                        html.I(className="fas fa-wallet", style={"fontSize": "22px", "marginRight": "12px", "color": "var(--solana-teal)"}),
                        html.H5("Token Wallet", style={"margin": "0", "fontWeight": "600", "color": "white"}),
                    ], className="wallet-title"),
                    html.Div([
                        html.Span(f"{token_balance}", className="balance-amount"),
                        html.Span("LOOP", className="balance-currency")
                    ], className="wallet-balance")
                ], className="token-wallet-header"),            
            # Transaction history styled like a blockchain ledger
            html.Div([
                html.H6("Recent Transactions", style={"marginBottom": "10px", "color": "var(--solana-gray)", "paddingLeft": "10px", "paddingTop": "10px"}),
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className=f"fas fa-{'arrow-up' if tx.get('amount', 0) < 0 else 'arrow-down'}", 
                                  style={"color": "#FF5757" if tx.get("amount", 0) < 0 else "var(--solana-teal)",
                                         "marginRight": "10px"}),
                            html.Div(tx.get("reason", ""), style={"fontSize": "14px"})
                        ], className="transaction-info"),
                        html.Div(f"{'+' if tx.get('amount', 0) > 0 else ''}{tx.get('amount', 0)} LOOP", 
                                className=f"transaction-amount {'positive' if tx.get('amount', 0) > 0 else 'negative'}")
                    ], className=f"transaction-item {'transaction-positive' if tx.get('amount', 0) > 0 else 'transaction-negative'}")
                    for tx in reversed(transactions)
                ])
            ], className="transaction-history"),
            
            # Close button
            html.Div([
                dbc.Button(
                    html.I(className="fas fa-times"),
                    id="close-wallet",
                    color=None,
                    style={
                        "backgroundColor": "var(--solana-purple)",
                        "width": "40px",
                        "height": "40px",
                        "borderRadius": "50%",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "marginTop": "15px",
                        "marginLeft": "auto",
                        "marginRight": "auto",
                        "boxShadow": "0 0 10px rgba(153, 69, 255, 0.5)"
                    }
                )
            ], style={"textAlign": "center", "padding": "0 0 15px 0"})
        ], className="token-wallet")
    except Exception as e:
        logger.error(f"Error in showing token wallet: {str(e)}")
        return html.Div("Error loading token information. Please try again.")

# Toggle token info display
@callback(
    [Output("token-info", "style"), Output("close-wallet", "style")],
    [Input("token-display", "n_clicks"), Input("close-wallet", "n_clicks")],
    [State("token-info", "style")],
    prevent_initial_call=True
)
def toggle_token_wallet(show_clicks, hide_clicks, current_style):
    # Initialize current_style if None
    if current_style is None:
        current_style = {"display": "none", "position": "fixed", "top": "50%", "left": "50%", 
                        "transform": "translate(-50%, -50%)", "zIndex": "1000", "width": "90%", 
                        "maxWidth": "350px", "backgroundColor": "rgba(35, 35, 51, 0.95)", 
                        "borderRadius": "15px", "boxShadow": "0 0 30px rgba(153, 69, 255, 0.7)",
                        "backdropFilter": "blur(10px)"}
    
    ctx_triggered = dash.callback_context.triggered
    if not ctx_triggered:
        return current_style, {"display": "none"}
        
    trigger_id = ctx_triggered[0]["prop_id"].split(".")[0]
    
    if trigger_id == "token-display":
        return {"display": "block", **{k:v for k,v in current_style.items() if k != "display"}}, {"display": "block"}
    elif trigger_id == "close-wallet":
        return {"display": "none", **{k:v for k,v in current_style.items() if k != "display"}}, {"display": "none"}
    
    return current_style, {"display": "none"}

# Progress Bar Container callback
@callback(
    Output("progress-bar-container", "children"),
    Input("game-state", "data"),
    prevent_initial_call=True
)
def update_progress_bar(game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None:
            return html.Div()
        
        # Calculate progress
        total_locations = len(GAME_DATA["locations"])
        completed_locations = len(game_state.get("completed_locations", []))
        progress_percentage = (completed_locations / total_locations) * 100 if total_locations > 0 else 0
        
        # Display progress bar
        return html.Div([
            html.Div(
                html.Div(
                    className="progress-bar",
                    style={"width": f"{progress_percentage}%"}
                ),
                className="progress"
            ),
            html.Div(
                f"{completed_locations}/{total_locations} locations",
                style={"fontSize": "14px", "color": "var(--solana-gray)", "textAlign": "right"}
            )
        ])
    except Exception as e:
        logger.error(f"Error updating progress bar: {str(e)}")
        return html.Div()

# Current Location Info callback
@callback(
    Output("current-location-info", "children"),
    Input("game-state", "data"),
    prevent_initial_call=True
)
def update_current_location(game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None or not game_state.get("game_started", False):
            return html.Div("Start your adventure by tapping the ARRIVED button!", 
                           style={"color": "var(--solana-blue)", "marginTop": "10px", "textAlign": "center"})
        
        # Get current location
        current_location_index = game_state.get("current_location_index", 0)
        if not (0 <= current_location_index < len(GAME_DATA["locations"])):
            return html.Div("Location information not available")
            
        current_location = GAME_DATA["locations"][current_location_index]
        current_step = game_state.get("current_step", "")
        
        # Prepare info based on current step
        if current_step == "finding_location":
            # Next destination display
            return html.Div([
                html.Div([
                    html.I(className="fas fa-map-marker-alt", style={"color": "var(--solana-blue)", "marginRight": "10px"}),
                    html.Span("Next Destination:", style={"color": "var(--solana-gray)", "fontSize": "14px"})
                ], style={"display": "flex", "alignItems": "center", "marginTop": "10px"}),
                
                html.Div(current_location["name"], style={
                    "marginLeft": "25px", 
                    "marginTop": "5px", 
                    "fontSize": "16px",
                    "fontWeight": "500"
                }),
                
                # Google Maps link
                html.A([
                    html.I(className="fas fa-directions", style={"marginRight": "8px"}),
                    "Get Directions"
                ], 
                href=current_location["google_maps_link"],
                target="_blank",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "backgroundColor": "rgba(3, 225, 255, 0.1)",
                    "color": "var(--solana-blue)",
                    "padding": "8px 12px",
                    "borderRadius": "8px",
                    "marginTop": "10px",
                    "marginLeft": "25px",
                    "border": "1px solid rgba(3, 225, 255, 0.3)",
                    "textDecoration": "none",
                    "transition": "all 0.3s ease"
                }),
            ])
        elif current_step == "solving_puzzle":
            # Current location display
            return html.Div([
                html.Div([
                    html.I(className="fas fa-location-dot", style={"color": "var(--solana-teal)", "marginRight": "10px"}),
                    html.Span("Current Location:", style={"color": "var(--solana-gray)", "fontSize": "14px"})
                ], style={"display": "flex", "alignItems": "center", "marginTop": "10px"}),
                
                html.Div(current_location["name"], style={
                    "marginLeft": "25px", 
                    "marginTop": "5px", 
                    "fontSize": "16px",
                    "fontWeight": "500"
                }),
                
                # Google Maps link
                html.A([
                    html.I(className="fas fa-map", style={"marginRight": "8px"}),
                    "View in Maps"
                ], 
                href=current_location["google_maps_link"],
                target="_blank",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "backgroundColor": "rgba(20, 241, 149, 0.1)",
                    "color": "var(--solana-teal)",
                    "padding": "8px 12px",
                    "borderRadius": "8px",
                    "marginTop": "10px",
                    "marginLeft": "25px",
                    "border": "1px solid rgba(20, 241, 149, 0.3)",
                    "textDecoration": "none",
                    "transition": "all 0.3s ease"
                }),
            ])
        else:
            # Default display
            return html.Div("Start your adventure by tapping the ARRIVED button!", 
                           style={"color": "var(--solana-blue)", "marginTop": "10px", "textAlign": "center"})
    except Exception as e:
        logger.error(f"Error updating current location info: {str(e)}")
        return html.Div("Location information not available")

# Audio Guide Container callback
@callback(
    [Output("audio-guide-container", "children"), Output("audio-guide-container", "style")],
    Input("game-state", "data"),
    prevent_initial_call=True
)
def update_audio_guide(game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None or not game_state.get("game_started", False) or game_state.get("current_step") != "solving_puzzle":
            return html.Div(), {"display": "none"}
        
        # Get current location audio
        current_location_index = game_state.get("current_location_index", 0)
        if not (0 <= current_location_index < len(GAME_DATA["locations"])):
            return html.Div(), {"display": "none"}
            
        current_location = GAME_DATA["locations"][current_location_index]
        audio_file = current_location.get("audio_fact")
        
        if not audio_file:
            return html.Div(), {"display": "none"}
        
        # Create custom audio player
        return html.Div([
            html.Div([
                html.I(className="fas fa-headphones", style={"color": "var(--solana-purple)", "marginRight": "10px"}),
                html.H5("Audio Guide", style={"margin": "0", "fontWeight": "600"})
            ], className="task-header"),
            
            html.Audio(
                id="audio-element",
                src=audio_file,
                controls=True,
                style={"width": "100%"}
            )
        ]), {"display": "block"}
    except Exception as e:
        logger.error(f"Error updating audio guide: {str(e)}")
        return html.Div(), {"display": "none"}

# Task Container callback
@callback(
    [Output("task-container", "children"), Output("task-container", "style")],
    Input("game-state", "data"),
    prevent_initial_call=True
)
def update_task_container(game_state):
    try:
        # Parse game_state if it's a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None or not game_state.get("game_started", False) or game_state.get("current_step") != "solving_puzzle":
            return html.Div(), {"display": "none"}
        
        # Get current puzzle
        current_location_index = game_state.get("current_location_index", 0)
        if not (0 <= current_location_index < len(GAME_DATA["locations"])):
            return html.Div(), {"display": "none"}
            
        current_location = GAME_DATA["locations"][current_location_index]
        puzzle = current_location.get("puzzle", {})
        
        if not puzzle or "question" not in puzzle:
            return html.Div(), {"display": "none"}
        
        # Get hints if any
        hints_used = game_state.get("hints_used", 0)
        previous_hints = game_state.get("previous_hints", [])
        hints_remaining = 3 - hints_used
        
        # Create task display
        task_elements = [
            html.Div([
                html.I(className="fas fa-puzzle-piece", style={"color": "var(--solana-teal)", "marginRight": "10px"}),
                html.H5("Your Task", style={"margin": "0", "fontWeight": "600"})
            ], className="task-header"),
            
            # Display puzzle question
            html.Div(
                puzzle["question"],
                className="question-box"
            ),
            
            # Show attempts remaining
            html.Div([
                html.I(className="fas fa-clock", style={"marginRight": "8px", "color": "var(--solana-gray)"}),
                f"Attempts remaining: ",
                html.Span(f"{MAX_PUZZLE_ATTEMPTS - game_state.get('puzzle_attempts', 0)}", 
                         style={"fontWeight": "bold", "color": "var(--solana-blue)"})
            ], style={"fontSize": "14px", "marginTop": "15px", "display": "flex", "alignItems": "center"}),
        ]
        
        # Add previously used hints
        if previous_hints:
            for i, hint in enumerate(previous_hints):
                task_elements.append(
                    html.Div([
                        html.I(className="fas fa-lightbulb", style={"color": "var(--solana-teal)", "marginRight": "10px"}),
                        f"Hint {i+1}: {hint}"
                    ], className="hint-box")
                )
        
        # Show hints remaining indicator
        if hints_remaining > 0:
            task_elements.append(
                html.Div([
                    html.I(className="fas fa-info-circle", style={"marginRight": "8px", "color": "var(--solana-gray)"}),
                    f"Hints remaining: ",
                    html.Span(f"{hints_remaining}", style={"fontWeight": "bold", "color": "var(--solana-teal)"})
                ], style={"fontSize": "14px", "marginTop": "15px", "display": "flex", "alignItems": "center"})
            )
        else:
            task_elements.append(
                html.Div([
                    html.I(className="fas fa-times-circle", style={"marginRight": "8px", "color": "#FF5757"}),
                    "No hints remaining"
                ], style={"fontSize": "14px", "marginTop": "15px", "display": "flex", "alignItems": "center"})
            )
        
        return task_elements, {"display": "block"}
    except Exception as e:
        logger.error(f"Error updating task container: {str(e)}")
        return html.Div(), {"display": "none"}

# Update chat messages callback
@callback(
    Output("chat-messages", "children"),
    Input("game-state", "data"),
    prevent_initial_call=True,
)
def update_chat_messages(game_state):
    try:
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                game_state = {}
                
        if game_state is None:
            return html.Div("Loading chat...")

        messages = game_state.get("messages", [])
        
        if not isinstance(messages, list):
            return html.Div("No messages yet.")

        # Show only the most recent message expanded, others collapsed
        chat_elements = []
        
        # Add older messages as collapsed accordions
        if len(messages) > 1:
            chat_elements.append(
                html.Div([
                    html.Div([
                        html.Span("Previous Messages", style={"flex": "1"}),
                        html.I(className="fas fa-chevron-down")
                    ], 
                    className="accordion-button",
                    style={
                        "backgroundColor": "rgba(153, 69, 255, 0.2)", 
                        "color": "white",
                        "borderRadius": "8px",
                        "padding": "10px 15px",
                        "marginBottom": "10px",
                        "cursor": "pointer",
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center"
                    }),
                    html.Div([
                        # Previous messages here
                        *[render_chat_message(message) for message in messages[:-1]]
                    ], className="accordion-content", style={"display": "none"})
                ], className="accordion-item")
            )
        
        # Add the most recent message (always visible)
        if messages:
            latest_message = messages[-1]
            chat_elements.append(render_chat_message(latest_message, is_latest=True))

        # Add auto-scroll
        scroll_to_bottom = html.Script("""
            setTimeout(function() {
                var chatDiv = document.getElementById('chat-messages');
                chatDiv.scrollTop = chatDiv.scrollHeight;
            }, 100);
        """)
        
        return html.Div(chat_elements + [scroll_to_bottom], id="chat-messages-container")
    except Exception as e:
        logger.error(f"Error in update_chat_messages: {str(e)}")
        return html.Div("Error loading chat messages. Please refresh the page.")

# Helper function to render chat messages with Web3 styling
def render_chat_message(message, is_latest=False):
    role = message.get("role", "")
    content = message.get("content", "")
    
    # Get appropriate icon
    icon = get_message_icon(role, content)
    
    # Get appropriate colors
    bg_color, icon_color = get_message_color(role, content)
    
    # Web3-styled message bubbles
    if role == "user":
        return html.Div(
            html.Div(
                [
                    html.Div(
                        icon,
                        className="chat-avatar user-avatar",
                        style={
                            "backgroundColor": "var(--solana-dark)",
                            "border": f"1px solid {icon_color}",
                            "color": icon_color,
                            "width": "36px",
                            "height": "36px",
                            "borderRadius": "50%",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "marginRight": "10px",
                            "fontSize": "14px",
                            "boxShadow": f"0 0 10px rgba(132, 136, 149, 0.3)"
                        },
                    ),
                    html.Div(
                        convert_text_to_components(content),
                        style={
                            "backgroundColor": bg_color,
                            "padding": "12px 15px",
                            "borderRadius": "12px 12px 0 12px",
                            "maxWidth": "calc(100% - 46px)",
                            "wordWrap": "break-word",
                            "border": f"1px solid {icon_color}",
                            "boxShadow": "0 2px 10px rgba(0, 0, 0, 0.1)",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "marginBottom": "12px",
                    "justifyContent": "flex-end",
                    "marginLeft": "auto",
                    "maxWidth": "85%",
                    "animation": "fadeIn 0.3s ease-in-out" if is_latest else "none",
                },
            ),
            style={"marginBottom": "8px", "display": "flex", "justifyContent": "flex-end"}
        )
    else:  # assistant
        return html.Div(
            html.Div(
                [
                    html.Div(
                        icon,
                        className="chat-avatar system-avatar",
                        style={
                            "backgroundColor": "var(--solana-dark)",
                            "border": f"1px solid {icon_color}",
                            "color": icon_color,
                            "width": "36px",
                            "height": "36px",
                            "borderRadius": "8px",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "marginRight": "10px",
                            "fontSize": "14px",
                            "boxShadow": f"0 0 10px rgba(0, 0, 0, 0.2)"
                        },
                    ),
                    html.Div(
                        convert_text_to_components(content),
                        style={
                            "backgroundColor": bg_color,
                            "padding": "12px 15px",
                            "borderRadius": "12px 12px 12px 0",
                            "maxWidth": "calc(100% - 46px)",
                            "wordWrap": "break-word",
                            "border": f"1px solid {icon_color}",
                            "boxShadow": "0 2px 10px rgba(0, 0, 0, 0.1)",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "marginBottom": "12px",
                    "justifyContent": "flex-start",
                    "maxWidth": "85%",
                    "animation": "fadeIn 0.3s ease-in-out" if is_latest else "none",
                },
            ),
            style={"marginBottom": "8px"}
        )

@callback(
    [Output("game-state", "data", allow_duplicate=True), Output("chat-input", "value")],
    [Input("send-button", "n_clicks"), Input("chat-input", "n_submit")],
    [State("chat-input", "value"), State("game-state", "data"), State("session-id", "data")],
    prevent_initial_call=True,
)
def handle_chat_input(n_clicks, n_submit, input_value, game_state, session_id):
    if (n_clicks is None and n_submit is None) or not input_value:
        raise PreventUpdate
    
    # Handle case where game_state is None
    if game_state is None:
        game_state = {"game_started": False, "messages": []}
    
    # Validate input to prevent processing empty messages    
    input_value = input_value.strip()
    if not input_value:
        raise PreventUpdate
    
    # Process the game state update atomically
    try:
        updated_game_state, _ = handle_user_input(game_state, input_value)
        
        # Ensure result is valid before saving
        updated_game_state = validate_game_state(updated_game_state)
        
        # Save to local storage if needed
        if session_id:
            save_result = save_game_state_locally(session_id, updated_game_state)
            if not save_result:
                logger.warning(f"Failed to save game state to local file for session {session_id}")
        
        return updated_game_state, ""
    except Exception as e:
        logger.error(f"Error in handle_chat_input: {str(e)}")
        # Return original state to avoid corrupting it
        return game_state, ""

# Update selfie container callback
@callback(
    Output("selfie-container", "style"),
    Input("game-state", "data"),
    prevent_initial_call=True,
)
def update_selfie_container(game_state):
    try:
        # Handle case where game_state is a string
        if isinstance(game_state, str):
            try:
                # Try to parse it as JSON
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                # If it's not valid JSON, use an empty dict
                return {"display": "none"}
                
        if game_state is None:
            return {"display": "none"}

        current_step = game_state.get("current_step", "")

        if current_step == "completed":
            return {"display": "block"}

        return {"display": "none"}
    except Exception as e:
        logger.error(f"Error in update_selfie_container: {str(e)}")
        return {"display": "none"}

# Handle selfie upload callback
@callback(
    [Output("selfie-preview", "children"), Output("submit-selfie", "style")],
    Input("upload-selfie", "contents"),
    prevent_initial_call=True,
)
def handle_selfie_upload(contents):
    if contents is None:
        return html.Div(), {"display": "none"}

    return html.Div(
        [html.Img(src=contents, style={"width": "100%", "maxWidth": "300px", "margin": "10px auto", "borderRadius": "12px", "boxShadow": "0 5px 15px rgba(0, 0, 0, 0.2)"})]
    ), {"marginTop": "15px", "display": "block", "backgroundColor": "var(--solana-teal)", "color": "var(--solana-dark)", "fontWeight": "bold", "border": "none", "padding": "12px 20px", "borderRadius": "10px"}

# Handle selfie submission callback
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("submit-selfie", "n_clicks"),
    State("upload-selfie", "contents"),
    State("game-state", "data"),
    State("session-id", "data"),
    prevent_initial_call=True,
)
def handle_selfie_submission(n_clicks, contents, game_state, session_id):
    if n_clicks is None or contents is None:
        raise PreventUpdate
    
    # Handle case where game_state is None
    if game_state is None:
        game_state = {"game_started": False, "current_step": "not_started", "messages": []}
        raise PreventUpdate
        
    # Handle case where game_state is a string
    if isinstance(game_state, str):
        try:
            # Try to parse it as JSON
            game_state = json.loads(game_state)
        except json.JSONDecodeError:
            # If it's not valid JSON, create a default game state
            logger.error("Game state is a string and not valid JSON in handle_selfie_submission")
            game_state = {"game_started": False, "current_step": "not_started", "messages": []}
            raise PreventUpdate

    # Process the selfie submission
    updated_game_state, _ = handle_completion_selfie(game_state, contents)

    # Delete local game state file (game is complete)
    if session_id:
        try:
            # Remove the game state file
            file_path = os.path.join(GAME_STATES_DIR, f"{session_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted game state file for session ID: {session_id}")
        except Exception as e:
            logger.error(f"Error deleting game state file: {str(e)}")

    # Ensure game state is JSON serializable
    sanitized_state = sanitize_for_json(updated_game_state)
    
    # Extra validation to ensure the sanitized state is actually JSON serializable
    if not is_json_serializable(sanitized_state):
        logger.error("Sanitized game state is still not JSON serializable in handle_selfie_submission!")
        # Create a simpler fallback state that we know is serializable
        sanitized_state = {
            "game_started": False,
            "current_step": "not_started",
            "messages": updated_game_state.get("messages", []) if isinstance(updated_game_state, dict) else [],
            "tokens_earned": updated_game_state.get("tokens_earned", 0) if isinstance(updated_game_state, dict) else 0
        }
    
    return sanitized_state

@callback(
    Output("timer-trigger", "data"),
    Input("interval-component", "n_intervals"),
    State("game-state", "data"),
    State("session-id", "data"),
    State("timer-trigger", "data"),
    prevent_initial_call=True,
)
def save_state_periodically(n_intervals, game_state, session_id, timer_data):
    """
    Periodically save game state to local storage to prevent data loss.
    """
    try:
        # Check if the callback was actually triggered by an interval
        if not dash.callback_context.triggered:
            raise PreventUpdate
        
        # Handle case where timer_data is invalid
        if timer_data is None:
            timer_data = {"last_save": 0, "success": None, "last_state_hash": None}
        elif isinstance(timer_data, str):
            try:
                timer_data = json.loads(timer_data)
            except json.JSONDecodeError:
                timer_data = {"last_save": 0, "success": None, "last_state_hash": None}
        elif not isinstance(timer_data, dict):
            # If timer_data is neither None, str, nor dict, initialize it
            timer_data = {"last_save": 0, "success": None, "last_state_hash": None}
            
        # Validate expected timer_data fields exist
        for key in ["last_save", "success", "last_state_hash"]:
            if key not in timer_data:
                timer_data[key] = None if key == "success" else 0 if key == "last_save" else None
        
        # Get current time
        current_time = int(time.time())
        
        # Only save every 6 intervals (every 3 minutes with 30s interval)
        if n_intervals % 6 != 0:
            raise PreventUpdate
        
        # Only save if it's been at least 3 minutes since last save
        last_save = timer_data.get("last_save", 0) or 0  # Handle None case
        if current_time - last_save < 180:
            raise PreventUpdate
        
        # Skip if no game state or session ID
        if game_state is None or session_id is None:
            raise PreventUpdate
            
        # Handle case where game_state is a string
        if isinstance(game_state, str):
            try:
                game_state = json.loads(game_state)
            except json.JSONDecodeError:
                logger.error("Game state is a string and not valid JSON")
                raise PreventUpdate
        
        # Check if game state has changed significantly
        last_saved_state = timer_data.get("last_state_hash")
        
        # Create a stable hash of the game state
        try:
            # Sanitize before hashing
            sanitized_state = sanitize_for_json(game_state)
            
            # Convert to JSON string
            state_json = json.dumps(sanitized_state, sort_keys=True)
            
            # Use hashlib for a more stable hash than Python's built-in hash function
            hash_obj = hashlib.md5(state_json.encode())
            current_state_hash = hash_obj.hexdigest()
        except Exception as e:
            # Log the specific error
            logger.error(f"Error hashing game state: {str(e)}")
            # Fall back to a timestamp-based hash
            current_state_hash = f"time_{current_time}"
        
        # If state hasn't changed, don't save but update last_save time
        if last_saved_state is not None and last_saved_state == current_state_hash:
            return {
                "last_save": current_time,
                "success": timer_data.get("success"),
                "last_state_hash": last_saved_state
            }
        
        # Save to local storage
        success = save_game_state_locally(session_id, game_state)
        
        # Return updated state
        return {
            "last_save": current_time,
            "success": success,
            "last_state_hash": current_state_hash
        }
    except dash.exceptions.PreventUpdate:
        # This is expected behavior, not an error
        raise  # Re-raise PreventUpdate to properly skip the callback
    except Exception as e:
        # Log only genuine errors
        import traceback
        logger.error(f"Error in save_state_periodically: {str(e)}\n{traceback.format_exc()}")
        # Return a valid state that won't break the app
        return {"last_save": int(time.time()), "success": False, "last_state_hash": None}

# Add a route to serve audio files (assuming they're in an "audio" folder)
@server.route("/audio/<path:path>")
def serve_audio(path):
    """Serve audio files."""
    try:
        # Check both potential locations for the audio files
        potential_paths = [
            os.path.join(os.getcwd(), "audio"),  # Try direct "audio" folder first
            os.path.join(os.getcwd(), "assets", "audio")  # Then try "assets/audio"
        ]
        
        for audio_dir in potential_paths:
            full_path = os.path.join(audio_dir, path)
            if os.path.exists(full_path):
                with open(full_path, "rb") as audio_file:
                    return Response(audio_file.read(), mimetype="audio/mpeg")
        
        # If we get here, the file wasn't found in any location
        logger.error(f"Audio file not found: {path}")
        return Response("Audio file not found", status=404)
    except Exception as e:
        logger.error(f"Error serving audio file {path}: {e}")
        return Response("Error serving audio file", status=500)

if __name__ == "__main__":
    # Test local storage before starting
    test_local_storage()

    # Run the app
    app.run(host="0.0.0.0", port=8050, debug=True)