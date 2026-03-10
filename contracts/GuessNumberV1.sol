// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV1 {
    address public playerA;
    address public playerB;

    uint8 private secretNumber;
    uint8 public maxAttempts;
    uint8 public attempts;
    bool public gameOver;
    bool public won;

    enum GuessResult {
        TooSmall,
        TooLarge,
        Correct,
        GameOver
    }

    event GameStarted(address indexed playerA, uint8 maxAttempts);
    event GuessMade(
        address indexed playerB,
        uint8 guessedNumber,
        GuessResult result,
        uint8 attemptsLeft
    );
    event GameEnded(address indexed playerB, bool won);

    modifier onlyPlayerA() {
        require(msg.sender == playerA, "Seul le joueur A peut faire cela");
        _;
    }

    modifier onlyPlayerB() {
        require(msg.sender == playerB, "Seul le joueur B peut jouer");
        _;
    }

    modifier notGameOver() {
        require(!gameOver, "La partie est terminee");
        _;
    }

    constructor(uint8 _secretNumber, uint8 _maxAttempts, address _playerB) {
        require(_secretNumber >= 1 && _secretNumber <= 100, "Nombre secret invalide");
        require(_maxAttempts > 0, "Le nombre d'essais doit etre > 0");
        require(_playerB != address(0), "Adresse du joueur B invalide");

        playerA = msg.sender;
        playerB = _playerB;
        secretNumber = _secretNumber;
        maxAttempts = _maxAttempts;
        attempts = 0;
        gameOver = false;
        won = false;

        emit GameStarted(playerA, maxAttempts);
    }

    function guess(uint8 _guess) external onlyPlayerB notGameOver returns (GuessResult) {
        require(_guess >= 1 && _guess <= 100, "La proposition doit etre entre 1 et 100");

        attempts++;

        GuessResult result;

        if (_guess < secretNumber) {
            result = GuessResult.TooSmall;
        } else if (_guess > secretNumber) {
            result = GuessResult.TooLarge;
        } else {
            result = GuessResult.Correct;
            won = true;
            gameOver = true;
            emit GuessMade(playerB, _guess, result, maxAttempts - attempts);
            emit GameEnded(playerB, true);
            return result;
        }

        if (attempts >= maxAttempts) {
            gameOver = true;
            emit GuessMade(playerB, _guess, result, 0);
            emit GameEnded(playerB, false);
            return result;
        }

        emit GuessMade(playerB, _guess, result, maxAttempts - attempts);
        return result;
    }

    function attemptsLeft() external view returns (uint8) {
        return maxAttempts - attempts;
    }

    function getGameState()
        external
        view
        returns (
            address,
            address,
            uint8,
            uint8,
            bool,
            bool
        )
    {
        return (playerA, playerB, maxAttempts, attempts, gameOver, won);
    }
    // ATTENTION :
    // Cette fonction expose le secret.
    // Elle est seulement la pour debug/demo, pas pour une vraie version securisee.
    function revealSecret() external view onlyPlayerA returns (uint8) {
        return secretNumber;
    }
}
