import random
import time
from collections import namedtuple
from abc import ABC, abstractmethod
from typing import List
# from pg_game import PG_Game

Action = namedtuple("Action", "insert_end, domino, flip")
TurnData = namedtuple("TurnData", "played_dominos, legal_moves")
GameData = namedtuple("GameData",
                      "played_dominos, player_datas, current_turn_index")
PlayerData = namedtuple("PlayerData", "name, hand, score")
TurnDataPoint = namedtuple("TurnDataPoint", "player_name, did_play, domino_played")


class ActionChooser(ABC):
    @abstractmethod
    def choose_action(self, data: TurnData) -> Action:
        pass


class ActionChooser_Random(ActionChooser):
    def choose_action(self, data: TurnData) -> Action:
        moves = data.legal_moves
        random.shuffle(moves)
        move = moves[0]
        return move


class ActionChooser_Player(ActionChooser):
    def choose_action(self, data: TurnData) -> Action:
        print(f'legal moves: {str(data.legal_moves).strip("[]")}')
        index = int(input(f'choose move[1-{len(data.legal_moves)}]: '))
        return data.legal_moves[index - 1]


class DisplayWrapper(ABC):
    @abstractmethod
    def display_game(self, game_data):
        pass

class DisplayWrapper_None(DisplayWrapper):
  def display_game(self, game_data):
    pass

class DisplayWrapper_Terminal(DisplayWrapper):
    def clear_term(self):
        time.sleep(0.1)
        print("\n" * 10)

    def display_game(self, game_data: GameData):
        players = game_data.player_datas
        string = f'{players[0].name}, {players[2].name}: {players[0].score} | {players[1].name}, {players[3].name}: {players[1].score}'
        string += f'\nin play: {game_data.played_dominos}'
        for i, p in enumerate(players):
            indicator = '>' if i == game_data.current_turn_index else ' '
            string += f'\n{indicator}{p.name}: {p.hand}'

        self.clear_term()
        print(string)


class Player:
    def __init__(self, name, action_chooser):
        self._name = name
        self._dominos = []
        self._action_chooser = action_chooser
        self.score = 0

    def reset(self):
        self._dominos = []

    def give_dominos(self, dominos):
        self._dominos = dominos

    def is_hand_empty(self):
        return len(self._dominos) == 0

    def has_double_six(self):
        return self._dominos.count((6, 6)) == 1

    def play_double_six(self, played_dominos):
        played_dominos.append((6, 6))
        self._dominos.remove((6, 6))
        return played_dominos

    def take_turn(self, played_dominos):
        moves = self.get_legal_moves(played_dominos)
        if len(moves) == 0: return False, played_dominos, None
        data = TurnData(played_dominos, moves)
        move = self._action_chooser.choose_action(data)
        domino = move.domino[::-1] if move.flip else move.domino
        if move.insert_end: played_dominos.append(domino)
        else: played_dominos.insert(0, domino)
        self._dominos.remove(move.domino)
        return True, played_dominos, domino

    def get_legal_moves(self, played_dominos) -> List[Action]:
        if len(played_dominos) == 0:
            return [Action(True, d, False) for d in self._dominos]
        head = played_dominos[0][0]
        tail = played_dominos[-1][1]
        actions = []
        for d in self._dominos:
            if d[0] == tail: actions.append(Action(True, d, False))
            if d[1] == tail: actions.append(Action(True, d, True))
            if d[0] == head: actions.append(Action(False, d, True))
            if d[1] == head: actions.append(Action(False, d, False))
        return actions

    def get_points(self):
        return sum(map(sum, self._dominos))

    def to_player_data(self):
        return PlayerData(self._name, self._dominos, self.score)

    def __str__(self):
        return f'{self._name}: {self._dominos}'


