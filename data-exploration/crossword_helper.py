from __future__ import annotations
from typing import Optional

from dataclasses import dataclass
import json

from numpy import inf


class Crossword:
    """Used to generate a crossword based on a config file and list of possible clues.

    Attributes:
        title (str): Title of the crossword.
        author (str): Author of the crossword.
        date (str): Date of the crossword.
        grid (list[str]): Representation of crossword grid where each string represents a row
            and each character represents a cell. The characters indicated the following:
            .       blank (to be generated)
            #       unused (blacked out)
            [a-z]   special (shaded or circled)
            [A-Z]   regular (known constraint)
        height (int): Height of the crossword based on the grid.
        width (int): Width of the crossword based on the grid.
        clues (dict[str, str]): Map of possible answers to their associated clue.
        entries (set[Entry]): Representations of the entries in the crossword.

    """

    def __init__(self, config_file, clues):
        """

        Args:
            config_file (str): Path to .json containing crossword metadata.
            clues (dict[str, str]): Map of possible answers to their associated clue.

        """
        # Import config file
        with open(config_file) as f:
            config = json.load(f)
        try:
            self.title = config['title']
            self.author = config['author']
            self.date = config['date']
            self.grid = config['grid']
            self.height = len(self.grid)
            self.width = len(self.grid[0])
        except KeyError:
            raise KeyError("config file must have title, author, date, and grid")

        # Convert clues to data class
        clues = [Clue(clue['answer'], clue['clue'], clue['priority']) for clue in clues]

        # Initialize crossword entries
        self.entries = []
        clue_enum = 1
        for i in range(self.height):
            for j in range(self.width):
                cell_starts_clue = False

                # Check if cell starts across entry
                if self.grid[i][j] != '#' and (j == 0 or self.grid[i][j-1] == '#'):
                    length = 1
                    while j + length < self.width and self.grid[i][j + length] != '#':
                        length += 1
                    if length > 1:
                        self.entries.append(Entry(f"A{str(clue_enum).zfill(2)}", (i, j), length, clues))
                        cell_starts_clue = True

                # Check if cell starts down entry
                if self.grid[i][j] != '#' and (i == 0 or self.grid[i-1][j] == '#'):
                    length = 1
                    while i + length < self.height and self.grid[i + length][j] != '#':
                        length += 1
                    if length > 1:
                        self.entries.append(Entry(f"D{str(clue_enum).zfill(2)}", (i, j), length, clues))
                        cell_starts_clue = True

                if cell_starts_clue:
                    clue_enum += 1

        # Add overlaps to entries
        for entry1 in self.entries:
            for entry2 in self.entries:
                if entry1 != entry2:
                    entry1.update_overlap(entry2)

    def generate(self, out_file: str = "", used_words: set[str] = set()):
        # Generate crossword
        if self._generate(used_words) is not None:
            Exception("Crossword could not be generated with word list")

        # Update clues for entries and fill in grid
        for entry in self.entries:
            for i in range(entry.length):
                row, col = entry.cells[i]
                self.grid[row][col] = entry.clue.answer[i]

        if out_file:
            self.export(out_file)

    def _generate(self, used_words: set[str] = set(), print_grid: bool = True) -> Optional[Entry]:
        # Get entries not yet assigned a clue
        possible_entries = [e for e in self.entries if not e.clue]

        # Return None if crossword is complete
        if len(possible_entries) == 0:
            return None

        # Find entry with least possible words and most intersections
        # TODO: Prioritize maximum remaining intersections over minimum possible words?
        entry = None
        clue_count = inf
        intersection_count = 0
        for e in possible_entries:
            e.update_constraints(used_words)
            # if e.clues_remaining() == 0:
            #     return e
            # elif e.open_intersections() > intersection_count:
            #     entry = e
            #     clue_count = e.clues_remaining()
            #     intersection_count = e.open_intersections()
            # elif e.open_intersections() == intersection_count and e.clues_remaining() < clue_count:
            #     entry = e
            #     intersection_count = e.open_intersections()
            if e.clues_remaining() < clue_count:
                entry = e
                clue_count = e.clues_remaining()
                intersection_count = e.open_intersections()
            elif e.clues_remaining() == clue_count and e.open_intersections() > intersection_count:
                entry = e
                intersection_count = e.open_intersections()

        # Try generating puzzle with word assigned to entry
        for clue in entry.sorted_clues():
            # Assign word to entry and remove from possible words
            entry.clue = clue
            used_words.add(clue.answer)

            # Generate and print grid if flag is set
            if print_grid:
                local_grid = [[x for x in row] for row in self.grid]
                for local_entry in [x for x in self.entries if x.clue]:
                    for i in range(local_entry.length):
                        row, col = local_entry.cells[i]
                        local_grid[row][col] = local_entry.clue.answer[i]
                print("\n" + "\n".join(["".join(row) for row in local_grid]))

            # Generate rest of puzzle and return None if successful
            failed_entry = self._generate(used_words, print_grid)
            if failed_entry is None:
                return None

            # Remove clue from entry and answer from used words
            entry.clue = None
            used_words.remove(clue.answer)

            # Continue backtracking if entry isn't constrained by failing entry
            if failed_entry not in entry.overlaps:
                return failed_entry

        # Return failed entry if no words result in a completed crossword
        return entry

    def export(self, out_file : str):
        output = {
            'title': self.title,
            'author': self.author,
            'date': self.date,
            'height': self.height,
            'width': self.width,
            'grid': self.grid,
            'entries': []
        }
        for entry in sorted(self.entries):
            output['entries'].append({
                'name': entry.name,
                'word': entry.clue.answer,
                'clue': entry.clue.clue,
                'cells': entry.cells
            })

        with open(out_file, 'w') as f:
            json.dump(output, f)

    def __str__(self):
        output = "\n".join(["".join(row) for row in self.grid])
        output += "\n\n"
        output += "\n".join([str(entry) for entry in sorted(self.entries)])

        return output


