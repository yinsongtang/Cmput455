"""
simple_board.py

Implements a basic Go board with functions to:
- initialize to a given board size
- check if a move is legal
- play a move

The board uses a 1-dimensional representation with padding
"""

import numpy as np
import time
from transpositiontable import TranspositionTable
from board_util import GoBoardUtil, BLACK, WHITE, EMPTY, BORDER, \
                       PASS, is_black_white, coord_to_point, where1d, \
                       MAXSIZE, NULLPOINT

class SimpleGoBoard(object):

    def get_color(self, point):
        return self.board[point]

    def pt(self, row, col):
        return coord_to_point(row, col, self.size)

    def is_legal(self, point, color):
        """
        Check whether it is legal for color to play on point
        """
        #board_copy = self.copy()
        # Try to play the move on a temporary copy of board
        # This prevents the board from being messed up by the move
        #try:
        #   legal = board_copy.play_move(point, color)
        #except:
        #    return False
        if point == PASS:
            return False
        elif self.board[point] != EMPTY:
            return False
        
        opp_color = GoBoardUtil.opponent(color)
        in_enemy_eye = self._is_surrounded(point, opp_color)
        self.board[point] = color
        single_captures = []
        neighbors = self.neighbors[point]
        for nb in neighbors:
            if self.board[nb] == opp_color:
                single_capture = self._detect_and_process_capture(nb)
                if single_capture == True:
                    self.board[point] = EMPTY
                    return False
        if not self._stone_has_liberty(point):
            # check suicide of whole block
            block = self._block_of(point)
            if not self._has_liberty(block): # undo suicide move
                self.board[point] = EMPTY
                return False
        self.board[point] = EMPTY
        return True
                
    def _detect_captures(self, point, opp_color):
        """
        Did move on point capture something?
        """
        for nb in self.neighbors_of_color(point, opp_color):
            if self._detect_capture(nb):
                return True
        return False

    def get_empty_points(self):
        """
        Return:
            The empty points on the board
        """
        return where1d(self.board == EMPTY)

    def __init__(self, size):
        """
        Creates a Go board of given size
        """
        assert 2 <= size <= MAXSIZE
        self.reset(size)

    def reset(self, size):
        """
        Creates a start state, an empty board with the given size
        The board is stored as a one-dimensional array
        See GoBoardUtil.coord_to_point for explanations of the array encoding
        """
        self.size = size
        self.NS = size + 1
        self.WE = 1
        self.ko_recapture = None
        self.current_player = BLACK
        self.moves = []
        self.current_winning_move = None
        self.maxpoint = size * size + 3 * (size + 1)
        self.board = np.full(self.maxpoint, BORDER, dtype = np.int32)
        self.liberty_of = np.full(self.maxpoint, NULLPOINT, dtype = np.int32)
        self._initialize_empty_points(self.board)
        self._initialize_neighbors()
        self.time = 0
        self.valid_points = self.valid_point()

    def row_start(self, row):
        assert row >= 1
        assert row <= self.size
        return row * self.NS + 1
        
    def _initialize_empty_points(self, board):
        """
        Fills points on the board with EMPTY
        Argument
        ---------
        board: numpy array, filled with BORDER
        """
        for row in range(1, self.size + 1):
            start = self.row_start(row)
            board[start : start + self.size] = EMPTY

    def _on_board_neighbors(self, point):
        nbs = []
        for nb in self._neighbors(point):
            if self.board[nb] != BORDER:
                nbs.append(nb)
        return nbs
            
    def _initialize_neighbors(self):
        """
        precompute neighbor array.
        For each point on the board, store its list of on-the-board neighbors
        """
        self.neighbors = []
        for point in range(self.maxpoint):
            if self.board[point] == BORDER:
                self.neighbors.append([])
            else:
                self.neighbors.append(self._on_board_neighbors(point))
        
    def is_eye(self, point, color):
        """
        Check if point is a simple eye for color
        """
        if not self._is_surrounded(point, color):
            return False
        # Eye-like shape. Check diagonals to detect false eye
        opp_color = GoBoardUtil.opponent(color)
        false_count = 0
        at_edge = 0
        for d in self._diag_neighbors(point):
            if self.board[d] == BORDER:
                at_edge = 1
            elif self.board[d] == opp_color:
                false_count += 1
        return false_count <= 1 - at_edge # 0 at edge, 1 in center
    
    def _is_surrounded(self, point, color):
        """
        check whether empty point is surrounded by stones of color.
        """
        for nb in self.neighbors[point]:
            nb_color = self.board[nb]
            if nb_color != color:
                return False
        return True

    def _stone_has_liberty(self, stone):
        lib = self.find_neighbor_of_color(stone, EMPTY)
        return lib != None

    def _get_liberty(self, block):
        """
        Find any liberty of the given block.
        Returns None in case there is no liberty.
        block is a numpy boolean array
        """
        for stone in where1d(block):
            lib = self.find_neighbor_of_color(stone, EMPTY)
            if lib != None:
                return lib
        return None

    def _has_liberty(self, block):
        """
        Check if the given block has any liberty.
        Also updates the liberty_of array.
        block is a numpy boolean array
        """
        lib = self._get_liberty(block)
        if lib != None:
            return True 
            '''assert self.get_color(lib) == EMPTY
            for stone in where1d(block):
                self.liberty_of[stone] = lib
            return True'''
        return False
    

    def _block_of(self, stone):
        """
        Find the block of given stone
        Returns a board of boolean markers which are set for
        all the points in the block 
        """
        marker = np.full(self.maxpoint, False, dtype = bool)
        pointstack = [stone]
        color = self.get_color(stone)
        assert is_black_white(color)
        marker[stone] = True
        while pointstack:
            p = pointstack.pop()
            neighbors = self.neighbors_of_color(p, color)
            for nb in neighbors:
                if not marker[nb]:
                    marker[nb] = True
                    pointstack.append(nb)
        return marker

    def _fast_liberty_check(self, nb_point):
        lib = self.liberty_of[nb_point]
        if lib != NULLPOINT and self.get_color(lib) == EMPTY:
            return True # quick exit, block has a liberty  
        if self._stone_has_liberty(nb_point):
            return True # quick exit, no need to look at whole block
        return False
        
    def _detect_capture(self, nb_point):
        """
        Check whether opponent block on nb_point is captured.
        Returns boolean.
        """
        if self._fast_liberty_check(nb_point):
            return False
        opp_block = self._block_of(nb_point)
        return not self._has_liberty(opp_block)
    
    def _detect_and_process_capture(self, nb_point):
        """
        Check whether opponent block on nb_point is captured.
        If yes, remove the stones.
        Returns the stone if only a single stone was captured,
            and returns None otherwise.
        This result is used in play_move to check for possible ko
        """
        opp_block = self._block_of(nb_point)
        if not self._has_liberty(opp_block):
            return True
        return False

    def play_move(self, point, color):
        """
        Play a move of color on point
        Returns boolean: whether move was legal
        """
        assert is_black_white(color)
        # Special cases
        if point == PASS:
            return False
        elif self.board[point] != EMPTY:
            raise ValueError("occupied")
        if point == self.ko_recapture:
            return False
            
        # General case: deal with captures, suicide, and next ko point
        opp_color = GoBoardUtil.opponent(color)
        in_enemy_eye = self._is_surrounded(point, opp_color)
        self.board[point] = color
        single_captures = []
        neighbors = self.neighbors[point]
        for nb in neighbors:
            if self.board[nb] == opp_color:
                single_capture = self._detect_and_process_capture(nb)
                if single_capture == True:
                    raise ValueError("capture")
        if not self._stone_has_liberty(point):
            # check suicide of whole block
            block = self._block_of(point)
            if not self._has_liberty(block): # undo suicide move
                self.board[point] = EMPTY
                raise ValueError("suicide")
        self.moves.append(point)
        self.ko_recapture = None
        if in_enemy_eye and len(single_captures) == 1:
            self.ko_recapture = single_captures[0]
        self.current_player = GoBoardUtil.opponent(color)
        return True
    
    def winner(self):
        result = BLACK if self.current_player == WHITE else WHITE
        return result

    def staticallyEvaluateForPlay(self):
        winColor = self.winner()
        assert winColor != EMPTY
        if winColor == self.current_player:
            return True
        assert winColor == GoBoardUtil.opponent(self.current_player)
        return False
    
    def valid_point(self):
        a = where1d(self.board == BLACK)
        b = where1d(self.board == WHITE)
        c = where1d(self.board == EMPTY)
        return np.concatenate([a,b,c])        
        
        
    def code(self):
        code = 0
        for i in self.valid_points:
            code += self.board[i] * (3 ** (i - self.size - 1))
        return code

    def storeResult(self, tt, result):
        tt.store(self.code(), result)
        return result
    
    def solve_single(self, tt, point):
        mid = int(((self.size+1)**2 + self.size + 1) / 2)
        fpoint = mid + mid - point[0]
        if time.time() > self.time:
            return False
        end = True
        codes = self.code()
        result = tt.lookup(codes)
        if result != None:
            return result
        empties = self.get_empty_points()
        color = self.current_player
        if fpoint in empties:
            end = False
            self.board[fpoint] = color
            self.current_player = GoBoardUtil.opponent(color)
            success = not self.negamaxBoolean(tt)
            self.board[fpoint] = EMPTY
            self.current_player = color
            if success:
                self.current_winning_move = fpoint
                tt.store(codes, True)
                return True
        for move in empties:
            if self.is_legal(move, color):
                end = False
                self.board[move] = color
                self.current_player = GoBoardUtil.opponent(color)
                success = not self.negamaxBoolean(tt)
                self.board[move] = EMPTY
                self.current_player = color
                if success:
                    self.current_winning_move = move
                    tt.store(codes, True)
                    return True
                    #return self.storeResult(tt, False)
                
        if end:
            result = self.staticallyEvaluateForPlay()
            tt.store(codes, result)
            return result
            #return self.storeResult(tt, result)
        tt.store(codes, False)
        return False
    
    def negamaxBoolean(self, tt):
        if time.time() > self.time:
            return False
        end = True
        codes = self.code()
        result = tt.lookup(codes)
        if result != None:
            return result
        empties = self.get_empty_points()
        color = self.current_player
        for move in empties:
            if self.is_legal(move, color):
                end = False
                self.board[move] = color
                self.current_player = GoBoardUtil.opponent(color)
                success = not self.negamaxBoolean(tt)
                self.board[move] = EMPTY
                self.current_player = color
                if success:
                    self.current_winning_move = move
                    tt.store(codes, True)
                    return True
                    #return self.storeResult(tt, False)
                
        if end:
            result = self.staticallyEvaluateForPlay()
            tt.store(codes, result)
            return result
            #return self.storeResult(tt, result)
        tt.store(codes, False)
        return False
        #return self.storeResult(tt, False)

    def call_search(self, point):
        tt = TranspositionTable() # use separate table for each color
        if point == None:
            return self.negamaxBoolean(tt)
        else:
            return self.solve_single(tt,point)

    def solveForColor(self, color, timelimit):
        self.current_winning_move = None
        assert is_black_white(color)
        self.time = time.time() + timelimit
        timeOut = False
        winForToPlay = self.negamaxBoolean()
        #if time.time() > self.time:
        #    timeOut = True
        winForColor = winForToPlay == (color == self.current_player)
        return winForColor, timeOut, self.current_winning_move
    
    def sigle_play(self):
        a = where1d(self.board == BLACK)
        b = where1d(self.board == WHITE)
        point = np.concatenate([a,b]) 
        if len(point) == 1:
            return point
        return   
        
    def solve(self, color, timelimit):
        #state.setDrawWinner(opponent(state.toPlay))
        self.time = time.time() + timelimit
        timeOut = False
        point = self.sigle_play()
        win = self.call_search(point)
        if time.time() > self.time:
            timeOut = True
        if win == (color == self.current_player):
            return True, timeOut, self.current_winning_move
    # loss or draw, do second search to find out
    #state.setDrawWinner(state.toPlay)
    #if self.call_search():
    #return EMPTY # draw
        else: # loss
            return False, timeOut, self.current_winning_move
            #return opponent(state.toPlay)

    def neighbors_of_color(self, point, color):
        """ List of neighbors of point of given color """
        nbc = []
        for nb in self.neighbors[point]:
            if self.get_color(nb) == color:
                nbc.append(nb)
        return nbc
        
    def find_neighbor_of_color(self, point, color):
        """ Return one neighbor of point of given color, or None """
        for nb in self.neighbors[point]:
            if self.get_color(nb) == color:
                return nb
        return None
        
    def _neighbors(self, point):
        """ List of all four neighbors of the point """
        return [point - 1, point + 1, point - self.NS, point + self.NS]

    def _diag_neighbors(self, point):
        """ List of all four diagonal neighbors of point """
        return [point - self.NS - 1, 
                point - self.NS + 1, 
                point + self.NS - 1, 
                point + self.NS + 1]
    
    def _point_to_coord(self, point):
        """
        Transform point index to row, col.
        
        Arguments
        ---------
        point
        
        Returns
        -------
        x , y : int
        coordination of the board  1<= x <=size, 1<= y <=size .
        """
        if point is None:
            return 'pass'
        row, col = divmod(point, self.NS)
        return row, col

    # def is_legal_gomoku(self, point, color):
    #     """
    #         Check whether it is legal for color to play on point, for the game of gomoku
    #         """
    #     return self.board[point] == EMPTY
    
    # def play_move_gomoku(self, point, color):
    #     """
    #         Play a move of color on point, for the game of gomoku
    #         Returns boolean: whether move was legal
    #         """
    #     assert is_black_white(color)
    #     assert point != PASS
    #     if self.board[point] != EMPTY:
    #         return False
    #     self.board[point] = color
    #     self.current_player = GoBoardUtil.opponent(color)
    #     return True
        
    # def _point_direction_check_connect_gomoko(self, point, shift):
    #     """
    #     Check if the point has connect5 condition in a direction
    #     for the game of Gomoko.
    #     """
    #     color = self.board[point]
    #     count = 1
    #     d = shift
    #     p = point
    #     while True:
    #         p = p + d
    #         if self.board[p] == color:
    #             count = count + 1
    #             if count == 5:
    #                 break
    #         else:
    #             break
    #     d = -d
    #     p = point
    #     while True:
    #         p = p + d
    #         if self.board[p] == color:
    #             count = count + 1
    #             if count == 5:
    #                 break
    #         else:
    #             break
    #     assert count <= 5
    #     return count == 5
    
    # def point_check_game_end_gomoku(self, point):
    #     """
    #         Check if the point causes the game end for the game of Gomoko.
    #         """
    #     # check horizontal
    #     if self._point_direction_check_connect_gomoko(point, 1):
    #         return True
        
    #     # check vertical
    #     if self._point_direction_check_connect_gomoko(point, self.NS):
    #         return True
        
    #     # check y=x
    #     if self._point_direction_check_connect_gomoko(point, self.NS + 1):
    #         return True
        
    #     # check y=-x
    #     if self._point_direction_check_connect_gomoko(point, self.NS - 1):
    #         return True
        
    #     return False
    
    # def check_game_end_gomoku(self):
    #     """
    #         Check if the game ends for the game of Gomoku.
    #         """
    #     white_points = where1d(self.board == WHITE)
    #     black_points = where1d(self.board == BLACK)
        
    #     for point in white_points:
    #         if self.point_check_game_end_gomoku(point):
    #             return True, WHITE
    
    #     for point in black_points:
    #         if self.point_check_game_end_gomoku(point):
    #             return True, BLACK

    #     return False, None
