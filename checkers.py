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
        me = (await self._client.get_me()).id
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
        self.games[chat] = {"board": board, "white": me, "black": opponent, "turn": "w", "chain": None, "selected": None}
        game = self.games[chat]
        form = await self.inline.form(
            text=self._board(game),
            message=message,
            reply_markup=self._buttons(chat),
            force_me=False,
            always_allow=[opponent],
            ttl=False,
        )
        if not form:
            self.games.pop(chat, None)
            await utils.answer(message, "❌ Inline-кнопки недоступны. Проверь inline-бот Hikka.")

    def _apply_move(self, g, player, start, end):
        if player not in (g["white"], g["black"]):
            return "Ты не участвуешь."
        if player != (g["white"] if g["turn"] == "w" else g["black"]):
            return "Сейчас не твой ход."
        board = g["board"]
        piece = board.get(start)
        if not piece or self._owner(piece) != g["turn"]:
            return "Выбери свою шашку."
        if g["chain"] is not None and start != g["chain"]:
            return "Продолжи взятие этой же шашкой."
        captures = self._captures(board, *start)
        capture = next(((dst, victim) for dst, victim in captures if dst == end), None)
        if not capture:
            if self._any_captures(board, g["turn"]):
                return "Взятие обязательно."
            if end not in self._steps(board, *start):
                return "Недопустимый ход."
        board.pop(start)
        if capture:
            board.pop(capture[1])
        if piece == "w" and end[0] == 0:
            piece = "W"
        elif piece == "b" and end[0] == 7:
            piece = "B"
        board[end] = piece
        if capture and self._captures(board, *end):
            g["chain"] = end
            g["selected"] = end
        else:
            g["chain"] = None
            g["selected"] = None
            g["turn"] = "b" if g["turn"] == "w" else "w"
        return None

    def _finished(self, g):
        return g["chain"] is None and not self._any_moves(g["board"], g["turn"])

    async def _move(self, message, arg):
        game = self.games.get(message.chat_id)
        if not game:
            await utils.answer(message, "❌ Нет партии, начни <code>.checkers</code> ответом на друга.")
            return
        match = re.fullmatch(r"([a-h][1-8])\s*[- ]\s*([a-h][1-8])", arg.strip().lower())
        if not match:
            await utils.answer(message, "❌ Ход: <code>.dmove a3 b4</code>")
            return
        start, end = self._sq(match.group(1)), self._sq(match.group(2))
        err = self._apply_move(game, getattr(message, "sender_id", None), start, end)
        if err:
            await utils.answer(message, "❌ " + err)
            return
        finished = self._finished(game)
        out = self._board(game)
        if finished:
            out += "\n🏆 Победили {}!".format("белые ⚪" if game["turn"] == "b" else "чёрные ⚫")
            self.games.pop(message.chat_id, None)
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
            match = re.fullmatch(r"\.dmove\s+(.+)", raw.strip(), re.I)
            if match:
                await self._move(message, match.group(1))
        except Exception:
            return

    def _available(self, game, pos):
        board = game["board"]
        piece = board.get(pos)
        if not piece or self._owner(piece) != game["turn"]:
            return []
        if game["chain"] is not None and pos != game["chain"]:
            return []
        captures = self._captures(board, *pos)
        if captures:
            return [dst for dst, victim in captures]
        if self._any_captures(board, game["turn"]):
            return []
        return self._steps(board, *pos)

    def _buttons(self, chat):
        game = self.games.get(chat)
        if not game:
            return [[{"text": "🏁 Завершено", "callback": self._click, "args": (chat, -1)}]]
        selected = game.get("selected")
        options = set(self._available(game, selected)) if selected is not None else set()
        piece_icons = {"w": "⚪", "W": "♔", "b": "⚫", "B": "♚"}
        rows = []
        for r in range(8):
            row = []
            for c in range(8):
                pos = (r, c)
                piece = game["board"].get(pos)
                label = piece_icons.get(piece, "▫" if (r + c) % 2 else "▪")
                if pos == selected:
                    label = "🔹"
                elif pos in options:
                    label = "🟢"
                row.append({"text": label, "callback": self._click, "args": (chat, r * 8 + c)})
            rows.append(row)
        rows.append([{"text": "🏳️ Сдаться", "callback": self._resign, "args": (chat,)}])
        return rows

    async def _click(self, call, chat, square):
        game = self.games.get(chat)
        if not game:
            await call.answer("Партия завершена.", show_alert=True)
            return
        player = call.from_user.id
        if player not in (game["white"], game["black"]):
            await call.answer("Ты не участвуешь в этой партии.", show_alert=True)
            return
        if player != (game["white"] if game["turn"] == "w" else game["black"]):
            await call.answer("Сейчас ход соперника.")
            return
        if square < 0:
            await call.answer("Партия завершена.")
            return
        pos = (square // 8, square % 8)
        piece = game["board"].get(pos)
        if piece and self._owner(piece) == game["turn"]:
            if game["chain"] is not None and pos != game["chain"]:
                await call.answer("Продолжи взятие той же шашкой.")
                return
            if not self._available(game, pos):
                await call.answer("Выбери шашку с допустимым ходом.")
                return
            game["selected"] = pos if game.get("selected") != pos or game["chain"] is not None else None
        elif game.get("selected") is not None:
            err = self._apply_move(game, player, game["selected"], pos)
            if err:
                await call.answer(err)
                return
        else:
            await call.answer("Сначала выбери свою шашку.")
            return
        done = self._finished(game)
        output = self._board(game)
        if done:
            output += "\n🏆 Победили {}!".format("белые ⚪" if game["turn"] == "b" else "чёрные ⚫")
        await call.edit(
            text=output,
            reply_markup=self._buttons(chat) if not done else [[{"text": "🏁 Партия завершена", "callback": self._click, "args": (chat, -1)}]],
            force_me=False, always_allow=[game["black"]],
        )
        if done:
            self.games.pop(chat, None)

    async def _resign(self, call, chat):
        game = self.games.get(chat)
        if not game:
            await call.answer("Партия завершена.")
            return
        if call.from_user.id not in (game["white"], game["black"]):
            await call.answer("Ты не участник.", show_alert=True)
            return
        winner = "чёрные ⚫" if call.from_user.id == game["white"] else "белые ⚪"
        self.games.pop(chat, None)
        await call.edit("🏳️ Сдача. Победили " + winner, reply_markup=[])
