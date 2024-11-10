# -*- coding: utf-8 -*-

# Copyright 2024 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extractors for https://www.bilibili.com/"""

from .common import Extractor, Message
from .. import text, util, exception


class BilibiliExtractor(Extractor):
    """Base class for bilibili extractors"""
    category = "bilibili"
    root = "https://www.bilibili.com"

    def __init__(self, match):
        Extractor.__init__(self, match)
        self.item = match.group(match.lastindex)

    def _init(self):
        self.api = BilibiliAPI(self)


class BilibiliUserArticlesExtractor(BilibiliExtractor):
    """Extractor for all articles of an user"""
    subcategory = "user"
    pattern = r"(?:https?://)?space\.bilibili\.com/(\d+)/article"
    example = "https://space.bilibili.com/12345/article"

    def items(self):
        for article in self.api.user_articles(self.item):
            article["_extractor"] = BilibiliArticleExtractor
            url = "{}/opus/{}".format(self.root, article["opus_id"])
            yield Message.Queue, url, article


class BilibiliArticleExtractor(BilibiliExtractor):
    """Extractor for images from an article"""
    subcategory = "article"
    pattern = (r"(?:https?://)?"
               r"(?:t\.bilibili\.com|(?:www\.)?bilibili.com/opus)/(\d+)")
    example = "https://www.bilibili.com/opus/12345"
    directory_fmt = ("{category}", "{username}")
    filename_fmt = "{id}_{num}.{extension}"
    archive_fmt = "{id}_{num}"

    def items(self):
        article = self.api.article(self.item)

        # Flatten modules list
        modules = {}
        for module in article["detail"]["modules"]:
            del module['module_type']
            modules.update(module)
        article["detail"]["modules"] = modules

        article["username"] = modules["module_author"]["name"]

        urls = []
        for paragraph in modules['module_content']['paragraphs']:
            pics = paragraph.get('pic', {}).get('pics', [])
            for pic in pics:
                urls.append(pic['url'])

        yield Message.Directory, article
        for article["num"], url in enumerate(urls, 1):
            yield Message.Url, url, text.nameext_from_url(url, article)


class BilibiliAPI():
    def __init__(self, extractor: BilibiliExtractor):
        self.extractor = extractor

    def _call(self, endpoint, params):
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1" + endpoint
        response = self.extractor.request(url, params=params).json()

        if response["code"] != 0:
            raise exception.StopExtraction("API request failed")

        return response

    def user_articles(self, user_id):
        endpoint = "/opus/feed/space"
        params = {"host_mid": user_id}

        while True:
            data = self._call(endpoint, params)

            for item in data["data"]["items"]:
                params["offset"] = item["opus_id"]
                yield item

            if not data["data"]["has_more"]:
                break

    def article(self, article_id):
        url = "https://www.bilibili.com/opus/{}".format(article_id)
        response = self.extractor.request(url)
        return util.json_loads(text.extr(
            response.text, "window.__INITIAL_STATE__=", ";"))
