// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GuessNumberV3 {
    struct Game {
        address payable playerA;
        address payable playerB;
        uint8 secretNumber;
        uint8 maxAttempts;
        uint8 attempts;
        uint256 stake;
        bool joined;
        bool gameOver;
        bool wonByB;
        int8 lastResultCode;
        uint8 lastGuess;
    }

    uint256 public totalGames;
    mapping(uint256 => Game) private games;

    event GameCreated(uint256 indexed gameId, address indexed playerA, address indexed playerB, uint256 stake, uint8 maxAttempts);
    event GameJoined(uint256 indexed gameId, address indexed playerB, uint256 stake);
    event GuessEvaluated(uint256 indexed gameId, address indexed playerB, uint8 guess, int8 resultCode, uint8 attemptsUsed, bool gameOver, bool wonByB);
    event Payout(uint256 indexed gameId, address indexed winner, uint256 amount);

    function createGame(address _playerB, uint8 _secretNumber, uint8 _maxAttempts) external payable returns (uint256 gameId) {
        require(_playerB != address(0), "playerB required");
        require(_secretNumber >= 1 && _secretNumber <= 100, "secret out of range");
        require(_maxAttempts > 0, "maxAttempts must be > 0");
        require(msg.value > 0, "stake required");

        gameId = totalGames;
        totalGames += 1;

        Game storage g = games[gameId];
        g.playerA = payable(msg.sender);
        g.playerB = payable(_playerB);
        g.secretNumber = _secretNumber;
        g.maxAttempts = _maxAttempts;
        g.stake = msg.value;
        g.lastResultCode = 2;

        emit GameCreated(gameId, msg.sender, _playerB, msg.value, _maxAttempts);
    }

    function joinGame(uint256 gameId) external payable {
        Game storage g = games[gameId];
        require(g.playerA != address(0), "game not found");
        require(msg.sender == g.playerB, "only playerB");
        require(!g.joined, "already joined");
        require(msg.value == g.stake, "exact stake required");

        g.joined = true;
        emit GameJoined(gameId, msg.sender, msg.value);
    }

    function previewGuess(uint256 gameId, uint8 guess_) public view returns (int8) {
        Game storage g = games[gameId];
        require(g.playerA != address(0), "game not found");
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");
        if (guess_ == g.secretNumber) return 0;
        if (guess_ < g.secretNumber) return 1;
        return -1;
    }

    function guess(uint256 gameId, uint8 guess_) external {
        Game storage g = games[gameId];
        require(g.playerA != address(0), "game not found");
        require(msg.sender == g.playerB, "only playerB");
        require(g.joined, "playerB not joined");
        require(!g.gameOver, "game over");
        require(guess_ >= 1 && guess_ <= 100, "guess out of range");

        g.attempts += 1;
        g.lastGuess = guess_;
        g.lastResultCode = previewGuess(gameId, guess_);

        if (g.lastResultCode == 0) {
            g.gameOver = true;
            g.wonByB = true;
            _pay(gameId, g.playerB, g.stake * 2);
        } else if (g.attempts >= g.maxAttempts) {
            g.gameOver = true;
            g.wonByB = false;
            _pay(gameId, g.playerA, g.stake * 2);
        }

        emit GuessEvaluated(gameId, msg.sender, guess_, g.lastResultCode, g.attempts, g.gameOver, g.wonByB);
    }

    function getGame(uint256 gameId)
        external
        view
        returns (
            address playerA,
            address playerB,
            uint8 maxAttempts,
            uint8 attempts,
            uint256 stake,
            bool joined,
            bool gameOver,
            bool wonByB,
            int8 lastResultCode,
            uint8 lastGuess
        )
    {
        Game storage g = games[gameId];
        require(g.playerA != address(0), "game not found");
        return (g.playerA, g.playerB, g.maxAttempts, g.attempts, g.stake, g.joined, g.gameOver, g.wonByB, g.lastResultCode, g.lastGuess);
    }

    function attemptsLeft(uint256 gameId) external view returns (uint8) {
        Game storage g = games[gameId];
        require(g.playerA != address(0), "game not found");
        return g.maxAttempts - g.attempts;
    }

    function _pay(uint256 gameId, address payable to, uint256 amount) internal {
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "transfer failed");
        emit Payout(gameId, to, amount);
    }
}
