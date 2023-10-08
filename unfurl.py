import asyncio
import aiohttp
import json
import re
import sys

from urllib.parse import quote as urlquote
from urllib.parse import quote_plus as urlquote_plus
from html import escape as htmlquote

from collections import OrderedDict

from typing import Optional
from time import time
from html import escape

from mautrix.types import TextMessageEventContent, MessageType, Format, RelatesTo, RelationType, EventType

from maubot import Plugin, MessageEvent
from maubot.handlers import command, event


YTURL_RE = re.compile(r'https?://(?:[^.]+[.])?youtube.com/.*?[^=]*=(?P<slug>[a-zA-Z0-9_-]{11})')


class UnfurlBot(Plugin):
    async def gather_ytmd(self, slug, session):
        res = await session.get('https://ytmd.strudelline.net/'+slug)
        jsonres = await res.json()
        return jsonres

    async def check_profanity(self, text, session):
        res = await session.post('https://profanity.strudelline.net/', data=text.encode('utf-8'))
        self.log.warning(f"presp: {res}")
        jsonres = await res.json()
        return jsonres
        

    @event.on(EventType.ROOM_MESSAGE)
    async def echo_handler(self, evt: MessageEvent) -> None:
        if evt.sender == self.client.mxid:
            return
        try:
            message = evt.content.body
        except:
            self.log.warning(f"No body found in message {evt.event_id}")

        slugs = YTURL_RE.findall(message)
        if len(slugs) > 0:
            slugs = list(OrderedDict.fromkeys(slugs))
        self.log.warning(f"SLUGS: {slugs}")
        for slug in slugs:
            text_profanity = {'lines': [], 'average': 0, 'overall': 0, 'max': 0, 'max5': []}
            title_profanity = {'lines': [], 'average': 0, 'overall': 0, 'max': 0}
            desc_profanity = {'lines': [], 'average': 0, 'overall': 0, 'max': 0}
            metadata = {
                "description": "<no description>",
                "text": "",
            }
            async with aiohttp.ClientSession() as session:
                ytmd = await self.gather_ytmd(slug, session)
                self.log.warning(f"YTMD: {ytmd}")
                if ytmd['text'] != '':
                    text_profanity = await self.check_profanity(ytmd['text'], session)
                    metadata['text'] = ytmd['text']
                if ytmd['title'] != '':
                    title_profanity = await self.check_profanity(ytmd['title'], session)
                    metadata['title'] = ytmd['title']
                if ytmd['description'] != '':
                    desc_profanity = await self.check_profanity(ytmd['description'], session)
                    metadata['description'] = ytmd['description']

            title = metadata.get('title', 'no title')
            description = metadata.get('description', 'no description')
            text = metadata.get('text', 'no transcript')

            profanity = (
                 "Profanity Check:\n"
                f"    Title: {title_profanity['overall']} overall, {title_profanity['max']} per line max, {title_profanity['average']} per line average\n"
                f"    Description: {desc_profanity['overall']} overall, {desc_profanity['max']} per line max, {desc_profanity['average']} per line average\n"
                f"    Transcript: {text_profanity['overall']} overall, {text_profanity['max']} per line max, {text_profanity['average']} per line average\n"
            )

            # start building the responses (plain and html)
            text_response = f"https://www.youtube.com/watch?v={slug} -- {title}\n{'-'*20}\n"
            html_response = f"<b><a href='https://www.youtube.com/watch?v={urlquote(slug)}'>{htmlquote(title)}</a></b><hr />"

            html_response += htmlquote(description).replace('\n', '<br />')
            text_response += description + '\n\n'

            html_response += f"<hr /><pre>{htmlquote(profanity)}</pre><br />"
            html_response += '<br />'.join([f"<span data-mx-spoiler>{htmlquote(l)}</span>" for l in text_profanity.get('max5', [])])
            text_response += profanity



            content = TextMessageEventContent(
                msgtype=MessageType.NOTICE, format=Format.HTML,
                formatted_body=html_response,
                body=text_response
            )
            await evt.respond(content, in_thread=True)
