// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV4 {
    address payable public immutable playerA;
    address payable public immutable playerB;
    bytes32 public immutable merkleRoot;
    uint8 public immutable maxAttempts;
    uint256 public immutable stake;

    uint8 public attempts;
    bool public joined;
    bool public gameOver;
    bool public wonByB;
    uint8 public pendingGuess;
    bool public hasPendingGuess;
    uint8 public lastResolvedGuess;
    int8 public lastResultCode; // -1 too high, 0 correct, 1 too low, 2 none yet

    event Joined(address indexed playerB, uint256 stake);
    event GuessSubmitted(address indexed playerB, uint8 guess, uint8 attemptsUsed);
    event GuessResolved(address indexed playerA, uint8 guess, int8 resultCode, bool gameOver, bool wonByB);
    event Payout(address indexed winner, uint256 amount);

    constructor(address _playerB, bytes32 _merkleRoot, uint8 _maxAttempts) payable {
        require(_playerB != address(0), "playerB required");
        require(_merkleRoot != bytes32(0), "root required");
        require(_maxAttempts > 0, "maxAttempts must be > 0");
        require(msg.value > 0, "stake required");

        playerA = payable(msg.sender);
        playerB = payable(_playerB);
        merkleRoot = _merkleRoot;
        maxAttempts = _maxAttempts;
        stake = msg.value;
        lastResultCode = 2;
    }

    modifier onlyPlayerA() {
        require(msg.sender == playerA, "only playerA");
        _;
    }

    modifier onlyPlayerB() {
        require(msg.sender == playerB, "only playerB");
        _;
    }

    function join() external payable onlyPlayerB {
        require(!joined, "already joined");
        require(msg.value == stake, "exact stake required");
        joined = true;
        emit Joined(playerB, msg.value);
    }

    function submitGuess(uint8 guess_) external onlyPlayerB {
        require(joined, "playerB not joined");
        require(!gameOver, "game over");
        require(!hasPendingGuess, "resolve pending guess first");
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");

        attempts += 1;
        pendingGuess = guess_;
        hasPendingGuess = true;
        emit GuessSubmitted(msg.sender, guess_, attempts);
    }

    function resolveGuess(uint8 guess_, int8 resultCode, bytes32[] calldata proof) external onlyPlayerA {
        require(!gameOver, "game over");
        require(hasPendingGuess, "no pending guess");
        require(guess_ == pendingGuess, "wrong pending guess");
        require(resultCode >= -1 && resultCode <= 1, "bad result code");
        require(_verify(proof, _leaf(guess_, resultCode)), "invalid proof");

        hasPendingGuess = false;
        lastResolvedGuess = guess_;
        lastResultCode = resultCode;

        if (resultCode == 0) {
            gameOver = true;
            wonByB = true;
            _pay(playerB, address(this).balance);
        } else if (attempts >= maxAttempts) {
            gameOver = true;
            wonByB = false;
            _pay(playerA, address(this).balance);
        }

        emit GuessResolved(msg.sender, guess_, resultCode, gameOver, wonByB);
    }

    function attemptsLeft() external view returns (uint8) {
        return maxAttempts - attempts;
    }

    function contractBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function _leaf(uint8 guess_, int8 resultCode) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(guess_, resultCode));
    }

    function _verify(bytes32[] calldata proof, bytes32 leaf_) internal view returns (bool) {
        bytes32 computed = leaf_;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 sibling = proof[i];
            if (computed <= sibling) {
                computed = keccak256(abi.encodePacked(computed, sibling));
            } else {
                computed = keccak256(abi.encodePacked(sibling, computed));
            }
        }
        return computed == merkleRoot;
    }

    function _pay(address payable to, uint256 amount) internal {
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "transfer failed");
        emit Payout(to, amount);
    }
}
