# Demo assets and third-party UI

All accounts, channel text, titles and comments seeded by this project are demonstration data. Demo videos are eight-second photographic studies generated specifically for the assignment with FFmpeg: a slow pan/zoom of a photograph and a quiet synthesized tone. They are not recordings of the described place or full tutorial content. There are no third-party video embeds, playback URLs or network requests in the demo UI.

Photographs: Unsplash, under the [Unsplash License](https://unsplash.com/license). Exact image source URLs are preserved in assets/demo/sources.json. The images are bundled for use inside the video demonstration, not sold as a standalone photo library. No endorsement or affiliation is implied.

Video generation: FFmpeg; source recipe in scripts/generate_demo.py. FFmpeg itself is installed as an operating-system dependency, not bundled as a binary in the source ZIP. Its license is determined by the distribution build.

The interface deliberately follows YouTube for the assignment. YouTube is a trademark of Google LLC; this is an independent educational implementation, not a Google service. The play mark is a small original SVG approximation for the exercise.

Outline icons are simple adaptations of the MIT-licensed [Tabler Icons](https://github.com/tabler/tabler-icons). Copyright (c) 2020–2026 Paweł Kuna. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the Software), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: the above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Swagger UI 5.17.14 is vendored in frontend/vendor under Apache License 2.0; its upstream LICENSE is included in that directory. This lets /docs work without an external CDN.
