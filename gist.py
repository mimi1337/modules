# meta developer: @mimi1337
# requires: aiohttp
"""GitHub Gist uploader for Hikka."""

import html
import os
import re

import aiohttp

from .. import loader, utils


@loader.tds
class GitGistMod(loader.Module):
    """Создание GitHub Gist из текста или текстовых файлов."""

    strings = {"name": "GitGist"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("github_token", "", "GitHub Personal Access Token с правом Gists"),
            loader.ConfigValue("public", True, "Делать Gist публичным"),
            loader.ConfigValue("max_kb", 1024, "Максимальный размер исходника (КБ)"),
        )

    async def _api(self, method, endpoint, payload=None):
        headers = {
            "Authorization": "Bearer " + str(self.config["github_token"]).strip(),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, "https://api.github.com" + endpoint,
                headers=headers, json=payload
            ) as response:
                if response.status == 204:
                    return {}
                data = await response.json(content_type=None)
                if response.status >= 400:
                    detail = data.get("message", "Unknown error") if isinstance(data, dict) else str(data)[:200]
                    raise RuntimeError("GitHub HTTP {}: {}".format(response.status, detail))
                return data

    @loader.command()
    async def gistcmd(self, message):
        """<текст> | ответ на файл | del <gist_id> — публикация GitHub Gist."""
        if not str(self.config["github_token"]).strip():
            await utils.answer(message, "❌ Укажи GitHub-токен в <code>.config GitGist</code> (github_token)")
            return

        args = utils.get_args_raw(message).strip()
        parts = args.split(maxsplit=1)

        if parts and parts[0].lower() in ("del", "delete"):
            gist_id = parts[1].strip() if len(parts) == 2 else ""
            if not re.fullmatch(r"[0-9a-fA-F]{8,64}", gist_id):
                await utils.answer(message, "❌ Используй: <code>.gist del GIST_ID</code>")
                return
            status = await utils.answer(message, "⏳ Удаляю Gist...")
            try:
                await self._api("DELETE", "/gists/" + gist_id)
                await utils.answer(status, "✅ Удалён Gist <code>{}</code>".format(gist_id))
            except Exception as exc:
                await utils.answer(status, "❌ {}".format(html.escape(str(exc))))
            return

        content = args
        filename = "snippet.txt"
        reply = await message.get_reply_message()
        limit = max(1, int(self.config["max_kb"])) * 1024

        if not content and reply:
            attached = getattr(reply, "file", None)
            if attached and getattr(reply, "media", None):
                size = getattr(attached, "size", 0) or 0
                if size > limit:
                    await utils.answer(message, "❌ Файл превышает лимит {} КБ".format(self.config["max_kb"]))
                    return
                filename = os.path.basename(str(getattr(attached, "name", None) or "snippet.txt").replace("\\", "/"))[:120] or "snippet.txt"
                try:
                    raw = await reply.download_media(file=bytes)
                except Exception as exc:
                    await utils.answer(message, "❌ Не удалось получить файл: {}".format(html.escape(str(exc))))
                    return
                if not raw or len(raw) > limit or b"\x00" in raw:
                    await utils.answer(message, "❌ Файл пустой, слишком большой или бинарный")
                    return
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    await utils.answer(message, "❌ Нужен текстовый файл в UTF-8")
                    return
            else:
                content = getattr(reply, "raw_text", "") or ""

        if not content:
            await utils.answer(message,
                "📌 <b>GitGist</b>\n"
                "• <code>.gist текст</code> — Gist из текста\n"
                "• Ответь <code>.gist</code> на файл .lua/.luau/.txt\n"
                "• <code>.gist del GIST_ID</code> — удалить")
            return

        data_bytes = content.encode("utf-8")
        if len(data_bytes) > limit:
            await utils.answer(message, "❌ Лимит: {} КБ".format(self.config["max_kb"]))
            return

        status = await utils.answer(message, "⏳ Создаю GitHub Gist...")
        public = str(self.config["public"]).lower() in ("true", "yes", "1")
        try:
            gist = await self._api("POST", "/gists", {
                "description": "Uploaded via GitGist (Hikka)",
                "public": public,
                "files": {filename: {"content": content}},
            })
            file_info = (gist.get("files") or {}).get(filename, {})
            gist_id = str(gist.get("id", ""))
            gist_url = str(gist.get("html_url", ""))
            raw_url = str(file_info.get("raw_url", ""))
            response = (
                "✅ <b>GitHub Gist создан</b>\n\n"
                "📄 <b>Файл:</b> <code>{}</code>\n"
                "📊 <b>Строк:</b> {} | <b>Размер:</b> {} Б\n"
                "🔓 <b>Доступ:</b> {}\n"
                "🔗 <b>Gist:</b> <a href=\"{}\">Открыть</a>\n"
                "📋 <b>Raw:</b> <code>{}</code>\n"
                "🗑 <b>Удалить:</b> <code>.gist del {}</code>"
            ).format(
                html.escape(filename), content.count("\n") + 1, len(data_bytes),
                "PUBLIC" if public else "SECRET",
                html.escape(gist_url, quote=True),
                html.escape(raw_url), html.escape(gist_id),
            )
            await utils.answer(status, response)
        except Exception as exc:
            await utils.answer(status, "❌ {}".format(html.escape(str(exc))))
