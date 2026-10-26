# `bgsky`, BG's Bluesky library

I am Brian Gawalt (BG?) and I write some bots who post to Bluesky.  This library
is just a single file I can use to centralize (lol) all their ATProto
operations.

There's lots of Python APIs to BSky and the ATmosphere, but this one is mine.
I don't expect anyone to use this. (Although I would absolutely welcome them to
do so!)  Part of that expectation is that it's not set up as a module per se;
it's just a single file I can `cp` into a particular bot's code base and make
use of it.

Any time you do make use of it, you will need one (1) dependency:

```
pip3 install requests
```

I like building over buying, but not even I want to roll my own TLS handshaker.