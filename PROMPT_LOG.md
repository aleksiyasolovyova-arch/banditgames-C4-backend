Prompt 1: (attached original files)

You are a software engineer. I want you to recreate this connect-4 game backend. It is currently written in typescript.
I want you to redo it in python. I want you to do OOP, following best practices. Further down the road, an ai will be
trained on the game, so for that, i want you to accommodate the following: The game state contains all the information
needed to: describe the current game situation unambiguously, determine legal actions based on that situation, evaluate
that state, generate the next state, … adapt according to the game in question You may need to refactor the game
implementation to accommodate for a more rich game state implementation. What can be included in the game state? All
observable things. So all information that a player/opponent or an AI player can see, for example: Game configuration:
board dimensions, board state, location of players, etc. Turn information: whose turn it is, turn/move number, remaining
time (if applicable). Legal actions: the set of actions that are currently allowed. History (optional): previous moves
Game status: is the game still in progress, if not, what is the outcome (win/loss/draw) and associated reward(s). How
many points have already been earned, etc.... whatever else you deem necessary... Consider the serialization of the game
state: a unique representation (e.g. JSON) so that the state can be saved and transmitted over the wire. In short: Build
a system that logs every move and game state for later ML model training. Async/batch logging for performance. Utility
values calculated and logged. The game will later have a front end in react. For that, i want you to use FastAPI. Also
create a requirements.txt with all needed python libraries.

Prompt 2:
Scrap your game logging implementation. I want the game state to be returned after every move. Give me the new code

Prompt 3:
Create a Dockerfile that is suitable.

