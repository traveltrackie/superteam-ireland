from solana.keypair import Keypair

# Generate sender keypair
sender = Keypair.generate()
sender_private_key = list(sender.secret_key)  # 64-byte private key array
sender_public_key = str(sender.public_key)

print("Sender Private Key (64-byte array):", sender_private_key)
print("Sender Public Key:", sender_public_key)

# Generate receiver keypair
receiver = Keypair.generate()
receiver_private_key = list(receiver.secret_key)  # 64-byte private key array
receiver_public_key = str(receiver.public_key)
print("Receiver Private Key (64-byte array):", receiver_private_key)
print("Receiver Public Key:", receiver_public_key)

