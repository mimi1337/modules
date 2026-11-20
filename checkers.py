# meta developer: @hardst1ly
"""Russian checkers (8x8) for Hikka: play with a friend."""

import html
import re

from .. import loader, utils

DIRS = ((-1, -1), (-1, 1), (1, -1), (1, 1))


@loader.tds
class HCheckersMod(loader.Module):
    """Русские шашки с другом: обязательное взятие, дамки, серии."""

    strings = {"name": "HCheckers"}

    def __init__(self):
        self.games = {}

    @staticmethod
    def _inside(r, c):
        return 0 <= r < 8 and 0 <= c < 8

    @staticmethod
    def _sq(s):
        return 8 - int(s[1]), ord(s[0].lower()) - 97

    @staticmethod
    def _label(r, c):
        return chr(c + 97) + str(8 - r)

    @staticmethod
    def _owner(piece):
        return "w" if piece.lower() == "w" else "b"

    @staticmethod
    def _enemy(a, b):
        return bool(a and b) and a.lower() != b.lower()

    def _captures(self, board, r, c):
        p = board.get((r, c))
        if not p:
            return []
        moves = []
        for dr, dc in DIRS:
            if p.isupper():
                rr, cc = r + dr, c + dc
                while self._inside(rr, cc) and not board.get((rr, cc)):
                    rr += dr
                    cc += dc
                if self._inside(rr, cc) and self._enemy(p, board.get((rr, cc))):
                    victim = (rr, cc)
                    rr += dr
                    cc += dc
                    while self._inside(rr, cc) and not board.get((rr, cc)):
                        moves.append(((rr, cc), victim))
                        rr += dr
                        cc += dc
            else:
                mr, mc = r + dr, c + dc
                tr, tc = r + 2 * dr, c + 2 * dc
                if (self._inside(tr, tc) and
                    self._enemy(p, board.get((mr, mc))) and
                    not board.get((tr, tc))):
                    moves.append(((tr, tc), (mr, mc)))
        return moves

    def _steps(self, board, r, c):
        p = board.get((r, c))
        if not p:
            return []
        moves = []
        for dr, dc in DIRS:
            if p.isupper():
                rr, cc = r + dr, c + dc
                while self._inside(rr, cc) and not board.get((rr, cc)):
                    moves.append((rr, cc))
                    rr += dr
                    cc += dc
            elif dr == (-1 if p == "w" else 1):
                tr, tc = r + dr, c + dc
                if self._inside(tr, tc) and not board.get((tr, tc)):
                    moves.append((tr, tc))
        return moves

    def _any_captures(self, board, color):
        return any(
            self._captures(board, r, c)
            for (r, c), piece in board.items() if self._owner(piece) == color
        )

    def _any_moves(self, board, color):
        return any(
            self._captures(board, r, c) or self._steps(board, r, c)
            for (r, c), piece in board.items() if self._owner(piece) == color
        )

    def _board(self, g):
        icons = {"w": "⛀", "W": "⛁", "b": "⛂", "B": "⛃"}
        rows = []
        for r in range(8):
            row = []
            for c in range(8):
                p = g["board"].get((r, c))
                row.append(icons.get(p, "·" if (r + c) % 2 else " "))
            rows.append("{} {}".format(8 - r, " ".join(row)))
        rows.append("  a b c d e f g h")
        turn = "белых ⚪" if g["turn"] == "w" else "чёрных ⚫"
        extra = "⚠️ Продолжай взятие той же шашкой!" if g["chain"] else "Ход {}.".format(turn)
        return (
            "🎯 <b>Русские шашки</b>\n<pre>{}</pre>\n"
            "{}\nБелые: <code>{}</code> | Чёрные: <code>{}</code>\n"
            "Ход: <code>.dmove a3 b4</code>"
        ).format(html.escape("\n".join(rows)), extra, g["white"], g["black"])

    async def checkerscmd(self, message):
        """Ответ на друга — старт; status — доска; stop — отмена."""
        chat = message.chat_id
        args = utils.get_args_raw(message).strip().lower()
        g = self.games.get(chat)
        if args in ("status", "board", "доска"):
            await utils.answer(message, self._board(g) if g else "❌ Нет партии.")
            return
        if args in ("stop", "end", "cancel"):
            if g:
                del self.games[chat]
                await utils.answer(message, "🛑 Партия в шашки завершена.")
            else:
                await utils.answer(message, "❌ Нет партии.")
            return
        if args in ("help", "?"):
            await utils.answer(message, "🎯 Ответь <code>.checkers</code> на сообщение друга. Ходы: <code>.dmove a3 b4</code>, доска: <code>.checkers status</code>, стоп: <code>.checkers stop</code>.")
            return
        if g:
            await utils.answer(message, "⚠️ Партия уже идёт. <code>.checkers status</code>.")
            return
        reply = await message.get_reply_message()
        opponent = getattr(reply, "sender_id", None) if reply else None
        me = (await self.client.get_me()).id
        if not opponent or opponent == me:
            await utils.answer(message, "❌ Ответь <code>.checkers</code> на сообщение друга.")
            return
        board = {}
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    if r < 3:
                        board[r, c] = "b"
                    elif r > 4:
                        board[r, c] = "w"
        self.games[chat] = {"board": board, "white": me, "black": opponent, "turn": "w", "chain": None}
        await utils.answer(message, "✅ Игра началась!\n" + self._board(self.games[chat]))

    async def _move(self, message, arg):
        g = self.games.get(message.chat_id)
        if not g:
            await utils.answer(message, "❌ Нет партии. Начни <code>.checkers</code> ответом на друга.")
            return
        player = getattr(message, "sender_id", None)
        if player not in (g["white"], g["black"]):
            return
        if player != (g["white"] if g["turn"] == "w" else g["black"]):
            await utils.answer(message, "⌛ Сейчас не твой ход.")
            return
        match = re.fullmatch(r"([a-h][1-8])\\s*[- ]\\s*([a-h][1-8])", arg.strip().lower())
        if not match:
            await utils.answer(message, "❌ Пример: <code>.dmove a3 b4</code>")
            return
        start, end = self._sq(match.group(1)), self._sq(match.group(2))
        b = g["board"]
        p = b.get(start)
        if not p or self._owner(p) != g["turn"]:
            await utils.answer(message, "❌ Тут нет твоей шашки.")
            return
        if g["chain"] and start != g["chain"]:
            await utils.answer(message, "❌ Нужно продолжить взятие шашкой <code>{}</code>".format(self._label(*g["chain"])))
            return

        captures = self._captures(b, *start)
        forced = self._any_captures(b, g["turn"])
        selected = next(((dest, victim) for dest, victim in captures if dest == end), None)
        if not selected and (forced or end not in self._steps(b, *start)):
            await utils.answer(message, "❌ Недопустимый ход. Взятие обязательно, если возможно.")
            return
        b.pop(start)
        if selected:
            b.pop(selected[1])
        if p == "w" and end[0] == 0:
            p = "W"
        elif p == "b" and end[0] == 7:
            p = "B"
        b[end] = p
        if selected and self._captures(b, *end):
            g["chain"] = end
        else:
            g["chain"] = None
            g["turn"] = "b" if g["turn"] == "w" else "w"

        if not g["chain"] and not self._any_moves(b, g["turn"]):
            winner = "белые ⚪" if g["turn"] == "b" else "чёрные ⚫"
            out = self._board(g) + "\n🏆 Победили {}!".format(winner)
            del self.games[message.chat_id]
        else:
            out = self._board(g)
        await utils.answer(message, out)

    async def dmovecmd(self, message):
        """a3 b4 — ход в шашках."""
        await self._move(message, utils.get_args_raw(message))

    async def watcher(self, message):
        """Ходы соперника без установки Hikka."""
        if getattr(message, "out", False):
            return
        try:
            if message.chat_id not in self.games:
                return
            raw = getattr(message, "raw_text", "") or ""
            match = re.fullmatch(r"\\.dmove\\s+(.+)", raw.strip(), re.I)
            if match:
                await self._move(message, match.group(1))
        except Exception:
            return
