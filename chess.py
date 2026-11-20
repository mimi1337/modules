# meta developer: @hardst1ly
# requires: python-chess
"""Chess for Hikka: play with a friend in the same chat."""

import html
import re

import chess
from .. import loader, utils


@loader.tds
class HChessMod(loader.Module):
    """Шахматы с другом. Для старта ответь .chess на его сообщение."""

    strings = {"name": "HChess"}

    def __init__(self):
        self.games = {}

    async def _board(self, game):
        board = game["board"]
        piece = {
            "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
            "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
        }
        lines = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                obj = board.piece_at(chess.square(file, rank))
                row.append(piece.get(obj.symbol(), "·") if obj else "·")
            lines.append("{} {}".format(rank + 1, " ".join(row)))
        lines.append("  a b c d e f g h")
        turn = "Белые ⚪" if board.turn else "Чёрные ⚫"
        if board.is_checkmate():
            state = "🏆 Мат! Победили {}.".format("чёрные" if board.turn else "белые")
        elif board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition() or board.is_seventyfive_moves():
            state = "🤝 Ничья."
        elif board.is_check():
            state = "⚠️ Шах. Ход: {}.".format(turn)
        else:
            state = "Ход: {}.".format(turn)
        return (
            "♟ <b>Шахматы</b>\n"
            "<pre>{}</pre>\n"
            "{}\n"
            "Белые: <code>{}</code> | Чёрные: <code>{}</code>\n"
            "Ход: <code>.cmove e2e4</code> (или <code>.cmove e7e8q</code>)"
        ).format(
            html.escape("\n".join(lines)), state,
            game["white"], game["black"]
        )

    async def chesscmd(self, message):
        """Ответ на сообщение — новая партия; status — доска; stop — отмена."""
        chat = message.chat_id
        args = utils.get_args_raw(message).strip().lower()
        game = self.games.get(chat)
        if args in ("status", "board", "доска"):
            await utils.answer(message, await self._board(game) if game else "❌ Нет активной партии.")
            return
        if args in ("stop", "end", "cancel"):
            if game:
                del self.games[chat]
                await utils.answer(message, "🛑 Шахматная партия завершена.")
            else:
                await utils.answer(message, "❌ Нет активной партии.")
            return
        if args in ("help", "?"):
            await utils.answer(message, "♟ Ответь <code>.chess</code> на сообщение друга. Ходы: <code>.cmove e2e4</code>; доска: <code>.chess status</code>; стоп: <code>.chess stop</code>.")
            return
        if game:
            await utils.answer(message, "⚠️ Партия уже идёт. <code>.chess status</code> или <code>.chess stop</code>.")
            return
        reply = await message.get_reply_message()
        opponent = getattr(reply, "sender_id", None) if reply else None
        me = (await self._client.get_me()).id
        if not opponent or opponent == me:
            await utils.answer(message, "❌ Ответь командой <code>.chess</code> на сообщение друга.")
            return
        self.games[chat] = {"board": chess.Board(), "white": me, "black": opponent, "selected": None}
        game = self.games[chat]
        form = await self.inline.form(
            text=await self._board(game),
            message=message,
            reply_markup=self._buttons(chat),
            force_me=False,
            always_allow=[opponent],
            ttl=False,
        )
        if not form:
            del self.games[chat]
            await utils.answer(message, "❌ Inline-кнопки недоступны. Проверь inline-бот Hikka.")

    async def _move(self, message, arg):
        game = self.games.get(message.chat_id)
        if not game:
            await utils.answer(message, "❌ Нет партии. Начни: <code>.chess</code> ответом на друга.")
            return
        player = getattr(message, "sender_id", None)
        if player not in (game["white"], game["black"]):
            return
        board = game["board"]
        if player != (game["white"] if board.turn else game["black"]):
            await utils.answer(message, "⌛ Сейчас не твой ход.")
            return
        move_str = arg.strip().lower()
        if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", move_str):
            await utils.answer(message, "❌ Пример хода: <code>.cmove e2e4</code>")
            return
        try:
            move = chess.Move.from_uci(move_str)
            if move not in board.legal_moves:
                await utils.answer(message, "❌ Недопустимый ход.")
                return
            board.push(move)
        except ValueError:
            await utils.answer(message, "❌ Недопустимый ход.")
            return
        result = await self._board(game)
        if board.is_game_over(claim_draw=True):
            del self.games[message.chat_id]
        await utils.answer(message, result)

    async def cmovecmd(self, message):
        """e2e4 — ход в шахматах."""
        await self._move(message, utils.get_args_raw(message))

    async def watcher(self, message):
        """Позволяет другу играть через .cmove без установки Hikka."""
        if getattr(message, "out", False):
            return
        try:
            if message.chat_id not in self.games:
                return
            text = getattr(message, "raw_text", "") or ""
            match = re.fullmatch(r"\.cmove\s+([a-h][1-8][a-h][1-8][qrbn]?)\s*", text, re.I)
            if match:
                await self._move(message, match.group(1))
        except Exception:
            return

    def _buttons(self, chat):
        game = self.games.get(chat)
        if not game:
            return [[{"text": "🏁 Игра окончена", "callback": self._click, "args": (chat, -1)}]]
        board = game["board"]
        selected = game.get("selected")
        legal_to = {m.to_square for m in board.legal_moves if selected is not None and m.from_square == selected}
        pieces = {
            "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
            "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
        }
        rows = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                square = chess.square(file, rank)
                piece = board.piece_at(square)
                symbol = pieces[piece.symbol()] if piece else ("▫" if (file + rank) % 2 else "▪")
                if square == selected:
                    symbol = "🔹"
                elif square in legal_to:
                    symbol = "🟢" if piece is None else "🔴"
                row.append({"text": symbol, "callback": self._click, "args": (chat, square)})
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
        board = game["board"]
        if board.is_game_over(claim_draw=True):
            await call.answer("Партия завершена.")
            return
        current = game["white"] if board.turn == chess.WHITE else game["black"]
        if player != current:
            await call.answer("Сейчас ход соперника.")
            return
        if square < 0:
            await call.answer("Партия завершена.")
            return
        picked = board.piece_at(square)
        if picked and picked.color == board.turn:
            game["selected"] = square if game.get("selected") != square else None
        elif game.get("selected") is not None:
            start = game["selected"]
            moves = [m for m in board.legal_moves if m.from_square == start and m.to_square == square]
            if not moves:
                await call.answer("Недопустимый ход.")
                return
            move = next((m for m in moves if m.promotion == chess.QUEEN), moves[0])
            board.push(move)
            game["selected"] = None
        else:
            await call.answer("Сначала выбери свою фигуру.")
            return
        finished = board.is_game_over(claim_draw=True)
        await call.edit(
            text=await self._board(game),
            reply_markup=self._buttons(chat) if not finished else [[{"text": "🏁 Партия завершена", "callback": self._click, "args": (chat, -1)}]],
            force_me=False,
            always_allow=[game["black"]],
        )
        if finished:
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
