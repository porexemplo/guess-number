from web3 import Web3

# ==============================
# CONFIGURATION
# ==============================

RPC_URL = "http://127.0.0.1:8545"  # exemple Ganache / Anvil / node local
CONTRACT_ADDRESS = "0xYourContractAddressHere"

PLAYER_B_ADDRESS = "0xYourPlayerBAddressHere"
PLAYER_B_PRIVATE_KEY = "YOUR_PRIVATE_KEY_HERE"

# ABI minimal du contrat
CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "uint8", "name": "_secretNumber", "type": "uint8"},
            {"internalType": "uint8", "name": "_maxAttempts", "type": "uint8"},
            {"internalType": "address", "name": "_playerB", "type": "address"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [{"internalType": "uint8", "name": "_guess", "type": "uint8"}],
        "name": "guess",
        "outputs": [{"internalType": "enum GuessNumberV1.GuessResult", "name": "", "type": "uint8"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getGameState",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint8", "name": "", "type": "uint8"},
            {"internalType": "uint8", "name": "", "type": "uint8"},
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "bool", "name": "", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "attemptsLeft",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

RESULT_LABELS = {
    0: "Plus petit",
    1: "Plus grand",
    2: "Correct",
    3: "Partie terminee"
}


def connect_web3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError("Impossible de se connecter au noeud Ethereum")
    return w3


def get_contract(w3):
    return w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )


def show_game_state(contract):
    player_a, player_b, max_attempts, attempts, game_over, won = contract.functions.getGameState().call()
    attempts_left = contract.functions.attemptsLeft().call()

    print("\n=== Etat du jeu ===")
    print(f"Joueur A       : {player_a}")
    print(f"Joueur B       : {player_b}")
    print(f"Essais max     : {max_attempts}")
    print(f"Essais utilises: {attempts}")
    print(f"Essais restants: {attempts_left}")
    print(f"Partie finie   : {game_over}")
    print(f"B a gagne      : {won}")
    print("===================\n")


def send_guess(w3, contract, guessed_number):
    account = Web3.to_checksum_address(PLAYER_B_ADDRESS)
    nonce = w3.eth.get_transaction_count(account)

    tx = contract.functions.guess(guessed_number).build_transaction({
        "from": account,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.to_wei("2", "gwei")
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PLAYER_B_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"Transaction envoyee : {tx_hash.hex()}")
    print(f"Bloc                : {receipt.blockNumber}")
    print(f"Statut              : {receipt.status}")


def read_guess_result_without_sending(contract, guessed_number, from_address):
    """
    Permet de simuler l'appel pour connaitre le resultat logique
    sans modifier l'etat.
    Utile pour afficher le retour attendu.
    """
    try:
        result = contract.functions.guess(guessed_number).call({
            "from": Web3.to_checksum_address(from_address)
        })
        return RESULT_LABELS.get(result, f"Code inconnu: {result}")
    except Exception as e:
        return f"Erreur simulation: {e}"


def main():
    w3 = connect_web3()
    contract = get_contract(w3)

    print("Connexion Ethereum OK")
    show_game_state(contract)

    while True:
        try:
            guess_value = int(input("Entre une proposition entre 1 et 100 (0 pour quitter) : "))
        except ValueError:
            print("Entre un entier valide.")
            continue

        if guess_value == 0:
            print("Fin du programme.")
            break

        if not (1 <= guess_value <= 100):
            print("Le nombre doit etre entre 1 et 100.")
            continue

        simulated_result = read_guess_result_without_sending(contract, guess_value, PLAYER_B_ADDRESS)
        print(f"Resultat attendu : {simulated_result}")

        confirm = input("Envoyer cette transaction ? (o/n) : ").strip().lower()
        if confirm != "o":
            print("Transaction annulee.")
            continue

        try:
            send_guess(w3, contract, guess_value)
            show_game_state(contract)
        except Exception as e:
            print(f"Erreur lors de l'envoi : {e}")


if __name__ == "__main__":
    main()