import tkinter
from src.url import URL, lex

WIDTH, HEIGHT = 800, 600


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()

    def load(self, url: URL):
        HSTEP, VSTEP = 13, 18
        cursor_x, cursor_y = HSTEP, VSTEP

        body = url.request()
        text = lex(body)

        for c in text:
            self.canvas.create_text(cursor_x, cursor_y, text=c)
            cursor_x += HSTEP

            if cursor_x >= WIDTH - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP


if __name__ == "__main__":
    import sys

    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
