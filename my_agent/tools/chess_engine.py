import shutil
import chess
import chess.engine


def _find_stockfish() -> str:
    """Find the Stockfish binary on this system."""
    # Check PATH first (works if installed via brew, apt, or manually)
    path = shutil.which("stockfish")
    if path:
        return path

    # Common locations by platform
    candidates = [
        "/opt/homebrew/bin/stockfish",      # macOS Apple Silicon (brew)
        "/usr/local/bin/stockfish",         # macOS Intel (brew)
        "/usr/games/stockfish",             # Ubuntu/Debian (apt)
        "/usr/bin/stockfish",               # Other Linux
        "/snap/bin/stockfish",              # Snap
    ]
    for p in candidates:
        if shutil.which(p) or __import__("os").path.isfile(p):
            return p

    return "stockfish"  # Last resort — hope it's on PATH at runtime


_STOCKFISH_PATH = _find_stockfish()


def analyze_chess_position(fen: str, depth: int = 40) -> str:
    """Analyze a chess position and return the best move.

    Takes a FEN string describing a chess position and uses the Stockfish
    engine to find the best move. Returns the move in standard algebraic
    notation (SAN), e.g. "Rd5", "Nf3", "e4", "O-O".

    IMPORTANT: When converting a chess board image to FEN:
    - FEN describes the board from rank 8 (top) to rank 1 (bottom).
    - Each rank is described left to right (a-file to h-file).
    - Uppercase = White pieces (K, Q, R, B, N, P).
    - Lowercase = Black pieces (k, q, r, b, n, p).
    - Numbers = consecutive empty squares.
    - Ranks are separated by '/'.
    - After the board, specify: active color (w/b), castling rights
      (KQkq or -), en passant square (- or e.g. e3), halfmove clock,
      fullmove number.
    - Example starting position:
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    Args:
        fen: A FEN string describing the chess position.
             Must include active color (whose turn it is).
        depth: Search depth for Stockfish (default 22, higher = stronger
               but slower). Use 25+ for mate-finding puzzles.

    Returns:
        A string with the best move in algebraic notation, the evaluation
        score, and the principal variation (best line), or an error message.
    """
    # Validate the FEN
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return f"Error: Invalid FEN string — {e}"

    if not board.is_valid():
        # Try to be helpful about common FEN mistakes
        issues = []
        status = board.status()
        if status & chess.STATUS_NO_WHITE_KING:
            issues.append("no white king")
        if status & chess.STATUS_NO_BLACK_KING:
            issues.append("no black king")
        if status & chess.STATUS_TOO_MANY_KINGS:
            issues.append("too many kings")
        if issues:
            return f"Error: Invalid position — {', '.join(issues)}. Double-check the FEN."
        return "Error: Invalid chess position. Double-check the FEN."

    if board.is_game_over():
        return f"The game is already over: {board.result()}"

    # Run Stockfish
    try:
        engine = chess.engine.SimpleEngine.popen_uci(_STOCKFISH_PATH)
    except Exception as e:
        return f"Error: Could not start Stockfish — {e}"

    try:
        # Use both depth and time limit for thoroughness
        result = engine.analyse(
            board,
            chess.engine.Limit(depth=depth, time=10.0),
        )
    except Exception as e:
        engine.quit()
        return f"Error: Stockfish analysis failed — {e}"

    engine.quit()

    # Extract results
    best_move_uci = result.get("pv", [None])[0]
    if best_move_uci is None:
        return "Error: Stockfish could not find a move."

    # Convert to standard algebraic notation (SAN)
    best_move_san = board.san(best_move_uci)

    # Get the score
    score = result.get("score")
    if score:
        pov_score = score.relative  # from the perspective of the side to move
        if pov_score.is_mate():
            score_str = f"Mate in {pov_score.mate()}"
        else:
            cp = pov_score.score()
            score_str = f"{cp/100:+.2f} pawns"
    else:
        score_str = "unknown"

    # Get the principal variation (best line)
    pv = result.get("pv", [])
    pv_board = board.copy()
    pv_san = []
    for move in pv[:10]:  # Show up to 10 moves
        pv_san.append(pv_board.san(move))
        pv_board.push(move)

    turn = "White" if board.turn == chess.WHITE else "Black"

    return (
        f"Best move for {turn}: {best_move_san}\n"
        f"Evaluation: {score_str}\n"
        f"Best line: {' '.join(pv_san)}"
    )
