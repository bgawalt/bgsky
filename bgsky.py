"""Brian Gawalt (BG) posts to BlueSky (or maybe some other AT Proto outlet).

Dependencies needed:
  pip3 install requests

Much thanks to Ian Klatz's ATProtoTools:
    https://klatz.co
    https://github.com/ianklatzco/atprototools/

## Example usage

```
import bgsky

if __name__ == '__main__':
  creds = bgsky.Credentials(
    host='https://bsky.social', username='brian.gawalt.com', password='letmein'    
  )
  builder = bgsky.PostBuilder(creds)
  builder.add_text("What's your favorite scary movie?")
  builder.add_link('Take our poll!', 'https://gawalt.com/moviepoll.html')
  builder.add_text(' ')
  builder.add_tag('movies')
  builder.post()
```

## Building `Credentials`

The credentials class is most easily managed with its `from_jsonfile`
constructor.  Pass it a filename for a text file that describes a single JSON
object with the following string-valued keys:

*  `'username'` (required): your username on that server -- whatever string
    appears after "@" on your profile, use that.  I use "brian.gawalt.com".
*  `'password'` (required): a password for that username on that server;
      app-specific passwords work here and are encouraged.
*  `'host'` (optional): the server hosting your PDS.  I use https://bsky.social,
      and that's used as the default if you don't provide one explicitly.
      (I.e., it's the module constant `bgsky.DEFAULT_HOST`.)


This just parses the text file into a `dict[str, str]` and passes it to the
other constructor function, `from_dict`.  And that's just doing the very simple
direct construction that you see in `Example Usage` above.  But keeping the
creds in a textfile seems like the normal usecase, where you're doing secrets
management by just having a file with the secrets in it.
  
## TODO

*  This should support OAuth
*  Support images
*  How does `"host"` in the credentials relate to the user's PDS?
"""


import datetime
import json
import sys

import requests


# Where to send posts to, by default:
DEFAULT_HOST = 'https://bsky.social'


# TODO Support OAuth
class Credentials:

  def __init__(
      self, username: str,  password: str,  host: str = DEFAULT_HOST
  ):
    self._host = host
    token_request_params = {'identifier': username, 'password': password}
    resp = requests.post(
      f'{host}/xrpc/com.atproto.server.createSession',
      json=token_request_params
    )
    self._auth_token = resp.json().get('accessJwt')
    if self._auth_token is None:
      raise ValueError('Whoopsie doodle, bad response: ' + str(resp.json()))
    self._did = resp.json().get('did')

  @property
  def auth_token(self) -> str:
    return self._auth_token

  @property
  def did(self) -> str:
    return self._did

  @property
  def host(self) -> str:
     return self._host

  @staticmethod
  def from_jsonfile(json_filename: str) -> 'Credentials':
    config = {}
    with open(json_filename, 'rt') as infile:
      json_text = infile.read()
    config = json.loads(json_text)
    return Credentials(
        username=config['username'],
        password=config['password'],
        host=config['host'],
      )

  def from_dict(config: dict[str, str]) -> 'Credentials':
    for req_key in ['password', 'username']:
      if req_key not in config:
        raise ValueError(f"Creds config missing required key '{req_key}'")
    return Credentials(
      username=config['username'],
      password=config['password'],
      host=config.get('host', DEFAULT_HOST)
    )


# TODO support mentions
# TODO support images
class PostBuilder:

  def __init__(self, creds: Credentials, langs: tuple[str, ...] = ('en-US',)):
    self._creds = creds
    self._langs = langs
    self._text_segments = []
    self._text_byte_len = 0
    self._facets = []

  def reset(self, langs: tuple[str, ...] | None = None):
    if langs is not None:
      self._langs = langs
    self._text_segments = []
    self._text_byte_len = 0
    self._facets = []

  def add_text(self, text: str):
    self._text_segments.append(text)
    self._text_byte_len += len(text.encode('UTF-8'))

  def add_link(self, link_text: str, url: str):
    link_text_len = len(link_text.encode('UTF-8'))
    facet = {
      'index': {
        'byteStart': self._text_byte_len,
        'byteEnd': self._text_byte_len + link_text_len
      },
      'features': [
        {            
          '$type': 'app.bsky.richtext.facet#link',
          'uri': url,
        }
      ]
    }
    self._text_segments.append(link_text)
    self._text_byte_len += link_text_len
    self._facets.append(facet)

  def add_hashtag(self, tag: str, num_hashes: int = 1):
    """Add a hashtag as the next segment of the post.
    
    `tag` should not start with '#'.  This method appends the octothorpes
    automatically in the displayed text, and the tag being indexed always has
    one less octothorpe than the display.  (The official lexicon doc calls the
    `num_hashes = 2` case 'double hash tags'.)

    The default here does what you want: calling `add_hashtag('myhashtag')`
    displays '#myhashtag' with a link that takes you to everyone else who used
    that tag (where the string that is indexed is 'myhashtag'.)

    Raises:
      ValueError: when `tag` starts with an octothorpe.
    """
    if tag[0] == '#':
      raise ValueError("`tag` cannot start with '#'")
    tag_text = ('#' * num_hashes) + tag
    tag_text_len = len(tag_text.encode('UTF-8'))
    facet = {
      'index': {
        'byteStart': self._text_byte_len,
        'byteEnd': self._text_byte_len + tag_text_len
      },
      'features': [
        {            
          '$type': 'app.bsky.richtext.facet#tag',
          'tag': ('#' * (num_hashes - 1)) + tag,
        }
      ]
    }
    self._text_segments.append(tag_text)
    self._text_byte_len += tag_text_len
    self._facets.append(facet)

  def post(self, timestamp_iso: str | None = None):
    if timestamp_iso is None:
      dtime_now = datetime.datetime.now(datetime.timezone.utc)
      timestamp_iso = dtime_now.isoformat().replace('+00:00', 'Z')
    text_content = ''.join(self._text_segments)
    record = {
      '$type': 'app.bsky.feed.post',
      'createdAt': timestamp_iso,
      'text': text_content,
    }
    if self._langs:
      record['langs'] = list(self._langs)
    if self._facets:
      record['facets'] = list(self._facets)
    msg_hdrs = {'Authorization': 'Bearer ' + self._creds.auth_token}
    msg_data = {
      'collection': 'app.bsky.feed.post',
      '$type': 'app.bsky.feed.post',
      'repo': self._creds.did,
      'record': record
    }
    msg_resp = requests.post(
      f'{self._creds.host}/xrpc/com.atproto.repo.createRecord',
      json=msg_data,
      headers=msg_hdrs
    )
    msg_resp.raise_for_status()
    

def main():
  creds = Credentials.from_jsonfile(sys.argv[1])
  builder = PostBuilder(creds)
  builder.add_text('your butt smells like a butt')
  builder.post()


if __name__ == '__main__':
  main()