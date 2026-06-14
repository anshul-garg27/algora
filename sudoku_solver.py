#!/usr/bin/env python3
import random
from copy import deepcopy

class SudokuSolver:
    def __init__(self):
        self.board = None
        self.original = None

    def is_valid(self, board, row, col, num):
        for x in range(9):
            if board[row][x] == num:
                return False
        for x in range(9):
            if board[x][col] == num:
                return False
        start_row = row - row % 3
        start_col = col - col % 3
        for i in range(3):
            for j in range(3):
                if board[i + start_row][j + start_col] == num:
                    return False
        return True

    def solve(self, board):
        for i in range(9):
            for j in range(9):
                if board[i][j] == 0:
                    for num in range(1, 10):
                        if self.is_valid(board, i, j, num):
                            board[i][j] = num
                            if self.solve(board):
                                return True
                            board[i][j] = 0
                    return False
        return True

    def count_solutions(self, board, max_solutions=2):
        count = [0]

        def solve_count():
            if count[0] >= max_solutions:
                return
            for i in range(9):
                for j in range(9):
                    if board[i][j] == 0:
                        for num in range(1, 10):
                            if self.is_valid(board, i, j, num):
                                board[i][j] = num
                                solve_count()
                                board[i][j] = 0
                        return
            count[0] += 1

        solve_count()
        return count[0]

    def generate_puzzle(self, difficulty='hard'):
        self.board = [[0 for _ in range(9)] for _ in range(9)]

        # Fill diagonal 3x3 boxes
        for box in range(3):
            nums = list(range(1, 10))
            random.shuffle(nums)
            for i in range(3):
                for j in range(3):
                    self.board[box * 3 + i][box * 3 + j] = nums[i * 3 + j]

        # Solve to get a complete valid board
        board_copy = deepcopy(self.board)
        self.solve(board_copy)
        self.board = board_copy

        # Remove numbers to create puzzle
        removed = 0
        target = 45 if difficulty == 'hard' else 35

        positions = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(positions)

        for row, col in positions:
            if removed >= target:
                break

            val = self.board[row][col]
            self.board[row][col] = 0

            # Check if puzzle still has unique solution
            test_board = deepcopy(self.board)
            if self.count_solutions(test_board) == 1:
                removed += 1
            else:
                self.board[row][col] = val

        self.original = deepcopy(self.board)
        return self.board

    def solve_puzzle(self):
        board_copy = deepcopy(self.board)
        if self.solve(board_copy):
            self.board = board_copy
            return True
        return False

    def is_valid_solution(self):
        board = self.board
        for i in range(9):
            for j in range(9):
                val = board[i][j]
                if val == 0:
                    return False
                if not (1 <= val <= 9):
                    return False

        for i in range(9):
            row = board[i]
            if len(set(row)) != 9 or any(x == 0 for x in row):
                return False

        for j in range(9):
            col = [board[i][j] for i in range(9)]
            if len(set(col)) != 9 or any(x == 0 for x in col):
                return False

        for box_row in range(3):
            for box_col in range(3):
                box = []
                for i in range(3):
                    for j in range(3):
                        box.append(board[box_row * 3 + i][box_col * 3 + j])
                if len(set(box)) != 9 or any(x == 0 for x in box):
                    return False

        return True

def main():
    total = 1000
    successful = 0

    for _ in range(total):
        solver = SudokuSolver()
        solver.generate_puzzle(difficulty='hard')

        if solver.solve_puzzle():
            if solver.is_valid_solution():
                successful += 1

    print(successful)

if __name__ == "__main__":
    main()
