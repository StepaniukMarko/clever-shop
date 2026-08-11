"""
Photo Provider Module for Clever Shop.
Modular architecture for image search.

Currently supports:
- Manual mode (Google Images link + paste URL)

Future providers (plug-in without rewriting):
- Google Custom Search API
- Bing Image Search API
- SerpAPI
"""

import os
from typing import List, Dict, Optional


class PhotoProvider:
    """Base class for photo search providers."""

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search for images.
        Returns list of {'url': '...', 'thumbnail': '...', 'source': '...'}
        """
        raise NotImplementedError


class ManualPhotoProvider(PhotoProvider):
    """
    Manual mode: generates Google Images search URL.
    Admin opens link, finds photo, pastes URL back.
    """

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        search_url = f'https://www.google.com/search?q={query.replace(" ", "+")}&tbm=isch'
        return [{
            'url': '',
            'thumbnail': '',
            'source': 'google_images',
            'search_url': search_url,
            'manual': True,
        }]


class GoogleCSEPhotoProvider(PhotoProvider):
    """
    Google Custom Search Engine provider.
    Requires: GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX env vars.

    Setup:
    1. Create project at https://console.cloud.google.com
    2. Enable Custom Search API
    3. Create search engine at https://cse.google.com
    4. Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX in Railway env vars
    """

    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_CSE_API_KEY', '')
        self.cx = os.environ.get('GOOGLE_CSE_CX', '')

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.cx)

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        if not self.is_configured:
            return ManualPhotoProvider().search(query, num_results)

        import requests
        try:
            resp = requests.get('https://www.googleapis.com/customsearch/v1', params={
                'key': self.api_key,
                'cx': self.cx,
                'q': query,
                'searchType': 'image',
                'num': min(num_results, 10),
                'imgSize': 'large',
            }, timeout=10)

            if resp.status_code != 200:
                return ManualPhotoProvider().search(query, num_results)

            data = resp.json()
            results = []
            for item in data.get('items', [])[:num_results]:
                results.append({
                    'url': item.get('link', ''),
                    'thumbnail': item.get('image', {}).get('thumbnailLink', ''),
                    'source': 'google_cse',
                    'title': item.get('title', ''),
                    'manual': False,
                })
            return results if results else ManualPhotoProvider().search(query, num_results)

        except Exception:
            return ManualPhotoProvider().search(query, num_results)


def get_photo_provider() -> PhotoProvider:
    """Get the best available photo provider."""
    google = GoogleCSEPhotoProvider()
    if google.is_configured:
        return google
    return ManualPhotoProvider()