class Game:
    DOMINOS = ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 1),
               (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (2, 2), (2, 3), (2, 4),
               (2, 5), (2, 6), (3, 3), (3, 4), (3, 5), (3, 6), (4, 4), (4, 5),
               (4, 6), (5, 5), (5, 6), (6, 6))

    def __init__(self,
                 round_score=200,
                 display_wrapper=DisplayWrapper_Terminal()):
        self.num_players = 4
        self.round_score = round_score
        self.game_num = 1
        self.round_num = 1
        self._display_wrapper = display_wrapper

    def _reset(self):
        self.played_dominos = []
        self.round_history = []
        for p in self.players:
            p.reset()

    def new_game(self, _players=None, shuffle_players=False):
        if _players == None:
            _players = [
                Player(f'P{i+1}', ActionChooser_Random())
                for i in range(self.num_players)
            ]
        if shuffle_players:
            random.shuffle(_players)
        self.players = _players
        self._reset()
        self.winner = self.players[0]
        self.first_game_round_step = True

    def new_round(self):
        self._reset()
        pool = list(self.DOMINOS)
        random.shuffle(pool)
        for i in range(len(self.players)):
            self.players[i].give_dominos(pool[i::4])
        if self.first_game_round_step:
            for p in self.players:
                if p.has_double_six():
                    self.winner = p
                    break
        self.next_player_index = self.players.index(self.winner)

    def step(self):
        next_player = self.players[self.next_player_index]
        did_play = False
        domino_played = None
        if self.first_game_round_step:
            self.played_dominos = next_player.play_double_six(
                self.played_dominos)
            did_play = True
            domino_played = (6,6)
            self.first_game_round_step = False
        else:
            did_play, self.played_dominos, domino_played = next_player.take_turn(self.played_dominos)
        self.round_history.append(TurnDataPoint(next_player._name, did_play, domino_played))

        self.check_for_bonus_points()

        if next_player.is_hand_empty():
            self.winner = next_player
            return False
        if self.is_locked():
            p_current = next_player
            p_next = self.players[self.get_next_player_index()]
            self.winner = p_current if p_current.get_points(
            ) < p_next.get_points() else p_next
            return False
        self.next_player_index = self.get_next_player_index()
        return True

    def check_for_bonus_points(self):
      bonus_points = 25
      if len(self.round_history) < 2: return

      last_move = self.round_history[-1]
      if last_move.did_play: return
      last_player = self.get_player_by_name(last_move.player_name)
      if len(self.round_history) == 2:
        self.give_points_to_team(last_player, bonus_points)
        return
      
      if len(self.round_history) < 4: return
      last_four = self.round_history[-4:]
      if last_four[0].did_play and not last_four[1].did_play and not last_four[2].did_play and not last_four[3].did_play:
        player = self.get_player_by_name(last_four[0].player_name)
        self.give_points_to_team(player, bonus_points)
        return

      if not last_player.is_hand_empty(): return
      last_domino = last_move.domino_played
      dominos_played_wout_last = self.played_dominos.remove(last_domino)
      head = dominos_played_wout_last[0][0]
      tail = dominos_played_wout_last[-1][1]
      if (last_domino[0] == head and last_domino[1] == tail) or (last_domino[1] == head and last_domino[0] == tail):
        self.give_points_to_team(last_player, bonus_points)
        return


    def get_player_by_name(self, name):
      players = [p for p in self.players if p._name == name]
      return players[0]

    def get_next_player_index(self):
      return (self.next_player_index + 1) % len(
            self.players)

    def give_points_to_team(self, player, points):
        player_index = self.players.index(self.winner)
        team = self.players[
            0::2] if player_index == 0 or player_index == 2 else self.players[
                1::2]
        for p in team:
            p.score += points

    def update_score(self):
        total_points = sum(p.get_points() for p in self.players)
        self.give_points_to_team(self.winner, total_points)
        # winner_index = self.players.index(self.winner)
        # winner_team = self.players[
        #     0::2] if winner_index == 0 or winner_index == 2 else self.players[
        #         1::2]
        # for p in winner_team:
        #     p.score += total_points

    def is_locked(self):
        head = self.played_dominos[0][0]
        tail = self.played_dominos[-1][1]
        if head != tail: return False

        count = 0
        for d in self.played_dominos:
            if d[0] == head: count += 1
            if d[1] == head: count += 1

        if count == 8: return True
        return False

    def display_score(self):
        for p in self.players:
            print(f'{p._name}: {p.score}')

    def play_round(self):
        self.new_round()
        while self.step():
            self._display_wrapper.display_game(self.to_game_data())
        self._display_wrapper.display_game(self.to_game_data())
        self.update_score()

    def to_game_data(self):
        return GameData(self.played_dominos,
                        [p.to_player_data() for p in self.players],
                        self.next_player_index)

    def play_game(self, _players=None, shuffle_players=False):
        self.new_game(_players, shuffle_players)
        while self.winner.score < self.round_score:
            self.play_round()

    def __str__(self):
        string = f'in play: {self.played_dominos}'
        for i, p in enumerate(self.players):
            indicator = '>' if i == self.next_player_index else ' '
            string += f'\n{indicator}{p}'
        return string


def playgame():
    game = Game(100)
    # players = [Player(f'R{i+1}', ActionChooser_Random()) for i in range(3)]
    # players.append(Player('PH', ActionChooser_Player()))
    # game.play_game(_players=players, shuffle_players=True)
    game.play_game()
    game.display_score()


def main():
    playgame()
    # pg_game = PG_Game()
    # pg_game.run()


if __name__ == "__main__":
    main()
