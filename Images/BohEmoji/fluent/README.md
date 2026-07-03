# BOH Fluent Emoji Assets

These PNGs are a 24x24 runtime copy of Microsoft's Fluent Emoji 3D set:

https://github.com/microsoft/fluentui-emoji

They are copied beside `bohcustoms.dll` at runtime under:

`BohEmoji\fluent\`

`manifest.tsv` maps supported shortcode/raw-Unicode tokens to PNG filenames.
Canonical shortcodes use the Fluent filename without `_3d`, for example
`:red_heart:`, `:money_bag:`, and `:artist_dark:`.

The upstream license text is kept in this folder as
`LICENSE.Microsoft-Fluent-Emoji.txt`.
