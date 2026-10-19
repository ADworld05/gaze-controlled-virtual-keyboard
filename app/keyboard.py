LETTERS = [list('qwertyuiop'), list('asdfghjkl'), list('zxcvbnm')]
SYMBOLS = [list('1234567890'), list('!@#$%&*()'), list('.,?:;\'"')]
TYPING = ['Case', '123 / ABC', 'Space', 'Backspace', 'New Line']
TOOLS = ['Clear', 'Copy', 'Pause', 'Calibrate']


class Keyboard:
    def __init__(self):
        self.symbols = False
        self.upper = False
        self.paused = False
        self.confirm_clear = False
        self.row, self.col = 1, 3

    @property
    def rows(self):
        if self.paused:
            return [['Resume', 'Calibrate']]
        if self.confirm_clear:
            return [['Cancel Clear', 'Confirm Clear']]
        return (SYMBOLS if self.symbols else LETTERS) + [TYPING, TOOLS]

    @property
    def target(self):
        return self.rows[self.row][self.col]

    def move(self, direction):
        before = (self.row, self.col)
        if direction in ('left', 'right'):
            self.col = max(0, min(len(self.rows[self.row]) - 1, self.col + (-1 if direction == 'left' else 1)))
        elif direction in ('up', 'down'):
            center = (self.col + .5) / len(self.rows[self.row])
            self.row = max(0, min(len(self.rows) - 1, self.row + (-1 if direction == 'up' else 1)))
            self.col = min(range(len(self.rows[self.row])), key=lambda c: abs((c + .5) / len(self.rows[self.row]) - center))
        return before != (self.row, self.col)

    def home(self):
        self.row, self.col = 0, 0

    def label(self, key):
        return key.upper() if self.upper and len(key) == 1 and key.isalpha() else key
