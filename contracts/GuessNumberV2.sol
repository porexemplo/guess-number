// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV2 {
    address public playerA;
    address public playerB;

    uint8 private secretNumber;
    uint8 public maxAttempts;
    uint8 public attempts;

    uint256 public stakeAmount;
    bool public playerBJoined;
    bool public gameOver;
    bool public wonByB;

    enum GuessResult {
        TooSmall,
        TooLarge,
        Correct
    }

    event GameCreated(
        address indexed playerA,
        uint8 maxAttempts,
        uint256 stakeAmount
    );

    event PlayerBJoined(address indexed playerB, uint256 stakeAmount);

    event GuessMade(
        address indexed playerB,
        uint8 guessedNumber,
        GuessResult result,
        uint8 attemptsLeft
    );

    event GameEnded(address indexed winner, uint256 reward, bool wonByB);

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

    modifier onlyWhenBJoined() {
        require(playerBJoined, "Le joueur B n'a pas encore rejoint");
        _;
    }

    constructor(uint8 _secretNumber, uint8 _maxAttempts) payable {
        require(_secretNumber >= 1 && _secretNumber <= 100, "Nombre secret invalide");
        require(_maxAttempts > 0, "Le nombre d'essais doit etre > 0");
        require(msg.value > 0, "Le joueur A doit miser de l'ETH");

        playerA = msg.sender;
        secretNumber = _secretNumber;
        maxAttempts = _maxAttempts;
        stakeAmount = msg.value;

        emit GameCreated(playerA, maxAttempts, stakeAmount);
    }

    function joinGame() external payable notGameOver {
        require(!playerBJoined, "Le joueur B a deja rejoint");
        require(msg.sender != playerA, "Le joueur A ne peut pas etre le joueur B");
        require(msg.value == stakeAmount, "La mise du joueur B doit etre egale a celle de A");

        playerB = msg.sender;
        playerBJoined = true;

        emit PlayerBJoined(playerB, msg.value);
    }

    function guess(uint8 _guess)
        external
        onlyPlayerB
        onlyWhenBJoined
        notGameOver
        returns (GuessResult)
    {
        require(_guess >= 1 && _guess <= 100, "La proposition doit etre entre 1 et 100");
        require(attempts < maxAttempts, "Plus aucune tentative disponible");

        attempts++;

        GuessResult result;

        if (_guess < secretNumber) {
            result = GuessResult.TooSmall;
            emit GuessMade(playerB, _guess, result, maxAttempts - attempts);
        } else if (_guess > secretNumber) {
            result = GuessResult.TooLarge;
            emit GuessMade(playerB, _guess, result, maxAttempts - attempts);
        } else {
            result = GuessResult.Correct;
            wonByB = true;
            gameOver = true;

            emit GuessMade(playerB, _guess, result, maxAttempts - attempts);

            uint256 reward = address(this).balance;
            payable(playerB).transfer(reward);

            emit GameEnded(playerB, reward, true);
            return result;
        }

        if (attempts >= maxAttempts) {
            gameOver = true;

            uint256 reward = address(this).balance;
            payable(playerA).transfer(reward);

            emit GameEnded(playerA, reward, false);
        }

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
            bool,
            bool,
            uint256,
            uint256
        )
    {
        return (
            playerA,
            playerB,
            maxAttempts,
            attempts,
            playerBJoined,
            gameOver,
            wonByB,
            stakeAmount,
            address(this).balance
        );
    }

    // Fonction de debug/demo uniquement
    // En vrai, cette version n'est toujours pas securisee
    function revealSecret() external view onlyPlayerA returns (uint8) {
        return secretNumber;
    }
}