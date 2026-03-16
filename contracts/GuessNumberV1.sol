// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV1 {
    address public immutable playerA;
    address public immutable playerB;
    uint8 private immutable secretNumber;
    uint8 public immutable maxAttempts;

    uint8 public attempts;
    bool public gameOver;
    bool public wonByB;
    int8 public lastResultCode; // -1 too high, 0 correct, 1 too low
    uint8 public lastGuess;

    event GuessEvaluated(address indexed playerB, uint8 guess, int8 resultCode, uint8 attemptsUsed, bool gameOver, bool wonByB);

    constructor(address _playerB, uint8 _secretNumber, uint8 _maxAttempts) {
        require(_playerB != address(0), "playerB required");
        require(_secretNumber >= 1 && _secretNumber <= 100, "secret out of range");
        require(_maxAttempts > 0, "maxAttempts must be > 0");

        playerA = msg.sender;
        playerB = _playerB;
        secretNumber = _secretNumber;
        maxAttempts = _maxAttempts;
        lastResultCode = 2; // no result yet
    }

    modifier onlyPlayerB() {
        require(msg.sender == playerB, "only playerB");
        _;
    }

    function previewGuess(uint8 guess_) public view returns (int8) {
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");
        if (guess_ == secretNumber) return 0;
        if (guess_ < secretNumber) return 1;
        return -1;
    }

    function guess(uint8 guess_) external onlyPlayerB {
        require(!gameOver, "game over");
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");

        attempts += 1;
        lastGuess = guess_;
        lastResultCode = previewGuess(guess_);

        if (lastResultCode == 0) {
            gameOver = true;
            wonByB = true;
        } else if (attempts >= maxAttempts) {
            gameOver = true;
            wonByB = false;
        }

        emit GuessEvaluated(playerB, guess_, lastResultCode, attempts, gameOver, wonByB);
    }

    function attemptsLeft() external view returns (uint8) {
        return maxAttempts - attempts;
    }
}
