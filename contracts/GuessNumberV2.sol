// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV2 {
    address payable public immutable playerA;
    address payable public immutable playerB;
    uint8 private immutable secretNumber;
    uint8 public immutable maxAttempts;
    uint256 public immutable stake;

    uint8 public attempts;
    bool public joined;
    bool public gameOver;
    bool public wonByB;
    int8 public lastResultCode; // -1 too high, 0 correct, 1 too low
    uint8 public lastGuess;

    event Joined(address indexed playerB, uint256 stake);
    event GuessEvaluated(address indexed playerB, uint8 guess, int8 resultCode, uint8 attemptsUsed, bool gameOver, bool wonByB);
    event Payout(address indexed winner, uint256 amount);

    constructor(address _playerB, uint8 _secretNumber, uint8 _maxAttempts) payable {
        require(_playerB != address(0), "playerB required");
        require(_secretNumber >= 1 && _secretNumber <= 100, "secret out of range");
        require(_maxAttempts > 0, "maxAttempts must be > 0");
        require(msg.value > 0, "stake required");

        playerA = payable(msg.sender);
        playerB = payable(_playerB);
        secretNumber = _secretNumber;
        maxAttempts = _maxAttempts;
        stake = msg.value;
        lastResultCode = 2;
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

    function join() external payable onlyPlayerB {
        require(!joined, "already joined");
        require(msg.value == stake, "exact stake required");
        joined = true;
        emit Joined(playerB, msg.value);
    }

    function guess(uint8 guess_) external onlyPlayerB {
        require(joined, "playerB not joined");
        require(!gameOver, "game over");
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");

        attempts += 1;
        lastGuess = guess_;
        lastResultCode = previewGuess(guess_);

        if (lastResultCode == 0) {
            gameOver = true;
            wonByB = true;
            _pay(playerB, address(this).balance);
        } else if (attempts >= maxAttempts) {
            gameOver = true;
            wonByB = false;
            _pay(playerA, address(this).balance);
        }

        emit GuessEvaluated(playerB, guess_, lastResultCode, attempts, gameOver, wonByB);
    }

    function attemptsLeft() external view returns (uint8) {
        return maxAttempts - attempts;
    }

    function contractBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function _pay(address payable to, uint256 amount) internal {
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "transfer failed");
        emit Payout(to, amount);
    }
}
