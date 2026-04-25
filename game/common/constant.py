# Game phases as string constants for compatibility with TypedDict
class GamePhase:
    SETUP = "setup"
    SPEAKING = "speaking"
    VOTING = "voting"
    RESULT = "result"


class PlayerRole:
    CIVILIAN = "civilian"
    SPY = "spy"

class GameWinner:
    CIVILIANS = "civilians"
    SPIES = "spies"