class Entry:

    def __init__(self, name, start_cell, length, clues):
        self.name = name
        self.start_cell = start_cell
        self.length = length
        self.orientation = name[0]
        self.enum = int(name[1:])
        self.clue : Clue = None
        self.overlaps : dict[Entry, tuple[int, int]] = dict()  # {Entry: (id of self, id of other)}
        self.constraints : list[tuple[int, str]] = []
        self.possible_clues : list[Clue] = [clue for clue in clues if len(clue.answer) == length]
        self.constrained_clues : list[Clue] = []

        self.cells = []
        for i in range(length):
            if self.orientation == 'A':
                self.cells.append((start_cell[0], start_cell[1] + i))
            else:
                self.cells.append((start_cell[0] + i, start_cell[1]))

    def update_overlap(self, other):
        if self.orientation == other.orientation:
            return
        for i in range(len(self.cells)):
            for j in range(len(other.cells)):
                if self.cells[i] == other.cells[j]:
                    self.overlaps[other] = (i, j)

    def update_constraints(self, used_words: set[str]) -> None:
        self.constraints = []
        for other, indices in self.overlaps.items():
            if other.clue:
                self.constraints.append((indices[0], other.clue.answer[indices[1]]))
        self.constrained_clues = [
            clue for clue in self.possible_clues
            if len(clue.answer) == self.length
            and clue.answer not in used_words
            and self.fits_constraints(clue.answer)
        ]

    def fits_constraints(self, word : str) -> bool:
        for index, letter in self.constraints:
            if word[index] != letter:
                return False
        return True

    def sorted_clues(self) -> list[Clue]:
        # TODO: Rank clues best to worst based on maximum constraint to intersecting entries
        return self.constrained_clues

    def clues_remaining(self) -> int:
        return len(self.constrained_clues)

    def open_intersections(self) -> int:
        return self.length - len(self.constraints)

    def __gt__(self, obj):
        return self.orientation > obj.orientation or \
            (self.orientation == obj.orientation and self.enum > obj.enum)

    def __str__(self):
        return self.name.ljust(4) \
            + str(self.start_cell).ljust(12) \
            + self.clue.answer.ljust(16) \
            + self.clue.clue

@dataclass
class Clue:
    answer: str
    clue: str
    priority: int = 1
